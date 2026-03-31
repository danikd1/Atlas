"""
Модуль для работы с ключевыми словами (архивный / legacy).

Исторически использовался плоский файл data/keywords.json с полями
strong/weak/blacklist. Сейчас основной источник ключевых слов — таксономия
в data/taxonomy.json, а этот модуль оставлен только для совместимости и
возможного переиспользования утилит нормализации/сохранения.
"""
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


def get_keywords_file_path(config_file: Optional[str] = None) -> Path:
    """
    Возвращает путь к файлу keywords.json.
    
    Args:
        config_file: Путь к файлу конфигурации. Если None, используется data/keywords.json
        
    Returns:
        Path к файлу конфигурации
    """
    if config_file:
        return Path(config_file)
    
    # Ищем keywords.json в data/ или в корне проекта
    project_root = Path(__file__).parent.parent
    data_path = project_root / "data" / "keywords.json"
    root_path = project_root / "keywords.json"
    
    if data_path.exists():
        return data_path
    elif root_path.exists():
        return root_path
    else:
        return data_path


def normalize_keywords_list(keywords: List[str]) -> List[str]:
    """
    Нормализует список ключевых слов: удаляет пустые, дубликаты, приводит к нижнему регистру.
    
    Args:
        keywords: Список ключевых слов
        
    Returns:
        Нормализованный отсортированный список
    """
    if not keywords:
        return []
    
    normalized = []
    seen = set()
    
    for keyword in keywords:
        if not isinstance(keyword, str):
            continue
        
        normalized_keyword = keyword.lower().strip()
        if normalized_keyword and normalized_keyword not in seen:
            seen.add(normalized_keyword)
            normalized.append(normalized_keyword)
    
    return sorted(normalized)


def load_keywords_config(config_file: Optional[str] = None) -> Dict[str, List[str]]:
    """
    Загружает конфигурацию ключевых слов из JSON файла.
    
    Args:
        config_file: Путь к файлу конфигурации. Если None, используется data/keywords.json
        
    Returns:
        Словарь конфигурации ключевых слов с ключами: 'strong', 'weak', 'blacklist'
        
    Raises:
        FileNotFoundError: Если файл не найден
        json.JSONDecodeError: Если файл содержит некорректный JSON
    """
    keywords_path = get_keywords_file_path(config_file)
    
    try:
        with open(keywords_path, "r", encoding="utf-8") as f:
            config = json.load(f)
    except FileNotFoundError:
        logger.error(f"Файл конфигурации не найден: {keywords_path}")
        raise
    except json.JSONDecodeError as e:
        logger.error(f"Ошибка парсинга JSON в {keywords_path}: {e}")
        raise
    
    # Валидация структуры
    required_keys = {"strong", "weak", "blacklist"}
    if not all(key in config for key in required_keys):
        missing = required_keys - set(config.keys())
        raise ValueError(f"В конфигурации отсутствуют ключи: {missing}")
    
    # Нормализация данных
    normalized_config = {}
    for key in required_keys:
        keywords = config.get(key, [])
        normalized_config[key] = normalize_keywords_list(keywords)
    
    logger.info(f"Загружена конфигурация ключевых слов: strong={len(normalized_config['strong'])}, "
                f"weak={len(normalized_config['weak'])}, blacklist={len(normalized_config['blacklist'])}")
    
    return normalized_config


def save_keywords_config(
    keywords_config: Dict[str, List[str]],
    output_file: Optional[str] = None
) -> Path:
    """
    Сохраняет конфигурацию ключевых слов в JSON файл.
    
    Args:
        keywords_config: Словарь конфигурации ключевых слов
        output_file: Путь к выходному файлу. Если None, используется data/keywords.json
        
    Returns:
        Path к сохраненному файлу
    """
    output_path = get_keywords_file_path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Нормализация перед сохранением
    normalized_config = {}
    for key in ["strong", "weak", "blacklist"]:
        keywords = keywords_config.get(key, [])
        normalized_config[key] = normalize_keywords_list(keywords)
    
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(normalized_config, f, ensure_ascii=False, indent=2)
    
    logger.info(f"Конфигурация ключевых слов сохранена в {output_path}")
    return output_path
