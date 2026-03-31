"""
Retrieval по коллекции (без rerank).

Шаг 4.3 из плана: вернуть top-K чанков по запросу и дать возможность
посмотреть результат глазами через терминал.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence, Tuple

import psycopg2

from config.config import (
    EMBEDDING_MODEL_NAME,
    POSTGRES_ENABLED,
    POSTGRES_TABLE_RAG_DOCUMENTS,
)
from src.pipeline.embedding_filter import get_embedding_model
from src.tools.db_state import get_connection


@dataclass
class RetrievedChunk:
    collection_id: int
    link: str
    chunk_index: int
    title: str
    summary: str
    source: str
    published_at: Optional[datetime]
    text_payload: str
    embed_similarity_to_topic: Optional[float]
    distance: float  # pgvector distance (меньше = ближе)


def _embedding_to_vector_str(embedding: Sequence[float]) -> str:
    """Форматирует вектор для pgvector: '[0.1,0.2,...]'."""
    return "[" + ",".join(str(float(x)) for x in embedding) + "]"


def embed_query(
    query: str,
    model: Optional[Any] = None,
) -> Tuple[Any, List[float]]:
    """
    Строит эмбеддинг запроса той же моделью, что и чанки.

    Returns:
        (model, embedding_list)
    """
    if model is None:
        model = get_embedding_model(EMBEDDING_MODEL_NAME)
    # На старте без специальных префиксов; при смене модели (E5 и т.п.)
    # сюда можно добавить "query: " + query.
    emb = model.encode([query], normalize_embeddings=True)[0]
    return model, emb.tolist()


def retrieve_chunks(
    conn,
    query_embedding: Sequence[float],
    collection_id: int,
    top_k: int = 30,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
) -> List[RetrievedChunk]:
    """
    Выполняет векторный поиск по чанкам коллекции в rag_documents.

    Args:
        conn: подключение к PostgreSQL (если None или POSTGRES_DISABLED — возвращает пустой список).
        query_embedding: вектор запроса (List[float]).
        collection_id: идентификатор коллекции.
        top_k: сколько чанков вернуть.
        date_from/date_to: опциональные границы по published_at.

    Returns:
        Список RetrievedChunk, отсортированный по возрастанию distance.
    """
    if conn is None or not POSTGRES_ENABLED:
        return []
    if not query_embedding:
        return []

    emb_str = _embedding_to_vector_str(query_embedding)

    conditions = ["collection_id = %s"]
    params: List[Any] = [collection_id]

    if date_from is not None:
        conditions.append("published_at >= %s")
        params.append(date_from)
    if date_to is not None:
        conditions.append("published_at <= %s")
        params.append(date_to)

    where_clause = " AND ".join(conditions)
    # Порядок плейсхолдеров: сначала вектор (distance/ORDER BY), потом условия WHERE, потом LIMIT.
    # emb_str используется дважды: для distance и для ORDER BY.
    params_for_query = [emb_str] + params + [emb_str, top_k]

    sql = f"""
        SELECT
            collection_id,
            link,
            chunk_index,
            title,
            summary,
            source,
            published_at,
            text_payload,
            embed_similarity_to_topic,
            (embedding <-> %s::vector) AS distance
        FROM {POSTGRES_TABLE_RAG_DOCUMENTS}
        WHERE {where_clause}
        ORDER BY embedding <-> %s::vector
        LIMIT %s;
    """

    chunks: List[RetrievedChunk] = []
    with conn.cursor() as cur:
        cur.execute(sql, params_for_query)
        rows = cur.fetchall()
        for row in rows:
            chunks.append(
                RetrievedChunk(
                    collection_id=row["collection_id"],
                    link=row["link"],
                    chunk_index=row["chunk_index"],
                    title=row.get("title") or "",
                    summary=row.get("summary") or "",
                    source=row.get("source") or "",
                    published_at=row.get("published_at"),
                    text_payload=row.get("text_payload") or "",
                    embed_similarity_to_topic=row.get("embed_similarity_to_topic"),
                    distance=float(row["distance"]) if row.get("distance") is not None else 0.0,
                )
            )
    return chunks


def print_retrieved_chunks(
    query: str,
    collection_id: int,
    top_k: int = 10,
    snippet_chars: int = 300,
) -> None:
    """
    Вспомогательная функция для терминала: выводит top-K чанков по запросу.

    Пример использования:

        python -m src.qa.retrieval \"my question\" 1
    """
    conn = get_connection()
    if conn is None:
        print("PostgreSQL отключён или недоступен (POSTGRES_ENABLED=False или нет подключения).")
        return

    model, q_emb = embed_query(query)
    chunks = retrieve_chunks(conn, q_emb, collection_id=collection_id, top_k=top_k)

    print(f"Query: {query!r}, collection_id={collection_id}, top_k={top_k}")
    print(f"Found chunks: {len(chunks)}")
    print("-" * 80)
    for idx, ch in enumerate(chunks, 1):
        snippet = ch.text_payload.replace("\n", " ")[:snippet_chars]
        print(f"[{idx}] distance={ch.distance:.4f} link={ch.link} chunk_index={ch.chunk_index}")
        if ch.title:
            print(f"     title: {ch.title}")
        if ch.published_at:
            print(f"     published_at: {ch.published_at}")
        print(f"     snippet: {snippet}")
        print("-" * 80)


def _parse_args(argv: Sequence[str]) -> Optional[Tuple[str, int, int]]:
    """
    Очень простой парсер аргументов для запуска через `python -m src.qa.retrieval`.
    Ожидает: query collection_id [top_k]
    """
    if len(argv) < 3:
        return None
    query = argv[1]
    try:
        collection_id = int(argv[2])
    except ValueError:
        return None
    top_k = 10
    if len(argv) >= 4:
        try:
            top_k = int(argv[3])
        except ValueError:
            top_k = 10
    return query, collection_id, top_k


if __name__ == "__main__":
    import sys

    parsed = _parse_args(sys.argv)
    if not parsed:
        print("Usage: python -m src.qa.retrieval \"your question\" <collection_id> [top_k]")
        sys.exit(1)
    q, cid, k = parsed
    print_retrieved_chunks(q, cid, top_k=k)

