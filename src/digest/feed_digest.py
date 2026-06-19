# -*- coding: utf-8 -*-
"""
Дайджест по лентам пользователя — без RAG-коллекций.

Алгоритм:
1. Загружаем статьи из processed_articles по feed_ids и диапазону дат.
2. Формируем ChunkRow-совместимые объекты из title + ai_summary.
3. Генерируем эмбеддинги на лету.
4. Кластеризуем KMeans (та же логика, что и digest_builder).
5. LLM описывает и классифицирует каждый кластер.
6. Раскладываем по 4 разделам дайджеста.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import numpy as np

from config.config import (
    DIGEST_LLM_LANGUAGE,
    DIGEST_MAX_ARTICLES_PER_CLUSTER,
    DIGEST_MAX_ITEMS_PER_SECTION,
    DIGEST_N_CLUSTERS,
    DIGEST_TYPICAL_CHUNKS_PER_CLUSTER,
    EMBEDDING_MODEL_NAME,
)
from src.digest.clustering import ChunkWithCluster, cluster_chunks, get_typical_chunks_for_cluster
from src.digest.describe_and_classify import describe_and_classify_cluster_from_chunks
from src.digest.load_chunks import ChunkRow, parse_embedding, make_summary_text, mix_embeddings
from src.digest.sections import ArticleRef, ClusterInfo, assign_clusters_to_sections
from src.pipeline.embedding_filter import get_embedding_model
from src.tools.db_state import get_articles_by_feed_ids, get_connection
from src.tools.llm_utils import create_gigachat_client

logger = logging.getLogger(__name__)



@dataclass
class FeedDigestOptions:
    from_date: Optional[datetime] = None
    to_date: Optional[datetime] = None
    language: str = DIGEST_LLM_LANGUAGE
    n_clusters: int = DIGEST_N_CLUSTERS
    max_items_per_section: int = DIGEST_MAX_ITEMS_PER_SECTION
    max_articles_per_cluster: int = DIGEST_MAX_ARTICLES_PER_CLUSTER
    typical_chunks_per_cluster: int = DIGEST_TYPICAL_CHUNKS_PER_CLUSTER
    gigachat_credentials: Optional[str] = None
    gigachat_model: Optional[str] = None


@dataclass
class FeedDigestResult:
    title: str
    feed_ids: List[int]
    generated_at: str
    from_date: Optional[str]
    to_date: Optional[str]
    article_count: int
    sections: Dict[str, List[Dict[str, Any]]]


def _rows_to_chunk_rows(rows: list[dict], embeddings) -> List[ChunkRow]:
    """Конвертирует строки из processed_articles в ChunkRow для кластеризации."""
    chunks = []
    for row, emb in zip(rows, embeddings):
        text = row.get("ai_summary") or row.get("summary") or row.get("title") or ""
        chunks.append(
            ChunkRow(
                id=row.get("id", 0),
                collection_id=0,
                link=row.get("link") or "",
                chunk_index=0,
                title=row.get("title") or "",
                summary=row.get("ai_summary") or row.get("summary") or "",
                source=row.get("feed_name") or row.get("source") or "",
                published_at=row.get("published_at"),
                text_payload=text,
                embed_similarity_to_topic=None,
                embedding=emb.tolist(),
            )
        )
    return chunks


def _articles_from_cluster(
    chunk_with_cluster: List[ChunkWithCluster],
    cluster_id: int,
) -> List[ArticleRef]:
    seen: Dict[str, ArticleRef] = {}
    for cwc in chunk_with_cluster:
        if cwc.cluster_id != cluster_id:
            continue
        c = cwc.chunk
        if c.link in seen:
            continue
        seen[c.link] = ArticleRef(link=c.link, title=c.title or c.link, published_at=c.published_at, article_id=c.id)
    return list(seen.values())


def build_digest_by_feeds(
    feed_ids: List[int],
    options: Optional[FeedDigestOptions] = None,
    collection_id: Optional[int] = None,
    user_id: int = 0,
) -> FeedDigestResult:
    """Собирает дайджест по статьям из заданных лент. Если задан collection_id — использует статьи коллекции."""
    if options is None:
        options = FeedDigestOptions()

    # Дефолтный период — последние 7 дней, если не задан
    from_date = options.from_date
    to_date = options.to_date
    if from_date is None and to_date is None and collection_id is None:
        to_date = datetime.utcnow()
        from_date = to_date - timedelta(days=7)

    empty_result = FeedDigestResult(
        title="Дайджест",
        feed_ids=feed_ids,
        generated_at=datetime.utcnow().isoformat() + "Z",
        from_date=from_date.isoformat() if from_date else None,
        to_date=to_date.isoformat() if to_date else None,
        article_count=0,
        sections={"key_trends": [], "methods": [], "tools": [], "case_studies": []},
    )

    conn = get_connection()
    if collection_id is not None:
        from src.tools.db_state import get_articles_for_bertopic_collection
        rows = get_articles_for_bertopic_collection(conn, collection_id, from_date=from_date, to_date=to_date, limit=300)
    else:
        rows = get_articles_by_feed_ids(conn, feed_ids, from_date=from_date, to_date=to_date, limit=300, user_id=user_id)

    if not rows:
        return empty_result

    # Тексты и кэш эмбеддингов из БД
    texts, cached_embeddings = [], []
    for row in rows:
        texts.append(make_summary_text(row.get("title") or "", row.get("ai_summary") or row.get("summary") or ""))
        parsed = parse_embedding(row.get("ai_summary_embedding_str"))
        cached_embeddings.append(np.array(parsed, dtype="float32") if parsed else None)

    # Смешанный режим через общую утилиту
    cached_count = sum(1 for e in cached_embeddings if e is not None)
    print(f"[digest] Эмбеддинги: {cached_count} из кэша, {len(texts) - cached_count} через модель (всего {len(texts)} статей)", flush=True)
    logger.info("Дайджест: эмбеддинги %d из кэша, %d через модель (всего %d статей)", cached_count, len(texts) - cached_count, len(texts))
    model = get_embedding_model(EMBEDDING_MODEL_NAME)
    embeddings = mix_embeddings(
        texts,
        cached_embeddings,
        lambda t: model.encode(t, normalize_embeddings=True, batch_size=32, show_progress_bar=False),
    )

    chunks = _rows_to_chunk_rows(rows, embeddings)

    n_clusters = min(options.n_clusters, len(chunks))
    if n_clusters < 2:
        # Слишком мало статей — один "кластер", без кластеризации
        client = create_gigachat_client(credentials=options.gigachat_credentials, model=options.gigachat_model)
        typical = chunks[:options.typical_chunks_per_cluster]
        llm_out = describe_and_classify_cluster_from_chunks(
            typical, language=options.language, client=client,
            max_snippets=options.typical_chunks_per_cluster,
        )
        articles = [ArticleRef(link=c.link, title=c.title, published_at=c.published_at, article_id=c.id) for c in chunks]
        cluster_info = ClusterInfo(
            cluster_id=0,
            label=llm_out.get("title") or "",
            description=llm_out.get("description") or "",
            primary_type=llm_out.get("primary_type") or "trend",
            articles=articles,
            size=len(chunks),
        )
        sections = assign_clusters_to_sections(
            [cluster_info],
            max_items_per_section=options.max_items_per_section,
            max_articles_per_cluster=options.max_articles_per_cluster,
        )
        return FeedDigestResult(
            title="Дайджест",
            feed_ids=feed_ids,
            generated_at=datetime.utcnow().isoformat() + "Z",
            from_date=from_date.isoformat() if from_date else None,
            to_date=to_date.isoformat() if to_date else None,
            article_count=len(rows),
            sections=sections,
        )

    chunk_with_cluster, centroids = cluster_chunks(chunks, n_clusters=n_clusters)
    if not chunk_with_cluster:
        return empty_result

    cluster_ids = sorted(set(cwc.cluster_id for cwc in chunk_with_cluster))
    client = create_gigachat_client(credentials=options.gigachat_credentials, model=options.gigachat_model)

    cluster_infos: List[ClusterInfo] = []
    for cid in cluster_ids:
        typical = get_typical_chunks_for_cluster(
            chunk_with_cluster, centroids, cid,
            max_chunks=options.typical_chunks_per_cluster,
        )
        llm_out = describe_and_classify_cluster_from_chunks(
            typical,
            language=options.language,
            client=client,
            max_snippets=options.typical_chunks_per_cluster,
        )
        articles = _articles_from_cluster(chunk_with_cluster, cid)
        size = sum(1 for cwc in chunk_with_cluster if cwc.cluster_id == cid)
        cluster_infos.append(
            ClusterInfo(
                cluster_id=cid,
                label=llm_out.get("title") or "",
                description=llm_out.get("description") or "",
                primary_type=llm_out.get("primary_type") or "trend",
                articles=articles,
                size=size,
            )
        )

    sections = assign_clusters_to_sections(
        cluster_infos,
        max_items_per_section=options.max_items_per_section,
        max_articles_per_cluster=options.max_articles_per_cluster,
    )

    return FeedDigestResult(
        title="Дайджест",
        feed_ids=feed_ids,
        generated_at=datetime.utcnow().isoformat() + "Z",
        from_date=from_date.isoformat() if from_date else None,
        to_date=to_date.isoformat() if to_date else None,
        article_count=len(rows),
        sections=sections,
    )
