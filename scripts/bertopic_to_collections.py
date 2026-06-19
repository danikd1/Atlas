"""
Фаза 0: Загрузка результатов BERTopic в PostgreSQL.

Читает:
  bertopic_output_2/topics_categories.csv  — одна тема → одна коллекция
  bertopic_output_2/articles_topics.csv    — статья → topic_id

Записывает:
  collections           — одна запись на тему (collection_key = "bertopic_topic_{id}")
  bertopic_assignments  — статья → topic_id
  rag_documents         — чанки для RAG по каждой теме

Запуск:
  python3 bertopic_to_collections.py

  # Только коллекции + assignments, без RAG-чанков (быстрая проверка):
  SKIP_RAG=1 python3 bertopic_to_collections.py
"""
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# ── Настройки ──────────────────────────────────────────────────────────────
OUTPUT_DIR = Path("bertopic_output_2")
TOPICS_CSV = OUTPUT_DIR / "topics_categories.csv"
ARTICLES_CSV = OUTPUT_DIR / "articles_topics.csv"
MODEL_VERSION: str = datetime.now().strftime("%Y%m%d")
SKIP_RAG: bool = os.environ.get("SKIP_RAG", "0").strip() == "1"
# Число статей-примеров, передаваемых GigaChat для генерации описания темы
TOPIC_DESCRIPTION_SAMPLE_SIZE: int = 5
# ───────────────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


# ── [1] Загрузка CSV ───────────────────────────────────────────────────────

def load_csvs() -> tuple:
    """
    Загружает topics_categories.csv и articles_topics.csv.
    Завершает скрипт если файлы не найдены.
    """
    for path in (TOPICS_CSV, ARTICLES_CSV):
        if not path.exists():
            logger.error(
                "Файл не найден: %s\n  Запустите сначала: python3 bertopic_explore_2.py",
                path,
            )
            sys.exit(1)

    df_topics = pd.read_csv(TOPICS_CSV)
    df_articles = pd.read_csv(ARTICLES_CSV)
    logger.info("Загружено тем: %d, статей: %d", len(df_topics), len(df_articles))
    return df_topics, df_articles


# ── [2] Описание темы через GigaChat ──────────────────────────────────────

def generate_topic_description(
    topic_id: int,
    keywords: str,
    sample_titles: List[str],
    client,
    rate_limiter,
) -> str:
    """
    Генерирует краткое название темы через GigaChat.
    Fallback: первое ключевое слово из keywords (если GigaChat отключён или недоступен).
    """
    from config.config import GIGACHAT_SUMMARIZATION_ENABLED

    # Fallback — первое ключевое слово, title-case
    kw_list = [k.strip() for k in (keywords or "").split(",") if k.strip()]
    fallback = kw_list[0].title() if kw_list else f"Topic {topic_id}"

    if not GIGACHAT_SUMMARIZATION_ENABLED or client is None:
        return fallback

    titles_block = "\n".join(f"- {t}" for t in sample_titles[:TOPIC_DESCRIPTION_SAMPLE_SIZE])
    user_content = (
        f"Тема {topic_id}.\n"
        f"Ключевые слова: {keywords}\n"
        f"Примеры заголовков статей:\n{titles_block}\n\n"
        "Напиши краткое название темы (не более 10 слов) на русском языке. "
        "Только название, без пояснений."
    )

    if rate_limiter:
        rate_limiter.wait_if_needed()

    try:
        result = client.chat({
            "messages": [
                {
                    "role": "system",
                    "content": "Ты помощник, который придумывает краткие названия для тематических кластеров статей.",
                },
                {"role": "user", "content": user_content},
            ],
            "temperature": 0.2,
        })
        name = result.choices[0].message.content.strip()
        return name if name else fallback
    except Exception as e:
        logger.warning("GigaChat для темы %d: %s — используем fallback.", topic_id, e)
        return fallback


def generate_topic_long_description(
    topic_id: int,
    keywords: str,
    sample_titles: List[str],
    client,
    rate_limiter,
) -> Optional[str]:
    """
    Генерирует 1-2 предложения описания темы через GigaChat.
    Fallback: строка с ключевыми словами.
    """
    from config.config import GIGACHAT_SUMMARIZATION_ENABLED

    kw_list = [k.strip() for k in (keywords or "").split(",") if k.strip()][:10]
    fallback = "Ключевые слова: " + ", ".join(kw_list) if kw_list else None

    if not GIGACHAT_SUMMARIZATION_ENABLED or client is None:
        return fallback

    titles_block = "\n".join(f"- {t}" for t in sample_titles[:TOPIC_DESCRIPTION_SAMPLE_SIZE])
    user_content = (
        f"Тема {topic_id}.\n"
        f"Ключевые слова: {keywords}\n"
        f"Примеры заголовков статей:\n{titles_block}\n\n"
        "Напиши 1-2 предложения описания этой темы на русском языке. "
        "Только описание, без пояснений."
    )

    if rate_limiter:
        rate_limiter.wait_if_needed()

    try:
        result = client.chat({
            "messages": [
                {
                    "role": "system",
                    "content": "Ты помощник, который пишет краткие описания для тематических кластеров статей.",
                },
                {"role": "user", "content": user_content},
            ],
            "temperature": 0.3,
        })
        desc = result.choices[0].message.content.strip()
        return desc if desc else fallback
    except Exception as e:
        logger.warning("GigaChat описание для темы %d: %s — используем fallback.", topic_id, e)
        return fallback


# ── [3] Загрузка summary из БД ────────────────────────────────────────────

def load_article_summaries(conn, links: List[str]) -> Dict[str, dict]:
    """
    Загружает title и summary из processed_articles по списку ссылок.
    Один запрос для всех ссылок разом.
    """
    if conn is None or not links:
        return {}
    from config.config import POSTGRES_TABLE_PROCESSED_ARTICLES
    with conn.cursor() as cur:
        cur.execute(
            f"SELECT link, title, summary FROM {POSTGRES_TABLE_PROCESSED_ARTICLES} WHERE link = ANY(%s);",
            (list(links),),
        )
        rows = cur.fetchall()
    return {
        row["link"]: {"title": row["title"] or "", "summary": row["summary"] or ""}
        for row in rows
    }


# ── main ───────────────────────────────────────────────────────────────────

def main() -> None:
    print("=" * 76)
    print("  bertopic_to_collections.py — Phase 0: BERTopic → PostgreSQL")
    print(f"  model_version={MODEL_VERSION}  skip_rag={SKIP_RAG}")
    print("=" * 76)

    # ── [1/6] Загрузка CSV ────────────────────────────────────────────────
    print("\n[1/6] Загружаем CSV из bertopic_output_2/...")
    df_topics, df_articles = load_csvs()

    # Убираем шумовую тему -1
    df_topics = df_topics[df_topics["topic_id"] >= 0].copy()
    df_articles_valid = df_articles[df_articles["topic_id"] >= 0].copy()
    print(f"  Тем (без шума): {len(df_topics)},  статей: {len(df_articles_valid)}")

    # ── [2/6] Подключение к БД ────────────────────────────────────────────
    print("\n[2/6] Подключаемся к PostgreSQL...")
    from src.tools.db_state import (
        add_to_inbox,
        ensure_tables,
        get_connection,
        get_or_create_bertopic_collection,
        upsert_bertopic_assignments,
    )
    from src.pipeline.rag_prep import prepare_and_upsert_rag_documents

    conn = get_connection()
    if conn is None:
        logger.error("Нет подключения к БД. Проверьте POSTGRES_* в config/config.py.")
        sys.exit(1)
    ensure_tables(conn)
    print("  ✓ Таблицы готовы")

    # ── [3/6] Инициализация GigaChat ──────────────────────────────────────
    print("\n[3/6] Инициализация GigaChat...")
    client = None
    rate_limiter = None
    from config.config import GIGACHAT_SUMMARIZATION_ENABLED
    if GIGACHAT_SUMMARIZATION_ENABLED:
        try:
            from src.tools.llm_utils import create_gigachat_client
            from src.tools.rate_limiter import RateLimiter
            from config.config import DEFAULT_LLM_SLEEP
            client = create_gigachat_client()
            rate_limiter = RateLimiter(delay_seconds=DEFAULT_LLM_SLEEP)
            print("  ✓ GigaChat готов")
        except Exception as e:
            logger.warning("GigaChat недоступен: %s — используем ключевые слова как имена тем.", e)
    else:
        print("  ⚠ GigaChat отключён — используем ключевые слова как имена тем")

    # ── [4/6] Создание коллекций ──────────────────────────────────────────
    print(f"\n[4/6] Создаём коллекции для {len(df_topics)} тем...")

    # Готовим словарь topic_id → список заголовков для GigaChat
    topic_sample_titles: Dict[int, List[str]] = {}
    for t_id, grp in df_articles_valid.groupby("topic_id"):
        topic_sample_titles[int(t_id)] = (
            grp["title"].dropna().head(TOPIC_DESCRIPTION_SAMPLE_SIZE).tolist()
        )

    collection_map: Dict[int, int] = {}  # topic_id → collection.id
    skipped = 0
    seen_topics: set = set()

    # topics_categories.csv содержит несколько строк на тему (по одной на мета-категорию)
    for _, row in df_topics.iterrows():
        topic_id = int(row["topic_id"])
        if topic_id in seen_topics:
            continue
        seen_topics.add(topic_id)

        keywords = str(row.get("top_keywords") or "")
        sample_titles = topic_sample_titles.get(topic_id, [])

        topic_name = generate_topic_description(
            topic_id=topic_id,
            keywords=keywords,
            sample_titles=sample_titles,
            client=client,
            rate_limiter=rate_limiter,
        )

        description = generate_topic_long_description(
            topic_id=topic_id,
            keywords=keywords,
            sample_titles=sample_titles,
            client=client,
            rate_limiter=rate_limiter,
        )

        collection = get_or_create_bertopic_collection(
            conn=conn,
            topic_id=topic_id,
            topic_name=topic_name,
            model_version=MODEL_VERSION,
            description=description,
        )
        if collection is None:
            logger.warning("Не удалось создать коллекцию для темы %d", topic_id)
            skipped += 1
            continue

        collection_map[topic_id] = collection["id"]
        print(f"  Тема {topic_id:>4}  → коллекция id={collection['id']}  «{topic_name[:55]}»")

    print(f"  ✓ Создано/обновлено: {len(collection_map)},  пропущено: {skipped}")

    # ── [5/6] bertopic_assignments ────────────────────────────────────────
    print(f"\n[5/6] Записываем bertopic_assignments ({len(df_articles_valid)} строк)...")
    assignments = [
        {
            "link": str(row["link"]),
            "topic_id": int(row["topic_id"]),
            "probability": None,  # fit_transform probs не сохранены в CSV; Phase 1 заполнит
        }
        for _, row in df_articles_valid.iterrows()
        if str(row.get("link") or "").strip()
    ]
    n_assignments = upsert_bertopic_assignments(conn, assignments, MODEL_VERSION)
    print(f"  ✓ Записано назначений: {n_assignments}")

    # ── [6/6] RAG-документы ───────────────────────────────────────────────
    total_chunks = 0
    if SKIP_RAG:
        print("\n[6/6] RAG-документы пропущены (SKIP_RAG=1)")
    else:
        print(f"\n[6/6] Готовим RAG-документы...")

        # Один запрос к БД — загружаем summary для всех статей разом
        all_links = df_articles_valid["link"].dropna().unique().tolist()
        summaries_map = load_article_summaries(conn, all_links)
        print(f"  Загружено summary из БД: {len(summaries_map)} из {len(all_links)} статей")

        # Загружаем модель эмбеддингов один раз для всех тем
        from src.pipeline.embedding_filter import get_embedding_model
        embed_model = get_embedding_model()

        for topic_id, collection_id in collection_map.items():
            mask = df_articles_valid["topic_id"] == topic_id
            topic_rows = df_articles_valid[mask].copy()
            if topic_rows.empty:
                continue

            # Собираем DataFrame в формате, который ожидает prepare_and_upsert_rag_documents
            records = []
            for _, r in topic_rows.iterrows():
                link = str(r.get("link") or "").strip()
                if not link:
                    continue
                db = summaries_map.get(link, {})
                published_dt = pd.to_datetime(r.get("published_at"), errors="coerce")
                records.append({
                    "link": link,
                    "title": db.get("title") or str(r.get("title") or ""),
                    "summary": db.get("summary") or str(r.get("topic_keywords") or ""),
                    "source": str(r.get("source") or ""),
                    "published_dt": None if pd.isnull(published_dt) else published_dt,
                })

            if not records:
                continue

            df_rag = pd.DataFrame(records).drop_duplicates("link")
            collection_dict = {
                "id": collection_id,
                "discipline": None,
                "ga": None,
                "activity": None,
            }
            n = prepare_and_upsert_rag_documents(conn, collection_dict, df_rag, model=embed_model)
            total_chunks += n
            if n > 0:
                print(f"  Тема {topic_id:>4}  → {n} чанков")

        print(f"  ✓ Всего RAG-чанков: {total_chunks}")

    # ── Итог ──────────────────────────────────────────────────────────────
    print("\n" + "=" * 76)
    print("  Phase 0 завершена.")
    print(f"  Коллекций:    {len(collection_map)}")
    print(f"  Назначений:   {n_assignments}")
    if not SKIP_RAG:
        print(f"  RAG-чанков:   {total_chunks}")
    print("=" * 76)

    conn.close()


if __name__ == "__main__":
    main()
