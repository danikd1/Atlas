"""
Тесты компонента Дайджест.

Покрывает: cluster_chunks, get_typical_chunks_for_cluster,
           _articles_from_cluster_chunks, assign_clusters_to_sections.
Запуск: python3 -m pytest tests/test_digest.py -v
"""
import numpy as np
import pytest

from src.digest.clustering import ChunkWithCluster, cluster_chunks, get_typical_chunks_for_cluster
from src.digest.digest_builder import _articles_from_cluster_chunks
from src.digest.load_chunks import ChunkRow
from src.digest.sections import ArticleRef, ClusterInfo, assign_clusters_to_sections


# ── Вспомогательные фабрики ───────────────────────────────────────────────────

def _make_chunk_row(
    link="https://example.com/article",
    title="Заголовок",
    embedding=None,
    chunk_index=0,
):
    if embedding is None:
        embedding = [0.1, 0.2, 0.3]
    return ChunkRow(
        id=1,
        collection_id=1,
        link=link,
        chunk_index=chunk_index,
        title=title,
        summary="",
        source="example.com",
        published_at=None,
        text_payload="Текст чанка",
        embed_similarity_to_topic=None,
        embedding=embedding,
    )


def _make_cwc(link="https://example.com/article", cluster_id=0, embedding=None):
    return ChunkWithCluster(
        chunk=_make_chunk_row(link=link, embedding=embedding),
        cluster_id=cluster_id,
    )


def _make_cluster_info(
    cluster_id=0,
    primary_type="trend",
    size=1,
    articles=None,
    label="Тренд",
):
    if articles is None:
        articles = [ArticleRef(link=f"https://example.com/{cluster_id}", title="Статья")]
    return ClusterInfo(
        cluster_id=cluster_id,
        label=label,
        description="Описание кластера",
        primary_type=primary_type,
        articles=articles,
        size=size,
    )


# ── cluster_chunks ─────────────────────────────────────────────────────────────

def test_cluster_chunks_empty_returns_empty():
    """Пустой список чанков → пустой результат без падения."""
    result, centroids = cluster_chunks([])
    assert result == []
    assert centroids.size == 0


def test_cluster_chunks_all_get_cluster_id():
    """Все чанки с эмбеддингами получают cluster_id."""
    chunks = [
        _make_chunk_row(embedding=[float(i), float(i), float(i)])
        for i in range(5)
    ]
    result, _ = cluster_chunks(chunks, n_clusters=2)
    assert len(result) == 5
    for cwc in result:
        assert isinstance(cwc.cluster_id, int)


def test_cluster_chunks_k_reduced_when_few_chunks():
    """Чанков меньше чем n_clusters → K уменьшается (нет исключения)."""
    chunks = [
        _make_chunk_row(link=f"https://example.com/{i}", embedding=[float(i), 0.0])
        for i in range(2)
    ]
    # n_clusters=10, но чанков только 2 → k=2, без ошибки
    result, centroids = cluster_chunks(chunks, n_clusters=10)
    assert len(result) == 2
    assert centroids.shape[0] == 2


def test_cluster_chunks_no_valid_embeddings_returns_empty():
    """Чанки без эмбеддингов → пустой результат."""
    chunks = [_make_chunk_row(embedding=None) for _ in range(3)]
    for c in chunks:
        c.embedding = None
    result, centroids = cluster_chunks(chunks)
    assert result == []


# ── get_typical_chunks_for_cluster ────────────────────────────────────────────

def test_get_typical_chunks_respects_max_chunks():
    """Возвращает не больше max_chunks чанков из кластера."""
    cwcs = [
        _make_cwc(link=f"https://example.com/{i}", cluster_id=0, embedding=[float(i), 0.0])
        for i in range(10)
    ]
    _, centroids = cluster_chunks([cwc.chunk for cwc in cwcs], n_clusters=1)
    result = get_typical_chunks_for_cluster(cwcs, centroids, cluster_id=0, max_chunks=3)
    assert len(result) <= 3


def test_get_typical_chunks_empty_cluster_returns_empty():
    """Если в кластере нет чанков — возвращает пустой список."""
    cwcs = [_make_cwc(cluster_id=1)]
    centroids = np.array([[0.1, 0.2], [0.3, 0.4]])
    result = get_typical_chunks_for_cluster(cwcs, centroids, cluster_id=0, max_chunks=5)
    assert result == []


# ── _articles_from_cluster_chunks ─────────────────────────────────────────────

def test_articles_deduped_by_link_within_cluster():
    """Два чанка с одним link → одна статья в результате."""
    cwcs = [
        _make_cwc(link="https://example.com/article", cluster_id=0),
        _make_cwc(link="https://example.com/article", cluster_id=0),
    ]
    result = _articles_from_cluster_chunks(cwcs, cluster_id=0)
    assert len(result) == 1
    assert result[0].link == "https://example.com/article"


def test_articles_excludes_other_clusters():
    """Статьи из другого кластера не попадают в результат."""
    cwcs = [
        _make_cwc(link="https://example.com/a0", cluster_id=0),
        _make_cwc(link="https://example.com/a1", cluster_id=1),
    ]
    result = _articles_from_cluster_chunks(cwcs, cluster_id=0)
    links = [a.link for a in result]
    assert "https://example.com/a0" in links
    assert "https://example.com/a1" not in links


# ── assign_clusters_to_sections ───────────────────────────────────────────────

def test_assign_trend_to_key_trends():
    """Кластер с primary_type='trend' попадает в раздел key_trends."""
    infos = [_make_cluster_info(cluster_id=0, primary_type="trend")]
    out = assign_clusters_to_sections(infos)
    assert len(out["key_trends"]) == 1
    assert len(out["methods"]) == 0


def test_assign_unknown_type_falls_back_to_key_trends():
    """Неизвестный primary_type → fallback в key_trends."""
    infos = [_make_cluster_info(cluster_id=0, primary_type="something_unknown")]
    out = assign_clusters_to_sections(infos)
    assert len(out["key_trends"]) == 1


def test_assign_sorted_by_size_desc():
    """В разделе кластеры отсортированы по size (больший — первый)."""
    infos = [
        _make_cluster_info(cluster_id=0, primary_type="tool", size=3,
                           articles=[ArticleRef(link="https://a.com/1", title="A")]),
        _make_cluster_info(cluster_id=1, primary_type="tool", size=7,
                           articles=[ArticleRef(link="https://a.com/2", title="B")]),
    ]
    out = assign_clusters_to_sections(infos)
    sizes_in_tools = [item["articles"][0]["link"] for item in out["tools"]]
    # Кластер с size=7 (link https://a.com/2) должен быть первым
    assert sizes_in_tools[0] == "https://a.com/2"


def test_assign_deduplicates_articles_within_section():
    """Одна и та же статья не повторяется дважды в одном разделе."""
    shared_link = "https://example.com/shared"
    infos = [
        _make_cluster_info(cluster_id=0, primary_type="method", size=2,
                           articles=[ArticleRef(link=shared_link, title="Статья")]),
        _make_cluster_info(cluster_id=1, primary_type="method", size=1,
                           articles=[ArticleRef(link=shared_link, title="Статья")]),
    ]
    out = assign_clusters_to_sections(infos)
    all_links = [a["link"] for item in out["methods"] for a in item["articles"]]
    assert all_links.count(shared_link) == 1


def test_assign_respects_max_items_per_section():
    """Не более max_items_per_section кластеров в одном разделе."""
    infos = [
        _make_cluster_info(cluster_id=i, primary_type="case_study", size=i,
                           articles=[ArticleRef(link=f"https://a.com/{i}", title=f"A{i}")])
        for i in range(5)
    ]
    out = assign_clusters_to_sections(infos, max_items_per_section=2)
    assert len(out["case_studies"]) <= 2
