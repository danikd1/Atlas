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
import socket
import time
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple
from urllib.error import URLError

import feedparser
import pandas as pd

from .tools.db_state import (
    ensure_tables,
    get_connection,
    load_feed_states,
    load_processed_links,
    update_feed_states_from_seen,
    update_state_with_articles,
)
logger = logging.getLogger(__name__)


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
    timeout: int = 30
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
    
    # Retry логика для сетевых запросов
    last_error = None
    for attempt in range(max_retries):
        try:
            # feedparser не поддерживает timeout напрямую, но используем retry
            feed = feedparser.parse(feed_url)
            
            # Проверка на ошибки парсинга
            if hasattr(feed, 'bozo') and feed.bozo:
                error_msg = getattr(feed, 'bozo_exception', 'Unknown parsing error')
                logger.warning(f"Ошибка парсинга RSS {feed_url}: {error_msg}")
                # Продолжаем работу, если есть entries
            
            # Обработка записей
            for entry in feed.entries:
                try:
                    # Пытаемся достать структурированную дату публикации
                    pub_struct = entry.get("published_parsed") or entry.get("updated_parsed")
                    
                    # При фильтрации по last_processed (cutoff_exclusive) без даты не включаем — иначе при повторе запуска все без даты снова попадут в выборку
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
                            # Пропускаем статью, если не можем обработать дату
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
            break
            
        except (URLError, socket.timeout, socket.gaierror, ConnectionError) as e:
            last_error = e
            if attempt < max_retries - 1:
                logger.warning(
                    f"Ошибка сети при парсинге {feed_url} (попытка {attempt + 1}/{max_retries}): {e}. "
                    f"Повтор через {retry_delay} сек..."
                )
                time.sleep(retry_delay)
            else:
                logger.error(f"Не удалось распарсить {feed_url} после {max_retries} попыток: {e}")
        except Exception as e:
            # Неожиданные ошибки не ретраим
            logger.error(f"Неожиданная ошибка при парсинге {feed_url}: {e}")
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
    # Импорт конфига только если нужно
    if rss_feeds is None:
        from config.config import RSS_FEEDS, SUMMARY_TRUNCATE_MAX_CHARS, SUMMARY_TRUNCATE_SOURCE_PREFIXES
        rss_feeds = RSS_FEEDS
    else:
        from config.config import SUMMARY_TRUNCATE_MAX_CHARS, SUMMARY_TRUNCATE_SOURCE_PREFIXES
    
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
    
    # Подключение к БД и загрузка уже обработанных ссылок (для межзапусковой дедупликации)
    conn = get_connection()
    ensure_tables(conn)
    processed_links = load_processed_links(conn)
    # Загружаем last_processed_published_at по каждому источнику для фильтрации только новых статей
    feed_states = load_feed_states(conn)

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
            
            articles = parse_rss(
                url,
                limit=limit_per_feed,
                hours_back=hours_back,
                min_published_dt=min_published_dt,
                max_retries=max_retries,
                retry_delay=retry_delay
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

                # Пропускаем статьи, которые уже были обработаны в прошлых запусках
                if link in processed_links:
                    skipped_already_processed += 1
                    continue

                # Добавляем имя источника (ключ из RSS_FEEDS), чтобы можно было хранить состояние по каждому источнику
                art["source"] = name

                # У части лент в summary приходит полный текст статьи — обрезаем до SUMMARY_TRUNCATE_MAX_CHARS
                if SUMMARY_TRUNCATE_SOURCE_PREFIXES and any(
                    name.startswith(p) for p in SUMMARY_TRUNCATE_SOURCE_PREFIXES
                ):
                    s = (art.get("summary") or "")
                    if len(s) > SUMMARY_TRUNCATE_MAX_CHARS:
                        art["summary"] = s[:SUMMARY_TRUNCATE_MAX_CHARS].strip()

                if link in seen_links:
                    skipped_duplicates += 1
                    continue
                
                seen_links.add(link)
                all_articles.append(art)
                per_feed_new_count[name] = per_feed_new_count.get(name, 0) + 1
        
        except Exception as e:
            feeds_failed += 1
            logger.error(f"Критическая ошибка при обработке ленты '{name}' ({url}): {e}")
            continue
    
    end_time = time.time()
    elapsed = end_time - start_time
    
    # Сохраняем новые статьи в БД и обновляем last_processed_published_at по каждому источнику
    update_state_with_articles(conn, all_articles)
    # Обновляем last_processed_published_at по всем лентам, где что-то видели (не только по лентам с новыми статьями)
    update_feed_states_from_seen(conn, per_feed_max_published)

    df = pd.DataFrame(all_articles)
    
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
    from config import RSS_FEEDS, DEFAULT_HOURS_BACK, DEFAULT_LIMIT_PER_FEED
    
    print("🚀 Запуск пайплайна сбора статей с Habr...")
    print(f"📡 Обработка {len(RSS_FEEDS)} RSS-лент...")
    
    # Этап 1: Сбор статей за последние 24 часа
    df_articles, stats = collect_articles_for_window(
        DEFAULT_HOURS_BACK,
        limit_per_feed=DEFAULT_LIMIT_PER_FEED,
        rss_feeds=RSS_FEEDS
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
