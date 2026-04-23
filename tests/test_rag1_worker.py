"""
Тесты для Сценария RAG.1 — Фоновое извлечение текстов статей.

Запуск:
    python3 -m pytest tests/test_rag1_worker.py -v
    # или конкретный тест:
    python3 -m pytest tests/test_rag1_worker.py::test_has_cyrillic -v
"""
from unittest.mock import MagicMock, patch, call
import pytest

from src.pipeline.text_extraction_worker import (
    _has_cyrillic,
    _summarize_with_bart_auto,
    get_pending_count,
    extract_pending_articles,
    BART_EN_MODEL,
    BART_RU_MODEL,
)


# ── _has_cyrillic ─────────────────────────────────────────────────────────────

def test_has_cyrillic_russian():
    assert _has_cyrillic("Привет мир") is True

def test_has_cyrillic_english():
    assert _has_cyrillic("Hello world") is False

def test_has_cyrillic_empty():
    assert _has_cyrillic("") is False

def test_has_cyrillic_mixed():
    assert _has_cyrillic("Hello Мир") is True


# ── Выбор модели BART ─────────────────────────────────────────────────────────

def test_bart_auto_selects_ru_model_by_title():
    """Кириллица в заголовке → IlyaGusev."""
    with patch("src.pipeline.text_extraction_worker._get_bart_pipeline") as mock_pipe:
        mock_pipe.return_value = lambda *a, **kw: [{"summary_text": "резюме"}]
        with patch("src.tools.translation.strip_html", return_value="текст статьи"):
            _summarize_with_bart_auto("Привет", "some text")
            mock_pipe.assert_called_once_with(BART_RU_MODEL)

def test_bart_auto_selects_ru_model_by_text():
    """Кириллица в тексте (при английском заголовке) → IlyaGusev."""
    with patch("src.pipeline.text_extraction_worker._get_bart_pipeline") as mock_pipe:
        mock_pipe.return_value = lambda *a, **kw: [{"summary_text": "summary"}]
        with patch("src.tools.translation.strip_html", return_value="Это русский текст статьи"):
            _summarize_with_bart_auto("English title", "Это русский текст статьи")
            mock_pipe.assert_called_once_with(BART_RU_MODEL)

def test_bart_auto_selects_en_model():
    """Только латиница → facebook/bart-large-cnn."""
    with patch("src.pipeline.text_extraction_worker._get_bart_pipeline") as mock_pipe:
        mock_pipe.return_value = lambda *a, **kw: [{"summary_text": "summary"}]
        with patch("src.tools.translation.strip_html", return_value="English article text"):
            _summarize_with_bart_auto("English title", "English article text")
            mock_pipe.assert_called_once_with(BART_EN_MODEL)

def test_bart_auto_empty_text_returns_empty():
    """Пустой текст → пустая строка, BART не вызывается."""
    with patch("src.pipeline.text_extraction_worker._get_bart_pipeline") as mock_pipe:
        result = _summarize_with_bart_auto("title", "")
        assert result == ""
        mock_pipe.assert_not_called()


# ── get_pending_count ─────────────────────────────────────────────────────────

def test_get_pending_count_returns_correct_number():
    conn = MagicMock()
    conn.cursor.return_value.__enter__.return_value.fetchone.return_value = (42,)
    assert get_pending_count(conn) == 42

def test_get_pending_count_none_conn():
    assert get_pending_count(None) == 0


# ── extract_pending_articles ──────────────────────────────────────────────────

def _make_article(article_id, link, title="Test", ai_summary=None):
    return {"id": article_id, "link": link, "title": title, "ai_summary": ai_summary}


def test_successful_extraction_saves_fulltext():
    """Успешное извлечение → full_text сохраняется, статья не помечается ошибкой."""
    conn = MagicMock()
    articles = [_make_article(1, "https://example.com/article1")]

    with patch("src.tools.db_state.get_articles_without_fulltext", return_value=articles), \
         patch("src.tools.db_state.get_articles_without_summary", return_value=[]), \
         patch("src.tools.db_state.update_article_full_text") as mock_update, \
         patch("src.tools.db_state.mark_fulltext_error") as mock_error, \
         patch("src.tools.db_state.save_ai_summary"), \
         patch("src.tools.text_extraction.extract_full_text", return_value="article text"), \
         patch("src.pipeline.text_extraction_worker._summarize_with_bart_auto", return_value="summary"):

        result = extract_pending_articles(conn, batch_size=10, domain_delay=0)

    mock_update.assert_called_once_with(conn, 1, "article text")
    mock_error.assert_not_called()
    assert result["extracted"] == 1


def test_failed_extraction_marks_error():
    """Нет текста → full_text_error = TRUE, повторно не обрабатывается."""
    conn = MagicMock()
    articles = [_make_article(2, "https://paywalled.com/article")]

    with patch("src.tools.db_state.get_articles_without_fulltext", return_value=articles), \
         patch("src.tools.db_state.get_articles_without_summary", return_value=[]), \
         patch("src.tools.db_state.update_article_full_text") as mock_update, \
         patch("src.tools.db_state.mark_fulltext_error") as mock_error, \
         patch("src.tools.db_state.mark_domain_fulltext_error", return_value=0), \
         patch("src.tools.text_extraction.extract_full_text", return_value=None):

        result = extract_pending_articles(conn, batch_size=10, domain_delay=0)

    mock_error.assert_called_once_with(conn, 2)
    mock_update.assert_not_called()
    assert result["failed"] == 1


def test_bart_not_called_if_summary_exists():
    """Если ai_summary уже есть — BART не перезаписывает."""
    conn = MagicMock()
    articles = [_make_article(3, "https://example.com/a", ai_summary="уже есть резюме")]

    with patch("src.tools.db_state.get_articles_without_fulltext", return_value=articles), \
         patch("src.tools.db_state.get_articles_without_summary", return_value=[]), \
         patch("src.tools.db_state.update_article_full_text"), \
         patch("src.tools.db_state.save_ai_summary") as mock_save, \
         patch("src.tools.text_extraction.extract_full_text", return_value="text"), \
         patch("src.pipeline.text_extraction_worker._summarize_with_bart_auto") as mock_bart:

        extract_pending_articles(conn, batch_size=10, domain_delay=0)

    mock_bart.assert_not_called()
    mock_save.assert_not_called()


def test_phase2_summarizes_articles_without_summary():
    """Фаза 2: статьи с full_text но без ai_summary получают BART-резюме."""
    conn = MagicMock()
    phase2_articles = [{"id": 10, "title": "Title", "full_text": "Some text"}]

    with patch("src.tools.db_state.get_articles_without_fulltext", return_value=[]), \
         patch("src.tools.db_state.get_articles_without_summary", return_value=phase2_articles), \
         patch("src.tools.db_state.save_ai_summary") as mock_save, \
         patch("src.pipeline.text_extraction_worker._summarize_with_bart_auto", return_value="summary"):

        result = extract_pending_articles(conn, batch_size=10, domain_delay=0)

    mock_save.assert_called_once_with(conn, 10, "summary")
    assert result["summarized"] == 1


def test_extraction_exception_marks_error():
    """Исключение при извлечении → full_text_error = TRUE."""
    conn = MagicMock()
    articles = [_make_article(4, "https://broken.com/article")]

    with patch("src.tools.db_state.get_articles_without_fulltext", return_value=articles), \
         patch("src.tools.db_state.get_articles_without_summary", return_value=[]), \
         patch("src.tools.db_state.mark_fulltext_error") as mock_error, \
         patch("src.tools.db_state.mark_domain_fulltext_error", return_value=0), \
         patch("src.tools.text_extraction.extract_full_text", side_effect=Exception("timeout")):

        result = extract_pending_articles(conn, batch_size=10, domain_delay=0)

    mock_error.assert_called_once_with(conn, 4)
    assert result["failed"] == 1
