# -*- coding: utf-8 -*-
"""
FastAPI-приложение системы Content Intelligence Platform.

Запуск: uvicorn src.api.app:app --reload --host 0.0.0.0 --port 8000
Swagger UI: http://localhost:8000/docs
ReDoc:       http://localhost:8000/redoc
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .schemas import (
    ArticleDetail,
    ArticleItem,
    ArticleReadRequest,
    CatalogFeedItem,
    CollectionArticle,
    CollectionItem,
    FeedCreate,
    FeedItem,
    FeedUpdate,
    FeedValidateRequest,
    FeedValidateResponse,
    FolderCreate,
    FolderItem,
    FolderUpdate,
    PipelineRunRequest,
    PipelineRunResponse,
    QARequest,
    QAResponse,
    QASource,
    RouterRequest,
    RouterResponse,
    RssCollectRequest,
    RssCollectResponse,
    serialize_digest_section_item,
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    from src.tools.db_state import (
        get_connection,
        ensure_tables,
        import_catalog_feeds,
        refresh_catalog_stats,
    )
    conn = get_connection()
    ensure_tables(conn)
    logger.info("БД инициализирована: все таблицы созданы.")
    imported = import_catalog_feeds(conn)
    logger.info("Каталог лент: импортировано %d новых лент из config.RSS_FEEDS.", imported)
    refresh_catalog_stats(conn)
    logger.info("Статистика каталога обновлена.")
    yield


_TAGS_METADATA = [
    {
        "name": "Служебные",
        "description": "Проверка доступности API.",
    },
    {
        "name": "Роутер",
    },
    {
        "name": "Коллекции",
    },
    {
        "name": "RSS",
        "description": "Сбор новых статей из RSS-источников в базу данных.",
    },
    {
        "name": "Пайплайн",
        "description": "Обработка статей из БД: фильтрация, эмбеддинги, суммаризация, RAG.",
    },
    {
        "name": "Q&A",
    },
    {
        "name": "Дайджест",
    },
    {
        "name": "Ленты",
        "description": "Управление RSS-лентами и подписками пользователей.",
    },
    {
        "name": "Каталог",
        "description": "Системный каталог лент из config.RSS_FEEDS — подписка/отписка одним кликом.",
    },
]

app = FastAPI(
    lifespan=lifespan,
    title="Content Intelligence Platform",
    description=(
        "API системы автоматизированного сбора, фильтрации и интеллектуального поиска "
        "по коллекциям статей из открытых источников.\n\n"
        "**Основные сценарии:**\n"
        "- Подбор темы через агент-роутер (`/api/router`)\n"
        "- Запуск пайплайна сбора и индексации (`/api/pipeline/run`)\n"
        "- Просмотр коллекций и статей (`/api/collections`)\n"
        "- Q&A по коллекции с указанием источников (`/api/qa`)\n"
        "- Формирование дайджеста по разделам (`/api/digest/{collection_id}`)"
    ),
    version="1.0.0",
    openapi_tags=_TAGS_METADATA,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent / "frontend"


def _router_state_to_response(state: dict) -> RouterResponse:
    return RouterResponse(
        status=state.get("status") or "not_found",
        selection=state.get("selection"),
        clarification_question=state.get("clarification_question"),
        confidence=float(state.get("confidence") or 0),
        reasoning=state.get("reasoning"),
        user_query=state.get("user_query") or "",
    )


@app.get(
    "/api/health",
    tags=["Служебные"],
    summary="Проверка доступности API",
    response_description="Статус сервера",
)
def health():
    """Возвращает `{\"status\": \"ok\"}` если сервер запущен и принимает запросы."""
    return {"status": "ok"}


@app.post(
    "/api/router",
    tags=["Роутер"],
    summary="Подбор темы по запросу пользователя",
    response_model=RouterResponse,
    response_description="Результат сопоставления запроса с таксономией",
)
def router_query(body: RouterRequest):
    """
    - **matched** — найден узел таксономии, возвращается `selection`
    - **not_found** — подходящий узел не определён
    - **clarification_needed** — тема неоднозначна, возвращается `clarification_question`
    """
    try:
        from src.agents.router import run_router
        state = run_router(user_query=body.query.strip())
        return _router_state_to_response(state)
    except Exception as e:
        logger.exception("Router error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get(
    "/api/collections",
    tags=["Коллекции"],
    summary="Список всех коллекций",
    response_model=list[CollectionItem],
    response_description="Массив коллекций с метаданными",
)
def list_collections():
    """Возвращает все коллекции, созданные в системе, с метаданными таксономии и датами обновления."""
    from src.tools.db_state import get_connection, list_collections as _list
    conn = get_connection()
    rows = _list(conn)
    return [CollectionItem(**r) for r in rows]


@app.get(
    "/api/collections/{collection_id}",
    tags=["Коллекции"],
    summary="Получить коллекцию по ID",
    response_model=CollectionItem,
    response_description="Метаданные коллекции",
    responses={404: {"description": "Коллекция не найдена"}},
)
def get_collection(collection_id: int):
    from src.tools.db_state import get_connection, get_collection_by_id
    conn = get_connection()
    row = get_collection_by_id(conn, collection_id)
    if not row:
        raise HTTPException(status_code=404, detail="Коллекция не найдена")
    return CollectionItem(**row)


@app.get(
    "/api/collections/{collection_id}/articles",
    tags=["Коллекции"],
    summary="Статьи коллекции",
    response_model=list[CollectionArticle],
    response_description="Массив статей с заголовками, аннотациями и ссылками",
    responses={404: {"description": "Коллекция не найдена"}},
)
def list_collection_articles(collection_id: int):
    from src.tools.db_state import get_connection, get_collection_by_id, get_articles_for_collection
    conn = get_connection()
    if not get_collection_by_id(conn, collection_id):
        raise HTTPException(status_code=404, detail="Коллекция не найдена")
    rows = get_articles_for_collection(conn, collection_id)
    return [CollectionArticle(**r) for r in rows]


@app.post(
    "/api/rss/collect",
    tags=["RSS"],
    summary="Собрать новые статьи из RSS-лент",
    response_model=RssCollectResponse,
    response_description="Статистика сбора: новые статьи, дубли, время выполнения",
)
def rss_collect_endpoint(body: RssCollectRequest):
    """
    Обходит все настроенные RSS-ленты и сохраняет **только новые** статьи в `processed_articles`.

    - Использует `last_processed_published_at` — не пересохраняет уже известные статьи.
    - Не выполняет фильтрацию, эмбеддинги или суммаризацию — только сбор сырых данных.
    - Вызывайте этот эндпоинт по расписанию (например, раз в час), а `POST /api/pipeline/run` — по запросу пользователя.
    """
    try:
        from src.main import collect_rss
        stats = collect_rss(
            hours_back=body.hours_back,
            limit_per_feed=body.limit_per_feed,
        )
        new_articles = stats.get("unique_articles", 0)
        # Обновляем статистику каталога после сбора
        from src.tools.db_state import get_connection, refresh_catalog_stats
        refresh_catalog_stats(get_connection())
        return RssCollectResponse(
            success=True,
            new_articles=new_articles,
            total_parsed=stats.get("total_parsed", 0),
            duplicates_skipped=stats.get("duplicates_skipped", 0),
            already_processed_skipped=stats.get("already_processed_skipped", 0),
            feeds_processed=stats.get("feeds_processed", 0),
            feeds_failed=stats.get("feeds_failed", 0),
            time_elapsed_sec=round(stats.get("time_elapsed_sec", 0.0), 2),
            message=f"Сбор завершён. Новых статей: {new_articles}.",
        )
    except Exception as e:
        logger.exception("RSS collect error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.post(
    "/api/pipeline/run",
    tags=["Пайплайн"],
    summary="Обработать статьи из БД (фильтрация, эмбеддинги, суммаризация, RAG)",
    response_model=PipelineRunResponse,
    response_description="Результат выполнения: количество обработанных статей",
)
def run_pipeline_endpoint(body: PipelineRunRequest):
    try:
        from src.main import run_pipeline
        df = run_pipeline(
            taxonomy_selection_override=body.taxonomy_selection,
            collection_name=body.collection_name,
        )
        count = len(df) if df is not None else 0
        return PipelineRunResponse(
            success=True,
            articles_count=count,
            message=f"Пайплайн завершён. Обработано статей: {count}.",
        )
    except Exception as e:
        logger.exception("Pipeline error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.post(
    "/api/qa",
    tags=["Q&A"],
    summary="Задать вопрос по коллекции (RAG + LLM)",
    response_model=QAResponse,
    response_description="Ответ LLM с указанием источников",
)
def qa_ask(body: QARequest):
    """
    Выполняет RAG-запрос к коллекции:

    1. Векторный поиск релевантных фрагментов по `collection_id` (pgvector)
    2. Переранжирование фрагментов cross-encoder (sentence-transformers)
    3. Сборка контекста и отправка в GigaChat
    4. Возврат ответа с перечнем источников

    Если релевантных фрагментов недостаточно, модель формирует ответ на основе
    общих знаний без цитирования источников.
    """
    try:
        from src.agents.qa_agent import run_qa_agent
        result = run_qa_agent(
            user_query=body.question.strip(),
            collection_id=body.collection_id,
            options=body.options,
        )
        if result.get("status") == "error":
            return QAResponse(
                status="error",
                error=result.get("error") or "Неизвестная ошибка",
            )
        ar = result.get("answer_result") or {}
        sources = [
            QASource(
                link=f.get("link") or "",
                title=f.get("title") or "",
                snippet=f.get("snippet"),
            )
            for f in (ar.get("fragments") or [])
        ]
        return QAResponse(
            status="ok",
            answer=ar.get("answer"),
            sources=sources,
        )
    except Exception as e:
        logger.exception("QA error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get(
    "/api/collections/{collection_id}/date-range",
    tags=["Коллекции"],
    summary="Диапазон дат статей в коллекции",
)
def get_collection_date_range(collection_id: int):
    """Возвращает min/max published_at статей в коллекции для ограничения date picker."""
    from src.tools.db_state import get_connection
    from config.config import POSTGRES_TABLE_RAG_DOCUMENTS
    conn = get_connection()
    if conn is None:
        raise HTTPException(status_code=503, detail="БД недоступна")
    with conn.cursor() as cur:
        cur.execute(
            f"SELECT MIN(published_at), MAX(published_at) FROM {POSTGRES_TABLE_RAG_DOCUMENTS} WHERE collection_id = %s AND published_at IS NOT NULL",
            (collection_id,),
        )
        row = cur.fetchone()
    min_dt = row["min"] if row else None
    max_dt = row["max"] if row else None
    return {
        "min_date": min_dt.date().isoformat() if min_dt else None,
        "max_date": max_dt.date().isoformat() if max_dt else None,
    }


@app.get(
    "/api/digest/{collection_id}",
    tags=["Дайджест"],
    summary="Сформировать дайджест по коллекции",
    response_description="Структурированный дайджест по четырём разделам",
    responses={500: {"description": "Ошибка при формировании дайджеста"}},
)
def get_digest(
    collection_id: int,
    from_date: Optional[datetime] = None,
    to_date: Optional[datetime] = None,
):
    """
    **Разделы дайджеста:** Тренды, Методы и подходы, Инструменты и технологии, Кейсы и примеры.

    Опциональные параметры:
    - **from_date** — начало периода (ISO 8601, например `2024-01-01T00:00:00`)
    - **to_date** — конец периода (ISO 8601, например `2024-03-01T00:00:00`)
    """
    try:
        from src.digest.digest_builder import build_digest, DigestOptions, DigestResult
        options = DigestOptions(from_date=from_date, to_date=to_date)
        result: DigestResult = build_digest(collection_id, options=options)
        return {
            "title": result.title,
            "collection_id": result.collection_id,
            "collection_meta": result.collection_meta,
            "generated_at": result.generated_at,
            "from_date": from_date.isoformat() if from_date else None,
            "to_date": to_date.isoformat() if to_date else None,
            "sections": serialize_digest_section_item(result.sections),
        }
    except Exception as e:
        logger.exception("Digest error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Ленты — управление RSS-лентами и подписками
# ---------------------------------------------------------------------------

@app.post(
    "/api/feeds/validate",
    tags=["Ленты"],
    summary="Проверить RSS-ленту по URL",
    response_model=FeedValidateResponse,
)
def validate_feed(body: FeedValidateRequest):
    """
    Проверяет URL до сохранения: делает GET-запрос и парсит как RSS/Atom.
    Возвращает название и favicon если лента валидна, иначе — ошибку.
    Ничего в БД не пишет.
    """
    import feedparser
    from urllib.parse import urlparse
    try:
        import socket; socket.setdefaulttimeout(10)
        feed = feedparser.parse(body.url, agent="Mozilla/5.0", request_headers={"Connection": "close"})
        if feed.bozo and not feed.entries:
            return FeedValidateResponse(valid=False, error="Не удалось распознать RSS-ленту")
        name = feed.feed.get("title") or urlparse(body.url).netloc
        domain = urlparse(body.url).netloc
        favicon_url = f"https://www.google.com/s2/favicons?domain={domain}&sz=32"
        # Заголовки последних статей для генерации описания
        titles = [e.get("title", "") for e in feed.entries[:10] if e.get("title")]
        # Генерируем описание и категорию через GigaChat (не блокируем ответ если недоступен)
        from src.tools.llm_utils import generate_feed_description, suggest_feed_category
        description = generate_feed_description(name=name, url=body.url, titles=titles)
        channel_description = feed.feed.get("description") or feed.feed.get("subtitle") or ""
        suggested_category = suggest_feed_category(name=name, description=channel_description, url=body.url)
        return FeedValidateResponse(
            valid=True,
            name=name,
            description=description,
            favicon_url=favicon_url,
            suggested_category=suggested_category,
        )
    except Exception as e:
        return FeedValidateResponse(valid=False, error=str(e))


@app.post(
    "/api/feeds",
    tags=["Ленты"],
    summary="Добавить ленту и подписаться",
    response_model=FeedItem,
    status_code=201,
)
def add_feed(body: FeedCreate):
    """Создаёт подписку пользователя на ленту. Если лента с таким URL уже есть — не дублирует."""
    from src.tools.db_state import get_connection, ensure_tables, create_feed, list_feeds
    conn = get_connection()
    ensure_tables(conn)
    feed = create_feed(conn, url=body.url, name=body.name, favicon_url=body.favicon_url, description=body.description, category=body.category, folder_id=body.folder_id)
    if not feed:
        raise HTTPException(status_code=500, detail="Не удалось создать ленту")
    feeds = list_feeds(conn)
    full_feed = next((f for f in feeds if f["id"] == feed["id"]), feed)
    return FeedItem(**full_feed)


@app.get(
    "/api/feeds",
    tags=["Ленты"],
    summary="Список подписок пользователя",
    response_model=list[FeedItem],
)
def get_feeds(include_hidden: bool = False):
    """Возвращает все ленты на которые подписан пользователь. Используется для отрисовки боковой панели."""
    from src.tools.db_state import get_connection, list_feeds
    conn = get_connection()
    return [FeedItem(**f) for f in list_feeds(conn, include_hidden=include_hidden)]


@app.delete(
    "/api/feeds/{feed_id}",
    tags=["Ленты"],
    summary="Отписаться от ленты",
    status_code=204,
    responses={404: {"description": "Подписка не найдена"}},
)
def remove_feed(feed_id: int):
    """Удаляет подписку пользователя на ленту. Саму ленту не удаляет."""
    from src.tools.db_state import get_connection, delete_feed
    conn = get_connection()
    if not delete_feed(conn, feed_id):
        raise HTTPException(status_code=404, detail="Подписка не найдена")


@app.patch(
    "/api/feeds/{feed_id}",
    tags=["Ленты"],
    summary="Обновить настройки подписки",
    response_model=FeedItem,
    responses={404: {"description": "Подписка не найдена"}},
)
def patch_feed(feed_id: int, body: FeedUpdate):
    """Обновляет название, статус (включена/выключена) или папку ленты."""
    from src.tools.db_state import get_connection, update_feed
    conn = get_connection()
    updated = update_feed(conn, feed_id, **body.model_dump(exclude_none=True))
    if not updated:
        raise HTTPException(status_code=404, detail="Подписка не найдена")
    return FeedItem(**updated)


# ─────────────────────────────────────────────────────────────
#  Статьи ленты (Сценарий 1.4)
# ─────────────────────────────────────────────────────────────

@app.get(
    "/api/feeds/{feed_id}/articles",
    tags=["Ленты"],
    summary="Список статей ленты",
    response_model=list[ArticleItem],
    responses={404: {"description": "Лента не найдена"}},
)
def get_feed_articles(feed_id: int, page: int = 1, unread_only: bool = False):
    """
    Возвращает статьи ленты с пагинацией (30 статей на страницу), новые первые.
    unread_only=true — только непрочитанные статьи.
    """
    from src.tools.db_state import get_connection, list_feed_articles
    conn = get_connection()
    articles = list_feed_articles(conn, feed_id=feed_id, page=page, unread_only=unread_only)
    return [ArticleItem(**a) for a in articles]


# ─────────────────────────────────────────────────────────────
#  Папки (Сценарий 1.3)
# ─────────────────────────────────────────────────────────────

@app.post(
    "/api/folders",
    tags=["Папки"],
    summary="Создать папку",
    response_model=FolderItem,
    status_code=201,
)
def create_folder_endpoint(body: FolderCreate):
    """Создаёт папку в боковой панели пользователя."""
    from src.tools.db_state import get_connection, create_folder
    conn = get_connection()
    folder = create_folder(conn, name=body.name)
    return FolderItem(**folder)


@app.get(
    "/api/folders",
    tags=["Папки"],
    summary="Список папок",
    response_model=list[FolderItem],
)
def get_folders():
    """Возвращает все папки пользователя, отсортированные по позиции."""
    from src.tools.db_state import get_connection, list_folders
    conn = get_connection()
    return [FolderItem(**f) for f in list_folders(conn)]


@app.patch(
    "/api/folders/{folder_id}",
    tags=["Папки"],
    summary="Переименовать или переместить папку",
    response_model=FolderItem,
    responses={404: {"description": "Папка не найдена"}},
)
def patch_folder(folder_id: int, body: FolderUpdate):
    """Обновляет название или позицию папки."""
    from src.tools.db_state import get_connection, update_folder
    conn = get_connection()
    folder = update_folder(conn, folder_id, **body.model_dump(exclude_none=True))
    if not folder:
        raise HTTPException(status_code=404, detail="Папка не найдена")
    return FolderItem(**folder)


@app.delete(
    "/api/folders/{folder_id}",
    tags=["Папки"],
    summary="Удалить папку",
    status_code=204,
    responses={404: {"description": "Папка не найдена"}},
)
def delete_folder_endpoint(folder_id: int):
    """Удаляет папку. Ленты внутри перемещаются в корень боковой панели."""
    from src.tools.db_state import get_connection, delete_folder
    conn = get_connection()
    if not delete_folder(conn, folder_id):
        raise HTTPException(status_code=404, detail="Папка не найдена")


# ─────────────────────────────────────────────────────────────
#  Каталог лент (Сценарий 1.2)
# ─────────────────────────────────────────────────────────────

@app.get(
    "/api/catalog",
    tags=["Каталог"],
    summary="Список лент каталога",
    response_model=list[CatalogFeedItem],
    response_description="Все системные ленты со статистикой и флагом подписки",
)
def get_catalog():
    """
    Возвращает все ленты каталога (из config.RSS_FEEDS) со статистикой:
    кол-во подписчиков, постов в день, последняя статья.
    Флаг is_subscribed показывает подписан ли текущий пользователь.
    Статистика берётся из кэша feed_catalog_stats — обновляется раз в час.
    """
    from src.tools.db_state import get_connection, list_catalog_feeds
    from urllib.parse import urlparse
    from config.config import RSS_SOURCE_DESCRIPTIONS
    conn = get_connection()
    rows = list_catalog_feeds(conn)
    result = []
    for r in rows:
        domain = urlparse(r["url"]).hostname or ""
        result.append(CatalogFeedItem(**r, source_description=RSS_SOURCE_DESCRIPTIONS.get(domain)))
    return result


@app.post(
    "/api/catalog/generate-descriptions",
    tags=["Каталог"],
    summary="Сгенерировать описания для лент каталога без описания",
)
def generate_catalog_descriptions():
    """
    Одноразовый эндпоинт: берёт все ленты каталога где description IS NULL,
    скачивает RSS, берёт до 10 заголовков статей, батчами по 10 отправляет в GigaChat
    и сохраняет сгенерированные описания на русском языке.
    """
    import feedparser
    from src.tools.db_state import get_connection, update_feed_descriptions
    from src.tools.llm_utils import generate_feed_descriptions_batch

    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id, url, name FROM feeds WHERE is_catalog = TRUE AND description IS NULL ORDER BY name;"
        )
        feeds_without_desc = [dict(r) for r in cur.fetchall()]

    if not feeds_without_desc:
        return {"message": "Все ленты уже имеют описание", "updated": 0}

    # Скачиваем RSS и собираем заголовки для каждой ленты
    feeds_with_titles = []
    for feed in feeds_without_desc:
        try:
            parsed = feedparser.parse(feed["url"])
            titles = [e.get("title", "") for e in parsed.entries[:10] if e.get("title")]
            if titles:
                feeds_with_titles.append({**feed, "titles": titles})
        except Exception as e:
            logger.warning("Не удалось скачать ленту %s: %s", feed["url"], e)

    # Батчами по 10 лент отправляем в GigaChat
    BATCH_SIZE = 10
    all_descriptions = {}
    for i in range(0, len(feeds_with_titles), BATCH_SIZE):
        batch = feeds_with_titles[i:i + BATCH_SIZE]
        result = generate_feed_descriptions_batch(batch)
        all_descriptions.update(result)
        logger.info("Батч %d/%d: получено %d описаний", i // BATCH_SIZE + 1,
                    (len(feeds_with_titles) + BATCH_SIZE - 1) // BATCH_SIZE, len(result))

    # Сохраняем в БД
    if all_descriptions:
        url_to_desc = {}
        id_to_url = {f["id"]: f["url"] for f in feeds_with_titles}
        for feed_id, description in all_descriptions.items():
            url_to_desc[id_to_url[feed_id]] = description
        update_feed_descriptions(conn, url_to_desc)

    return {
        "message": f"Обработано {len(feeds_with_titles)} лент, сгенерировано {len(all_descriptions)} описаний",
        "updated": len(all_descriptions),
        "skipped_no_articles": len(feeds_without_desc) - len(feeds_with_titles),
    }


@app.get(
    "/api/articles/{article_id}",
    tags=["Статьи"],
    summary="Полные данные статьи (Reader mode)",
    response_model=ArticleDetail,
    responses={404: {"description": "Статья не найдена"}},
)
def get_article(article_id: int):
    """
    Возвращает полные данные статьи включая full_text.
    Если full_text отсутствует в БД — извлекает с оригинального сайта и сохраняет.
    Если извлечение не удалось — возвращает full_text: null (не ошибку).
    """
    from src.tools.db_state import get_connection, get_article_by_id, update_article_full_text
    conn = get_connection()
    article = get_article_by_id(conn, article_id)
    if not article:
        raise HTTPException(status_code=404, detail="Статья не найдена")

    if article.get("full_text") is None:
        try:
            from src.tools.text_extraction import extract_full_text
            text = extract_full_text(article["link"])
            if text:
                update_article_full_text(conn, article_id, text)
                article["full_text"] = text
        except Exception as e:
            logger.warning("Не удалось извлечь full_text для article_id=%s: %s", article_id, e)

    return ArticleDetail(**article)


@app.get(
    "/api/articles/unread",
    tags=["Статьи"],
    summary='Умная папка "Непрочитанное"',
    response_model=list[ArticleItem],
    response_description="Все непрочитанные статьи из подписок пользователя",
)
def get_unread_articles(page: int = 1):
    """Возвращает непрочитанные статьи из всех активных лент пользователя, новые первые."""
    from src.tools.db_state import get_connection, list_unread_articles
    conn = get_connection()
    return [ArticleItem(**a) for a in list_unread_articles(conn, page=page)]


@app.get(
    "/api/articles/today",
    tags=["Статьи"],
    summary='Умная папка "Сегодня"',
    response_model=list[ArticleItem],
    response_description="Статьи опубликованные сегодня из подписок пользователя",
)
def get_today_articles(page: int = 1):
    """Возвращает статьи из лент пользователя опубликованные сегодня, новые первые."""
    from src.tools.db_state import get_connection, list_today_articles
    conn = get_connection()
    return [ArticleItem(**a) for a in list_today_articles(conn, page=page)]


@app.post(
    "/api/articles/read",
    tags=["Статьи"],
    summary="Пометить статью прочитанной",
    response_description="Подтверждение записи факта прочтения",
)
def mark_read(body: ArticleReadRequest):
    """Записывает факт прочтения статьи. Повторный вызов безопасен (idempotent)."""
    from src.tools.db_state import get_connection, mark_article_read
    conn = get_connection()
    mark_article_read(conn, link=body.link)
    return {"ok": True}


@app.post(
    "/api/feeds/{feed_id}/read-all",
    tags=["Статьи"],
    summary="Пометить все статьи ленты прочитанными",
    response_description="Количество помеченных статей",
    responses={404: {"description": "Лента не найдена"}},
)
def mark_feed_read_all(feed_id: int):
    """Помечает все статьи ленты прочитанными. Повторный вызов безопасен."""
    from src.tools.db_state import get_connection, get_feed_by_id, mark_feed_all_read
    conn = get_connection()
    if not get_feed_by_id(conn, feed_id):
        raise HTTPException(status_code=404, detail="Лента не найдена")
    marked = mark_feed_all_read(conn, feed_id=feed_id)
    return {"marked": marked}


if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")

    @app.get("/", include_in_schema=False)
    def index():
        return FileResponse(FRONTEND_DIR / "index.html")
else:
    @app.get("/", include_in_schema=False)
    def index():
        return {"message": "Frontend not found. Create directory 'frontend' with index.html."}
