"""
RAG Indexer Worker — чанкирует статьи, считает эмбеддинги, пишет в pgvector.

Запуск: python -m src.workers.rag_worker
HTTP:   GET  /status  — текущее состояние
        POST /run     — запустить индексацию досрочно
        POST /pause   — поставить на паузу (текущий батч дозавершается)
        POST /resume  — снять с паузы

Крутится в цикле while True пока есть необработанные статьи.
Rate limiting не нужен — только локальные вычисления, HTTP-запросов нет.
"""
from __future__ import annotations

import logging
import os
import threading
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)


class _NoStatusFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        return "GET /status" not in record.getMessage()

logging.getLogger("uvicorn.access").addFilter(_NoStatusFilter())

# ─── Конфигурация ─────────────────────────────────────────────────────────────

# Интервал проверки очереди (секунды). По умолчанию 30 сек.
POLL_INTERVAL_SEC = int(os.environ.get("RAG_POLL_INTERVAL_SEC", 30))

# ─── Состояние ────────────────────────────────────────────────────────────────

_state: dict = {
    "running": False,
    "paused": False,
    "last_run_at": None,   # ISO строка UTC
    "last_result": None,   # {"indexed": int, "chunks_created": int, "failed": int}
    "error": None,
}
_lock = threading.Lock()
_run_event = threading.Event()
_pause_event = threading.Event()
_pause_event.set()  # не на паузе при старте


# ─── Логика индексации ────────────────────────────────────────────────────────

def _do_indexing() -> None:
    from src.tools.db_state import get_connection
    from src.pipeline.rag_indexer import index_pending_articles

    _state["running"] = True
    _state["error"] = None
    logger.info("RAG worker: начинаем индексацию...")

    total_indexed = 0
    total_chunks = 0

    try:
        conn = get_connection()

        # Крутимся пока есть что индексировать
        while True:
            # Проверяем паузу перед каждым батчем
            _pause_event.wait()

            result = index_pending_articles(conn)
            total_indexed += result["indexed"]
            total_chunks += result["chunks_created"]

            if result["indexed"] == 0:
                # Очередь пуста — выходим из цикла
                break

        _state["last_run_at"] = datetime.now(timezone.utc).isoformat()
        _state["last_result"] = {"indexed": total_indexed, "chunks_created": total_chunks}
        logger.info("RAG worker: завершён. Проиндексировано: %d | Чанков: %d", total_indexed, total_chunks)

    except Exception as e:
        logger.exception("RAG worker: ошибка: %s", e)
        _state["error"] = str(e)
    finally:
        _state["running"] = False
        # Сбрасываем паузу — следующий запуск стартует чисто
        _pause_event.set()
        _state["paused"] = False


def _worker_loop() -> None:
    """Бесконечный цикл: ждёт POLL_INTERVAL_SEC или сигнала /run, затем индексирует."""
    while True:
        _run_event.wait(timeout=POLL_INTERVAL_SEC)
        _run_event.clear()

        if not _lock.acquire(blocking=False):
            logger.info("RAG worker: уже запущен, пропускаем.")
            continue

        try:
            _do_indexing()
        finally:
            _lock.release()


# ─── FastAPI приложение ───────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    from src.tools.db_state import get_connection, ensure_tables
    conn = get_connection()
    ensure_tables(conn)
    logger.info("RAG worker: БД подключена.")

    t = threading.Thread(target=_worker_loop, daemon=True, name="rag-loop")
    t.start()
    logger.info("RAG worker: цикл запущен, интервал %d сек.", POLL_INTERVAL_SEC)
    yield


app = FastAPI(title="RAG Indexer Worker", lifespan=lifespan)


@app.get("/status")
def status():
    """Текущее состояние воркера."""
    from src.tools.db_state import get_connection, get_rag_stats
    try:
        conn = get_connection()
        rag = get_rag_stats(conn)
    except Exception:
        rag = {"indexed": None, "pending": None, "total_chunks": None}
    return {**_state, **rag}


@app.post("/run")
def run():
    """Запустить индексацию досрочно."""
    if _state["running"]:
        return {"started": False, "reason": "already running"}
    _run_event.set()
    return {"started": True}


@app.post("/pause")
def pause():
    """Поставить на паузу. Текущий батч дозавершается."""
    _pause_event.clear()
    _state["paused"] = True
    logger.info("RAG worker: поставлен на паузу.")
    return {"paused": True}


@app.post("/resume")
def resume():
    """Снять с паузы."""
    _pause_event.set()
    _state["paused"] = False
    logger.info("RAG worker: снят с паузы.")
    return {"paused": False}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8003)
