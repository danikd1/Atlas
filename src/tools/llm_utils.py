"""
Модуль для работы с GigaChat LLM.

Обеспечивает:
- Очистку текста для LLM
- Суммаризацию статей
"""
import logging
import re
from typing import Optional

from bs4 import BeautifulSoup
from gigachat import GigaChat

from config.config import (
    DEFAULT_SUMMARY_MAX_CHARS,
    DEFAULT_SUMMARY_TEMPERATURE,
    DEFAULT_TEXT_CLEAN_MAX_CHARS,
    GIGACHAT_CREDENTIALS,
    GIGACHAT_MODEL,
    GIGACHAT_VERIFY_SSL,
)
from .prompt_loader import format_prompt, load_prompt
from .rate_limiter import RateLimiter

logger = logging.getLogger(__name__)


def create_gigachat_client() -> GigaChat:
    """
    Создает новый клиент GigaChat.
    
    Returns:
        Экземпляр GigaChat
        
    Raises:
        RuntimeError: Если не удалось создать клиент
    """
    try:
        logger.info(f"Инициализация GigaChat клиента (модель: {GIGACHAT_MODEL})...")
        client = GigaChat(
            credentials=GIGACHAT_CREDENTIALS,
            verify_ssl_certs=GIGACHAT_VERIFY_SSL,
            model=GIGACHAT_MODEL,
        )
        logger.info("✅ GigaChat клиент инициализирован")
        return client
    except Exception as e:
        error_msg = f"Ошибка инициализации GigaChat клиента: {e}"
        logger.error(error_msg)
        raise RuntimeError(error_msg) from e


def clean_text_for_llm(text: str, max_chars: int = DEFAULT_TEXT_CLEAN_MAX_CHARS) -> str:
    """
    Очищает текст перед отправкой в LLM.
    
    - Если текст содержит HTML — извлекает только видимый текст через BeautifulSoup
    - Удаляет <script>, <style> и скрытые элементы
    - Нормализует переносы строк и пробелы
    - Удаляет слишком длинные блоки пустых строк
    - При необходимости обрезает текст по длине
    
    Args:
        text: Исходный текст для очистки
        max_chars: Максимальная длина текста после очистки
        
    Returns:
        Очищенный текст
    """
    if not isinstance(text, str) or len(text.strip()) == 0:
        return ""
    
    try:
        # Пробуем распарсить как HTML
        soup = BeautifulSoup(text, "lxml")
        
        # Удаляем скрипты и стили
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()
        
        # Извлекаем текст
        cleaned = soup.get_text(separator="\n")
    except Exception:
        # Если не HTML, используем текст как есть
        cleaned = text
    
    # Нормализация пробелов
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    
    # Нормализация пустых строк (оставляем максимум 2 подряд)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    
    cleaned = cleaned.strip()
    
    # Обрезка если текст слишком длинный
    if max_chars is not None and len(cleaned) > max_chars:
        cleaned = cleaned[:max_chars] + "\n\n[TEXT TRUNCATED]"
    
    return cleaned


def summarize_article(
    title: str,
    full_text: str,
    client: GigaChat,
    rate_limiter: Optional[RateLimiter] = None,
    max_chars: int = DEFAULT_SUMMARY_MAX_CHARS,
    temperature: float = DEFAULT_SUMMARY_TEMPERATURE
) -> str:
    """
    Делает выжимку из статьи: 3–4 предложения на русском.
    
    Использует очищенный full_text.
    
    Args:
        title: Заголовок статьи
        full_text: Полный текст статьи
        client: Клиент GigaChat (обязательный параметр)
        rate_limiter: Rate limiter для управления задержками
        max_chars: Максимальная длина текста для суммаризации
        temperature: Temperature для LLM
        
    Returns:
        Краткая выжимка статьи (3–4 предложения)
    """
    if not isinstance(full_text, str) or not full_text.strip():
        return "Не удалось получить текст статьи для суммаризации."
    
    cleaned = clean_text_for_llm(full_text, max_chars=max_chars)
    
    # Загружаем промпты из файлов
    system_prompt = load_prompt("summary_system")
    user_prompt_template = load_prompt("summary_user")
    user_prompt = format_prompt(user_prompt_template, title=title, cleaned_text=cleaned)
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    
    # Rate limiting
    if rate_limiter:
        rate_limiter.wait_if_needed()
    
    try:
        result = client.chat({"messages": messages, "temperature": temperature})
        summary = result.choices[0].message.content.strip()
        return summary
    except Exception as e:
        logger.error(f"Ошибка при суммаризации статьи '{title[:50]}...': {e}")
        return "Ошибка при суммаризации статьи."


def format_summary_text(summary: str, width: int = 100) -> str:
    """
    Форматирует суммаризацию: аккуратные переносы строк, абзацы.
    
    Args:
        summary: Текст суммаризации
        width: Ширина строки для переноса
        
    Returns:
        Отформатированный текст
    """
    import textwrap
    
    # Разделяем на абзацы, сохраняем структуру
    paragraphs = summary.split("\n")
    
    formatted = []
    for p in paragraphs:
        p = p.strip()
        if not p:
            formatted.append("")  # пустая строка между абзацами
        else:
            wrapped = textwrap.fill(p, width=width)
            formatted.append(wrapped)
    
    return "\n".join(formatted)
