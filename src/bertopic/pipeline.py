"""
BERTopic pipeline, обёрнутый для API.

Запускает полный пайплайн асинхронно в фоновом потоке:
  1. Загрузка статей из processed_articles
  2. Вычисление эмбеддингов
  3. BERTopic кластеризация
  4. Сохранение CSV-файлов
  5. Создание коллекций в БД + assignments

Прогресс доступен через get_task(task_id).
"""

import logging
import sys
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent.parent
OUTPUT_DIR = PROJECT_ROOT / "bertopic_output_2"

# ── In-memory task store ───────────────────────────────────────────────────
# {task_id: {status, progress, message, result, error}}
_tasks: Dict[str, Dict] = {}
_tasks_lock = threading.Lock()


def get_task(task_id: str) -> Optional[Dict]:
    return _tasks.get(task_id)


def list_tasks() -> List[Dict]:
    return [{"task_id": k, **v} for k, v in _tasks.items()]


def _set(task_id: str, **kwargs):
    with _tasks_lock:
        if task_id in _tasks:
            _tasks[task_id].update(kwargs)


# ── Public API ─────────────────────────────────────────────────────────────

def run_async(
    min_topic_size: int = 5,
    n_categories: int = 10,
    skip_rag: bool = True,
    source_filter: Optional[str] = None,
    limit: Optional[int] = None,
    days_back: Optional[int] = None,
    user_id: Optional[int] = None,
    gigachat_credentials: Optional[str] = None,
    gigachat_model: Optional[str] = None,
) -> str:
    """Запускает пайплайн в фоновом потоке. Возвращает task_id."""
    task_id = str(uuid.uuid4())
    with _tasks_lock:
        _tasks[task_id] = {
            "status": "pending",
            "progress": 0.0,
            "message": "В очереди",
            "result": None,
            "error": None,
            "started_at": datetime.now().isoformat(),
            "gigachat_credentials": gigachat_credentials,
            "gigachat_model": gigachat_model,
        }

    thread = threading.Thread(
        target=_run,
        args=(task_id, min_topic_size, n_categories, skip_rag, source_filter, limit, days_back, user_id, gigachat_credentials, gigachat_model),
        daemon=True,
    )
    thread.start()
    return task_id


# ── Internal pipeline ──────────────────────────────────────────────────────

MAX_ARTICLES_BERTOPIC = 5000  # UMAP квадратично растёт — выше 5k часы на CPU

def _run(task_id, min_topic_size, n_categories, skip_rag, source_filter, limit, days_back=None, user_id=None, gigachat_credentials=None, gigachat_model=None):
    _set(task_id, status="running", progress=0.0, message="Подготовка...")

    try:
        model_version = datetime.now().strftime("%Y%m%d")

        # Защитный потолок: UMAP при >5k статей может считать часами на CPU
        effective_limit = min(limit, MAX_ARTICLES_BERTOPIC) if limit else MAX_ARTICLES_BERTOPIC

        # ── [1/6] Загрузка статей ──────────────────────────────────────────
        _set(task_id, progress=0.05, message="Загружаем статьи...")
        docs, meta, cached_embeddings = _load_articles(limit=effective_limit, source_filter=source_filter, days_back=days_back, user_id=user_id)

        if len(docs) < 2:
            raise ValueError(
                f"Недостаточно статей: {len(docs)}. Запустите сбор RSS."
            )

        _set(task_id, progress=0.1, message=f"Загружено {len(docs)} статей")

        # ── [2/6] Эмбеддинги ──────────────────────────────────────────────
        cached_count = sum(1 for e in cached_embeddings if e is not None)
        fresh_count = len(docs) - cached_count
        _set(task_id, progress=0.15, message=f"Анализируем: {cached_count} уже готовы, {fresh_count} обрабатываем впервые")
        logger.info("Эмбеддинги: %d из кэша, %d через модель (всего %d)", cached_count, fresh_count, len(docs))
        embeddings = _compute_embeddings(docs, cached_embeddings)

        # ── [3/6] BERTopic ────────────────────────────────────────────────
        _set(task_id, progress=0.38, message="Ищем темы...")
        logger.info("Запускаем BERTopic (min_topic_size=%d)...", min_topic_size)
        topic_model, topics, probs = _run_bertopic(docs, embeddings, min_topic_size)

        info = topic_model.get_topic_info()
        n_topics = len(info[info["Topic"] >= 0])
        _set(task_id, progress=0.6, message=f"Найдено {n_topics} тем")
        logger.info("BERTopic завершён: %d тем", n_topics)

        # ── [4/6] Сохранение CSV ──────────────────────────────────────────
        logger.info("Сохраняем результаты в CSV...")
        topics_data = _save_outputs(topic_model, topics, meta, docs, n_categories)
        logger.info("CSV сохранены в %s/", OUTPUT_DIR.name)

        # ── [5/6] Коллекции в БД ──────────────────────────────────────────
        _set(task_id, progress=0.72, message="Формируем карту...")
        logger.info("Создаём коллекции в БД...")
        n_collections, n_assignments = _load_to_db(
            topic_model, topics, meta, topics_data, model_version, owner_id=user_id,
            gigachat_credentials=gigachat_credentials, gigachat_model=gigachat_model,
        )
        _set(task_id, progress=0.95, message="Почти готово...")
        logger.info("Создано %d коллекций, %d назначений", n_collections, n_assignments)

        # ── [6/6] Готово ──────────────────────────────────────────────────
        _set(
            task_id,
            status="done",
            progress=1.0,
            message="Готово",
            result={
                "n_topics": n_topics,
                "n_articles": len(docs),
                "n_collections": n_collections,
                "n_assignments": n_assignments,
                "model_version": model_version,
            },
        )
        logger.info("BERTopic pipeline done: %d topics, %d articles", n_topics, len(docs))

    except Exception as e:
        logger.exception("BERTopic pipeline error: %s", e)
        _set(task_id, status="error", progress=0.0, message=str(e), error=str(e))


# ── Step functions ─────────────────────────────────────────────────────────

def _to_embedding(value) -> Optional[np.ndarray]:
    """Конвертирует pgvector значение из БД в numpy array. Переиспользует parse_embedding из load_chunks."""
    from src.digest.load_chunks import parse_embedding
    parsed = parse_embedding(value)
    if parsed is None:
        return None
    return np.array(parsed, dtype="float32")


def _load_articles(
    limit: Optional[int],
    source_filter: Optional[str],
    days_back: Optional[int] = None,
    user_id: Optional[int] = None,
) -> Tuple[List[str], List[Dict], List[Optional[np.ndarray]]]:
    from src.tools.db_state import get_connection
    from src.digest.load_chunks import make_summary_text
    from config.config import POSTGRES_TABLE_PROCESSED_ARTICLES

    conn = get_connection()
    if conn is None:
        raise RuntimeError("Нет подключения к БД")

    conditions = [
        "pa.title IS NOT NULL",
        "((pa.ai_summary IS NOT NULL AND pa.ai_summary != '') OR (pa.summary IS NOT NULL AND pa.summary != ''))",
    ]
    params: list = []

    if days_back:
        conditions.append("pa.published_at >= NOW() - INTERVAL '1 day' * %s")
        params.append(days_back)

    if source_filter:
        conditions.append("pa.source ILIKE %s")
        params.append(f"%{source_filter}%")

    if user_id is not None:
        conditions.append("pa.feed_id IN (SELECT feed_id FROM user_feeds WHERE user_id = %s)")
        params.append(user_id)

    where = " AND ".join(conditions)
    limit_clause = f"LIMIT {limit}" if limit else ""

    sql = f"""
        SELECT pa.link, pa.title, pa.ai_summary, pa.summary, pa.source, pa.published_at,
               pa.ai_summary_embedding::text AS ai_summary_embedding_str
        FROM {POSTGRES_TABLE_PROCESSED_ARTICLES} pa
        WHERE {where}
        ORDER BY pa.published_at DESC NULLS LAST
        {limit_clause};
    """

    with conn.cursor() as cur:
        cur.execute(sql, params or None)
        rows = cur.fetchall()
    conn.close()

    docs, meta, cached_embeddings = [], [], []
    for row in rows:
        title = (row.get("title") or "").strip()
        body = (row.get("ai_summary") or row.get("summary") or "").strip()
        if not title:
            continue
        docs.append(make_summary_text(title, body))
        meta.append({
            "link": str(row.get("link") or ""),
            "title": title,
            "source": str(row.get("source") or ""),
            "published_at": row.get("published_at"),
        })
        cached_embeddings.append(_to_embedding(row.get("ai_summary_embedding_str")))

    return docs, meta, cached_embeddings


def _compute_embeddings(docs: List[str], cached: Optional[List[Optional[np.ndarray]]] = None) -> np.ndarray:
    from src.pipeline.embedding_filter import get_embedding_model
    from src.digest.load_chunks import mix_embeddings
    from config.config import DEFAULT_EMBED_BATCH_SIZE

    model = get_embedding_model()

    def encode_fn(texts):
        return model.encode(texts, batch_size=DEFAULT_EMBED_BATCH_SIZE, normalize_embeddings=True, show_progress_bar=False).astype("float32")

    if cached is None:
        cached = [None] * len(docs)

    cached_count = sum(1 for e in cached if e is not None)
    logger.info("Эмбеддинги: %d из кэша, %d через модель", cached_count, len(docs) - cached_count)

    return mix_embeddings(docs, cached, encode_fn)


def _run_bertopic(docs: List[str], embeddings: np.ndarray, min_topic_size: int):
    from bertopic import BERTopic
    from bertopic.representation import KeyBERTInspired
    from hdbscan import HDBSCAN
    from sklearn.feature_extraction.text import CountVectorizer
    from umap import UMAP
    from config.config import EMBEDDING_MODEL_NAME
    from src.pipeline.embedding_filter import get_embedding_model

    n = len(docs)
    n_neighbors = min(15, max(2, n // 10))

    umap_model = UMAP(
        n_neighbors=n_neighbors, n_components=5,
        min_dist=0.0, metric="cosine", random_state=42,
    )
    hdbscan_model = HDBSCAN(
        min_cluster_size=min_topic_size, min_samples=1,
        metric="euclidean", cluster_selection_method="eom",
        prediction_data=True,
    )
    vectorizer = CountVectorizer(
        ngram_range=(1, 2), min_df=2,
        max_features=10000, stop_words="english",
    )
    representation_model = KeyBERTInspired()
    embedding_model = get_embedding_model(EMBEDDING_MODEL_NAME)  # берём из кэша, не грузим повторно

    topic_model = BERTopic(
        embedding_model=embedding_model,
        umap_model=umap_model,
        hdbscan_model=hdbscan_model,
        vectorizer_model=vectorizer,
        representation_model=representation_model,
        nr_topics="auto",
        top_n_words=15,
        verbose=False,
    )

    topics, probs = topic_model.fit_transform(docs, embeddings=embeddings)
    return topic_model, topics, probs


def _save_outputs(topic_model, topics, meta, docs, n_categories):
    """Сохраняет CSV файлы и возвращает словарь topic_id → {keywords, size}."""
    import csv
    from sklearn.cluster import KMeans
    from umap import UMAP

    OUTPUT_DIR.mkdir(exist_ok=True)

    info = topic_model.get_topic_info()
    valid = info[info["Topic"] >= 0].copy()
    valid_ids = sorted(valid["Topic"].tolist())
    counts_map = {int(r["Topic"]): int(r["Count"]) for _, r in valid.iterrows()}

    # keywords per topic
    topics_data: Dict[int, Dict] = {}
    for t_id in valid_ids:
        words = topic_model.get_topic(t_id)
        kw = ", ".join(w for w, _ in words[:8])
        topics_data[t_id] = {
            "keywords": kw,
            "size": counts_map.get(t_id, 0),
        }

    # articles_topics.csv
    topic_kw = {t: d["keywords"] for t, d in topics_data.items()}
    articles_path = OUTPUT_DIR / "articles_topics.csv"
    with open(articles_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["topic_id", "topic_keywords", "source", "title", "link", "published_at"])
        writer.writeheader()
        for t_id, m in zip(topics, meta):
            writer.writerow({
                "topic_id": t_id,
                "topic_keywords": topic_kw.get(t_id, "noise"),
                "source": m["source"],
                "title": m["title"],
                "link": m["link"],
                "published_at": str(m.get("published_at") or ""),
            })

    # topics_categories.csv — KMeans категоризация
    n_cat = min(n_categories, max(2, len(valid_ids) // 2))
    emb_source = getattr(topic_model, "topic_embeddings_", None)
    cat_labels = [0] * len(valid_ids)

    if emb_source is not None and len(valid_ids) >= n_cat:
        try:
            if isinstance(emb_source, dict):
                embs = np.array([emb_source[t] for t in valid_ids], dtype="float32")
            else:
                # topic_embeddings_ может иметь n_topics или n_topics+1 элементов
                # (в зависимости от версии BERTopic: с outlier-вектором или без)
                offset = 1 if len(emb_source) > max(valid_ids) + 1 else 0
                embs = np.array([emb_source[t + offset] for t in valid_ids], dtype="float32")
            norms = np.linalg.norm(embs, axis=1, keepdims=True)
            embs_norm = embs / np.where(norms == 0, 1.0, norms)
            km = KMeans(n_clusters=n_cat, random_state=42, n_init=10)
            cat_labels = km.fit_predict(embs_norm).tolist()
        except Exception as e:
            logger.warning("KMeans категоризация не удалась: %s", e)

    cat_path = OUTPUT_DIR / "topics_categories.csv"
    with open(cat_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["category", "category_name", "topic_id", "topic_size", "top_keywords"])
        for t_id, cat in zip(valid_ids, cat_labels):
            writer.writerow([
                cat + 1,
                f"Категория {cat + 1}",
                t_id,
                counts_map.get(t_id, 0),
                topics_data[t_id]["keywords"],
            ])

    return topics_data


def _load_to_db(topic_model, topics, meta, topics_data, model_version, owner_id=None, gigachat_credentials=None, gigachat_model=None):
    """Создаёт коллекции и записывает assignments в БД."""
    from src.tools.db_state import (
        get_connection,
        ensure_tables,
        delete_bertopic_collections,
        delete_bertopic_assignments,
        create_bertopic_collection,
        upsert_bertopic_assignments,
    )
    from config.config import GIGACHAT_SUMMARIZATION_ENABLED

    conn = get_connection()
    if conn is None:
        raise RuntimeError("Нет подключения к БД для записи результатов")

    ensure_tables(conn)

    # Удаляем старые коллекции и assignments пользователя — каждый запуск создаёт свежие
    n_del_assign = delete_bertopic_assignments(conn, owner_id=owner_id)
    n_del_col = delete_bertopic_collections(conn, owner_id=owner_id)
    conn.commit()
    if n_del_col or n_del_assign:
        logger.info("Удалено: коллекций=%d, assignments=%d", n_del_col, n_del_assign)

    # GigaChat (опционально)
    client = None
    rate_limiter = None
    if gigachat_credentials:
        try:
            from src.tools.llm_utils import create_gigachat_client
            from src.tools.rate_limiter import RateLimiter
            from config.config import DEFAULT_LLM_SLEEP
            client = create_gigachat_client(credentials=gigachat_credentials, model=gigachat_model)
            rate_limiter = RateLimiter(delay_seconds=DEFAULT_LLM_SLEEP)
        except Exception as e:
            logger.warning("GigaChat недоступен: %s", e)

    # Собираем примеры заголовков per topic
    from collections import defaultdict
    topic_titles: Dict[int, List[str]] = defaultdict(list)
    for t_id, m in zip(topics, meta):
        if t_id >= 0:
            topic_titles[t_id].append(m["title"])

    collection_map: Dict[int, int] = {}

    for t_id, data in topics_data.items():
        keywords = data["keywords"]
        sample_titles = topic_titles.get(t_id, [])[:5]

        # Название и описание темы
        topic_name = _generate_name(t_id, keywords, sample_titles, client, rate_limiter)
        topic_description = _generate_description(t_id, keywords, sample_titles, client, rate_limiter)

        collection = create_bertopic_collection(
            conn=conn,
            topic_id=t_id,
            topic_name=topic_name,
            model_version=model_version,
            description=topic_description,
            keywords=keywords,
            owner_id=owner_id,
        )
        if collection:
            collection_map[t_id] = collection["id"]

    # Assignments
    assignments = [
        {"link": m["link"], "topic_id": t_id, "probability": None}
        for t_id, m in zip(topics, meta)
        if t_id >= 0 and m["link"]
    ]
    n_assignments = upsert_bertopic_assignments(conn, assignments, model_version, owner_id=owner_id)

    conn.commit()
    conn.close()

    return len(collection_map), n_assignments


def _generate_description(topic_id, keywords, sample_titles, client, rate_limiter) -> str:
    """Генерирует краткое описание темы через GigaChat или возвращает fallback."""
    if client is None:
        return keywords

    if rate_limiter:
        rate_limiter.wait_if_needed()

    try:
        titles_block = "\n".join(f"- {t}" for t in sample_titles)
        result = client.chat({
            "messages": [
                {"role": "system", "content": "Ты помогаешь описывать тематические кластеры статей."},
                {"role": "user", "content": (
                    f"Ключевые слова кластера: {keywords}\n"
                    f"Примеры заголовков статей:\n{titles_block}\n\n"
                    "Напиши 1-2 предложения на русском: о чём этот кластер, какой круг тем он охватывает. "
                    "Только описание, без вводных слов и заголовков."
                )},
            ],
            "temperature": 0.3,
        })
        desc = result.choices[0].message.content.strip()
        return desc if desc else keywords
    except Exception as e:
        logger.warning("GigaChat описание для темы %d: %s", topic_id, e)
        return keywords


def _generate_name(topic_id, keywords, sample_titles, client, rate_limiter) -> str:
    """Генерирует название темы через GigaChat или возвращает fallback."""
    kw_list = [k.strip() for k in keywords.split(",") if k.strip()]
    fallback = kw_list[0].title() if kw_list else f"Тема {topic_id}"

    if client is None:
        return fallback

    if rate_limiter:
        rate_limiter.wait_if_needed()

    try:
        titles_block = "\n".join(f"- {t}" for t in sample_titles)
        result = client.chat({
            "messages": [
                {"role": "system", "content": "Придумай краткое название для тематического кластера статей."},
                {"role": "user", "content": (
                    f"Ключевые слова: {keywords}\n"
                    f"Примеры заголовков:\n{titles_block}\n\n"
                    "Краткое название (не более 8 слов) на русском. Только название."
                )},
            ],
            "temperature": 0.2,
        })
        name = result.choices[0].message.content.strip()
        return name if name else fallback
    except Exception as e:
        logger.warning("GigaChat для темы %d: %s", topic_id, e)
        return fallback
