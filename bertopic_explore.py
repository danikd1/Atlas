"""
Шаг 1: BERTopic на статьях из rag_documents.

Что делает:
  - Загружает статьи + готовые эмбеддинги из rag_documents (не считает заново)
  - Запускает BERTopic → находит темы автоматически
  - Печатает темы с ключевыми словами и примерами статей
  - Сохраняет HTML-отчёты (карта тем, иерархия, ранги слов)

Запуск:
  cd /Users/macbookpro/SberAgencyCrawler
  python3 bertopic_explore.py

  # Конкретная коллекция:
  COLLECTION_ID=3 python3 bertopic_explore.py

  # Размер минимальной темы (по умолчанию 3):
  MIN_TOPIC_SIZE=5 python3 bertopic_explore.py
"""
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ── настройки ──────────────────────────────────────────────────────────────
COLLECTION_ID: Optional[int] = (
    int(os.environ["COLLECTION_ID"]) if "COLLECTION_ID" in os.environ else None
)
MIN_TOPIC_SIZE: int = int(os.environ.get("MIN_TOPIC_SIZE", "3"))
OUTPUT_DIR = Path("bertopic_output")
# ───────────────────────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))


# ── загрузка статей + эмбеддингов из БД ───────────────────────────────────

def load_docs_and_embeddings(
    collection_id: Optional[int] = None,
) -> Tuple[List[str], List[str], List[Any], List[Dict]]:
    """
    Возвращает:
      docs       — список текстов "title. summary" (для BERTopic)
      links      — список URL (для отображения примеров)
      embeddings — список векторов float (уже посчитаны в БД)
      meta       — список словарей с метаданными статей
    """
    try:
        from src.tools.db_state import get_connection
        from config.config import POSTGRES_TABLE_RAG_DOCUMENTS, POSTGRES_TABLE_COLLECTIONS
    except ImportError as e:
        print(f"  ✗ Ошибка импорта: {e}")
        sys.exit(1)

    conn = get_connection()
    if conn is None:
        print("  ✗ Нет подключения к БД. Проверьте POSTGRES_* в config.")
        sys.exit(1)

    where = "r.title IS NOT NULL AND r.summary IS NOT NULL AND r.summary != '' AND r.embedding IS NOT NULL"
    params: list = []
    if collection_id is not None:
        where += " AND r.collection_id = %s"
        params.append(collection_id)

    sql = f"""
        SELECT DISTINCT ON (r.link)
            r.link,
            r.title,
            r.summary,
            r.collection_id,
            c.collection_key,
            c.discipline,
            c.ga,
            r.embedding::text AS embedding_str
        FROM {POSTGRES_TABLE_RAG_DOCUMENTS} r
        JOIN {POSTGRES_TABLE_COLLECTIONS} c ON c.id = r.collection_id
        WHERE {where}
        ORDER BY r.link, r.chunk_index;
    """

    with conn.cursor() as cur:
        cur.execute(sql, params or None)
        rows = cur.fetchall()
    conn.close()

    if not rows:
        print("  ✗ В БД нет статей с эмбеддингами.")
        sys.exit(1)

    docs, links, embeddings, meta = [], [], [], []
    for row in rows:
        title   = (row.get("title") or "").strip()
        summary = (row.get("summary") or "").strip()
        emb_str = row.get("embedding_str") or ""

        # Парсим вектор из строки pgvector "[0.1,0.2,...]"
        emb_str = emb_str.strip().lstrip("[").rstrip("]")
        if not emb_str:
            continue
        try:
            vec = [float(x) for x in emb_str.split(",")]
        except ValueError:
            continue

        docs.append(f"{title}. {summary}" if summary else title)
        links.append(str(row.get("link") or ""))
        embeddings.append(vec)
        meta.append({
            "link": str(row.get("link") or ""),
            "title": title,
            "collection_key": row.get("collection_key") or "",
            "discipline": row.get("discipline") or "",
            "ga": row.get("ga") or "",
        })

    return docs, links, embeddings, meta


# ── запуск BERTopic ────────────────────────────────────────────────────────

def run_bertopic(docs, embeddings, min_topic_size: int = 3):
    """
    Запускает BERTopic с готовыми эмбеддингами.
    Возвращает (topic_model, topics, probs).
    """
    import numpy as np
    from bertopic import BERTopic
    from umap import UMAP
    from hdbscan import HDBSCAN
    from sklearn.feature_extraction.text import CountVectorizer

    emb_array = np.array(embeddings, dtype="float32")
    n = len(docs)

    # Параметры UMAP — адаптируем под размер корпуса
    n_neighbors = min(15, max(2, n // 10))
    umap_model = UMAP(
        n_neighbors=n_neighbors,
        n_components=5,
        min_dist=0.0,
        metric="cosine",
        random_state=42,
    )

    # HDBSCAN — мин. размер кластера
    hdbscan_model = HDBSCAN(
        min_cluster_size=min_topic_size,
        min_samples=1,
        metric="euclidean",
        cluster_selection_method="eom",
        prediction_data=True,
    )

    # Векторайзер — поддержка английского и русского, без стоп-слов
    vectorizer = CountVectorizer(
        ngram_range=(1, 2),
        min_df=1,
        stop_words=None,       # BERTopic сам применяет c-TF-IDF
        max_features=5000,
    )

    topic_model = BERTopic(
        umap_model=umap_model,
        hdbscan_model=hdbscan_model,
        vectorizer_model=vectorizer,
        nr_topics="auto",
        top_n_words=10,
        verbose=False,
    )

    # fit_transform с готовыми эмбеддингами — не считаем их заново
    topics, probs = topic_model.fit_transform(docs, embeddings=emb_array)
    return topic_model, topics, probs


# ── вывод результатов ──────────────────────────────────────────────────────

def print_topics(topic_model, docs: List[str], topics: List[int], meta: List[Dict]) -> None:
    info = topic_model.get_topic_info()
    total   = len(docs)
    noise   = int((info[info["Topic"] == -1]["Count"].values or [0])[0])
    n_topics = len(info[info["Topic"] >= 0])

    print(f"\n  Статей всего:       {total}")
    print(f"  Распознано тем:     {n_topics}")
    print(f"  Нераспознано (шум): {noise} ({noise/total:.0%})")

    print("\n" + "─" * 72)
    print(f"  {'#':<4} {'Размер':<7} {'Ключевые слова'}")
    print("─" * 72)

    for _, row in info[info["Topic"] >= 0].sort_values("Count", ascending=False).iterrows():
        t_id   = int(row["Topic"])
        count  = int(row["Count"])
        words  = topic_model.get_topic(t_id)          # [(word, score), ...]
        kw     = ", ".join(w for w, _ in words[:8])
        print(f"  {t_id:<4} {count:<7} {kw}")

        # Примеры статей для этой темы (первые 2)
        indices = [i for i, t in enumerate(topics) if t == t_id][:2]
        for idx in indices:
            title = (meta[idx]["title"] or "")[:70]
            col   = meta[idx]["collection_key"]
            print(f"       ↳ [{col}] {title}")

    print("─" * 72)
    print(f"\n  Примечание: тема -1 = «шум» (статьи без чёткой темы)")


def save_html_reports(topic_model, docs: List[str]) -> None:
    OUTPUT_DIR.mkdir(exist_ok=True)

    try:
        fig = topic_model.visualize_topics()
        path = OUTPUT_DIR / "topics_map.html"
        fig.write_html(str(path))
        print(f"  ✓ Карта тем:      {path}")
    except Exception as e:
        print(f"  ⚠ Карта тем: {e}")

    try:
        fig = topic_model.visualize_hierarchy()
        path = OUTPUT_DIR / "topics_hierarchy.html"
        fig.write_html(str(path))
        print(f"  ✓ Иерархия тем:   {path}")
    except Exception as e:
        print(f"  ⚠ Иерархия: {e}")

    try:
        fig = topic_model.visualize_barchart(top_n_topics=20, n_words=8)
        path = OUTPUT_DIR / "topics_barchart.html"
        fig.write_html(str(path))
        print(f"  ✓ Ранги слов:     {path}")
    except Exception as e:
        print(f"  ⚠ Ранги слов: {e}")

    try:
        fig = topic_model.visualize_documents(docs)
        path = OUTPUT_DIR / "docs_map.html"
        fig.write_html(str(path))
        print(f"  ✓ Карта статей:   {path}")
    except Exception as e:
        print(f"  ⚠ Карта статей: {e}")


def save_csv(topic_model, topics: List[int], meta: List[Dict]) -> None:
    import csv
    info = topic_model.get_topic_info()
    topic_kw = {
        int(r["Topic"]): ", ".join(w for w, _ in topic_model.get_topic(int(r["Topic"]))[:6])
        for _, r in info[info["Topic"] >= 0].iterrows()
    }

    path = OUTPUT_DIR / "articles_topics.csv"
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["topic_id", "topic_keywords", "collection_key", "discipline", "ga", "title", "link"])
        writer.writeheader()
        for i, (t_id, m) in enumerate(zip(topics, meta)):
            writer.writerow({
                "topic_id":       t_id,
                "topic_keywords": topic_kw.get(t_id, "noise"),
                "collection_key": m["collection_key"],
                "discipline":     m["discipline"],
                "ga":             m["ga"],
                "title":          m["title"],
                "link":           m["link"],
            })
    print(f"  ✓ Таблица статей: {path}")


# ── main ───────────────────────────────────────────────────────────────────

def main() -> None:
    print("=" * 72)
    print("  BERTopic — извлечение тем из статей")
    source = f"коллекция #{COLLECTION_ID}" if COLLECTION_ID else "все коллекции"
    print(f"  Источник: {source} | min_topic_size={MIN_TOPIC_SIZE}")
    print("=" * 72)

    # ── [1/3] Загрузка данных ─────────────────────────────────────────────
    print("\n[1/3] Загружаем статьи и эмбеддинги из БД...")
    docs, links, embeddings, meta = load_docs_and_embeddings(COLLECTION_ID)
    print(f"  ✓ Загружено: {len(docs)} статей")

    # Показываем распределение по коллекциям
    from collections import Counter
    col_counts = Counter(m["collection_key"] for m in meta)
    print(f"  Коллекции: {dict(col_counts.most_common(10))}")

    if len(docs) < 10:
        print(f"\n  ⚠ Слишком мало статей ({len(docs)}) для надёжного моделирования.")
        print("    Рекомендуется минимум 30-50 статей. Продолжаем с тем что есть...")

    # ── [2/3] BERTopic ────────────────────────────────────────────────────
    print(f"\n[2/3] Запускаем BERTopic (min_topic_size={MIN_TOPIC_SIZE})...")
    print("  Используем готовые эмбеддинги из БД — не считаем заново")
    topic_model, topics, probs = run_bertopic(docs, embeddings, MIN_TOPIC_SIZE)
    print("  ✓ Готово")

    print_topics(topic_model, docs, topics, meta)

    # ── [3/3] Сохранение отчётов ──────────────────────────────────────────
    print(f"\n[3/3] Сохраняем отчёты в {OUTPUT_DIR}/...")
    save_html_reports(topic_model, docs)
    save_csv(topic_model, topics, meta)

    print("\n" + "=" * 72)
    print("  Следующий шаг:")
    print("  Откройте bertopic_output/topics_hierarchy.html в браузере —")
    print("  это дерево тем, из которого можно собрать таксономию D/GA.")
    print("=" * 72)


if __name__ == "__main__":
    main()
