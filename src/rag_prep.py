"""
Подготовка RAG-документов из результата пайплайна и запись в rag_documents.

Строит text_payload (заголовок + full_text или summary), считает эмбеддинги
и выполняет upsert в таблицу rag_documents для текущей коллекции.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import pandas as pd

from config.config import DEFAULT_EMBED_BATCH_SIZE

from .tools.db_state import upsert_rag_documents

logger = logging.getLogger(__name__)

# Максимальная длина text_payload для эмбеддинга (обрезание long full_text)
RAG_PAYLOAD_MAX_CHARS = 12_000


def build_text_payload(row: pd.Series) -> str:
    """
    Формирует текст для эмбеддинга: заголовок + полный текст или выжимка.

    Если есть full_text — берётся префикс до RAG_PAYLOAD_MAX_CHARS символов;
    иначе используется summary.
    """
    title = (row.get("title") or "").strip()
    full_text = row.get("full_text")
    summary = (row.get("summary") or "").strip()
    if full_text and isinstance(full_text, str) and full_text.strip():
        body = full_text.strip()
        if len(body) > RAG_PAYLOAD_MAX_CHARS:
            body = body[: RAG_PAYLOAD_MAX_CHARS] + "..."
        text = f"{title}\n\n{body}" if title else body
    else:
        text = f"{title}\n\n{summary}" if title else summary
    return text or " "


def prepare_rag_documents_from_df(
    df: pd.DataFrame,
    collection: Dict[str, Any],
) -> List[Dict]:
    """
    Преобразует df_relevant в список словарей для записи в rag_documents.

    Каждый элемент содержит: link, title, summary, source, published_at,
    text_payload, embed_similarity_to_topic. Поле embedding заполняется отдельно.
    """
    collection_id = collection.get("id")
    if collection_id is None:
        return []
    discipline = collection.get("discipline")
    ga = collection.get("ga")
    activity = collection.get("activity")
    docs = []
    for _, row in df.iterrows():
        link = row.get("link")
        if not link:
            continue
        published_at = row.get("published_dt")
        docs.append({
            "link": link,
            "title": (row.get("title") or "").strip(),
            "summary": (row.get("summary") or "").strip(),
            "source": (row.get("source") or "").strip(),
            "published_at": published_at,
            "text_payload": build_text_payload(row),
            "embed_similarity_to_topic": float(row["embed_similarity"]) if "embed_similarity" in row else None,
        })
    return docs


def prepare_and_upsert_rag_documents(
    conn,
    collection: Dict[str, Any],
    df_relevant: pd.DataFrame,
    model=None,
    batch_size: int = DEFAULT_EMBED_BATCH_SIZE,
) -> int:
    """
    Строит RAG-документы из df_relevant, считает эмбеддинги и записывает в rag_documents.

    Args:
        conn: Подключение к PostgreSQL (если None — запись не выполняется).
        collection: Объект коллекции с id, discipline, ga, activity.
        df_relevant: DataFrame с колонками title, link, source, published_dt, full_text, summary, embed_similarity.
        model: SentenceTransformer для эмбеддингов; если None — загружается через get_embedding_model().
        batch_size: Размер батча для encode.

    Returns:
        Количество записанных документов (0 при conn=None или пустом df).
    """
    if conn is None or df_relevant is None or df_relevant.empty:
        return 0
    if collection is None or collection.get("id") is None:
        return 0

    docs = prepare_rag_documents_from_df(df_relevant, collection)
    if not docs:
        return 0

    if model is None:
        from .embedding_filter import get_embedding_model
        model = get_embedding_model()

    texts = [d["text_payload"] for d in docs]
    embeddings = model.encode(
        texts,
        batch_size=batch_size,
        show_progress_bar=False,
        normalize_embeddings=True,
    )
    for i, d in enumerate(docs):
        d["embedding"] = embeddings[i].tolist()

    count = upsert_rag_documents(
        conn,
        collection_id=collection["id"],
        discipline=collection.get("discipline"),
        ga=collection.get("ga"),
        activity=collection.get("activity"),
        documents=docs,
    )
    logger.info("RAG: записано документов в коллекцию %s: %d", collection.get("id"), count)
    return count
