"""
Механический тест: hybrid_retrieve_chunks находит то же что search_articles.

search_articles — ground truth (10/10 из прошлого теста).
hybrid_retrieve_chunks — новый retrieval для answer_from_rag.

Запуск: python3 tests/test_hybrid_retrieval.py
"""
import sys, os, logging
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
logging.basicConfig(level=logging.WARNING)

from src.chat.tools import search_articles
from src.qa.retrieval import hybrid_retrieve_chunks, retrieve_chunks, embed_query
from src.tools.db_state import get_connection, get_or_create_global_rag_collection

COLLECTION_ID = 206
TOP_K = 250

QUERIES = [
    ("как масштабировать workloads в Kubernetes",            "Сем RU→EN"),
    ("GKE active buffer scaling",                            "Точн EN BM25-кейс"),
    ("мошенничество борьба с фродом предотвращение",         "Сем RU→EN"),
    ("fraud prevention free trial abuse",                    "Точн EN"),
    ("компьютерная криминалистика Windows",                  "Точн RU"),
    ("AI speech synthesis text to speech generation",        "Точн EN"),
    ("медленные запросы ClickHouse диагностика",             "Сем RU→RU"),
    ("Airflow ClickHouse ETL data pipeline",                 "EN→RU термины"),
    ("постквантовая криптография защита SSH",                "Сем RU→EN"),
    ("Kotlin IO dispatcher connection pool",                 "EN→RU термины"),
]


def run():
    conn = get_connection()
    assert conn, "Нет подключения к БД"

    W = 40
    print(f"\n{'─'*115}")
    print(f"  {'#':>2}  {'vec':>5}  {'hyb':>5}  {'тип':<22}  {'запрос':<40}  ground-truth статья (top-1 search_articles)")
    print(f"{'─'*115}")

    vec_score = 0
    hyb_score = 0

    for i, (q, label) in enumerate(QUERIES, 1):
        _, emb = embed_query(q)

        # Ground truth: top-1 из search_articles (hybrid + rerank, 10/10)
        sa_results = search_articles(q)
        gt_link = sa_results[0]["link"] if sa_results else None
        gt_title = (sa_results[0]["title"][:W] + "…") if sa_results and len(sa_results[0]["title"]) > W else (sa_results[0]["title"] if sa_results else "—")

        # Pure vector (старый путь, top_k=40)
        vec40 = retrieve_chunks(conn, emb, collection_id=COLLECTION_ID, top_k=40)
        vec40_links = {c.link for c in vec40}
        vec_ok = gt_link in vec40_links if gt_link else False

        # Hybrid (новый путь, top_k=250)
        hyb250 = hybrid_retrieve_chunks(conn, q, emb, collection_id=COLLECTION_ID, top_k=TOP_K)
        hyb250_links = {c.link for c in hyb250}
        hyb_ok = gt_link in hyb250_links if gt_link else False

        vec_mark = "✅" if vec_ok else "❌"
        hyb_mark = "✅" if hyb_ok else "❌"

        if vec_ok: vec_score += 1
        if hyb_ok: hyb_score += 1

        # Ранг в каждом методе
        vec_rank = next((r + 1 for r, c in enumerate(vec40) if c.link == gt_link), None)
        hyb_rank = next((r + 1 for r, c in enumerate(hyb250) if c.link == gt_link), None)
        vec_str = f"{vec_rank}" if vec_rank else "—"
        hyb_str = f"{hyb_rank}" if hyb_rank else "—"

        print(f"  {i:>2}  {vec_mark} {vec_str:>3}  {hyb_mark} {hyb_str:>3}  {label:<22}  {q[:40]:<40}  {gt_title}")

    conn.close()
    print(f"{'─'*115}")
    print(f"\n  pure-vector top-40 : {vec_score}/10")
    print(f"  hybrid       top-250: {hyb_score}/10")

    assert hyb_score >= vec_score, "Hybrid не должен быть хуже pure-vector!"
    print(f"\n  {'✅ Hybrid лучше или равен pure-vector' if hyb_score >= vec_score else '❌ РЕГРЕССИЯ'}")


if __name__ == "__main__":
    run()
