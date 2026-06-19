"""
Task 2.5: тесты финализации агента.

  1. Unit-тест обрезки контекста (_truncate_for_api)
  2. Сценарий: search_articles  — «найди статьи про микросервисы»
  3. Сценарий: answer_from_rag  — «объясни что такое Docker»
  4. Сценарий: lookup_glossary → search_articles — «производственный процесс в банке»

Запуск:
    python3 tests/test_agent_finalization.py
"""
import os, sys, logging
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
logging.basicConfig(level=logging.WARNING)

from gigachat.models.chat import Messages, MessagesRole

from src.chat.agent import (
    MAX_CONTEXT_MESSAGES,
    _truncate_for_api,
    _to_sdk_messages,
    run_chat_agent,
)
from config.config import GIGACHAT_CREDENTIALS, GIGACHAT_MODEL


# ── 1. Unit-тест обрезки ────────────────────────────────────────

def test_truncation():
    # Строим список: SYSTEM + 30 user-сообщений
    raw = [{"role": "user", "content": f"msg {i}"} for i in range(30)]
    sdk = _to_sdk_messages(raw)
    assert sdk[0].role == MessagesRole.SYSTEM, "первое сообщение должно быть SYSTEM"

    truncated = _truncate_for_api(sdk)
    assert truncated[0].role == MessagesRole.SYSTEM, "SYSTEM сохраняется"
    assert len(truncated) == MAX_CONTEXT_MESSAGES + 1, (
        f"ожидали {MAX_CONTEXT_MESSAGES + 1}, получили {len(truncated)}"
    )
    # Последнее сообщение = msg 29 (самое свежее)
    assert truncated[-1].content == "msg 29"
    # Первое non-system = msg 10 (30 - 20 = 10)
    assert truncated[1].content == "msg 10"

    # Не обрезает если сообщений меньше лимита
    short = _to_sdk_messages([{"role": "user", "content": "только одно"}])
    assert _truncate_for_api(short) == short

    print("✅ _truncate_for_api: обрезка корректна")


# ── Вспомогательная функция для живых тестов ───────────────────

def run_agent(query: str):
    msgs = [{"role": "user", "content": query}]
    events = list(run_chat_agent(msgs, GIGACHAT_CREDENTIALS, GIGACHAT_MODEL))
    tools_called = [e["tool"] for e in events if e["type"] == "tool_start"]
    done = next(e for e in events if e["type"] == "done")
    return tools_called, done


# ── 2. search_articles ──────────────────────────────────────────

def test_search_articles():
    tools, done = run_agent("найди статьи про микросервисы")
    assert "search_articles" in tools, f"ожидали search_articles, получили: {tools}"
    assert done["answer"], "ответ не должен быть пустым"
    print(f"✅ search_articles: тулы={tools}, ответ={done['answer'][:80]}...")


# ── 3. answer_from_rag ─────────────────────────────────────────

def test_answer_from_rag():
    tools, done = run_agent("объясни подробно что такое Docker и как он работает")
    assert "answer_from_rag" in tools, f"ожидали answer_from_rag, получили: {tools}"
    assert done["answer"], "ответ не должен быть пустым"
    print(f"✅ answer_from_rag: тулы={tools}, ответ={done['answer'][:80]}...")


# ── 4. lookup_glossary → search_articles ───────────────────────

def test_glossary_then_search():
    tools, done = run_agent("найди статьи про производственный процесс в банке")
    assert "lookup_glossary" in tools, f"ожидали lookup_glossary, получили: {tools}"
    assert done["answer"], "ответ не должен быть пустым"
    print(f"✅ lookup_glossary→search: тулы={tools}, ответ={done['answer'][:80]}...")


# ── Запуск ─────────────────────────────────────────────────────

if __name__ == "__main__":
    print("\n── Unit-тест обрезки ──────────────────────")
    test_truncation()

    if not GIGACHAT_CREDENTIALS:
        print("⚠️  GIGACHAT_CREDENTIALS не задан — живые тесты пропущены")
        sys.exit(0)

    print("\n── Живые сценарии ─────────────────────────")
    test_search_articles()
    test_answer_from_rag()
    test_glossary_then_search()
    print("\n✅ Все тесты прошли")
