"""
Подготовка RAG-документов (чанков) из результата пайплайна и запись в rag_documents.

Чанкирование по full_text (рекурсивно: абзацы → строки → предложения), payload = title + chunk_text.
Эмбеддинги по каждому чанку, upsert по (collection_id, link, chunk_index).
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import pandas as pd

from config.config import (
    DEFAULT_EMBED_BATCH_SIZE,
    RAG_CHUNK_MAX_TOKENS,
    RAG_CHUNK_OVERLAP_TOKENS,
)

from .chunking import chunk_text_recursive
from .tools.db_state import delete_rag_documents_by_links, upsert_rag_documents

logger = logging.getLogger(__name__)


def _build_chunk_payload(title: str, chunk_text: str) -> str:
    """Формирует text_payload для чанка: заголовок + текст чанка."""
    title = (title or "").strip()
    chunk_text = (chunk_text or "").strip()
    if title and chunk_text:
        return f"{title}\n\n{chunk_text}"
    return chunk_text or title or " "


def prepare_rag_documents_from_df(
    df: pd.DataFrame,
    collection: Dict[str, Any],
    tokenizer: Any,
    max_tokens: int = RAG_CHUNK_MAX_TOKENS,
    overlap_tokens: int = RAG_CHUNK_OVERLAP_TOKENS,
) -> List[Dict]:
    """
    Преобразует df_relevant в список чанков для записи в rag_documents.

    По каждой статье: если есть full_text — рекурсивное чанкирование; иначе один псевдо-чанк (title + summary).
    Каждый элемент: link, chunk_index, title, summary, source, published_at, text_payload, embed_similarity_to_topic.
    Поле embedding заполняется в prepare_and_upsert_rag_documents.
    """
    collection_id = collection.get("id")
    if collection_id is None:
        return []
    discipline = collection.get("discipline")
    ga = collection.get("ga")
    activity = collection.get("activity")
    docs: List[Dict] = []
    for _, row in df.iterrows():
        link = row.get("link")
        if not link:
            continue
        title = (row.get("title") or "").strip()
        summary = (row.get("summary") or "").strip()
        source = (row.get("source") or "").strip()
        published_at = row.get("published_dt")
        embed_sim = float(row["embed_similarity"]) if "embed_similarity" in row else None
        full_text = row.get("full_text")

        if full_text and isinstance(full_text, str) and full_text.strip():
            chunks = chunk_text_recursive(
                full_text.strip(),
                tokenizer=tokenizer,
                max_tokens=max_tokens,
                overlap_tokens=overlap_tokens,
            )
            if not chunks:
                # fallback: один чанк из всего текста (обрезаем по токенам не делаем — уже внутри чанкера)
                chunks = [full_text.strip()[: 2048]]  # на случай сбоя чанкера
        else:
            # Нет full_text — один псевдо-чанк: в цикле ниже payload = title + "\n\n" + summary
            if not title and not summary:
                continue
            chunks = [summary if summary else ""]

        for chunk_index, chunk_text in enumerate(chunks):
            text_payload = _build_chunk_payload(title, chunk_text)
            docs.append({
                "link": link,
                "chunk_index": chunk_index,
                "title": title,
                "summary": summary,
                "source": source,
                "published_at": published_at,
                "text_payload": text_payload,
                "embed_similarity_to_topic": embed_sim,
            })
    return docs


def prepare_and_upsert_rag_documents(
    conn,
    collection: Dict[str, Any],
    df_relevant: pd.DataFrame,
    model=None,
    batch_size: int = DEFAULT_EMBED_BATCH_SIZE,
    max_tokens: int = RAG_CHUNK_MAX_TOKENS,
    overlap_tokens: int = RAG_CHUNK_OVERLAP_TOKENS,
) -> int:
    """
    Строит RAG-чанки из df_relevant, считает эмбеддинги и записывает в rag_documents.

    Args:
        conn: Подключение к PostgreSQL (если None — запись не выполняется).
        collection: Объект коллекции с id, discipline, ga, activity.
        df_relevant: DataFrame с колонками title, link, source, published_dt, full_text, summary, embed_similarity.
        model: SentenceTransformer для эмбеддингов; если None — загружается через get_embedding_model().
        batch_size: Размер батча для encode.
        max_tokens: Максимум токенов на чанк.
        overlap_tokens: Перекрытие между соседними чанками (токенов).

    Returns:
        Количество записанных строк (чанков); 0 при conn=None или пустом df.
    """
    if conn is None or df_relevant is None or df_relevant.empty:
        return 0
    if collection is None or collection.get("id") is None:
        return 0

    if model is None:
        from .embedding_filter import get_embedding_model
        model = get_embedding_model()

    tokenizer = getattr(model, "tokenizer", None)
    if tokenizer is None and hasattr(model, "tokenizer"):
        tokenizer = model.tokenizer
    if tokenizer is None:
        try:
            from transformers import AutoTokenizer
            from config.config import EMBEDDING_MODEL_NAME
            tokenizer = AutoTokenizer.from_pretrained(EMBEDDING_MODEL_NAME)
        except Exception as e:
            logger.warning("Токенайзер для чанкирования недоступен, используем приближение по символам: %s", e)
            tokenizer = None

    docs = prepare_rag_documents_from_df(
        df_relevant,
        collection,
        tokenizer=tokenizer,
        max_tokens=max_tokens,
        overlap_tokens=overlap_tokens,
    )
    if not docs:
        return 0

    texts = [d["text_payload"] for d in docs]
    embeddings = model.encode(
        texts,
        batch_size=batch_size,
        show_progress_bar=False,
        normalize_embeddings=True,
    )
    for i, d in enumerate(docs):
        d["embedding"] = embeddings[i].tolist()

    # Удаляем старые чанки по статьям, которые обновляем (чтобы не оставались лишние чанки)
    links_to_replace = list({d["link"] for d in docs})
    delete_rag_documents_by_links(conn, collection["id"], links_to_replace)

    count = upsert_rag_documents(
        conn,
        collection_id=collection["id"],
        discipline=collection.get("discipline"),
        ga=collection.get("ga"),
        activity=collection.get("activity"),
        documents=docs,
    )
    logger.info(
        "RAG: записано чанков в коллекцию %s: %d (статей: %d)",
        collection.get("id"),
        count,
        len(df_relevant),
    )
    return count
