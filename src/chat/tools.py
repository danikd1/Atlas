"""
Инструменты (tools) чат-агента Atlas.

Каждая функция — один tool из function calling:
- get_article:      полный текст статьи по ссылке           (Task 2.1)
- search_articles:  поиск статей с summary                  (Task 2.2)
- answer_from_rag:  развёрнутый ответ через RAG             (Task 2.3)
- lookup_glossary:  поиск банковского термина в глоссарии   (Task 2.4)
"""
from __future__ import annotations

import json
import logging
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from config.config import POSTGRES_TABLE_PROCESSED_ARTICLES, POSTGRES_TABLE_RAG_DOCUMENTS
from src.qa.answer import AnswerOptions, answer_question
from src.qa.rerank import get_rerank_model
from src.qa.retrieval import _embedding_to_vector_str, embed_query
from src.tools.db_state import get_connection, get_or_create_global_rag_collection

logger = logging.getLogger(__name__)

# ── Глоссарий: загружается один раз при импорте модуля ─────────────────────
_GLOSSARY_PATH = Path(__file__).parent.parent.parent / "data" / "glossary.json"
try:
    _GLOSSARY: Dict[str, Dict[str, Any]] = json.loads(_GLOSSARY_PATH.read_text(encoding="utf-8"))
except Exception as _e:
    logger.warning("lookup_glossary: не удалось загрузить глоссарий (%s)", _e)
    _GLOSSARY = {}


def get_article(link: str) -> str:
    """
    Возвращает полный текст статьи по ссылке.

    Собирает все чанки статьи из rag_documents в порядке chunk_index
    и объединяет их в единый текст.

    Args:
        link: URL статьи.

    Returns:
        Полный текст статьи или пустая строка если статья не найдена.
    """
    if not link or not link.strip():
        return ""

    conn = get_connection()
    if conn is None:
        logger.warning("get_article: нет подключения к БД")
        return ""

    try:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT DISTINCT ON (chunk_index) text_payload
                FROM {POSTGRES_TABLE_RAG_DOCUMENTS}
                WHERE link = %s
                ORDER BY chunk_index ASC;
                """,
                (link.strip(),),
            )
            rows = cur.fetchall()

        if not rows:
            return ""

        chunks = [row["text_payload"] for row in rows if row.get("text_payload")]
        return "\n\n".join(chunks)

    except Exception as e:
        logger.warning("get_article(%s): ошибка БД: %s", link, e)
        return ""
    finally:
        conn.close()


def search_articles(
    query: str,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Ищет статьи в базе знаний Atlas.

    Алгоритм (Шаг 2 — BM25 hybrid):
      1a. Векторный поиск — top-250 чанков по эмбеддинг-дистанции (LaBSE)
      1b. BM25 поиск — top-250 чанков через PostgreSQL tsvector/tsquery (simple)
      2.  Группировка — лучший чанк на статью (по дистанции / BM25-score)
      3.  RRF-слияние — объединяем оба списка через Reciprocal Rank Fusion (k=60)
      4.  Cross-encoder reranking — (query, chunk_text) → score
      5.  Возврат top-10 по cross-encoder score + ai_summary из processed_articles

    Args:
        query:     поисковый запрос на естественном языке.
        date_from: нижняя граница по дате публикации (ISO строка YYYY-MM-DD, опционально).
        date_to:   верхняя граница по дате публикации (ISO строка YYYY-MM-DD, опционально).

    Returns:
        Список [{title, link, published_at, summary}, ...], до 10 статей.
        Пустой список если ничего не найдено или ошибка.
    """
    if not query or not query.strip():
        return []

    conn = get_connection()
    if conn is None:
        logger.warning("search_articles: нет подключения к БД")
        return []

    try:
        _, emb = embed_query(query.strip())
        emb_str = _embedding_to_vector_str(emb)
        q = query.strip()

        conditions: List[str] = []
        where_params: List[Any] = []

        if date_from:
            try:
                date.fromisoformat(date_from)
                conditions.append("published_at >= %s")
                where_params.append(date_from)
            except ValueError:
                logger.warning("search_articles: невалидный date_from=%r", date_from)

        if date_to:
            try:
                date.fromisoformat(date_to)
                conditions.append("published_at <= %s")
                where_params.append(date_to)
            except ValueError:
                logger.warning("search_articles: невалидный date_to=%r", date_to)

        where_clause = ("WHERE " + " AND ".join(conditions)) if conditions else ""

        # ── Шаг 1а: top-250 чанков по вектору ──────────────────────────────
        vec_sql = f"""
            SELECT
                link,
                title,
                published_at,
                summary,
                text_payload,
                (embedding <-> %s::vector) AS distance
            FROM {POSTGRES_TABLE_RAG_DOCUMENTS}
            {where_clause}
            ORDER BY embedding <-> %s::vector
            LIMIT 250;
        """
        with conn.cursor() as cur:
            cur.execute(vec_sql, [emb_str] + where_params + [emb_str])
            vector_rows = cur.fetchall()

        # ── Шаг 1б: top-250 чанков по BM25 (simple — без стемминга, ловит точные термины) ──
        bm25_rows: List[Any] = []
        try:
            bm25_sql = f"""
                WITH fts AS (
                    SELECT link, title, published_at, summary, text_payload,
                           to_tsvector('simple', text_payload) AS tsv
                    FROM {POSTGRES_TABLE_RAG_DOCUMENTS}
                    {where_clause}
                )
                SELECT link, title, published_at, summary, text_payload,
                       ts_rank(tsv, plainto_tsquery('simple', %s)) AS bm25_score
                FROM fts
                WHERE tsv @@ plainto_tsquery('simple', %s)
                ORDER BY bm25_score DESC
                LIMIT 250;
            """
            # params: date_params (WHERE внутри CTE), query для ts_rank, query для @@
            bm25_params = where_params + [q, q]
            with conn.cursor() as cur:
                cur.execute(bm25_sql, bm25_params)
                bm25_rows = cur.fetchall()
        except Exception as bm25_err:
            logger.warning("search_articles: BM25 недоступен (%s) — только вектор", bm25_err)

        if not vector_rows and not bm25_rows:
            logger.info("search_articles(%r): ничего не найдено", query)
            return []

        # ── Шаг 2: группировка — лучший чанк на статью ──────────────────────
        def _row_to_art(row: dict, dist: float = 0.0) -> dict:
            return {
                "link": row["link"],
                "title": row.get("title") or "",
                "published_at": row.get("published_at"),
                "summary": row.get("summary") or "",
                "text_payload": row.get("text_payload") or "",
                "distance": dist,
            }

        vector_best: Dict[str, dict] = {}
        for row in vector_rows:
            link = row["link"]
            dist = float(row["distance"])
            if link not in vector_best or dist < vector_best[link]["distance"]:
                vector_best[link] = _row_to_art(row, dist)

        bm25_best: Dict[str, dict] = {}
        for row in bm25_rows:
            link = row["link"]
            score = float(row["bm25_score"])
            if link not in bm25_best or score > bm25_best[link].get("bm25_score", -1.0):
                art = _row_to_art(row, dist=float("inf"))  # distance неизвестна из BM25
                art["bm25_score"] = score
                bm25_best[link] = art

        # ── Шаг 3: RRF-слияние ───────────────────────────────────────────────
        # Ранги считаются после сортировки: вектор — по дистанции, BM25 — по убыванию score
        vector_ranked = sorted(vector_best.values(), key=lambda x: x["distance"])
        bm25_ranked   = sorted(bm25_best.values(),   key=lambda x: -x.get("bm25_score", 0.0))

        vector_rank = {art["link"]: i + 1 for i, art in enumerate(vector_ranked)}
        bm25_rank   = {art["link"]: i + 1 for i, art in enumerate(bm25_ranked)}

        K = 60
        all_links = set(vector_best.keys()) | set(bm25_best.keys())
        candidates: List[dict] = []
        for link in all_links:
            vr = vector_rank.get(link, len(vector_ranked) + 1000)
            br = bm25_rank.get(link,   len(bm25_ranked)   + 1000)
            rrf = 1.0 / (K + vr) + 1.0 / (K + br)
            art = vector_best.get(link) or bm25_best[link]
            if art.get("text_payload"):
                candidates.append({**art, "rrf_score": rrf})

        logger.info(
            "search_articles(%r): вектор=%d статей  BM25=%d статей  после RRF=%d",
            query, len(vector_best), len(bm25_best), len(candidates),
        )

        # ── Шаг 4: cross-encoder reranking ──────────────────────────────────
        try:
            reranker = get_rerank_model()
            pairs = [(q, art["text_payload"]) for art in candidates]
            scores = reranker.predict(pairs)
            for art, score in zip(candidates, scores):
                art["ce_score"] = float(score)
            candidates.sort(key=lambda x: x["ce_score"], reverse=True)
        except Exception as re_err:
            logger.warning("search_articles: cross-encoder недоступен (%s) — fallback по RRF", re_err)
            for art in candidates:
                art["ce_score"] = art["rrf_score"]
            candidates.sort(key=lambda x: x["ce_score"], reverse=True)

        top = candidates[:10]

        if not top:
            logger.info("search_articles(%r): после reranking статей не осталось", query)
            return []

        # ── Шаг 5: ai_summary для финальных статей ──────────────────────────
        top_links = [art["link"] for art in top]
        ai_summaries: Dict[str, str] = {}
        article_ids: Dict[str, int] = {}
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT link, id, ai_summary
                FROM {POSTGRES_TABLE_PROCESSED_ARTICLES}
                WHERE link = ANY(%s);
                """,
                (top_links,),
            )
            for row in cur.fetchall():
                article_ids[row["link"]] = row["id"]
                if row.get("ai_summary"):
                    ai_summaries[row["link"]] = row["ai_summary"]

        results: List[Dict[str, Any]] = []
        for art in top:
            published_at = art["published_at"]
            results.append({
                "title": art["title"],
                "link": art["link"],
                "published_at": published_at.isoformat() if published_at else None,
                "summary": ai_summaries.get(art["link"]) or art["summary"] or "",
                "article_id": article_ids.get(art["link"]),
                "_ce_score": art["ce_score"],
                "_rrf_score": art["rrf_score"],
                "_distance": art["distance"],
            })

        # ── Лог таблицей ────────────────────────────────────────────────────
        logger.info("search_articles(%r): итого %d статей в топ-10", query, len(results))
        if results:
            W_TITLE, W_LINK = 35, 40
            sep = "─" * (4 + 8 + 8 + 8 + W_TITLE + W_LINK + 4)
            logger.info(sep)
            logger.info("  %2s  %-8s  %-8s  %-8s  %-*s  %s", "#", "ce_score", "rrf", "dist", W_TITLE, "title", "link")
            logger.info(sep)
            for i, r in enumerate(results, 1):
                title = (r["title"][:W_TITLE - 1] + "…") if len(r["title"]) > W_TITLE else r["title"]
                link  = (r["link"][:W_LINK - 1]   + "…") if len(r["link"])  > W_LINK  else r["link"]
                logger.info(
                    "  %2d  %-8.4f  %-8.4f  %-8.4f  %-*s  %s",
                    i, r["_ce_score"], r["_rrf_score"], r["_distance"],
                    W_TITLE, title, link,
                )
            logger.info(sep)

        for r in results:
            r.pop("_ce_score", None)
            r.pop("_rrf_score", None)
            r.pop("_distance", None)

        return results

    except Exception as e:
        logger.warning("search_articles(%s): ошибка: %s", query, e)
        return []
    finally:
        conn.close()


def answer_from_rag(
    query: str,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    gigachat_credentials: str = "",
    gigachat_model: str = "",
) -> Dict[str, Any]:
    """
    Развёрнутый ответ на вопрос по базе знаний Atlas.

    Тонкая обёртка над answer_question() из src.qa.answer:
      1. Получает ID глобальной RAG-коллекции
      2. Гибридный retrieval (вектор + BM25 + RRF) top-250 чанков → cross-encoder rerank top-10
      3. GigaChat генерирует ответ по найденным фрагментам
      4. Возвращает ответ + список источников

    Args:
        query:     вопрос на естественном языке.
        date_from: нижняя граница по дате публикации (ISO строка YYYY-MM-DD, опционально).
        date_to:   верхняя граница по дате публикации (ISO строка YYYY-MM-DD, опционально).

    Returns:
        {"answer": str, "sources": [{title, link, published_at}, ...]}
        При ошибке — {"answer": "сообщение об ошибке", "sources": []}
    """
    q = query.strip()
    if not q:
        return {"answer": "", "sources": []}

    conn = get_connection()
    if conn is None:
        logger.warning("answer_from_rag: нет подключения к БД")
        return {"answer": "Нет подключения к базе данных.", "sources": []}

    try:
        collection = get_or_create_global_rag_collection(conn)
        if not collection:
            return {"answer": "RAG-коллекция недоступна.", "sources": []}
        collection_id = collection["id"]
    except Exception as e:
        logger.warning("answer_from_rag: не удалось получить collection_id: %s", e)
        return {"answer": "Ошибка подключения к базе данных.", "sources": []}
    finally:
        conn.close()

    options = AnswerOptions()
    if date_from:
        try:
            options.from_date = datetime.fromisoformat(date_from)
        except ValueError:
            logger.warning("answer_from_rag: невалидный date_from=%r", date_from)
    if date_to:
        try:
            options.to_date = datetime.fromisoformat(date_to)
        except ValueError:
            logger.warning("answer_from_rag: невалидный date_to=%r", date_to)

    result = answer_question(
        q,
        collection_id,
        options,
        gigachat_credentials=gigachat_credentials or None,
        gigachat_model=gigachat_model or None,
    )

    sources: List[Dict[str, Any]] = []
    for s in result.sources:
        published_at = s.get("published_at")
        sources.append({
            "title": s.get("title", ""),
            "link": s.get("link", ""),
            "published_at": published_at.isoformat() if published_at else None,
        })

    logger.info(
        "answer_from_rag(%r): ответ %d симв., источников %d",
        q, len(result.answer), len(sources),
    )
    return {"answer": result.answer, "sources": sources}


def lookup_glossary(term: str) -> Optional[Dict[str, Any]]:
    """
    Ищет банковский термин в глоссарии Atlas.

    Поиск нечувствителен к регистру. Сначала ищет точное совпадение,
    затем частичное (запрос содержится в термине или наоборот).

    Args:
        term: термин для поиска.

    Returns:
        {"definition": str, "synonyms": list[str]} если найдено, иначе None.
    """
    if not term or not term.strip():
        return None

    needle = term.strip().lower()

    # Точное совпадение
    for key, value in _GLOSSARY.items():
        if key.lower() == needle:
            logger.info("lookup_glossary(%r): точное совпадение → %r", term, key)
            return value

    # Частичное совпадение: запрос ⊆ термин или термин ⊆ запрос
    # Минимум 3 символа чтобы короткие аббревиатуры (АС, НТ, СТ) не давали ложных совпадений
    if len(needle) >= 3:
        for key, value in _GLOSSARY.items():
            key_lower = key.lower()
            if len(key_lower) >= 3 and (needle in key_lower or key_lower in needle):
                logger.info("lookup_glossary(%r): частичное совпадение → %r", term, key)
                return value

    logger.info("lookup_glossary(%r): термин не найден", term)
    return None
