"""
Модуль для загрузки промптов из JSON файла.
"""
import json
import logging
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# Кэш загруженных промптов
_prompts_data: Optional[Dict] = None


def get_prompts_file() -> Path:
    """
    Возвращает путь к файлу с промптами.
    
    Returns:
        Path к файлу data/prompts.json
    """
    project_root = Path(__file__).parent.parent.parent
    return project_root / "data" / "prompts.json"


def _load_prompts_data() -> Dict:
    """
    Загружает все промпты из JSON файла.
    
    Returns:
        Словарь со всеми промптами
        
    Raises:
        FileNotFoundError: Если файл промптов не найден
        json.JSONDecodeError: Если файл содержит некорректный JSON
    """
    global _prompts_data
    if _prompts_data is not None:
        return _prompts_data
    
    prompts_file = get_prompts_file()
    
    if not prompts_file.exists():
        error_msg = f"Файл промптов не найден: {prompts_file}"
        logger.error(error_msg)
        raise FileNotFoundError(error_msg)
    
    try:
        with open(prompts_file, "r", encoding="utf-8") as f:
            _prompts_data = json.load(f)
        logger.debug(f"Загружены промпты из {prompts_file}")
        return _prompts_data
    except json.JSONDecodeError as e:
        error_msg = f"Ошибка парсинга JSON в {prompts_file}: {e}"
        logger.error(error_msg)
        raise
    except Exception as e:
        error_msg = f"Ошибка загрузки промптов из {prompts_file}: {e}"
        logger.error(error_msg)
        raise


def load_prompt(prompt_name: str) -> str:
    """
    Загружает промпт из JSON файла.
    
    Поддерживает два формата имени:
    - "summary_system" -> prompts["summary"]["system"]
    - "title_filter_user" -> prompts["title_filter"]["user"]
    
    Args:
        prompt_name: Имя промпта в формате "{category}_{type}"
        
    Returns:
        Содержимое промпта
        
    Raises:
        KeyError: Если промпт не найден
    """
    prompts = _load_prompts_data()
    
    # Сначала проверяем, может быть это простой ключ верхнего уровня (например, "relevance_guidelines")
    if prompt_name in prompts:
        prompt_text = prompts[prompt_name]
        if isinstance(prompt_text, str):
            logger.debug(f"Загружен промпт (верхний уровень): {prompt_name}")
            return prompt_text
    
    # Если не найден как простой ключ, ищем как вложенную структуру: "title_filter_system" -> ("title_filter", "system")
    # Ищем последний "_" для разделения на category и type
    last_underscore = prompt_name.rfind("_")
    if last_underscore == -1:
        error_msg = f"Промпт '{prompt_name}' не найден"
        logger.error(error_msg)
        raise KeyError(error_msg)
    
    category = prompt_name[:last_underscore]
    prompt_type = prompt_name[last_underscore + 1:]
    
    try:
        prompt_text = prompts[category][prompt_type]
        logger.debug(f"Загружен промпт: {prompt_name}")
        return prompt_text
    except KeyError as e:
        error_msg = f"Промпт '{prompt_name}' не найден (category='{category}', type='{prompt_type}')"
        logger.error(error_msg)
        raise KeyError(error_msg) from e


def format_prompt(template: str, **kwargs) -> str:
    """
    Форматирует промпт-шаблон с подстановкой переменных.
    
    Args:
        template: Шаблон промпта с плейсхолдерами {variable}
        **kwargs: Значения для подстановки
        
    Returns:
        Отформатированный промпт
    """
    try:
        return template.format(**kwargs)
    except KeyError as e:
        logger.error(f"Отсутствует переменная в промпте: {e}")
        raise
    except Exception as e:
        logger.error(f"Ошибка форматирования промпта: {e}")
        raise

