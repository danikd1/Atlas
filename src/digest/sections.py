"""
Раскладка кластеров по разделам дайджеста.

По primary_type (trend / method / tool / case_study) относим каждый кластер
в соответствующий раздел; ограничиваем число кластеров и статей на кластер.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Set

# Маппинг primary_type -> ключ раздела в выводе
SECTION_KEY_BY_TYPE = {
    "trend": "key_trends",
    "method": "methods",
    "tool": "tools",
    "case_study": "case_studies",
}


@dataclass
class ArticleRef:
    """Ссылка на статью в разделе дайджеста."""
    link: str
    title: str
    published_at: Any = None


@dataclass
class ClusterInfo:
    """Информация о кластере после LLM: заголовок, описание и тип."""
    cluster_id: int
    label: str  # короткий заголовок (3–7 слов) от LLM
    description: str
    primary_type: str  # trend | method | tool | case_study
    articles: List[ArticleRef]  # уникальные статьи (по link) в этом кластере
    size: int = 0  # число чанков в кластере (для сортировки)


def assign_clusters_to_sections(
    cluster_infos: List[ClusterInfo],
    max_items_per_section: int = 5,
    max_articles_per_cluster: int = 3,
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Раскладывает кластеры по четырём разделам дайджеста.

    В каждом разделе — до max_items_per_section кластеров, у каждого
    до max_articles_per_cluster статей. Кластеры в разделе сортируются по size (убывание).

    Returns:
        {
            "key_trends": [ {"label": str, "description": str, "articles": [{"link", "title", "published_at"}] }, ... ],
            "methods": [ ... ],
            "tools": [ ... ],
            "case_studies": [ ... ],
        }
    """
    by_section: Dict[str, List[ClusterInfo]] = {
        "key_trends": [],
        "methods": [],
        "tools": [],
        "case_studies": [],
    }

    for info in cluster_infos:
        key = SECTION_KEY_BY_TYPE.get(info.primary_type)
        if key is None:
            key = "key_trends"  # fallback
        by_section[key].append(info)

    out: Dict[str, List[Dict[str, Any]]] = {
        "key_trends": [],
        "methods": [],
        "tools": [],
        "case_studies": [],
    }

    for section_key, infos in by_section.items():
        # Сортируем по размеру кластера (больше чанков — выше)
        infos_sorted = sorted(infos, key=lambda x: x.size, reverse=True)
        used_links: Set[str] = set()  # в рамках раздела каждая статья только один раз
        for info in infos_sorted[:max_items_per_section]:
            # Берём только статьи, которые ещё не встречались в этом разделе
            articles = []
            for a in info.articles[:max_articles_per_cluster]:
                if a.link not in used_links:
                    articles.append({"link": a.link, "title": a.title, "published_at": a.published_at})
                    used_links.add(a.link)
            # Пропускаем пункт, если после дедупликации не осталось статей (все уже были выше)
            if not articles:
                continue
            label = (info.label or info.description[:60] or "").strip()
            if not label and info.description:
                label = info.description[:60] + ("..." if len(info.description) > 60 else "")
            out[section_key].append({
                "label": label,
                "description": info.description,
                "articles": articles,
            })

    return out
