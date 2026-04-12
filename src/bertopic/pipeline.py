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
        }

    thread = threading.Thread(
        target=_run,
        args=(task_id, min_topic_size, n_categories, skip_rag, source_filter, limit, days_back),
        daemon=True,
    )
    thread.start()
    return task_id


# ── Internal pipeline ──────────────────────────────────────────────────────

def _run(task_id, min_topic_size, n_categories, skip_rag, source_filter, limit, days_back=None):
    _set(task_id, status="running", progress=0.0, message="Инициализация...")

    try:
        model_version = datetime.now().strftime("%Y%m%d")

        # ── [1/6] Загрузка статей ──────────────────────────────────────────
        _set(task_id, progress=0.05, message="Загружаем статьи из БД...")
        docs, meta = _load_articles(limit=limit, source_filter=source_filter, days_back=days_back)

        if len(docs) < 20:
            raise ValueError(
                f"Недостаточно статей: {len(docs)}. Нужно минимум 20 "
                f"(рекомендуется 100+). Запустите сбор RSS."
            )

        _set(task_id, progress=0.1, message=f"Загружено {len(docs)} статей")

        # ── [2/6] Эмбеддинги ──────────────────────────────────────────────
        _set(task_id, progress=0.15, message=f"Вычисляем эмбеддинги ({len(docs)} статей)...")
        embeddings = _compute_embeddings(docs)
        _set(task_id, progress=0.35, message="Эмбеддинги готовы")

        # ── [3/6] BERTopic ────────────────────────────────────────────────
        _set(task_id, progress=0.38, message=f"Запускаем BERTopic (min_topic_size={min_topic_size})...")
        topic_model, topics, probs = _run_bertopic(docs, embeddings, min_topic_size)

        info = topic_model.get_topic_info()
        n_topics = len(info[info["Topic"] >= 0])
        _set(task_id, progress=0.6, message=f"BERTopic завершён: {n_topics} тем")

        # ── [4/6] Сохранение CSV ──────────────────────────────────────────
        _set(task_id, progress=0.62, message="Сохраняем результаты в CSV...")
        topics_data = _save_outputs(topic_model, topics, meta, docs, n_categories)
        _set(task_id, progress=0.7, message=f"CSV сохранены в {OUTPUT_DIR.name}/")

        # ── [5/6] Коллекции в БД ──────────────────────────────────────────
        _set(task_id, progress=0.72, message="Создаём коллекции в БД...")
        n_collections, n_assignments = _load_to_db(
            topic_model, topics, meta, topics_data, model_version
        )
        _set(task_id, progress=0.95, message=f"Создано {n_collections} коллекций, {n_assignments} назначений")

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

def _load_articles(
    limit: Optional[int],
    source_filter: Optional[str],
    days_back: Optional[int] = None,
) -> Tuple[List[str], List[Dict]]:
    from src.tools.db_state import get_connection
    from config.config import POSTGRES_TABLE_PROCESSED_ARTICLES

    conn = get_connection()
    if conn is None:
        raise RuntimeError("Нет подключения к БД")

    conditions = ["title IS NOT NULL", "summary IS NOT NULL", "summary != ''"]
    params: list = []

    if days_back:
        conditions.append("published_at >= NOW() - INTERVAL '1 day' * %s")
        params.append(days_back)

    if source_filter:
        conditions.append("source ILIKE %s")
        params.append(f"%{source_filter}%")

    where = " AND ".join(conditions)
    limit_clause = f"LIMIT {limit}" if limit else ""

    sql = f"""
        SELECT link, title, summary, source, published_at
        FROM {POSTGRES_TABLE_PROCESSED_ARTICLES}
        WHERE {where}
        ORDER BY published_at DESC NULLS LAST
        {limit_clause};
    """

    with conn.cursor() as cur:
        cur.execute(sql, params or None)
        rows = cur.fetchall()
    conn.close()

    docs, meta = [], []
    for row in rows:
        title = (row.get("title") or "").strip()
        summary = (row.get("summary") or "").strip()
        if not title:
            continue
        docs.append(f"{title}. {summary}" if summary else title)
        meta.append({
            "link": str(row.get("link") or ""),
            "title": title,
            "source": str(row.get("source") or ""),
            "published_at": row.get("published_at"),
        })

    return docs, meta


def _compute_embeddings(docs: List[str]) -> np.ndarray:
    from src.pipeline.embedding_filter import get_embedding_model
    from config.config import DEFAULT_EMBED_BATCH_SIZE

    model = get_embedding_model()
    embeddings = model.encode(
        docs,
        batch_size=DEFAULT_EMBED_BATCH_SIZE,
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    return embeddings.astype("float32")


def _run_bertopic(docs: List[str], embeddings: np.ndarray, min_topic_size: int):
    from bertopic import BERTopic
    from bertopic.representation import KeyBERTInspired
    from hdbscan import HDBSCAN
    from sentence_transformers import SentenceTransformer
    from sklearn.feature_extraction.text import CountVectorizer
    from umap import UMAP
    from config.config import EMBEDDING_MODEL_NAME

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
    embedding_model = SentenceTransformer(EMBEDDING_MODEL_NAME)

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
                embs = np.array([emb_source[t + 1] for t in valid_ids], dtype="float32")
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


def _load_to_db(topic_model, topics, meta, topics_data, model_version):
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

    # Удаляем старые коллекции и assignments — каждый запуск создаёт свежие
    n_del_assign = delete_bertopic_assignments(conn)
    n_del_col = delete_bertopic_collections(conn)
    conn.commit()
    if n_del_col or n_del_assign:
        logger.info("Удалено: коллекций=%d, assignments=%d", n_del_col, n_del_assign)

    # GigaChat (опционально)
    client = None
    rate_limiter = None
    if GIGACHAT_SUMMARIZATION_ENABLED:
        try:
            from src.tools.llm_utils import create_gigachat_client
            from src.tools.rate_limiter import RateLimiter
            from config.config import DEFAULT_LLM_SLEEP
            client = create_gigachat_client()
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
        )
        if collection:
            collection_map[t_id] = collection["id"]

    # Assignments
    assignments = [
        {"link": m["link"], "topic_id": t_id, "probability": None}
        for t_id, m in zip(topics, meta)
        if t_id >= 0 and m["link"]
    ]
    n_assignments = upsert_bertopic_assignments(conn, assignments, model_version)

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
