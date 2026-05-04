"""
RSS Collector Worker — собирает статьи из RSS-лент по расписанию.

Запуск: python -m src.workers.collect_worker
HTTP:   GET  /status  — текущее состояние
        POST /run     — запустить сбор досрочно

После завершения сбора автоматически уведомляет extraction worker через /run.
"""
from __future__ import annotations

import logging
import os
import threading
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import httpx
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

# Интервал планового сбора (секунды). По умолчанию 1 час.
COLLECT_INTERVAL_SEC = int(os.environ.get("COLLECT_INTERVAL_SEC", 3600))

# URL extraction worker — для уведомления после сбора
WORKER_EXTRACTION_URL = os.environ.get("WORKER_EXTRACTION_URL", "http://worker-extraction:8002")

# ─── Состояние ────────────────────────────────────────────────────────────────

_state: dict = {
    "running": False,
    "last_run_at": None,       # ISO строка UTC
    "last_new_articles": None, # int
    "last_stats": None,        # полная статистика последнего сбора
    "error": None,
}
_lock = threading.Lock()
_run_event = threading.Event()


# ─── Логика сбора ─────────────────────────────────────────────────────────────

def _do_collect() -> None:
    from src.main import collect_rss
    from src.tools.db_state import get_connection, get_feeds_as_dict, refresh_catalog_stats

    _state["running"] = True
    _state["error"] = None
    logger.info("Collect worker: начинаем сбор RSS...")

    try:
        conn = get_connection()
        db_feeds = get_feeds_as_dict(conn)
        logger.info("Collect worker: лент из БД: %d", len(db_feeds))
        stats = collect_rss(rss_feeds=db_feeds if db_feeds else None)
        refresh_catalog_stats(conn)

        new_articles = stats.get("unique_articles", 0)
        _state["last_run_at"] = datetime.now(timezone.utc).isoformat()
        _state["last_new_articles"] = new_articles
        _state["last_stats"] = stats
        logger.info("Collect worker: завершён. Новых статей: %d", new_articles)

        # Уведомляем extraction worker — пусть сразу начнёт обработку
        try:
            httpx.post(f"{WORKER_EXTRACTION_URL}/run", timeout=5)
            logger.info("Collect worker: extraction worker уведомлён.")
        except Exception as e:
            logger.warning("Collect worker: не удалось уведомить extraction worker: %s", e)

    except Exception as e:
        logger.exception("Collect worker: ошибка сбора: %s", e)
        _state["error"] = str(e)
    finally:
        _state["running"] = False


def _worker_loop() -> None:
    """Бесконечный цикл: ждёт COLLECT_INTERVAL_SEC или сигнала /run, затем собирает."""
    # Запускаем первый сбор сразу при старте контейнера
    _run_event.set()

    while True:
        triggered = _run_event.wait(timeout=COLLECT_INTERVAL_SEC)
        _run_event.clear()

        if not _lock.acquire(blocking=False):
            logger.info("Collect worker: уже запущен, пропускаем.")
            continue

        try:
            _do_collect()
        finally:
            _lock.release()


# ─── FastAPI приложение ───────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    from src.tools.db_state import get_connection, ensure_tables, import_catalog_feeds, refresh_catalog_stats
    conn = get_connection()
    ensure_tables(conn)
    import_catalog_feeds(conn)
    refresh_catalog_stats(conn)
    logger.info("Collect worker: БД инициализирована.")

    t = threading.Thread(target=_worker_loop, daemon=True, name="collect-loop")
    t.start()
    logger.info("Collect worker: цикл запущен, интервал %d сек.", COLLECT_INTERVAL_SEC)
    yield


app = FastAPI(title="RSS Collector Worker", lifespan=lifespan)


@app.get("/status")
def status():
    """Текущее состояние воркера."""
    return _state


@app.post("/run")
def run():
    """Запустить сбор досрочно. Если уже запущен — возвращает started=false."""
    if _state["running"]:
        return {"started": False, "reason": "already running"}
    _run_event.set()
    return {"started": True}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
