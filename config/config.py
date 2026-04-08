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
# Формат: {"Название": {"url": "...", "category": "..."}}
# Категории: AI & ML, Engineering, Cloud & DevOps, Data, Security,
#            Design, Tools, Management, Tech News, Case Studies
RSS_FEEDS = {
    # --- Habr: тематические хабы ---
    # "pm":                    {"url": "https://habr.com/ru/rss/hubs/pm/articles/",                       "category": "Management"},
    # "hr_management":         {"url": "https://habr.com/ru/rss/hubs/hr_management/articles/",            "category": "Management"},
    # "statistics":            {"url": "https://habr.com/ru/rss/hubs/statistics/articles/",               "category": "Data"},
    # "productpm":             {"url": "https://habr.com/ru/rss/hubs/productpm/articles/",                "category": "Management"},
    # "analysis_design":       {"url": "https://habr.com/ru/rss/hubs/analysis_design/articles/",          "category": "Design"},
    # "dev_management":        {"url": "https://habr.com/ru/rss/hubs/dev_management/articles/",           "category": "Management"},
    # "complete_code":         {"url": "https://habr.com/ru/rss/hubs/complete_code/articles/",            "category": "Engineering"},
    # "devops":                {"url": "https://habr.com/ru/rss/hubs/devops/articles/",                   "category": "Cloud & DevOps"},
    # "git":                   {"url": "https://habr.com/ru/rss/hubs/git/articles/",                      "category": "Engineering"},
    # "agile":                 {"url": "https://habr.com/ru/rss/hubs/agile/articles/",                    "category": "Management"},
    # "web_testing":           {"url": "https://habr.com/ru/rss/hubs/web_testing/articles/",              "category": "Engineering"},
    # "mobile_testing":        {"url": "https://habr.com/ru/rss/hubs/mobile_testing/articles/",           "category": "Engineering"},
    # "programming":           {"url": "https://habr.com/ru/rss/hubs/programming/articles/",              "category": "Engineering"},
    # "java":                  {"url": "https://habr.com/ru/rss/hubs/java/articles/",                     "category": "Engineering"},
    # "kotlin":                {"url": "https://habr.com/ru/rss/hubs/kotlin/articles/",                   "category": "Engineering"},
    # "it_testing":            {"url": "https://habr.com/ru/rss/hubs/it_testing/articles/",               "category": "Engineering"},
    # "infosecurity":          {"url": "https://habr.com/ru/rss/hubs/infosecurity/articles/",             "category": "Security"},
    # "python":                {"url": "https://habr.com/ru/rss/hubs/python/articles/",                   "category": "Engineering"},
    # "win_dev":               {"url": "https://habr.com/ru/rss/hubs/win_dev/articles/",                  "category": "Engineering"},
    # "engineering_systems":   {"url": "https://habr.com/ru/rss/hubs/engineering_systems/articles/",      "category": "Engineering"},
    # "dwh":                   {"url": "https://habr.com/ru/rss/hubs/dwh/articles/",                      "category": "Data"},
    # "refactoring":           {"url": "https://habr.com/ru/rss/hubs/refactoring/articles/",              "category": "Engineering"},
    # "research":              {"url": "https://habr.com/ru/rss/hubs/research/articles/",                 "category": "Tech News"},
    # "sales":                 {"url": "https://habr.com/ru/rss/hubs/sales/articles/",                    "category": "Management"},
    # "business_models":       {"url": "https://habr.com/ru/rss/hubs/business_models/articles/",          "category": "Management"},
    # "itcompanies":           {"url": "https://habr.com/ru/rss/hubs/itcompanies/articles/",              "category": "Tech News"},
    # "artificial_intelligence":{"url": "https://habr.com/ru/rss/hubs/artificial_intelligence/articles/", "category": "AI & ML"},
    # "nlp":                   {"url": "https://habr.com/ru/rss/hubs/natural_language_processing/articles/", "category": "AI & ML"},
    # "machine_learning":      {"url": "https://habr.com/ru/rss/hubs/machine_learning/articles/",         "category": "AI & ML"},
    # "futurenow":             {"url": "https://habr.com/ru/rss/hubs/futurenow/articles/",                "category": "Tech News"},
    # "popular_science":       {"url": "https://habr.com/ru/rss/hubs/popular_science/articles/",          "category": "Tech News"},
    # "webdev":                {"url": "https://habr.com/ru/rss/hubs/webdev/articles/",                   "category": "Engineering"},
    # "itstandarts":           {"url": "https://habr.com/ru/rss/hubs/itstandarts/articles/",              "category": "Engineering"},
    # "usability":             {"url": "https://habr.com/ru/rss/hubs/usability/articles/",                "category": "Design"},
    # "api":                   {"url": "https://habr.com/ru/rss/hubs/api/articles/",                      "category": "Engineering"},
    # "reverse_engineering":   {"url": "https://habr.com/ru/rss/hubs/reverse-engineering/articles/",      "category": "Security"},
    # "hi":                    {"url": "https://habr.com/ru/rss/hubs/hi/articles/",                       "category": "Tech News"},
    # "crypto":                {"url": "https://habr.com/ru/rss/hubs/crypto/articles/",                   "category": "Security"},
    # "system_programming":    {"url": "https://habr.com/ru/rss/hubs/system_programming/articles/",       "category": "Engineering"},
    # "virtualization":        {"url": "https://habr.com/ru/rss/hubs/virtualization/articles/",           "category": "Cloud & DevOps"},
    # "cvs":                   {"url": "https://habr.com/ru/rss/hubs/cvs/articles/",                      "category": "Engineering"},
    # "tdd":                   {"url": "https://habr.com/ru/rss/hubs/tdd/articles/",                      "category": "Engineering"},
    # "algorithms":            {"url": "https://habr.com/ru/rss/hubs/algorithms/articles/",               "category": "Engineering"},
    # "parallel_programming":  {"url": "https://habr.com/ru/rss/hubs/parallel_programming/articles/",     "category": "Engineering"},
    # "funcprog":              {"url": "https://habr.com/ru/rss/hubs/funcprog/articles/",                 "category": "Engineering"},
    # "industrial_control_system": {"url": "https://habr.com/ru/rss/hubs/industrial_control_system/articles/", "category": "Engineering"},
    # "lib":                   {"url": "https://habr.com/ru/rss/hubs/lib/articles/",                      "category": "Engineering"},
    # "distributed_systems":   {"url": "https://habr.com/ru/rss/hubs/distributed_systems/articles/",      "category": "Engineering"},
    # "data_engineering":      {"url": "https://habr.com/ru/rss/hubs/data_engineering/articles/",         "category": "Data"},
    # "visual_programming":    {"url": "https://habr.com/ru/rss/hubs/visual_programming/articles/",       "category": "Engineering"},
    # "mobile_dev":            {"url": "https://habr.com/ru/rss/hubs/mobile_dev/articles/",               "category": "Engineering"},
    # "gtd":                   {"url": "https://habr.com/ru/rss/hubs/gtd/articles/",                      "category": "Management"},
    # "weban":                 {"url": "https://habr.com/ru/rss/hubs/weban/articles/",                    "category": "Data"},
    # "business_laws":         {"url": "https://habr.com/ru/rss/hubs/business-laws/articles/",            "category": "Management"},
    # "career":                {"url": "https://habr.com/ru/rss/hubs/career/articles/",                   "category": "Management"},
    # "technical_writing":     {"url": "https://habr.com/ru/rss/hubs/technical_writing/articles/",        "category": "Engineering"},
    # "startuprise":           {"url": "https://habr.com/ru/rss/hubs/startuprise/articles/",              "category": "Management"},
    # "terminator":            {"url": "https://habr.com/ru/rss/hubs/terminator/articles/",               "category": "Tech News"},
    # "community_management":  {"url": "https://habr.com/ru/rss/hubs/community_management/articles/",     "category": "Management"},

    # --- Habr: корпоративные блоги ---
    # "beeline_cloud":         {"url": "https://habr.com/ru/rss/companies/beeline_cloud/articles/",       "category": "Cloud & DevOps"},
    # "cian_company":          {"url": "https://habr.com/ru/rss/companies/cian/articles/",                "category": "Case Studies"},
    # "vk_company":            {"url": "https://habr.com/ru/rss/companies/vk/articles/",                  "category": "Tech News"},
    # "oleg_bunin":            {"url": "https://habr.com/ru/rss/companies/oleg-bunin/articles/",          "category": "Engineering"},
    # "raiffeisenbank":        {"url": "https://habr.com/ru/rss/companies/raiffeisenbank/articles/",      "category": "Case Studies"},
    # "simbirsoft":            {"url": "https://habr.com/ru/rss/companies/simbirsoft/articles/",          "category": "Engineering"},
    # "tochka":                {"url": "https://habr.com/ru/rss/companies/tochka/articles/",              "category": "Case Studies"},
    # "sberbank":              {"url": "https://habr.com/ru/rss/companies/sberbank/articles/",            "category": "Case Studies"},
    # "otus_company":          {"url": "https://habr.com/ru/rss/companies/otus/articles/",                "category": "Engineering"},
    # "avito_company":         {"url": "https://habr.com/ru/rss/companies/avito/articles/",               "category": "Case Studies"},
    # "testograf_company":     {"url": "https://habr.com/ru/rss/companies/testograf/articles/",           "category": "Case Studies"},
    # "vktech_company":        {"url": "https://habr.com/ru/rss/companies/vktech/articles/",              "category": "Engineering"},
    # "gazprombank":           {"url": "https://habr.com/ru/rss/companies/gazprombank/articles/",         "category": "Case Studies"},
    # "habr":                  {"url": "https://habr.com/ru/rss/companies/habr/articles/",                "category": "Tech News"},
    # "jetinfosystems":        {"url": "https://habr.com/ru/rss/companies/jetinfosystems/articles/",      "category": "Engineering"},
    # "mts_ai":                {"url": "https://habr.com/ru/rss/companies/mts_ai/articles/",              "category": "AI & ML"},
    # "mws":                   {"url": "https://habr.com/ru/rss/companies/mws/articles/",                 "category": "Cloud & DevOps"},
    # "ods":                   {"url": "https://habr.com/ru/rss/companies/ods/articles/",                 "category": "Data"},
    # "yadro":                 {"url": "https://habr.com/ru/rss/companies/yadro/articles/",               "category": "Engineering"},
    # "cleverpumpkin":         {"url": "https://habr.com/ru/rss/companies/cleverpumpkin/articles/",       "category": "Engineering"},
    # "inferit":               {"url": "https://habr.com/ru/rss/companies/inferit/articles/",             "category": "Engineering"},
    # "onlinepatent":          {"url": "https://habr.com/ru/rss/companies/onlinepatent/articles/",        "category": "Management"},
    # "x5tech":                {"url": "https://habr.com/ru/rss/companies/x5tech/articles/",              "category": "Case Studies"},
    # "redmadrobot":           {"url": "https://habr.com/ru/rss/companies/redmadrobot/articles/",         "category": "Engineering"},
    # "dododev":               {"url": "https://habr.com/ru/rss/companies/dododev/articles/",             "category": "Case Studies"},
    # "ru_mts":                {"url": "https://habr.com/ru/rss/companies/ru_mts/articles/",              "category": "Tech News"},

    # --- Toptal ---
    "toptal1": {"url": "https://www.toptal.com/project-managers/blog.rss",        "category": "Management"},
    "toptal2": {"url": "https://www.toptal.com/product-managers/blog.rss",         "category": "Management"},
    "toptal3": {"url": "https://www.toptal.com/management-consultants/blog.rss",   "category": "Management"},
    "toptal4": {"url": "https://www.toptal.com/developers/blog.rss",               "category": "Engineering"},

    # --- GitHub ---
    "Github Insights":          {"url": "https://github.blog/news-insights/feed/",     "category": "Tech News"},
    "Github AI & ML":           {"url": "https://github.blog/ai-and-ml/feed/",         "category": "AI & ML"},
    "Github Developer skills":  {"url": "https://github.blog/developer-skills/feed/",  "category": "Engineering"},
    "Github Engineering":       {"url": "https://github.blog/engineering/feed/",        "category": "Engineering"},
    "Github Enterprise software": {"url": "https://github.blog/enterprise-software/feed/", "category": "Tools"},
    "Github Open Source":       {"url": "https://github.blog/open-source/feed/",       "category": "Engineering"},
    "Github Security":          {"url": "https://github.blog/security/feed/",           "category": "Security"},
    # "Github":                {"url": "https://github.blog/feed/", "category": "Tech News"},  # агрегирует суб-ленты, дубли

    # "OpenAI": {"url": "https://openai.com/news/rss.xml", "category": "AI & ML"},  # нужен vpn

    # --- Google ---
    "Google":                   {"url": "https://blog.google/rss/",                                                            "category": "Tech News"},
    "Google DeepMind":          {"url": "https://deepmind.google/blog/rss.xml",                                                "category": "AI & ML"},
    "Google Research":          {"url": "https://research.google/blog/rss/",                                                   "category": "AI & ML"},
    "Google Developers":        {"url": "https://developers.googleblog.com/feeds/posts/default/?alt=rss",                      "category": "Engineering"},
    "Google Cloud":             {"url": "https://cloudblog.withgoogle.com/products/devops-sre/rss/",                           "category": "Cloud & DevOps"},

    "Google Cloud ai-machine-learning":       {"url": "https://cloudblog.withgoogle.com/products/ai-machine-learning/rss/",         "category": "AI & ML"},
    "Google Cloud api-management":            {"url": "https://cloudblog.withgoogle.com/products/api-management/rss/",              "category": "Cloud & DevOps"},
    "Google Cloud Application Development":   {"url": "https://cloudblog.withgoogle.com/products/application-development/rss/",     "category": "Engineering"},
    "Google Cloud Application Modernization": {"url": "https://cloudblog.withgoogle.com/products/application-modernization/rss/",   "category": "Cloud & DevOps"},
    "Google Cloud Chrome Enterprise":         {"url": "https://cloudblog.withgoogle.com/products/chrome-enterprise/rss/",           "category": "Tools"},
    "Google Cloud Compute":                   {"url": "https://cloudblog.withgoogle.com/products/compute/rss/",                     "category": "Cloud & DevOps"},
    "Google Cloud Containers & Kubernetes":   {"url": "https://cloudblog.withgoogle.com/products/containers-kubernetes/rss/",       "category": "Cloud & DevOps"},
    "Google Cloud Data Analytics":            {"url": "https://cloudblog.withgoogle.com/products/data-analytics/rss/",              "category": "Data"},
    "Google Cloud Databases":                 {"url": "https://cloudblog.withgoogle.com/products/databases/rss/",                   "category": "Data"},
    "Google Cloud DevOps & SRE":              {"url": "https://cloudblog.withgoogle.com/products/devops-sre/rss/",                  "category": "Cloud & DevOps"},
    "Google Cloud Threat Intelligence":       {"url": "https://cloudblog.withgoogle.com/topics/threat-intelligence/rss/",           "category": "Security"},
    "Google Cloud Infrastructure":            {"url": "https://cloudblog.withgoogle.com/products/infrastructure/rss/",              "category": "Cloud & DevOps"},
    "Google Cloud Infrastructure Modernization": {"url": "https://cloudblog.withgoogle.com/products/infrastructure-modernization/rss/", "category": "Cloud & DevOps"},
    "Google Cloud Storage & Data Transfer":   {"url": "https://cloudblog.withgoogle.com/products/storage-data-transfer/rss/",      "category": "Data"},
    "Google Cloud Startups":                  {"url": "https://cloudblog.withgoogle.com/topics/startups/rss/",                     "category": "Case Studies"},

    "Google workspace":         {"url": "https://blog.google/products-and-platforms/products/workspace/rss/", "category": "Tools"},
    "Google Ads & Commerce":    {"url": "https://blog.google/products/ads-commerce/rss/",                     "category": "Tools"},

    # --- Microsoft Azure ---
    "Microsoft Azure Blog":                         {"url": "https://azure.microsoft.com/en-us/blog/feed/",                                     "category": "Cloud & DevOps"},
    "Microsoft Azure Blog AI Professionals":        {"url": "https://azure.microsoft.com/en-us/blog/audience/ai-professionals/feed/",           "category": "AI & ML"},
    "Microsoft Azure Blog Business Decision Makers": {"url": "https://azure.microsoft.com/en-us/blog/audience/business-decision-makers/feed/",  "category": "Management"},
    "Microsoft Azure Blog Data Professionals":      {"url": "https://azure.microsoft.com/en-us/blog/audience/data-professionals/feed/",         "category": "Data"},
    "Microsoft Azure Blog Developers":              {"url": "https://azure.microsoft.com/en-us/blog/audience/developers/feed/",                 "category": "Engineering"},
    # "Microsoft Azure Blog IT Decision Makers": {"url": "https://azure.microsoft.com/en-us/blog/audience/it-decision-makers/feed/", "category": "Management"},  # дубли от Microsoft Azure Blog
    "Microsoft Azure Blog IT Implementors":         {"url": "https://azure.microsoft.com/en-us/blog/audience/it-implementors/feed/",            "category": "Cloud & DevOps"},
    "Microsoft Azure Blogs Best Practices":         {"url": "https://azure.microsoft.com/en-us/blog/content-type/best-practices/feed/",         "category": "Cloud & DevOps"},
    "Microsoft Azure Blogs Customer Stories":       {"url": "https://azure.microsoft.com/en-us/blog/content-type/customer-stories/feed/",       "category": "Case Studies"},

    # нужен vpn
    # "AWS Blog Insights":               {"url": "https://aws.amazon.com/ru/blogs/aws-insights/feed/",              "category": "Tech News"},
    # "AWS Blog AWS":                    {"url": "https://aws.amazon.com/ru/blogs/aws/feed/",                       "category": "Tech News"},
    # "AWS Blog DevOps":                 {"url": "https://aws.amazon.com/ru/blogs/devops/feed/",                    "category": "Cloud & DevOps"},
    # "AWS Blog Infrastructure":         {"url": "https://aws.amazon.com/ru/blogs/infrastructure-and-automation/feed/", "category": "Cloud & DevOps"},
    # "AWS Blog Open Source":            {"url": "https://aws.amazon.com/ru/blogs/opensource/feed/",                "category": "Engineering"},
    # "AWS Blog Business Intelligence":  {"url": "https://aws.amazon.com/ru/blogs/business-intelligence/feed/",    "category": "Data"},

    # --- MIT ---
    "MIT Technology Review": {"url": "https://www.technologyreview.com/feed", "category": "Tech News"},

    # --- Atlassian: Management ---
    "Atlassian Communication":   {"url": "https://www.atlassian.com/blog/communication/feed",    "category": "Management"},
    "Atlassian Distributed Work": {"url": "https://www.atlassian.com/blog/distributed-work/feed", "category": "Management"},
    "Atlassian Leadership":      {"url": "https://www.atlassian.com/blog/leadership/feed",        "category": "Management"},
    "Atlassian Productivity":    {"url": "https://www.atlassian.com/blog/productivity/feed",      "category": "Management"},
    "Atlassian Strategy":        {"url": "https://www.atlassian.com/blog/strategy/feed",          "category": "Management"},
    "Atlassian Teamwork":        {"url": "https://www.atlassian.com/blog/teamwork/feed",          "category": "Management"},
    "Atlassian Agile":           {"url": "https://www.atlassian.com/blog/agile/feed",             "category": "Management"},
    "Atlassian Project Management": {"url": "https://www.atlassian.com/blog/project-management/feed", "category": "Management"},
    "Atlassian Work Management": {"url": "https://www.atlassian.com/blog/work-management/feed",   "category": "Management"},
    "Atlassian Focus":           {"url": "https://www.atlassian.com/blog/focus/feed",             "category": "Management"},

    # --- Atlassian: Tools ---
    "Atlassian Add-ons":              {"url": "https://www.atlassian.com/blog/add-ons/feed",              "category": "Tools"},
    "Atlassian Bitbucket":            {"url": "https://www.atlassian.com/blog/bitbucket/feed",            "category": "Tools"},
    "Atlassian Crucible":             {"url": "https://www.atlassian.com/blog/crucible/feed",             "category": "Tools"},
    "Atlassian Halp":                 {"url": "https://www.atlassian.com/blog/halp/feed",                 "category": "Tools"},
    "Atlassian Access":               {"url": "https://www.atlassian.com/blog/access/feed",               "category": "Tools"},
    "Atlassian Confluence":           {"url": "https://www.atlassian.com/blog/confluence/feed",           "category": "Tools"},
    # "Atlassian Fisheye":           {"url": "https://www.atlassian.com/blog/fisheye/feed", "category": "Tools"},  # устаревший продукт, нет новых статей
    "Atlassian Jira":                 {"url": "https://www.atlassian.com/blog/jira/feed",                 "category": "Tools"},
    "Atlassian Bamboo":               {"url": "https://www.atlassian.com/blog/bamboo/feed",               "category": "Tools"},
    "Atlassian Crowd":                {"url": "https://www.atlassian.com/blog/crowd/feed",                "category": "Tools"},
    "Atlassian Jira Align":           {"url": "https://www.atlassian.com/blog/jira-align/feed",           "category": "Tools"},
    "Atlassian Jira Product Discovery": {"url": "https://www.atlassian.com/blog/jira-product-discovery/feed", "category": "Tools"},
    "Atlassian Sourcetree":           {"url": "https://www.atlassian.com/blog/sourcetree/feed",           "category": "Tools"},
    "Atlassian Jira Service Management": {"url": "https://www.atlassian.com/blog/jira-service-management/feed", "category": "Tools"},
    "Atlassian Statuspage":           {"url": "https://www.atlassian.com/blog/statuspage/feed",           "category": "Tools"},
    "Atlassian Loom":                 {"url": "https://www.atlassian.com/blog/loom/feed",                 "category": "Tools"},
    "Atlassian Trello":               {"url": "https://www.atlassian.com/blog/trello/feed",               "category": "Tools"},
    "Atlassian Enterprise":           {"url": "https://www.atlassian.com/blog/enterprise/feed",           "category": "Tools"},
    "Atlassian It Service Management": {"url": "https://www.atlassian.com/blog/it-service-management/feed", "category": "Tools"},

    # --- Atlassian: Engineering ---
    "Atlassian Atlassian Engineering": {"url": "https://www.atlassian.com/blog/atlassian-engineering/feed", "category": "Engineering"},
    "Atlassian Continuous Delivery":   {"url": "https://www.atlassian.com/blog/continuous-delivery/feed",   "category": "Engineering"},
    "Atlassian Developer":             {"url": "https://www.atlassian.com/blog/developer/feed",              "category": "Engineering"},
    "Atlassian Git":                   {"url": "https://www.atlassian.com/blog/git/feed",                    "category": "Engineering"},
    "Atlassian Devops":                {"url": "https://www.atlassian.com/blog/devops/feed",                 "category": "Cloud & DevOps"},

    # --- Atlassian: Other ---
    "Atlassian Artificial Intelligence": {"url": "https://www.atlassian.com/blog/artificial-intelligence/feed", "category": "AI & ML"},
    "Atlassian Design":                  {"url": "https://www.atlassian.com/blog/design/feed",                  "category": "Design"},
    "Atlassian Inside Atlassian":        {"url": "https://www.atlassian.com/blog/inside-atlassian/feed",        "category": "Case Studies"},
    "Atlassian Announcements":           {"url": "https://www.atlassian.com/blog/announcements/feed",           "category": "Tech News"},

    # "Slack Design": {"url": "https://slack.design/feed/", "category": "Design"},
    # "GitLab Blog":  {"url": "https://about.gitlab.com/atom.xml",    "category": "Engineering"},
    # "GitLab Releases": {"url": "https://about.gitlab.com/releases.xml", "category": "Tech News"},
    # "Figma":        {"url": "https://www.figma.com/blog/feed/atom.xml", "category": "Design"},
    # "Яндекс Cloud": {"url": "https://yandex.cloud/ru/feed.atom",    "category": "Cloud & DevOps"},

    # --- Российские ---
    "Сбербанк": {"url": "https://sberbs.ru/blogs/blog.atom", "category": "Case Studies"},

    # "VK Tech":          {"url": "", "category": "Engineering"},
    # "Ozon Tech":        {"url": "", "category": "Engineering"},
    # "Wb Tech":          {"url": "", "category": "Engineering"},
    # "Raiffeisenbank":   {"url": "", "category": "Engineering"},
}

# Описания источников для каталога (ключ — домен)
RSS_SOURCE_DESCRIPTIONS = {
    "www.atlassian.com":        "Всё о продуктивности команд и инструментах для совместной работы.",
    "cloudblog.withgoogle.com": "Как проектировать, масштабировать и защищать облачные системы.",
    "azure.microsoft.com":      "Облачные решения для разработчиков и бизнеса.",
    "github.blog":              "Жизнь разработчика: инструменты, тренды, культура.",
    "www.toptal.com":           "Опыт лучших специалистов в управлении и разработке продуктов.",
    "blog.google":              "Что делает Google и куда движутся технологии.",
}


def get_feed_urls() -> dict:
    """Возвращает {name: url} — формат для rss_parser и других мест где категория не нужна."""
    return {name: feed["url"] if isinstance(feed, dict) else feed for name, feed in RSS_FEEDS.items()}


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

