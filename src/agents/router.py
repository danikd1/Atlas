# -*- coding: utf-8 -*-
"""
Роутер запросов по таксономии D/GA/A на LangGraph + GigaChat.

По запросу пользователя возвращает выбранные узлы (discipline, ga, activity)
или флаг уточнения; результат подставляется в TAXONOMY_SELECTION для пайплайна.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Optional

from langgraph.graph import END, START, StateGraph

from src.taxonomy import format_taxonomy_for_router_prompt, load_taxonomy

from .router_prompt import get_router_system_prompt

logger = logging.getLogger(__name__)

# Состояние графа роутера
RouterState = dict[str, Any]


def _call_router_llm(
    system_prompt: str,
    user_query: str,
    client: Any,
    temperature: float = 0.0,
) -> str:
    """Вызов GigaChat: системный промпт + запрос пользователя, возврат текста ответа."""
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_query.strip()},
    ]
    try:
        result = client.chat({"messages": messages, "temperature": temperature})
        return (result.choices[0].message.content or "").strip()
    except Exception as e:
        logger.exception("Ошибка вызова GigaChat в роутере: %s", e)
        raise


def _parse_router_response(text: str) -> Optional[dict[str, Any]]:
    """Извлекает JSON из ответа LLM (допускает обёртку в markdown или лишний текст)."""
    if not text:
        return None
    stripped = text.strip()
    start = stripped.find("{")
    if start < 0:
        try:
            return json.loads(stripped)
        except json.JSONDecodeError:
            return None
    depth = 0
    for i in range(start, len(stripped)):
        if stripped[i] == "{":
            depth += 1
        elif stripped[i] == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(stripped[start : i + 1])
                except json.JSONDecodeError:
                    break
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        return None


def _route_node(state: RouterState) -> RouterState:
    """
    Узел графа: вызов LLM с системным промптом и запросом пользователя, парсинг JSON.
    Заполняет response_json, selection (для пайплайна), clarification_needed, clarification_question.
    """
    client = state["gigachat_client"]
    system_prompt = state["system_prompt"]
    user_query = state["user_query"]

    raw = _call_router_llm(system_prompt, user_query, client)
    response_json = _parse_router_response(raw)

    out: RouterState = {
        "response_text": raw,
        "response_json": response_json,
        "selection": None,
        "clarification_needed": False,
        "clarification_question": None,
        "status": "not_found",
        "confidence": 0.0,
        "reasoning": None,
    }

    if not response_json:
        logger.warning("Роутер: не удалось распарсить JSON из ответа LLM")
        return out

    out["status"] = response_json.get("status") or "not_found"
    out["confidence"] = float(response_json.get("confidence") or 0)
    out["clarification_needed"] = bool(response_json.get("clarification_needed"))
    out["clarification_question"] = response_json.get("clarification_question")
    out["reasoning"] = response_json.get("reasoning")

    if out["status"] == "matched":
        out["selection"] = {
            "discipline": response_json.get("discipline"),
            "ga": response_json.get("ga"),
            "activity": response_json.get("activity"),
        }
    return out


def _build_router_graph():
    """Собирает граф: один узел route (LLM + парсинг)."""
    workflow = StateGraph(RouterState)
    workflow.add_node("route", _route_node)
    workflow.add_edge(START, "route")
    workflow.add_edge("route", END)
    return workflow.compile()


def router_output_to_taxonomy_selection(router_output: RouterState) -> Optional[dict[str, Optional[str]]]:
    """
    Преобразует вывод роутера в формат TAXONOMY_SELECTION для пайплайна.
    Возвращает None, если status != "matched" или selection отсутствует.
    """
    if router_output.get("status") != "matched":
        return None
    sel = router_output.get("selection")
    if not sel:
        return None
    discipline = sel.get("discipline")
    ga = sel.get("ga")
    activity = sel.get("activity")

    # Если агент выбрал A, но не указал GA/discipline — доопределяем их по таксономии.
    # Если указал GA, но не указал discipline — доопределяем discipline по таксономии.
    if activity or ga:
        taxonomy = load_taxonomy()
        disciplines = taxonomy.get("disciplines") or []

        # Сначала восстанавливаем GA и discipline по activity (если нужно)
        if activity and not ga:
            for d in disciplines:
                for g in d.get("groups") or []:
                    for a in g.get("activities") or []:
                        if a.get("id") == activity:
                            ga = g.get("id")
                            if not discipline:
                                discipline = d.get("id")
                            break
                    if ga:
                        break
                if ga:
                    break

        # Затем восстанавливаем discipline по GA (если нужно и всё ещё не определён)
        if ga and not discipline:
            for d in disciplines:
                for g in d.get("groups") or []:
                    if g.get("id") == ga:
                        discipline = d.get("id")
                        break
                if discipline:
                    break

    # Если вообще ничего не выбрано (все None) — считаем, что выбора нет
    if not (discipline or ga or activity):
        return None

    return {
        "discipline": discipline,
        "ga": ga,
        "activity": activity,
    }


def format_router_result_for_display(router_out: RouterState) -> str:
    """Форматирует результат роутера для вывода в консоль (режим теста без пайплайна)."""
    lines = [
        "",
        "=" * 60,
        "РЕЗУЛЬТАТ АГЕНТА-РОУТЕРА",
        "=" * 60,
        f"Запрос: {router_out.get('user_query', '')}",
        f"Статус: {router_out.get('status', '?')}",
        f"Уверенность (confidence): {router_out.get('confidence', 0):.2f}",
        "",
    ]
    sel = router_out.get("selection")
    if sel:
        lines.append("Выбранные узлы:")
        lines.append(f"  D (discipline): {sel.get('discipline')}")
        lines.append(f"  GA:             {sel.get('ga')}")
        lines.append(f"  A (activity):   {sel.get('activity')}")
        lines.append("")
    if router_out.get("clarification_needed") and router_out.get("clarification_question"):
        lines.append("Требуется уточнение:")
        lines.append(f"  {router_out['clarification_question']}")
        lines.append("")
    reasoning = router_out.get("reasoning")
    if reasoning:
        lines.append("Почему выбран этот узел:")
        lines.append(f"  {reasoning}")
        lines.append("")
    lines.append("=" * 60)
    return "\n".join(lines)


def run_router(
    user_query: str,
    taxonomy: Optional[dict[str, Any]] = None,
    gigachat_client: Optional[Any] = None,
) -> RouterState:
    """
    Запускает роутер: по запросу пользователя возвращает выбранные узлы D/GA/A или уточнение.

    Args:
        user_query: Запрос пользователя на естественном языке.
        taxonomy: Таксономия (если None — загружается из data/taxonomy.json).
        gigachat_client: Клиент GigaChat (если None — создаётся через create_gigachat_client).

    Returns:
        Состояние с ключами: selection (dict | None), status, confidence,
        clarification_needed, clarification_question, response_json, ...
    """
    if taxonomy is None:
        taxonomy = load_taxonomy()
    domain_block = format_taxonomy_for_router_prompt(taxonomy)
    system_prompt = get_router_system_prompt(domain_block)

    if gigachat_client is None:
        from src.tools.llm_utils import create_gigachat_client
        gigachat_client = create_gigachat_client()

    graph = _build_router_graph()
    initial: RouterState = {
        "user_query": user_query,
        "system_prompt": system_prompt,
        "gigachat_client": gigachat_client,
        "response_text": "",
        "response_json": None,
        "selection": None,
        "clarification_needed": False,
        "clarification_question": None,
        "status": "not_found",
        "confidence": 0.0,
        "reasoning": None,
    }
    result = graph.invoke(initial)
    return result


if __name__ == "__main__":
    """Запуск только роутера для теста: python3 -m src.agents.router 'ваш запрос'"""
    import sys
    if len(sys.argv) < 2:
        print("Использование: python3 -m src.agents.router \"ваш запрос\"", file=sys.stderr)
        sys.exit(1)
    query = " ".join(sys.argv[1:]).strip()
    if not query:
        print("Укажите непустой запрос.", file=sys.stderr)
        sys.exit(1)
    print("🤖 Запрос к агенту-роутеру...")
    out = run_router(query)
    print(format_router_result_for_display(out))
