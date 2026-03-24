"""
Эксперимент: zero-shot классификация статей по таксономии D/GA без дообучения.

Флоу:
  Статья → Шаг 1: определяем Discipline (D1..D6)
          → Шаг 2: определяем Group (GA1..GAn) внутри победившей D
          → Результат: (D_id, GA_id, имя) + вероятности

Источник статей (приоритет):
  1. БД — таблица rag_documents: поля title + summary (LLM-описание)
     Можно указать конкретную коллекцию через COLLECTION_ID,
     либо оставить None — тогда берутся уникальные статьи из всех коллекций.
  2. Встроенные тестовые статьи TEST_ARTICLES (если БД недоступна)

Запуск:
  cd /Users/macbookpro/SberAgencyCrawler
  python zero_shot_classify.py

  # Конкретная коллекция:
  COLLECTION_ID=3 python zero_shot_classify.py

  # Лимит статей:
  LIMIT=20 python zero_shot_classify.py

Зависимости:
  pip install transformers           # если не установлен как зависимость sentence-transformers
  Модель скачивается автоматически при первом запуске (~280 MB)

Модели (настраивается через MODEL_NAME ниже):
  - "MoritzLaurer/mDeBERTa-v3-base-mnli-xnli"  # многоязычная, ~280 MB — РЕКОМЕНДУЕТСЯ
  - "facebook/bart-large-mnli"                   # только EN, точнее, ~1.6 GB
"""
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ── настройки ──────────────────────────────────────────────────────────────
MODEL_NAME = "MoritzLaurer/mDeBERTa-v3-base-mnli-xnli"
TOP_K_DISCIPLINES = 2   # сколько D показывать в промежуточных итогах
MIN_GA_SCORE = 0.05     # порог ниже которого GA считается нерелевантным

# Источник данных: id коллекции (int) или None — все коллекции
COLLECTION_ID: Optional[int] = (
    int(os.environ["COLLECTION_ID"]) if "COLLECTION_ID" in os.environ else None
)
# Максимум статей для классификации (None = без лимита)
LIMIT: Optional[int] = (
    int(os.environ["LIMIT"]) if "LIMIT" in os.environ else 30
)
# ───────────────────────────────────────────────────────────────────────────

# Добавляем корень проекта в sys.path, чтобы работал import src.*
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.taxonomy import load_taxonomy  # noqa: E402


# ── загрузка статей из БД ──────────────────────────────────────────────────

def load_articles_from_db(
    collection_id: Optional[int] = None,
    limit: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Загружает уникальные статьи из rag_documents.
    Использует title + summary (LLM-описание) как текст для классификации.

    Args:
        collection_id: id конкретной коллекции или None (все коллекции).
        limit: максимум статей, None = без лимита.

    Returns:
        Список словарей {id, title, summary, collection_id, collection_key, expected}.
        Пустой список если БД недоступна.
    """
    try:
        from src.tools.db_state import get_connection
        from config.config import POSTGRES_TABLE_RAG_DOCUMENTS, POSTGRES_TABLE_COLLECTIONS
    except ImportError as e:
        print(f"  ⚠ Не удалось импортировать модули БД: {e}")
        return []

    conn = get_connection()
    if conn is None:
        return []

    try:
        with conn.cursor() as cur:
            if collection_id is not None:
                # Статьи конкретной коллекции — уникальные по link
                cur.execute(
                    f"""
                    SELECT DISTINCT ON (r.link)
                        r.link        AS id,
                        r.title,
                        r.summary,
                        r.collection_id,
                        c.collection_key,
                        c.discipline  AS col_discipline,
                        c.ga          AS col_ga
                    FROM {POSTGRES_TABLE_RAG_DOCUMENTS} r
                    JOIN {POSTGRES_TABLE_COLLECTIONS} c ON c.id = r.collection_id
                    WHERE r.collection_id = %s
                      AND r.title IS NOT NULL
                      AND r.summary IS NOT NULL
                      AND r.summary != ''
                    ORDER BY r.link, r.chunk_index
                    {f"LIMIT {limit}" if limit else ""};
                    """,
                    (collection_id,),
                )
            else:
                # Уникальные статьи по всем коллекциям (дедупликация по link)
                cur.execute(
                    f"""
                    SELECT DISTINCT ON (r.link)
                        r.link        AS id,
                        r.title,
                        r.summary,
                        r.collection_id,
                        c.collection_key,
                        c.discipline  AS col_discipline,
                        c.ga          AS col_ga
                    FROM {POSTGRES_TABLE_RAG_DOCUMENTS} r
                    JOIN {POSTGRES_TABLE_COLLECTIONS} c ON c.id = r.collection_id
                    WHERE r.title IS NOT NULL
                      AND r.summary IS NOT NULL
                      AND r.summary != ''
                    ORDER BY r.link, r.chunk_index
                    {f"LIMIT {limit}" if limit else ""};
                    """,
                )

            rows = cur.fetchall()
    except Exception as e:
        print(f"  ⚠ Ошибка запроса к БД: {e}")
        return []
    finally:
        conn.close()

    articles = []
    for row in rows:
        col_d = row.get("col_discipline") or ""
        col_ga = row.get("col_ga") or ""
        # В поле expected — метка из коллекции (то, куда статья уже была отнесена вручную)
        expected = f"{col_d}/{col_ga}" if col_d and col_ga else (col_d or row.get("collection_key") or "?")
        articles.append({
            "id": str(row.get("id") or "")[-40:],   # обрезаем длинные URL
            "title": (row.get("title") or "").strip(),
            "summary": (row.get("summary") or "").strip(),
            "collection_id": row.get("collection_id"),
            "collection_key": row.get("collection_key") or "",
            "expected": expected,
        })
    return articles


# ── встроенные тестовые статьи (fallback если БД недоступна) ──────────────
TEST_ARTICLES = [
    {
        "id": "art_01",
        "title": "How to Set Up Jira Workflows for Cross-Functional Teams",
        "summary": (
            "A practical guide to configuring Jira boards, sprint settings, "
            "and workflow automation for teams spanning engineering, design, and QA. "
            "Covers custom issue types, board filters, and connecting Jira to Confluence."
        ),
        "expected": "D2/GA1",
    },
    {
        "id": "art_02",
        "title": "The Scrum Master as Servant Leader: Common Mistakes and How to Avoid Them",
        "summary": (
            "Explores the leadership style of effective Scrum masters, the most common "
            "pitfalls in sprint facilitation, and how to coach teams toward self-organization. "
            "Includes real stories from practitioners at scale-ups."
        ),
        "expected": "D4/GA2",
    },
    {
        "id": "art_03",
        "title": "Running Customer Interviews That Actually Validate Your Idea",
        "summary": (
            "Step-by-step framework for CustDev interviews: how to structure problem "
            "interviews, avoid leading questions, spot confirmation bias, and translate "
            "raw feedback into product decisions. Based on JTBD and Opportunity Solution Tree."
        ),
        "expected": "D1",
    },
    {
        "id": "art_04",
        "title": "Product Roadmap for Senior Stakeholders: Tactical vs Strategic",
        "summary": (
            "How to build two versions of your roadmap — one for the C-suite and one "
            "for the delivery team. Covers data-driven prioritisation, OKR alignment, "
            "and managing stakeholder expectations without over-promising."
        ),
        "expected": "D2/GA7",
    },
    {
        "id": "art_05",
        "title": "REST vs gRPC: When to Choose Which API Framework",
        "summary": (
            "A deep dive into performance trade-offs between REST, gRPC, and GraphQL. "
            "Includes benchmarks for latency and throughput, guidance on API governance, "
            "versioning strategies, and security best practices."
        ),
        "expected": "D3/GA1",
    },
    {
        "id": "art_06",
        "title": "PySpark Optimization: 7 Tips for High-Performance Data Pipelines",
        "summary": (
            "Practical techniques to squeeze performance out of Apache Spark: partition "
            "tuning, broadcast joins, avoiding shuffles, caching strategies, and monitoring "
            "with Spark UI. Benchmarks on 100 GB datasets."
        ),
        "expected": "D4/GA6",
    },
    {
        "id": "art_07",
        "title": "SAFe in Practice: Release Train Engineer Experience Notes",
        "summary": (
            "A transformation notes from a Release Train Engineer who rolled out SAFe "
            "across four product teams. Covers PI Planning, ART launch, common resistance "
            "patterns, and metrics for measuring Agile scaling success."
        ),
        "expected": "D6/GA1",
    },
    {
        "id": "art_08",
        "title": "Как определить MVP scope: от идеи к первым пользователям",
        "summary": (
            "Разбираем подход к брейнштормингу фич, их приоритизации и обрезке до минимально "
            "жизнеспособного продукта. Метод MoSCoW, impact/effort матрица и примеры из "
            "реальных продуктовых команд. Как не перегрузить первый релиз."
        ),
        "expected": "D2/GA8 или D1/GA2",
    },
    {
        "id": "art_09",
        "title": "Citizen Development: Building Internal Tools Without a Single Line of Code",
        "summary": (
            "How business analysts and ops teams use low-code platforms like Power Apps "
            "and Retool to build dashboards, approval flows, and data entry forms — "
            "reducing dependency on engineering and closing talent gaps fast."
        ),
        "expected": "D4/GA3",
    },
    {
        "id": "art_10",
        "title": "Agile Budgeting: How to Fund Iterations Instead of Projects",
        "summary": (
            "Traditional project budgets don't fit Agile delivery. This article explains "
            "value-stream funding, rolling forecasts, and how to present budget plans "
            "to finance teams unfamiliar with iterative development."
        ),
        "expected": "D2/GA5",
    },
]


# ── работа с таксономией ───────────────────────────────────────────────────

def _make_label(node: Dict[str, Any], fallback_prefix: str = "") -> str:
    """
    Строит строку-кандидат для классификатора из узла таксономии.
    Приоритет: topic_descriptions[0] → name + keywords (первые 5).
    """
    descriptions = [
        str(t).strip()
        for t in (node.get("topic_descriptions") or [])
        if t and isinstance(t, str) and str(t).strip()
    ]
    if descriptions:
        return descriptions[0]

    # Fallback: генерируем описание из имени и ключевых слов
    name = node.get("name") or fallback_prefix
    keywords = [
        str(k).strip()
        for k in (node.get("keywords") or [])[:5]
        if k and isinstance(k, str) and str(k).strip()
    ]
    if keywords:
        return f"Materials about {name}: {', '.join(keywords)}."
    return f"Materials about {name}."


def build_label_maps(
    taxonomy: Dict[str, Any],
) -> Tuple[
    Dict[str, str],          # discipline_id → label text
    Dict[str, str],          # discipline_id → display name
    Dict[str, Dict[str, str]],  # discipline_id → {ga_id → label text}
    Dict[str, Dict[str, str]],  # discipline_id → {ga_id → display name}
]:
    """Строит карты меток для двухуровневой классификации."""
    d_labels: Dict[str, str] = {}
    d_names: Dict[str, str] = {}
    ga_labels: Dict[str, Dict[str, str]] = {}
    ga_names: Dict[str, Dict[str, str]] = {}

    for d in taxonomy.get("disciplines") or []:
        d_id = d.get("id", "")
        d_labels[d_id] = _make_label(d, fallback_prefix=d.get("name", d_id))
        d_names[d_id] = d.get("name", d_id)

        ga_labels[d_id] = {}
        ga_names[d_id] = {}
        for g in d.get("groups") or []:
            g_id = g.get("id", "")
            ga_labels[d_id][g_id] = _make_label(
                g, fallback_prefix=f"{d.get('name', '')} — {g.get('name', g_id)}"
            )
            ga_names[d_id][g_id] = g.get("name", g_id)

    return d_labels, d_names, ga_labels, ga_names


# ── классификация ──────────────────────────────────────────────────────────

def classify_article(
    article_text: str,
    classifier,
    d_labels: Dict[str, str],
    d_names: Dict[str, str],
    ga_labels: Dict[str, Dict[str, str]],
    ga_names: Dict[str, Dict[str, str]],
    top_k_disciplines: int = TOP_K_DISCIPLINES,
    min_ga_score: float = MIN_GA_SCORE,
) -> Dict[str, Any]:
    """
    Двухуровневая zero-shot классификация:
      1. Определяем дисциплину (D)
      2. Определяем группу (GA) внутри победившей D

    Returns dict с ключами:
      discipline_id, discipline_name, discipline_score,
      ga_id, ga_name, ga_score,
      top_disciplines (list), ga_ranking (list)
    """
    # ── Шаг 1: Выбор дисциплины ──────────────────────────────────────────
    d_ids = list(d_labels.keys())
    d_texts = [d_labels[d] for d in d_ids]

    d_result = classifier(
        article_text,
        candidate_labels=d_texts,
        multi_label=False,
    )

    # Восстанавливаем d_id по позиции текста
    d_text_to_id = {text: d_id for d_id, text in d_labels.items()}
    top_disciplines = [
        {
            "id": d_text_to_id[label],
            "name": d_names[d_text_to_id[label]],
            "score": round(score, 4),
        }
        for label, score in zip(d_result["labels"], d_result["scores"])
    ]
    best_d = top_disciplines[0]

    # ── Шаг 2: Выбор группы внутри лучшей D ──────────────────────────────
    winner_d_id = best_d["id"]
    ga_map = ga_labels.get(winner_d_id, {})

    ga_ranking: List[Dict[str, Any]] = []
    ga_id: Optional[str] = None
    ga_name: Optional[str] = None
    ga_score: Optional[float] = None

    if ga_map:
        ga_ids = list(ga_map.keys())
        ga_texts = [ga_map[g] for g in ga_ids]

        ga_result = classifier(
            article_text,
            candidate_labels=ga_texts,
            multi_label=False,
        )

        ga_text_to_id = {text: g_id for g_id, text in ga_map.items()}
        ga_ranking = [
            {
                "id": ga_text_to_id[label],
                "name": ga_names[winner_d_id].get(ga_text_to_id[label], label),
                "score": round(score, 4),
            }
            for label, score in zip(ga_result["labels"], ga_result["scores"])
            if score >= min_ga_score
        ]

        if ga_ranking:
            best_ga = ga_ranking[0]
            ga_id = best_ga["id"]
            ga_name = best_ga["name"]
            ga_score = best_ga["score"]

    return {
        "discipline_id": winner_d_id,
        "discipline_name": best_d["name"],
        "discipline_score": best_d["score"],
        "ga_id": ga_id,
        "ga_name": ga_name,
        "ga_score": ga_score,
        "top_disciplines": top_disciplines[:top_k_disciplines],
        "ga_ranking": ga_ranking[:3],
    }


# ── форматированный вывод ──────────────────────────────────────────────────

def _bar(score: float, width: int = 20) -> str:
    filled = round(score * width)
    return "█" * filled + "░" * (width - filled)


def print_result(article: Dict[str, Any], result: Dict[str, Any]) -> None:
    sep = "─" * 72
    print(f"\n{sep}")
    print(f"  [{article['id']}] {article['title']}")
    print(f"  Ожидалось : {article['expected']}")
    print(sep)

    d_id = result["discipline_id"]
    d_score = result["discipline_score"]
    print(f"  Шаг 1 — Дисциплина:")
    print(f"    ▶ {d_id} «{result['discipline_name']}»  {_bar(d_score)}  {d_score:.2%}")
    for alt in result["top_disciplines"][1:]:
        print(f"      {alt['id']} «{alt['name']}»  {_bar(alt['score'])}  {alt['score']:.2%}")

    ga_id = result["ga_id"]
    if ga_id:
        ga_score = result["ga_score"]
        print(f"  Шаг 2 — Группа внутри {d_id}:")
        print(
            f"    ▶ {ga_id} «{result['ga_name']}»  {_bar(ga_score)}  {ga_score:.2%}"
        )
        for alt in result["ga_ranking"][1:]:
            print(f"      {alt['id']} «{alt['name']}»  {_bar(alt['score'])}  {alt['score']:.2%}")
        result_label = f"{d_id} / {ga_id}"
    else:
        print(f"  Шаг 2 — Группы в {d_id} не определены (нет данных)")
        result_label = d_id

    print(f"\n  Итог: {result_label}")


def print_summary(articles: List[Dict], results: List[Dict]) -> None:
    print("\n" + "═" * 72)
    print("  СВОДКА")
    print("═" * 72)
    print(f"  {'ID':<8} {'Заголовок':<42} {'Результат':<18}")
    print(f"  {'─'*8} {'─'*42} {'─'*18}")
    for art, res in zip(articles, results):
        d_id = res["discipline_id"]
        ga_id = res.get("ga_id") or "—"
        label = f"{d_id} / {ga_id}" if ga_id != "—" else d_id
        title = art["title"][:40] + ("…" if len(art["title"]) > 40 else "")
        print(f"  {art['id']:<8} {title:<42} {label:<18}")
    print("═" * 72)


# ── main ───────────────────────────────────────────────────────────────────

def main() -> None:
    print("=" * 72)
    print("  Zero-shot классификация статей по таксономии D/GA")
    print(f"  Модель: {MODEL_NAME}")
    print("=" * 72)

    # ── [1/4] Загрузка таксономии ─────────────────────────────────────────
    print("\n[1/4] Загружаем таксономию...")
    taxonomy = load_taxonomy()
    d_labels, d_names, ga_labels, ga_names = build_label_maps(taxonomy)
    disciplines_count = len(d_labels)
    ga_count = sum(len(v) for v in ga_labels.values())
    print(f"  Дисциплин: {disciplines_count},  групп (GA): {ga_count}")

    # ── [2/4] Загрузка статей ─────────────────────────────────────────────
    print("\n[2/4] Загружаем статьи...")
    articles = load_articles_from_db(collection_id=COLLECTION_ID, limit=LIMIT)

    if articles:
        source_label = (
            f"rag_documents (коллекция #{COLLECTION_ID})"
            if COLLECTION_ID
            else "rag_documents (все коллекции)"
        )
        print(f"  ✓ Источник: БД → {source_label}")
        print(f"  ✓ Загружено статей: {len(articles)}")
        # Показываем из каких коллекций пришли статьи
        keys = sorted({a["collection_key"] for a in articles if a.get("collection_key")})
        if keys:
            print(f"  Коллекции: {', '.join(keys)}")
    else:
        print("  ⚠ БД недоступна или пуста — используем встроенные тестовые статьи")
        articles = TEST_ARTICLES

    print(f"\n  Пример входного текста для классификатора:")
    sample = articles[0]
    sample_text = f"{sample['title']}. {sample['summary']}"
    print(f"  title  : {sample['title'][:80]}")
    print(f"  summary: {sample['summary'][:120]}{'…' if len(sample['summary']) > 120 else ''}")

    # ── [3/4] Загрузка модели ─────────────────────────────────────────────
    print(f"\n[3/4] Загружаем модель {MODEL_NAME}...")
    print("  (При первом запуске модель скачивается ~280 MB)")
    try:
        from transformers import pipeline
        classifier = pipeline(
            "zero-shot-classification",
            model=MODEL_NAME,
            # device=0,  # раскомментировать для GPU
        )
        print("  ✓ Модель загружена")
    except ImportError:
        print("\n  ✗ Библиотека transformers не установлена.")
        print("    Установите: pip install transformers")
        sys.exit(1)

    # ── [4/4] Классификация ───────────────────────────────────────────────
    print(f"\n[4/4] Классифицируем {len(articles)} статей...\n")
    results = []
    for i, article in enumerate(articles, 1):
        print(f"  [{i}/{len(articles)}] {article['title'][:60]}…", end="\r")
        text = f"{article['title']}. {article['summary']}"
        result = classify_article(
            text, classifier, d_labels, d_names, ga_labels, ga_names
        )
        results.append(result)
        print_result(article, result)

    print_summary(articles, results)

    print("\nПодсказки:")
    print("  • COLLECTION_ID=3 python zero_shot_classify.py  — конкретная коллекция")
    print("  • LIMIT=50 python zero_shot_classify.py         — больше статей")
    print(f"  • Поменяйте MODEL_NAME на 'facebook/bart-large-mnli' для сравнения точности")


if __name__ == "__main__":
    main()
