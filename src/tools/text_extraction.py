"""
Модуль для извлечения полного текста статей из веб-страниц.

Использует trafilatura для извлечения чистого текста без HTML-разметки.
При блокировке по User-Agent (например, toptal.com) повторяет запрос с браузерным User-Agent.
"""
import logging
import time
from typing import Optional
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

import pandas as pd
import trafilatura

from config.config import (
    DEFAULT_TEXT_EXTRACTION_RETRIES,
    DEFAULT_TEXT_EXTRACTION_SLEEP,
    DEFAULT_TEXT_MIN_LENGTH,
)

logger = logging.getLogger(__name__)

# User-Agent обычного браузера — часть сайтов (toptal.com, dzone.com и др.) отдают 403 или пустую страницу на дефолтный UA trafilatura
BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

# Заголовки, имитирующие обычный браузер (некоторые сайты проверяют Accept / Accept-Language)
BROWSER_HEADERS = {
    "User-Agent": BROWSER_USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def _fetch_html_with_user_agent(url: str, timeout: int = 30) -> Optional[str]:
    """Скачивает HTML по URL с браузерными заголовками. Следует редиректам. Возвращает None при ошибке."""
    try:
        req = Request(url, headers=BROWSER_HEADERS)
        with urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except (URLError, HTTPError, OSError) as e:
        logger.debug(f"Запрос с User-Agent не удался для {url}: {e}")
        return None


def extract_full_text(
    url: str,
    retries: int = DEFAULT_TEXT_EXTRACTION_RETRIES,
    sleep_time: float = DEFAULT_TEXT_EXTRACTION_SLEEP,
    min_length: int = DEFAULT_TEXT_MIN_LENGTH
) -> Optional[str]:
    """
    Извлекает полный текст статьи по URL.

    Сначала используется trafilatura.fetch_url; если страница не загрузилась (403, пустой ответ),
    повторяется запрос с браузерным User-Agent и переданный HTML обрабатывается trafilatura.extract.
    """
    for attempt in range(retries):
        try:
            downloaded = trafilatura.fetch_url(url)

            # Fallback: сайт блокирует стандартный UA или отдаёт пустую/неполную страницу (toptal, dzone и др.)
            if not downloaded:
                downloaded = _fetch_html_with_user_agent(url)

            if downloaded:
                text = trafilatura.extract(
                    downloaded,
                    include_links=False,
                    include_images=False,
                    include_tables=False,
                    favor_recall=True,
                    deduplicate=True,
                )

                if text and len(text) >= min_length:
                    return text
                if text:
                    logger.warning(
                        "Текст слишком короткий (%s символов) для %s",
                        len(text),
                        url[:80],
                    )
                # Страница загрузилась, но текста мало или нет — пробуем запрос с браузерными заголовками
                # (актуально для dzone.com, feeds.dzone.com и сайтов с контентом по редиректу)
                downloaded = _fetch_html_with_user_agent(url)
                if downloaded:
                    text = trafilatura.extract(
                        downloaded,
                        include_links=False,
                        include_images=False,
                        include_tables=False,
                        favor_recall=True,
                        deduplicate=True,
                    )
                    if text and len(text) >= min_length:
                        return text
        except Exception as e:
            logger.warning(
                "Ошибка извлечения текста (попытка %s/%s) для %s: %s",
                attempt + 1,
                retries,
                url[:80],
                e,
            )

        if attempt < retries - 1:
            time.sleep(sleep_time)

    return None


def add_full_text_column(
    df: pd.DataFrame,
    retries: int = DEFAULT_TEXT_EXTRACTION_RETRIES,
    sleep_time: float = DEFAULT_TEXT_EXTRACTION_SLEEP
) -> pd.DataFrame:
    """
    Добавляет колонку 'full_text' в DataFrame со статьями.
    
    Args:
        df: DataFrame со статьями (должен содержать колонку 'link')
        retries: Количество попыток при ошибке извлечения
        sleep_time: Время задержки между попытками (секунды)
        
    Returns:
        DataFrame с добавленной колонкой 'full_text'
        
    Raises:
        ValueError: Если DataFrame не содержит колонку 'link'
    """
    if "link" not in df.columns:
        raise ValueError("DataFrame должен содержать колонку 'link'")
    
    df = df.copy()
    texts = []
    
    total = len(df)
    logger.info(f"Извлечение полного текста для {total} статей...")
    
    for idx, (_, row) in enumerate(df.iterrows(), 1):
        link = row["link"]
        txt = extract_full_text(link, retries=retries, sleep_time=sleep_time)
        texts.append(txt)  # None если не удалось извлечь
        
        if idx % 10 == 0:
            logger.info(f"Обработано {idx}/{total} статей...")
    
    df["full_text"] = texts
    
    successful = sum(1 for t in texts if t is not None)
    logger.info(f"✅ Извлечение завершено: {successful}/{total} статей успешно")
    
    return df

