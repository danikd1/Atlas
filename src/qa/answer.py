"""
Ядро QA-ассистента: answer_question.

Использует:
- retrieval по коллекции (src.qa.retrieval.retrieve_chunks / embed_query)
- rerank с cross-encoder (src.qa.rerank.rerank_chunks)
- GigaChat (src.tools.llm_utils.create_gigachat_client) для генерации ответа.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

from config.config import DEFAULT_LLM_SLEEP
from src.qa.retrieval import RetrievedChunk, embed_query, retrieve_chunks
from src.qa.rerank import RerankedChunk, rerank_chunks
from src.tools.db_state import get_connection
from src.tools.llm_utils import clean_text_for_llm, create_gigachat_client


@dataclass
class AnswerOptions:
    top_k_retrieval: int = 40
    top_k_rerank: int = 10
    from_date: Optional[datetime] = None
    to_date: Optional[datetime] = None
    language: str = "ru"  # "ru" | "en"


@dataclass
class FragmentDoc:
    fragment_id: int  # индекс фрагмента в промпте (совпадает с [i] в ответе)
    link: str
    title: str
    summary: str
    published_at: Optional[datetime]
    snippet: str
    similarity: Optional[float]
    rerank_score: Optional[float]


@dataclass
class AnswerResult:
    answer: str
    fragments: List[FragmentDoc]
    sources: List[Dict[str, Any]]
    collection: Optional[dict[str, Any]]


def _load_collection_meta(conn, collection_id: int) -> Optional[dict[str, Any]]:
    """
    Загружает краткие метаданные коллекции по id (или None).
    """
    if conn is None:
        return None
    from config.config import POSTGRES_TABLE_COLLECTIONS

    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT id, name, discipline, ga, activity, collection_key,
                   created_at, updated_at, last_refreshed_at
            FROM {POSTGRES_TABLE_COLLECTIONS}
            WHERE id = %s;
            """,
            (collection_id,),
        )
        row = cur.fetchone()
        if not row:
            return None
        return {
            "id": row["id"],
            "name": row.get("name") or "",
            "discipline": row.get("discipline"),
            "ga": row.get("ga"),
            "activity": row.get("activity"),
            "collection_key": row.get("collection_key"),
            "created_at": row.get("created_at"),
            "updated_at": row.get("updated_at"),
            "last_refreshed_at": row.get("last_refreshed_at"),
        }


def _build_llm_prompt(
    query: str,
    fragments: List[FragmentDoc],
    language: str = "ru",
    max_chars_per_chunk: int = 1200,
) -> list[dict[str, str]]:
    """
    Строит messages для GigaChat: system + user с контекстом.
    """
    if language == "en":
        system_msg = (
            "You are a helpful assistant answering questions based only on the provided article fragments. "
            "Use the fragments as your only source of truth. "
            "If you don't have enough information, say so explicitly."
        )
    else:
        system_msg = (
            "Ты — помощник, отвечающий на вопросы ИСКЛЮЧИТЕЛЬНО на основе приведённых фрагментов статей. "
            "Если информации недостаточно, прямо скажи об этом. "
            "По возможности ссылайся на номер фрагмента и/или ссылку на статью."
        )

    context_lines: List[str] = []
    for frag in fragments:
        snippet_raw = frag.snippet or ""
        snippet_clean = clean_text_for_llm(snippet_raw, max_chars=max_chars_per_chunk)
        line_header = (
            f"[{frag.fragment_id}] title={frag.title!r}, "
            f"link={frag.link}, published_at={frag.published_at}"
        )
        context_lines.append(line_header)
        context_lines.append(snippet_clean)
        context_lines.append("")  # пустая строка между фрагментами

    context_block = "\n".join(context_lines).strip()

    if language == "en":
        user_msg = (
            "Use ONLY the following article fragments as context:\n\n"
            f"{context_block}\n\n"
            f"Question: {query}\n\n"
            "Answer in English. If you reference a fragment, mention its [number]."
        )
    else:
        user_msg = (
            "Используй ТОЛЬКО следующие фрагменты статей как контекст:\n\n"
            f"{context_block}\n\n"
            f"Вопрос: {query}\n\n"
            "Ответь по-русски. Если опираешься на конкретный фрагмент, упоминай его номер в квадратных скобках."
        )

    return [
        {"role": "system", "content": system_msg},
        {"role": "user", "content": user_msg},
    ]


def answer_question(
    query: str,
    collection_id: int,
    options: Optional[AnswerOptions] = None,
) -> AnswerResult:
    """
    Высокоуровневая функция QA-ассистента:
    - нормализует опции,
    - делает retrieval + rerank,
    - строит контекст и вызывает GigaChat,
    - возвращает AnswerResult.
    """
    conn = get_connection()
    if options is None:
        options = AnswerOptions()

    collection_meta = _load_collection_meta(conn, collection_id) if conn else None

    # Если коллекции нет — сразу возвращаем ответ об ошибке.
    if not collection_meta:
        return AnswerResult(
            answer=f"Коллекция с id={collection_id} не найдена.",
            fragments=[],
            sources=[],
            collection=None,
        )

    # Эмбеддинг запроса + retrieval
    model, q_emb = embed_query(query)
    retrieved = retrieve_chunks(
        conn,
        q_emb,
        collection_id=collection_id,
        top_k=options.top_k_retrieval,
        date_from=options.from_date,
        date_to=options.to_date,
    )
    if not retrieved:
        return AnswerResult(
            answer="В этой коллекции не удалось найти релевантные фрагменты статей для ответа на вопрос.",
            fragments=[],
            sources=[],
            collection=collection_meta,
        )

    # Rerank (если top_k_rerank задан и > 0)
    reranked: List[RerankedChunk]
    if options.top_k_rerank and options.top_k_rerank > 0:
        reranked = rerank_chunks(
            query,
            retrieved,
            top_k_rerank=options.top_k_rerank,
        )
        if not reranked:
            # fallback: без rerank, используем первые top_k_rerank из retrieval
            reranked = [
                RerankedChunk(chunk=ch, score=0.0)
                for ch in retrieved[: options.top_k_rerank]
            ]
    else:
        reranked = [RerankedChunk(chunk=ch, score=0.0) for ch in retrieved]

    # Формирование списка фрагментов (с индексами, совпадающими с [i] в промпте)
    fragments: List[FragmentDoc] = []
    link_to_fragment_ids: Dict[str, List[int]] = {}
    for idx, rc in enumerate(reranked, 1):
        ch = rc.chunk
        snippet = clean_text_for_llm(ch.text_payload or "", max_chars=600)
        frag = FragmentDoc(
            fragment_id=idx,
            link=ch.link,
            title=ch.title,
            summary=ch.summary,
            published_at=ch.published_at,
            snippet=snippet,
            similarity=ch.embed_similarity_to_topic,
            rerank_score=rc.score,
        )
        fragments.append(frag)
        link_to_fragment_ids.setdefault(ch.link, []).append(idx)

    # Построение промпта и вызов GigaChat
    messages = _build_llm_prompt(
        query=query,
        fragments=fragments,
        language=options.language,
    )

    client = create_gigachat_client()
    try:
        result = client.chat({"messages": messages, "temperature": 0.1})
        answer_text = (result.choices[0].message.content or "").strip()
    except Exception as e:
        answer_text = f"Ошибка при обращении к LLM: {e}"

    # Формирование sources для UI: по одной записи на статью (уникальный link),
    # плюс список fragment_id'ов, которые относятся к этой статье.
    sources: List[Dict[str, Any]] = []
    for link, frag_ids in link_to_fragment_ids.items():
        # Находим любой фрагмент по этому link, чтобы взять title/summary/published_at
        any_frag = next((f for f in fragments if f.link == link), None)
        if any_frag is None:
            continue
        sources.append(
            {
                "link": link,
                "title": any_frag.title,
                "summary": any_frag.summary,
                "published_at": any_frag.published_at,
                "fragments": frag_ids,
            }
        )

    return AnswerResult(
        answer=answer_text,
        fragments=fragments,
        sources=sources,
        collection=collection_meta,
    )


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 3:
        print("Usage: python -m src.qa.answer \"your question\" <collection_id>")
        sys.exit(1)
    q = sys.argv[1]
    try:
        cid = int(sys.argv[2])
    except ValueError:
        print("collection_id must be an integer")
        sys.exit(1)

    res = answer_question(q, cid)
    print("ANSWER:")
    print(res.answer)
    print("\nFRAGMENTS (что видел LLM):")
    for f in res.fragments:
        print(f"[{f.fragment_id}] {f.title} ({f.link})")
    print("\nSOURCES (по статьям):")
    for i, s in enumerate(res.sources, 1):
        fr_ids = ", ".join(str(fid) for fid in s.get("fragments", []))
        print(f"[{i}] {s.get('title', '')} ({s.get('link', '')}) <- фрагменты [{fr_ids}]")
