"""
Дайджест по RAG-коллекции: 4 раздела без графа (Фаза 1).

- load_chunks_for_collection: загрузка чанков коллекции из rag_documents
- cluster_chunks: кластеризация эмбеддингов (KMeans)
- describe_and_classify_cluster: LLM — описание и тип (trend/method/tool/case_study)
- build_digest: точка входа — сборка дайджеста с key_trends, methods, tools, case_studies
"""
from src.digest.digest_builder import (
    DigestOptions,
    DigestResult,
    build_digest,
)
from src.digest.load_chunks import (
    ChunkRow,
    load_chunks_for_collection,
)

__all__ = [
    "build_digest",
    "DigestResult",
    "DigestOptions",
    "load_chunks_for_collection",
    "ChunkRow",
]
