# -*- coding: utf-8 -*-
"""
QA по лентам пользователя — без RAG-коллекций.

Алгоритм:
1. Загружаем статьи из processed_articles по feed_ids.
2. Формируем текстовые «чанки»: title + ai_summary (или summary).
3. Эмбеддируем запрос и чанки (та же модель, что и RAG).
4. Сортируем по косинусной близости, берём top_k.
5. Строим промпт и вызываем GigaChat.
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
    article_count: int  # сколько статей было в контексте


def _cosine_sim(a: List[float], b: List[float]) -> float:
    va = np.array(a, dtype=np.float32)
    vb = np.array(b, dtype=np.float32)
    denom = (np.linalg.norm(va) * np.linalg.norm(vb))
    if denom == 0:
        return 0.0
    return float(np.dot(va, vb) / denom)


def answer_question_by_feeds(
    query: str,
    feed_ids: List[int],
    options: Optional[FeedQAOptions] = None,
) -> FeedQAResult:
    """QA по статьям из заданных лент без RAG."""
    if options is None:
        options = FeedQAOptions()

    conn = get_connection()
    rows = get_articles_by_feed_ids(
        conn,
        feed_ids,
        from_date=options.from_date,
        to_date=options.to_date,
        limit=200,
    )

    if not rows:
        return FeedQAResult(
            answer="Статей по выбранным лентам за указанный период не найдено.",
            sources=[],
            article_count=0,
        )

    # Строим текстовые представления статей
    texts = []
    for row in rows:
        text = row.get("title") or ""
        body = row.get("ai_summary") or row.get("summary") or ""
        if body:
            text = f"{text}\n{body}"
        texts.append(text.strip())

    # Эмбеддируем запрос и все статьи
    model = get_embedding_model(EMBEDDING_MODEL_NAME)
    query_emb = model.encode([query], normalize_embeddings=True)[0].tolist()
    article_embs = model.encode(texts, normalize_embeddings=True, batch_size=32, show_progress_bar=False)

    # Ранжируем по косинусной близости
    scores = [_cosine_sim(query_emb, emb.tolist()) for emb in article_embs]
    ranked = sorted(zip(scores, rows, texts), key=lambda x: x[0], reverse=True)
    top = ranked[: options.top_k]

    # Формируем контекст для LLM
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
        sources.append(
            FeedQASource(
                link=row.get("link") or "",
                title=row.get("title") or "",
                feed_name=feed_name,
                published_at=row.get("published_at"),
                snippet=snippet[:300],
                article_id=row.get("id") or 0,
            )
        )

    context_block = "\n".join(context_lines)

    if options.language == "en":
        system_msg = (
            "You are a helpful assistant. Answer the question using ONLY the provided article fragments. "
            "If you don't have enough information, say so."
        )
        user_msg = (
            f"Article fragments:\n\n{context_block}\n\n"
            f"Question: {query}\n\n"
            "Answer in English. Reference fragments by [number] when relevant."
        )
    else:
        system_msg = (
            "Ты — помощник, отвечающий ИСКЛЮЧИТЕЛЬНО на основе приведённых фрагментов статей. "
            "Если информации недостаточно — прямо скажи об этом. "
            "Ссылайся на номер фрагмента в квадратных скобках."
        )
        user_msg = (
            f"Фрагменты статей:\n\n{context_block}\n\n"
            f"Вопрос: {query}\n\n"
            "Ответь по-русски. Если опираешься на фрагмент — упоминай его номер [N]."
        )

    client = create_gigachat_client()
    try:
        result = client.chat({
            "messages": [
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_msg},
            ],
            "temperature": 0.1,
        })
        answer_text = (result.choices[0].message.content or "").strip()
    except Exception as e:
        logger.exception("FeedQA: ошибка LLM: %s", e)
        answer_text = f"Ошибка при обращении к LLM: {e}"

    return FeedQAResult(
        answer=answer_text,
        sources=sources,
        article_count=len(rows),
    )
