"""
Фоновый воркер извлечения текстов и BART-суммаризации.

Две фазы:
1. Извлечение: находит статьи с full_text IS NULL, скачивает текст, сохраняет.
   После каждого успешного извлечения — генерирует BART-резюме если ai_summary пуст.
2. Досуммаризация: находит статьи с full_text IS NOT NULL AND ai_summary IS NULL
   (открытые пользователем до развёртывания воркера) — только BART, без извлечения.
"""
from __future__ import annotations

import logging
import re
import time
from collections import defaultdict
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

from config.config import BART_SUMMARIZATION_MODEL
BART_EN_MODEL = BART_SUMMARIZATION_MODEL
BART_RU_MODEL = "cointegrated/rut5-base-absum"

# Кэш pipeline по имени модели — два синглтона для EN и RU
_bart_pipelines: dict = {}


def _get_bart_pipeline(model_name: str):
    if model_name not in _bart_pipelines:
        from transformers import pipeline
        logger.info("Загружаем BART модель: %s", model_name)
        _bart_pipelines[model_name] = pipeline("summarization", model=model_name, truncation=True)
    return _bart_pipelines[model_name]


def _has_cyrillic(text: str) -> bool:
    return bool(re.search(r"[а-яёА-ЯЁ]", text))


def _summarize_with_bart_auto(title: str, full_text: str) -> str:
    """Суммаризация через BART с автовыбором модели по языку.
    Вызывает strip_html перед подачей в модель — безопасно и для HTML и для plain text.
    """
    from src.tools.translation import strip_html
    from config.config import BART_SUMMARY_MAX_LENGTH, BART_SUMMARY_MIN_LENGTH

    clean = strip_html(full_text) if full_text else ""
    if not clean.strip():
        return ""

    model_name = BART_RU_MODEL if (_has_cyrillic(title) or _has_cyrillic(clean[:200])) else BART_EN_MODEL
    lang = "RU" if model_name == BART_RU_MODEL else "EN"
    logger.debug("BART[%s] title=%r", lang, (title or "")[:60])
    pipe = _get_bart_pipeline(model_name)

    combined = f"{title}. {clean}" if title else clean
    combined = combined[:4000]

    result = pipe(
        combined,
        max_new_tokens=BART_SUMMARY_MAX_LENGTH,
        min_new_tokens=BART_SUMMARY_MIN_LENGTH,
        do_sample=False,
    )
    return result[0]["summary_text"].strip()


def get_pending_count(conn, user_id: int = None) -> int:
    """Сколько статей ожидают извлечения full_text.
    Если user_id задан — только по лентам этого пользователя."""
    if conn is None:
        return 0
    with conn.cursor() as cur:
        if user_id is not None:
            cur.execute(
                """SELECT COUNT(*) FROM processed_articles pa
                   JOIN user_feeds uf ON uf.feed_id = pa.feed_id AND uf.user_id = %s
                   WHERE pa.full_text IS NULL AND pa.full_text_error = FALSE;""",
                (user_id,),
            )
        else:
            cur.execute(
                "SELECT COUNT(*) FROM processed_articles WHERE full_text IS NULL AND full_text_error = FALSE;"
            )
        row = cur.fetchone()
        return int(row[0]) if row else 0


def extract_pending_articles(
    conn,
    batch_size: int = 10,
    domain_delay: float = 2.0,
    full_scan: bool = False,
) -> dict:
    """
    Основной метод воркера.

    Args:
        batch_size: максимум статей на домен за один запуск (при full_scan игнорируется).
        domain_delay: пауза между запросами к одному домену (секунды).
        full_scan: если True — обрабатывает все статьи без лимита на домен.
                   Используется для первоначального заполнения базы.

    Returns:
        {"extracted": int, "summarized": int, "failed": int, "skipped": int}
    """
    from src.tools.db_state import (
        get_articles_without_fulltext,
        get_articles_without_summary,
        update_article_full_text,
        mark_fulltext_error,
        mark_domain_fulltext_error,
        save_ai_summary,
    )
    from src.tools.text_extraction import extract_full_text

    extracted = 0
    summarized = 0
    failed = 0
    skipped = 0

    # ── Фаза 1: извлечение текстов ───────────────────────────────────────────
    fetch_limit = 100_000 if full_scan else batch_size * 20
    articles = get_articles_without_fulltext(conn, limit=fetch_limit)

    # Группируем по домену — не бомбим один сайт подряд
    by_domain: dict = defaultdict(list)
    for article in articles:
        domain = urlparse(article["link"]).netloc
        by_domain[domain].append(article)

    per_domain_limit = len(articles) if full_scan else batch_size
    total_phase1 = sum(min(len(v), per_domain_limit) for v in by_domain.values())
    done_phase1 = 0

    # Статистика по доменам для итогового вывода
    domain_stats: dict = {}

    if total_phase1:
        print(f"\n[worker] Фаза 1: извлечение текстов — {total_phase1} статей из {len(by_domain)} доменов", flush=True)

    for domain, domain_articles in by_domain.items():
        domain_extracted = 0
        domain_summarized = 0
        domain_failed = 0
        domain_batch = domain_articles[:per_domain_limit]

        for article in domain_batch:
            article_id = article["id"]
            link = article["link"]
            title = article.get("title") or ""
            done_phase1 += 1

            t_start = time.time()
            try:
                text = extract_full_text(link)
                t_fetched = time.time()
                fetch_sec = t_fetched - t_start

                if text:
                    update_article_full_text(conn, article_id, text)
                    extracted += 1
                    domain_extracted += 1

                    # BART только если ai_summary ещё не заполнено
                    bart_sec = 0.0
                    bart_label = ""
                    if not article.get("ai_summary"):
                        lang = "RU" if _has_cyrillic(title) else "EN"
                        try:
                            summary = _summarize_with_bart_auto(title, text)
                            bart_sec = time.time() - t_fetched
                            bart_label = f"bart[{lang}]={bart_sec:.1f}s"
                            if summary:
                                save_ai_summary(conn, article_id, summary)
                                summarized += 1
                                domain_summarized += 1
                        except Exception as e:
                            bart_sec = time.time() - t_fetched
                            bart_label = f"bart[{lang}]=ERR"
                            logger.warning("BART error for %s: %s", link[:80], e)

                    print(
                        f"  [{done_phase1}/{total_phase1}] ✓  {len(text):>6} chars"
                        f"  fetch={fetch_sec:.1f}s  {bart_label}"
                        f"  {link[:80]}",
                        flush=True,
                    )
                else:
                    fetch_sec = time.time() - t_start
                    mark_fulltext_error(conn, article_id)
                    failed += 1
                    domain_failed += 1
                    print(
                        f"  [{done_phase1}/{total_phase1}] ✗ нет текста"
                        f"  fetch={fetch_sec:.1f}s"
                        f"  {link[:80]}",
                        flush=True,
                    )
            except Exception as e:
                elapsed = time.time() - t_start
                mark_fulltext_error(conn, article_id)
                failed += 1
                domain_failed += 1
                print(
                    f"  [{done_phase1}/{total_phase1}] ✗ ошибка ({elapsed:.1f}s): {e}  {link[:80]}",
                    flush=True,
                )

            time.sleep(domain_delay)

        domain_stats[domain] = (domain_extracted, domain_summarized, domain_failed)

        # Если весь батч домена провалился — домен не поддерживает извлечение (JS-рендеринг и т.д.)
        # Помечаем оставшиеся статьи домена ошибкой чтобы не возвращаться к ним
        if domain_extracted == 0 and len(domain_batch) > 0:
            skipped_count = mark_domain_fulltext_error(conn, domain)
            if skipped_count > 0:
                skipped += skipped_count

    if domain_stats:
        print("", flush=True)
        max_domain_len = max(len(d) for d in domain_stats)
        for domain, (d_ext, d_sum, d_fail) in domain_stats.items():
            print(
                f"  {domain:<{max_domain_len}}  —  "
                f"Полных текстов скачано: {d_ext} | AI-резюме: {d_sum} | Ошибок: {d_fail}",
                flush=True,
            )

    # ── Фаза 2: досуммаризация статей с full_text но без ai_summary ──────────
    to_summarize = get_articles_without_summary(conn, limit=50)
    if to_summarize:
        print(f"\n[worker] Фаза 2: BART-суммаризация — {len(to_summarize)} статей", flush=True)

    for i, article in enumerate(to_summarize, 1):
        try:
            summary = _summarize_with_bart_auto(
                article.get("title") or "",
                article.get("full_text") or "",
            )
            if summary:
                save_ai_summary(conn, article["id"], summary)
                summarized += 1
                print(f"  [{i}/{len(to_summarize)}] ✓ summary  id={article['id']}", flush=True)
        except Exception as e:
            logger.warning("BART phase2 error for article_id=%s: %s", article["id"], e)
            print(f"  [{i}/{len(to_summarize)}] ✗ ошибка BART  id={article['id']}: {e}", flush=True)

    print(
        f"\n[worker] Итого: Полных текстов скачано: {extracted} | AI-резюме: {summarized} | Ошибок: {failed} | Пропущено: {skipped}\n",
        flush=True,
    )
    logger.info(
        "Extraction worker: завершён. Полных текстов скачано: %d | AI-резюме: %d | Ошибок: %d | Пропущено: %d",
        extracted, summarized, failed, skipped,
    )
    return {"extracted": extracted, "summarized": summarized, "failed": failed, "skipped": skipped}
