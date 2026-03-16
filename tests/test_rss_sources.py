"""
Самопроверка RSS-источников и сохранения в БД без запуска полного пайплайна.

Проверяет:
  1. Из каждой RSS-ссылки корректно достаются данные (parse_rss → структура записей).
  2. Данные попадают в df_articles и сохраняются в processed_articles (collect_articles_for_window).
  3. Для каждой проверяемой статьи извлекается полный текст (add_full_text_column).

Запуск из корня проекта:
  python tests/test_rss_sources.py                    # все ленты из config, с БД
  python tests/test_rss_sources.py --feed pm          # одна лента
  python tests/test_rss_sources.py --feed pm --feed python  # несколько лент
  python tests/test_rss_sources.py --no-db            # без проверки БД (только парсинг и full_text)
  python tests/test_rss_sources.py --dry-run         # только парсинг + извлечение текста, без collect (нет записи в БД)
  python tests/test_rss_sources.py --limit 2        # макс. статей на ленту при сборе (по умолчанию 3)
  python tests/test_rss_sources.py --no-window     # все статьи из RSS без временного окна (не меняет основной пайплайн)
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Корень проекта в PYTHONPATH для запуска tests/test_rss_sources.py напрямую
_root = Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

import pandas as pd

from config.config import (
    DEFAULT_HOURS_BACK,
    DEFAULT_LIMIT_PER_FEED,
    DEFAULT_TEXT_MIN_LENGTH,
    POSTGRES_TABLE_PROCESSED_ARTICLES,
    RSS_FEEDS,
)
from src.rss_parser import collect_articles_for_window, parse_rss, validate_and_deduplicate_feeds
from src.tools.db_state import get_connection
from src.tools.text_extraction import add_full_text_column


REQUIRED_ARTICLE_KEYS = ("title", "link", "published", "summary")
REQUIRED_DF_COLUMNS = ("title", "link", "published", "summary", "source")


def _get_article_from_db(conn, link: str) -> dict | None:
    """Возвращает строку из processed_articles по link или None."""
    if conn is None:
        return None
    with conn.cursor() as cur:
        cur.execute(
            f"SELECT source, link, published_at, title, summary FROM {POSTGRES_TABLE_PROCESSED_ARTICLES} WHERE link = %s;",
            (link,),
        )
        row = cur.fetchone()
        return dict(row) if row else None


def check_parse_rss(
    name: str, url: str, limit: int = 5, hours_back: int | None = 168
) -> tuple[bool, str, list[dict]]:
    """
    Проверяет парсинг одной RSS-ленты. Возвращает (ok, message, entries).
    При hours_back=None временное окно не применяется — берутся все записи из ленты (до limit).
    """
    try:
        kwargs = {"limit": limit}
        if hours_back is not None:
            kwargs["hours_back"] = hours_back
        entries = parse_rss(url, **kwargs)
    except Exception as e:
        return False, f"parse_rss error: {e}", []

    if not entries:
        return True, "OK (0 записей)" + (" за период" if hours_back is not None else ""), []

    errors = []
    for i, art in enumerate(entries):
        for key in REQUIRED_ARTICLE_KEYS:
            if key not in art:
                errors.append(f"запись {i}: нет ключа '{key}'")
                continue
        if not (art.get("title") or "").strip():
            errors.append(f"запись {i}: пустой title")
        if not (art.get("link") or "").strip():
            errors.append(f"запись {i}: пустой link")

    if errors:
        return False, "; ".join(errors), entries
    return True, f"OK ({len(entries)} записей)", entries


def check_collect_and_db(
    rss_feeds: dict[str, str],
    limit_per_feed: int = 3,
    hours_back: int | None = None,
    skip_db: bool = False,
) -> tuple[pd.DataFrame, dict, list[str]]:
    """
    Запускает collect_articles_for_window и проверяет:
    - структура df_articles (колонки, нет дубликатов link);
    - при skip_db=False — каждая строка df есть в processed_articles с совпадающими полями.
    Возвращает (df_articles, stats, список ошибок).
    При hours_back=None используется DEFAULT_HOURS_BACK (основная система не меняется).
    Для режима «без окна» передайте большое значение, например 87600.
    """
    # Окно для collect: если передан None, используем дефолт из конфига
    hours = hours_back if hours_back is not None else DEFAULT_HOURS_BACK
    df, stats = collect_articles_for_window(
        hours,
        limit_per_feed=limit_per_feed,
        rss_feeds=rss_feeds,
    )
    errors = []

    # Проверка колонок df
    for col in REQUIRED_DF_COLUMNS:
        if col not in df.columns:
            errors.append(f"В df_articles нет колонки '{col}'")
    if not df.empty and df.duplicated(subset=["link"]).any():
        errors.append("В df_articles есть дубликаты по link")
    for _, row in df.iterrows():
        if not (row.get("link") or "").strip():
            errors.append("В df_articles есть строка с пустым link")
        if not (row.get("title") or "").strip():
            errors.append(f"В df_articles есть строка с пустым title: link={row.get('link')}")

    # Проверка сохранения в БД
    if not skip_db and not df.empty:
        conn = get_connection()
        if conn is None:
            errors.append("БД недоступна — проверка сохранения в processed_articles пропущена")
        else:
            for _, row in df.iterrows():
                link = row.get("link")
                if not link:
                    continue
                db_row = _get_article_from_db(conn, link)
                if db_row is None:
                    errors.append(f"В processed_articles нет записи для link: {link[:80]}...")
                    continue
                if (db_row.get("title") or "").strip() != (row.get("title") or "").strip():
                    errors.append(f"Не совпадает title в БД для link: {link[:60]}...")
                if (db_row.get("source") or "").strip() != (row.get("source") or "").strip():
                    errors.append(f"Не совпадает source в БД для link: {link[:60]}...")

    return df, stats, errors


def check_full_text_extraction(
    df: pd.DataFrame,
    min_length: int = DEFAULT_TEXT_MIN_LENGTH,
    max_articles: int = 5,
) -> tuple[pd.DataFrame, list[str]]:
    """
    Добавляет колонку full_text для первых max_articles строк и проверяет результат.
    Возвращает (df с full_text, список ошибок).
    """
    if df.empty:
        return df, []
    sample = df.head(max_articles).copy()
    out = add_full_text_column(sample, retries=2, sleep_time=1.0)
    errors = []
    if "full_text" not in out.columns:
        errors.append("Колонка full_text не добавлена")
        return out, errors
    for _, row in out.iterrows():
        link = row.get("link", "")
        txt = row.get("full_text")
        if txt is None:
            errors.append(f"Не удалось извлечь текст для link: {link[:80]}...")
        elif len(txt) < min_length:
            errors.append(f"Текст слишком короткий ({len(txt)} < {min_length}) для link: {link[:60]}...")
    return out, errors


def main():
    parser = argparse.ArgumentParser(
        description="Проверка RSS-источников: парсинг, df_articles, processed_articles, извлечение текста."
    )
    parser.add_argument(
        "--feed",
        action="append",
        dest="feeds",
        default=None,
        help="Имя ленты из config (можно указать несколько раз). Без указания — все ленты.",
    )
    parser.add_argument(
        "--no-db",
        action="store_true",
        help="Не проверять сохранение в БД (только парсинг и full_text).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Только парсинг + извлечение текста по одной статье с ленты; без collect и без записи в БД.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=3,
        metavar="N",
        help="Макс. статей на ленту при сборе (по умолчанию 3).",
    )
    parser.add_argument(
        "--hours",
        type=int,
        default=None,
        metavar="H",
        help=f"Окно в часах для сбора (по умолчанию из config: {DEFAULT_HOURS_BACK}).",
    )
    parser.add_argument(
        "--no-window",
        action="store_true",
        help="Без временного окна: парсинг — все записи из ленты (до limit), сбор — очень большое окно (10 лет). Основной пайплайн не меняется.",
    )
    args = parser.parse_args()

    if args.feeds:
        rss_feeds = {k: v for k, v in RSS_FEEDS.items() if k in args.feeds}
        missing = set(args.feeds) - set(rss_feeds)
        if missing:
            print(f"⚠️ Не найдены в config: {missing}. Доступные: {list(RSS_FEEDS.keys())[:10]}...")
    else:
        rss_feeds = dict(RSS_FEEDS)
    rss_feeds = validate_and_deduplicate_feeds(rss_feeds)
    if not rss_feeds:
        print("Нет лент для проверки.")
        return 1

    # Режим «без окна»: парсинг — все статьи из RSS (hours_back=None), сбор — большое окно
    NO_WINDOW_HOURS = 87600  # ~10 лет, чтобы не отсекать по времени в collect
    if args.no_window:
        hours_back_parse = None
        hours_back_collect = NO_WINDOW_HOURS
    else:
        hours_back_parse = args.hours or DEFAULT_HOURS_BACK
        hours_back_collect = args.hours or DEFAULT_HOURS_BACK

    limit_per_feed = max(1, args.limit)

    print("=" * 60)
    print("ПРОВЕРКА RSS-ИСТОЧНИКОВ (без пайплайна)")
    print("=" * 60)
    print(
        f"Лент: {len(rss_feeds)}, окно парсинга: {hours_back_parse if hours_back_parse is not None else 'нет'}, "
        f"окно сбора: {hours_back_collect} ч, лимит на ленту: {limit_per_feed}"
    )
    if args.no_db:
        print("Режим: без проверки БД")
    if args.dry_run:
        print("Режим: dry-run (только парсинг + извлечение текста, без collect)")
    print()

    # ——— 1) Парсинг каждой ленты ———
    print("1) Парсинг RSS (parse_rss)...")
    parse_ok = 0
    parse_fail = 0
    first_entries_by_feed = {}
    for name in sorted(rss_feeds.keys()):
        url = rss_feeds[name]
        ok, msg, entries = check_parse_rss(name, url, limit=limit_per_feed, hours_back=hours_back_parse)
        if entries:
            first_entries_by_feed[name] = entries
        if ok:
            parse_ok += 1
            print(f"   ✅ {name}: {msg}")
        else:
            parse_fail += 1
            print(f"   ❌ {name}: {msg}")
    print(f"   Итого: {parse_ok} OK, {parse_fail} ошибок\n")

    if args.dry_run:
        # Только проверка извлечения полного текста по одной статье с каждой ленты
        print("2) Извлечение полного текста (по одной статье с ленты, dry-run)...")
        rows = []
        for name, entries in first_entries_by_feed.items():
            if not entries:
                continue
            art = entries[0].copy()
            art["source"] = name
            rows.append(art)
        if not rows:
            print("   Нет статей для проверки текста.")
            return 0 if parse_fail == 0 else 1
        df_sample = pd.DataFrame(rows)
        out, text_errors = check_full_text_extraction(df_sample, max_articles=len(df_sample))
        if text_errors:
            for e in text_errors:
                print(f"   ❌ {e}")
        else:
            print(f"   ✅ Извлечён текст для {len(out)} статей")
        # Вывод полного текста по каждой статье
        for idx, (_, row) in enumerate(out.iterrows(), 1):
            title = row.get("title", "")[:60]
            link = row.get("link", "")
            txt = row.get("full_text")
            print(f"\n   --- Статья {idx}: {title}... | {link} ---")
            if txt:
                print(txt)
            else:
                print("   (текст не извлечён)")
        print("=" * 60)
        return 0 if (parse_fail == 0 and not text_errors) else 1

    # ——— 2) Сбор в df и проверка БД ———
    print("2) Сбор статей (collect_articles_for_window) и проверка df_articles / processed_articles...")
    df_articles, stats, collect_errors = check_collect_and_db(
        rss_feeds,
        limit_per_feed=limit_per_feed,
        hours_back=hours_back_collect,
        skip_db=args.no_db,
    )
    if collect_errors:
        for e in collect_errors:
            print(f"   ❌ {e}")
    else:
        print(f"   ✅ df_articles: {len(df_articles)} строк, колонки и дубликаты OK")
        if not args.no_db and not df_articles.empty:
            print("   ✅ Записи в processed_articles совпадают с df_articles")
    print()

    # ——— 3) Извлечение полного текста (выборочно) ———
    print("3) Извлечение полного текста (add_full_text_column)...")
    text_errors = []
    if df_articles.empty:
        print("   Нет статей для проверки текста.")
    else:
        # По одной статье с каждого источника (если есть)
        seen_source = set()
        sample_rows = []
        for _, row in df_articles.iterrows():
            src = row.get("source")
            if src and src not in seen_source:
                seen_source.add(src)
                sample_rows.append(row)
            if len(sample_rows) >= 10:
                break
        df_sample = pd.DataFrame(sample_rows) if sample_rows else df_articles.head(5)
        out, text_errors = check_full_text_extraction(df_sample, max_articles=len(df_sample))
        if text_errors:
            for e in text_errors:
                print(f"   ❌ {e}")
        else:
            print(f"   ✅ Текст извлечён для {len(out)} статей")
        # Вывод полного текста по каждой статье
        for idx, (_, row) in enumerate(out.iterrows(), 1):
            title = row.get("title", "")[:60]
            link = row.get("link", "")
            txt = row.get("full_text")
            print(f"\n   --- Статья {idx}: {title}... | {link} ---")
            if txt:
                print(txt)
            else:
                print("   (текст не извлечён)")
    print("=" * 60)

    has_errors = parse_fail > 0 or collect_errors or (not df_articles.empty and text_errors)
    return 1 if has_errors else 0


if __name__ == "__main__":
    sys.exit(main())
