"""
Конфигурация проекта: RSS-ленты и параметры пайплайна.
"""
import os

# RSS-источники
RSS_FEEDS = {
    "pm": "https://habr.com/ru/rss/hubs/pm/articles/",
    "hr_management": "https://habr.com/ru/rss/hubs/hr_management/articles/",
    "statistics": "https://habr.com/ru/rss/hubs/statistics/articles/",
    "productpm": "https://habr.com/ru/rss/hubs/productpm/articles/",
    "analysis_design": "https://habr.com/ru/rss/hubs/analysis_design/articles/",
    "dev_management": "https://habr.com/ru/rss/hubs/dev_management/articles/",
    "complete_code": "https://habr.com/ru/rss/hubs/complete_code/articles/",
    "devops": "https://habr.com/ru/rss/hubs/devops/articles/",
    "git": "https://habr.com/ru/rss/hubs/git/articles/",
    "beeline_cloud": "https://habr.com/ru/rss/companies/beeline_cloud/articles/",
    "agile": "https://habr.com/ru/rss/hubs/agile/articles/",
    "web_testing": "https://habr.com/ru/rss/hubs/web_testing/articles/",
    "mobile_testing": "https://habr.com/ru/rss/hubs/mobile_testing/articles/",
    "programming": "https://habr.com/ru/rss/hubs/programming/articles/",
    "java": "https://habr.com/ru/rss/hubs/java/articles/",
    "kotlin": "https://habr.com/ru/rss/hubs/kotlin/articles/",
    "it_testing": "https://habr.com/ru/rss/hubs/it_testing/articles/",
    "cian_company": "https://habr.com/ru/rss/companies/cian/articles/",
    "infosecurity": "https://habr.com/ru/rss/hubs/infosecurity/articles/",
    "vk_company": "https://habr.com/ru/rss/companies/vk/articles/",
    "python": "https://habr.com/ru/rss/hubs/python/articles/",
    "win_dev": "https://habr.com/ru/rss/hubs/win_dev/articles/",
    "oleg_bunin": "https://habr.com/ru/rss/companies/oleg-bunin/articles/",
    "raiffeisenbank": "https://habr.com/ru/rss/companies/raiffeisenbank/articles/",
    "engineering_systems": "https://habr.com/ru/rss/hubs/engineering_systems/articles/",
    "simbirsoft": "https://habr.com/ru/rss/companies/simbirsoft/articles/",
    "tochka": "https://habr.com/ru/rss/companies/tochka/articles/",
    "sberbank": "https://habr.com/ru/rss/companies/sberbank/articles/",
    "dwh": "https://habr.com/ru/rss/hubs/dwh/articles/",
    "otus_company": "https://habr.com/ru/rss/companies/otus/articles/",
    "refactoring": "https://habr.com/ru/rss/hubs/refactoring/articles/",
    "research": "https://habr.com/ru/rss/hubs/research/articles/",
    "avito_company": "https://habr.com/ru/rss/companies/avito/articles/",
    "testograf_company": "https://habr.com/ru/rss/companies/testograf/articles/",
    "sales": "https://habr.com/ru/rss/hubs/sales/articles/",
    "business_models": "https://habr.com/ru/rss/hubs/business_models/articles/",
    "itcompanies": "https://habr.com/ru/rss/hubs/itcompanies/articles/",
    "artificial_intelligence": "https://habr.com/ru/rss/hubs/artificial_intelligence/articles/",
    "vktech_company": "https://habr.com/ru/rss/companies/vktech/articles/",
    "nlp": "https://habr.com/ru/rss/hubs/natural_language_processing/articles/",
    "machine_learning": "https://habr.com/ru/rss/hubs/machine_learning/articles/",
    "futurenow": "https://habr.com/ru/rss/hubs/futurenow/articles/",
    "ru_mts": "https://habr.com/ru/rss/companies/ru_mts/articles/",
    "popular_science": "https://habr.com/ru/rss/hubs/popular_science/articles/",
    "cian": "https://habr.com/ru/rss/companies/cian/articles/",
    "dododev": "https://habr.com/ru/rss/companies/dododev/articles/",
    "gazprombank": "https://habr.com/ru/rss/companies/gazprombank/articles/",
    "habr": "https://habr.com/ru/rss/companies/habr/articles/",
    "jetinfosystems": "https://habr.com/ru/rss/companies/jetinfosystems/articles/",
    "mts_ai": "https://habr.com/ru/rss/companies/mts_ai/articles/",
    "mws": "https://habr.com/ru/rss/companies/mws/articles/",
    "ods": "https://habr.com/ru/rss/companies/ods/articles/",
    "yadro": "https://habr.com/ru/rss/companies/yadro/articles/",
    "cleverpumpkin": "https://habr.com/ru/rss/companies/cleverpumpkin/articles/",
    "inferit": "https://habr.com/ru/rss/companies/inferit/articles/",
    "onlinepatent": "https://habr.com/ru/rss/companies/onlinepatent/articles/",
    "x5tech": "https://habr.com/ru/rss/companies/x5tech/articles/",
    "redmadrobot": "https://habr.com/ru/rss/companies/redmadrobot/articles/",
    "webdev": "https://habr.com/ru/rss/hubs/webdev/articles/",
    "itstandarts": "https://habr.com/ru/rss/hubs/itstandarts/articles/",
    "usability": "https://habr.com/ru/rss/hubs/usability/articles/",
    "api": "https://habr.com/ru/rss/hubs/api/articles/",
    "reverse_engineering": "https://habr.com/ru/rss/hubs/reverse-engineering/articles/",
    "hi": "https://habr.com/ru/rss/hubs/hi/articles/",
    "crypto": "https://habr.com/ru/rss/hubs/crypto/articles/",
    "system_programming": "https://habr.com/ru/rss/hubs/system_programming/articles/",
    "virtualization": "https://habr.com/ru/rss/hubs/virtualization/articles/",
    "cvs": "https://habr.com/ru/rss/hubs/cvs/articles/",
    "tdd": "https://habr.com/ru/rss/hubs/tdd/articles/",
    "algorithms": "https://habr.com/ru/rss/hubs/algorithms/articles/",
    "parallel_programming": "https://habr.com/ru/rss/hubs/parallel_programming/articles/",
    "funcprog": "https://habr.com/ru/rss/hubs/funcprog/articles/",
    "industrial_control_system": "https://habr.com/ru/rss/hubs/industrial_control_system/articles/",
    "lib": "https://habr.com/ru/rss/hubs/lib/articles/",
    "distributed_systems": "https://habr.com/ru/rss/hubs/distributed_systems/articles/",
    "data_engineering": "https://habr.com/ru/rss/hubs/data_engineering/articles/",
    "visual_programming": "https://habr.com/ru/rss/hubs/visual_programming/articles/",
    "mobile_dev": "https://habr.com/ru/rss/hubs/mobile_dev/articles/",
    "gtd": "https://habr.com/ru/rss/hubs/gtd/articles/",
    "weban": "https://habr.com/ru/rss/hubs/weban/articles/",
    "business_laws": "https://habr.com/ru/rss/hubs/business-laws/articles/",
    "career": "https://habr.com/ru/rss/hubs/career/articles/",
    "technical_writing": "https://habr.com/ru/rss/hubs/technical_writing/articles/",
    "startuprise": "https://habr.com/ru/rss/hubs/startuprise/articles/",
    "terminator": "https://habr.com/ru/rss/hubs/terminator/articles/",
    "community_management": "https://habr.com/ru/rss/hubs/community_management/articles/"
}

# Параметры по умолчанию
DEFAULT_HOURS_BACK = 72
DEFAULT_LIMIT_PER_FEED = 30
DEFAULT_RSS_TIMEOUT = 30  # секунд
DEFAULT_MAX_RETRIES = 3
DEFAULT_RETRY_DELAY = 2  # секунд

# Лемматизация: слишком общие однословные леммы для исключения из Boolean-фильтра
GENERIC_SINGLE_LEMMAS = {
    "процесс",
    "показатель",
    "измерение",
    "борд"
}

# Таксономия: выбранные узлы для фильтрации (D / GA / A).
# Заполняется агентом-taxonomy по запросу пользователя; здесь — значение по умолчанию для пайплайна.
# Пример: {"discipline": "D1", "ga": "GA2", "activity": "A5"} или только {"discipline": "D1", "ga": None, "activity": None}.
TAXONOMY_SELECTION = {
    "discipline": "D1",
    "ga": "GA1",
    "activity": "A1",
}

# Эмбеддинги: параметры фильтрации
DEFAULT_EMBED_THRESHOLD = 0.35  # Порог сходства для embedding-фильтра
DEFAULT_EMBED_BATCH_SIZE = 32  # Размер батча для обработки эмбеддингов

# Эмбеддинги: модель
EMBEDDING_MODEL_NAME = "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"

# Извлечение текста: параметры
DEFAULT_TEXT_EXTRACTION_RETRIES = 3  # Количество попыток при ошибке
DEFAULT_TEXT_EXTRACTION_SLEEP = 2.0  # Задержка между попытками (секунды)
DEFAULT_TEXT_MIN_LENGTH = 300  # Минимальная длина текста для успешного извлечения

# GigaChat: конфигурация
GIGACHAT_CREDENTIALS = "MDE5YjBmMDctYzZmNC03NzliLTg2MjUtYmI4ZTRhZWNmOTI2OmVkZWNmMDNiLWI1YTYtNDM2OS1iZDkzLWRiZTYxOWM3ZjgyMQ=="
GIGACHAT_MODEL = "GigaChat"  # Модель GigaChat
GIGACHAT_VERIFY_SSL = False  # Проверка SSL сертификатов

# LLM: параметры обработки текста
DEFAULT_TEXT_CLEAN_MAX_CHARS = 12000  # Максимальная длина текста для очистки
DEFAULT_SUMMARY_MAX_CHARS = 8000  # Максимальная длина текста для суммаризации
DEFAULT_SUMMARY_TEMPERATURE = 0.2  # Temperature для суммаризации
DEFAULT_RELEVANCE_TEMPERATURE = 0.0  # Temperature для фильтрации релевантности
DEFAULT_LLM_SLEEP = 1.5  # Задержка между запросами к LLM (секунды)


# PostgreSQL: конфигурация хранения состояния краулера
POSTGRES_ENABLED = True  # Можно отключить БД, если она недоступна

# Базовые параметры подключения (заполни под свою локальную БД)
POSTGRES_HOST = "localhost"
POSTGRES_PORT = 5432
POSTGRES_DB = "postgres" 
POSTGRES_USER = "macbookpro"  
POSTGRES_PASSWORD = ""  

# Имена таблиц для состояния краулера
POSTGRES_TABLE_PROCESSED_ARTICLES = "processed_articles"
POSTGRES_TABLE_FEED_STATE = "last_published_at"

