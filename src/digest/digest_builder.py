"""
Сборка дайджеста по коллекции: загрузка чанков, кластеризация, LLM-описание и раскладка по 4 разделам.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

from config.config import (
    DIGEST_LLM_LANGUAGE,
    DIGEST_MAX_ARTICLES_PER_CLUSTER,
    DIGEST_MAX_ITEMS_PER_SECTION,
    DIGEST_N_CLUSTERS,
    DIGEST_TYPICAL_CHUNKS_PER_CLUSTER,
    POSTGRES_TABLE_COLLECTIONS,
)
from src.digest.clustering import (
    ChunkWithCluster,
    cluster_chunks,
    get_typical_chunks_for_cluster,
)
from src.digest.describe_and_classify import describe_and_classify_cluster_from_chunks
from src.digest.load_chunks import ChunkRow, load_chunks_for_collection
from src.digest.sections import (
    ArticleRef,
    ClusterInfo,
    assign_clusters_to_sections,
)
from src.tools.db_state import get_connection
from src.tools.llm_utils import create_gigachat_client

logger = logging.getLogger(__name__)


@dataclass
class DigestOptions:
    """Опции сборки дайджеста."""
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
class DigestResult:
    """Результат build_digest: структура дайджеста для 4 разделов."""
    title: str
    collection_id: int
    collection_meta: Optional[Dict[str, Any]]
    generated_at: str
    sections: Dict[str, List[Dict[str, Any]]]


def _load_collection_meta(conn, collection_id: int) -> Optional[Dict[str, Any]]:
    """Загружает метаданные коллекции по id."""
    if conn is None:
        return None
    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT id, name, discipline, ga, activity, collection_key,
                   created_at, updated_at, last_refreshed_at
            FROM {POSTGRES_TABLE_COLLECTIONS}
            WHERE id = %s;
            """,
            (collection_id,),
        )
        row = cur.fetchone()
        if not row:
            return None
        return {
            "id": row["id"],
            "name": row.get("name") or "",
            "discipline": row.get("discipline"),
            "ga": row.get("ga"),
            "activity": row.get("activity"),
            "collection_key": row.get("collection_key"),
            "created_at": row.get("created_at"),
            "updated_at": row.get("updated_at"),
            "last_refreshed_at": row.get("last_refreshed_at"),
        }


def _articles_from_cluster_chunks(
    chunk_with_cluster: List[ChunkWithCluster],
    cluster_id: int,
) -> List[ArticleRef]:
    """Уникальные статьи (по link) в кластере; для каждой берём title и published_at из первого чанка."""
    seen: Dict[str, ArticleRef] = {}
    for cwc in chunk_with_cluster:
        if cwc.cluster_id != cluster_id:
            continue
        c = cwc.chunk
        if c.link in seen:
            continue
        seen[c.link] = ArticleRef(link=c.link, title=c.title or c.link, published_at=c.published_at)
    return list(seen.values())


def build_digest(
    collection_id: int,
    options: Optional[DigestOptions] = None,
) -> DigestResult:
    """
    Собирает дайджест по коллекции: 4 раздела без графа.

    1. Загрузка чанков из rag_documents.
    2. Кластеризация (KMeans).
    3. Для каждого кластера: LLM даёт описание и тип (trend/method/tool/case_study).
    4. Раскладка по разделам key_trends, methods, tools, case_studies.

    Returns:
        DigestResult с полем sections: { key_trends, methods, tools, case_studies }.
    """
    if options is None:
        options = DigestOptions()

    conn = get_connection()
    collection_meta = _load_collection_meta(conn, collection_id) if conn else None

    chunks = load_chunks_for_collection(
        conn,
        collection_id,
        from_date=options.from_date,
        to_date=options.to_date,
    )
    if not chunks:
        return DigestResult(
            title="UX Digest",
            collection_id=collection_id,
            collection_meta=collection_meta,
            generated_at=datetime.utcnow().isoformat() + "Z",
            sections={
                "key_trends": [],
                "methods": [],
                "tools": [],
                "case_studies": [],
            },
        )

    chunk_with_cluster, centroids = cluster_chunks(
        chunks,
        n_clusters=options.n_clusters,
    )
    if not chunk_with_cluster:
        return DigestResult(
            title="UX Digest",
            collection_id=collection_id,
            collection_meta=collection_meta,
            generated_at=datetime.utcnow().isoformat() + "Z",
            sections={
                "key_trends": [],
                "methods": [],
                "tools": [],
                "case_studies": [],
            },
        )

    # Уникальные cluster_id
    cluster_ids = sorted(set(cwc.cluster_id for cwc in chunk_with_cluster))
    client = create_gigachat_client(credentials=options.gigachat_credentials, model=options.gigachat_model)

    cluster_infos: List[ClusterInfo] = []
    for cid in cluster_ids:
        typical = get_typical_chunks_for_cluster(
            chunk_with_cluster,
            centroids,
            cid,
            max_chunks=options.typical_chunks_per_cluster,
        )
        llm_out = describe_and_classify_cluster_from_chunks(
            typical,
            language=options.language,
            client=client,
            max_snippets=options.typical_chunks_per_cluster,
        )

        articles = _articles_from_cluster_chunks(chunk_with_cluster, cid)
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

    return DigestResult(
        title="UX Digest",
        collection_id=collection_id,
        collection_meta=collection_meta,
        generated_at=datetime.utcnow().isoformat() + "Z",
        sections=sections,
    )


if __name__ == "__main__":
    """CLI: python -m src.digest.digest_builder <collection_id>"""
    import argparse
    import json

    parser = argparse.ArgumentParser(description="Сборка UX Digest по RAG-коллекции (4 раздела).")
    parser.add_argument("collection_id", type=int, help="ID коллекции")
    parser.add_argument("--json", action="store_true", help="Вывести результат в JSON")
    args = parser.parse_args()

    result = build_digest(args.collection_id)
    if args.json:
        # DigestResult: dataclass -> dict для JSON (datetime в sections нужно сериализовать)
        def _serialize(obj: Any) -> Any:
            if hasattr(obj, "isoformat"):
                return obj.isoformat()
            if isinstance(obj, dict):
                return {k: _serialize(v) for k, v in obj.items()}
            if isinstance(obj, list):
                return [_serialize(x) for x in obj]
            return obj

        out = {
            "title": result.title,
            "collection_id": result.collection_id,
            "collection_meta": result.collection_meta,
            "generated_at": result.generated_at,
            "sections": _serialize(result.sections),
        }
        print(json.dumps(out, ensure_ascii=False, indent=2))
    else:
        print(f"# {result.title}")
        print(f"Collection: {result.collection_meta.get('name', '')} (id={result.collection_id})")
        print(f"Generated: {result.generated_at}\n")
        for section_name, items in result.sections.items():
            print(f"## {section_name}")
            if not items:
                print("  (пока нет пунктов)")
            for i, item in enumerate(items, 1):
                label = item.get("label", "") or item.get("description", "")[:60]
                print(f"  {i}. {label}")
                desc = (item.get("description") or "").strip()
                if desc:
                    for para in desc.split("\n"):
                        print(f"      {para.strip()}")
                for a in item.get("articles", []):
                    print(f"      - {a.get('title', '')} | {a.get('link', '')}")
            print()
