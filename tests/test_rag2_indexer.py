"""
Тесты для Сценария RAG.2 — Индексация: чанкирование и запись в rag_documents.

Запуск:
    python3 -m pytest tests/test_rag2_indexer.py -v
    # или конкретный тест:
    python3 -m pytest tests/test_rag2_indexer.py::test_empty_queue_returns_zeros -v
"""
from unittest.mock import MagicMock, patch, call
import numpy as np
import pytest

from src.pipeline.rag_indexer import index_pending_articles


# ── Вспомогательные фабрики ───────────────────────────────────────────────────

def _make_article(article_id, link="https://example.com/a", title="Test Title",
                  full_text="Some text content.", summary="", source="example.com"):
    return {
        "id": article_id,
        "link": link,
        "title": title,
        "full_text": full_text,
        "summary": summary,
        "source": source,
        "published_at": None,
    }


def _fake_model(dim=768):
    """Мок SentenceTransformer — возвращает случайные эмбеддинги нужной размерности."""
    model = MagicMock()
    model.tokenizer = None
    def encode(texts, **kwargs):
        return np.random.rand(len(texts), dim).astype(np.float32)
    model.encode.side_effect = encode
    return model


# ── Пустая очередь ────────────────────────────────────────────────────────────

def test_empty_queue_returns_zeros():
    """Нет статей для индексации → возвращает нули, ничего не пишет в БД."""
    conn = MagicMock()

    with patch("src.tools.db_state.get_or_create_global_rag_collection",
               return_value={"id": 1}), \
         patch("src.tools.db_state.get_articles_for_rag_indexing", return_value=[]), \
         patch("src.tools.db_state.upsert_rag_documents") as mock_upsert:

        result = index_pending_articles(conn)

    assert result == {"indexed": 0, "chunks_created": 0, "failed": 0}
    mock_upsert.assert_not_called()


def test_no_collection_returns_zeros():
    """Коллекция недоступна (БД упала) → возвращает нули без падения."""
    conn = MagicMock()

    with patch("src.tools.db_state.get_or_create_global_rag_collection",
               return_value=None):
        result = index_pending_articles(conn)

    assert result == {"indexed": 0, "chunks_created": 0, "failed": 0}


# ── Успешная индексация ───────────────────────────────────────────────────────

def test_successful_indexing_marks_article():
    """Статья с full_text → чанкируется, эмбеддируется, помечается rag_indexed_at."""
    conn = MagicMock()
    article = _make_article(1, full_text="First paragraph.\n\nSecond paragraph.")

    with patch("src.tools.db_state.get_or_create_global_rag_collection",
               return_value={"id": 42}), \
         patch("src.tools.db_state.get_articles_for_rag_indexing",
               return_value=[article]), \
         patch("src.tools.db_state.delete_rag_documents_by_links") as mock_delete, \
         patch("src.tools.db_state.upsert_rag_documents", return_value=2) as mock_upsert, \
         patch("src.tools.db_state.mark_articles_rag_indexed") as mock_mark, \
         patch("src.pipeline.embedding_filter.get_embedding_model",
               return_value=_fake_model()):

        result = index_pending_articles(conn)

    assert result["indexed"] == 1
    assert result["chunks_created"] == 2
    assert result["failed"] == 0
    mock_mark.assert_called_once_with(conn, [1])
    mock_delete.assert_called_once_with(conn, 42, ["https://example.com/a"])


def test_chunks_contain_title_in_payload():
    """text_payload каждого чанка начинается с заголовка статьи."""
    conn = MagicMock()
    article = _make_article(1, title="Уникальный заголовок",
                            full_text="Первый абзац.\n\nВторой абзац.")
    captured_docs = []

    def capture_upsert(conn, collection_id, discipline, ga, activity, documents):
        captured_docs.extend(documents)
        return len(documents)

    with patch("src.tools.db_state.get_or_create_global_rag_collection",
               return_value={"id": 1}), \
         patch("src.tools.db_state.get_articles_for_rag_indexing",
               return_value=[article]), \
         patch("src.tools.db_state.delete_rag_documents_by_links"), \
         patch("src.tools.db_state.upsert_rag_documents", side_effect=capture_upsert), \
         patch("src.tools.db_state.mark_articles_rag_indexed"), \
         patch("src.pipeline.embedding_filter.get_embedding_model",
               return_value=_fake_model()):

        index_pending_articles(conn)

    assert len(captured_docs) > 0
    for doc in captured_docs:
        assert "Уникальный заголовок" in doc["text_payload"]


def test_embeddings_attached_to_chunks():
    """Каждый чанк в upsert получает embedding — список float нужной размерности."""
    conn = MagicMock()
    article = _make_article(1, full_text="Text for embedding test.")
    captured_docs = []

    def capture_upsert(conn, collection_id, discipline, ga, activity, documents):
        captured_docs.extend(documents)
        return len(documents)

    with patch("src.tools.db_state.get_or_create_global_rag_collection",
               return_value={"id": 1}), \
         patch("src.tools.db_state.get_articles_for_rag_indexing",
               return_value=[article]), \
         patch("src.tools.db_state.delete_rag_documents_by_links"), \
         patch("src.tools.db_state.upsert_rag_documents", side_effect=capture_upsert), \
         patch("src.tools.db_state.mark_articles_rag_indexed"), \
         patch("src.pipeline.embedding_filter.get_embedding_model",
               return_value=_fake_model(dim=768)):

        index_pending_articles(conn)

    assert len(captured_docs) > 0
    for doc in captured_docs:
        assert "embedding" in doc
        assert isinstance(doc["embedding"], list)
        assert len(doc["embedding"]) == 768


def test_chunk_indices_are_sequential():
    """chunk_index назначается последовательно начиная с 0."""
    conn = MagicMock()
    # Длинный текст чтобы гарантированно разбился на несколько чанков
    long_text = "Sentence number one. " * 100
    article = _make_article(1, full_text=long_text)
    captured_docs = []

    def capture_upsert(conn, collection_id, discipline, ga, activity, documents):
        captured_docs.extend(documents)
        return len(documents)

    with patch("src.tools.db_state.get_or_create_global_rag_collection",
               return_value={"id": 1}), \
         patch("src.tools.db_state.get_articles_for_rag_indexing",
               return_value=[article]), \
         patch("src.tools.db_state.delete_rag_documents_by_links"), \
         patch("src.tools.db_state.upsert_rag_documents", side_effect=capture_upsert), \
         patch("src.tools.db_state.mark_articles_rag_indexed"), \
         patch("src.pipeline.embedding_filter.get_embedding_model",
               return_value=_fake_model()):

        index_pending_articles(conn)

    indices = [d["chunk_index"] for d in captured_docs]
    assert indices == list(range(len(indices)))


# ── HTML в full_text ──────────────────────────────────────────────────────────

def test_strip_html_called_before_chunking():
    """strip_html вызывается перед чанкированием — HTML-теги не попадают в text_payload."""
    conn = MagicMock()
    article = _make_article(1, full_text="<p>Текст статьи.</p><p>Второй абзац.</p>")
    captured_docs = []

    def capture_upsert(conn, collection_id, discipline, ga, activity, documents):
        captured_docs.extend(documents)
        return len(documents)

    with patch("src.tools.db_state.get_or_create_global_rag_collection",
               return_value={"id": 1}), \
         patch("src.tools.db_state.get_articles_for_rag_indexing",
               return_value=[article]), \
         patch("src.tools.db_state.delete_rag_documents_by_links"), \
         patch("src.tools.db_state.upsert_rag_documents", side_effect=capture_upsert), \
         patch("src.tools.db_state.mark_articles_rag_indexed"), \
         patch("src.pipeline.embedding_filter.get_embedding_model",
               return_value=_fake_model()):

        index_pending_articles(conn)

    assert len(captured_docs) > 0
    for doc in captured_docs:
        assert "<p>" not in doc["text_payload"]
        assert "</p>" not in doc["text_payload"]


def test_empty_html_counted_as_failed():
    """full_text содержит только HTML без текста → counted as failed, статья не помечается."""
    conn = MagicMock()
    article = _make_article(1, full_text="<p></p><div></div>")

    with patch("src.tools.db_state.get_or_create_global_rag_collection",
               return_value={"id": 1}), \
         patch("src.tools.db_state.get_articles_for_rag_indexing",
               return_value=[article]), \
         patch("src.tools.db_state.delete_rag_documents_by_links"), \
         patch("src.tools.db_state.upsert_rag_documents") as mock_upsert, \
         patch("src.tools.db_state.mark_articles_rag_indexed") as mock_mark, \
         patch("src.pipeline.embedding_filter.get_embedding_model",
               return_value=_fake_model()):

        result = index_pending_articles(conn)

    assert result["failed"] == 1
    assert result["indexed"] == 0
    mock_upsert.assert_not_called()
    mock_mark.assert_not_called()


# ── Повторная индексация ──────────────────────────────────────────────────────

def test_old_chunks_deleted_before_upsert():
    """Перед записью новых чанков старые удаляются через delete_rag_documents_by_links."""
    conn = MagicMock()
    article = _make_article(1, link="https://example.com/article")

    call_order = []

    def track_delete(*args, **kwargs):
        call_order.append("delete")

    def track_upsert(*args, **kwargs):
        call_order.append("upsert")
        return 1

    with patch("src.tools.db_state.get_or_create_global_rag_collection",
               return_value={"id": 1}), \
         patch("src.tools.db_state.get_articles_for_rag_indexing",
               return_value=[article]), \
         patch("src.tools.db_state.delete_rag_documents_by_links",
               side_effect=track_delete), \
         patch("src.tools.db_state.upsert_rag_documents",
               side_effect=track_upsert), \
         patch("src.tools.db_state.mark_articles_rag_indexed"), \
         patch("src.pipeline.embedding_filter.get_embedding_model",
               return_value=_fake_model()):

        index_pending_articles(conn)

    assert call_order == ["delete", "upsert"], "delete должен вызываться до upsert"


# ── Несколько статей ─────────────────────────────────────────────────────────

def test_multiple_articles_all_indexed():
    """Несколько статей → все помечаются rag_indexed_at = NOW()."""
    conn = MagicMock()
    articles = [
        _make_article(1, link="https://example.com/a1", full_text="Text one."),
        _make_article(2, link="https://example.com/a2", full_text="Text two."),
        _make_article(3, link="https://example.com/a3", full_text="Text three."),
    ]

    with patch("src.tools.db_state.get_or_create_global_rag_collection",
               return_value={"id": 1}), \
         patch("src.tools.db_state.get_articles_for_rag_indexing",
               return_value=articles), \
         patch("src.tools.db_state.delete_rag_documents_by_links"), \
         patch("src.tools.db_state.upsert_rag_documents", return_value=3), \
         patch("src.tools.db_state.mark_articles_rag_indexed") as mock_mark, \
         patch("src.pipeline.embedding_filter.get_embedding_model",
               return_value=_fake_model()):

        result = index_pending_articles(conn)

    assert result["indexed"] == 3
    marked_ids = mock_mark.call_args[0][1]
    assert sorted(marked_ids) == [1, 2, 3]


def test_one_article_fails_others_indexed():
    """Исключение при обработке одной статьи → остальные индексируются."""
    conn = MagicMock()
    articles = [
        _make_article(1, link="https://example.com/ok", full_text="Good text."),
        _make_article(2, link="https://example.com/bad", full_text="Bad text."),
    ]

    original_strip = __import__("src.tools.translation", fromlist=["strip_html"]).strip_html

    call_count = [0]
    def flaky_strip(html):
        call_count[0] += 1
        if call_count[0] == 2:
            raise RuntimeError("simulated failure")
        return original_strip(html)

    with patch("src.tools.db_state.get_or_create_global_rag_collection",
               return_value={"id": 1}), \
         patch("src.tools.db_state.get_articles_for_rag_indexing",
               return_value=articles), \
         patch("src.tools.db_state.delete_rag_documents_by_links"), \
         patch("src.tools.db_state.upsert_rag_documents", return_value=1), \
         patch("src.tools.db_state.mark_articles_rag_indexed") as mock_mark, \
         patch("src.pipeline.embedding_filter.get_embedding_model",
               return_value=_fake_model()), \
         patch("src.tools.translation.strip_html", side_effect=flaky_strip):

        result = index_pending_articles(conn)

    assert result["indexed"] == 1
    assert result["failed"] == 1
    marked_ids = mock_mark.call_args[0][1]
    assert 1 in marked_ids
    assert 2 not in marked_ids


# ── Глобальная коллекция ──────────────────────────────────────────────────────

def test_global_collection_used_for_upsert():
    """Чанки записываются именно в глобальную коллекцию — collection_id совпадает."""
    conn = MagicMock()
    article = _make_article(1)
    captured_collection_id = []

    def capture_upsert(conn, collection_id, discipline, ga, activity, documents):
        captured_collection_id.append(collection_id)
        return len(documents)

    with patch("src.tools.db_state.get_or_create_global_rag_collection",
               return_value={"id": 99}), \
         patch("src.tools.db_state.get_articles_for_rag_indexing",
               return_value=[article]), \
         patch("src.tools.db_state.delete_rag_documents_by_links"), \
         patch("src.tools.db_state.upsert_rag_documents",
               side_effect=capture_upsert), \
         patch("src.tools.db_state.mark_articles_rag_indexed"), \
         patch("src.pipeline.embedding_filter.get_embedding_model",
               return_value=_fake_model()):

        index_pending_articles(conn)

    assert captured_collection_id == [99]
    # discipline/ga/activity = NULL — глобальная коллекция не привязана к таксономии
