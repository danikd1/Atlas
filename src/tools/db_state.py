"""
Утилиты для работы с PostgreSQL: хранение состояния краулера и RAG-данных.

Храним:
- таблица processed_articles: уникальные обработанные статьи (дедуп по link)
- таблица last_published_at: last_processed_published_at по каждому RSS-источнику
- таблица collections: логические RAG-коллекции (D/GA/A + имя)
- таблица rag_documents: документы с эмбеддингами по коллекциям (pgvector)
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Dict, Iterable, List, Optional, Set, TypedDict


class CollectionRow(TypedDict, total=False):
    """Строка таблицы collections (id, name, D/GA/A, collection_key, временные метки)."""
    id: int
    name: str
    discipline: Optional[str]
    ga: Optional[str]
    activity: Optional[str]
    collection_key: str
    user_id: Optional[str]
    team_id: Optional[str]
    created_at: datetime
    updated_at: datetime
    last_refreshed_at: Optional[datetime]

import pandas as pd
import psycopg2
from psycopg2.extras import DictCursor

from src.tools.llm_utils import clean_text_for_llm

from config.config import (
    EMBEDDING_DIM,
    POSTGRES_DB,
    POSTGRES_ENABLED,
    POSTGRES_HOST,
    POSTGRES_PASSWORD,
    POSTGRES_PORT,
    POSTGRES_TABLE_COLLECTIONS,
    POSTGRES_TABLE_FEED_STATE,
    POSTGRES_TABLE_PROCESSED_ARTICLES,
    POSTGRES_TABLE_RAG_DOCUMENTS,
    POSTGRES_USER,
)

logger = logging.getLogger(__name__)


def get_connection():
    """
    Возвращает подключение к PostgreSQL или None, если БД отключена/недоступна.
    """
    if not POSTGRES_ENABLED:
        return None

    try:
        conn = psycopg2.connect(
            host=POSTGRES_HOST,
            port=POSTGRES_PORT,
            dbname=POSTGRES_DB,
            user=POSTGRES_USER,
            password=POSTGRES_PASSWORD,
            cursor_factory=DictCursor,
        )
        conn.autocommit = True
        return conn
    except Exception as e:
        logger.warning(f"Не удалось подключиться к PostgreSQL: {e}. Работаем без БД.")
        return None


def ensure_tables(conn) -> None:
    """
    Создает необходимые таблицы, если их еще нет.
    """
    if conn is None:
        return

    with conn.cursor() as cur:
        # Таблица с обработанными статьями (title, summary нужны для пайплайна по окну из БД)
        cur.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {POSTGRES_TABLE_PROCESSED_ARTICLES} (
                id SERIAL PRIMARY KEY,
                source TEXT NOT NULL,
                link TEXT NOT NULL UNIQUE,
                published_at TIMESTAMPTZ,
                processed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                title TEXT,
                summary TEXT
            );
            """
        )
        # Добавляем колонки title, summary если таблица уже существовала без них (PG 11+ или игнорируем ошибку)
        for col in ("title", "summary"):
            try:
                cur.execute(
                    f"""
                    ALTER TABLE {POSTGRES_TABLE_PROCESSED_ARTICLES}
                    ADD COLUMN IF NOT EXISTS {col} TEXT;
                    """
                )
            except Exception:
                # колонка уже есть или старая версия PG без IF NOT EXISTS
                pass

        # Таблица состояния по каждому RSS-источнику
        cur.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {POSTGRES_TABLE_FEED_STATE} (
                source TEXT PRIMARY KEY,
                last_processed_published_at TIMESTAMPTZ
            );
            """
        )

        # Таблица логических коллекций для RAG (selection D/GA/A + имя; одна пара = одна запись).
        # Уникальность по (collection_key, name): один и тот же D/GA/A может иметь несколько коллекций с разными именами.
        cur.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {POSTGRES_TABLE_COLLECTIONS} (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                discipline TEXT,
                ga TEXT,
                activity TEXT,
                collection_key TEXT NOT NULL,
                user_id TEXT,
                team_id TEXT,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                last_refreshed_at TIMESTAMPTZ,
                UNIQUE (collection_key, name)
            );
            """
        )
        # Миграция: если раньше был UNIQUE только по collection_key — убираем его, оставляем UNIQUE(collection_key, name).
        try:
            cur.execute(
                f"ALTER TABLE {POSTGRES_TABLE_COLLECTIONS} DROP CONSTRAINT IF EXISTS {POSTGRES_TABLE_COLLECTIONS}_collection_key_key;"
            )
        except Exception:
            pass
        try:
            cur.execute(
                f"""
                ALTER TABLE {POSTGRES_TABLE_COLLECTIONS}
                ADD CONSTRAINT {POSTGRES_TABLE_COLLECTIONS}_collection_key_name_key UNIQUE (collection_key, name);
                """
            )
        except Exception:
            pass
        try:
            cur.execute(
                f"""
                CREATE INDEX IF NOT EXISTS idx_collections_user_created
                ON {POSTGRES_TABLE_COLLECTIONS} (user_id, created_at DESC);
                """
            )
        except Exception:
            pass

        # Расширение pgvector для векторного поиска (должно быть установлено в БД)
        try:
            cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
        except Exception as e:
            logger.warning("Расширение pgvector недоступно: %s. Таблица rag_documents не будет создана.", e)
        else:
            # Таблица RAG-документов: одна строка — один чанк статьи в одной коллекции.
            # Уникальность по (collection_id, link, chunk_index).
            cur.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {POSTGRES_TABLE_RAG_DOCUMENTS} (
                    id BIGSERIAL PRIMARY KEY,
                    collection_id INT NOT NULL REFERENCES {POSTGRES_TABLE_COLLECTIONS}(id) ON DELETE CASCADE,
                    link TEXT NOT NULL,
                    chunk_index INT NOT NULL DEFAULT 0,
                    title TEXT,
                    summary TEXT,
                    source TEXT,
                    published_at TIMESTAMPTZ,
                    discipline TEXT,
                    ga TEXT,
                    activity TEXT,
                    text_payload TEXT NOT NULL,
                    embedding vector({EMBEDDING_DIM}),
                    embed_similarity_to_topic REAL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    UNIQUE (collection_id, link, chunk_index)
                );
                """
            )
            # Миграция: добавить chunk_index если таблица создана по старой схеме
            try:
                cur.execute(
                    f"""
                    ALTER TABLE {POSTGRES_TABLE_RAG_DOCUMENTS}
                    ADD COLUMN IF NOT EXISTS chunk_index INT NOT NULL DEFAULT 0;
                    """
                )
            except Exception:
                pass
            # Заменить старый UNIQUE(collection_id, link) на UNIQUE(collection_id, link, chunk_index)
            try:
                cur.execute(
                    f"ALTER TABLE {POSTGRES_TABLE_RAG_DOCUMENTS} DROP CONSTRAINT IF EXISTS {POSTGRES_TABLE_RAG_DOCUMENTS}_collection_id_link_key;"
                )
            except Exception:
                pass
            try:
                cur.execute(
                    f"""
                    ALTER TABLE {POSTGRES_TABLE_RAG_DOCUMENTS}
                    DROP CONSTRAINT IF EXISTS {POSTGRES_TABLE_RAG_DOCUMENTS}_collection_id_link_chunk_index_key;
                    """
                )
                cur.execute(
                    f"""
                    ALTER TABLE {POSTGRES_TABLE_RAG_DOCUMENTS}
                    ADD CONSTRAINT {POSTGRES_TABLE_RAG_DOCUMENTS}_collection_id_link_chunk_index_key
                    UNIQUE (collection_id, link, chunk_index);
                    """
                )
            except Exception:
                pass
            try:
                cur.execute(
                    f"""
                    CREATE INDEX IF NOT EXISTS idx_rag_documents_collection_published
                    ON {POSTGRES_TABLE_RAG_DOCUMENTS} (collection_id, published_at DESC);
                    """
                )
            except Exception:
                pass
            try:
                cur.execute(
                    f"""
                    CREATE INDEX IF NOT EXISTS idx_rag_documents_collection_id
                    ON {POSTGRES_TABLE_RAG_DOCUMENTS} (collection_id);
                    """
                )
            except Exception:
                pass


def build_collection_key(selection: Dict[str, Optional[str]]) -> str:
    """
    Строит уникальный ключ коллекции по selection (discipline, ga, activity).

    Формат: "D1", "D1.GA1", "D1.GA1.A1". Null-уровни не включаются.
    """
    d = (selection.get("discipline") or "").strip()
    g = (selection.get("ga") or "").strip()
    a = (selection.get("activity") or "").strip()
    parts = [d] if d else []
    if g:
        parts.append(g)
    if a:
        parts.append(a)
    return ".".join(parts) if parts else ""


def get_or_create_collection(
    conn,
    selection: Dict[str, Optional[str]],
    taxonomy: Dict,
    user_id: Optional[str] = None,
    team_id: Optional[str] = None,
    collection_name: Optional[str] = None,
) -> Optional[CollectionRow]:
    """
    Находит коллекцию по паре (collection_key, name) или создаёт новую.

    Логика:
    - Если запись с таким collection_key и именем уже есть — только обновляются
      last_refreshed_at и updated_at (та же коллекция обновлена).
    - Если такой пары нет (новое имя или новый selection) — создаётся новая запись.
    Таким образом, один и тот же D/GA/A может иметь несколько коллекций с разными именами.

    Returns:
        Словарь с полями id, name, collection_key, ... или None при conn=None / пустом selection.
    """
    if conn is None:
        return None
    key = build_collection_key(selection)
    if not key:
        return None

    if collection_name and collection_name.strip():
        name = collection_name.strip()
    else:
        from src.taxonomy import get_collection_display_name
        name = get_collection_display_name(taxonomy, selection)
    discipline = selection.get("discipline")
    ga = selection.get("ga")
    activity = selection.get("activity")

    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT id, name, discipline, ga, activity, collection_key, user_id, team_id,
                   created_at, updated_at, last_refreshed_at
            FROM {POSTGRES_TABLE_COLLECTIONS}
            WHERE collection_key = %s AND name = %s;
            """,
            (key, name),
        )
        row = cur.fetchone()
        if row:
            cur.execute(
                f"""
                UPDATE {POSTGRES_TABLE_COLLECTIONS}
                SET last_refreshed_at = NOW(), updated_at = NOW()
                WHERE id = %s
                RETURNING id, name, discipline, ga, activity, collection_key, user_id, team_id,
                          created_at, updated_at, last_refreshed_at;
                """,
                (row["id"],),
            )
            row = cur.fetchone()
        else:
            cur.execute(
                f"""
                INSERT INTO {POSTGRES_TABLE_COLLECTIONS}
                    (name, discipline, ga, activity, collection_key, user_id, team_id, updated_at, last_refreshed_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
                RETURNING id, name, discipline, ga, activity, collection_key, user_id, team_id,
                          created_at, updated_at, last_refreshed_at;
                """,
                (name, discipline, ga, activity, key, user_id, team_id),
            )
            row = cur.fetchone()
    if not row:
        return None
    return {
        "id": row["id"],
        "name": row["name"],
        "discipline": row["discipline"],
        "ga": row["ga"],
        "activity": row["activity"],
        "collection_key": row["collection_key"],
        "user_id": row["user_id"],
        "team_id": row["team_id"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "last_refreshed_at": row["last_refreshed_at"],
    }


def update_collection_last_refreshed(conn, collection_id: int) -> None:
    """Обновляет last_refreshed_at у коллекции после успешного прогона пайплайна."""
    if conn is None or collection_id is None:
        return
    with conn.cursor() as cur:
        cur.execute(
            f"""
            UPDATE {POSTGRES_TABLE_COLLECTIONS}
            SET last_refreshed_at = NOW(), updated_at = NOW()
            WHERE id = %s;
            """,
            (collection_id,),
        )


def list_collections(conn) -> List[CollectionRow]:
    """
    Возвращает список всех коллекций (для UI и API).
    Сортировка по updated_at по убыванию.
    """
    if conn is None:
        return []
    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT id, name, discipline, ga, activity, collection_key, user_id, team_id,
                   created_at, updated_at, last_refreshed_at
            FROM {POSTGRES_TABLE_COLLECTIONS}
            ORDER BY updated_at DESC NULLS LAST, id DESC;
            """,
        )
        rows = cur.fetchall()
    return [dict(row) for row in rows]


def get_collection_by_id(conn, collection_id: int) -> Optional[CollectionRow]:
    """Возвращает одну коллекцию по id или None."""
    if conn is None:
        return None
    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT id, name, discipline, ga, activity, collection_key, user_id, team_id,
                   created_at, updated_at, last_refreshed_at
            FROM {POSTGRES_TABLE_COLLECTIONS}
            WHERE id = %s;
            """,
            (collection_id,),
        )
        row = cur.fetchone()
    return dict(row) if row else None


def get_articles_for_collection(
    conn,
    collection_id: int,
) -> List[Dict]:
    """
    Возвращает список статей коллекции из rag_documents: одна запись на статью (по link).
    Поля: link, title, summary, source, published_at.
    """
    if conn is None:
        return []
    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT DISTINCT ON (link) link, title, summary, source, published_at
            FROM {POSTGRES_TABLE_RAG_DOCUMENTS}
            WHERE collection_id = %s
            ORDER BY link, chunk_index;
            """,
            (collection_id,),
        )
        rows = cur.fetchall()
    return [dict(row) for row in rows]


def _embedding_to_vector_str(embedding: List[float]) -> str:
    """Формирует строку для вставки в колонку pgvector: '[0.1, 0.2, ...]'."""
    return "[" + ",".join(str(float(x)) for x in embedding) + "]"


def delete_rag_documents_by_links(conn, collection_id: int, links: Iterable[str]) -> None:
    """
    Удаляет из rag_documents все чанки статей с указанными link в данной коллекции.
    Вызывать перед upsert при обновлении коллекции, чтобы убрать устаревшие чанки.
    """
    if conn is None or not links:
        return
    links_list = list(links)
    if not links_list:
        return
    with conn.cursor() as cur:
        cur.execute(
            f"""
            DELETE FROM {POSTGRES_TABLE_RAG_DOCUMENTS}
            WHERE collection_id = %s AND link = ANY(%s);
            """,
            (collection_id, links_list),
        )


def upsert_rag_documents(
    conn,
    collection_id: int,
    discipline: Optional[str],
    ga: Optional[str],
    activity: Optional[str],
    documents: List[Dict],
) -> int:
    """
    Вставляет или обновляет RAG-документы (чанки) в таблице rag_documents.
    Upsert по (collection_id, link, chunk_index).

    Каждый элемент documents должен содержать: link, chunk_index, title, summary, source,
    published_at, text_payload, embedding (список float), embed_similarity_to_topic (опционально).

    Returns:
        Количество обработанных строк (вставлено или обновлено).
    """
    if conn is None or not documents:
        return 0
    count = 0
    with conn.cursor() as cur:
        for doc in documents:
            link = doc.get("link")
            if not link:
                continue
            chunk_index = int(doc.get("chunk_index", 0))
            title = doc.get("title") or ""
            summary = doc.get("summary") or ""
            source = doc.get("source") or ""
            published_at = doc.get("published_at")
            text_payload = doc.get("text_payload") or ""
            embedding = doc.get("embedding")
            embed_sim = doc.get("embed_similarity_to_topic")
            if embedding is not None:
                emb_str = _embedding_to_vector_str(embedding)
            else:
                emb_str = None
            cur.execute(
                f"""
                INSERT INTO {POSTGRES_TABLE_RAG_DOCUMENTS}
                    (collection_id, link, chunk_index, title, summary, source, published_at,
                     discipline, ga, activity, text_payload, embedding, embed_similarity_to_topic, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::vector, %s, NOW())
                ON CONFLICT (collection_id, link, chunk_index) DO UPDATE SET
                    title = EXCLUDED.title,
                    summary = EXCLUDED.summary,
                    source = EXCLUDED.source,
                    published_at = EXCLUDED.published_at,
                    discipline = EXCLUDED.discipline,
                    ga = EXCLUDED.ga,
                    activity = EXCLUDED.activity,
                    text_payload = EXCLUDED.text_payload,
                    embedding = EXCLUDED.embedding,
                    embed_similarity_to_topic = EXCLUDED.embed_similarity_to_topic,
                    updated_at = NOW();
                """,
                (
                    collection_id,
                    link,
                    chunk_index,
                    title,
                    summary,
                    source,
                    published_at,
                    discipline,
                    ga,
                    activity,
                    text_payload,
                    emb_str,
                    embed_sim,
                ),
            )
            count += 1
    return count


def load_processed_links(conn) -> Set[str]:
    """
    Загружает множество уже обработанных ссылок (для дедупликации между запусками).
    """
    if conn is None:
        return set()

    with conn.cursor() as cur:
        cur.execute(f"SELECT link FROM {POSTGRES_TABLE_PROCESSED_ARTICLES};")
        rows = cur.fetchall()
        return {row["link"] for row in rows if row.get("link")}


def load_articles_for_window(conn, hours_back: int):
    """
    Загружает из БД статьи, у которых published_at попадает в окно «последние hours_back часов».
    Так временное окно пайплайна реально означает «статьи за последние N часов», а не «срез после last_run».

    Returns:
        DataFrame с колонками title, link, published, summary, source, published_dt
        или пустой DataFrame при conn=None / пустом результате.
    """
    if conn is None:
        return pd.DataFrame()

    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT source, link, published_at, title, summary
            FROM {POSTGRES_TABLE_PROCESSED_ARTICLES}
            WHERE published_at >= NOW() - INTERVAL '1 hour' * %s
            ORDER BY published_at DESC;
            """,
            (hours_back,),
        )
        rows = cur.fetchall()

    if not rows:
        return pd.DataFrame()

    records = []
    for row in rows:
        published_at = row.get("published_at")
        records.append({
            "source": row.get("source"),
            "link": row.get("link") or "",
            "published": published_at.strftime("%Y-%m-%d %H:%M:%S") if published_at else "—",
            "summary": row.get("summary") or "Без описания",
            "title": row.get("title") or "",
            "published_dt": published_at,
        })
    return pd.DataFrame(records)


def update_feed_states_from_seen(conn, per_feed_max: Dict[str, datetime]) -> None:
    """
    Обновляет last_processed_published_at по каждой ленте по макс. дате среди *увиденных* статей
    (не только добавленных). Чтобы при повторном запуске parse_rss не возвращал те же записи.
    """
    if conn is None or not per_feed_max:
        return

    with conn.cursor() as cur:
        for source, max_dt in per_feed_max.items():
            if not source or not isinstance(max_dt, datetime):
                continue
            cur.execute(
                f"""
                INSERT INTO {POSTGRES_TABLE_FEED_STATE} (source, last_processed_published_at)
                VALUES (%s, %s)
                ON CONFLICT (source)
                DO UPDATE SET last_processed_published_at = GREATEST(
                    EXCLUDED.last_processed_published_at,
                    {POSTGRES_TABLE_FEED_STATE}.last_processed_published_at
                );
                """,
                (source, max_dt),
            )


def load_feed_states(conn) -> Dict[str, datetime]:
    """
    Загружает last_processed_published_at по каждому RSS-источнику.
    
    Returns:
        Словарь {source: last_processed_published_at}, где source - ключ из RSS_FEEDS
    """
    if conn is None:
        return {}

    with conn.cursor() as cur:
        cur.execute(
            f"SELECT source, last_processed_published_at FROM {POSTGRES_TABLE_FEED_STATE};"
        )
        rows = cur.fetchall()
        result = {}
        for row in rows:
            source = row.get("source")
            last_dt = row.get("last_processed_published_at")
            if source and isinstance(last_dt, datetime):
                result[source] = last_dt
        return result


def update_state_with_articles(conn, articles: Iterable[Dict]) -> None:
    """
    Сохраняет новые статьи в БД и обновляет last_processed_published_at по каждому источнику.

    Ожидается, что каждая статья имеет поля:
    - source: имя RSS-источника (ключ из RSS_FEEDS)
    - link: уникальный URL статьи
    - published_dt: datetime или None
    - title, summary: для последующей выборки по окну (опционально)
    """
    if conn is None:
        return

    articles = list(articles)
    if not articles:
        return

    with conn.cursor() as cur:
        # Вставка обработанных статей (игнорируем дубликаты по link).
        # summary очищаем так же, как перед эмбеддингами, чтобы в БД сразу хранился тот текст,
        # который примерно пойдет в модель (без HTML/шумов).
        for art in articles:
            source = art.get("source")
            link = art.get("link")
            published_dt = art.get("published_dt")
            title = art.get("title") or ""
            raw_summary = art.get("summary") or ""
            # Не ограничиваем длину при сохранении в БД, чтобы не терять информацию;
            # clean_text_for_llm убирает HTML и нормализует пробелы.
            summary = clean_text_for_llm(raw_summary, max_chars=None) if raw_summary else ""

            if not link or not source:
                continue

            cur.execute(
                f"""
                INSERT INTO {POSTGRES_TABLE_PROCESSED_ARTICLES} (source, link, published_at, title, summary)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (link) DO UPDATE SET
                    title = EXCLUDED.title,
                    summary = EXCLUDED.summary,
                    published_at = COALESCE(EXCLUDED.published_at, {POSTGRES_TABLE_PROCESSED_ARTICLES}.published_at);
                """,
                (source, link, published_dt, title, summary),
            )

        # Обновление last_processed_published_at по каждому источнику
        # Берем максимум published_dt среди переданных статей для каждого source
        per_source_max: Dict[str, datetime] = {}
        for art in articles:
            source = art.get("source")
            published_dt = art.get("published_dt")
            if not source or not isinstance(published_dt, datetime):
                continue
            current_max = per_source_max.get(source)
            if current_max is None or published_dt > current_max:
                per_source_max[source] = published_dt

        for source, max_dt in per_source_max.items():
            cur.execute(
                f"""
                INSERT INTO {POSTGRES_TABLE_FEED_STATE} (source, last_processed_published_at)
                VALUES (%s, %s)
                ON CONFLICT (source)
                DO UPDATE SET last_processed_published_at = GREATEST(
                    EXCLUDED.last_processed_published_at,
                    {POSTGRES_TABLE_FEED_STATE}.last_processed_published_at
                );
                """,
                (source, max_dt),
            )

