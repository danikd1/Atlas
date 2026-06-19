"""
Тесты компонента RSS-сбора.

Покрывает: strip_appeared_first_on, validate_and_deduplicate_feeds.
Запуск: python3 -m pytest tests/test_rss_collection.py -v
"""
import pytest

from src.pipeline.rss_parser import strip_appeared_first_on, validate_and_deduplicate_feeds


# ── strip_appeared_first_on ───────────────────────────────────────────────────

def test_strip_appeared_first_on_removes_via_regex():
    """Мусорная фраза 'The post ... appeared first on ...' удаляется через regex."""
    summary = "Полезный текст статьи. The post Заголовок appeared first on Блог."
    result = strip_appeared_first_on(summary)
    assert "appeared first on" not in result
    assert "Полезный текст статьи" in result


def test_strip_appeared_first_on_removes_via_split():
    """Фраза ' appeared first on ' удаляется через split (запасной путь)."""
    summary = "Текст статьи appeared first on Название блога."
    result = strip_appeared_first_on(summary)
    assert "appeared first on" not in result
    assert "Текст статьи" in result


def test_strip_appeared_first_on_clean_text_unchanged():
    """Строка без мусора возвращается без изменений."""
    summary = "Обычный текст без лишних фраз."
    result = strip_appeared_first_on(summary)
    assert result == summary


def test_strip_appeared_first_on_empty_string():
    """Пустая строка → возвращает пустую строку без падения."""
    assert strip_appeared_first_on("") == ""


def test_strip_appeared_first_on_none():
    """None → возвращает пустую строку без падения."""
    assert strip_appeared_first_on(None) == ""


# ── validate_and_deduplicate_feeds ────────────────────────────────────────────

def test_validate_feeds_removes_empty_url():
    """Пустой URL пропускается."""
    feeds = {"лента1": "https://example.com", "лента2": ""}
    result = validate_and_deduplicate_feeds(feeds)
    assert "лента2" not in result
    assert "лента1" in result


def test_validate_feeds_removes_empty_name():
    """Пустое имя ленты пропускается."""
    feeds = {"": "https://example.com", "лента1": "https://other.com"}
    result = validate_and_deduplicate_feeds(feeds)
    assert "" not in result
    assert "лента1" in result


def test_validate_feeds_strips_url_whitespace():
    """URL с пробелами обрезается через strip()."""
    feeds = {"лента1": "  https://example.com  "}
    result = validate_and_deduplicate_feeds(feeds)
    assert result["лента1"] == "https://example.com"


def test_validate_feeds_raises_on_non_dict():
    """Не-словарь на входе → выбрасывает ValueError."""
    with pytest.raises(ValueError):
        validate_and_deduplicate_feeds(["https://example.com"])
