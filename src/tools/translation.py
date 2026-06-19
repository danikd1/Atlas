"""
Перевод текста EN → RU с помощью Helsinki-NLP/opus-mt-en-ru (MarianMT).

Модель загружается лениво при первом вызове и кэшируется в памяти процесса.
Длинные тексты разбиваются на чанки по ~400 слов (лимит модели 512 токенов).
"""

from __future__ import annotations
import re
from html import escape
from typing import Optional

MODEL_NAME = "Helsinki-NLP/opus-mt-en-ru"

_model = None
_tokenizer = None


def _get_translator():
    global _model, _tokenizer
    if _model is None:
        from transformers import MarianMTModel, MarianTokenizer
        _tokenizer = MarianTokenizer.from_pretrained(MODEL_NAME)
        _model = MarianMTModel.from_pretrained(MODEL_NAME)
    return _model, _tokenizer


def _split_into_chunks(text: str, max_words: int = 200) -> list[str]:
    """Разбивает текст на чанки по границам предложений, не превышая max_words слов."""
    # Разбиваем на предложения
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    chunks: list[str] = []
    current: list[str] = []
    current_words = 0

    for sentence in sentences:
        words = len(sentence.split())
        if current_words + words > max_words and current:
            chunks.append(" ".join(current))
            current = [sentence]
            current_words = words
        else:
            current.append(sentence)
            current_words += words

    if current:
        chunks.append(" ".join(current))

    return chunks or [text]


def _is_garbage(text: str) -> bool:
    """Проверяет что перевод не является мусором (повторяющиеся токены)."""
    if len(text) < 10:
        return False
    # Берём первые 100 символов и проверяем на повторяющиеся паттерны
    sample = text[:200].upper()
    words = sample.split()
    if len(words) < 4:
        return False
    # Если больше 40% слов повторяются — мусор
    unique = len(set(words))
    return unique / len(words) < 0.4


def _translate_chunk(text: str, model, tokenizer) -> str:
    """Переводит один чанк текста."""
    inputs = tokenizer(
        [text],
        return_tensors="pt",
        padding=True,
        truncation=True,
        max_length=512,
    )
    translated = model.generate(
        **inputs,
        num_beams=4,
        repetition_penalty=3.0,
        no_repeat_ngram_size=4,
        max_new_tokens=512,
    )
    result = tokenizer.decode(translated[0], skip_special_tokens=True)
    # Если получился мусор — возвращаем оригинал
    if _is_garbage(result):
        return text
    return result


def translate_text(text: str) -> str:
    """
    Переводит произвольный текст с EN на RU.
    Разбивает на чанки если текст длинный.
    """
    if not text or not text.strip():
        return text

    model, tokenizer = _get_translator()
    chunks = _split_into_chunks(text)
    translated_chunks = [_translate_chunk(chunk, model, tokenizer) for chunk in chunks]
    return " ".join(translated_chunks)


# Блочные элементы, чей текст переводим как единицу
_BLOCK_TAGS = {"p", "h1", "h2", "h3", "h4", "h5", "h6", "li", "td", "th", "figcaption", "blockquote"}


def _translate_html_tag(tag) -> None:
    """Рекурсивно переводит блочные элементы, сохраняя структуру HTML."""
    from bs4 import NavigableString, Tag
    for child in list(tag.children):
        if not isinstance(child, Tag):
            continue
        if child.name == "img":
            continue  # изображения не трогаем
        if child.name in _BLOCK_TAGS:
            text = child.get_text(strip=True)
            if text:
                child.clear()
                child.append(NavigableString(translate_text(text)))
        else:
            _translate_html_tag(child)


def translate_html_structure(html: str) -> str:
    """Переводит HTML с сохранением структуры: заголовки, параграфы, списки, картинки.
    Инлайн-ссылки (<a>) теряют href — порядок слов после перевода меняется."""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    _translate_html_tag(soup)
    return str(soup)


def strip_html(html: str) -> str:
    """Извлекает plain text из HTML через BeautifulSoup."""
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")
        # Добавляем перенос строки после блочных элементов
        for tag in soup.find_all(["p", "br", "h1", "h2", "h3", "h4", "li"]):
            tag.append("\n")
        return soup.get_text(separator=" ").strip()
    except Exception:
        # Fallback: простое удаление тегов через regex
        return re.sub(r"<[^>]+>", " ", html).strip()


def translate_article(
    title: Optional[str],
    summary: Optional[str],
    full_text: Optional[str],
) -> dict:
    """
    Переводит все поля статьи.
    Возвращает dict с ключами title, summary, full_text.
    """
    result: dict = {}

    result["title"] = translate_text(title) if title else None
    result["summary"] = translate_text(summary) if summary else None

    if full_text:
        if re.search(r"<[a-z][\s\S]*>", full_text, re.IGNORECASE):
            # HTML (новый формат trafilatura) — переводим с сохранением структуры
            result["full_text"] = translate_html_structure(full_text)
        else:
            # Plain text (старые статьи в БД) — прежняя логика
            translated_plain = translate_text(full_text)
            paragraphs = [p.strip() for p in translated_plain.split("\n") if p.strip()]
            result["full_text"] = "\n".join(f"<p>{escape(p)}</p>" for p in paragraphs)
    else:
        result["full_text"] = None

    return result
