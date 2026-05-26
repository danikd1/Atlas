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
from typing import Optional

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

_SEP = "━" * 40

# ─── Состояние ────────────────────────────────────────────────────────────────

_state: dict = {
    "running": False,
    "last_run_at": None,        # ISO строка UTC
    "last_new_articles": None,  # int
    "last_stats": None,         # полная статистика последнего сбора
    "error": None,
    "last_recheck_at": None,    # ISO строка UTC — последняя проверка мёртвых лент
}
_lock = threading.Lock()
_run_event = threading.Event()


# ─── Логика сбора ─────────────────────────────────────────────────────────────

def _do_collect() -> None:
    from src.main import collect_rss
    from src.tools.db_state import get_connection, get_feeds_as_dict, refresh_catalog_stats

    _state["running"] = True
    _state["error"] = None

    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    logger.info(_SEP)
    logger.info("🔄 СБОР RSS — %s", now_str)
    logger.info(_SEP)

    conn = None
    try:
        conn = get_connection()
        db_feeds = get_feeds_as_dict(conn)
        logger.info("Лент в очереди: %d", len(db_feeds))

        start = datetime.now(timezone.utc)
        stats = collect_rss(rss_feeds=db_feeds if db_feeds else None)
        refresh_catalog_stats(conn)
        elapsed = (datetime.now(timezone.utc) - start).total_seconds()

        new_articles = stats.get("unique_articles", 0)
        duplicates = stats.get("duplicates_skipped", 0)
        feeds_failed = stats.get("feeds_failed", 0)

        _state["last_run_at"] = datetime.now(timezone.utc).isoformat()
        _state["last_new_articles"] = new_articles
        _state["last_stats"] = stats

        logger.info(
            "Новых статей: %d | Дублей: %d | Упало лент: %d",
            new_articles, duplicates, feeds_failed,
        )
        logger.info("Время: %.1f сек", elapsed)
        logger.info(_SEP)

        # Уведомляем extraction worker — пусть сразу начнёт обработку
        try:
            httpx.post(f"{WORKER_EXTRACTION_URL}/run", timeout=5)
            logger.info("Extraction worker уведомлён.")
        except Exception as e:
            logger.warning("Не удалось уведомить extraction worker: %s", e)

    except Exception as e:
        logger.exception("Ошибка сбора: %s", e)
        _state["error"] = str(e)
    finally:
        _state["running"] = False
        if conn:
            conn.close()


def _do_recheck_dead_feeds() -> None:
    """Проверяет отключённые ленты — если лента ожила, включает её обратно.
    Также отключает новые тихие ленты и запускает очистку БД.

    Логика по типу отключения:
    - 'error'  — лента снова отвечает HTTP 200 → включаем
    - 'quiet'  — лента опубликовала ≥1 статьи за последние 30 дней → включаем
    """
    from src.pipeline.rss_parser import parse_rss
    from src.tools.db_state import (
        get_connection, get_dead_feeds_for_recheck, reenable_feed,
        disable_quiet_feeds, cleanup_stale_feeds_and_articles, log_feed_event,
    )

    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    logger.info(_SEP)
    logger.info("🩺 RECHECK ЛЕНТ — %s", now_str)
    logger.info(_SEP)

    conn = None
    try:
        conn = get_connection()

        # Отключаем новые тихие ленты
        newly_disabled = disable_quiet_feeds(conn)
        if newly_disabled:
            logger.info("Новых тихих: %d", newly_disabled)

        dead_feeds = get_dead_feeds_for_recheck(conn)
        if not dead_feeds:
            logger.info("Отключённых лент для проверки нет.")
        else:
            error_feeds = [f for f in dead_feeds if f.get("disabled_reason") == "error"]
            quiet_feeds = [f for f in dead_feeds if f.get("disabled_reason") == "quiet"]
            logger.info("На проверку: %d (error: %d, quiet: %d)", len(dead_feeds), len(error_feeds), len(quiet_feeds))

            reenabled = 0
            for feed in dead_feeds:
                feed_id = feed["id"]
                url = feed["url"]
                name = feed.get("name", url)
                reason = feed.get("disabled_reason", "error")
                try:
                    if reason == "quiet":
                        entries = parse_rss(url, limit=1, hours_back=720, max_retries=1, raise_on_network_error=True)
                        if not entries:
                            logger.info("💤 Всё ещё молчит (quiet): %s", name)
                            continue
                    else:
                        parse_rss(url, limit=1, max_retries=1, raise_on_network_error=True)

                    reenable_feed(conn, feed_id)
                    log_feed_event(conn, "reenabled",
                                   feed_id=feed_id, feed_name=name, feed_url=url,
                                   detail=f"was: {reason}")
                    reenabled += 1
                    logger.info("✅ Ожила (%s → active): %s", reason, name)
                except Exception as e:
                    logger.info("❌ Всё ещё мертва (%s): %s", reason, name)
                    logger.debug("  Причина: %s", e)

            logger.info("Итог: включено %d из %d", reenabled, len(dead_feeds))

        # Очистка БД
        logger.info(_SEP)
        logger.info("🧹 ОЧИСТКА БД")
        logger.info(_SEP)
        cleanup_stats = cleanup_stale_feeds_and_articles(conn)
        logger.info(
            "Удалено лент: %d | Статей: %d | Reads: %d | BERTopic: %d | RAG: %d | Inbox: %d | FeedState: %d",
            cleanup_stats.get("feeds_deleted", 0),
            cleanup_stats.get("articles_deleted", 0),
            cleanup_stats.get("reads_deleted", 0),
            cleanup_stats.get("bertopic_deleted", 0),
            cleanup_stats.get("rag_deleted", 0),
            cleanup_stats.get("inbox_deleted", 0),
            cleanup_stats.get("feed_state_deleted", 0),
        )
        logger.info(_SEP)
    finally:
        if conn:
            conn.close()


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
            # Ежедневная проверка: recheck + очистка
            now = datetime.now(timezone.utc)
            last_recheck = _state["last_recheck_at"]
            if last_recheck is None or (now - datetime.fromisoformat(last_recheck)).total_seconds() >= 86400:
                try:
                    _do_recheck_dead_feeds()
                except Exception as e:
                    logger.exception("Ошибка ежедневного recheck: %s", e)
                finally:
                    _state["last_recheck_at"] = now.isoformat()
        finally:
            _lock.release()


# ─── FastAPI приложение ───────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    from src.tools.db_state import get_connection, ensure_tables, import_catalog_feeds, refresh_catalog_stats
    conn = get_connection()
    try:
        ensure_tables(conn)
        import_catalog_feeds(conn)
        refresh_catalog_stats(conn)
    finally:
        if conn:
            conn.close()
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
