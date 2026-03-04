"""
Модуль фильтрации статей с использованием лемматизации.

Обеспечивает:
- Лемматизацию текста с помощью pymorphy3
- Boolean-фильтрацию по ключевым словам (strong/weak/blacklist)
- Подготовку лемм для фильтрации с исключением слишком общих терминов
"""
import logging
import re
import time
from typing import Dict, List, Optional, Tuple

import pandas as pd
from pymorphy3 import MorphAnalyzer

from .taxonomy import get_keywords_config_for_selection, load_taxonomy

logger = logging.getLogger(__name__)

# Инициализация морфологического анализатора
_morph_analyzer = None


def get_morph_analyzer() -> MorphAnalyzer:
    """
    Получает или создает экземпляр морфологического анализатора.
    Используется lazy initialization для оптимизации.
    """
    global _morph_analyzer
    if _morph_analyzer is None:
        try:
            _morph_analyzer = MorphAnalyzer()
        except Exception as e:
            logger.error(f"Ошибка инициализации морфологического анализатора: {e}")
            raise
    return _morph_analyzer


def tokenize(text: str) -> List[str]:
    """
    Токенизирует текст, извлекая слова и числа.
    
    Args:
        text: Входной текст
        
    Returns:
        Список токенов
    """
    if not text:
        return []
    return re.findall(r"[A-Za-zА-Яа-яЁё0-9]+", text.lower())


def lemmatize_token(token: str) -> str:
    """
    Лемматизирует один токен.
    
    Args:
        token: Токен для лемматизации
        
    Returns:
        Лемма токена
    """
    if not token:
        return token
    
    try:
        morph = get_morph_analyzer()
        p = morph.parse(token)
        if not p:
            return token
        return p[0].normal_form
    except Exception as e:
        logger.debug(f"Ошибка лемматизации токена '{token}': {e}")
        return token


def lemmatize_text(text: str) -> str:
    """
    Лемматизирует весь текст.
    
    Args:
        text: Входной текст
        
    Returns:
        Текст с лемматизированными словами, разделенными пробелами
    """
    if not text:
        return ""
    
    tokens = tokenize(text)
    lemmas = [lemmatize_token(t) for t in tokens]
    return " ".join(lemmas)


def lemmatize_phrase(phrase: str) -> str:
    """
    Лемматизирует фразу (ключевое слово/фразу).
    
    Args:
        phrase: Фраза для лемматизации
        
    Returns:
        Лемматизированная фраза
    """
    if not phrase:
        return ""
    
    tokens = tokenize(phrase)
    lemmas = [lemmatize_token(t) for t in tokens]
    return " ".join(lemmas)


def prepare_strong_lemmas_for_bool_filter(
    strong_keywords: List[str],
    generic_single_lemmas: Optional[set] = None
) -> Tuple[List[str], List[str]]:
    """
    Подготавливает список сильных лемм для Boolean-фильтра,
    исключая слишком общие однословные леммы.
    
    Args:
        strong_keywords: Список сильных ключевых слов
        generic_single_lemmas: Множество слишком общих однословных лемм
        
    Returns:
        Tuple[все_леммы, леммы_для_фильтра]
    """
    if generic_single_lemmas is None:
        from config.config import GENERIC_SINGLE_LEMMAS
        generic_single_lemmas = GENERIC_SINGLE_LEMMAS
    
    # Лемматизируем все сильные ключевые слова
    strong_lemmas = [lemmatize_phrase(k) for k in strong_keywords]
    
    # Фильтруем слишком общие однословные леммы
    strong_lemmas_for_bool = [
        lemma for lemma in strong_lemmas
        if not (len(lemma.split()) == 1 and lemma in generic_single_lemmas)
    ]
    
    return strong_lemmas, strong_lemmas_for_bool


def bool_filter_lemmas(
    title: str,
    summary: str,
    strong_lemmas_for_bool: List[str],
    blacklist_lemmas: Optional[List[str]] = None,
    use_blacklist: bool = False
) -> Tuple[bool, Dict[str, str]]:
    """
    Boolean-фильтр с лемматизацией:
    - лемматизируем title+summary
    - проверяем наличие blacklist-лемм (если включено)
    - проверяем наличие strong-лемм
    
    Args:
        title: Заголовок статьи
        summary: Краткое описание статьи
        strong_lemmas_for_bool: Список сильных лемм для фильтрации
        blacklist_lemmas: Список лемм для blacklist (опционально)
        use_blacklist: Использовать ли blacklist для фильтрации (по умолчанию False)
        
    Returns:
        Tuple[прошла_ли_фильтр, причина]
    """
    raw_text = (title or "") + " " + (summary or "")
    lem_text = lemmatize_text(raw_text)
    
    # Проверка blacklist (только если включено)
    if use_blacklist and blacklist_lemmas:
        for bad_lemma in blacklist_lemmas:
            if bad_lemma and bad_lemma in lem_text:
                return False, {"reason": f"blacklist lemma matched: {bad_lemma}"}
    
    # Проверка strong-лемм
    for good_lemma in strong_lemmas_for_bool:
        if good_lemma and good_lemma in lem_text:
            return True, {"reason": f"strong lemma matched: {good_lemma}"}
    
    return False, {"reason": "no strong lemmas found"}


def _apply_filter_to_row(
    row: pd.Series,
    strong_lemmas_for_bool: List[str],
    blacklist_lemmas: Optional[List[str]],
    use_blacklist: bool
) -> Tuple[bool, str]:
    """
    Вспомогательная функция для применения фильтра к одной строке.
    Избегает двойного вызова bool_filter_lemmas и изолирует ошибки.
    
    Args:
        row: Строка DataFrame
        strong_lemmas_for_bool: Список сильных лемм
        blacklist_lemmas: Список blacklist лемм
        use_blacklist: Использовать ли blacklist
        
    Returns:
        Tuple[результат_фильтра, причина]
    """
    try:
        title = row.get("title", "")
        summary = row.get("summary", "")
        
        result, reason_dict = bool_filter_lemmas(
            title,
            summary,
            strong_lemmas_for_bool,
            blacklist_lemmas,
            use_blacklist
        )
        return result, reason_dict["reason"]
    except Exception as e:
        logger.warning(f"Ошибка обработки статьи: {e}")
        return False, f"error: {str(e)[:50]}"


def filter_articles_by_keywords(
    df: pd.DataFrame,
    keywords_config: Optional[Dict[str, List[str]]] = None,
    generic_single_lemmas: Optional[set] = None,
    use_blacklist: bool = False
) -> Tuple[pd.DataFrame, Dict]:
    """
    Фильтрует статьи по ключевым словам с использованием лемматизации.
    
    Args:
        df: DataFrame со статьями (должен содержать колонки 'title' и 'summary')
        keywords_config: Конфигурация ключевых слов. Если None, загружается из таксономии по TAXONOMY_SELECTION (config).
        generic_single_lemmas: Множество слишком общих однословных лемм. Если None, берется из config
        use_blacklist: Использовать ли blacklist для фильтрации (по умолчанию False)
        
    Returns:
        Tuple[отфильтрованный_DataFrame, статистика]
    """
    start_time = time.time()
    
    # Валидация входных данных
    if df is None or df.empty:
        return pd.DataFrame(), {
            "total_articles": 0,
            "passed": 0,
            "blacklisted": 0,
            "strong_matches": 0,
            "weak_matches": 0,
            "time_elapsed_sec": 0,
            "strong_lemmas_total": 0,
            "strong_lemmas_for_bool": 0,
            "errors": 0
        }
    
    if "title" not in df.columns or "summary" not in df.columns:
        raise ValueError("DataFrame должен содержать колонки 'title' и 'summary'")
    
    # Загрузка конфигурации ключевых слов из таксономии по выбранным узлам D/GA/A
    if keywords_config is None:
        from config.config import TAXONOMY_SELECTION
        taxonomy = load_taxonomy()
        keywords_config = get_keywords_config_for_selection(taxonomy, TAXONOMY_SELECTION)
    
    strong_keywords = keywords_config.get("strong", [])
    weak_keywords = keywords_config.get("weak", [])
    blacklist_keywords = keywords_config.get("blacklist", [])
    
    # Подготовка лемм
    logger.info("Лемматизация ключевых слов...")
    strong_lemmas, strong_lemmas_for_bool = prepare_strong_lemmas_for_bool_filter(
        strong_keywords,
        generic_single_lemmas
    )
    
    # Лемматизация blacklist (только если будет использоваться)
    blacklist_lemmas = [lemmatize_phrase(k) for k in blacklist_keywords] if use_blacklist else []
    
    logger.info(f"Всего strong-лемм: {len(strong_lemmas)}, для фильтра: {len(strong_lemmas_for_bool)}")
    
    # Применение фильтра с изоляцией ошибок
    logger.info(f"Применение Boolean-фильтра к {len(df)} статьям...")
    df = df.copy()
    
    # Оптимизация: один вызов на строку вместо двух
    filter_results = df.apply(
        lambda row: _apply_filter_to_row(
            row,
            strong_lemmas_for_bool,
            blacklist_lemmas if use_blacklist else None,
            use_blacklist
        ),
        axis=1
    )
    
    # Разделяем результаты и причины
    df["bool_lemma_result"] = filter_results.apply(lambda x: x[0])
    df["bool_lemma_reason"] = filter_results.apply(lambda x: x[1])
    
    # Подсчет ошибок
    errors = len(df[df["bool_lemma_reason"].str.startswith("error:", na=False)])
    
    # Фильтрация статей
    df_pass = df[df["bool_lemma_result"] == True].copy()
    
    end_time = time.time()
    elapsed = end_time - start_time
    
    # Подсчет статистики
    total_articles = len(df)
    passed = len(df_pass)
    
    # Подсчет blacklisted статей (только если blacklist используется)
    blacklisted = 0
    if use_blacklist and len(df) > 0:
        blacklisted = len(df[df["bool_lemma_reason"].str.contains("blacklist", na=False, case=False)])
    
    stats = {
        "total_articles": total_articles,
        "passed": passed,
        "blacklisted": blacklisted,
        "strong_matches": passed,
        "weak_matches": 0,
        "time_elapsed_sec": elapsed,
        "strong_lemmas_total": len(strong_lemmas),
        "strong_lemmas_for_bool": len(strong_lemmas_for_bool),
        "errors": errors
    }
    
    logger.info(f"Фильтрация завершена: {passed}/{total_articles} статей прошло фильтр (ошибок: {errors})")
    
    return df_pass, stats


if __name__ == "__main__":
    # Тестирование модуля
    logging.basicConfig(level=logging.INFO)
    
    # Пример использования
    test_df = pd.DataFrame({
        "title": ["Тестирование и DevOps метрики"],
        "summary": ["Статья о метриках DORA и CI/CD"]
    })
    
    df_filtered, stats = filter_articles_by_keywords(test_df)
    print(f"Статистика: {stats}")
    print(f"Результат: {df_filtered}")
