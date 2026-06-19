"""
Extraction Worker — извлекает full_text статей и генерирует BART-резюме.

Запуск: python -m src.workers.extraction_worker
HTTP:   GET  /status          — текущее состояние
        POST /run             — запустить досрочно (body: {"full_scan": false})
        POST /run?full_scan=1 — запустить в режиме полного сканирования

Две фазы:
  1. Скачивает full_text для статей с full_text IS NULL.
  2. Генерирует BART-резюме для статей с full_text IS NOT NULL AND ai_summary IS NULL.

После завершения уведомляет rag worker через /run.
"""
from __future__ import annotations

import logging
import os
import threading
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import httpx
from fastapi import FastAPI
from pydantic import BaseModel

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
POLL_INTERVAL_SEC = int(os.environ.get("EXTRACTION_POLL_INTERVAL_SEC", 30))

# URL rag worker — для уведомления после извлечения
WORKER_RAG_URL = os.environ.get("WORKER_RAG_URL", "http://worker-rag:8003")

# ─── Состояние ────────────────────────────────────────────────────────────────

_state: dict = {
    "running": False,
    "full_scan": False,
    "last_run_at": None,   # ISO строка UTC
    "last_result": None,   # {"extracted": int, "summarized": int, "failed": int, "skipped": int}
    "error": None,
}
_lock = threading.Lock()
_run_event = threading.Event()
_next_full_scan = False  # флаг: следующий запуск будет full_scan


# ─── Логика извлечения ────────────────────────────────────────────────────────

def _do_extraction(full_scan: bool = False) -> None:
    from src.tools.db_state import get_connection
    from src.pipeline.text_extraction_worker import extract_pending_articles

    _state["running"] = True
    _state["full_scan"] = full_scan
    _state["error"] = None
    mode = "full_scan" if full_scan else "batch"
    logger.info("Extraction worker: начинаем извлечение текстов (режим: %s)...", mode)

    try:
        conn = get_connection()
        result = extract_pending_articles(conn, full_scan=full_scan)
        _state["last_run_at"] = datetime.now(timezone.utc).isoformat()
        _state["last_result"] = result
        logger.info(
            "Extraction worker: завершён. Полных текстов скачано: %d | AI-резюме: %d | Ошибок: %d | Пропущено: %d",
            result.get("extracted", 0), result.get("summarized", 0),
            result.get("failed", 0), result.get("skipped", 0),
        )

        # Уведомляем rag worker — пусть сразу начнёт индексацию
        try:
            httpx.post(f"{WORKER_RAG_URL}/run", timeout=5)
            logger.info("Extraction worker: rag worker уведомлён.")
        except Exception as e:
            logger.warning("Extraction worker: не удалось уведомить rag worker: %s", e)

    except Exception as e:
        logger.exception("Extraction worker: ошибка: %s", e)
        _state["error"] = str(e)
    finally:
        _state["running"] = False
        _state["full_scan"] = False


def _worker_loop() -> None:
    """Бесконечный цикл: ждёт POLL_INTERVAL_SEC или сигнала /run, затем извлекает."""
    global _next_full_scan

    while True:
        _run_event.wait(timeout=POLL_INTERVAL_SEC)
        _run_event.clear()

        if not _lock.acquire(blocking=False):
            logger.info("Extraction worker: уже запущен, пропускаем.")
            continue

        try:
            full_scan = _next_full_scan
            _next_full_scan = False
            _do_extraction(full_scan=full_scan)
        finally:
            _lock.release()


# ─── FastAPI приложение ───────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    from src.tools.db_state import get_connection, ensure_tables
    conn = get_connection()
    ensure_tables(conn)
    logger.info("Extraction worker: БД подключена.")

    t = threading.Thread(target=_worker_loop, daemon=True, name="extraction-loop")
    t.start()
    logger.info("Extraction worker: цикл запущен, интервал %d сек.", POLL_INTERVAL_SEC)
    yield


app = FastAPI(title="Extraction Worker", lifespan=lifespan)


class RunRequest(BaseModel):
    full_scan: bool = False


@app.get("/status")
def status():
    """Текущее состояние воркера."""
    from src.tools.db_state import get_connection
    from src.pipeline.text_extraction_worker import get_pending_count
    try:
        conn = get_connection()
        pending = get_pending_count(conn)
    except Exception:
        pending = None
    return {**_state, "pending": pending}


@app.post("/run")
def run(body: RunRequest = RunRequest()):
    """Запустить извлечение досрочно. full_scan=true — без лимита на домен."""
    global _next_full_scan
    if _state["running"]:
        return {"started": False, "reason": "already running"}
    _next_full_scan = body.full_scan
    _run_event.set()
    return {"started": True, "full_scan": body.full_scan}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
