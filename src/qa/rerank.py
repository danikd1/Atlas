"""
Rerank с cross-encoder поверх результата retrieval.

Шаг 4.4 из плана: переранжировать top-K чанков по запросу и иметь возможность
увидеть, что именно поднялось/отфильтровалось.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List, Optional, Sequence, Tuple

from sentence_transformers import CrossEncoder

from config.config import QA_RERANK_MODEL_NAME
from src.qa.retrieval import RetrievedChunk, embed_query, retrieve_chunks
from src.tools.db_state import get_connection


_RERANK_MODEL: Optional[CrossEncoder] = None


def get_rerank_model(model_name: str = QA_RERANK_MODEL_NAME) -> CrossEncoder:
    """
    Ленивая загрузка cross-encoder модели для rerank.
    """
    global _RERANK_MODEL
    if _RERANK_MODEL is None:
        _RERANK_MODEL = CrossEncoder(model_name)
    return _RERANK_MODEL


@dataclass
class RerankedChunk:
    chunk: RetrievedChunk
    score: float  # score cross-encoder'а (больше = лучше)


def rerank_chunks(
    query: str,
    chunks: Sequence[RetrievedChunk],
    top_k_rerank: int = 10,
    model: Optional[CrossEncoder] = None,
) -> List[RerankedChunk]:
    """
    Переранжирует список чанков по score cross-encoder'а.

    Args:
        query: текст вопроса пользователя.
        chunks: список чанков, полученных из retrieval.
        top_k_rerank: сколько чанков вернуть после rerank.
        model: опционально уже загруженная модель CrossEncoder.

    Returns:
        Список RerankedChunk, отсортированный по убыванию score, длиной до top_k_rerank.
    """
    if not chunks:
        return []
    if model is None:
        model = get_rerank_model()

    # CrossEncoder ожидает пары (query, text)
    pairs = [(query, ch.text_payload) for ch in chunks]
    scores = model.predict(pairs)

    reranked: List[RerankedChunk] = [
        RerankedChunk(chunk=ch, score=float(s)) for ch, s in zip(chunks, scores)
    ]
    reranked.sort(key=lambda x: x.score, reverse=True)
    return reranked[: top_k_rerank]


def print_rerank_comparison(
    query: str,
    collection_id: int,
    top_k_retrieval: int = 30,
    top_k_rerank: int = 10,
    snippet_chars: int = 200,
) -> None:
    """
    Вспомогательная функция для терминала:
    - делает retrieval (top_k_retrieval),
    - применяет rerank,
    - печатает, какие чанки попали в top_k_rerank, а какие были отброшены.

    Пример:

        python -m src.qa.rerank "мой вопрос" 13 30 10
    """
    conn = get_connection()
    if conn is None:
        print("PostgreSQL отключён или недоступен.")
        return

    # Используем ту же модель эмбеддингов, что и retrieval
    model, q_emb = embed_query(query)
    retrieved = retrieve_chunks(
        conn,
        q_emb,
        collection_id=collection_id,
        top_k=top_k_retrieval,
    )
    if not retrieved:
        print("Retrieval вернул 0 чанков.")
        return

    reranked = rerank_chunks(query, retrieved, top_k_rerank=top_k_rerank)
    top_set = { (rc.chunk.link, rc.chunk.chunk_index) for rc in reranked }

    print(f"Query: {query!r}, collection_id={collection_id}")
    print(f"Retrieval: {len(retrieved)} чанков, Rerank: top-{len(reranked)}")
    print("=" * 80)
    print("TOP после rerank:")
    print("-" * 80)
    for i, rc in enumerate(reranked, 1):
        ch = rc.chunk
        snippet = ch.text_payload.replace("\n", " ")[:snippet_chars]
        print(f"[{i}] score={rc.score:.4f} link={ch.link} chunk_index={ch.chunk_index}")
        if ch.title:
            print(f"     title: {ch.title}")
        if ch.published_at:
            print(f"     published_at: {ch.published_at}")
        print(f"     snippet: {snippet}")
        print("-" * 80)

    print()
    print("Отброшенные чанки (есть в retrieval, нет в top rerank):")
    print("-" * 80)
    for i, ch in enumerate(retrieved, 1):
        key = (ch.link, ch.chunk_index)
        if key in top_set:
            continue
        snippet = ch.text_payload.replace("\n", " ")[:snippet_chars]
        print(f"[retrieval #{i}] link={ch.link} chunk_index={ch.chunk_index}")
        if ch.title:
            print(f"     title: {ch.title}")
        if ch.published_at:
            print(f"     published_at: {ch.published_at}")
        print(f"     snippet: {snippet}")
        print("-" * 80)


def _parse_args(argv: Sequence[str]) -> Optional[Tuple[str, int, int, int]]:
    """
    Простой парсер аргументов для запуска через `python -m src.qa.rerank`.
    Ожидает: query collection_id [top_k_retrieval] [top_k_rerank]
    """
    if len(argv) < 3:
        return None
    query = argv[1]
    try:
        collection_id = int(argv[2])
    except ValueError:
        return None
    top_k_retrieval = 30
    top_k_rerank = 10
    if len(argv) >= 4:
        try:
            top_k_retrieval = int(argv[3])
        except ValueError:
            top_k_retrieval = 30
    if len(argv) >= 5:
        try:
            top_k_rerank = int(argv[4])
        except ValueError:
            top_k_rerank = 10
    return query, collection_id, top_k_retrieval, top_k_rerank


if __name__ == "__main__":
    import sys
    from typing import Sequence  # локальный импорт для type hints

    parsed = _parse_args(sys.argv)
    if not parsed:
        print("Usage: python -m src.qa.rerank \"your question\" <collection_id> [top_k_retrieval] [top_k_rerank]")
        sys.exit(1)
    q, cid, k_ret, k_rr = parsed
    print_rerank_comparison(q, cid, top_k_retrieval=k_ret, top_k_rerank=k_rr)

