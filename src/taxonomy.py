"""
Модуль работы с таксономией: загрузка и выбор ключевых слов по узлам D/GA/A.

Таксономия — иерархия: Discipline (D) → Group of Activities (GA) → Activity (A).
Агент-taxonomy по запросу пользователя возвращает выбранные узлы (discipline, ga, activity);
по ним собираются наборы ключевых слов для фильтрации статей.
"""
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any

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


def get_topic_descriptions_for_selection(
    taxonomy: Dict[str, Any],
    selection: Optional[Dict[str, Optional[str]]] = None,
) -> List[str]:
    """
    Собирает список описаний топиков (TOPIC_DESCRIPTIONS) для построения topic embedding
    по выбранным узлам таксономии (D / GA / A).

    Выбранные узлы задаются полями discipline, ga, activity (каждый может быть null).
    Описания собираются с выбранных узлов и объединяются в один список в порядке D → GA → A.

    Args:
        taxonomy: Загруженная таксономия (результат load_taxonomy).
        selection: Словарь с ключами discipline, ga, activity.
                   Пример: {"discipline": "D1", "ga": "GA2", "activity": "A5"}.

    Returns:
        Список строк — описания топиков для передачи в build_topic_embedding.
    """
    selection = selection or {}
    discipline_id = selection.get("discipline")
    ga_id = selection.get("ga")
    activity_id = selection.get("activity")

    descriptions: List[str] = []

    disciplines = taxonomy.get("disciplines") or []
    for d in disciplines:
        if d.get("id") != discipline_id:
            continue
        descriptions.extend(_collect_topic_descriptions_from_node(d))
        if ga_id is not None:
            for g in (d.get("groups") or []):
                if g.get("id") != ga_id:
                    continue
                descriptions.extend(_collect_topic_descriptions_from_node(g))
                if activity_id is not None:
                    for a in (g.get("activities") or []):
                        if a.get("id") == activity_id:
                            descriptions.extend(_collect_topic_descriptions_from_node(a))
                            break
                break
        break

    return descriptions


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
