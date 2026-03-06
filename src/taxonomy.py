"""
Модуль работы с таксономией: загрузка и выбор ключевых слов по узлам D/GA/A.

Таксономия — иерархия: Discipline (D) → Group of Activities (GA) → Activity (A).
Агент-taxonomy по запросу пользователя возвращает выбранные узлы (discipline, ga, activity);
по ним собираются наборы ключевых слов для фильтрации статей.
"""
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple

logger = logging.getLogger(__name__)


def get_taxonomy_path(taxonomy_file: Optional[str] = None) -> Path:
    """
    Возвращает путь к файлу таксономии.

    Args:
        taxonomy_file: Путь к файлу. Если None — data/taxonomy.json в корне проекта.

    Returns:
        Path к файлу таксономии.
    """
    if taxonomy_file:
        return Path(taxonomy_file)
    project_root = Path(__file__).parent.parent
    return project_root / "data" / "taxonomy.json"


def load_taxonomy(taxonomy_file: Optional[str] = None) -> Dict[str, Any]:
    """
    Загружает таксономию из JSON.

    Args:
        taxonomy_file: Путь к файлу. Если None — data/taxonomy.json.

    Returns:
        Словарь с ключами: version, blacklist, disciplines (список D с groups и activities).

    Raises:
        FileNotFoundError: Файл не найден.
        json.JSONDecodeError: Некорректный JSON.
    """
    path = get_taxonomy_path(taxonomy_file)
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if "disciplines" not in data:
        raise ValueError("В таксономии отсутствует ключ 'disciplines'")
    logger.info("Загружена таксономия: %s", path)
    return data


def _collect_keywords_from_node(node: Dict[str, Any]) -> List[str]:
    """Собирает ключевые слова из узла (D, GA или A)."""
    raw = node.get("keywords") or []
    return [str(k).strip().lower() for k in raw if k and isinstance(k, str)]


def _collect_topic_descriptions_from_node(node: Dict[str, Any]) -> List[str]:
    """Собирает описания топиков из узла (D, GA или A)."""
    raw = node.get("topic_descriptions") or []
    return [str(t).strip() for t in raw if t and isinstance(t, str)]


def get_topic_descriptions_per_node(
    taxonomy: Dict[str, Any],
    selection: Optional[Dict[str, Optional[str]]] = None,
) -> List[Tuple[str, List[str]]]:
    """
    Собирает описания топиков по каждому выбранному узлу отдельно (D, GA, A).
    У каждого узла свой список описаний, без объединения в один.

    Args:
        taxonomy: Загруженная таксономия (результат load_taxonomy).
        selection: Словарь с ключами discipline, ga, activity.

    Returns:
        Список пар (node_id, list of topic_descriptions) для каждого узла,
        у которого есть хотя бы одно описание. Порядок: D → GA → A.
    """
    selection = selection or {}
    discipline_id = selection.get("discipline")
    ga_id = selection.get("ga")
    activity_id = selection.get("activity")

    result: List[Tuple[str, List[str]]] = []

    disciplines = taxonomy.get("disciplines") or []
    for d in disciplines:
        if d.get("id") != discipline_id:
            continue
        desc_d = _collect_topic_descriptions_from_node(d)
        if desc_d:
            result.append((d.get("id", ""), desc_d))
        if ga_id is not None:
            for g in (d.get("groups") or []):
                if g.get("id") != ga_id:
                    continue
                desc_g = _collect_topic_descriptions_from_node(g)
                if desc_g:
                    result.append((g.get("id", ""), desc_g))
                if activity_id is not None:
                    for a in (g.get("activities") or []):
                        if a.get("id") == activity_id:
                            desc_a = _collect_topic_descriptions_from_node(a)
                            if desc_a:
                                result.append((a.get("id", ""), desc_a))
                            break
                break
        break

    return result


def get_keywords_config_for_selection(
    taxonomy: Dict[str, Any],
    selection: Optional[Dict[str, Optional[str]]] = None,
) -> Dict[str, List[str]]:
    """
    Собирает конфиг ключевых слов для фильтрации по выбранным узлам таксономии.

    Выбранные узлы задаются полями discipline, ga, activity (каждый может быть null).
    Ключевые слова собираются с выбранных узлов и объединяются в список strong.
    weak не заполняется (оставлен для совместимости с форматом фильтра).
    blacklist берётся из корня таксономии.

    Args:
        taxonomy: Загруженная таксономия (результат load_taxonomy).
        selection: Словарь с ключами discipline, ga, activity.
                   Пример: {"discipline": "D1", "ga": "GA2", "activity": "A5"}.
                   Если None или пустой — возвращается конфиг с пустыми strong/weak и blacklist из таксономии.

    Returns:
        Словарь в формате для фильтра: {"strong": [...], "weak": [], "blacklist": [...]}.
    """
    selection = selection or {}
    discipline_id = selection.get("discipline")
    ga_id = selection.get("ga")
    activity_id = selection.get("activity")

    strong: List[str] = []
    seen = set()

    def add_keywords(keywords: List[str]) -> None:
        for k in keywords:
            k = k.strip().lower()
            if k and k not in seen:
                seen.add(k)
                strong.append(k)

    disciplines = taxonomy.get("disciplines") or []
    for d in disciplines:
        if d.get("id") != discipline_id:
            continue
        add_keywords(_collect_keywords_from_node(d))
        if ga_id is not None:
            for g in (d.get("groups") or []):
                if g.get("id") != ga_id:
                    continue
                add_keywords(_collect_keywords_from_node(g))
                if activity_id is not None:
                    for a in (g.get("activities") or []):
                        if a.get("id") == activity_id:
                            add_keywords(_collect_keywords_from_node(a))
                            break
                break
        break

    blacklist_raw = taxonomy.get("blacklist") or []
    blacklist = [str(b).strip().lower() for b in blacklist_raw if b and isinstance(b, str)]

    return {
        "strong": strong,
        "weak": [],
        "blacklist": blacklist,
    }


def get_collection_display_name(
    taxonomy: Dict[str, Any],
    selection: Optional[Dict[str, Optional[str]]] = None,
) -> str:
    """
    Собирает отображаемое имя коллекции по selection из таксономии.

    Формат: "D1 / GA1 / A1 — Имя активности" или "D1 / GA1 — Имя GA", "D1 — Имя дисциплины".

    Args:
        taxonomy: Загруженная таксономия (load_taxonomy).
        selection: Словарь с ключами discipline, ga, activity.

    Returns:
        Строка для отображения в UI, например "D1 / GA1 / A1 — Определение границ MVP".
    """
    selection = selection or {}
    discipline_id = selection.get("discipline")
    ga_id = selection.get("ga")
    activity_id = selection.get("activity")

    parts: List[str] = []
    name_suffix = ""

    for d in taxonomy.get("disciplines") or []:
        if d.get("id") != discipline_id:
            continue
        parts.append(f"{d['id']}")
        name_suffix = d.get("name") or ""
        if ga_id is not None:
            for g in (d.get("groups") or []):
                if g.get("id") != ga_id:
                    continue
                parts.append(f"{g['id']}")
                name_suffix = g.get("name") or ""
                if activity_id is not None:
                    for a in (g.get("activities") or []):
                        if a.get("id") == activity_id:
                            parts.append(f"{a['id']}")
                            name_suffix = a.get("name") or ""
                            break
                break
        break

    if not parts:
        return "—"
    return " / ".join(parts) + (" — " + name_suffix if name_suffix else "")


def format_taxonomy_for_router_prompt(taxonomy: Dict[str, Any]) -> str:
    """
    Формирует блок «Предметная область» для системного промпта роутера из таксономии.
    Используются name, topic_descriptions (как описание), keywords и example_queries (у активностей).
    """
    lines: List[str] = []
    for d in taxonomy.get("disciplines") or []:
        lines.append(f"{d['id']}. {d['name']}")
        desc = _collect_topic_descriptions_from_node(d)
        if desc:
            lines.append(f"  Описание: {' '.join(desc)}")
        kw = _collect_keywords_from_node(d)
        if kw:
            lines.append(f"  Ключевые слова: {', '.join(kw)}")
        for g in d.get("groups") or []:
            lines.append(f"  {g['id']}. {g['name']}")
            g_desc = _collect_topic_descriptions_from_node(g)
            if g_desc:
                lines.append(f"    Описание: {' '.join(g_desc)}")
            g_kw = _collect_keywords_from_node(g)
            if g_kw:
                lines.append(f"    Ключевые слова: {', '.join(g_kw)}")
            for a in g.get("activities") or []:
                a_desc = _collect_topic_descriptions_from_node(a)
                part = f"    {a['id']}. {a['name']}"
                if a_desc:
                    part += f" — {' '.join(a_desc)}"
                lines.append(part)
                a_kw = _collect_keywords_from_node(a)
                if a_kw:
                    lines.append(f"      Ключевые слова: {', '.join(a_kw)}")
                eq = a.get("example_queries") or []
                eq = [str(q).strip() for q in eq if q and isinstance(q, str)][:5]
                if eq:
                    lines.append(f"      Примеры запросов: {'; '.join(eq)}")
        lines.append("")
    return "\n".join(lines).strip()
