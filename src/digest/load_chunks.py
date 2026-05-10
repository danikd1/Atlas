"""
Загрузка чанков коллекции из rag_documents для дайджеста.

Без векторного запроса — все чанки по collection_id (и опционально по датам).
Эмбеддинги уже лежат в БД, только читаем.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, List, Optional

import numpy as np

from config.config import (
    POSTGRES_ENABLED,
    POSTGRES_TABLE_RAG_DOCUMENTS,
)
from src.tools.db_state import get_connection


def _embedding_from_row(row: Any) -> Optional[List[float]]:
    """Достаёт вектор эмбеддинга из строки БД (pgvector может вернуть list или str)."""
    emb = row.get("embedding")
    return parse_embedding(emb)


def parse_embedding(value: Any) -> Optional[List[float]]:
    """Парсит значение pgvector (list, tuple или строку '[0.1,0.2,...]') в list[float].
    Переиспользуется в pipeline.py и feed_digest.py чтобы не дублировать логику.
    """
    if value is None:
        return None
    if isinstance(value, (list, tuple)):
        return [float(x) for x in value]
    if isinstance(value, str):
        s = value.strip()
        if s.startswith("[") and s.endswith("]"):
            s = s[1:-1]
        if not s:
            return None
        return [float(x.strip()) for x in s.split(",")]
    return None


# Стандартный разделитель для текста title + ai_summary.
# Используется при сохранении кэша (rag_indexer) и при чтении (BERTopic, дайджест).
SUMMARY_TEXT_SEP = ". "


def make_summary_text(title: str, summary: str) -> str:
    """Формирует текст title + ai_summary для эмбеддирования. Единый формат для кэша и потребителей."""
    title = (title or "").strip()
    summary = (summary or "").strip()
    if title and summary:
        return f"{title}{SUMMARY_TEXT_SEP}{summary}"
    return title or summary or "—"


def mix_embeddings(
    texts: List[str],
    cached: List[Optional[np.ndarray]],
    encode_fn,
) -> np.ndarray:
    """Смешанный режим: берёт эмбеддинги из кэша где есть, досчитывает остаток через encode_fn.

    Args:
        texts: тексты для эмбеддирования (используются только для отсутствующих в кэше)
        cached: список кэшированных эмбеддингов (None если нет кэша)
        encode_fn: callable(list[str]) -> np.ndarray — функция кодирования

    Returns:
        np.ndarray shape (len(texts), embedding_dim)
    """
    result: List[Optional[np.ndarray]] = list(cached)
    missing_indices, missing_texts = [], []

    for i, emb in enumerate(cached):
        if emb is None:
            missing_indices.append(i)
            missing_texts.append(texts[i])

    if missing_texts:
        fresh = encode_fn(missing_texts)
        for idx, emb in zip(missing_indices, fresh):
            result[idx] = emb

    return np.array(result, dtype="float32")


@dataclass
class ChunkRow:
    """Один чанк из rag_documents с эмбеддингом для кластеризации."""
    id: int
    collection_id: int
    link: str
    chunk_index: int
    title: str
    summary: str
    source: str
    published_at: Optional[datetime]
    text_payload: str
    embed_similarity_to_topic: Optional[float]
    embedding: Optional[List[float]]


def load_chunks_for_collection(
    conn,
    collection_id: int,
    from_date: Optional[datetime] = None,
    to_date: Optional[datetime] = None,
) -> List[ChunkRow]:
    """
    Загружает все чанки коллекции из rag_documents с эмбеддингами.

    Args:
        conn: подключение к PostgreSQL (DictCursor).
        collection_id: id коллекции.
        from_date, to_date: опциональные границы по published_at.

    Returns:
        Список ChunkRow. Чанки без эмбеддинга пропускаются (не годятся для кластеризации).
    """
    if conn is None or not POSTGRES_ENABLED:
        return []

    conditions = ["collection_id = %s", "embedding IS NOT NULL"]
    params: List[Any] = [collection_id]
    if from_date is not None:
        conditions.append("published_at >= %s")
        params.append(from_date)
    if to_date is not None:
        conditions.append("published_at <= %s")
        params.append(to_date)
    where = " AND ".join(conditions)

    sql = f"""
        SELECT id, collection_id, link, chunk_index, title, summary, source,
               published_at, text_payload, embed_similarity_to_topic, embedding
        FROM {POSTGRES_TABLE_RAG_DOCUMENTS}
        WHERE {where}
        ORDER BY link, chunk_index;
    """
    out: List[ChunkRow] = []
    with conn.cursor() as cur:
        cur.execute(sql, params)
        for row in cur.fetchall():
            emb = _embedding_from_row(row)
            if emb is None:
                continue
            out.append(
                ChunkRow(
                    id=row["id"],
                    collection_id=row["collection_id"],
                    link=row["link"] or "",
                    chunk_index=int(row["chunk_index"] or 0),
                    title=(row.get("title") or "").strip(),
                    summary=(row.get("summary") or "").strip(),
                    source=(row.get("source") or "").strip(),
                    published_at=row.get("published_at"),
                    text_payload=(row.get("text_payload") or "").strip(),
                    embed_similarity_to_topic=row.get("embed_similarity_to_topic"),
                    embedding=emb,
                )
            )
    return out
