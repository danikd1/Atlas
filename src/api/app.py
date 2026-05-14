# -*- coding: utf-8 -*-
"""
FastAPI-приложение системы Content Intelligence Platform.

Запуск: uvicorn src.api.app:app --reload --host 0.0.0.0 --port 8000
Swagger UI доступен только при ENVIRONMENT=development:
  http://localhost:8000/docs
  http://localhost:8000/redoc
"""
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
from pathlib import Path
from typing import Optional

import httpx
from pydantic import BaseModel

from fastapi import BackgroundTasks, FastAPI, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

import secrets
from datetime import datetime, timedelta, timezone

from src.auth.auth import get_current_user, hash_password, verify_password, create_access_token
from config.config import ALLOWED_ORIGINS

limiter = Limiter(key_func=get_remote_address)

from .schemas import (
    ArticleDetail,
    ArticleItem,
    ArticleReadRequest,
    AuthRegister,
    AuthLogin,
    AuthResponse,
    ForgotPasswordRequest,
    VerifyResetCodeRequest,
    ResetPasswordRequest,
    BookmarkRequest,
    SummarizeResponse,
    SummarizeRequest,
    CatalogFeedItem,
    CollectionArticle,
    CollectionItem,
    FeedBatchCreate,
    FeedAddResponse,
    FeedCreate,
    FeedItem,
    FeedUpdate,
    FeedValidateRequest,
    FeedValidateResponse,
    FolderCreate,
    FolderItem,
    FolderUpdate,
    FeedDigestRequest,
    FeedQARequest,
    FeedQAResponse,
    FeedQASourceItem,
    QARequest,
    QAResponse,
    QASource,
    RouterRequest,
    RouterResponse,
    RssCollectRequest,
    RssCollectResponse,
    serialize_digest_section_item,
    BertopicRunRequest,
    BertopicRunResponse,
    BertopicStatusResponse,
    BertopicTopicItem,
    BertopicTopicsResponse,
    UserInfo,
    ChangePasswordRequest,
    GigaChatTestRequest,
    GigaChatTestResponse,
)

logger = logging.getLogger(__name__)

# ─── Worker URLs ──────────────────────────────────────────────────────────────
# В Docker Compose — имена сервисов. Для локальной разработки — localhost.

WORKER_COLLECTOR_URL = os.environ.get("WORKER_COLLECTOR_URL", "http://localhost:8001")
WORKER_EXTRACTION_URL = os.environ.get("WORKER_EXTRACTION_URL", "http://localhost:8002")
WORKER_RAG_URL = os.environ.get("WORKER_RAG_URL", "http://localhost:8003")

_WORKER_TIMEOUT = 1  # секунда — внутренняя сеть, быстрый ответ или сразу ошибка


def _call_worker(url: str, method: str = "GET", **kwargs) -> dict:
    """Делает HTTP-запрос к воркеру. При недоступности возвращает {"error": "unavailable"}."""
    try:
        resp = httpx.request(method, url, timeout=_WORKER_TIMEOUT, **kwargs)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logger.debug("Worker недоступен (%s): %s", url, e)
        return {"error": "unavailable"}


async def _call_worker_async(client: httpx.AsyncClient, url: str, method: str = "GET", **kwargs) -> dict:
    """Асинхронный вызов воркера — для параллельных запросов."""
    try:
        resp = await client.request(method, url, timeout=_WORKER_TIMEOUT, **kwargs)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logger.debug("Worker недоступен (%s): %s", url, e)
        return {"error": "unavailable"}


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

_is_dev = os.environ.get("ENVIRONMENT", "production") == "development"

app = FastAPI(
    lifespan=lifespan,
    title="Content Intelligence Platform",
    description=(
        "API системы автоматизированного сбора, фильтрации и интеллектуального поиска "
        "по коллекциям статей из открытых источников.\n\n"
        "**Основные сценарии:**\n"
        "- Подбор темы через агент-роутер (`/api/router`)\n"
        "- Просмотр коллекций и статей (`/api/collections`)\n"
        "- Q&A по коллекции с указанием источников (`/api/qa`)\n"
        "- Формирование дайджеста по разделам (`/api/digest/{collection_id}`)"
    ),
    version="1.0.0",
    openapi_tags=_TAGS_METADATA,
    docs_url="/docs" if _is_dev else None,
    redoc_url="/redoc" if _is_dev else None,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
    allow_headers=["Authorization", "Content-Type"],
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


# ─── Auth ──────────────────────────────────────────────────────────────────

@app.post(
    "/api/auth/register",
    tags=["Auth"],
    summary="Регистрация нового пользователя",
    response_model=AuthResponse,
)
@limiter.limit("5/minute")
def auth_register(request: Request, body: AuthRegister):
    from src.tools.db_state import get_connection, create_user
    from config.config import ALLOWED_EMAILS
    email = body.email.strip().lower()
    if ALLOWED_EMAILS and email not in ALLOWED_EMAILS:
        raise HTTPException(status_code=403, detail="Регистрация закрыта")
    conn = get_connection()
    if conn is None:
        raise HTTPException(status_code=503, detail="БД недоступна")
    user = create_user(conn, email=email, password_hash=hash_password(body.password))
    if user is None:
        raise HTTPException(status_code=400, detail="Пользователь с таким email уже существует")
    return AuthResponse(access_token=create_access_token(user["id"]))


@app.post(
    "/api/auth/login",
    tags=["Auth"],
    summary="Вход в систему",
    response_model=AuthResponse,
)
@limiter.limit("10/minute")
def auth_login(request: Request, body: AuthLogin):
    from src.tools.db_state import get_connection, get_user_by_email
    conn = get_connection()
    if conn is None:
        raise HTTPException(status_code=503, detail="БД недоступна")
    user = get_user_by_email(conn, email=body.email.strip().lower())
    if user is None or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Неверный email или пароль")
    return AuthResponse(access_token=create_access_token(user["id"]))


@app.get(
    "/api/auth/me",
    tags=["Auth"],
    summary="Данные текущего пользователя",
    response_model=UserInfo,
)
def auth_me(current_user: dict = Depends(get_current_user)):
    return UserInfo(**current_user)


@app.post(
    "/api/auth/change-password",
    tags=["Auth"],
    summary="Смена пароля",
)
def change_password(body: ChangePasswordRequest, current_user: dict = Depends(get_current_user)):
    from src.tools.db_state import get_connection, get_user_by_id, update_user_password
    conn = get_connection()
    user = get_user_by_id(conn, current_user["id"])
    if not verify_password(body.current_password, user["password_hash"]):
        raise HTTPException(status_code=400, detail="Неверный текущий пароль")
    update_user_password(conn, current_user["id"], hash_password(body.new_password))
    conn.commit()
    return {"ok": True}


@app.post(
    "/api/auth/forgot-password",
    tags=["Auth"],
    summary="Запрос кода сброса пароля",
)
@limiter.limit("3/minute")
def forgot_password(request: Request, body: ForgotPasswordRequest):
    from src.tools.db_state import get_connection, get_user_by_email, create_password_reset_code
    from src.tools.email_service import send_password_reset_code

    # Всегда возвращаем одинаковый ответ — защита от перебора email
    conn = get_connection()
    if conn is not None:
        email = body.email.strip().lower()
        user = get_user_by_email(conn, email)
        if user:
            code = f"{secrets.randbelow(1_000_000):06d}"
            expires_at = datetime.now(timezone.utc) + timedelta(minutes=15)
            create_password_reset_code(conn, user["id"], code, expires_at)
            send_password_reset_code(email, code)
    return {"ok": True, "message": "Если аккаунт существует — письмо с кодом отправлено"}


def _get_valid_code_or_raise(email: str, code: str):
    """Проверяет код сброса пароля. Возвращает запись или бросает 400/503."""
    from src.tools.db_state import get_connection, get_valid_reset_code
    conn = get_connection()
    if conn is None:
        raise HTTPException(status_code=503, detail="БД недоступна")
    record = get_valid_reset_code(conn, email.strip().lower(), code)
    if record is None:
        raise HTTPException(status_code=400, detail="Неверный или просроченный код")
    return conn, record


@app.post(
    "/api/auth/verify-reset-code",
    tags=["Auth"],
    summary="Проверка кода сброса пароля",
)
@limiter.limit("10/minute")
def verify_reset_code(request: Request, body: VerifyResetCodeRequest):
    _get_valid_code_or_raise(body.email, body.code)
    return {"ok": True}


@app.post(
    "/api/auth/reset-password",
    tags=["Auth"],
    summary="Сброс пароля по коду",
)
@limiter.limit("5/minute")
def reset_password(request: Request, body: ResetPasswordRequest):
    from src.tools.db_state import reset_password_atomically

    conn, record = _get_valid_code_or_raise(body.email, body.code)
    reset_password_atomically(conn, record["user_id"], record["id"], hash_password(body.new_password))
    return {"ok": True}


@app.post(
    "/api/router",
    tags=["Роутер"],
    summary="Подбор темы по запросу пользователя",
    response_model=RouterResponse,
    response_description="Результат сопоставления запроса с таксономией",
)
def router_query(body: RouterRequest, current_user: dict = Depends(get_current_user)):
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
def list_collections(current_user: dict = Depends(get_current_user)):
    """Возвращает все коллекции, созданные в системе, с метаданными таксономии и датами обновления."""
    from src.tools.db_state import get_connection, list_collections as _list
    conn = get_connection()
    rows = _list(conn, owner_id=current_user["id"])
    return [CollectionItem(**r) for r in rows]


@app.get(
    "/api/collections/{collection_id}",
    tags=["Коллекции"],
    summary="Получить коллекцию по ID",
    response_model=CollectionItem,
    response_description="Метаданные коллекции",
    responses={404: {"description": "Коллекция не найдена"}},
)
def get_collection(collection_id: int, current_user: dict = Depends(get_current_user)):
    from src.tools.db_state import get_connection, get_collection_by_id
    conn = get_connection()
    row = get_collection_by_id(conn, collection_id, owner_id=current_user["id"])
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
def list_collection_articles(collection_id: int, current_user: dict = Depends(get_current_user)):
    from src.tools.db_state import get_connection, get_collection_by_id, get_articles_for_collection
    conn = get_connection()
    if not get_collection_by_id(conn, collection_id, owner_id=current_user["id"]):
        raise HTTPException(status_code=404, detail="Коллекция не найдена")
    rows = get_articles_for_collection(conn, collection_id)
    return [CollectionArticle(**r) for r in rows]


@app.get(
    "/api/rss/status",
    tags=["RSS"],
    summary="Статус автообновления лент",
)
async def rss_status(current_user: dict = Depends(get_current_user)):
    """Возвращает состояние всех воркеров и статистику индексации.
    Три вызова к воркерам выполняются параллельно — общий таймаут 1 сек."""
    import asyncio
    from src.tools.db_state import get_connection, get_rag_stats
    from src.pipeline.text_extraction_worker import get_pending_count

    conn = get_connection()

    # БД и воркеры опрашиваем параллельно
    async with httpx.AsyncClient() as client:
        rag_task = asyncio.get_event_loop().run_in_executor(
            None, lambda: get_rag_stats(conn, user_id=current_user["id"])
        )
        pending_task = asyncio.get_event_loop().run_in_executor(
            None, lambda: get_pending_count(conn, user_id=current_user["id"])
        )
        collector, extraction, rag_worker, rag, pending = await asyncio.gather(
            _call_worker_async(client, f"{WORKER_COLLECTOR_URL}/status"),
            _call_worker_async(client, f"{WORKER_EXTRACTION_URL}/status"),
            _call_worker_async(client, f"{WORKER_RAG_URL}/status"),
            rag_task,
            pending_task,
        )

    return {
        # Collect worker
        "is_running": collector.get("running", False),
        "last_run_at": collector.get("last_run_at"),
        "last_new_articles": collector.get("last_new_articles"),
        "collector_error": collector.get("error"),
        # Extraction worker
        "text_extraction_running": extraction.get("running", False),
        "text_extraction_pending": pending,
        # RAG worker (живые данные из БД, не из памяти воркера)
        "rag_indexing": rag_worker.get("running", False),
        "rag_paused": rag_worker.get("paused", False),
        "rag_indexed": rag["indexed"],
        "rag_pending": rag["pending"],
    }


@app.post(
    "/api/rss/collect",
    tags=["RSS"],
    summary="Собрать новые статьи из RSS-лент",
    response_model=RssCollectResponse,
    response_description="Статистика сбора: новые статьи, дубли, время выполнения",
)
def rss_collect_endpoint(body: RssCollectRequest, current_user: dict = Depends(get_current_user)):
    """
    Запускает сбор RSS досрочно через collect worker.

    - Делегирует выполнение worker-collector — тот собирает и уведомляет extraction worker.
    - Возвращает немедленно: {"started": true} или {"started": false} если уже запущен.
    """
    result = _call_worker(f"{WORKER_COLLECTOR_URL}/run", method="POST")
    if result.get("error"):
        raise HTTPException(status_code=503, detail="Collect worker недоступен.")
    if not result.get("started"):
        raise HTTPException(status_code=409, detail="Сбор уже выполняется.")
    return RssCollectResponse(
        success=True,
        new_articles=0,
        total_parsed=0,
        duplicates_skipped=0,
        already_processed_skipped=0,
        feeds_processed=0,
        feeds_failed=0,
        time_elapsed_sec=0.0,
        message="Сбор запущен. Результат будет доступен через GET /api/rss/status.",
    )


class ExtractRequest(BaseModel):
    full_scan: bool = False


@app.post(
    "/api/rss/extract",
    tags=["RSS"],
    summary="Запустить фоновое извлечение текстов вручную",
)
def rss_extract_endpoint(body: ExtractRequest = ExtractRequest(), current_user: dict = Depends(get_current_user)):
    """Запускает extraction worker через внутреннее API.
    full_scan=true — обрабатывает все статьи без лимита (для первоначального заполнения).
    """
    result = _call_worker(
        f"{WORKER_EXTRACTION_URL}/run",
        method="POST",
        json={"full_scan": body.full_scan},
    )
    if result.get("error"):
        raise HTTPException(status_code=503, detail="Extraction worker недоступен.")
    return result


@app.post(
    "/api/rss/index",
    tags=["RSS"],
    summary="Запустить RAG-индексацию вручную",
)
def rss_index_endpoint(current_user: dict = Depends(get_current_user)):
    """Запускает RAG-индексацию через внутреннее API rag worker."""
    result = _call_worker(f"{WORKER_RAG_URL}/run", method="POST")
    if result.get("error"):
        raise HTTPException(status_code=503, detail="RAG worker недоступен.")
    return result


@app.post(
    "/api/rss/index/pause",
    tags=["RSS"],
    summary="Поставить RAG-индексатор на паузу",
)
def rss_index_pause(current_user: dict = Depends(get_current_user)):
    """Приостанавливает RAG-индексатор между батчами. Текущий батч завершается."""
    result = _call_worker(f"{WORKER_RAG_URL}/pause", method="POST")
    if result.get("error"):
        raise HTTPException(status_code=503, detail="RAG worker недоступен.")
    return result


@app.post(
    "/api/rss/index/resume",
    tags=["RSS"],
    summary="Возобновить RAG-индексатор после паузы",
)
def rss_index_resume(current_user: dict = Depends(get_current_user)):
    """Снимает паузу RAG-индексатора."""
    result = _call_worker(f"{WORKER_RAG_URL}/resume", method="POST")
    if result.get("error"):
        raise HTTPException(status_code=503, detail="RAG worker недоступен.")
    return result




@app.post(
    "/api/qa",
    tags=["Q&A"],
    summary="Задать вопрос по коллекции (RAG + LLM)",
    response_model=QAResponse,
    response_description="Ответ LLM с указанием источников",
)
def qa_ask(body: QARequest, current_user: dict = Depends(get_current_user)):
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
        from src.tools.db_state import get_connection, get_collection_by_id
        if body.collection_id is not None:
            conn = get_connection()
            if not get_collection_by_id(conn, body.collection_id, owner_id=current_user["id"]):
                raise HTTPException(status_code=404, detail="Коллекция не найдена")
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
def get_collection_date_range(collection_id: int, current_user: dict = Depends(get_current_user)):
    """Возвращает min/max published_at статей в коллекции для ограничения date picker."""
    from src.tools.db_state import get_connection, get_collection_by_id
    from config.config import POSTGRES_TABLE_RAG_DOCUMENTS
    conn = get_connection()
    if conn is None:
        raise HTTPException(status_code=503, detail="БД недоступна")
    if not get_collection_by_id(conn, collection_id, owner_id=current_user["id"]):
        raise HTTPException(status_code=404, detail="Коллекция не найдена")
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
    current_user: dict = Depends(get_current_user),
):
    """
    **Разделы дайджеста:** Тренды, Методы и подходы, Инструменты и технологии, Кейсы и примеры.

    Опциональные параметры:
    - **from_date** — начало периода (ISO 8601, например `2024-01-01T00:00:00`)
    - **to_date** — конец периода (ISO 8601, например `2024-03-01T00:00:00`)
    """
    try:
        from src.digest.digest_builder import build_digest, DigestOptions, DigestResult
        from src.tools.db_state import get_connection, get_collection_by_id
        conn = get_connection()
        if not get_collection_by_id(conn, collection_id, owner_id=current_user["id"]):
            raise HTTPException(status_code=404, detail="Коллекция не найдена")
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


# ─── GigaChat credentials test ────────────────────────────────────────────────

@app.post(
    "/api/gigachat/test",
    tags=["GigaChat"],
    response_model=GigaChatTestResponse,
    summary="Проверить подключение к GigaChat",
)
def test_gigachat(body: GigaChatTestRequest, current_user: dict = Depends(get_current_user)):
    """Проверяет корректность переданных GigaChat credentials минимальным тестовым запросом."""
    try:
        from src.tools.llm_utils import create_gigachat_client
        client = create_gigachat_client(credentials=body.credentials, model=body.model)
        client.chat({"messages": [{"role": "user", "content": "Привет"}], "max_tokens": 5})
        return GigaChatTestResponse(ok=True)
    except Exception as e:
        return GigaChatTestResponse(ok=False, error=str(e))


# ─── BERTopic ─────────────────────────────────────────────────────────────────

@app.post(
    "/api/bertopic/run",
    tags=["BERTopic"],
    summary="Запустить BERTopic пайплайн асинхронно",
    response_model=BertopicRunResponse,
)
def bertopic_run(body: BertopicRunRequest, current_user: dict = Depends(get_current_user)):
    """
    Запускает полный BERTopic пайплайн в фоновом потоке.
    Возвращает task_id для отслеживания прогресса через GET /api/bertopic/status/{task_id}.
    """
    from src.bertopic.pipeline import run_async
    task_id = run_async(
        min_topic_size=body.min_topic_size,
        n_categories=body.n_categories,
        skip_rag=body.skip_rag,
        source_filter=body.source_filter,
        limit=body.limit,
        days_back=body.days_back,
        user_id=current_user["id"],
        gigachat_credentials=body.gigachat_credentials,
        gigachat_model=body.gigachat_model,
    )
    return BertopicRunResponse(
        task_id=task_id,
        status="pending",
        message="Пайплайн запущен",
    )


@app.get(
    "/api/bertopic/status/{task_id}",
    tags=["BERTopic"],
    summary="Статус выполнения BERTopic пайплайна",
    response_model=BertopicStatusResponse,
)
def bertopic_status(task_id: str, current_user: dict = Depends(get_current_user)):
    """Возвращает прогресс (0.0–1.0) и статус задачи: pending | running | done | error."""
    from src.bertopic.pipeline import get_task
    task = get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail=f"Задача {task_id} не найдена")
    return BertopicStatusResponse(
        task_id=task_id,
        status=task["status"],
        progress=task["progress"],
        message=task["message"],
        error=task.get("error"),
        result=task.get("result"),
        started_at=task.get("started_at"),
    )


@app.get(
    "/api/bertopic/topics",
    tags=["BERTopic"],
    summary="Список тем (коллекций) BERTopic для карты",
    response_model=BertopicTopicsResponse,
)
def bertopic_topics(current_user: dict = Depends(get_current_user)):
    """
    Возвращает все BERTopic-темы с количеством статей и ключевыми словами.
    Используется фронтендом для построения пузырьковой карты.
    """
    from src.tools.db_state import get_connection, get_bertopic_topics
    conn = get_connection()
    if conn is None:
        raise HTTPException(status_code=503, detail="Нет подключения к БД")
    try:
        rows = get_bertopic_topics(conn, owner_id=current_user["id"])
        topics = [
            BertopicTopicItem(
                id=row["id"],
                name=row["name"],
                description=row.get("description"),
                keywords=row.get("keywords"),
                bertopic_topic_id=row.get("bertopic_topic_id"),
                article_count=row.get("article_count") or 0,
                model_version=row.get("model_version"),
            )
            for row in rows
        ]
        return BertopicTopicsResponse(topics=topics, total=len(topics))
    except Exception as e:
        logger.exception("BERTopic topics error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@app.get(
    "/api/bertopic/collections/{collection_id}/articles",
    tags=["BERTopic"],
    summary="Статьи BERTopic-коллекции (через assignments)",
)
def bertopic_collection_articles(collection_id: int, current_user: dict = Depends(get_current_user)):
    """
    Загружает статьи темы через bertopic_assignments → processed_articles.
    Работает даже если skip_rag=True (rag_documents пустые).
    """
    from src.tools.db_state import get_connection, get_articles_for_bertopic_collection, get_collection_by_id
    conn = get_connection()
    if conn is None:
        raise HTTPException(status_code=503, detail="Нет подключения к БД")
    try:
        collection = get_collection_by_id(conn, collection_id, owner_id=current_user["id"])
        if not collection:
            raise HTTPException(status_code=403, detail="Коллекция не найдена или не принадлежит пользователю")
        rows = get_articles_for_bertopic_collection(conn, collection_id, user_id=current_user["id"])
        return rows
    except Exception as e:
        logger.exception("BERTopic collection articles error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@app.get(
    "/api/bertopic/collections/{collection_id}/rag-status",
    tags=["BERTopic"],
    summary="Статус RAG-индексации для BERTopic-коллекции",
)
def bertopic_collection_rag_status(collection_id: int, current_user: dict = Depends(get_current_user)):
    """Возвращает {total, indexed, ready} — сколько статей коллекции проиндексировано в RAG."""
    from src.tools.db_state import get_connection, get_collection_by_id, get_global_rag_collection, get_rag_coverage_for_collection
    conn = get_connection()
    if conn is None:
        raise HTTPException(status_code=503, detail="Нет подключения к БД")
    try:
        collection = get_collection_by_id(conn, collection_id, owner_id=current_user["id"])
        if not collection:
            raise HTTPException(status_code=403, detail="Коллекция не найдена или не принадлежит пользователю")
        rag_collection = get_global_rag_collection(conn)
        if not rag_collection:
            return {"total": 0, "indexed": 0, "ready": False}
        coverage = get_rag_coverage_for_collection(conn, rag_collection["id"], collection_id)
        total, indexed = coverage["total"], coverage["indexed"]
        return {"total": total, "indexed": indexed, "ready": total > 0 and total == indexed}
    finally:
        conn.close()


@app.get(
    "/api/feeds/rag-status",
    tags=["Q&A"],
    summary="Статус RAG-индексации для указанных лент",
)
def feeds_rag_status(feed_ids: str, current_user: dict = Depends(get_current_user)):
    """Возвращает {total, indexed, ready} — сколько статей из указанных лент проиндексировано в RAG.
    feed_ids передаётся как строка через запятую: ?feed_ids=1,2,3"""
    from src.tools.db_state import get_connection, get_global_rag_collection, get_rag_coverage_for_feeds
    try:
        ids = [int(x) for x in feed_ids.split(",") if x.strip()]
    except ValueError:
        raise HTTPException(status_code=400, detail="feed_ids должны быть числами через запятую")
    conn = get_connection()
    if conn is None:
        raise HTTPException(status_code=503, detail="Нет подключения к БД")
    try:
        rag_collection = get_global_rag_collection(conn)
        if not rag_collection:
            return {"total": 0, "indexed": 0, "ready": False}
        coverage = get_rag_coverage_for_feeds(conn, rag_collection["id"], ids, current_user["id"])
        total, indexed = coverage["total"], coverage["indexed"]
        return {"total": total, "indexed": indexed, "ready": total > 0 and total == indexed}
    finally:
        conn.close()


@app.post(
    "/api/feeds/qa",
    tags=["Q&A"],
    summary="QA по статьям из лент",
    response_model=FeedQAResponse,
)
def feed_qa(body: FeedQARequest, current_user: dict = Depends(get_current_user)):
    """QA по статьям пользователя из указанных лент. При наличии RAG-индекса использует pgvector, иначе — in-memory similarity."""
    from src.tools.db_state import get_connection, list_feeds
    conn = get_connection()
    user_feed_ids = {f["id"] for f in list_feeds(conn, user_id=current_user["id"])}
    forbidden = [fid for fid in body.feed_ids if fid not in user_feed_ids]
    if forbidden:
        raise HTTPException(status_code=403, detail=f"Ленты не принадлежат пользователю: {forbidden}")
    try:
        from src.qa.feed_qa import FeedQAOptions, answer_question_by_feeds
        opts = FeedQAOptions(
            top_k=body.top_k,
            from_date=body.from_date,
            to_date=body.to_date,
            gigachat_credentials=body.gigachat_credentials,
            gigachat_model=body.gigachat_model,
        )
        result = answer_question_by_feeds(body.question.strip(), body.feed_ids, opts, collection_id=body.collection_id, user_id=current_user["id"])
        return FeedQAResponse(
            status="ok",
            answer=result.answer,
            sources=[
                FeedQASourceItem(
                    link=s.link,
                    title=s.title,
                    feed_name=s.feed_name,
                    published_at=s.published_at,
                    snippet=s.snippet,
                    article_id=s.article_id,
                )
                for s in result.sources
            ],
            article_count=result.article_count,
        )
    except Exception as e:
        logger.exception("FeedQA error: %s", e)
        return FeedQAResponse(status="error", error=str(e))


@app.post(
    "/api/feeds/digest",
    tags=["Дайджест"],
    summary="Дайджест по статьям из лент (без RAG)",
)
def feed_digest(body: FeedDigestRequest, current_user: dict = Depends(get_current_user)):
    """Дайджест по статьям из указанных лент за период. Не требует предварительной индексации."""
    from src.tools.db_state import get_connection, list_feeds
    conn = get_connection()
    user_feed_ids = {f["id"] for f in list_feeds(conn, user_id=current_user["id"])}
    forbidden = [fid for fid in body.feed_ids if fid not in user_feed_ids]
    if forbidden:
        raise HTTPException(status_code=403, detail=f"Ленты не принадлежат пользователю: {forbidden}")
    try:
        from src.digest.feed_digest import FeedDigestOptions, build_digest_by_feeds
        opts = FeedDigestOptions(
            from_date=body.from_date,
            to_date=body.to_date,
            gigachat_credentials=body.gigachat_credentials,
            gigachat_model=body.gigachat_model,
        )
        result = build_digest_by_feeds(body.feed_ids, opts, collection_id=body.collection_id, user_id=current_user["id"])
        return {
            "title": result.title,
            "feed_ids": result.feed_ids,
            "generated_at": result.generated_at,
            "from_date": result.from_date,
            "to_date": result.to_date,
            "article_count": result.article_count,
            "sections": serialize_digest_section_item(result.sections),
        }
    except Exception as e:
        logger.exception("FeedDigest error: %s", e)
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
def validate_feed(body: FeedValidateRequest, current_user: dict = Depends(get_current_user)):
    """
    Проверяет URL до сохранения: делает GET-запрос и парсит как RSS/Atom.
    Возвращает название и favicon если лента валидна, иначе — ошибку.
    Ничего в БД не пишет.
    """
    import feedparser
    import httpx
    from urllib.parse import urlparse
    try:
        headers = {"User-Agent": "Mozilla/5.0 (compatible; RSSReader/1.0)"}
        with httpx.Client(timeout=10, follow_redirects=True, headers=headers) as client:
            response = client.get(body.url)
            response.raise_for_status()
        feed = feedparser.parse(response.text)
        if feed.bozo and not feed.entries:
            return FeedValidateResponse(valid=False, error="Не удалось распознать RSS-ленту")
        name = feed.feed.get("title") or urlparse(body.url).netloc
        domain = urlparse(body.url).netloc
        favicon_url = f"https://www.google.com/s2/favicons?domain={domain}&sz=32"
        # Заголовки последних статей для генерации описания
        titles = [e.get("title", "") for e in feed.entries[:10] if e.get("title")]
        # Генерируем описание и категорию через GigaChat (не блокируем ответ если недоступен)
        from src.tools.llm_utils import generate_feed_description, suggest_feed_category
        description = generate_feed_description(name=name, url=body.url, titles=titles, credentials=body.gigachat_credentials, model=body.gigachat_model)
        channel_description = feed.feed.get("description") or feed.feed.get("subtitle") or ""
        suggested_category = suggest_feed_category(name=name, description=channel_description, url=body.url, credentials=body.gigachat_credentials, model=body.gigachat_model)
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
    response_model=FeedAddResponse,
    status_code=201,
)
def add_feed(body: FeedCreate, background_tasks: BackgroundTasks, current_user: dict = Depends(get_current_user)):
    """Создаёт подписку пользователя на ленту. Если лента с таким URL уже есть — не дублирует.

    Синхронно пробует собрать статьи и возвращает fetch_status:
    - 'ok'    — статьи получены, лента активна
    - 'quiet' — лента отвечает, но статей нет; подписка сохранена, лента помечена quiet
    - 'error' — непредвиденная ошибка; форма закрывается молча
    """
    import feedparser as _fp
    import socket as _socket
    from src.main import collect_rss
    from src.tools.db_state import (
        get_connection, ensure_tables, create_feed,
        refresh_catalog_stats, POSTGRES_TABLE_FEED_STATE,
    )

    conn = get_connection()
    ensure_tables(conn)
    feed = create_feed(
        conn, url=body.url, name=body.name, favicon_url=body.favicon_url,
        description=body.description, category=body.category,
        folder_id=body.folder_id, user_id=current_user["id"],
    )
    if not feed:
        raise HTTPException(status_code=500, detail="Не удалось создать ленту")

    feed_id = feed["id"]
    fetch_status = "ok"
    fetch_error = None

    # Валидация при добавлении уже доказала что лента отвечает и парсится —
    # всегда запускаем сбор, независимо от текущего состояния в БД.

    # Шаг 1: привязываем существующие статьи по ссылкам из RSS (best-effort).
    # Нужно при повторной подписке — статьи могли быть под другим feed_id.
    try:
        _old_to = _socket.getdefaulttimeout()
        _socket.setdefaulttimeout(15)
        try:
            _rss = _fp.parse(body.url)
        finally:
            _socket.setdefaulttimeout(_old_to)
        _links = [e.get("link") for e in _rss.entries if e.get("link")]
        if _links:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE processed_articles SET feed_id = %s"
                    " WHERE link = ANY(%s) AND (feed_id IS NULL OR feed_id != %s)",
                    (feed_id, _links, feed_id),
                )
                if cur.rowcount:
                    logger.info("add_feed: привязали %d статей к feed_id=%s", cur.rowcount, feed_id)
    except Exception:
        pass  # Привязка — вспомогательный шаг, не блокируем основной путь

    # Шаг 2: если лента была отключена — сбрасываем состояние перед сбором
    if not feed.get("enabled", True):
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE feeds SET enabled=TRUE, error_count=0, last_error=NULL,"
                " disabled_reason=NULL, disabled_at=NULL WHERE id=%s",
                (feed_id,),
            )

    # Шаг 3: собираем статьи и определяем результат
    try:
        with conn.cursor() as cur:
            cur.execute(f"DELETE FROM {POSTGRES_TABLE_FEED_STATE} WHERE source = %s", (body.name,))
        collect_rss(rss_feeds={body.name: body.url})

        # Проверяем есть ли статьи после сбора
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) AS cnt FROM processed_articles WHERE feed_id = %s",
                (feed_id,),
            )
            articles_count = (cur.fetchone() or {}).get("cnt", 0)

        if articles_count == 0:
            # Лента отвечает, но статей нет — помечаем quiet
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE feeds SET enabled=FALSE, disabled_reason='quiet',"
                    " error_count=0, disabled_at=NOW() WHERE id=%s",
                    (feed_id,),
                )
            fetch_status = "quiet"
        else:
            fetch_status = "ok"

    except Exception as e:
        # Неожиданная ошибка сбора — форма закроется молча, лента останется в БД
        logger.warning("add_feed: ошибка сбора %s: %s", body.url, e)
        fetch_status = "error"

    background_tasks.add_task(refresh_catalog_stats, conn)

    # Собираем данные ленты для ответа
    feed_data = dict(feed)
    feed_data.setdefault("folder_id", body.folder_id)
    feed_data.setdefault("hidden", False)
    feed_data.setdefault("unread_count", 0)
    feed_data.setdefault("created_at", None)
    # Приводим enabled и last_error к актуальному состоянию после всех UPDATE
    feed_data["enabled"] = fetch_status == "ok"
    feed_data["last_error"] = fetch_error

    return FeedAddResponse(**feed_data, fetch_status=fetch_status, fetch_error=fetch_error)


@app.post(
    "/api/feeds/batch",
    tags=["Ленты"],
    summary="Массовая подписка на ленты",
    response_model=list[FeedItem],
    status_code=201,
)
def add_feeds_batch(body: FeedBatchCreate, background_tasks: BackgroundTasks, current_user: dict = Depends(get_current_user)):
    """Подписывает пользователя на несколько лент за один запрос. Эффективнее чем N отдельных вызовов /api/feeds."""
    from src.tools.db_state import get_connection, ensure_tables, create_feed, list_feeds, refresh_catalog_stats
    conn = get_connection()
    ensure_tables(conn)

    results = []
    for feed_data in body.feeds:
        feed = create_feed(
            conn,
            url=feed_data.url,
            name=feed_data.name,
            favicon_url=feed_data.favicon_url,
            description=feed_data.description,
            category=feed_data.category,
            folder_id=feed_data.folder_id,
            user_id=current_user["id"],
        )
        if feed:
            results.append(feed)

    feeds = list_feeds(conn, user_id=current_user["id"])
    feeds_by_id = {f["id"]: f for f in feeds}
    background_tasks.add_task(refresh_catalog_stats, conn)

    return [FeedItem(**feeds_by_id.get(f["id"], f)) for f in results]


@app.get(
    "/api/feeds",
    tags=["Ленты"],
    summary="Список подписок пользователя",
    response_model=list[FeedItem],
)
def get_feeds(include_hidden: bool = False, include_disabled: bool = False, current_user: dict = Depends(get_current_user)):
    """Возвращает все ленты на которые подписан пользователь. Используется для отрисовки боковой панели."""
    from src.tools.db_state import get_connection, list_feeds
    conn = get_connection()
    return [FeedItem(**f) for f in list_feeds(conn, user_id=current_user["id"], include_hidden=include_hidden, include_disabled=include_disabled)]


@app.get(
    "/api/feeds/{feed_id}",
    tags=["Ленты"],
    summary="Получить подписку по ID",
    response_model=FeedItem,
    responses={404: {"description": "Подписка не найдена"}},
)
def get_feed(feed_id: int, current_user: dict = Depends(get_current_user)):
    """Возвращает данные одной ленты пользователя: название, favicon, unread_count и т.д. 404 если пользователь не подписан на эту ленту."""
    from src.tools.db_state import get_connection, get_user_feed_by_id
    conn = get_connection()
    feed = get_user_feed_by_id(conn, feed_id, user_id=current_user["id"])
    if not feed:
        raise HTTPException(status_code=404, detail="Подписка не найдена")
    return FeedItem(**feed)


@app.delete(
    "/api/feeds/{feed_id}",
    tags=["Ленты"],
    summary="Отписаться от ленты",
    status_code=204,
    responses={404: {"description": "Подписка не найдена"}},
)
def remove_feed(feed_id: int, background_tasks: BackgroundTasks, current_user: dict = Depends(get_current_user)):
    """Удаляет подписку пользователя на ленту. Саму ленту не удаляет."""
    from src.tools.db_state import get_connection, delete_feed, refresh_catalog_stats
    conn = get_connection()
    if not delete_feed(conn, feed_id, user_id=current_user["id"]):
        raise HTTPException(status_code=404, detail="Подписка не найдена")
    background_tasks.add_task(refresh_catalog_stats, conn)


@app.patch(
    "/api/feeds/{feed_id}",
    tags=["Ленты"],
    summary="Обновить настройки подписки",
    response_model=FeedItem,
    responses={404: {"description": "Подписка не найдена"}},
)
def patch_feed(feed_id: int, body: FeedUpdate, current_user: dict = Depends(get_current_user)):
    """Обновляет название, статус (включена/выключена) или папку ленты."""
    from src.tools.db_state import get_connection, update_feed
    conn = get_connection()
    updated = update_feed(conn, feed_id, user_id=current_user["id"], **body.model_dump(exclude_unset=True))
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
def get_feed_articles(feed_id: int, page: int = 1, unread_only: bool = False, current_user: dict = Depends(get_current_user)):
    """
    Возвращает статьи ленты с пагинацией (30 статей на страницу), новые первые.
    unread_only=true — только непрочитанные статьи.
    Работает для любой ленты (каталожной или подписки) — 404 не возвращает.
    """
    from src.tools.db_state import get_connection, list_feed_articles
    conn = get_connection()
    articles = list_feed_articles(conn, feed_id=feed_id, page=page, unread_only=unread_only, user_id=current_user["id"])
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
def create_folder_endpoint(body: FolderCreate, current_user: dict = Depends(get_current_user)):
    """Создаёт папку в боковой панели пользователя."""
    from src.tools.db_state import get_connection, create_folder
    conn = get_connection()
    folder = create_folder(conn, name=body.name, favicon_url=body.favicon_url, user_id=current_user["id"])
    return FolderItem(**folder)


@app.get(
    "/api/folders",
    tags=["Папки"],
    summary="Список папок",
    response_model=list[FolderItem],
)
def get_folders(current_user: dict = Depends(get_current_user)):
    """Возвращает все папки пользователя, отсортированные по позиции."""
    from src.tools.db_state import get_connection, list_folders
    conn = get_connection()
    return [FolderItem(**f) for f in list_folders(conn, user_id=current_user["id"])]


@app.patch(
    "/api/folders/{folder_id}",
    tags=["Папки"],
    summary="Переименовать или переместить папку",
    response_model=FolderItem,
    responses={404: {"description": "Папка не найдена"}},
)
def patch_folder(folder_id: int, body: FolderUpdate, current_user: dict = Depends(get_current_user)):
    """Обновляет название или позицию папки."""
    from src.tools.db_state import get_connection, update_folder
    conn = get_connection()
    folder = update_folder(conn, folder_id, user_id=current_user["id"], **body.model_dump(exclude_unset=True))
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
def delete_folder_endpoint(folder_id: int, current_user: dict = Depends(get_current_user)):
    """Удаляет папку. Ленты внутри перемещаются в корень боковой панели."""
    from src.tools.db_state import get_connection, delete_folder
    conn = get_connection()
    if not delete_folder(conn, folder_id, user_id=current_user["id"]):
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
def get_catalog(current_user: dict = Depends(get_current_user)):
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
    rows = list_catalog_feeds(conn, user_id=current_user["id"])
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
def generate_catalog_descriptions(current_user: dict = Depends(get_current_user)):
    """
    Одноразовый эндпоинт: берёт все ленты каталога где description IS NULL,
    скачивает RSS, берёт до 10 заголовков статей, батчами по 10 отправляет в GigaChat
    и сохраняет сгенерированные описания на русском языке.
    """
    import feedparser
    import socket
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
            old_timeout = socket.getdefaulttimeout()
            socket.setdefaulttimeout(15)
            try:
                parsed = feedparser.parse(feed["url"])
            finally:
                socket.setdefaulttimeout(old_timeout)
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
    "/api/articles",
    tags=["Статьи"],
    summary='Все посты из подписок пользователя',
    response_model=list[ArticleItem],
    response_description="Все статьи из всех активных лент пользователя",
)
def get_all_articles(page: int = 1, current_user: dict = Depends(get_current_user)):
    """Возвращает все статьи из подписок пользователя, новые первые. Скрытые ленты исключены."""
    from src.tools.db_state import get_connection, list_all_articles
    conn = get_connection()
    return [ArticleItem(**a) for a in list_all_articles(conn, user_id=current_user["id"], page=page)]


@app.get(
    "/api/articles/unread",
    tags=["Статьи"],
    summary='Умная папка "Непрочитанное"',
    response_model=list[ArticleItem],
    response_description="Все непрочитанные статьи из подписок пользователя",
)
def get_unread_articles(page: int = 1, current_user: dict = Depends(get_current_user)):
    """Возвращает непрочитанные статьи из всех активных лент пользователя, новые первые."""
    from src.tools.db_state import get_connection, list_unread_articles
    conn = get_connection()
    return [ArticleItem(**a) for a in list_unread_articles(conn, user_id=current_user["id"], page=page)]


@app.get(
    "/api/articles/today",
    tags=["Статьи"],
    summary='Умная папка "Сегодня"',
    response_model=list[ArticleItem],
    response_description="Статьи опубликованные сегодня из подписок пользователя",
)
def get_today_articles(current_user: dict = Depends(get_current_user)):
    """Возвращает все статьи из лент пользователя опубликованные сегодня, новые первые."""
    from src.tools.db_state import get_connection, list_today_articles
    conn = get_connection()
    return [ArticleItem(**a) for a in list_today_articles(conn, user_id=current_user["id"])]


@app.get(
    "/api/articles/by-feeds",
    tags=["Статьи"],
    summary="Статьи из нескольких лент",
    response_model=list[ArticleItem],
)
def get_articles_by_feeds(feed_ids: str, page: int = 1, current_user: dict = Depends(get_current_user)):
    """
    Возвращает объединённый список статей из нескольких лент, отсортированный по дате.
    feed_ids — через запятую: ?feed_ids=1,2,3
    Используется для боковой панели мульти-лентных источников.
    """
    from src.tools.db_state import get_connection, list_articles_by_feed_ids
    try:
        ids = [int(x.strip()) for x in feed_ids.split(",") if x.strip()]
    except ValueError:
        raise HTTPException(status_code=422, detail="feed_ids должны быть числами через запятую")
    if not ids:
        return []
    conn = get_connection()
    return [ArticleItem(**a) for a in list_articles_by_feed_ids(conn, ids, page=page, user_id=current_user["id"])]


@app.get(
    "/api/articles/search",
    tags=["Статьи"],
    summary="Поиск статей по заголовку и summary",
    response_model=list[ArticleItem],
)
def search_articles_endpoint(q: str, limit: int = 20, current_user: dict = Depends(get_current_user)):
    """Полнотекстовый поиск (ILIKE) по title, ai_summary, summary. Только ленты пользователя."""
    if not q or len(q.strip()) < 2:
        return []
    from src.tools.db_state import get_connection, search_articles
    conn = get_connection()
    return [ArticleItem(**a) for a in search_articles(conn, q.strip(), user_id=current_user["id"], limit=min(limit, 50))]


@app.get(
    "/api/articles/{article_id}",
    tags=["Статьи"],
    summary="Полные данные статьи (Reader mode)",
    response_model=ArticleDetail,
    responses={404: {"description": "Статья не найдена"}},
)
def get_article(article_id: int, current_user: dict = Depends(get_current_user)):
    """
    Возвращает полные данные статьи включая full_text.
    Если full_text отсутствует в БД — извлекает с оригинального сайта и сохраняет.
    Если извлечение не удалось — возвращает full_text: null (не ошибку).
    """
    from src.tools.db_state import get_connection, get_article_by_id, update_article_full_text
    conn = get_connection()
    article = get_article_by_id(conn, article_id, user_id=current_user["id"])
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


@app.post(
    "/api/articles/{article_id}/summarize",
    tags=["Статьи"],
    summary="AI-резюме статьи",
    response_model=SummarizeResponse,
    responses={404: {"description": "Статья не найдена"}},
)
def summarize_article_endpoint(article_id: int, force: bool = False, body: SummarizeRequest = SummarizeRequest(), current_user: dict = Depends(get_current_user)):
    """
    Генерирует краткое AI-резюме статьи (3–4 предложения).

    Логика:
    1. Если ai_summary уже есть в БД и force=False — возвращает его мгновенно (cached=true).
    2. Если full_text отсутствует — пытается извлечь с оригинального сайта через trafilatura.
    3. Если full_text всё равно недоступен — использует краткое RSS-описание (summary) как fallback.
    4. Вызывает summarize_article() из llm_utils (GigaChat → ошибка если нет credentials).
    5. Сохраняет результат в processed_articles.ai_summary для кэширования.

    force=true — пересчитать даже если кэш есть (например, при смене модели).
    """
    from src.tools.db_state import (
        get_connection,
        get_article_for_summarize,
        save_ai_summary,
        update_article_full_text,
    )
    conn = get_connection()
    article = get_article_for_summarize(conn, article_id)
    if not article:
        raise HTTPException(status_code=404, detail="Статья не найдена")

    # 1. Кэш — возвращаем сразу (если не force и credentials не переданы)
    # Если переданы gigachat_credentials — всегда перезаписываем (в т.ч. BART-резюме)
    has_credentials = bool(body.gigachat_credentials)
    if article.get("ai_summary") and not force and not has_credentials:
        return SummarizeResponse(ai_summary=article["ai_summary"], cached=True)

    # 2. Извлекаем full_text если нет
    full_text = article.get("full_text")
    if not full_text:
        try:
            from src.tools.text_extraction import extract_full_text
            full_text = extract_full_text(article["link"])
            if full_text:
                update_article_full_text(conn, article_id, full_text)
        except Exception as e:
            logger.warning("Не удалось извлечь full_text для article_id=%s: %s", article_id, e)

    if not full_text:
        # Fallback: используем краткое описание из RSS если full_text недоступен
        rss_summary = article.get("summary") or ""
        if not rss_summary.strip():
            return SummarizeResponse(
                ai_summary=None,
                cached=False,
                error="Полный текст недоступен, описание отсутствует",
            )
        logger.info("article_id=%s: full_text недоступен, суммаризируем по RSS summary", article_id)
        full_text = rss_summary

    # 3. Суммаризация через GigaChat
    try:
        from src.tools.llm_utils import create_gigachat_client, summarize_article
        try:
            giga_client = create_gigachat_client(
                credentials=body.gigachat_credentials,
                model=body.gigachat_model,
            )
        except ValueError as e:
            return SummarizeResponse(ai_summary=None, cached=False, error=str(e))
        from src.tools.translation import strip_html
        clean_text = strip_html(full_text) if full_text else ""
        summary = summarize_article(
            title=article.get("title") or "",
            full_text=clean_text,
            client=giga_client,
        )
    except Exception as e:
        logger.error("Ошибка суммаризации article_id=%s: %s", article_id, e)
        return SummarizeResponse(
            ai_summary=None,
            cached=False,
            error="Ошибка при генерации резюме",
        )

    # 4. Кэшируем результат
    save_ai_summary(conn, article_id, summary)

    return SummarizeResponse(ai_summary=summary, cached=False)


@app.post(
    "/api/articles/{article_id}/translate",
    tags=["Статьи"],
    summary="Перевод статьи EN → RU",
)
def translate_article_endpoint(article_id: int, current_user: dict = Depends(get_current_user)):
    """
    Переводит title, summary и full_text статьи с EN на RU.
    Использует Helsinki-NLP/opus-mt-en-ru (MarianMT), локально.
    Модель загружается при первом вызове (~10 сек), затем кэшируется в памяти.
    """
    from src.tools.db_state import get_connection, get_article_by_id
    from src.tools.translation import translate_article

    conn = get_connection()
    article = get_article_by_id(conn, article_id, user_id=current_user["id"])
    if not article:
        raise HTTPException(status_code=404, detail="Статья не найдена")

    translated = translate_article(
        title=article.get("title"),
        summary=article.get("summary"),
        full_text=article.get("full_text"),
    )
    return translated


@app.post(
    "/api/articles/read",
    tags=["Статьи"],
    summary="Пометить статью прочитанной",
    response_description="Подтверждение записи факта прочтения",
)
def mark_read(body: ArticleReadRequest, current_user: dict = Depends(get_current_user)):
    """Записывает факт прочтения статьи. Повторный вызов безопасен (idempotent)."""
    from src.tools.db_state import get_connection, mark_article_read
    conn = get_connection()
    mark_article_read(conn, link=body.link, user_id=current_user["id"])
    return {"ok": True}


@app.delete(
    "/api/articles/read",
    tags=["Статьи"],
    summary="Снять метку прочитанного",
    response_description="Подтверждение снятия метки",
)
def mark_unread(body: ArticleReadRequest, current_user: dict = Depends(get_current_user)):
    """Удаляет факт прочтения статьи. Повторный вызов безопасен (idempotent)."""
    from src.tools.db_state import get_connection, mark_article_unread
    conn = get_connection()
    mark_article_unread(conn, link=body.link, user_id=current_user["id"])
    return {"ok": True}


@app.post(
    "/api/articles/bookmark",
    tags=["Статьи"],
    summary="Добавить статью в закладки",
)
def add_bookmark(body: BookmarkRequest, current_user: dict = Depends(get_current_user)):
    """Добавляет статью в закладки. Повторный вызов безопасен (idempotent)."""
    from src.tools.db_state import get_connection, add_bookmark as _add_bookmark
    _add_bookmark(get_connection(), link=body.link, user_id=current_user["id"])
    return {"ok": True}


@app.delete(
    "/api/articles/bookmark",
    tags=["Статьи"],
    summary="Убрать статью из закладок",
)
def remove_bookmark(body: BookmarkRequest, current_user: dict = Depends(get_current_user)):
    """Удаляет статью из закладок."""
    from src.tools.db_state import get_connection, remove_bookmark as _remove_bookmark
    _remove_bookmark(get_connection(), link=body.link, user_id=current_user["id"])
    return {"ok": True}


@app.get(
    "/api/bookmarks",
    tags=["Статьи"],
    summary="Закладки пользователя",
    response_model=list[ArticleItem],
)
def get_bookmarks(page: int = 1, current_user: dict = Depends(get_current_user)):
    """Возвращает закладки пользователя, отсортированные по дате сохранения (новые первые)."""
    from src.tools.db_state import get_connection, list_bookmarks
    rows = list_bookmarks(get_connection(), user_id=current_user["id"], page=page)
    return [ArticleItem(**r) for r in rows]


@app.post(
    "/api/feeds/{feed_id}/read-all",
    tags=["Статьи"],
    summary="Пометить все статьи ленты прочитанными",
    response_description="Количество помеченных статей",
    responses={404: {"description": "Лента не найдена"}},
)
def mark_feed_read_all(feed_id: int, current_user: dict = Depends(get_current_user)):
    """Помечает все статьи ленты прочитанными. Повторный вызов безопасен."""
    from src.tools.db_state import get_connection, get_feed_by_id, mark_feed_all_read
    conn = get_connection()
    if not get_feed_by_id(conn, feed_id):
        raise HTTPException(status_code=404, detail="Лента не найдена")
    marked = mark_feed_all_read(conn, feed_id=feed_id, user_id=current_user["id"])
    return {"marked": marked}


# ─────────────────────────────────────────────────────────────
#  Миграция данных (МП.2)
# ─────────────────────────────────────────────────────────────

@app.post(
    "/api/admin/migrate-legacy-data",
    tags=["Админ"],
    summary="Перенести данные user_id=0 на первого пользователя",
    include_in_schema=True,
)
def migrate_legacy_data(current_user: dict = Depends(get_current_user)):
    """
    Одноразовая миграция: переносит все данные user_id=0 на первого зарегистрированного пользователя (id=1).
    Вызывается вручную после развёртывания МП.2.
    Требует авторизации. Безопасно повторять — UPDATE WHERE user_id=0 без данных не упадёт.
    """
    from src.tools.db_state import get_connection
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM users ORDER BY id ASC LIMIT 1;")
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=400, detail="В системе нет зарегистрированных пользователей")
        target_user_id = row["id"]
        cur.execute("UPDATE user_feeds SET user_id = %s WHERE user_id = 0;", (target_user_id,))
        feeds_updated = cur.rowcount
        cur.execute("UPDATE feed_folders SET user_id = %s WHERE user_id = 0;", (target_user_id,))
        folders_updated = cur.rowcount
        cur.execute("UPDATE article_reads SET user_id = %s WHERE user_id = 0;", (target_user_id,))
        reads_updated = cur.rowcount
        cur.execute("UPDATE article_bookmarks SET user_id = %s WHERE user_id = 0;", (target_user_id,))
        bookmarks_updated = cur.rowcount
    conn.commit()
    return {
        "target_user_id": target_user_id,
        "user_feeds_updated": feeds_updated,
        "feed_folders_updated": folders_updated,
        "article_reads_updated": reads_updated,
        "article_bookmarks_updated": bookmarks_updated,
    }


if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")

    @app.get("/", include_in_schema=False)
    def index():
        return FileResponse(FRONTEND_DIR / "index.html")
else:
    @app.get("/", include_in_schema=False)
    def index():
        return {"message": "Frontend not found. Create directory 'frontend' with index.html."}
