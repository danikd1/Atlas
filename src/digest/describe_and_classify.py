"""
Описание и классификация кластера через LLM.

Один вызов на кластер: по 3–7 типичным чанкам возвращаем короткое описание темы
и тип контента (trend / method / tool / case_study) для раскладки по разделам дайджеста.
"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List

from src.digest.load_chunks import ChunkRow
from src.tools.llm_utils import clean_text_for_llm, create_gigachat_client

logger = logging.getLogger(__name__)

SECTION_TYPES = ("trend", "method", "tool", "case_study")


def _build_cluster_prompt(chunk_texts: List[str], language: str = "ru") -> list[dict[str, str]]:
    """Строит messages для GigaChat: короткий заголовок, описание темы и тип."""
    max_chars_per_snippet = 400
    lines: List[str] = []
    for i, raw in enumerate(chunk_texts, 1):
        clean = clean_text_for_llm(raw or "", max_chars=max_chars_per_snippet)
        if clean:
            lines.append(f"[{i}] {clean}")
    context = "\n\n".join(lines).strip() or "(нет текста)"

    type_rubric_en = (
        "When choosing TYPE, use this rubric:\n"
        "- trend: what is changing or gaining weight in the world (shifts in roles, user expectations, direction of the industry). Not 'how to do' but 'what is happening / where things are going'.\n"
        "- method: how people do things — methodologies, approaches, frameworks, ways of organizing work (research, prioritization, experiments). Focus on the 'way of doing', not a specific software.\n"
        "- tool: what people use — concrete tools, services, platforms (Jira, Figma, survey tools, analytics). Something you can 'take and use'.\n"
        "- case_study: examples from practice — company/team stories, 'how we implemented', 'how we measured', before/after. Concrete stories, not overview articles."
    )
    type_rubric_ru = (
        "При выборе TYPE руководствуйся правилами:\n"
        "- trend: что в мире меняется или набирает вес (сдвиги в ролях, ожиданиях пользователей, направление индустрии). Не «как сделать», а «что происходит / куда всё идёт».\n"
        "- method: как делают — методики, подходы, фреймворки, способы организации работы (исследования, приоритизация, эксперименты). Акцент на «способ», не на конкретный софт.\n"
        "- tool: чем делают — конкретные инструменты, сервисы, платформы (Jira, Figma, опросники, аналитика). То, что можно «взять и использовать».\n"
        "- case_study: примеры из практики — истории компаний/команд, «как мы внедрили», «как измерили», до/после. Конкретные истории, а не обзорные статьи."
    )

    if language == "en":
        system_msg = (
            "You analyze groups of article snippets for a digest. Reply with exactly three lines:\n"
            "1) TITLE: a short headline in 3-7 words (e.g. 'Product engineers and AI').\n"
            "2) DESCRIPTION: 2-3 sentences on the common theme.\n"
            "3) TYPE: exactly one word — trend, method, tool, or case_study.\n\n"
            f"{type_rubric_en}"
        )
        user_msg = (
            "Snippets from one cluster:\n\n"
            f"{context}\n\n"
            "Give TITLE (3-7 words), DESCRIPTION (2-3 sentences), TYPE (one of: trend, method, tool, case_study)."
        )
    else:
        system_msg = (
            "Ты анализируешь группы фрагментов статей для дайджеста. Ответь ровно тремя строками:\n"
            "1) TITLE: короткий заголовок на русском языке в 3–7 словах (например: «Продуктовые инженеры и ИИ»).\n"
            "2) DESCRIPTION: 2–3 предложения на русском языке об общей теме.\n"
            "3) TYPE: ровно одно слово — trend, method, tool или case_study.\n\n"
            "Важно: TITLE и DESCRIPTION всегда пиши на русском языке, даже если статьи на английском.\n\n"
            f"{type_rubric_ru}"
        )
        user_msg = (
            "Фрагменты из одного кластера:\n\n"
            f"{context}\n\n"
            "Дай TITLE (3–7 слов, на русском), DESCRIPTION (2–3 предложения, на русском), TYPE (одно: trend, method, tool, case_study)."
        )

    return [
        {"role": "system", "content": system_msg},
        {"role": "user", "content": user_msg},
    ]


def _parse_llm_response(content: str) -> Dict[str, Any]:
    """Парсит ответ LLM: TITLE, DESCRIPTION и TYPE. Учитывает форматы вроде '1) TITLE: ... 2) DESCRIPTION: ...'."""
    title = ""
    description = ""
    primary_type = "trend"
    text = content.strip()

    # Ищем подстроки TITLE:, DESCRIPTION:, TYPE: в любом месте ответа (LLM иногда нумерует "1) TITLE: ...")
    for marker, key in [
        ("TITLE:", "title"),
        ("DESCRIPTION:", "desc"),
        ("TYPE:", "type"),
    ]:
        pos = text.upper().find(marker)
        if pos >= 0:
            rest = text[pos + len(marker) :].strip()
            # Обрезаем до следующего маркера или до конца
            end = len(rest)
            for next_m in ("TITLE:", "DESCRIPTION:", "TYPE:"):
                if next_m == marker:
                    continue
                p = rest.upper().find(next_m)
                if p >= 0 and p < end:
                    end = p
            value = rest[:end].strip()
            # Убираем хвосты вида " 2)" или ". 3)" от нумерации LLM
            value = re.sub(r"\s*\d+\)\s*$", "", value).strip().rstrip(".")
            if key == "title":
                title = value
            elif key == "desc":
                description = value
            elif key == "type":
                for t in SECTION_TYPES:
                    if t in value.lower() or value.lower() == t:
                        primary_type = t
                        break

    # Fallback: построчный разбор по ключевым словам TITLE:/DESCRIPTION:/TYPE:
    if not title or not description:
        for line in content.split("\n"):
            line = line.strip()
            if not line:
                continue
            if line.upper().startswith("TITLE:") and not title:
                title = line.split(":", 1)[-1].strip()
            elif line.upper().startswith("DESCRIPTION:") and not description:
                description = line.split(":", 1)[-1].strip()
            elif line.upper().startswith("TYPE:") and primary_type == "trend":
                raw = line.split(":", 1)[-1].strip().lower()
                for t in SECTION_TYPES:
                    if t in raw or raw == t:
                        primary_type = t
                        break

    # Fallback: нумерованный формат "1) заголовок" "2) описание" "3) type" (без TITLE:/DESCRIPTION:)
    if not title or not description:
        lines = content.split("\n")
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            if not line:
                i += 1
                continue
            if re.match(r"^1\)", line):
                title = line[2:].strip().lstrip(".- ")
                if title.startswith("«") or title.startswith("'"):
                    title = title.strip()
                i += 1
            elif re.match(r"^2\)", line):
                parts = [line[2:].strip().lstrip(".- ")]
                i += 1
                while i < len(lines):
                    next_line = lines[i].strip()
                    if re.match(r"^[123]\)", next_line) or next_line.upper().startswith("TYPE:"):
                        break
                    if next_line:
                        parts.append(next_line)
                    i += 1
                description = "\n".join(parts).strip()
            elif re.match(r"^3\)", line):
                raw = line[2:].strip().lower().lstrip(".- ")
                if "type:" in raw:
                    raw = raw.split("type:", 1)[-1].strip()
                for t in SECTION_TYPES:
                    if t in raw or raw == t:
                        primary_type = t
                        break
                i += 1
            else:
                i += 1

    # Убираем из description нумерацию в начале строк ("1) ...", "2) ..."), если парсер оставил сырой вывод
    if description and re.match(r"^\d+\)", description.strip()):
        description = re.sub(r"^\d+\)\s*", "", description.strip(), count=1)
    description = re.sub(r"\n\s*\d+\)\s*", "\n", description or "").strip()

    if not description:
        description = content.strip()[:500]
    if not title:
        title = description[:50] + ("..." if len(description) > 50 else "")

    return {"title": title, "description": description, "primary_type": primary_type}


def describe_and_classify_cluster(
    chunk_texts: List[str],
    language: str = "ru",
    client=None,
) -> Dict[str, Any]:
    """
    По списку текстов чанков кластера возвращает описание темы и тип контента.

    Args:
        chunk_texts: тексты типичных чанков (например, text_payload или title + snippet).
        language: "ru" | "en".
        client: опционально уже созданный GigaChat-клиент.

    Returns:
        {"title": str, "description": str, "primary_type": "trend"|"method"|"tool"|"case_study"}.
    """
    if not chunk_texts:
        return {"description": "", "primary_type": "trend"}

    messages = _build_cluster_prompt(chunk_texts, language=language)
    if client is None:
        client = create_gigachat_client()

    try:
        result = client.chat({"messages": messages, "temperature": 0.2})
        text = (result.choices[0].message.content or "").strip()
        return _parse_llm_response(text)
    except Exception as e:
        logger.warning("describe_and_classify_cluster: LLM error %s", e)
        return {"title": "", "description": f"(ошибка: {e})", "primary_type": "trend"}


def describe_and_classify_cluster_from_chunks(
    chunks: List[ChunkRow],
    language: str = "ru",
    client=None,
    max_snippets: int = 5,
) -> Dict[str, Any]:
    """
    Удобная обёртка: по списку ChunkRow берёт text_payload (или title+summary)
    и вызывает describe_and_classify_cluster.
    """
    texts = []
    for c in chunks[:max_snippets]:
        t = (c.text_payload or "").strip()
        if not t and (c.title or c.summary):
            t = f"{c.title or ''}\n{c.summary or ''}".strip()
        if t:
            texts.append(t)
    return describe_and_classify_cluster(texts, language=language, client=client)
