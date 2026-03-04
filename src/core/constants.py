"""
Константы и перечисления для проекта.
"""
from enum import Enum


class RelevanceStatus(str, Enum):
    """Статусы релевантности статей."""
    RELEVANT = "relevant"
    IRRELEVANT = "irrelevant"
    NEED_FULLTEXT = "need_fulltext"
    
    def __str__(self) -> str:
        return self.value

