# -*- coding: utf-8 -*-
"""
FastAPI-приложение системы Content Intelligence Platform.

Запуск: uvicorn src.api.app:app --reload --host 0.0.0.0 --port 8000
Swagger UI: http://localhost:8000/docs
ReDoc:       http://localhost:8000/redoc
"""
from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .schemas import (
    CollectionArticle,
    CollectionItem,
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
]

app = FastAPI(
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
    "/api/digest/{collection_id}",
    tags=["Дайджест"],
    summary="Сформировать дайджест по коллекции",
    response_description="Структурированный дайджест по четырём разделам",
    responses={500: {"description": "Ошибка при формировании дайджеста"}},
)
def get_digest(collection_id: int):
    """
    **Разделы дайджеста:** Тренды, Методы и подходы, Инструменты и технологии, Кейсы и примеры.
    """
    try:
        from src.digest.digest_builder import build_digest, DigestResult
        result: DigestResult = build_digest(collection_id)
        return {
            "title": result.title,
            "collection_id": result.collection_id,
            "collection_meta": result.collection_meta,
            "generated_at": result.generated_at,
            "sections": serialize_digest_section_item(result.sections),
        }
    except Exception as e:
        logger.exception("Digest error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")

    @app.get("/", include_in_schema=False)
    def index():
        return FileResponse(FRONTEND_DIR / "index.html")
else:
    @app.get("/", include_in_schema=False)
    def index():
        return {"message": "Frontend not found. Create directory 'frontend' with index.html."}
