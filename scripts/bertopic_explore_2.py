"""
BERTopic на ПОЛНОМ корпусе из processed_articles (все RSS-источники, без таксономической фильтрации).

Отличия от bertopic_explore.py:
  - Источник: таблица processed_articles (title + RSS-summary), а не rag_documents
  - Эмбеддинги вычисляются на лету (не нужны в БД заранее)
  - Покрывает ВСЕ статьи, а не только прошедшие фильтр по таксономии
  - Дополнительно: темы кластеризуются в N мета-категорий (KMeans на эмбеддингах тем)
    - topics_map_overview.html   — одна карта, цвет = мета-категория, легенда кликабельна
    - topics_map_cat_NN.html     — отдельная карта для каждой мета-категории

Подготовка данных (если processed_articles пустая):
  python3 -m src.main --collect
  # или
  curl -X POST http://localhost:8000/api/rss/collect

Запуск:
  cd /Users/macbookpro/SberAgencyCrawler
  python3 bertopic_explore_2.py

  # Лимит статей (по умолчанию все):
  LIMIT=500 python3 bertopic_explore_2.py

  # Фильтр по источнику:
  SOURCE_FILTER=Atlassian python3 bertopic_explore_2.py

  # Минимальный размер темы (по умолчанию 5):
  MIN_TOPIC_SIZE=10 python3 bertopic_explore_2.py

  # Количество мета-категорий (по умолчанию 8):
  N_CATEGORIES=6 python3 bertopic_explore_2.py
"""
import os
import sys
from collections import Counter
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

# ── настройки ──────────────────────────────────────────────────────────────
LIMIT: Optional[int] = (
    int(os.environ["LIMIT"]) if "LIMIT" in os.environ else None
)
SOURCE_FILTER: Optional[str] = os.environ.get("SOURCE_FILTER")
MIN_TOPIC_SIZE: int = int(os.environ.get("MIN_TOPIC_SIZE", "5"))
N_CATEGORIES: int = int(os.environ.get("N_CATEGORIES", "10"))
OUTPUT_DIR = Path("bertopic_output_2")
# ───────────────────────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


# ── загрузка статей из processed_articles ─────────────────────────────────

def load_docs_from_processed_articles(
    limit: Optional[int] = None,
    source_filter: Optional[str] = None,
) -> Tuple[List[str], List[Dict]]:
    """
    Читает статьи из processed_articles (все RSS, без фильтрации по таксономии).

    Returns:
        docs — список текстов "title. summary"
        meta — список метаданных {link, title, source, published_at}
    """
    try:
        from src.tools.db_state import get_connection
        from config.config import POSTGRES_TABLE_PROCESSED_ARTICLES
    except ImportError as e:
        print(f"  ✗ Ошибка импорта: {e}")
        sys.exit(1)

    conn = get_connection()
    if conn is None:
        print("  ✗ Нет подключения к БД. Проверьте POSTGRES_* в config.")
        sys.exit(1)

    conditions = ["title IS NOT NULL", "summary IS NOT NULL", "summary != ''"]
    params: list = []

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

    if not rows:
        print("  ✗ Таблица processed_articles пуста или нет статей по фильтру.")
        print()
        print("  Сначала загрузите статьи из RSS:")
        print("    python3 -m src.main --collect")
        print("    # или")
        print("    curl -X POST http://localhost:8000/api/rss/collect")
        sys.exit(1)

    docs, meta = [], []
    for row in rows:
        title   = (row.get("title") or "").strip()
        summary = (row.get("summary") or "").strip()
        if not title:
            continue
        docs.append(f"{title}. {summary}" if summary else title)
        meta.append({
            "link":         str(row.get("link") or ""),
            "title":        title,
            "source":       str(row.get("source") or ""),
            "published_at": row.get("published_at"),
        })

    return docs, meta


# ── вычисление эмбеддингов ─────────────────────────────────────────────────

def compute_embeddings(docs: List[str], batch_size: int = 64) -> np.ndarray:
    """
    Вычисляет эмбеддинги через модель из config (sentence-transformers).
    Та же модель, что используется в пайплайне — результаты совместимы.
    """
    from src.pipeline.embedding_filter import get_embedding_model
    from config.config import DEFAULT_EMBED_BATCH_SIZE

    model = get_embedding_model()
    _batch = min(batch_size, DEFAULT_EMBED_BATCH_SIZE)

    print(f"  Модель: {model}")
    print(f"  Батч:   {_batch}, статей: {len(docs)}")

    embeddings = model.encode(
        docs,
        batch_size=_batch,
        normalize_embeddings=True,
        show_progress_bar=True,
    )
    return embeddings.astype("float32")


# ── запуск BERTopic ────────────────────────────────────────────────────────

def run_bertopic(docs: List[str], embeddings: np.ndarray, min_topic_size: int = 5):
    """
    Запускает BERTopic с готовыми эмбеддингами.

    Представление тем: c-TF-IDF (первичный) → KeyBERTInspired (уточнение).
    KeyBERT выбирает слова по семантической близости к центроиду темы,
    что убирает частотный шум ("time", "way", "new" и т.п.).
    """
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
        n_neighbors=n_neighbors,
        n_components=5,
        min_dist=0.0,
        metric="cosine",
        random_state=42,
    )
    hdbscan_model = HDBSCAN(
        min_cluster_size=min_topic_size,
        min_samples=1,
        metric="euclidean",
        cluster_selection_method="eom",
        prediction_data=True,
    )
    # c-TF-IDF: базовый словарь кандидатов (стоп-слова убраны)
    vectorizer = CountVectorizer(
        ngram_range=(1, 2),
        min_df=2,
        max_features=10000,
        stop_words="english",
    )
    # KeyBERT: переранжирует кандидатов по близости к эмбеддингу темы.
    # Требует embedding_model в BERTopic — используем ту же модель что и для статей.
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


# ── вывод результатов ──────────────────────────────────────────────────────

def print_topics(
    topic_model, docs: List[str], topics: List[int], meta: List[Dict]
) -> None:
    info     = topic_model.get_topic_info()
    total    = len(docs)
    noise_df = info[info["Topic"] == -1]
    noise    = int(noise_df["Count"].values[0]) if len(noise_df) else 0
    n_topics = len(info[info["Topic"] >= 0])

    print(f"\n  Статей всего:       {total}")
    print(f"  Распознано тем:     {n_topics}")
    print(f"  Нераспознано (шум): {noise} ({noise / total:.0%})")

    print("\n" + "─" * 76)
    print(f"  {'#':<5} {'Размер':<7} {'Ключевые слова'}")
    print("─" * 76)

    for _, row in info[info["Topic"] >= 0].sort_values("Count", ascending=False).iterrows():
        t_id  = int(row["Topic"])
        count = int(row["Count"])
        words = topic_model.get_topic(t_id)
        kw    = ", ".join(w for w, _ in words[:8])
        print(f"  {t_id:<5} {count:<7} {kw}")

        indices = [i for i, t in enumerate(topics) if t == t_id][:2]
        for idx in indices:
            title  = (meta[idx]["title"] or "")[:68]
            source = meta[idx]["source"]
            print(f"       ↳ [{source}] {title}")

    print("─" * 76)
    print("  Примечание: тема -1 = «шум» (статьи без чёткой принадлежности)")


def print_source_stats(meta: List[Dict]) -> None:
    source_counts = Counter(m["source"] for m in meta)
    print(f"\n  Топ-15 источников:")
    for src, cnt in source_counts.most_common(15):
        print(f"    {cnt:>4}  {src}")
    if len(source_counts) > 15:
        print(f"    ...ещё {len(source_counts) - 15} источников")


# ── категоризация тем ──────────────────────────────────────────────────────

def _get_topic_embeddings(topic_model, valid_ids: List[int]) -> Optional[np.ndarray]:
    """
    Извлекает высокоразмерные эмбеддинги тем из BERTopic.
    Поддерживает dict-формат (новый) и ndarray-формат (старый).
    """
    emb_source = getattr(topic_model, "topic_embeddings_", None)
    if emb_source is None:
        return None
    try:
        if isinstance(emb_source, dict):
            return np.array([emb_source[t] for t in valid_ids], dtype="float32")
        else:
            # ndarray: row 0 = topic -1 (outliers), row i+1 = topic i
            return np.array([emb_source[t + 1] for t in valid_ids], dtype="float32")
    except Exception:
        return None


def save_categorized_topics_maps(topic_model, n_categories: int = 10) -> None:
    """
    Группирует темы BERTopic в n_categories мета-категорий (KMeans на эмбеддингах тем),
    затем сохраняет:
      - topics_map_overview.html       — одна карта, цвет = мета-категория (легенда кликабельна)
      - topics_map_cat_01.html ...     — отдельная карта BERTopic для каждой мета-категории
      - topics_categories.csv          — таблица тема → категория
    """
    import csv

    import plotly.colors as pc
    import plotly.graph_objects as go
    from sklearn.cluster import KMeans
    from umap import UMAP

    OUTPUT_DIR.mkdir(exist_ok=True)

    topic_info = topic_model.get_topic_info()
    valid = topic_info[topic_info["Topic"] >= 0].copy()

    if len(valid) == 0:
        print("  ⚠ Нет тем для категоризации")
        return

    valid_ids  = sorted(valid["Topic"].tolist())
    n_topics   = len(valid_ids)
    n_cat      = min(n_categories, max(2, n_topics // 2))
    counts_map = {int(r["Topic"]): int(r["Count"]) for _, r in valid.iterrows()}

    # ── Эмбеддинги тем ────────────────────────────────────────────────────
    embs = _get_topic_embeddings(topic_model, valid_ids)
    if embs is None or len(embs) == 0:
        print("  ⚠ Не удалось получить эмбеддинги тем — пропускаем категоризацию")
        return

    # Нормализация
    norms = np.linalg.norm(embs, axis=1, keepdims=True)
    embs_norm = embs / np.where(norms == 0, 1.0, norms)

    # ── UMAP 2D для визуализации ───────────────────────────────────────────
    n_neighbors_2d = min(10, max(2, n_topics - 1))
    coords_2d = UMAP(
        n_components=2,
        n_neighbors=n_neighbors_2d,
        min_dist=0.1,
        metric="cosine",
        random_state=42,
    ).fit_transform(embs_norm)

    # ── KMeans ─────────────────────────────────────────────────────────────
    km = KMeans(n_clusters=n_cat, random_state=42, n_init=10)
    cat_labels = km.fit_predict(embs_norm).tolist()

    topic_to_cat: Dict[int, int] = {t: c for t, c in zip(valid_ids, cat_labels)}
    cat_to_topics: Dict[int, List[int]] = {}
    for t, c in topic_to_cat.items():
        cat_to_topics.setdefault(c, []).append(t)

    # Имя категории = топ-3 слова самой крупной темы в ней
    cat_names: Dict[int, str] = {}
    for cat_idx, t_list in cat_to_topics.items():
        top_t = max(t_list, key=lambda t: counts_map.get(t, 0))
        words = topic_model.get_topic(top_t)
        kw = " · ".join(w for w, _ in words[:3])
        cat_names[cat_idx] = f"Кат. {cat_idx + 1}: {kw}"

    # ── Обзорная карта (один scatter per категория) ────────────────────────
    colors = pc.qualitative.Plotly + pc.qualitative.D3 + pc.qualitative.G10

    fig = go.Figure()
    for cat_idx in sorted(cat_to_topics.keys()):
        t_list = cat_to_topics[cat_idx]
        color  = colors[cat_idx % len(colors)]
        xs, ys, sizes, labels, hovers = [], [], [], [], []

        for t in t_list:
            pos  = valid_ids.index(t)
            size = counts_map.get(t, 1)
            words = topic_model.get_topic(t)
            kw_str = ", ".join(w for w, _ in words[:6])

            xs.append(float(coords_2d[pos, 0]))
            ys.append(float(coords_2d[pos, 1]))
            sizes.append(min(90, max(14, size * 0.6)))
            labels.append(f"T{t}")
            hovers.append(f"<b>Тема {t}</b> ({size} статей)<br>{kw_str}")

        fig.add_trace(go.Scatter(
            x=xs, y=ys,
            mode="markers+text",
            name=cat_names[cat_idx],
            text=labels,
            textposition="top center",
            textfont=dict(size=9),
            marker=dict(
                size=sizes,
                color=color,
                opacity=0.85,
                line=dict(width=1, color="white"),
            ),
            hovertext=hovers,
            hoverinfo="text",
        ))

    fig.update_layout(
        title=(
            f"Intertopic Distance Map — {n_topics} тем в {n_cat} категориях"
            "<br><sup>Кликните на категорию в легенде, чтобы скрыть/показать её темы</sup>"
        ),
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False, title=""),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False, title=""),
        height=820,
        legend=dict(
            orientation="v",
            x=1.01,
            y=1,
            bgcolor="rgba(255,255,255,0.85)",
            bordercolor="#ccc",
            borderwidth=1,
        ),
        hovermode="closest",
        plot_bgcolor="white",
        paper_bgcolor="white",
    )

    overview_path = OUTPUT_DIR / "topics_map_overview.html"
    fig.write_html(str(overview_path))
    print(f"  ✓ Обзорная карта:   {overview_path}")

    # ── Отдельные карты per категория ─────────────────────────────────────
    print(f"\n  Карты по категориям:")
    for cat_idx in sorted(cat_to_topics.keys()):
        t_list = cat_to_topics[cat_idx]
        try:
            subfig = topic_model.visualize_topics(topics=t_list)
            cat_label = cat_names[cat_idx]
            fname = f"topics_map_cat_{cat_idx + 1:02d}.html"
            (OUTPUT_DIR / fname).parent.mkdir(parents=True, exist_ok=True)
            subfig.write_html(str(OUTPUT_DIR / fname))
            total_docs = sum(counts_map.get(t, 0) for t in t_list)
            print(f"    ✓ {cat_label[:52]:<52} ({total_docs} ст.) → {fname}")
        except Exception as e:
            print(f"    ⚠ Категория {cat_idx + 1}: {e}")

    # ── CSV категорий ──────────────────────────────────────────────────────
    csv_path = OUTPUT_DIR / "topics_categories.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["category", "category_name", "topic_id", "topic_size", "top_keywords"])
        for cat_idx in sorted(cat_to_topics.keys()):
            for t in sorted(cat_to_topics[cat_idx], key=lambda x: -counts_map.get(x, 0)):
                words = topic_model.get_topic(t)
                kw    = ", ".join(w for w, _ in words[:8])
                writer.writerow([cat_idx + 1, cat_names[cat_idx], t, counts_map.get(t, 0), kw])
    print(f"\n  ✓ Таблица категорий: {csv_path}")


# ── стандартные HTML-отчёты ────────────────────────────────────────────────

def save_html_reports(topic_model, docs: List[str]) -> None:
    OUTPUT_DIR.mkdir(exist_ok=True)

    reports = [
        ("visualize_topics",    {},                                  "topics_map.html",       "Карта тем (все)"),
        ("visualize_hierarchy", {},                                  "topics_hierarchy.html", "Иерархия тем"),
        ("visualize_barchart",  {"top_n_topics": 50, "n_words": 15}, "topics_barchart.html", "Ранги слов"),
        ("visualize_documents", {"docs": docs},                     "docs_map.html",         "Карта статей"),
    ]
    for method, kwargs, filename, label in reports:
        try:
            fig  = getattr(topic_model, method)(**kwargs)
            path = OUTPUT_DIR / filename
            fig.write_html(str(path))
            print(f"  ✓ {label:<22} {path}")
        except Exception as e:
            print(f"  ⚠ {label}: {e}")


def save_csv(topic_model, topics: List[int], meta: List[Dict]) -> None:
    import csv

    info     = topic_model.get_topic_info()
    topic_kw = {
        int(r["Topic"]): ", ".join(w for w, _ in topic_model.get_topic(int(r["Topic"]))[:6])
        for _, r in info[info["Topic"] >= 0].iterrows()
    }

    OUTPUT_DIR.mkdir(exist_ok=True)
    path = OUTPUT_DIR / "articles_topics.csv"
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["topic_id", "topic_keywords", "source", "title", "link", "published_at"],
        )
        writer.writeheader()
        for t_id, m in zip(topics, meta):
            writer.writerow({
                "topic_id":       t_id,
                "topic_keywords": topic_kw.get(t_id, "noise"),
                "source":         m["source"],
                "title":          m["title"],
                "link":           m["link"],
                "published_at":   str(m.get("published_at") or ""),
            })
    print(f"  ✓ Таблица статей:    {path}")


# ── main ───────────────────────────────────────────────────────────────────

def main() -> None:
    print("=" * 76)
    print("  BERTopic v2 — полный корпус из processed_articles")
    parts = []
    if LIMIT:
        parts.append(f"limit={LIMIT}")
    if SOURCE_FILTER:
        parts.append(f"source_filter='{SOURCE_FILTER}'")
    parts.append(f"min_topic_size={MIN_TOPIC_SIZE}")
    parts.append(f"n_categories={N_CATEGORIES}")
    print(f"  Параметры: {' | '.join(parts)}")
    print("=" * 76)

    # ── [1/5] Загрузка статей ─────────────────────────────────────────────
    print("\n[1/5] Загружаем статьи из processed_articles...")
    docs, meta = load_docs_from_processed_articles(
        limit=LIMIT,
        source_filter=SOURCE_FILTER,
    )
    print(f"  ✓ Загружено: {len(docs)} статей")
    print_source_stats(meta)

    if len(docs) < 20:
        print(f"\n  ⚠ Слишком мало статей ({len(docs)}) для BERTopic.")
        print("    Запустите сбор: python3 -m src.main --collect")
        sys.exit(1)

    # ── [2/5] Вычисление эмбеддингов ─────────────────────────────────────
    print(f"\n[2/5] Вычисляем эмбеддинги для {len(docs)} статей...")
    embeddings = compute_embeddings(docs)
    print(f"  ✓ Эмбеддинги: shape={embeddings.shape}")

    # ── [3/5] BERTopic ────────────────────────────────────────────────────
    print(f"\n[3/5] Запускаем BERTopic (min_topic_size={MIN_TOPIC_SIZE})...")
    topic_model, topics, probs = run_bertopic(docs, embeddings, MIN_TOPIC_SIZE)
    print("  ✓ Готово")

    print_topics(topic_model, docs, topics, meta)

    # ── [4/5] Категоризация тем ───────────────────────────────────────────
    print(f"\n[4/5] Кластеризуем темы в {N_CATEGORIES} категорий...")
    save_categorized_topics_maps(topic_model, n_categories=N_CATEGORIES)

    # ── [5/5] Стандартные отчёты ──────────────────────────────────────────
    print(f"\n[5/5] Сохраняем стандартные отчёты в {OUTPUT_DIR}/...")
    save_html_reports(topic_model, docs)
    save_csv(topic_model, topics, meta)

    # ── [6/6] Сохраняем BERTopic-модель ───────────────────────────────────
    print(f"\n[6/6] Сохраняем BERTopic-модель...")
    models_dir = Path("models")
    models_dir.mkdir(exist_ok=True)
    model_path = str(models_dir / "bertopic_model")
    try:
        topic_model.save(model_path)
        print(f"  ✓ Модель сохранена: {model_path}/")
    except Exception as e:
        print(f"  ⚠ Не удалось сохранить модель: {e}")

    print("\n" + "=" * 76)
    print("  Что смотреть:")
    print(f"  • По категориям:  {OUTPUT_DIR}/topics_map_overview.html")
    print(f"  • Категория N:    {OUTPUT_DIR}/topics_map_cat_NN.html")
    print(f"  • Иерархия:       {OUTPUT_DIR}/topics_hierarchy.html")
    print(f"  • Таблица тем:    {OUTPUT_DIR}/topics_categories.csv")
    print(f"  • Модель:         models/bertopic_model/")
    print("=" * 76)


if __name__ == "__main__":
    main()
