"""
Модуль парсинга RSS-лент с обработкой ошибок и retry логикой.

Обеспечивает:
- Парсинг RSS-лент с обработкой сетевых ошибок
- Фильтрацию статей по времени публикации
- Retry логику для устойчивости к сетевым сбоям
- Валидацию и дедупликацию RSS-лент
"""
import calendar
import logging
import re
import time
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

import feedparser
import httpx
import pandas as pd

from ..tools.db_state import (
    ensure_tables,
    get_connection,
    get_existing_links,
    get_feeds_as_dict,
    load_feed_states,
    load_feed_url_id_map,
    update_feed_states_from_seen,
    update_feed_status,
    update_state_with_articles,
)
logger = logging.getLogger(__name__)

# XML 1.0 допускает только: #x9 | #xA | #xD | [#x20-#xD7FF] | [#xE000-#xFFFD] | [#x10000-#x10FFFF]
# Всё остальное — управляющие и суррогатные символы — вызывает bozo-ошибку в feedparser.
_RE_INVALID_XML = re.compile(
    '[^\x09\x0A\x0D\x20-퟿-�𐀀-􏿿]'
)


def _clean_xml_content(text: str) -> str:
    """Удаляет символы недопустимые в XML 1.0 — предотвращает bozo-ошибки feedparser."""
    return _RE_INVALID_XML.sub('', text)


def validate_and_deduplicate_feeds(rss_feeds: Dict[str, str]) -> Dict[str, str]:
    """
    Валидирует словарь RSS-лент и обрабатывает дубликаты ключей.
    
    Args:
        rss_feeds: Словарь {name: url}
        
    Returns:
        Очищенный словарь без дубликатов ключей
        
    Note:
        При дубликатах ключей сохраняется последнее значение (как в Python dict),
        но логируется предупреждение.
    """
    if not isinstance(rss_feeds, dict):
        raise ValueError("rss_feeds должен быть словарем")
    
    # Проверка на дубликаты ключей
    seen_keys = set()
    duplicates = []
    
    for key in rss_feeds.keys():
        if key in seen_keys:
            duplicates.append(key)
        seen_keys.add(key)
    
    if duplicates:
        logger.warning(
            f"Обнаружены дубликаты ключей в RSS feeds: {duplicates}. "
            f"Будут использованы последние значения."
        )
    
    # Валидация URL
    cleaned_feeds = {}
    for name, url in rss_feeds.items():
        if not isinstance(name, str) or not name.strip():
            logger.warning(f"Пропущен некорректный ключ: {name}")
            continue
        if not isinstance(url, str) or not url.strip():
            logger.warning(f"Пропущен некорректный URL для '{name}': {url}")
            continue
        cleaned_feeds[name] = url.strip()
    
    return cleaned_feeds


# Шаблон в конце summary у части лент (GitHub Blog, Microsoft Azure Blog, Atlassian, Slack и др.):
# "The post\n[заголовок]\nappeared first on\n[название блога]." — убираем, чтобы не дублировать заголовок и не засорять БД.
# \s* перед "The post" — в HTML может не быть пробела (например </p><p>The post).
_RE_STRIP_APPEARED_FIRST = re.compile(
    r"\s*The post\s+.+?appeared first on\s+.+$",
    re.IGNORECASE | re.DOTALL,
)


def strip_appeared_first_on(summary: str) -> str:
    """
    Удаляет из конца summary шаблон «The post ... appeared first on ...».
    Сначала regex; если не сработал — обрезаем по фразе " appeared first on ".
    """
    if not summary or not isinstance(summary, str):
        return summary or ""
    s = summary.strip()
    cleaned = _RE_STRIP_APPEARED_FIRST.sub("", s).strip()
    if cleaned != s:
        return cleaned or s
    if " appeared first on " in s:
        return s.split(" appeared first on ")[0].strip() or s
    return s


def parse_rss(
    feed_url: str,
    limit: int = 30,
    hours_back: Optional[int] = None,
    min_published_dt: Optional[datetime] = None,
    max_retries: int = 3,
    retry_delay: int = 2,
    timeout: int = 30,
    raise_on_network_error: bool = False,
) -> List[Dict]:
    """
    Парсит RSS-ленту с обработкой ошибок и retry логикой.
    
    Args:
        feed_url: URL RSS-ленты
        limit: Максимальное количество статей для парсинга
        hours_back: Фильтр по времени (только статьи за последние N часов)
        min_published_dt: Минимальная дата публикации (статьи новее этой даты).
                          Если задан и hours_back, используется более поздняя из двух дат.
        max_retries: Максимальное количество попыток при ошибке
        retry_delay: Задержка между попытками (секунды)
        timeout: Таймаут запроса (секунды)
        
    Returns:
        Список словарей со статьями
    """
    # Сырые записи из одной RSS-ленты (без учета дедупликации между источниками)
    entries: List[Dict] = []
    cutoff_dt = None
    
    # Вычисляем границу времени: используем min_published_dt или hours_back, или более позднюю из двух
    # Важно: все datetime должны быть offset-aware (с timezone), так как из БД приходят TIMESTAMPTZ
    cutoff_from_hours = None
    if hours_back is not None:
        if hours_back < 0:
            raise ValueError("hours_back должен быть неотрицательным")
        # Используем timezone-aware datetime (UTC)
        now = datetime.now(timezone.utc)
        cutoff_from_hours = now - timedelta(hours=hours_back)
    
    # Нормализуем min_published_dt: если он offset-naive, делаем его offset-aware (UTC)
    if min_published_dt is not None:
        if min_published_dt.tzinfo is None:
            # Если пришёл offset-naive, считаем его UTC
            min_published_dt = min_published_dt.replace(tzinfo=timezone.utc)
    
    # Выбираем более позднюю дату (чтобы не пропустить новые статьи)
    if min_published_dt is not None and cutoff_from_hours is not None:
        cutoff_dt = max(min_published_dt, cutoff_from_hours)
    elif min_published_dt is not None:
        cutoff_dt = min_published_dt
    elif cutoff_from_hours is not None:
        cutoff_dt = cutoff_from_hours
    
    # Для last_processed_published_at — только строго новее (pub_dt > cutoff), иначе при повторе запуска та же статья попадёт снова
    cutoff_exclusive = min_published_dt is not None
    
    # Retry логика для сетевых запросов.
    # httpx.Client создаётся один раз на все попытки — переиспользуем соединение.
    # User-Agent нужен чтобы некоторые серверы (например atlassianblog.wpengine.com)
    # не блокировали запросы с дефолтным python-httpx идентификатором.
    headers = {"User-Agent": "Mozilla/5.0 (compatible; RSSReader/1.0)"}
    with httpx.Client(timeout=timeout, follow_redirects=True, headers=headers) as client:
        for attempt in range(max_retries):
            try:
                # Загружаем сырой XML через httpx — получаем контроль над таймаутом и контентом.
                # Очищаем невалидные XML-символы до парсинга, чтобы избежать bozo-ошибок feedparser.
                response = client.get(feed_url)
                response.raise_for_status()
                raw_content = _clean_xml_content(response.text)
                feed = feedparser.parse(raw_content)

                # Проверка на остаточные ошибки парсинга (после очистки символов)
                if hasattr(feed, 'bozo') and feed.bozo:
                    error_msg = getattr(feed, 'bozo_exception', 'Unknown parsing error')
                    logger.warning(f"Ошибка парсинга RSS {feed_url}: {error_msg}")
                    # Продолжаем работу, если есть entries

                # Обработка записей
                for entry in feed.entries:
                    try:
                        # Пытаемся достать структурированную дату публикации
                        pub_struct = entry.get("published_parsed") or entry.get("updated_parsed")

                        # При фильтрации по last_processed (cutoff_exclusive) без даты не включаем —
                        # иначе при повторе запуска все без даты снова попадут в выборку
                        if cutoff_exclusive and pub_struct is None:
                            continue

                        # Фильтрация по времени
                        if cutoff_dt is not None and pub_struct is not None:
                            try:
                                timestamp = calendar.timegm(pub_struct)
                                pub_dt = datetime.fromtimestamp(timestamp, tz=timezone.utc)
                                # cutoff_exclusive (last_processed): только строго новее (pub_dt > cutoff)
                                # иначе: статьи не старше cutoff (pub_dt >= cutoff)
                                if cutoff_exclusive:
                                    if pub_dt <= cutoff_dt:
                                        continue
                                else:
                                    if pub_dt < cutoff_dt:
                                        continue
                            except (ValueError, OSError) as e:
                                logger.debug(f"Ошибка обработки даты для статьи: {e}")
                                continue

                        # Извлечение данных статьи
                        title = entry.get("title", "")
                        link = entry.get("link", "").strip()
                        published = entry.get("published", "—")
                        summary = strip_appeared_first_on(entry.get("summary", "Без описания"))

                        # Валидация обязательных полей
                        if not title or not link:
                            logger.debug(f"Пропущена статья без title или link: {link}")
                            continue

                        # Базовое представление статьи.
                        # published_dt используем для хранения нормализованной даты (если удалось распарсить).
                        article = {
                            "title": title,
                            "link": link,
                            "published": published,
                            "summary": summary,
                            "published_dt": pub_dt if "pub_dt" in locals() else None,
                        }
                        entries.append(article)

                        # Ограничение по количеству
                        if limit is not None and len(entries) >= limit:
                            break

                    except Exception as e:
                        logger.debug(f"Ошибка обработки записи из RSS: {e}")
                        continue

                # Успешно распарсили
                return entries

            except httpx.HTTPStatusError as e:
                # 4xx — ошибка клиента (404, 403 и т.п.), ретрай бессмысленен
                logger.error(f"HTTP {e.response.status_code} при парсинге {feed_url}: {e}")
                if raise_on_network_error:
                    raise
                break
            except (ConnectionError, httpx.TimeoutException, httpx.ConnectError) as e:
                # Сетевые сбои — ретраим
                if attempt < max_retries - 1:
                    logger.warning(
                        f"Ошибка сети при парсинге {feed_url} (попытка {attempt + 1}/{max_retries}): {e}. "
                        f"Повтор через {retry_delay} сек..."
                    )
                    time.sleep(retry_delay)
                else:
                    logger.error(f"Не удалось распарсить {feed_url} после {max_retries} попыток: {e}")
                    if raise_on_network_error:
                        raise
            except Exception as e:
                # Неожиданные ошибки не ретраим
                logger.error(f"Неожиданная ошибка при парсинге {feed_url}: {e}")
                if raise_on_network_error:
                    raise
                break

    return entries


def collect_articles_for_window(
    hours_back: int,
    limit_per_feed: int = 30,
    rss_feeds: Optional[Dict[str, str]] = None,
    max_retries: int = 3,
    retry_delay: int = 2
) -> Tuple[pd.DataFrame, Dict]:
    """
    Собирает статьи из всех RSS-лент за указанный период.
    
    Args:
        hours_back: Количество часов назад для фильтрации
        limit_per_feed: Максимальное количество статей на ленту
        rss_feeds: Словарь RSS-лент {name: url}. Если None, используется конфиг по умолчанию
        max_retries: Максимальное количество попыток при ошибке
        retry_delay: Задержка между попытками (секунды)
        
    Returns:
        Tuple[DataFrame, Dict]: DataFrame со статьями и статистика
    """
    from config.config import SUMMARY_TRUNCATE_MAX_CHARS, SUMMARY_TRUNCATE_SOURCE_PREFIXES

    # Если ленты не переданы явно — пробуем взять из БД, fallback на config
    if rss_feeds is None:
        _conn_tmp = get_connection()
        ensure_tables(_conn_tmp)
        db_feeds = get_feeds_as_dict(_conn_tmp)
        if db_feeds:
            rss_feeds = db_feeds
            logger.info("RSS: используем %d лент из БД (user_feeds)", len(rss_feeds))
        else:
            from config.config import get_feed_urls
            rss_feeds = get_feed_urls()
            logger.info("RSS: user_feeds пустая, используем %d лент из config", len(rss_feeds))
    
    # Валидация и обработка дубликатов
    rss_feeds = validate_and_deduplicate_feeds(rss_feeds)
    
    if not rss_feeds:
        logger.warning("Список RSS-лент пуст")
        return pd.DataFrame(), {
            "total_parsed": 0,
            "unique_articles": 0,
            "duplicates_skipped": 0,
            "already_processed_skipped": 0,
            "time_elapsed_sec": 0,
            "hours_back": hours_back,
            "feeds_processed": 0,
            "feeds_failed": 0
        }
    
    # Подключение к БД
    conn = get_connection()
    ensure_tables(conn)
    # Загружаем last_processed_published_at по каждому источнику для фильтрации только новых статей
    feed_states = load_feed_states(conn)
    # Загружаем {url: feed_id} чтобы проставить feed_id на каждую статью при сохранении
    feed_url_id_map = load_feed_url_id_map(conn)

    all_articles = []  # Список всех собранных статей (уникальные по ссылке)
    seen_links = set()  # Множество уже встреченных ссылок в рамках текущего запуска
    total_parsed = 0  # Сколько записей из RSS перебрали в этом запуске (по всем лентам, до дедупа)
    skipped_duplicates = 0  # Сколько статей было отброшено как дубликаты в рамках текущего запуска
    skipped_already_processed = 0  # Сколько статей было пропущено как уже обработанные ранее
    feeds_failed = 0  # Счётчик лент, которые завершились с критической ошибкой
    per_feed_max_published: Dict[str, datetime] = {} # По каждой ленте — макс. дата среди всех увиденных статей.
    per_feed_new_count: Dict[str, int] = {} # По каждой ленте — сколько новых статей добавили в этом запуске (для вывода в лог)

    start_time = time.time()

    for name, url in rss_feeds.items():
        try:
            # Для каждого источника используем его last_processed_published_at, если он есть
            min_published_dt = feed_states.get(name)
            if min_published_dt:
                logger.debug(
                    f"Источник '{name}': используем last_processed_published_at = {min_published_dt}"
                )

            # Временный лог, чтобы видеть, на какой ленте может происходить «зависание»
            logger.info("Парсинг RSS-ленты '%s' (%s)...", name, url)

            articles = parse_rss(
                url,
                limit=limit_per_feed,
                hours_back=hours_back,
                min_published_dt=min_published_dt,
                max_retries=max_retries,
                retry_delay=retry_delay,
                raise_on_network_error=True,
            )

            for art in articles:
                total_parsed += 1
                link = art["link"]
                # Обновляем макс. дату по ленте по всем увиденным (чтобы при следующем запуске не тянуть те же записи)
                pub_dt = art.get("published_dt")
                if pub_dt is not None and name:
                    current = per_feed_max_published.get(name)
                    if current is None or pub_dt > current:
                        per_feed_max_published[name] = pub_dt

                # Добавляем имя источника (ключ из RSS_FEEDS), чтобы можно было хранить состояние по каждому источнику
                art["source"] = name
                # Проставляем feed_id по URL ленты — надёжная связь со статьёй без строкового матча
                art["feed_id"] = feed_url_id_map.get(url)

                # У части лент в summary приходит полный текст статьи — обрезаем до SUMMARY_TRUNCATE_MAX_CHARS
                if SUMMARY_TRUNCATE_SOURCE_PREFIXES and any(
                    name.startswith(p) for p in SUMMARY_TRUNCATE_SOURCE_PREFIXES
                ):
                    s = (art.get("summary") or "")
                    if len(s) > SUMMARY_TRUNCATE_MAX_CHARS:
                        art["summary"] = s[:SUMMARY_TRUNCATE_MAX_CHARS].strip()

                # Дедупликация внутри текущего запуска (один URL из нескольких лент)
                if link in seen_links:
                    skipped_duplicates += 1
                    continue

                seen_links.add(link)
                all_articles.append(art)

            update_feed_status(conn, url, error=None)
        except Exception as e:
            feeds_failed += 1
            logger.error(f"Критическая ошибка при обработке ленты '{name}' ({url}): {e}")
            update_feed_status(conn, url, error=str(e))
            continue

    # Один батч-запрос к БД: из всех кандидатов этого запуска узнаём какие уже есть в processed_articles.
    # Заменяет load_processed_links() — больше не грузим всю таблицу в память.
    candidate_links = [art["link"] for art in all_articles]
    existing_in_db = get_existing_links(conn, candidate_links)
    new_articles = [art for art in all_articles if art["link"] not in existing_in_db]
    skipped_already_processed = len(all_articles) - len(new_articles)

    # per_feed_new_count считаем только по действительно новым статьям
    for art in new_articles:
        name = art.get("source", "")
        per_feed_new_count[name] = per_feed_new_count.get(name, 0) + 1

    end_time = time.time()
    elapsed = end_time - start_time

    # Сохраняем только новые статьи в БД
    update_state_with_articles(conn, new_articles)
    # Обновляем last_processed_published_at по всем лентам, где что-то видели (не только по лентам с новыми статьями)
    update_feed_states_from_seen(conn, per_feed_max_published)

    df = pd.DataFrame(new_articles)
    
    stats = {
        "total_parsed": total_parsed,
        "unique_articles": len(df),
        "duplicates_skipped": skipped_duplicates,
        "already_processed_skipped": skipped_already_processed,
        "time_elapsed_sec": elapsed,
        "hours_back": hours_back,
        "feeds_processed": len(rss_feeds),
        "feeds_failed": feeds_failed,
        "per_feed_new_count": per_feed_new_count,
    }
    
    return df, stats


def main():
    """
    Главная функция пайплайна: собирает статьи и сохраняет результат.
    """
    from config import get_feed_urls, DEFAULT_HOURS_BACK, DEFAULT_LIMIT_PER_FEED
    _feed_urls = get_feed_urls()

    print("🚀 Запуск пайплайна сбора статей с Habr...")
    print(f"📡 Обработка {len(_feed_urls)} RSS-лент...")
    
    # Этап 1: Сбор статей за последние 24 часа
    df_articles, stats = collect_articles_for_window(
        DEFAULT_HOURS_BACK,
        limit_per_feed=DEFAULT_LIMIT_PER_FEED,
        rss_feeds=_feed_urls
    )
    
    # Сохранение результата
    output_file = "articles_collected.csv"
    df_articles.to_csv(output_file, index=False, encoding='utf-8')
    
    # Вывод краткой сводки
    print("\n" + "="*60)
    print("📊 ИТОГОВАЯ СВОДКА")
    print("="*60)
    print(f"✅ Уникальных статей собрано: {stats['unique_articles']}")
    print(f"📝 Всего попыток добавления: {stats['total_parsed']}")
    print(f"🔄 Дубликатов отброшено: {stats['duplicates_skipped']}")
    if stats['feeds_failed'] > 0:
        print(f"⚠️  Лент с ошибками: {stats['feeds_failed']}")
    print(f"⏱️  Время выполнения: {stats['time_elapsed_sec']:.2f} сек ({stats['time_elapsed_sec']/60:.2f} мин)")
    print(f"💾 Результат сохранен в: {output_file}")
    print("="*60)
    
    return df_articles, stats


if __name__ == "__main__":
    # Настройка логирования для standalone запуска
    logging.basicConfig(
        level=logging.WARNING,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    main()
