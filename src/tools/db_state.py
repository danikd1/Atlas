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
    description: Optional[str]
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
    POSTGRES_TABLE_BERTOPIC_ASSIGNMENTS,
    POSTGRES_TABLE_COLLECTIONS,
    POSTGRES_TABLE_FEED_STATE,
    POSTGRES_TABLE_INBOX_ARTICLES,
    POSTGRES_TABLE_PROCESSED_ARTICLES,
    POSTGRES_TABLE_RAG_DOCUMENTS,
    POSTGRES_USER,
    RSS_FEEDS,
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
        # Добавляем колонки если таблица уже существовала без них
        for col_def in (
            "title TEXT",
            "summary TEXT",
            "feed_id INT REFERENCES feeds(id) ON DELETE SET NULL",
            "full_text TEXT",
            "ai_summary TEXT",
        ):
            try:
                cur.execute(
                    f"""
                    ALTER TABLE {POSTGRES_TABLE_PROCESSED_ARTICLES}
                    ADD COLUMN IF NOT EXISTS {col_def};
                    """
                )
            except Exception:
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
        # Миграция: добавить колонку description если таблица уже существовала
        try:
            cur.execute(
                f"""
                ALTER TABLE {POSTGRES_TABLE_COLLECTIONS}
                ADD COLUMN IF NOT EXISTS description TEXT;
                """
            )
        except Exception:
            pass

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


        # Миграция: новые колонки в collections для BERTopic
        for col_def in ("bertopic_topic_id INT", "model_version TEXT"):
            try:
                cur.execute(
                    f"""
                    ALTER TABLE {POSTGRES_TABLE_COLLECTIONS}
                    ADD COLUMN IF NOT EXISTS {col_def};
                    """
                )
            except Exception:
                pass

        # Таблица назначений статей на BERTopic-темы
        cur.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {POSTGRES_TABLE_BERTOPIC_ASSIGNMENTS} (
                link          TEXT NOT NULL,
                topic_id      INT  NOT NULL,
                probability   FLOAT,
                assigned_at   TIMESTAMPTZ DEFAULT NOW(),
                model_version TEXT,
                PRIMARY KEY (link, topic_id)
            );
            """
        )

        # Буфер статей без чёткой темы (prob < порога при transform)
        try:
            cur.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {POSTGRES_TABLE_INBOX_ARTICLES} (
                    link        TEXT PRIMARY KEY,
                    title       TEXT,
                    source      TEXT,
                    embedding   VECTOR({EMBEDDING_DIM}),
                    received_at TIMESTAMPTZ DEFAULT NOW(),
                    checked_at  TIMESTAMPTZ
                );
                """
            )
        except Exception as e:
            logger.warning("Таблица inbox_articles не создана (pgvector?): %s", e)

        # Глобальный каталог RSS-лент: один URL = одна запись, независимо от числа подписчиков.
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS feeds (
                id              SERIAL PRIMARY KEY,
                url             TEXT NOT NULL UNIQUE,
                name            TEXT NOT NULL,
                favicon_url     TEXT,
                category        TEXT,
                is_catalog      BOOLEAN DEFAULT FALSE,
                enabled         BOOLEAN DEFAULT TRUE,
                last_fetched_at TIMESTAMPTZ,
                last_error      TEXT,
                error_count     INT DEFAULT 0
            );
            """
        )

        # Миграция: добавляем category если таблица уже существует без неё
        cur.execute(
            """
            ALTER TABLE feeds ADD COLUMN IF NOT EXISTS category TEXT;
            """
        )

        # Подписки пользователей на ленты: связь M:N между пользователем и лентой.
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS user_feeds (
                feed_id    INT NOT NULL REFERENCES feeds(id) ON DELETE CASCADE,
                user_id    INT,
                folder_id  INT,
                position   INT DEFAULT 0,
                hidden     BOOLEAN DEFAULT FALSE,
                PRIMARY KEY (feed_id, user_id)
            );
            """
        )

        # Папки пользователя для группировки лент в боковой панели.
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS feed_folders (
                id        SERIAL PRIMARY KEY,
                user_id   INT,
                name      TEXT NOT NULL,
                position  INT DEFAULT 0
            );
            """
        )

        # Миграция: добавить hidden если таблица уже существует без этого поля.
        cur.execute(
            """
            ALTER TABLE user_feeds ADD COLUMN IF NOT EXISTS hidden BOOLEAN DEFAULT FALSE;
            """
        )

        # Миграция: favicon_url для папок (каталожные источники).
        cur.execute(
            """
            ALTER TABLE feed_folders ADD COLUMN IF NOT EXISTS favicon_url TEXT;
            """
        )

        # Миграция: описание ленты (решение 1A).
        cur.execute(
            """
            ALTER TABLE feeds ADD COLUMN IF NOT EXISTS description TEXT;
            """
        )

        # Миграция: дата подписки пользователя (решение 1A).
        cur.execute(
            """
            ALTER TABLE user_feeds ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW();
            """
        )

        # Факты прочтения статей (Сценарий 1.5).
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS article_reads (
                link     TEXT NOT NULL,
                user_id  INT  NOT NULL DEFAULT 0,
                read_at  TIMESTAMPTZ DEFAULT NOW(),
                PRIMARY KEY (link, user_id)
            );
            """
        )

        # Закладки пользователей (Сценарий 2.1).
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS article_bookmarks (
                link     TEXT        NOT NULL,
                user_id  INT         NOT NULL DEFAULT 0,
                saved_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                PRIMARY KEY (link, user_id)
            );
            """
        )

        # Кэш статистики каталога: подписчики, посты в день, последний пост.
        # Обновляется раз в час через refresh_catalog_stats() — тяжёлые агрегаты не считаются при каждом запросе.
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS feed_catalog_stats (
                feed_id        INT PRIMARY KEY REFERENCES feeds(id) ON DELETE CASCADE,
                subscribers    INT DEFAULT 0,
                posts_per_week INT DEFAULT 0,
                last_post_at   TIMESTAMPTZ,
                updated_at     TIMESTAMPTZ DEFAULT NOW()
            );
            """
        )


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
    description: Optional[str] = None,
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
        from src.pipeline.taxonomy import get_collection_display_name
        name = get_collection_display_name(taxonomy, selection)
    discipline = selection.get("discipline")
    ga = selection.get("ga")
    activity = selection.get("activity")

    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT id, name, description, discipline, ga, activity, collection_key, user_id, team_id,
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
                SET last_refreshed_at = NOW(), updated_at = NOW(),
                    description = COALESCE(%s, description)
                WHERE id = %s
                RETURNING id, name, description, discipline, ga, activity, collection_key, user_id, team_id,
                          created_at, updated_at, last_refreshed_at;
                """,
                (description, row["id"]),
            )
            row = cur.fetchone()
        else:
            cur.execute(
                f"""
                INSERT INTO {POSTGRES_TABLE_COLLECTIONS}
                    (name, description, discipline, ga, activity, collection_key, user_id, team_id, updated_at, last_refreshed_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
                RETURNING id, name, description, discipline, ga, activity, collection_key, user_id, team_id,
                          created_at, updated_at, last_refreshed_at;
                """,
                (name, description, discipline, ga, activity, key, user_id, team_id),
            )
            row = cur.fetchone()
    if not row:
        return None
    return {
        "id": row["id"],
        "name": row["name"],
        "description": row["description"],
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
            SELECT c.id, c.name, c.description, c.discipline, c.ga, c.activity,
                   c.collection_key, c.user_id, c.team_id,
                   c.created_at, c.updated_at, c.last_refreshed_at,
                   COUNT(DISTINCT r.link) AS article_count
            FROM {POSTGRES_TABLE_COLLECTIONS} c
            LEFT JOIN {POSTGRES_TABLE_RAG_DOCUMENTS} r ON r.collection_id = c.id
            GROUP BY c.id
            ORDER BY c.updated_at DESC NULLS LAST, c.id DESC;
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
            SELECT id, name, description, discipline, ga, activity, collection_key, user_id, team_id,
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
            try:
                import pandas as pd
                if pd.isnull(published_at):
                    published_at = None
            except (TypeError, ValueError, ImportError):
                pass
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


def get_or_create_bertopic_collection(
    conn,
    topic_id: int,
    topic_name: str,
    model_version: str,
    description: Optional[str] = None,
) -> Optional[CollectionRow]:
    """
    Находит или создаёт коллекцию для BERTopic-темы.

    collection_key = "bertopic_topic_{topic_id}"
    discipline/ga/activity = NULL
    """
    if conn is None:
        return None
    key = f"bertopic_topic_{topic_id}"
    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT id, name, description, discipline, ga, activity, collection_key,
                   user_id, team_id, created_at, updated_at, last_refreshed_at
            FROM {POSTGRES_TABLE_COLLECTIONS}
            WHERE collection_key = %s AND name = %s;
            """,
            (key, topic_name),
        )
        row = cur.fetchone()
        if row:
            cur.execute(
                f"""
                UPDATE {POSTGRES_TABLE_COLLECTIONS}
                SET last_refreshed_at = NOW(), updated_at = NOW(),
                    bertopic_topic_id = %s, model_version = %s,
                    description = COALESCE(%s, description)
                WHERE id = %s
                RETURNING id, name, description, discipline, ga, activity, collection_key,
                          user_id, team_id, created_at, updated_at, last_refreshed_at;
                """,
                (topic_id, model_version, description, row["id"]),
            )
            row = cur.fetchone()
        else:
            cur.execute(
                f"""
                INSERT INTO {POSTGRES_TABLE_COLLECTIONS}
                    (name, description, discipline, ga, activity, collection_key,
                     bertopic_topic_id, model_version, updated_at, last_refreshed_at)
                VALUES (%s, %s, NULL, NULL, NULL, %s, %s, %s, NOW(), NOW())
                RETURNING id, name, description, discipline, ga, activity, collection_key,
                          user_id, team_id, created_at, updated_at, last_refreshed_at;
                """,
                (topic_name, description, key, topic_id, model_version),
            )
            row = cur.fetchone()
    if not row:
        return None
    return dict(row)


def upsert_bertopic_assignments(
    conn,
    assignments: List[Dict],
    model_version: str,
) -> int:
    """
    Вставляет или обновляет записи о принадлежности статей к BERTopic-темам.

    Каждый элемент assignments: {"link": str, "topic_id": int, "probability": float|None}
    """
    if conn is None or not assignments:
        return 0
    count = 0
    with conn.cursor() as cur:
        for a in assignments:
            link = a.get("link")
            topic_id = a.get("topic_id")
            if not link or topic_id is None:
                continue
            cur.execute(
                f"""
                INSERT INTO {POSTGRES_TABLE_BERTOPIC_ASSIGNMENTS}
                    (link, topic_id, probability, model_version, assigned_at)
                VALUES (%s, %s, %s, %s, NOW())
                ON CONFLICT (link, topic_id) DO UPDATE SET
                    probability   = EXCLUDED.probability,
                    model_version = EXCLUDED.model_version,
                    assigned_at   = NOW();
                """,
                (link, topic_id, a.get("probability"), model_version),
            )
            count += 1
    return count


def add_to_inbox(
    conn,
    articles: List[Dict],
) -> int:
    """
    Добавляет статьи в inbox_articles (буфер без чёткой темы).

    Каждый элемент: {"link": str, "title": str, "source": str, "embedding": list[float]|None}
    """
    if conn is None or not articles:
        return 0
    count = 0
    with conn.cursor() as cur:
        for art in articles:
            link = art.get("link")
            if not link:
                continue
            embedding = art.get("embedding")
            emb_str = _embedding_to_vector_str(embedding) if embedding else None
            cur.execute(
                f"""
                INSERT INTO {POSTGRES_TABLE_INBOX_ARTICLES}
                    (link, title, source, embedding, received_at)
                VALUES (%s, %s, %s, %s::vector, NOW())
                ON CONFLICT (link) DO NOTHING;
                """,
                (link, art.get("title") or "", art.get("source") or "", emb_str),
            )
            count += 1
    return count


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


# ---------------------------------------------------------------------------
# Feeds — управление RSS-лентами и подписками пользователей
# ---------------------------------------------------------------------------

def create_feed(conn, url: str, name: str, favicon_url: Optional[str] = None, category: Optional[str] = None, description: Optional[str] = None, folder_id: Optional[int] = None, user_id: Optional[int] = None) -> Optional[dict]:
    """
    Добавляет ленту в систему и подписывает пользователя.
    Если лента с таким URL уже существует — берёт её id (не создаёт дубль, не меняет данные).
    В однопользовательском режиме user_id=None → используем 0 как анонимный пользователь.
    Возвращает dict с данными подписки или None при ошибке.
    """
    if conn is None:
        return None
    _user_id = user_id if user_id is not None else 0
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO feeds (url, name, favicon_url, category, description)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (url) DO NOTHING
            RETURNING id, url, name, favicon_url, category, description, enabled, error_count, last_fetched_at;
            """,
            (url, name, favicon_url, category, description),
        )
        feed_row = cur.fetchone()
        if feed_row is None:
            cur.execute(
                "SELECT id, url, name, favicon_url, category, description, enabled, error_count, last_fetched_at FROM feeds WHERE url = %s;",
                (url,),
            )
            feed_row = cur.fetchone()
        feed = dict(feed_row)
        cur.execute(
            """
            INSERT INTO user_feeds (feed_id, user_id, folder_id)
            VALUES (%s, %s, %s)
            ON CONFLICT (feed_id, user_id) DO NOTHING;
            """,
            (feed["id"], _user_id, folder_id),
        )
        return feed


def list_feeds(conn, user_id: Optional[int] = None, include_hidden: bool = False) -> List[dict]:
    """
    Возвращает ленты на которые подписан пользователь.
    По умолчанию скрытые ленты (hidden=True) не возвращаются.
    include_hidden=True используется на странице настроек.
    В однопользовательском режиме user_id=None → используем 0.
    """
    if conn is None:
        return []
    _user_id = user_id if user_id is not None else 0
    # WHERE-клауза: фильтр по hidden должен быть в WHERE, а не после LEFT JOIN
    # (иначе парсер воспринимает его как продолжение ON-клаузы и хидден ленты
    # всё равно попадают в результат).
    hidden_where = "" if include_hidden else "WHERE uf.hidden = FALSE"
    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT f.id, f.url, f.name, f.favicon_url, f.description, f.category, f.enabled,
                   f.error_count, f.last_fetched_at, f.last_error,
                   uf.folder_id, uf.position, uf.hidden, uf.created_at,
                   COUNT(pa.link) FILTER (
                       WHERE pa.link IS NOT NULL
                         AND ar.link IS NULL
                   ) AS unread_count
            FROM feeds f
            JOIN user_feeds uf ON uf.feed_id = f.id AND uf.user_id = %s
            LEFT JOIN processed_articles pa ON pa.feed_id = f.id
            LEFT JOIN article_reads ar ON ar.link = pa.link AND ar.user_id = %s
            {hidden_where}
            GROUP BY f.id, f.url, f.name, f.favicon_url, f.description, f.category, f.enabled,
                     f.error_count, f.last_fetched_at, f.last_error,
                     uf.folder_id, uf.position, uf.hidden, uf.created_at
            ORDER BY uf.position ASC, f.name ASC;
            """,
            (_user_id, _user_id),
        )
        return [dict(r) for r in cur.fetchall()]


def get_user_feed_by_id(conn, feed_id: int, user_id: Optional[int] = None) -> Optional[dict]:
    """
    Возвращает полные данные подписки пользователя на ленту по feed_id.
    Включает favicon_url, unread_count, folder_id — всё то же что list_feeds но для одной ленты.
    Возвращает None если пользователь не подписан на эту ленту или лента не существует.
    """
    if conn is None:
        return None
    _user_id = user_id if user_id is not None else 0
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT f.id, f.url, f.name, f.favicon_url, f.description, f.category, f.enabled,
                   f.error_count, f.last_fetched_at, f.last_error,
                   uf.folder_id, uf.position, uf.hidden, uf.created_at,
                   COUNT(pa.link) FILTER (
                       WHERE pa.link IS NOT NULL
                         AND ar.link IS NULL
                   ) AS unread_count
            FROM feeds f
            JOIN user_feeds uf ON uf.feed_id = f.id AND uf.user_id = %s
            LEFT JOIN processed_articles pa ON pa.feed_id = f.id
            LEFT JOIN article_reads ar ON ar.link = pa.link AND ar.user_id = %s
            WHERE f.id = %s
            GROUP BY f.id, f.url, f.name, f.favicon_url, f.description, f.category, f.enabled,
                     f.error_count, f.last_fetched_at, f.last_error,
                     uf.folder_id, uf.position, uf.hidden, uf.created_at;
            """,
            (_user_id, _user_id, feed_id),
        )
        row = cur.fetchone()
        return dict(row) if row else None


def get_feed_by_id(conn, feed_id: int) -> Optional[dict]:
    """Возвращает ленту из таблицы feeds по ID, или None если не найдена."""
    if conn is None:
        return None
    with conn.cursor() as cur:
        cur.execute("SELECT id, url, name, enabled FROM feeds WHERE id = %s;", (feed_id,))
        row = cur.fetchone()
        return dict(row) if row else None


def delete_feed(conn, feed_id: int, user_id: Optional[int] = None) -> bool:
    """
    Удаляет подписку пользователя на ленту (запись из user_feeds).
    Саму ленту в feeds не трогает — другие пользователи могут быть подписаны.
    В однопользовательском режиме user_id=None → используем 0.
    Возвращает True если подписка была найдена и удалена.
    """
    if conn is None:
        return False
    _user_id = user_id if user_id is not None else 0
    with conn.cursor() as cur:
        cur.execute(
            """
            DELETE FROM user_feeds
            WHERE feed_id = %s AND user_id = %s;
            """,
            (feed_id, _user_id),
        )
        return cur.rowcount > 0


def update_feed(conn, feed_id: int, user_id: Optional[int] = None, **kwargs) -> Optional[dict]:
    """
    Обновляет пользовательские настройки подписки: name, enabled, folder_id, position, hidden.
    Возвращает обновлённую запись или None если подписка не найдена.
    """
    if conn is None:
        return None
    _user_id = user_id if user_id is not None else 0
    allowed = {"folder_id", "position", "hidden"}
    feed_allowed = {"name", "enabled"}
    user_updates = {k: v for k, v in kwargs.items() if k in allowed}
    feed_updates = {k: v for k, v in kwargs.items() if k in feed_allowed}

    with conn.cursor() as cur:
        if feed_updates:
            set_clause = ", ".join(f"{k} = %s" for k in feed_updates)
            cur.execute(
                f"UPDATE feeds SET {set_clause} WHERE id = %s;",
                list(feed_updates.values()) + [feed_id],
            )
        if user_updates:
            set_clause = ", ".join(f"{k} = %s" for k in user_updates)
            cur.execute(
                f"UPDATE user_feeds SET {set_clause} WHERE feed_id = %s AND user_id = %s;",
                list(user_updates.values()) + [feed_id, _user_id],
            )
        cur.execute(
            """
            SELECT f.id, f.url, f.name, f.favicon_url, f.description, f.category, f.enabled,
                   f.error_count, f.last_fetched_at, f.last_error,
                   uf.folder_id, uf.position, uf.hidden, uf.created_at,
                   COUNT(pa.link) FILTER (
                       WHERE pa.link IS NOT NULL AND ar.link IS NULL
                   ) AS unread_count
            FROM feeds f
            JOIN user_feeds uf ON uf.feed_id = f.id
            LEFT JOIN processed_articles pa ON pa.feed_id = f.id
            LEFT JOIN article_reads ar ON ar.link = pa.link AND ar.user_id = %s
            WHERE f.id = %s AND uf.user_id = %s
            GROUP BY f.id, f.url, f.name, f.favicon_url, f.description, f.category, f.enabled,
                     f.error_count, f.last_fetched_at, f.last_error,
                     uf.folder_id, uf.position, uf.hidden, uf.created_at;
            """,
            (_user_id, feed_id, _user_id),
        )
        row = cur.fetchone()
        return dict(row) if row else None


def update_feed_status(conn, url: str, error: Optional[str] = None) -> None:
    """
    Вызывается сборщиком после каждой попытки опросить ленту.
    При успехе (error=None): обнуляет error_count, обновляет last_fetched_at.
    При ошибке: записывает текст в last_error, инкрементирует error_count.
    """
    if conn is None:
        return
    with conn.cursor() as cur:
        if error is None:
            cur.execute(
                """
                UPDATE feeds SET error_count = 0, last_error = NULL, last_fetched_at = NOW()
                WHERE url = %s;
                """,
                (url,),
            )
        else:
            cur.execute(
                """
                UPDATE feeds SET error_count = error_count + 1, last_error = %s
                WHERE url = %s;
                """,
                (error, url),
            )


def get_feeds_as_dict(conn) -> dict:
    """
    Возвращает все активные ленты в формате {name: url}
    для передачи в collect_articles_for_window().
    Включает и каталожные ленты (is_catalog=TRUE), и ленты пользователей —
    чтобы scheduler обновлял и главную страницу, и подписки.
    Если таблица пустая — возвращает пустой dict (fallback на config).
    """
    if conn is None:
        return {}
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT DISTINCT f.name, f.url
            FROM feeds f
            WHERE f.enabled = TRUE;
            """
        )
        rows = cur.fetchall()
        return {r["name"]: r["url"] for r in rows}

def load_feed_url_id_map(conn) -> Dict[str, int]:
    """
    Возвращает словарь {url: feed_id} для всех лент в таблице feeds.

    Используется сборщиком чтобы проставить feed_id на каждую статью
    в момент сохранения — без зависимости от строкового ключа source.
    """
    if conn is None:
        return {}
    with conn.cursor() as cur:
        cur.execute("SELECT id, url FROM feeds;")
        return {row["url"]: row["id"] for row in cur.fetchall()}


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

            feed_id = art.get("feed_id")

            cur.execute(
                f"""
                INSERT INTO {POSTGRES_TABLE_PROCESSED_ARTICLES} (source, link, published_at, title, summary, feed_id)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (link) DO UPDATE SET
                    title   = EXCLUDED.title,
                    summary = EXCLUDED.summary,
                    published_at = COALESCE(EXCLUDED.published_at, {POSTGRES_TABLE_PROCESSED_ARTICLES}.published_at),
                    feed_id = COALESCE(EXCLUDED.feed_id, {POSTGRES_TABLE_PROCESSED_ARTICLES}.feed_id);
                """,
                (source, link, published_dt, title, summary, feed_id),
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


# ─────────────────────────────────────────────────────────────
#  Сценарий 1.2 — Каталог лент
# ─────────────────────────────────────────────────────────────

def import_catalog_feeds(conn) -> int:
    """
    Импортирует ленты из config.RSS_FEEDS в таблицу feeds с флагом is_catalog=True.

    Вызывается при старте сервера. Ленты которые уже есть в таблице не перезаписываются
    (ON CONFLICT DO NOTHING). Возвращает количество новых записей.
    """
    if conn is None:
        return 0
    from urllib.parse import urlparse
    count = 0
    with conn.cursor() as cur:
        for name, feed in RSS_FEEDS.items():
            url = feed["url"] if isinstance(feed, dict) else feed
            category = feed.get("category") if isinstance(feed, dict) else None
            if not url:
                continue
            domain = urlparse(url).netloc
            favicon_url = f"https://www.google.com/s2/favicons?domain={domain}&sz=32"
            cur.execute(
                """
                INSERT INTO feeds (url, name, favicon_url, category, is_catalog, enabled)
                VALUES (%s, %s, %s, %s, TRUE, TRUE)
                ON CONFLICT (url) DO UPDATE SET
                    is_catalog = TRUE,
                    name       = EXCLUDED.name,
                    category   = COALESCE(EXCLUDED.category, feeds.category)
                RETURNING (xmax = 0) AS inserted;
                """,
                (url, name, favicon_url, category),
            )
            row = cur.fetchone()
            if row and row["inserted"]:
                count += 1
    conn.commit()
    logger.info("import_catalog_feeds: добавлено %d новых лент в каталог", count)
    return count


def refresh_catalog_stats(conn) -> None:
    """
    Пересчитывает статистику для всех каталожных лент и сохраняет в feed_catalog_stats.

    Для каждой ленты считает:
    - subscribers    — кол-во пользователей подписанных через user_feeds
    - posts_per_week — кол-во постов в неделю за последние 30 дней (целое число)
    - last_post_at   — дата последней статьи за всё время (без ограничения 30 дней)

    Связь со статьями: сначала по feed_id (надёжно), фоллбэк на source = feeds.name
    для старых статей собранных до добавления feed_id.

    Вызывается при старте сервера и раз в час планировщиком.
    """
    if conn is None:
        return
    with conn.cursor() as cur:
        cur.execute("SELECT id, name FROM feeds WHERE is_catalog = TRUE;")
        feeds = cur.fetchall()

        for feed in feeds:
            feed_id = feed["id"]
            feed_name = feed["name"]

            cur.execute(
                "SELECT COUNT(*) AS cnt FROM user_feeds WHERE feed_id = %s;",
                (feed_id,),
            )
            subscribers = cur.fetchone()["cnt"]

            cur.execute(
                f"""
                SELECT
                    COUNT(*) FILTER (WHERE published_at > NOW() - INTERVAL '7 days')
                        AS posts_per_week,
                    MAX(published_at) AS last_post_at
                FROM {POSTGRES_TABLE_PROCESSED_ARTICLES}
                WHERE feed_id = %s
                   OR (feed_id IS NULL AND source = %s);
                """,
                (feed_id, feed_name),
            )
            stats = cur.fetchone()
            posts_per_week = int(stats["posts_per_week"] or 0)
            last_post_at = stats["last_post_at"]

            cur.execute(
                """
                INSERT INTO feed_catalog_stats
                    (feed_id, subscribers, posts_per_week, last_post_at, updated_at)
                VALUES (%s, %s, %s, %s, NOW())
                ON CONFLICT (feed_id) DO UPDATE SET
                    subscribers    = EXCLUDED.subscribers,
                    posts_per_week = EXCLUDED.posts_per_week,
                    last_post_at   = EXCLUDED.last_post_at,
                    updated_at     = NOW();
                """,
                (feed_id, subscribers, posts_per_week, last_post_at),
            )
    conn.commit()
    logger.info("refresh_catalog_stats: статистика обновлена для %d лент", len(feeds))


def list_catalog_feeds(conn, user_id=None):
    """
    Возвращает все ленты каталога (is_catalog=True) со статистикой и флагом подписки.

    Флаг is_subscribed=True если пользователь уже подписан на ленту через user_feeds.
    Статистика берётся из кэша feed_catalog_stats — быстро.
    В однопользовательском режиме user_id=None → используем 0.
    """
    if conn is None:
        return []
    _user_id = user_id if user_id is not None else 0
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                f.id, f.url, f.name, f.favicon_url, f.description, f.category, f.enabled,
                f.error_count, f.last_fetched_at,
                COALESCE(s.subscribers, 0)    AS subscribers,
                COALESCE(s.posts_per_week, 0) AS posts_per_week,
                s.last_post_at,
                CASE WHEN uf.feed_id IS NOT NULL THEN TRUE ELSE FALSE END AS is_subscribed
            FROM feeds f
            LEFT JOIN feed_catalog_stats s ON s.feed_id = f.id
            LEFT JOIN user_feeds uf
                ON uf.feed_id = f.id
               AND uf.user_id = %s
            WHERE f.is_catalog = TRUE
            ORDER BY f.name;
            """,
            (_user_id,),
        )
        return [dict(row) for row in cur.fetchall()]


def update_feed_descriptions(conn, feed_descriptions: dict) -> None:
    """
    Сохраняет описания лент в feeds.description.
    Записывает только если description ещё не заполнен (IS NULL).
    feed_descriptions: {url: description}
    """
    if not feed_descriptions or conn is None:
        return
    with conn.cursor() as cur:
        for url, description in feed_descriptions.items():
            cur.execute(
                "UPDATE feeds SET description = %s WHERE url = %s AND description IS NULL;",
                (description, url),
            )
    conn.commit()
    logger.info("update_feed_descriptions: обновлено %d описаний лент", len(feed_descriptions))


# ─────────────────────────────────────────────────────────────
#  Папки (Сценарий 1.3)
# ─────────────────────────────────────────────────────────────

def create_folder(conn, name: str, favicon_url: Optional[str] = None, user_id: Optional[int] = None) -> dict:
    """
    Создаёт папку в боковой панели.
    Возвращает созданную папку с id.
    """
    _user_id = user_id if user_id is not None else 0
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO feed_folders (user_id, name, favicon_url)
            VALUES (%s, %s, %s)
            RETURNING id, user_id, name, position, favicon_url;
            """,
            (_user_id, name, favicon_url),
        )
        return dict(cur.fetchone())


def list_folders(conn, user_id: Optional[int] = None) -> List[dict]:
    """
    Возвращает все папки пользователя, отсортированные по position.
    """
    _user_id = user_id if user_id is not None else 0
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, user_id, name, position, favicon_url
            FROM feed_folders
            WHERE user_id = %s
            ORDER BY position ASC, name ASC;
            """,
            (_user_id,),
        )
        return [dict(row) for row in cur.fetchall()]


def update_folder(conn, folder_id: int, user_id: Optional[int] = None, **kwargs) -> Optional[dict]:
    """
    Обновляет name или position папки.
    Возвращает обновлённую папку или None если не найдена.
    """
    _user_id = user_id if user_id is not None else 0
    allowed = {"name", "position"}
    updates = {k: v for k, v in kwargs.items() if k in allowed}
    if not updates:
        return None
    with conn.cursor() as cur:
        set_clause = ", ".join(f"{k} = %s" for k in updates)
        cur.execute(
            f"""
            UPDATE feed_folders SET {set_clause}
            WHERE id = %s AND user_id = %s
            RETURNING id, user_id, name, position;
            """,
            list(updates.values()) + [folder_id, _user_id],
        )
        row = cur.fetchone()
        return dict(row) if row else None


def delete_folder(conn, folder_id: int, user_id: Optional[int] = None) -> bool:
    """
    Удаляет папку. Ленты внутри перемещаются в корень (folder_id = NULL).
    Возвращает True если папка найдена и удалена.
    """
    _user_id = user_id if user_id is not None else 0
    with conn.cursor() as cur:
        # Перемещаем ленты в корень
        cur.execute(
            "UPDATE user_feeds SET folder_id = NULL WHERE folder_id = %s AND user_id = %s;",
            (folder_id, _user_id),
        )
        cur.execute(
            "DELETE FROM feed_folders WHERE id = %s AND user_id = %s;",
            (folder_id, _user_id),
        )
        return cur.rowcount > 0


# ─────────────────────────────────────────────────────────────
#  Все статьи подписок (Сценарий 1.3 — "Все посты")
# ─────────────────────────────────────────────────────────────

def list_all_articles(
    conn, user_id: int = 0, page: int = 1, page_size: int = 30
) -> List[dict]:
    """
    "Все посты": все статьи из всех подписок пользователя с пагинацией.
    Скрытые ленты исключены. Отсортированы по дате (новые первые).
    """
    if conn is None:
        return []
    offset = (page - 1) * page_size
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                pa.id,
                pa.link,
                pa.title,
                pa.summary,
                pa.published_at,
                pa.source,
                (ar.link IS NOT NULL) AS is_read,
                (ab.link IS NOT NULL) AS is_saved
            FROM processed_articles pa
            JOIN user_feeds uf ON uf.feed_id = pa.feed_id AND uf.user_id = %s
            LEFT JOIN article_reads ar ON ar.link = pa.link AND ar.user_id = %s
            LEFT JOIN article_bookmarks ab ON ab.link = pa.link AND ab.user_id = %s
            WHERE uf.hidden = FALSE
            ORDER BY pa.published_at DESC NULLS LAST
            LIMIT %s OFFSET %s;
            """,
            (user_id, user_id, user_id, page_size, offset),
        )
        return [dict(row) for row in cur.fetchall()]


# ─────────────────────────────────────────────────────────────
#  Статьи ленты (Сценарий 1.4)
# ─────────────────────────────────────────────────────────────

def list_feed_articles(
    conn,
    feed_id: int,
    page: int = 1,
    page_size: int = 30,
    user_id: int = 0,
    unread_only: bool = False,
) -> List[dict]:
    """
    Возвращает статьи ленты с пагинацией, отсортированные по дате (новые первые).
    Поле is_read определяется через LEFT JOIN с article_reads.
    unread_only=True — возвращает только непрочитанные статьи.
    """
    if conn is None:
        return []
    offset = (page - 1) * page_size
    unread_filter = "AND ar.link IS NULL" if unread_only else ""
    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT
                pa.id,
                pa.link,
                pa.title,
                pa.summary,
                pa.published_at,
                pa.source,
                (ar.link IS NOT NULL) AS is_read,
                (ab.link IS NOT NULL) AS is_saved
            FROM processed_articles pa
            LEFT JOIN article_reads ar
                ON ar.link = pa.link AND ar.user_id = %s
            LEFT JOIN article_bookmarks ab
                ON ab.link = pa.link AND ab.user_id = %s
            WHERE pa.feed_id = %s
            {unread_filter}
            ORDER BY pa.published_at DESC NULLS LAST
            LIMIT %s OFFSET %s;
            """,
            (user_id, user_id, feed_id, page_size, offset),
        )
        return [dict(row) for row in cur.fetchall()]


def list_articles_by_feed_ids(
    conn,
    feed_ids: List[int],
    page: int = 1,
    page_size: int = 30,
    user_id: int = 0,
) -> List[dict]:
    """
    Возвращает статьи из нескольких лент одновременно, отсортированные по дате (новые первые).
    Используется для боковой панели мульти-лентных источников (например, все ленты Google).
    """
    if conn is None or not feed_ids:
        return []
    offset = (page - 1) * page_size
    placeholders = ",".join(["%s"] * len(feed_ids))
    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT
                pa.id,
                pa.link,
                pa.title,
                pa.summary,
                pa.published_at,
                pa.source,
                (ar.link IS NOT NULL) AS is_read,
                (ab.link IS NOT NULL) AS is_saved
            FROM processed_articles pa
            LEFT JOIN article_reads ar
                ON ar.link = pa.link AND ar.user_id = %s
            LEFT JOIN article_bookmarks ab
                ON ab.link = pa.link AND ab.user_id = %s
            WHERE pa.feed_id IN ({placeholders})
            ORDER BY pa.published_at DESC NULLS LAST
            LIMIT %s OFFSET %s;
            """,
            (user_id, user_id, *feed_ids, page_size, offset),
        )
        return [dict(row) for row in cur.fetchall()]


def get_article_by_id(conn, article_id: int, user_id: int = 0) -> Optional[dict]:
    """
    Возвращает полные данные статьи по id, включая full_text и is_read.
    Возвращает None если статья не найдена.
    """
    if conn is None:
        return None
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                pa.id,
                pa.link,
                pa.title,
                pa.summary,
                pa.full_text,
                pa.published_at,
                pa.source,
                (ar.link IS NOT NULL) AS is_read,
                (ab.link IS NOT NULL) AS is_saved
            FROM processed_articles pa
            LEFT JOIN article_reads ar
                ON ar.link = pa.link AND ar.user_id = %s
            LEFT JOIN article_bookmarks ab
                ON ab.link = pa.link AND ab.user_id = %s
            WHERE pa.id = %s;
            """,
            (user_id, user_id, article_id),
        )
        row = cur.fetchone()
        return dict(row) if row else None


def update_article_full_text(conn, article_id: int, full_text: str) -> None:
    """Сохраняет извлечённый full_text в processed_articles."""
    if conn is None:
        return
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE processed_articles SET full_text = %s WHERE id = %s;",
            (full_text, article_id),
        )


def get_article_for_summarize(conn, article_id: int) -> Optional[dict]:
    """
    Возвращает минимальный набор полей для эндпоинта суммаризации:
    {id, link, title, full_text, ai_summary}.
    Возвращает None если статья не найдена.
    """
    if conn is None:
        return None
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, link, title, full_text, ai_summary
            FROM processed_articles
            WHERE id = %s;
            """,
            (article_id,),
        )
        row = cur.fetchone()
        return dict(row) if row else None


def save_ai_summary(conn, article_id: int, ai_summary: str) -> None:
    """Сохраняет AI-резюме в processed_articles (кэш для повторных запросов)."""
    if conn is None:
        return
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE processed_articles SET ai_summary = %s WHERE id = %s;",
            (ai_summary, article_id),
        )


def mark_article_read(conn, link: str, user_id: int = 0) -> None:
    """Помечает статью прочитанной (INSERT ON CONFLICT DO NOTHING)."""
    if conn is None:
        return
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO article_reads (link, user_id)
            VALUES (%s, %s)
            ON CONFLICT (link, user_id) DO NOTHING;
            """,
            (link, user_id),
        )


def mark_article_unread(conn, link: str, user_id: int = 0) -> None:
    """Снимает метку прочитанного (DELETE). Идемпотентна."""
    if conn is None:
        return
    with conn.cursor() as cur:
        cur.execute(
            "DELETE FROM article_reads WHERE link = %s AND user_id = %s;",
            (link, user_id),
        )


def mark_feed_all_read(conn, feed_id: int, user_id: int = 0) -> int:
    """
    Помечает все статьи ленты прочитанными.
    Возвращает количество новых записей (не считая уже прочитанных).
    """
    if conn is None:
        return 0
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO article_reads (link, user_id)
            SELECT pa.link, %s
            FROM processed_articles pa
            WHERE pa.feed_id = %s
            ON CONFLICT (link, user_id) DO NOTHING;
            """,
            (user_id, feed_id),
        )
        return cur.rowcount


def get_read_links(conn, links: List[str], user_id: int = 0) -> Set[str]:
    """Возвращает множество ссылок, которые пользователь уже прочитал."""
    if conn is None or not links:
        return set()
    with conn.cursor() as cur:
        cur.execute(
            "SELECT link FROM article_reads WHERE link = ANY(%s) AND user_id = %s;",
            (links, user_id),
        )
        return {row["link"] for row in cur.fetchall()}


def list_unread_articles(
    conn, user_id: int = 0, page: int = 1, page_size: int = 30
) -> List[dict]:
    """
    Умная папка "Непрочитанное": все непрочитанные статьи из всех лент пользователя.
    Отсортированы по дате (новые первые).
    """
    if conn is None:
        return []
    offset = (page - 1) * page_size
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                pa.id,
                pa.link,
                pa.title,
                pa.summary,
                pa.published_at,
                pa.source,
                FALSE AS is_read,
                (ab.link IS NOT NULL) AS is_saved
            FROM processed_articles pa
            JOIN user_feeds uf ON uf.feed_id = pa.feed_id AND uf.user_id = %s
            LEFT JOIN article_reads ar ON ar.link = pa.link AND ar.user_id = %s
            LEFT JOIN article_bookmarks ab ON ab.link = pa.link AND ab.user_id = %s
            WHERE ar.link IS NULL
              AND uf.hidden = FALSE
            ORDER BY pa.published_at DESC NULLS LAST
            LIMIT %s OFFSET %s;
            """,
            (user_id, user_id, user_id, page_size, offset),
        )
        return [dict(row) for row in cur.fetchall()]


def list_today_articles(
    conn, user_id: int = 0
) -> List[dict]:
    """
    Умная папка "Сегодня": все статьи из лент пользователя опубликованные сегодня.
    Возвращает все статьи без ограничений — за один день их обычно немного.
    Отсортированы по дате (новые первые).
    """
    if conn is None:
        return []
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                pa.id,
                pa.link,
                pa.title,
                pa.summary,
                pa.published_at,
                pa.source,
                (ar.link IS NOT NULL) AS is_read,
                (ab.link IS NOT NULL) AS is_saved
            FROM processed_articles pa
            JOIN user_feeds uf ON uf.feed_id = pa.feed_id AND uf.user_id = %s
            LEFT JOIN article_reads ar ON ar.link = pa.link AND ar.user_id = %s
            LEFT JOIN article_bookmarks ab ON ab.link = pa.link AND ab.user_id = %s
            WHERE pa.published_at >= CURRENT_DATE
              AND uf.hidden = FALSE
            ORDER BY pa.published_at DESC NULLS LAST;
            """,
            (user_id, user_id, user_id),
        )
        return [dict(row) for row in cur.fetchall()]


def add_bookmark(conn, link: str, user_id: int = 0) -> None:
    """Добавляет статью в закладки. Повторный вызов безопасен (ON CONFLICT DO NOTHING)."""
    if conn is None:
        return
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO article_bookmarks (link, user_id) VALUES (%s, %s) ON CONFLICT DO NOTHING;",
            (link, user_id),
        )


def remove_bookmark(conn, link: str, user_id: int = 0) -> None:
    """Удаляет статью из закладок."""
    if conn is None:
        return
    with conn.cursor() as cur:
        cur.execute(
            "DELETE FROM article_bookmarks WHERE link = %s AND user_id = %s;",
            (link, user_id),
        )


def list_bookmarks(
    conn, user_id: int = 0, page: int = 1, page_size: int = 30
) -> List[dict]:
    """
    Возвращает закладки пользователя, отсортированные по дате сохранения (новые первые).
    """
    if conn is None:
        return []
    offset = (page - 1) * page_size
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                pa.id,
                pa.link,
                pa.title,
                pa.summary,
                pa.published_at,
                pa.source,
                (ar.link IS NOT NULL) AS is_read,
                TRUE AS is_saved,
                ab.saved_at
            FROM processed_articles pa
            JOIN article_bookmarks ab ON ab.link = pa.link AND ab.user_id = %s
            LEFT JOIN article_reads ar ON ar.link = pa.link AND ar.user_id = %s
            ORDER BY ab.saved_at DESC
            LIMIT %s OFFSET %s;
            """,
            (user_id, user_id, page_size, offset),
        )
        return [dict(row) for row in cur.fetchall()]


def get_articles_by_feed_ids(
    conn,
    feed_ids: list[int],
    from_date=None,
    to_date=None,
    limit: int = 150,
    user_id: int = 0,
) -> list[dict]:
    """Статьи из processed_articles по списку feed_ids (для QA/Digest без RAG)."""
    if conn is None or not feed_ids:
        return []
    conditions = ["pa.feed_id = ANY(%s)"]
    params: list = [feed_ids]
    if from_date is not None:
        conditions.append("pa.published_at >= %s")
        params.append(from_date)
    if to_date is not None:
        conditions.append("pa.published_at <= %s")
        params.append(to_date)
    where = " AND ".join(conditions)
    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT pa.id, pa.link, pa.title, pa.ai_summary, pa.summary,
                   pa.full_text, pa.published_at, pa.source, pa.feed_id,
                   rf.name AS feed_name
            FROM processed_articles pa
            LEFT JOIN feeds rf ON rf.id = pa.feed_id
            WHERE {where}
            ORDER BY pa.published_at DESC NULLS LAST
            LIMIT %s;
            """,
            params + [limit],
        )
        return [dict(row) for row in cur.fetchall()]


def search_articles(conn, query: str, user_id: int = 0, limit: int = 20) -> list[dict]:
    """Поиск статей по заголовку и ai_summary. Только по лентам пользователя."""
    if conn is None:
        return []
    pattern = f"%{query}%"
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT DISTINCT
                pa.id,
                pa.link,
                pa.title,
                pa.summary,
                pa.published_at,
                pa.source,
                pa.feed_id,
                (ar.link IS NOT NULL) AS is_read,
                (ab.link IS NOT NULL) AS is_saved
            FROM processed_articles pa
            JOIN user_feeds uf ON uf.feed_id = pa.feed_id AND uf.user_id = %s
            LEFT JOIN article_reads ar ON ar.link = pa.link AND ar.user_id = %s
            LEFT JOIN article_bookmarks ab ON ab.link = pa.link AND ab.user_id = %s
            WHERE
                pa.title ILIKE %s
                OR pa.ai_summary ILIKE %s
                OR pa.summary ILIKE %s
            ORDER BY pa.published_at DESC NULLS LAST
            LIMIT %s;
            """,
            (user_id, user_id, user_id, pattern, pattern, pattern, limit),
        )
        return [dict(row) for row in cur.fetchall()]
