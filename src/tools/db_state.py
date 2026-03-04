"""
Утилиты для работы с PostgreSQL: хранение состояния краулера.

Храним:
- таблица processed_articles: уникальные обработанные статьи (дедуп по link)
- таблица crawler_feed_state: last_processed_published_at по каждому RSS-источнику
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Dict, Iterable, List, Optional, Set

import pandas as pd
import psycopg2
from psycopg2.extras import DictCursor

from config.config import (
    POSTGRES_DB,
    POSTGRES_ENABLED,
    POSTGRES_HOST,
    POSTGRES_PASSWORD,
    POSTGRES_PORT,
    POSTGRES_TABLE_FEED_STATE,
    POSTGRES_TABLE_PROCESSED_ARTICLES,
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
        # Вставка обработанных статей (игнорируем дубликаты по link)
        for art in articles:
            source = art.get("source")
            link = art.get("link")
            published_dt = art.get("published_dt")
            title = art.get("title") or ""
            summary = art.get("summary") or ""

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

