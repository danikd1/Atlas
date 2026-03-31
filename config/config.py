"""
Конфигурация проекта: RSS-ленты и параметры пайплайна.
"""
import getpass
import os
from enum import Enum


class RelevanceStatus(str, Enum):
    """Статусы релевантности статей."""
    RELEVANT = "relevant"
    IRRELEVANT = "irrelevant"
    NEED_FULLTEXT = "need_fulltext"

    def __str__(self) -> str:
        return self.value

# RSS-источники
RSS_FEEDS = {
    # "pm": "https://habr.com/ru/rss/hubs/pm/articles/",
    # "hr_management": "https://habr.com/ru/rss/hubs/hr_management/articles/",
    # "statistics": "https://habr.com/ru/rss/hubs/statistics/articles/",
    # "productpm": "https://habr.com/ru/rss/hubs/productpm/articles/",
    # "analysis_design": "https://habr.com/ru/rss/hubs/analysis_design/articles/",
    # "dev_management": "https://habr.com/ru/rss/hubs/dev_management/articles/",
    # "complete_code": "https://habr.com/ru/rss/hubs/complete_code/articles/",
    # "devops": "https://habr.com/ru/rss/hubs/devops/articles/",
    # "git": "https://habr.com/ru/rss/hubs/git/articles/",
    # "beeline_cloud": "https://habr.com/ru/rss/companies/beeline_cloud/articles/",
    # "agile": "https://habr.com/ru/rss/hubs/agile/articles/",
    # "web_testing": "https://habr.com/ru/rss/hubs/web_testing/articles/",
    # "mobile_testing": "https://habr.com/ru/rss/hubs/mobile_testing/articles/",
    # "programming": "https://habr.com/ru/rss/hubs/programming/articles/",
    # "java": "https://habr.com/ru/rss/hubs/java/articles/",
    # "kotlin": "https://habr.com/ru/rss/hubs/kotlin/articles/",
    # "it_testing": "https://habr.com/ru/rss/hubs/it_testing/articles/",
    # "cian_company": "https://habr.com/ru/rss/companies/cian/articles/",
    # "infosecurity": "https://habr.com/ru/rss/hubs/infosecurity/articles/",
    # "vk_company": "https://habr.com/ru/rss/companies/vk/articles/",
    # "python": "https://habr.com/ru/rss/hubs/python/articles/",
    # "win_dev": "https://habr.com/ru/rss/hubs/win_dev/articles/",
    # "oleg_bunin": "https://habr.com/ru/rss/companies/oleg-bunin/articles/",
    # "raiffeisenbank": "https://habr.com/ru/rss/companies/raiffeisenbank/articles/",
    # "engineering_systems": "https://habr.com/ru/rss/hubs/engineering_systems/articles/",
    # "simbirsoft": "https://habr.com/ru/rss/companies/simbirsoft/articles/",
    # "tochka": "https://habr.com/ru/rss/companies/tochka/articles/",
    # "sberbank": "https://habr.com/ru/rss/companies/sberbank/articles/",
    # "dwh": "https://habr.com/ru/rss/hubs/dwh/articles/",
    # "otus_company": "https://habr.com/ru/rss/companies/otus/articles/",
    # "refactoring": "https://habr.com/ru/rss/hubs/refactoring/articles/",
    # "research": "https://habr.com/ru/rss/hubs/research/articles/",
    # "avito_company": "https://habr.com/ru/rss/companies/avito/articles/",
    # "testograf_company": "https://habr.com/ru/rss/companies/testograf/articles/",
    # "sales": "https://habr.com/ru/rss/hubs/sales/articles/",
    # "business_models": "https://habr.com/ru/rss/hubs/business_models/articles/",
    # "itcompanies": "https://habr.com/ru/rss/hubs/itcompanies/articles/",
    # "artificial_intelligence": "https://habr.com/ru/rss/hubs/artificial_intelligence/articles/",
    # "vktech_company": "https://habr.com/ru/rss/companies/vktech/articles/",
    # "nlp": "https://habr.com/ru/rss/hubs/natural_language_processing/articles/",
    # "machine_learning": "https://habr.com/ru/rss/hubs/machine_learning/articles/",
    # "futurenow": "https://habr.com/ru/rss/hubs/futurenow/articles/",
    # "ru_mts": "https://habr.com/ru/rss/companies/ru_mts/articles/",
    # "popular_science": "https://habr.com/ru/rss/hubs/popular_science/articles/",
    # "cian": "https://habr.com/ru/rss/companies/cian/articles/",
    # "dododev": "https://habr.com/ru/rss/companies/dododev/articles/",
    # "gazprombank": "https://habr.com/ru/rss/companies/gazprombank/articles/",
    # "habr": "https://habr.com/ru/rss/companies/habr/articles/",
    # "jetinfosystems": "https://habr.com/ru/rss/companies/jetinfosystems/articles/",
    # "mts_ai": "https://habr.com/ru/rss/companies/mts_ai/articles/",
    # "mws": "https://habr.com/ru/rss/companies/mws/articles/",
    # "ods": "https://habr.com/ru/rss/companies/ods/articles/",
    # "yadro": "https://habr.com/ru/rss/companies/yadro/articles/",
    # "cleverpumpkin": "https://habr.com/ru/rss/companies/cleverpumpkin/articles/",
    # "inferit": "https://habr.com/ru/rss/companies/inferit/articles/",
    # "onlinepatent": "https://habr.com/ru/rss/companies/onlinepatent/articles/",
    # "x5tech": "https://habr.com/ru/rss/companies/x5tech/articles/",
    # "redmadrobot": "https://habr.com/ru/rss/companies/redmadrobot/articles/",
    # "webdev": "https://habr.com/ru/rss/hubs/webdev/articles/",
    # "itstandarts": "https://habr.com/ru/rss/hubs/itstandarts/articles/",
    # "usability": "https://habr.com/ru/rss/hubs/usability/articles/",
    # "api": "https://habr.com/ru/rss/hubs/api/articles/",
    # "reverse_engineering": "https://habr.com/ru/rss/hubs/reverse-engineering/articles/",
    # "hi": "https://habr.com/ru/rss/hubs/hi/articles/",
    # "crypto": "https://habr.com/ru/rss/hubs/crypto/articles/",
    # "system_programming": "https://habr.com/ru/rss/hubs/system_programming/articles/",
    # "virtualization": "https://habr.com/ru/rss/hubs/virtualization/articles/",
    # "cvs": "https://habr.com/ru/rss/hubs/cvs/articles/",
    # "tdd": "https://habr.com/ru/rss/hubs/tdd/articles/",
    # "algorithms": "https://habr.com/ru/rss/hubs/algorithms/articles/",
    # "parallel_programming": "https://habr.com/ru/rss/hubs/parallel_programming/articles/",
    # "funcprog": "https://habr.com/ru/rss/hubs/funcprog/articles/",
    # "industrial_control_system": "https://habr.com/ru/rss/hubs/industrial_control_system/articles/",
    # "lib": "https://habr.com/ru/rss/hubs/lib/articles/",
    # "distributed_systems": "https://habr.com/ru/rss/hubs/distributed_systems/articles/",
    # "data_engineering": "https://habr.com/ru/rss/hubs/data_engineering/articles/",
    # "visual_programming": "https://habr.com/ru/rss/hubs/visual_programming/articles/",
    # "mobile_dev": "https://habr.com/ru/rss/hubs/mobile_dev/articles/",
    # "gtd": "https://habr.com/ru/rss/hubs/gtd/articles/",
    # "weban": "https://habr.com/ru/rss/hubs/weban/articles/",
    # "business_laws": "https://habr.com/ru/rss/hubs/business-laws/articles/",
    # "career": "https://habr.com/ru/rss/hubs/career/articles/",
    # "technical_writing": "https://habr.com/ru/rss/hubs/technical_writing/articles/",
    # "startuprise": "https://habr.com/ru/rss/hubs/startuprise/articles/",
    # "terminator": "https://habr.com/ru/rss/hubs/terminator/articles/",
    # "community_management": "https://habr.com/ru/rss/hubs/community_management/articles/",

    "toptal1": "https://www.toptal.com/project-managers/blog.rss",
    "toptal2": "https://www.toptal.com/product-managers/blog.rss",
    "toptal3": "https://www.toptal.com/management-consultants/blog.rss",
    "toptal4": "https://www.toptal.com/developers/blog.rss",

    "Github Insights": "https://github.blog/news-insights/feed/",
    "Github AI & ML": "https://github.blog/ai-and-ml/feed/",
    "Github Developer skills": "https://github.blog/developer-skills/feed/",
    "Github Engineering": "https://github.blog/engineering/feed/",
    "Github Enterprise software": "https://github.blog/enterprise-software/feed/",
    "Github Open Source": "https://github.blog/open-source/feed/",
    "Github Security": "https://github.blog/security/feed/",
    "Github": "https://github.blog/feed/",
    
    # "OpenAI": "https://openai.com/news/rss.xml", #почему-то нужен vpn

    "Google": "https://blog.google/rss/",
    "Google DeepMind": "https://deepmind.google/blog/rss.xml",
    "Google Research": "https://research.google/blog/rss/",
    "Google Developers": "https://developers.googleblog.com/feeds/posts/default/?alt=rss",
    "Google Cloud": "https://cloudblog.withgoogle.com/products/devops-sre/rss/",

    "Google Cloud ai-machine-learning": "https://cloudblog.withgoogle.com/products/ai-machine-learning/rss/",
    "Google Cloud api-management": "https://cloudblog.withgoogle.com/products/api-management/rss/",
    "Google Cloud Application Development": "https://cloudblog.withgoogle.com/products/application-development/rss/",
    "Google Cloud Application Modernization": "https://cloudblog.withgoogle.com/products/application-modernization/rss/",
    "Google Cloud Chrome Enterprise": "https://cloudblog.withgoogle.com/products/chrome-enterprise/rss/",
    "Google Cloud Compute": "https://cloudblog.withgoogle.com/products/compute/rss/",
    "Google Cloud Containers & Kubernetes": "https://cloudblog.withgoogle.com/products/containers-kubernetes/rss/",
    "Google Cloud Data Analytics": "https://cloudblog.withgoogle.com/products/data-analytics/rss/",
    "Google Cloud Databases": "https://cloudblog.withgoogle.com/products/databases/rss/",
    "Google Cloud DevOps & SRE": "https://cloudblog.withgoogle.com/products/devops-sre/rss/",
    "Google Cloud Threat Intelligence": "https://cloudblog.withgoogle.com/topics/threat-intelligence/rss/",
    "Google Cloud Infrastructure": "https://cloudblog.withgoogle.com/products/infrastructure/rss/",
    "Google Cloud Infrastructure Modernization": "https://cloudblog.withgoogle.com/products/infrastructure-modernization/rss/",
    "Google Cloud Storage & Data Transfer": "https://cloudblog.withgoogle.com/products/storage-data-transfer/rss/",
    "Google Cloud Startups": "https://cloudblog.withgoogle.com/topics/startups/rss/",

    "Google workspace": "https://blog.google/products-and-platforms/products/workspace/rss/",
    "Google Ads & Commerce": "https://blog.google/products/ads-commerce/rss/",

    "Microsoft Azure Blog": "https://azure.microsoft.com/en-us/blog/feed/",
    "Microsoft Azure Blog AI Professionals": "https://azure.microsoft.com/en-us/blog/audience/ai-professionals/feed/",
    "Microsoft Azure Blog Business Decision Makers": "https://azure.microsoft.com/en-us/blog/audience/business-decision-makers/feed/",
    "Microsoft Azure Blog Data Professionals": "https://azure.microsoft.com/en-us/blog/audience/data-professionals/feed/",
    "Microsoft Azure Blog Developers": "https://azure.microsoft.com/en-us/blog/audience/developers/feed/",
    "Microsoft Azure Blog IT Decision Makers": "https://azure.microsoft.com/en-us/blog/audience/it-decision-makers/feed/",
    "Microsoft Azure Blog IT Implementors": "https://azure.microsoft.com/en-us/blog/audience/it-implementors/feed/",
    "Microsoft Azure Blogs Best Practices": "https://azure.microsoft.com/en-us/blog/content-type/best-practices/feed/",
    "Microsoft Azure Blogs Customer Stories": "https://azure.microsoft.com/en-us/blog/content-type/customer-stories/feed/",

    #нужен vpn
    # "AWS Blog Insights": "https://aws.amazon.com/ru/blogs/aws-insights/feed/",
    # "AWS Blog AWS": "https://aws.amazon.com/ru/blogs/aws/feed/",
    # "AWS Blog SMB": "https://aws.amazon.com/ru/blogs/smb/feed/",
    # "AWS Blog Business Intelligence": "https://aws.amazon.com/ru/blogs/business-intelligence/feed/",
    # "AWS Blog DevOps": "https://aws.amazon.com/ru/blogs/devops/feed/",
    # "AWS Blog Infrastructure and Automation": "https://aws.amazon.com/ru/blogs/infrastructure-and-automation/feed/",
    # "AWS Blog Open Source": "https://aws.amazon.com/ru/blogs/opensource/feed/",
    # "AWS Blog Public Sector": "https://aws.amazon.com/ru/blogs/publicsector/feed/",
    # "AWS Blog Russia": "https://aws.amazon.com/ru/blogs/rus/feed/",

    "MIT Technology Review": "https://www.technologyreview.com/feed",

    "Atlassian Communication": "https://www.atlassian.com/blog/communication/feed",
    "Atlassian Distributed Work": "https://www.atlassian.com/blog/distributed-work/feed",
    "Atlassian Leadership": "https://www.atlassian.com/blog/leadership/feed",
    "Atlassian Productivity": "https://www.atlassian.com/blog/productivity/feed",
    "Atlassian Strategy": "https://www.atlassian.com/blog/strategy/feed",
    "Atlassian Teamwork": "https://www.atlassian.com/blog/teamwork/feed",

    "Atlassian Add-ons": "https://www.atlassian.com/blog/add-ons/feed",
    "Atlassian Bitbucket": "https://www.atlassian.com/blog/bitbucket/feed",
    "Atlassian Crucible": "https://www.atlassian.com/blog/crucible/feed",
    "Atlassian Halp": "https://www.atlassian.com/blog/halp/feed",
    "Atlassian Access": "https://www.atlassian.com/blog/access/feed",
    "Atlassian Confluence": "https://www.atlassian.com/blog/confluence/feed",
    "Atlassian Fisheye": "https://www.atlassian.com/blog/fisheye/feed",
    "Atlassian Jira": "https://www.atlassian.com/blog/jira/feed",
    "Atlassian Bamboo": "https://www.atlassian.com/blog/bamboo/feed",
    "Atlassian Crowd": "https://www.atlassian.com/blog/crowd/feed",
    "Atlassian Focus": "https://www.atlassian.com/blog/focus/feed",
    "Atlassian Jira Align": "https://www.atlassian.com/blog/jira-align/feed",
    "Atlassian Jira Product Discovery": "https://www.atlassian.com/blog/jira-product-discovery/feed",
    "Atlassian Sourcetree": "https://www.atlassian.com/blog/sourcetree/feed",
    "Atlassian Jira Service Management": "https://www.atlassian.com/blog/jira-service-management/feed",
    "Atlassian Statuspage": "https://www.atlassian.com/blog/statuspage/feed",
    "Atlassian Loom": "https://www.atlassian.com/blog/loom/feed",
    "Atlassian Trello   ": "https://www.atlassian.com/blog/trello/feed",

    "Atlassian Artificial Intelligence": "https://www.atlassian.com/blog/artificial-intelligence/feed",
    "Atlassian Agile": "https://www.atlassian.com/blog/agile/feed",
    "Atlassian Atlassian Engineering": "https://www.atlassian.com/blog/atlassian-engineering/feed",
    "Atlassian Continuous Delivery": "https://www.atlassian.com/blog/continuous-delivery/feed",
    "Atlassian Design": "https://www.atlassian.com/blog/design/feed",
    "Atlassian Developer": "https://www.atlassian.com/blog/developer/feed",
    "Atlassian Devops": "https://www.atlassian.com/blog/devops/feed",
    "Atlassian Enterprise": "https://www.atlassian.com/blog/enterprise/feed",
    "Atlassian Git": "https://www.atlassian.com/blog/git/feed",
    "Atlassian It Service Management": "https://www.atlassian.com/blog/it-service-management/feed",
    "Atlassian Inside Atlassian": "https://www.atlassian.com/blog/inside-atlassian/feed",
    "Atlassian Project Management": "https://www.atlassian.com/blog/project-management/feed",
    "Atlassian Work Management": "https://www.atlassian.com/blog/work-management/feed",
    "Atlassian Announcements": "https://www.atlassian.com/blog/announcements/feed",

    # "Slack Design": "https://slack.design/feed/",
    # "Slack blog": "",

    # "GitLab Blog": "https://about.gitlab.com/atom.xml",
    # "GitLab Releases": "https://about.gitlab.com/releases.xml",

    # "Figma": "https://www.figma.com/blog/feed/atom.xml",

    # "Яндекс Cloud": "https://yandex.cloud/ru/feed.atom",

    "Сбербанк": "https://sberbs.ru/blogs/blog.atom",
    
    # "VK Tech": "",
    # "Ozon Tech": "",
    # "Wb Tech": "",
    # "Raiffeisenbank": "",

}

# Источники, в которых в RSS в summary приходит полный текст статьи; обрезаем до SUMMARY_TRUNCATE_MAX_CHARS (~128 токенов)
SUMMARY_TRUNCATE_SOURCE_PREFIXES = ("Google Cloud", "GitLab Blog", "Сбербанк",  "GitLab Releases")
SUMMARY_TRUNCATE_MAX_CHARS = 512

# Параметры по умолчанию
DEFAULT_HOURS_BACK = 87600
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
    "discipline": "D3",
    "ga": "GA1",
    "activity": None,
}

# Эмбеддинги: параметры фильтрации
DEFAULT_EMBED_THRESHOLD = 0.35  # Порог сходства для embedding-фильтра (статья проходит этап 3)
# Порог сходства для попадания в дайджест и RAG: из прошедших этап 3 берём только статьи с embed_similarity >= этого значения (полный текст, суммаризация, rag_documents)
EMBED_RELEVANT_THRESHOLD = 0.35
DEFAULT_EMBED_BATCH_SIZE = 32  # Размер батча для обработки эмбеддингов

# Эмбеддинги: модель
EMBEDDING_MODEL_NAME = "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"

# Rerank для QA: cross-encoder (можно заменить на мультиязычный аналог при необходимости)
QA_RERANK_MODEL_NAME = "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"

# Извлечение текста: параметры
DEFAULT_TEXT_EXTRACTION_RETRIES = 3  # Количество попыток при ошибке
DEFAULT_TEXT_EXTRACTION_SLEEP = 2.0  # Задержка между попытками (секунды)
DEFAULT_TEXT_MIN_LENGTH = 300  # Минимальная длина текста для успешного извлечения

# GigaChat: конфигурация
GIGACHAT_CREDENTIALS = "MDE5OTUyOTgtMWZmMC03NjRjLWI4ZTQtODRkZTMwNmNhMTJjOjE1NmFiNTUzLTExYjItNDRmZi1hMWJiLTZhMWUzZmM5M2YyNg=="
GIGACHAT_MODEL = "GigaChat"  # Модель GigaChat
GIGACHAT_VERIFY_SSL = False  # Проверка SSL сертификатов

# Если False — GigaChat пропускается и сразу используется BART-fallback.
# Удобно для тестирования fallback без отключения интернета.
# Управляется переменной окружения: GIGACHAT_SUMMARIZATION_ENABLED=false python3 -m src.main
GIGACHAT_SUMMARIZATION_ENABLED: bool = (
    os.environ.get("GIGACHAT_SUMMARIZATION_ENABLED", "true").strip().lower() != "false"
)
GIGACHAT_SUMMARIZATION_ENABLED = True

# BART fallback: модель для суммаризации когда GigaChat недоступен.
# facebook/bart-large-cnn  — английский, ~1.6 GB, высокое качество (по умолчанию)
# IlyaGusev/mbart_ru_sum_gazeta — русский, ~900 MB (раскомментируй для RU-статей)
BART_SUMMARIZATION_MODEL = "facebook/bart-large-cnn"
BART_SUMMARY_MAX_LENGTH = 130   # токенов в резюме
BART_SUMMARY_MIN_LENGTH = 40    # токенов минимум

# LLM: параметры обработки текста
DEFAULT_TEXT_CLEAN_MAX_CHARS = 12000  # Максимальная длина текста для очистки
DEFAULT_SUMMARY_MAX_CHARS = 8000  # Максимальная длина текста для суммаризации
DEFAULT_SUMMARY_TEMPERATURE = 0.2  # Temperature для суммаризации
DEFAULT_RELEVANCE_TEMPERATURE = 0.0  # Temperature для фильтрации релевантности
DEFAULT_LLM_SLEEP = 1.5  # Задержка между запросами к LLM (секунды)


# PostgreSQL: конфигурация хранения состояния краулера и RAG-данных
POSTGRES_ENABLED = True  # Можно отключить БД, если она недоступна

# Базовые параметры подключения (заполни под свою локальную БД)
POSTGRES_HOST = "localhost"
POSTGRES_PORT = 5432
POSTGRES_DB = "postgres"
# По умолчанию — текущий пользователь macOS/Linux (как у Homebrew Postgres). Переопределение: POSTGRES_USER=...
POSTGRES_USER = os.environ.get("POSTGRES_USER") or getpass.getuser()
POSTGRES_PASSWORD = ""

# Имена таблиц для состояния краулера и RAG-коллекций
POSTGRES_TABLE_PROCESSED_ARTICLES = "processed_articles"
POSTGRES_TABLE_FEED_STATE = "last_published_at"
POSTGRES_TABLE_COLLECTIONS = "collections"
POSTGRES_TABLE_RAG_DOCUMENTS = "rag_documents"
POSTGRES_TABLE_BERTOPIC_ASSIGNMENTS = "bertopic_assignments"
POSTGRES_TABLE_INBOX_ARTICLES = "inbox_articles"

# Размерность вектора эмбеддингов (paraphrase-multilingual-mpnet-base-v2 = 768)
EMBEDDING_DIM = 768

# RAG-чанкирование: размер чанка и перекрытие (в токенах)
RAG_CHUNK_MAX_TOKENS = 128
RAG_CHUNK_OVERLAP_TOKENS = 50

# Дайджест (4 раздела без графа): кластеризация + LLM-описание/классификация
DIGEST_N_CLUSTERS = 15  # число кластеров KMeans (можно None для авто по HDBSCAN)
DIGEST_MAX_ITEMS_PER_SECTION = 5  # макс. кластеров в каждом разделе (key_trends, methods, tools, case_studies)
DIGEST_MAX_ARTICLES_PER_CLUSTER = 3  # макс. статей (по link) в блоке
DIGEST_LLM_LANGUAGE = "ru"  # "ru" | "en"
DIGEST_TYPICAL_CHUNKS_PER_CLUSTER = 5  # сколько чанков отдавать в LLM для описания кластера

