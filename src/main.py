"""
Главный файл пайплайна сбора и обработки статей с Habr.

Запускает все этапы обработки и выводит итоговый результат.
"""
import argparse
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from .embedding_filter import filter_articles_by_embedding, get_embedding_model
from .lemmatization_filter import filter_articles_by_keywords
from .taxonomy import get_keywords_config_for_selection, get_topic_descriptions_per_node, load_taxonomy
from .tools.llm_utils import create_gigachat_client, format_summary_text, summarize_article
# from .graph import filter_articles_by_relevance  # Закомментировано - не используется
from .rss_parser import collect_articles_for_window
from .tools.db_state import get_connection, load_articles_for_window
from .tools.rate_limiter import RateLimiter
from .tools.text_extraction import add_full_text_column
from config.config import (
    DEFAULT_EMBED_THRESHOLD,
    DEFAULT_HOURS_BACK,
    DEFAULT_LIMIT_PER_FEED,
    DEFAULT_LLM_SLEEP,
    GENERIC_SINGLE_LEMMAS,
    RSS_FEEDS,
    TAXONOMY_SELECTION,
)


def _resolve_taxonomy_selection(override: Optional[dict] = None) -> dict:
    """Выбор узлов для пайплайна: override (от агента) или из config."""
    if override is not None:
        return {
            "discipline": override.get("discipline"),
            "ga": override.get("ga"),
            "activity": override.get("activity"),
        }
    return TAXONOMY_SELECTION

# Настройка логирования
logging.basicConfig(
    level=logging.WARNING,  # Только предупреждения и ошибки
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

GREEN = "\033[32m"
RESET = "\033[0m"


def run_pipeline(taxonomy_selection_override: Optional[dict] = None):
    """
    Запускает весь пайплайн обработки статей.

    Args:
        taxonomy_selection_override: Если задан, используется вместо TAXONOMY_SELECTION из config (например, результат агента-роутера).
    """
    selection = _resolve_taxonomy_selection(taxonomy_selection_override)
    pipeline_start = time.time()

    print("="*60)
    print("🚀 ЗАПУСК ПАЙПЛАЙНА СБОРА СТАТЕЙ С HABR")
    print("="*60)
    print(f"📅 Время запуска: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Этап 1: Сбор статей из RSS-лент (только новые, по last_processed_published_at) и сохранение в БД
    print("📥 Этап 1: Сбор статей из RSS-лент...")
    stage1_start = time.time()
    
    df_articles, stats_rss = collect_articles_for_window(
        DEFAULT_HOURS_BACK,
        limit_per_feed=DEFAULT_LIMIT_PER_FEED,
        rss_feeds=RSS_FEEDS
    )
    
    # Временное окно пайплайна берём из БД по published_at (реально «последние N часов»)
    conn = get_connection()
    if conn is not None:
        df_for_pipeline = load_articles_for_window(conn, DEFAULT_HOURS_BACK)
        if df_for_pipeline.empty:
            df_for_pipeline = df_articles  # fallback: только что собранные
    else:
        df_for_pipeline = df_articles
    
    stage1_time = time.time() - stage1_start
    print(f"   ✓ Завершено за {stage1_time:.2f} сек")
    print(f"   ✓ Собрано новых из RSS: {stats_rss['unique_articles']}")
    print(f"   ✓ Статей в окне {DEFAULT_HOURS_BACK} ч для пайплайна: {len(df_for_pipeline)}")
    print()
    # 1) После "RSS-лент для обработки" — все просмотренные источники (зелёный если есть новые статьи)
    print(f"📡 RSS-лент для обработки: {len(RSS_FEEDS)}")
    per_feed_new = stats_rss.get("per_feed_new_count", {})
    for name in sorted(RSS_FEEDS.keys()):
        count = per_feed_new.get(name, 0)
        prefix = f"{GREEN}" if count > 0 else ""
        suffix = f"{RESET}" if count > 0 else ""
        print(f"   📡 {prefix}{name} - новых в rss: {count}{suffix}")
    print()
    # 2) Все статьи, попавшие в пайплайн: источник | название | ссылка (зелёный + если новая статья)
    new_links = set(df_articles["link"]) if not df_articles.empty else set()
    for _, row in df_for_pipeline.iterrows():
        source = row.get("source", "")
        title = row.get("title", "")
        link = row.get("link", "")
        is_new = link in new_links
        prefix = f"{GREEN}+ " if is_new else "   "
        suffix = f"{RESET}" if is_new else ""
        print(f"   {prefix}{source} | {title} | {link}{suffix}")
    print()
    
    # Этап 2: Фильтрация по ключевым словам (ключевые слова из таксономии по выбранным узлам D/GA/A)
    print("🔍 Этап 2: Фильтрация по ключевым словам...")
    stage2_start = time.time()
    taxonomy = load_taxonomy()
    keywords_config = get_keywords_config_for_selection(taxonomy, selection)
    df_filtered, stats_keywords = filter_articles_by_keywords(
        df_for_pipeline,
        keywords_config=keywords_config,
        generic_single_lemmas=GENERIC_SINGLE_LEMMAS
    )
    
    stage2_time = time.time() - stage2_start
    print(f"   ✓ Завершено за {stage2_time:.2f} сек")
    print(f"   ✓ Статей прошло фильтр: {stats_keywords['passed']}")
    print()
    # 3) Все статьи из пайплайна: полное название | rss источник (зелёный + если прошла; для прошедших — по какому ключевому слову)
    passed_links = set(df_filtered["link"]) if not df_filtered.empty else set()
    link_to_reason = dict(zip(df_filtered["link"], df_filtered["bool_lemma_reason"])) if not df_filtered.empty else {}
    for _, row in df_for_pipeline.iterrows():
        title = row.get("title", "")
        source = row.get("source", "")
        link = row.get("link", "")
        is_passed = link in passed_links
        prefix = f"{GREEN}+ " if is_passed else "   "
        suffix = f"{RESET}" if is_passed else ""
        reason = link_to_reason.get(link, "")
        if reason.startswith("strong lemma matched: "):
            match_keyword = reason.replace("strong lemma matched: ", "", 1)
            print(f"   {prefix}{title} | {source}{suffix}  ← ключ: {match_keyword}")
        else:
            print(f"   {prefix}{title} | {source}{suffix}")
    print()
    
    # Этап 3: Фильтрация по эмбеддингам (ключевые слова и topic_descriptions из таксономии по D/GA/A)
    print("🎯 Этап 3: Фильтрация по эмбеддингам...")
    stage3_start = time.time()
    topic_descriptions_per_node = get_topic_descriptions_per_node(taxonomy, selection)
    embed_model = get_embedding_model()
    df_embedding, stats_embedding = filter_articles_by_embedding(
        df_filtered,
        keywords_config=keywords_config,
        model=embed_model,
        topic_descriptions_per_node=topic_descriptions_per_node,
        threshold=DEFAULT_EMBED_THRESHOLD
    )
    
    stage3_time = time.time() - stage3_start
    print(f"   ✓ Завершено за {stage3_time:.2f} сек")
    print(f"   ✓ Статей прошло фильтр: {stats_embedding['passed']}")
    print()
    # 4) Все статьи из пайплайна (после ключевых слов): название | источник (зелёный если прошла фильтр по эмбеддингам)
    embedding_passed_links = set(df_embedding["link"]) if not df_embedding.empty else set()
    for _, row in df_filtered.iterrows():
        title = row.get("title", "")
        source = row.get("source", "")
        link = row.get("link", "")
        is_passed = link in embedding_passed_links
        prefix = f"{GREEN}" if is_passed else ""
        suffix = f"{RESET}" if is_passed else ""
        print(f"   {prefix}{title} | {source}{suffix}")
    print()
    
    # Сортируем по убыванию embed_similarity и берем топ-6
    print("📊 Выбор топ-6 статей по сходству...")
    df_embedding_sorted = df_embedding.sort_values("embed_similarity", ascending=False)
    df_top6 = df_embedding_sorted.head(6).copy()
    print(f"   ✓ Отобрано статей: {len(df_top6)}")
    print()
    # 5) Все статьи после эмбеддингов в отсортированном виде (зелёный — вошли в топ-6 дайджеста)
    top6_links = set(df_top6["link"]) if not df_top6.empty else set()
    for rank, (_, row) in enumerate(df_embedding_sorted.iterrows(), 1):
        title = row.get("title", "")
        source = row.get("source", "")
        link = row.get("link", "")
        sim = row.get("embed_similarity", 0)
        in_top6 = link in top6_links
        prefix = f"{GREEN}" if in_top6 else ""
        suffix = f"{RESET}" if in_top6 else ""
        print(f"   {prefix}{rank}. {title} | {source} (сходство: {sim:.3f}){suffix}")
    print()
    
    # Этап 4: Извлечение полного текста статей (только для топ-6)
    print("📄 Этап 4: Извлечение полного текста статей...")
    stage4_start = time.time()
    
    df_with_text = add_full_text_column(df_top6)
    
    stage4_time = time.time() - stage4_start
    successful_texts = sum(1 for t in df_with_text["full_text"] if t is not None)
    print(f"   ✓ Завершено за {stage4_time:.2f} сек")
    print(f"   ✓ Успешно извлечено текстов: {successful_texts}/{len(df_with_text)}")
    print()
    
    # Этап 5: LLM-фильтрация релевантности (ЗАКОММЕНТИРОВАНО)
    # print("🤖 Этап 5: LLM-фильтрация релевантности...")
    # stage5_start = time.time()
    # 
    # df_relevant = filter_articles_by_relevance(df_with_text)
    # 
    # stage5_time = time.time() - stage5_start
    # print(f"   ✓ Завершено за {stage5_time:.2f} сек")
    # print(f"   ✓ Релевантных статей: {len(df_relevant)}")
    # print()
    # 
    # Используем df_with_text вместо df_relevant
    df_relevant = df_with_text
    
    # Этап 6: Суммаризация статей
    print("📝 Этап 6: Суммаризация статей...")
    stage6_start = time.time()
    
    # Создаем клиент GigaChat и rate limiter один раз
    giga_client = create_gigachat_client()
    rate_limiter = RateLimiter(delay_seconds=DEFAULT_LLM_SLEEP)
    
    summaries = []
    total_relevant = len(df_relevant)
    
    for idx, (_, row) in enumerate(df_relevant.iterrows(), 1):
        title = row["title"]
        full_text = row.get("full_text")
        
        # Пропускаем статьи без текста
        if full_text is None:
            logger.warning(f"Пропуск статьи {idx} без текста: {title[:50]}...")
            summaries.append("Не удалось получить текст статьи для суммаризации.")
            continue
        
        print(f"   ▶ Суммаризация [{idx}/{total_relevant}]: {title[:60]}...")
        summary = summarize_article(
            title=title,
            full_text=full_text,
            client=giga_client,
            rate_limiter=rate_limiter
        )
        summaries.append(summary)
    
    df_relevant["summary"] = summaries
    
    stage6_time = time.time() - stage6_start
    print(f"   ✓ Завершено за {stage6_time:.2f} сек")
    print(f"   ✓ Суммаризировано статей: {len(summaries)}")
    print()
    
    # Сохранение финального результата
    project_root = Path(__file__).parent.parent
    outputs_dir = project_root / "outputs"
    outputs_dir.mkdir(exist_ok=True)
    
    output_file = outputs_dir / "articles_filtered.csv"
    df_relevant.to_csv(output_file, index=False, encoding='utf-8')
    
    # Итоговая статистика
    total_time = time.time() - pipeline_start
    
    print("="*60)
    print("📊 ИТОГОВАЯ СВОДКА ПАЙПЛАЙНА")
    print("="*60)
    print("📥 Этап 1 (RSS сбор):")
    print(f"   • Уникальных статей собрано в этом запуске: {stats_rss['unique_articles']}")
    print(f"   • Записей из RSS перебрано: {stats_rss['total_parsed']} "
          f"(одна статья может быть в нескольких лентах → считаем каждый раз; "
          f"пропущено уже в БД: {stats_rss.get('already_processed_skipped', 0)}, дубликатов в запуске: {stats_rss['duplicates_skipped']})")
    if stats_rss.get('feeds_failed', 0) > 0:
        print(f"   • Лент с ошибками: {stats_rss['feeds_failed']}")
    print()
    print("🔍 Этап 2 (Фильтрация по ключевым словам с лемматизацией):")
    print(f"   • Всего статей на входе: {stats_keywords['total_articles']}")
    print(f"   • Прошло фильтр: {stats_keywords['passed']}")
    print()
    print("🎯 Этап 3 (Фильтрация по эмбеддингам):")
    print(f"   • Всего статей на входе: {stats_embedding['total_articles']}")
    print(f"   • Прошло фильтр: {stats_embedding['passed']}")
    print(f"   • Отклонено: {stats_embedding['rejected']}")
    print(f"   • Сходство: min={stats_embedding['min_similarity']:.3f}, "
          f"mean={stats_embedding['mean_similarity']:.3f}, max={stats_embedding['max_similarity']:.3f}")
    print()
    print("📊 Выбор топ-6 статей:")
    print(f"   • Отобрано статей по embed_similarity: {len(df_top6)}")
    if len(df_top6) > 0:
        top_similarity = df_top6["embed_similarity"].max()
        min_similarity = df_top6["embed_similarity"].min()
        print(f"   • Диапазон сходства: {min_similarity:.3f} - {top_similarity:.3f}")
    print()
    print("📄 Этап 4 (Извлечение полного текста):")
    print(f"   • Всего статей: {len(df_with_text)}")
    print(f"   • Успешно извлечено: {successful_texts}")
    print()
    # print("🤖 Этап 5 (LLM-фильтрация релевантности):")
    # print(f"   • Всего статей на входе: {len(df_with_text)}")
    # print(f"   • Релевантных статей: {len(df_relevant)}")
    # print()
    print("📝 Этап 6 (Суммаризация):")
    print(f"   • Суммаризировано статей: {len(summaries)}")
    print()
    print(f"⏱️  Общее время выполнения: {total_time:.2f} сек ({total_time/60:.2f} мин)")
    print(f"💾 Результат сохранен: {output_file}")
    print("="*60)
    
    # Вывод дайджеста
    if len(df_relevant) > 0:
        print("\n" + "="*60)
        print("📋 ДАЙДЖЕСТ СТАТЕЙ")
        print("="*60 + "\n")
        
        for i, (_, row) in enumerate(df_relevant.iterrows(), 1):
            title = row["title"]
            link = row["link"]
            summary = row["summary"]
            similarity = row.get("embed_similarity", 0.0)
            
            formatted_summary = format_summary_text(summary, width=95)
            
            print("─" * 60)
            print(f"🔹 {title}")
            print(f"🔗 {link}")
            print(f"📊 Сходство: {similarity:.3f}\n")
            print("📝 Выжимка:\n")
            print(formatted_summary)
            print("\n")
    
    return df_relevant


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Пайплайн сбора и фильтрации статей с Habr.")
    parser.add_argument(
        "--query",
        type=str,
        default=None,
        help="Запрос на естественном языке: агент-роутер выберет узлы D/GA/A, пайплайн запустится с этой выборкой.",
    )
    args = parser.parse_args()

    if args.query:
        from .agents.router import run_router, router_output_to_taxonomy_selection
        print("🤖 Запрос к агенту-роутеру: выбор узлов таксономии по запросу...")
        router_out = run_router(args.query)
        selection = router_output_to_taxonomy_selection(router_out)
        if router_out.get("clarification_needed") and router_out.get("clarification_question"):
            print("❓ Требуется уточнение:", router_out["clarification_question"])
            print("   Запустите снова с уточнённым запросом (--query \"...\") или без --query для конфига.")
            raise SystemExit(1)
        if router_out.get("status") == "not_found" or selection is None:
            print("⚠️ По запросу не найден подходящий узел таксономии (status=not_found). Запуск с TAXONOMY_SELECTION из config.")
            selection = None
        else:
            print(f"   Выборка: D={selection.get('discipline')}, GA={selection.get('ga')}, A={selection.get('activity')}")
        run_pipeline(taxonomy_selection_override=selection)
    else:
        run_pipeline()

