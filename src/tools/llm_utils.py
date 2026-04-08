"""
Модуль для работы с GigaChat LLM.

Обеспечивает:
- Очистку текста для LLM
- Суммаризацию статей через GigaChat (основной путь)
- Суммаризацию через facebook/bart-large-cnn (fallback когда GigaChat недоступен)

Управление fallback:
  # В config.py: GIGACHAT_SUMMARIZATION_ENABLED = False
  # Или через env:
  GIGACHAT_SUMMARIZATION_ENABLED=false python3 -m src.main
"""
import logging
import re
from typing import Optional

from bs4 import BeautifulSoup
from gigachat import GigaChat

from config.config import (
    BART_SUMMARIZATION_MODEL,
    BART_SUMMARY_MAX_LENGTH,
    BART_SUMMARY_MIN_LENGTH,
    DEFAULT_SUMMARY_MAX_CHARS,
    DEFAULT_SUMMARY_TEMPERATURE,
    DEFAULT_TEXT_CLEAN_MAX_CHARS,
    GIGACHAT_CREDENTIALS,
    GIGACHAT_MODEL,
    GIGACHAT_SUMMARIZATION_ENABLED,
    GIGACHAT_VERIFY_SSL,
)
from .prompt_loader import format_prompt, load_prompt
from .rate_limiter import RateLimiter

logger = logging.getLogger(__name__)

# Ленивая инициализация BART — загружается только при первом вызове fallback
_bart_pipeline = None


def _get_bart_pipeline():
    """Возвращает pipeline суммаризации BART (загружает модель при первом вызове)."""
    global _bart_pipeline
    if _bart_pipeline is None:
        try:
            from transformers import pipeline
            logger.info("Загрузка BART fallback модели: %s", BART_SUMMARIZATION_MODEL)
            _bart_pipeline = pipeline(
                "summarization",
                model=BART_SUMMARIZATION_MODEL,
                truncation=True,
            )
            logger.info("✅ BART модель загружена")
        except Exception as e:
            logger.error("Не удалось загрузить BART модель: %s", e)
            raise RuntimeError(f"BART fallback недоступен: {e}") from e
    return _bart_pipeline


def _summarize_with_bart(title: str, text: str, max_chars: int = 4000) -> str:
    """
    Суммаризация через facebook/bart-large-cnn (fallback).

    BART — английская модель, результат на том же языке что и входной текст.
    Для русских статей используйте IlyaGusev/mbart_ru_sum_gazeta (см. config.py).

    Args:
        title: Заголовок статьи (добавляется к тексту для контекста).
        text: Текст статьи.
        max_chars: Обрезаем вход до этого числа символов перед подачей в модель.

    Returns:
        Строка-резюме от BART.
    """
    bart = _get_bart_pipeline()

    # BART принимает до 1024 токенов; обрезаем по символам как приближение
    combined = f"{title}. {text}" if title else text
    combined = combined[:max_chars]

    result = bart(
        combined,
        max_length=BART_SUMMARY_MAX_LENGTH,
        min_length=BART_SUMMARY_MIN_LENGTH,
        do_sample=False,
    )
    return result[0]["summary_text"].strip()


def create_gigachat_client() -> GigaChat:
    """
    Создает новый клиент GigaChat.

    FastAPI запускает синхронные эндпоинты в AnyIO worker thread, где нет
    event loop. GigaChat при инициализации вызывает asyncio.get_event_loop()
    внутри — создаём loop вручную если его нет.

    Returns:
        Экземпляр GigaChat

    Raises:
        RuntimeError: Если не удалось создать клиент
    """
    import asyncio
    try:
        asyncio.get_event_loop()
    except RuntimeError:
        asyncio.set_event_loop(asyncio.new_event_loop())

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
    client: Optional[GigaChat] = None,
    rate_limiter: Optional[RateLimiter] = None,
    max_chars: int = DEFAULT_SUMMARY_MAX_CHARS,
    temperature: float = DEFAULT_SUMMARY_TEMPERATURE,
) -> str:
    """
    Делает выжимку из статьи: 3–4 предложения на русском (GigaChat) или на языке
    оригинала (BART fallback).

    Порядок:
      1. Если GIGACHAT_SUMMARIZATION_ENABLED=True и client передан — GigaChat.
      2. Если GigaChat выбросил исключение или отключён — BART fallback.
      3. Если и BART недоступен — возвращает строку с ошибкой.

    Args:
        title: Заголовок статьи.
        full_text: Полный текст статьи.
        client: Клиент GigaChat; если None и GigaChat включён — логируется предупреждение.
        rate_limiter: Rate limiter для управления задержками между запросами к GigaChat.
        max_chars: Максимальная длина текста перед отправкой в модель.
        temperature: Temperature для GigaChat.

    Returns:
        Краткая выжимка статьи.
    """
    if not isinstance(full_text, str) or not full_text.strip():
        return "Не удалось получить текст статьи для суммаризации."

    cleaned = clean_text_for_llm(full_text, max_chars=max_chars)

    # ── Основной путь: GigaChat ───────────────────────────────────────────
    if GIGACHAT_SUMMARIZATION_ENABLED:
        if client is None:
            logger.warning("GigaChat включён, но client не передан — переключаемся на BART.")
        else:
            system_prompt = load_prompt("summary_system")
            user_prompt_template = load_prompt("summary_user")
            user_prompt = format_prompt(user_prompt_template, title=title, cleaned_text=cleaned)

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]

            if rate_limiter:
                rate_limiter.wait_if_needed()

            try:
                result = client.chat({"messages": messages, "temperature": temperature})
                return result.choices[0].message.content.strip()
            except Exception as e:
                logger.warning(
                    "GigaChat недоступен для статьи '%s': %s — переключаемся на BART.",
                    title[:50],
                    e,
                )
    else:
        logger.info("GigaChat отключён (GIGACHAT_SUMMARIZATION_ENABLED=False) — используем BART.")

    # ── Fallback: BART ────────────────────────────────────────────────────
    try:
        summary = _summarize_with_bart(title, cleaned)
        logger.info("BART fallback успешно сработал для '%s'", title[:50])
        return summary
    except Exception as e:
        logger.error("BART fallback тоже недоступен для '%s': %s", title[:50], e)
        return "Ошибка при суммаризации статьи (GigaChat и BART недоступны)."


FEED_CATEGORIES = [
    "AI & ML",
    "Engineering",
    "Cloud & DevOps",
    "Data",
    "Security",
    "Design",
    "Tools",
    "Management",
    "Tech News",
    "Case Studies",
]


def suggest_feed_category(name: str, description: str, url: str) -> Optional[str]:
    """
    Определяет категорию RSS-ленты через GigaChat.

    Используется при добавлении ленты пользователем вручную — предлагает категорию
    которую пользователь может принять или изменить.

    Args:
        name: Название ленты (из тега <title> RSS-фида).
        description: Описание ленты (из тега <description> или <subtitle>).
        url: URL ленты — используется как дополнительный контекст.

    Returns:
        Название категории из FEED_CATEGORIES или None если GigaChat недоступен.
    """
    try:
        categories_list = "\n".join(f"- {c}" for c in FEED_CATEGORIES)
        prompt = (
            f"Определи категорию для RSS-ленты. Выбери одну категорию из списка ниже.\n\n"
            f"Лента:\n"
            f"- Название: {name}\n"
            f"- Описание: {description or 'не указано'}\n"
            f"- URL: {url}\n\n"
            f"Доступные категории:\n{categories_list}\n\n"
            f"Ответь одной строкой — только названием категории из списка, без пояснений."
        )
        client = create_gigachat_client()
        with client:
            from gigachat.models import Chat, Messages, MessagesRole
            response = client.chat(
                Chat(
                    messages=[Messages(role=MessagesRole.USER, content=prompt)],
                    temperature=0.0,
                    max_tokens=20,
                )
            )
        result = response.choices[0].message.content.strip()
        # Проверяем что ответ входит в список категорий
        if result in FEED_CATEGORIES:
            return result
        # Пробуем найти частичное совпадение
        for cat in FEED_CATEGORIES:
            if cat.lower() in result.lower() or result.lower() in cat.lower():
                return cat
        logger.warning("GigaChat вернул неизвестную категорию: '%s'", result)
        return None
    except Exception as e:
        logger.warning("Не удалось определить категорию через GigaChat: %s", e)
        return None


def generate_feed_description(name: str, url: str, titles: list) -> Optional[str]:
    """
    Генерирует описание RSS-ленты на русском языке на основе заголовков последних статей.

    Args:
        name: Название ленты.
        url: URL ленты — используется как дополнительный контекст.
        titles: Список заголовков последних статей (до 10).

    Returns:
        Описание ленты одним предложением на русском или None если GigaChat недоступен.
    """
    if not titles:
        return None
    try:
        titles_text = "\n".join(f"- {t}" for t in titles[:10])
        prompt = (
            f"Напиши описание RSS-ленты одним коротким предложением на русском языке.\n"
            f"Описание должно объяснять о чём эта лента — какие темы она освещает.\n"
            f"Не упоминай название ленты в описании.\n\n"
            f"Лента: {name}\n"
            f"URL: {url}\n\n"
            f"Последние заголовки статей:\n{titles_text}\n\n"
            f"Ответь только одним предложением, без пояснений."
        )
        client = create_gigachat_client()
        with client:
            from gigachat.models import Chat, Messages, MessagesRole
            response = client.chat(
                Chat(
                    messages=[Messages(role=MessagesRole.USER, content=prompt)],
                    temperature=0.3,
                    max_tokens=100,
                )
            )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logger.warning("Не удалось сгенерировать описание ленты через GigaChat: %s", e)
        return None


def generate_feed_descriptions_batch(feeds: list) -> dict:
    """
    Генерирует описания для нескольких лент за один LLM-вызов.

    Args:
        feeds: Список словарей {"id": int, "name": str, "url": str, "titles": List[str]}

    Returns:
        Словарь {feed_id: description} для лент где удалось сгенерировать описание.
    """
    if not feeds:
        return {}
    try:
        feeds_text = ""
        for i, feed in enumerate(feeds, 1):
            titles_text = "\n".join(f"  - {t}" for t in feed["titles"][:10])
            feeds_text += (
                f"Лента {i}:\n"
                f"  Название: {feed['name']}\n"
                f"  URL: {feed['url']}\n"
                f"  Заголовки статей:\n{titles_text}\n\n"
            )
        prompt = (
            f"Для каждой ленты напиши описание одним коротким предложением на русском языке.\n"
            f"Описание должно объяснять о чём лента — какие темы она освещает.\n"
            f"Не упоминай название ленты в описании.\n\n"
            f"{feeds_text}"
            f"Ответь строго в формате JSON-массива:\n"
            f'[{{"index": 1, "description": "..."}}, {{"index": 2, "description": "..."}}, ...]'
        )
        client = create_gigachat_client()
        with client:
            from gigachat.models import Chat, Messages, MessagesRole
            response = client.chat(
                Chat(
                    messages=[Messages(role=MessagesRole.USER, content=prompt)],
                    temperature=0.3,
                    max_tokens=1000,
                )
            )
        import json, re
        raw = response.choices[0].message.content.strip()
        # Вырезаем JSON из ответа если обёрнут в markdown
        match = re.search(r"\[.*\]", raw, re.DOTALL)
        if not match:
            logger.warning("generate_feed_descriptions_batch: не удалось найти JSON в ответе")
            return {}
        items = json.loads(match.group())
        result = {}
        for item in items:
            idx = item.get("index", 0) - 1
            if 0 <= idx < len(feeds) and item.get("description"):
                result[feeds[idx]["id"]] = item["description"].strip()
        return result
    except Exception as e:
        logger.warning("generate_feed_descriptions_batch: ошибка GigaChat: %s", e)
        return {}


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
