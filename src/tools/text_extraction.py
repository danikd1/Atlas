"""
Модуль для извлечения полного текста статей из веб-страниц.

Использует trafilatura для извлечения чистого текста без HTML-разметки.
"""
import logging
import time
from typing import Optional

import pandas as pd
import trafilatura

from config.config import DEFAULT_TEXT_EXTRACTION_RETRIES, DEFAULT_TEXT_EXTRACTION_SLEEP

logger = logging.getLogger(__name__)


def extract_full_text(
    url: str,
    retries: int = DEFAULT_TEXT_EXTRACTION_RETRIES,
    sleep_time: float = DEFAULT_TEXT_EXTRACTION_SLEEP,
    min_length: int = 300
) -> Optional[str]:
    """
    Извлекает полный текст статьи по URL.
    
    Пытается скачать статью и извлечь чистый текст без картинок, ссылок и HTML-разметки.
    Если сайт временно не отвечает — делает несколько попыток.
    
    Args:
        url: URL статьи для извлечения текста
        retries: Количество попыток при ошибке
        sleep_time: Время задержки между попытками (секунды)
        min_length: Минимальная длина текста для успешного извлечения
        
    Returns:
        Извлеченный текст или None, если не удалось извлечь
    """
    for attempt in range(retries):
        try:
            downloaded = trafilatura.fetch_url(url)
            
            if downloaded:
                text = trafilatura.extract(
                    downloaded,
                    include_links=False,
                    include_images=False,
                    include_tables=False,
                    favor_recall=True,
                    deduplicate=True,
                )
                
                if text and len(text) > min_length:
                    return text
                elif text:
                    logger.warning(f"Текст слишком короткий ({len(text)} символов) для {url}")
            
        except Exception as e:
            logger.warning(f"Ошибка извлечения текста (попытка {attempt + 1}/{retries}) для {url}: {e}")
        
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

