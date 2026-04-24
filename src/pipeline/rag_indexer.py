"""
Фоновый воркер RAG-индексации.

Берёт статьи с full_text IS NOT NULL AND rag_indexed_at IS NULL,
чанкирует, считает эмбеддинги батчом, пишет в rag_documents (Global RAG Index).
Запускается автоматически после завершения text_extraction_worker.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def index_pending_articles(conn, batch_size: int = 50) -> dict:
    """
    Основной метод RAG-индексатора.

    1. Получает глобальную коллекцию (создаёт если нет).
    2. Берёт до batch_size статей с full_text IS NOT NULL AND rag_indexed_at IS NULL.
    3. Для каждой статьи: strip_html → chunk_text_recursive → text_payload = title + chunk.
    4. Считает эмбеддинги батчом через SentenceTransformer.
    5. Удаляет старые чанки статьи, записывает новые.
    6. Проставляет rag_indexed_at = NOW().

    Returns:
        {"indexed": int, "chunks_created": int, "failed": int}
    """
    from src.tools.db_state import (
        get_or_create_global_rag_collection,
        get_articles_for_rag_indexing,
        mark_articles_rag_indexed,
        delete_rag_documents_by_links,
        upsert_rag_documents,
    )
    from src.tools.translation import strip_html
    from src.pipeline.chunking import chunk_text_recursive
    from src.pipeline.embedding_filter import get_embedding_model
    from config.config import RAG_CHUNK_MAX_TOKENS, RAG_CHUNK_OVERLAP_TOKENS, DEFAULT_EMBED_BATCH_SIZE

    indexed = 0
    chunks_created = 0
    failed = 0

    collection = get_or_create_global_rag_collection(conn)
    if collection is None:
        logger.error("RAG indexer: не удалось получить/создать глобальную коллекцию.")
        return {"indexed": 0, "chunks_created": 0, "failed": 0}

    collection_id = collection["id"]
    articles = get_articles_for_rag_indexing(conn, limit=batch_size)

    if not articles:
        return {"indexed": 0, "chunks_created": 0, "failed": 0}

    print(f"\n[rag-indexer] Индексируем {len(articles)} статей...", flush=True)

    model = get_embedding_model()
    # Получаем токенайзер из модели — пробуем несколько способов для разных версий sentence_transformers
    tokenizer = None
    try:
        tokenizer = model.tokenizer  # sentence_transformers >= 3.x
    except AttributeError:
        pass
    if tokenizer is None:
        try:
            tokenizer = model[0].tokenizer  # sentence_transformers < 3.x
        except Exception:
            pass
    if tokenizer is None:
        try:
            from transformers import AutoTokenizer
            from config.config import EMBEDDING_MODEL_NAME
            tokenizer = AutoTokenizer.from_pretrained(EMBEDDING_MODEL_NAME)
        except Exception as e:
            logger.warning("Токенайзер для чанкирования недоступен, используем приближение по символам: %s", e)

    # Собираем все чанки батчом — одно обращение к модели на все статьи
    all_docs: list[dict] = []
    article_ids_ok: list[int] = []

    from src.pipeline.chunking import count_tokens

    for article in articles:
        article_id = article["id"]
        link = article["link"]
        title = (article.get("title") or "").strip()
        summary = (article.get("summary") or "").strip()
        source = (article.get("source") or "").strip()
        published_at = article.get("published_at")
        full_text = article.get("full_text") or ""
        summary = article.get("summary") or ""

        try:
            clean = strip_html(full_text) if full_text else ""
            if not clean.strip():
                # full_text пустой или не содержит текста — fallback на summary.
                # Это нормально для источников с пейволом или JS-рендерингом.
                clean = summary.strip()
            if not clean.strip():
                # Нет ни full_text ни summary — пропускаем
                failed += 1
                continue

            # Резервируем место под title в text_payload — чанк + заголовок должны уложиться в лимит модели
            title_tokens = count_tokens(title, tokenizer) + 2  # +2 за "\n\n"
            chunk_max = max(32, RAG_CHUNK_MAX_TOKENS - title_tokens)

            chunks = chunk_text_recursive(
                clean,
                tokenizer=tokenizer,
                max_tokens=chunk_max,
                overlap_tokens=RAG_CHUNK_OVERLAP_TOKENS,
            )
            if not chunks:
                chunks = [clean[:2048]]

            for chunk_index, chunk_text in enumerate(chunks):
                # Логика совпадает с _build_chunk_payload() в rag_prep.py
                text_payload = f"{title}\n\n{chunk_text}" if title and chunk_text else chunk_text or title or " "
                all_docs.append({
                    "link": link,
                    "chunk_index": chunk_index,
                    "title": title,
                    "summary": summary,
                    "source": source,
                    "published_at": published_at,
                    "text_payload": text_payload,
                    "_article_id": article_id,  # временный ключ, не идёт в БД
                })
            article_ids_ok.append(article_id)
        except Exception as e:
            logger.warning("RAG indexer: ошибка при чанкировании article_id=%s: %s", article_id, e)
            failed += 1

    if not all_docs:
        if article_ids_ok:
            mark_articles_rag_indexed(conn, article_ids_ok)
        print(f"[rag-indexer] Нет чанков для индексации.", flush=True)
        return {"indexed": indexed, "chunks_created": chunks_created, "failed": failed}

    # Обрезаем text_payload до точного лимита модели.
    # chunking.py использует приближение 4 символа/токен (калибровка под английский).
    # Для русского BPE-токен ≈ 1–1.5 символа — чанки могут превышать лимит.
    # Truncate tokenizer'ом чтобы model.encode() не выдавал предупреждений.
    if tokenizer is not None:
        for doc in all_docs:
            ids = tokenizer.encode(
                doc["text_payload"],
                add_special_tokens=False,
                truncation=True,
                max_length=RAG_CHUNK_MAX_TOKENS,
            )
            if len(ids) >= RAG_CHUNK_MAX_TOKENS:
                doc["text_payload"] = tokenizer.decode(ids, skip_special_tokens=True)

    # Считаем эмбеддинги одним батчом
    texts = [d["text_payload"] for d in all_docs]
    embeddings = model.encode(
        texts,
        batch_size=DEFAULT_EMBED_BATCH_SIZE,
        show_progress_bar=False,
        normalize_embeddings=True,
    )
    for i, doc in enumerate(all_docs):
        doc["embedding"] = embeddings[i].tolist()

    # Удаляем старые чанки и записываем новые (по статье)
    links_to_replace = list({d["link"] for d in all_docs})
    delete_rag_documents_by_links(conn, collection_id, links_to_replace)

    # Убираем временный ключ перед upsert
    docs_for_upsert = [{k: v for k, v in d.items() if k != "_article_id"} for d in all_docs]

    count = upsert_rag_documents(
        conn,
        collection_id=collection_id,
        discipline=None,
        ga=None,
        activity=None,
        documents=docs_for_upsert,
    )
    chunks_created += count
    indexed += len(article_ids_ok)

    # Помечаем успешно проиндексированные
    if article_ids_ok:
        mark_articles_rag_indexed(conn, article_ids_ok)

    print(
        f"[rag-indexer] Готово: Проиндексировано статей: {indexed} | Чанков создано: {chunks_created} | Ошибок: {failed}",
        flush=True,
    )
    logger.info(
        "RAG worker: завершён. Проиндексировано: %d | Чанков: %d | Ошибок: %d",
        indexed, chunks_created, failed,
    )
    return {"indexed": indexed, "chunks_created": chunks_created, "failed": failed}
