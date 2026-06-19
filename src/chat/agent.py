"""
ReAct-цикл чат-агента Atlas.

Алгоритм:
  1. Добавить SYSTEM_PROMPT к messages[]
  2. Вызвать GigaChat с описанием тулов
     - finish_reason == "function_call" → выполнить тул → добавить в messages[] → повтор
     - finish_reason == "stop"         → финальный ответ → выход
  3. Аварийный выход при превышении MAX_ITERATIONS

Запуск из терминала:
    python -m src.chat.agent "расскажи подробно про статью https://..."
"""
from __future__ import annotations

import json
import logging
import sys
from datetime import date
from typing import Any, Dict, Generator, List

from gigachat.models.chat import (
    Chat,
    FunctionCall,
    FunctionParameters,
    FunctionParametersProperty,
    Messages,
    MessagesRole,
)
from gigachat.models.chat import Function as GigaChatFunction

from src.chat.prompts import SYSTEM_PROMPT
from src.chat.tools import answer_from_rag, get_article, lookup_glossary, search_articles
from src.tools.llm_utils import create_gigachat_client

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────
# Константы
# ──────────────────────────────────────────────────────────────

MAX_ITERATIONS = 5
MAX_CONTEXT_MESSAGES = 20  # максимум non-system сообщений в контексте GigaChat

# Модели без поддержки function calling → апгрейд до Pro
_LITE_MODELS = {"GigaChat", "GigaChat-Lite", "GigaChat Lite", ""}

# ──────────────────────────────────────────────────────────────
# Описание тулов для GigaChat (TOOLS_SCHEMA)
# Тулы добавляются по одному в задачах 2.1–2.4
# ──────────────────────────────────────────────────────────────

TOOLS_SCHEMA: List[GigaChatFunction] = [
    GigaChatFunction(
        name="get_article",
        description=(
            "Получить полный текст статьи по ссылке. "
            "Вызывай когда пользователь хочет подробно изучить конкретную статью."
        ),
        parameters=FunctionParameters(
            properties={
                "link": FunctionParametersProperty(**{
                    "type": "string",
                    "description": "URL статьи",
                }),
            },
            required=["link"],
        ),
        few_shot_examples=[
            {
                "request": "расскажи подробно про эту статью",
                "params": {"link": "https://example.com/article"},
            },
            {
                "request": "хочу прочитать первую статью полностью",
                "params": {"link": "https://example.com/article"},
            },
        ],
    ),
    GigaChatFunction(
        name="search_articles",
        description=(
            "Найти список статей по теме. "
            "Возвращает заголовки, ссылки, даты и краткие описания статей. "
            "Вызывай когда пользователь хочет найти статьи или получить обзор темы."
        ),
        parameters=FunctionParameters(
            properties={
                "query": FunctionParametersProperty(**{
                    "type": "string",
                    "description": "Поисковый запрос",
                }),
                "date_from": FunctionParametersProperty(**{
                    "type": "string",
                    "description": "Начальная дата поиска YYYY-MM-DD (опционально)",
                }),
                "date_to": FunctionParametersProperty(**{
                    "type": "string",
                    "description": "Конечная дата поиска YYYY-MM-DD (опционально)",
                }),
            },
            required=["query"],
        ),
        few_shot_examples=[
            {
                "request": "найди статьи про Docker",
                "params": {"query": "Docker контейнеры"},
            },
            {
                "request": "что нового по кибербезопасности за последний месяц",
                "params": {"query": "кибербезопасность", "date_from": "2026-05-01"},
            },
        ],
    ),
    GigaChatFunction(
        name="answer_from_rag",
        description=(
            "Ответить на вопрос по базе знаний Atlas. "
            "Возвращает развёрнутый ответ на основе содержимого статей и список источников. "
            "Вызывай когда пользователь хочет получить объяснение или ответ на конкретный вопрос, "
            "а не просто список статей."
        ),
        parameters=FunctionParameters(
            properties={
                "query": FunctionParametersProperty(**{
                    "type": "string",
                    "description": "Вопрос на естественном языке",
                }),
                "date_from": FunctionParametersProperty(**{
                    "type": "string",
                    "description": "Начальная дата поиска YYYY-MM-DD (опционально)",
                }),
                "date_to": FunctionParametersProperty(**{
                    "type": "string",
                    "description": "Конечная дата поиска YYYY-MM-DD (опционально)",
                }),
            },
            required=["query"],
        ),
        few_shot_examples=[
            {
                "request": "объясни что такое Kubernetes",
                "params": {"query": "как работает Kubernetes"},
            },
            {
                "request": "расскажи про безопасность контейнеров",
                "params": {"query": "безопасность Docker и Kubernetes контейнеров"},
            },
        ],
    ),
    GigaChatFunction(
        name="lookup_glossary",
        description=(
            "Найти определение специфичного банковского или IT-термина в глоссарии Atlas. "
            "Вызывай перед поиском если запрос содержит узкоспециальный термин из банковской сферы "
            "(РВПС, НПЛ, ОВП, кредитный конвейер, скоринг и др.) чтобы уточнить его значение "
            "и синонимы для более точного поиска."
        ),
        parameters=FunctionParameters(
            properties={
                "term": FunctionParametersProperty(**{
                    "type": "string",
                    "description": "Термин для поиска в глоссарии",
                }),
            },
            required=["term"],
        ),
        few_shot_examples=[
            {
                "request": "найди статьи про РВПС",
                "params": {"term": "РВПС"},
            },
            {
                "request": "расскажи про производственный процесс в банке",
                "params": {"term": "производственный процесс"},
            },
        ],
    ),
]


# ──────────────────────────────────────────────────────────────
# Вспомогательные функции
# ──────────────────────────────────────────────────────────────

def _truncate_for_api(sdk_messages: List[Messages]) -> List[Messages]:
    """
    Возвращает [SYSTEM] + последние MAX_CONTEXT_MESSAGES non-system сообщений.

    sdk_messages[0] всегда SYSTEM. Обрезка применяется перед каждым вызовом GigaChat
    чтобы не превышать контекстное окно модели при длинных диалогах.
    Полная история в sdk_messages сохраняется и возвращается фронтенду в done-событии.
    """
    system_msg = sdk_messages[0]
    rest = sdk_messages[1:]
    if len(rest) > MAX_CONTEXT_MESSAGES:
        logger.debug(
            "[агент] обрезка контекста: %d → %d сообщений",
            len(rest), MAX_CONTEXT_MESSAGES,
        )
        rest = rest[-MAX_CONTEXT_MESSAGES:]
    return [system_msg] + rest


def ensure_pro_model(model: str) -> str:
    """
    Апгрейдит GigaChat-Lite → GigaChat-Pro.
    GigaChat-Lite не поддерживает function calling.
    """
    if (model or "").strip() in _LITE_MODELS:
        logger.info(
            "Модель %r не поддерживает function calling → переключаю на GigaChat-Pro",
            model,
        )
        return "GigaChat-Pro"
    return model


def dispatch_tool(
    name: str,
    args: dict,
    gigachat_credentials: str = "",
    gigachat_model: str = "",
):
    """
    Маршрутизатор вызовов тулов.

    Возвращает:
        str   — для текстовых результатов (get_article)
        list  — для структурированных результатов (search_articles)
        dict  — для структурированных результатов (answer_from_rag, lookup_glossary)
    """
    if name == "get_article":
        link = args.get("link", "")
        result = get_article(link)
        if not result:
            return f"Статья по ссылке '{link}' не найдена в базе знаний Atlas."
        return result

    if name == "search_articles":
        results = search_articles(
            query=args.get("query", ""),
            date_from=args.get("date_from"),
            date_to=args.get("date_to"),
        )
        return results  # list[dict], может быть пустым — агент сам сообщит об отсутствии результатов

    if name == "answer_from_rag":
        return answer_from_rag(
            query=args.get("query", ""),
            date_from=args.get("date_from"),
            date_to=args.get("date_to"),
            gigachat_credentials=gigachat_credentials,
            gigachat_model=gigachat_model,
        )  # {"answer": str, "sources": list[dict]}

    if name == "lookup_glossary":
        term = args.get("term", "")
        result = lookup_glossary(term=term)
        if result is None:
            return {"found": False, "term": term}
        return {"found": True, **result}

    logger.warning("dispatch_tool: неизвестный тул %r (args=%s)", name, args)
    return f"Тул '{name}' не найден. Доступные тулы: get_article, search_articles, answer_from_rag, lookup_glossary."


def _to_sdk_messages(messages: List[Dict[str, Any]]) -> List[Messages]:
    """
    Конвертирует list[dict] → list[Messages] (SDK-модели).
    Добавляет SYSTEM_PROMPT в начало.
    """
    today = date.today().isoformat()
    system_content = f"**Сегодняшняя дата:** {today}\n\n{SYSTEM_PROMPT}"
    result: List[Messages] = [
        Messages(role=MessagesRole.SYSTEM, content=system_content)
    ]
    for msg in messages:
        role_str = msg.get("role", "user")
        content = str(msg.get("content") or "")
        name = msg.get("name")
        fc_raw = msg.get("function_call")

        try:
            role = MessagesRole(role_str)
        except ValueError:
            role = MessagesRole.USER

        if fc_raw and isinstance(fc_raw, dict):
            result.append(Messages(
                role=role,
                content=content,
                function_call=FunctionCall(
                    name=fc_raw["name"],
                    arguments=fc_raw.get("arguments"),
                ),
                name=name,
            ))
        else:
            result.append(Messages(role=role, content=content, name=name))

    return result


def _to_dict_messages(sdk_messages: List[Messages]) -> List[Dict[str, Any]]:
    """
    Конвертирует list[Messages] → list[dict].
    Системный промпт не включается (он не нужен фронтенду).
    """
    result = []
    for msg in sdk_messages:
        role = msg.role if isinstance(msg.role, str) else msg.role.value
        if role == "system":
            continue

        d: Dict[str, Any] = {"role": role, "content": msg.content or ""}

        if msg.name:
            d["name"] = msg.name

        if msg.function_call:
            d["function_call"] = {
                "name": msg.function_call.name,
                "arguments": msg.function_call.arguments,
            }

        result.append(d)

    return result


# ──────────────────────────────────────────────────────────────
# Основная функция
# ──────────────────────────────────────────────────────────────

def run_chat_agent(
    messages: List[Dict[str, Any]],
    gigachat_credentials: str,
    gigachat_model: str,
) -> Generator[Dict[str, Any], None, None]:
    """
    ReAct-цикл агента. Генерирует события по мере работы.

    Аргументы:
        messages:             история диалога без системного промпта (list[dict])
        gigachat_credentials: API-ключ GigaChat
        gigachat_model:       название модели (автоапгрейд Lite → Pro)

    Генерирует события:
        {"type": "tool_start", "tool": str, "args": dict}
        {"type": "tool_done",  "tool": str}
        {"type": "done", "answer": str, "sources": list, "messages": list[dict]}

    Пример использования (MVP):
        events = list(run_chat_agent(messages, creds, model))
        result = events[-1]  # type == "done"
    """
    model = ensure_pro_model(gigachat_model)
    client = create_gigachat_client(credentials=gigachat_credentials, model=model)

    sdk_messages = _to_sdk_messages(messages)
    accumulated_sources: List[Dict[str, Any]] = []

    with client:
        for iteration in range(1, MAX_ITERATIONS + 1):
            logger.info("[агент] итерация %d / %d", iteration, MAX_ITERATIONS)

            response = client.chat(Chat(
                messages=_truncate_for_api(sdk_messages),
                functions=TOOLS_SCHEMA,
                temperature=0.1,
            ))

            choice = response.choices[0]
            finish_reason = choice.finish_reason

            # ── Агент хочет вызвать тул ──────────────────────────────────────
            if finish_reason == "function_call":
                fc = choice.message.function_call
                name = fc.name
                args = fc.arguments or {}

                logger.info("[агент] тул: %s  args: %s", name, args)
                yield {"type": "tool_start", "tool": name, "args": args}

                # Записываем запрос агента в историю
                sdk_messages.append(Messages(
                    role=MessagesRole.ASSISTANT,
                    content="",
                    function_call=FunctionCall(name=name, arguments=args),
                ))

                # Выполняем тул
                tool_result = dispatch_tool(
                    name, args,
                    gigachat_credentials=gigachat_credentials,
                    gigachat_model=model,
                )

                # Накапливаем источники из answer_from_rag и search_articles
                if name == "answer_from_rag" and isinstance(tool_result, dict):
                    accumulated_sources.extend(tool_result.get("sources", []))
                elif name == "search_articles" and isinstance(tool_result, list):
                    seen_links = {s["link"] for s in accumulated_sources}
                    for article in tool_result:
                        link = article.get("link")
                        if link and link not in seen_links:
                            accumulated_sources.append({
                                "title": article.get("title", ""),
                                "link": link,
                                "published_at": article.get("published_at", ""),
                                "snippet": article.get("summary", ""),
                                "article_id": article.get("article_id"),
                            })
                            seen_links.add(link)

                logger.info(
                    "[агент] тул %s → %s",
                    name,
                    f"{len(tool_result)} симв." if isinstance(tool_result, str)
                    else f"{len(tool_result)} элементов",
                )

                # Записываем результат в историю.
                # GigaChat требует content в виде JSON-строки:
                #   str  → {"result": "текст"}
                #   list/dict → сериализуем напрямую (структурированные данные)
                if isinstance(tool_result, str):
                    content_json = json.dumps({"result": tool_result}, ensure_ascii=False)
                else:
                    content_json = json.dumps(tool_result, ensure_ascii=False, default=str)
                sdk_messages.append(Messages(
                    role=MessagesRole.FUNCTION,
                    name=name,
                    content=content_json,
                ))

                yield {"type": "tool_done", "tool": name}

            # ── Финальный текстовый ответ ────────────────────────────────────
            elif finish_reason in ("stop", None):
                answer = choice.message.content or ""
                logger.info("[агент] финальный ответ: %d симв.", len(answer))

                sdk_messages.append(Messages(
                    role=MessagesRole.ASSISTANT,
                    content=answer,
                ))

                yield {
                    "type": "done",
                    "answer": answer,
                    "sources": accumulated_sources,
                    "messages": _to_dict_messages(sdk_messages),
                }
                return

            else:
                logger.warning(
                    "[агент] неожиданный finish_reason: %r — прерываю цикл",
                    finish_reason,
                )
                break

    # ── Аварийный выход: превышен MAX_ITERATIONS ─────────────────────────────
    logger.warning("[агент] превышен MAX_ITERATIONS=%d", MAX_ITERATIONS)
    yield {
        "type": "done",
        "answer": (
            "Запрос слишком сложный для одного прохода. "
            "Попробуйте разбить его на несколько вопросов."
        ),
        "sources": accumulated_sources,
        "messages": _to_dict_messages(sdk_messages),
    }


# ──────────────────────────────────────────────────────────────
# Запуск из терминала
# ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import os

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    query = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "Привет! Что ты умеешь?"

    credentials = os.environ.get("GIGACHAT_CREDENTIALS", "")
    model = os.environ.get("GIGACHAT_MODEL", "")
    if not credentials or not model:
        try:
            from config.config import GIGACHAT_CREDENTIALS, GIGACHAT_MODEL
            credentials = credentials or GIGACHAT_CREDENTIALS
            model = model or GIGACHAT_MODEL
        except ImportError:
            pass

    if not credentials:
        print("❌ GIGACHAT_CREDENTIALS не задан. Передайте через env или config.")
        sys.exit(1)

    print(f"Вопрос: {query}\n{'─' * 60}")

    initial_messages = [{"role": "user", "content": query}]

    for event in run_chat_agent(initial_messages, credentials, model or "GigaChat-Pro"):
        if event["type"] == "tool_start":
            print(f"🔧 Вызов тула: {event['tool']}  args={event.get('args')}")
        elif event["type"] == "tool_done":
            print(f"✅ Тул {event['tool']} завершён")
        elif event["type"] == "done":
            print(f"\n{'─' * 60}\n💬 Ответ:\n{event['answer']}")
