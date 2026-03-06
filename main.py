"""
Точка входа в пайплайн сбора и обработки статей с Habr.

Запуск:
  python3 main.py                    — пайплайн с TAXONOMY_SELECTION из config
  python3 main.py --query "запрос"   — агент-роутер выберет узлы D/GA/A, затем пайплайн
"""
import argparse

from src.main import run_pipeline

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Пайплайн сбора и фильтрации статей с Habr.")
    parser.add_argument(
        "--query",
        type=str,
        default=None,
        help="Запрос на естественном языке: агент-роутер выберет узлы D/GA/A, пайплайн запустится с этой выборкой.",
    )
    parser.add_argument(
        "--router-only",
        action="store_true",
        help="Только запустить агента-роутера по запросу (без пайплайна). Показать выбранные узлы и обоснование. Требуется --query.",
    )
    args = parser.parse_args()

    if args.router_only:
        if not args.query:
            print("Для --router-only укажите запрос: python3 main.py --router-only --query \"ваш запрос\"")
            exit(1)
        from src.agents.router import run_router, format_router_result_for_display
        print("🤖 Запрос к агенту-роутеру (режим теста, без пайплайна)...")
        out = run_router(args.query)
        print(format_router_result_for_display(out))
        exit(0)

    if args.query:
        from src.agents.router import run_router, router_output_to_taxonomy_selection
        print("🤖 Запрос к агенту-роутеру: выбор узлов таксономии по запросу...")
        router_out = run_router(args.query)
        selection = router_output_to_taxonomy_selection(router_out)
        if router_out.get("clarification_needed") and router_out.get("clarification_question"):
            print("❓ Требуется уточнение:", router_out["clarification_question"])
            print("   Запустите снова с уточнённым запросом (--query \"...\") или без --query для конфига.")
            exit(1)
        if router_out.get("status") == "not_found" or selection is None:
            print("⚠️ По запросу не найден подходящий узел таксономии (status=not_found). Запуск с TAXONOMY_SELECTION из config.")
            selection = None
            collection_name = None
        else:
            print(f"   Выборка: D={selection.get('discipline')}, GA={selection.get('ga')}, A={selection.get('activity')}")
            # Пользователь выбирает имя коллекции, под которой будет сохранён результат этого запуска.
            try:
                raw_name = input("📝 Введите имя коллекции (Enter — имя по умолчанию): ").strip()
            except EOFError:
                raw_name = ""
            collection_name = raw_name or None
        run_pipeline(taxonomy_selection_override=selection, collection_name=collection_name)
    else:
        run_pipeline()
