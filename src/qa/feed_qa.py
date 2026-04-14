# -*- coding: utf-8 -*-
"""
QA по лентам пользователя.

Три пути:
1. BERTopic (collection_id задан) — in-memory similarity по статьям коллекции.
2. RAG (feed_ids + чанки есть в rag_documents) — pgvector поиск по глобальной коллекции.
3. In-memory fallback (feed_ids + rag_documents пуста) — in-memory cosine similarity по title+ai_summary.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

import numpy as np

from config.config import EMBEDDING_MODEL_NAME
from src.pipeline.embedding_filter import get_embedding_model
from src.tools.db_state import get_articles_by_feed_ids, get_connection
from src.tools.llm_utils import clean_text_for_llm, create_gigachat_client

logger = logging.getLogger(__name__)


@dataclass
class FeedQAOptions:
    top_k: int = 12
    from_date: Optional[datetime] = None
    to_date: Optional[datetime] = None
    language: str = "ru"
    gigachat_credentials: Optional[str] = None
    gigachat_model: Optional[str] = None


@dataclass
class FeedQASource:
    link: str
    title: str
    feed_name: str
    published_at: Optional[datetime]
    snippet: str
    article_id: int = 0


@dataclass
class FeedQAResult:
    answer: str
    sources: List[FeedQASource]
    article_count: int  # сколько статей/чанков было в контексте


def _cosine_sim(a: List[float], b: List[float]) -> float:
    va = np.array(a, dtype=np.float32)
    vb = np.array(b, dtype=np.float32)
    denom = (np.linalg.norm(va) * np.linalg.norm(vb))
    if denom == 0:
        return 0.0
    return float(np.dot(va, vb) / denom)


def _build_prompt(query: str, context_block: str, language: str) -> list[dict]:
    if language == "en":
        return [
            {
                "role": "system",
                "content": (
                    "You are a helpful assistant. Answer the question using ONLY the provided article fragments. "
                    "If you don't have enough information, say so."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Article fragments:\n\n{context_block}\n\n"
                    f"Question: {query}\n\n"
                    "Answer in English. Reference fragments by [number] when relevant."
                ),
            },
        ]
    return [
        {
            "role": "system",
            "content": (
                "Ты — помощник, отвечающий ИСКЛЮЧИТЕЛЬНО на основе приведённых фрагментов статей. "
                "Если информации недостаточно — прямо скажи об этом. "
                "Ссылайся на номер фрагмента в квадратных скобках."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Фрагменты статей:\n\n{context_block}\n\n"
                f"Вопрос: {query}\n\n"
                "Ответь по-русски. Если опираешься на фрагмент — упоминай его номер [N]."
            ),
        },
    ]


def _call_gigachat(messages: list, options: FeedQAOptions) -> str:
    client = create_gigachat_client(credentials=options.gigachat_credentials, model=options.gigachat_model)
    try:
        result = client.chat({"messages": messages, "temperature": 0.1})
        return (result.choices[0].message.content or "").strip()
    except Exception as e:
        logger.exception("FeedQA: ошибка LLM: %s", e)
        return f"Ошибка при обращении к LLM: {e}"


# ── Путь 1: BERTopic ──────────────────────────────────────────────────────────

def _answer_via_bertopic(
    query: str,
    collection_id: int,
    options: FeedQAOptions,
    conn,
) -> FeedQAResult:
    """In-memory similarity по статьям BERTopic-коллекции."""
    from src.tools.db_state import get_articles_for_bertopic_collection

    rows = get_articles_for_bertopic_collection(
        conn, collection_id,
        from_date=options.from_date,
        to_date=options.to_date,
    )
    if not rows:
        return FeedQAResult(
            answer="Статей в этой коллекции за указанный период не найдено.",
            sources=[],
            article_count=0,
        )
    return _inmemory_similarity(query, rows, options)


# ── Путь 2: RAG (pgvector) ────────────────────────────────────────────────────

def _answer_via_rag(
    query: str,
    rag_collection_id: int,
    feed_ids: List[int],
    user_id: int,
    options: FeedQAOptions,
    conn,
) -> FeedQAResult:
    """pgvector поиск по глобальной RAG-коллекции с фильтром по лентам пользователя."""
    from src.qa.retrieval import embed_query, retrieve_chunks_by_feeds
    from src.qa.rerank import rerank_chunks

    _, q_emb = embed_query(query)
    chunks = retrieve_chunks_by_feeds(
        conn,
        q_emb,
        collection_id=rag_collection_id,
        feed_ids=feed_ids,
        user_id=user_id,
        top_k=40,
        date_from=options.from_date,
        date_to=options.to_date,
    )
    if not chunks:
        return FeedQAResult(
            answer="Нет релевантных фрагментов в RAG-индексе для ответа на вопрос.",
            sources=[],
            article_count=0,
        )

    try:
        reranked = rerank_chunks(query, chunks, top_k_rerank=options.top_k)
        top_chunks = [rc.chunk for rc in reranked]
    except Exception as e:
        logger.warning("FeedQA RAG: rerank недоступен (%s), используем retrieval порядок", e)
        top_chunks = chunks[: options.top_k]

    context_lines: List[str] = []
    sources: List[FeedQASource] = []
    seen_links: set = set()
    for idx, chunk in enumerate(top_chunks, 1):
        snippet = clean_text_for_llm(chunk.text_payload or "", max_chars=800)
        context_lines.append(
            f"[{idx}] {chunk.title}\n"
            f"Источник: {chunk.source} | {chunk.link}\n"
            f"{snippet}\n"
        )
        if chunk.link not in seen_links:
            seen_links.add(chunk.link)
            sources.append(FeedQASource(
                link=chunk.link,
                title=chunk.title,
                feed_name=chunk.source,
                published_at=chunk.published_at,
                snippet=snippet[:300],
                article_id=chunk.article_id,
            ))

    messages = _build_prompt(query, "\n".join(context_lines), options.language)
    answer_text = _call_gigachat(messages, options)

    return FeedQAResult(
        answer=answer_text,
        sources=sources,
        article_count=len(seen_links),
    )


# ── Путь 3: In-memory fallback ────────────────────────────────────────────────

def _answer_via_inmemory(
    query: str,
    feed_ids: List[int],
    options: FeedQAOptions,
    user_id: int,
    conn,
) -> FeedQAResult:
    """In-memory cosine similarity по title+ai_summary из processed_articles."""
    rows = get_articles_by_feed_ids(
        conn,
        feed_ids,
        from_date=options.from_date,
        to_date=options.to_date,
        limit=200,
        user_id=user_id,
    )
    if not rows:
        return FeedQAResult(
            answer="Статей по выбранным лентам за указанный период не найдено.",
            sources=[],
            article_count=0,
        )
    return _inmemory_similarity(query, rows, options)


def _inmemory_similarity(
    query: str,
    rows: List[Dict[str, Any]],
    options: FeedQAOptions,
) -> FeedQAResult:
    """Общая логика in-memory similarity — используется путями BERTopic и fallback."""
    texts = []
    for row in rows:
        text = row.get("title") or ""
        body = row.get("ai_summary") or row.get("summary") or ""
        if body:
            text = f"{text}\n{body}"
        texts.append(text.strip())

    model = get_embedding_model(EMBEDDING_MODEL_NAME)
    query_emb = model.encode([query], normalize_embeddings=True)[0].tolist()
    article_embs = model.encode(texts, normalize_embeddings=True, batch_size=32, show_progress_bar=False)

    scores = [_cosine_sim(query_emb, emb.tolist()) for emb in article_embs]
    ranked = sorted(zip(scores, rows, texts), key=lambda x: x[0], reverse=True)
    top = ranked[: options.top_k]

    context_lines: List[str] = []
    sources: List[FeedQASource] = []
    for idx, (score, row, text) in enumerate(top, 1):
        snippet = clean_text_for_llm(text, max_chars=800)
        feed_name = row.get("feed_name") or row.get("source") or ""
        context_lines.append(
            f"[{idx}] {row.get('title', '')}\n"
            f"Источник: {feed_name} | {row.get('link', '')}\n"
            f"{snippet}\n"
        )
        sources.append(FeedQASource(
            link=row.get("link") or "",
            title=row.get("title") or "",
            feed_name=feed_name,
            published_at=row.get("published_at"),
            snippet=snippet[:300],
            article_id=row.get("id") or 0,
        ))

    messages = _build_prompt(query, "\n".join(context_lines), options.language)
    answer_text = _call_gigachat(messages, options)

    return FeedQAResult(
        answer=answer_text,
        sources=sources,
        article_count=len(top),
    )


# ── Публичный API ─────────────────────────────────────────────────────────────

def answer_question_by_feeds(
    query: str,
    feed_ids: List[int],
    options: Optional[FeedQAOptions] = None,
    collection_id: Optional[int] = None,
    user_id: int = 0,
) -> FeedQAResult:
    """
    QA по статьям из заданных лент.

    Маршрутизация:
    - collection_id задан → путь BERTopic (in-memory по статьям коллекции)
    - feed_ids + чанки есть в rag_documents → путь RAG (pgvector)
    - иначе → путь in-memory fallback (cosine similarity по title+ai_summary)
    """
    if options is None:
        options = FeedQAOptions()

    conn = get_connection()

    # Путь 1: BERTopic-коллекция
    if collection_id is not None:
        return _answer_via_bertopic(query, collection_id, options, conn)

    # Путь 2 / 3: по лентам — RAG или in-memory
    # RAG включается только при 100% покрытии: все статьи с full_text уже проиндексированы.
    # Частичный индекс → in-memory по ai_summary всей ленты: полный охват важнее качества чанков.
    try:
        from src.tools.db_state import get_global_rag_collection, get_rag_chunk_count, get_rag_pending_for_feeds
        rag_collection = get_global_rag_collection(conn)
        if rag_collection and feed_ids:
            pending = get_rag_pending_for_feeds(conn, feed_ids, user_id)
            if pending == 0:
                chunk_count = get_rag_chunk_count(conn, rag_collection["id"], feed_ids, user_id)
                if chunk_count > 0:
                    return _answer_via_rag(query, rag_collection["id"], feed_ids, user_id, options, conn)
    except Exception as e:
        logger.warning("FeedQA: ошибка проверки RAG-индекса, fallback на in-memory: %s", e)

    # Путь 3: in-memory fallback
    return _answer_via_inmemory(query, feed_ids, options, user_id, conn)
