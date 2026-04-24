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

    # ══════════════════════════════════════════════════════════════
    # HABR — тематические хабы
    # ══════════════════════════════════════════════════════════════

    # AI & ML
    "Habr: Искусственный интеллект": {"url": "https://habr.com/ru/rss/hubs/artificial_intelligence/articles/", "category": "AI & ML"},
    "Habr: Машинное обучение":       {"url": "https://habr.com/ru/rss/hubs/machine_learning/articles/",         "category": "AI & ML"},
    "Habr: NLP":                     {"url": "https://habr.com/ru/rss/hubs/natural_language_processing/articles/", "category": "AI & ML"},

    # Engineering
    "Habr: Программирование":          {"url": "https://habr.com/ru/rss/hubs/programming/articles/",          "category": "Engineering"},
    "Habr: Python":                    {"url": "https://habr.com/ru/rss/hubs/python/articles/",                "category": "Engineering"},
    "Habr: Java":                      {"url": "https://habr.com/ru/rss/hubs/java/articles/",                  "category": "Engineering"},
    "Habr: Kotlin":                    {"url": "https://habr.com/ru/rss/hubs/kotlin/articles/",                "category": "Engineering"},
    "Habr: Веб-разработка":            {"url": "https://habr.com/ru/rss/hubs/webdev/articles/",                "category": "Engineering"},
    "Habr: Мобильная разработка":      {"url": "https://habr.com/ru/rss/hubs/mobile_dev/articles/",            "category": "Engineering"},
    "Habr: Алгоритмы":                 {"url": "https://habr.com/ru/rss/hubs/algorithms/articles/",            "category": "Engineering"},
    "Habr: Распределённые системы":    {"url": "https://habr.com/ru/rss/hubs/distributed_systems/articles/",   "category": "Engineering"},
    "Habr: Системное программирование":{"url": "https://habr.com/ru/rss/hubs/system_programming/articles/",    "category": "Engineering"},
    "Habr: API":                       {"url": "https://habr.com/ru/rss/hubs/api/articles/",                   "category": "Engineering"},
    "Habr: Git":                       {"url": "https://habr.com/ru/rss/hubs/git/articles/",                   "category": "Engineering"},
    "Habr: Рефакторинг":               {"url": "https://habr.com/ru/rss/hubs/refactoring/articles/",           "category": "Engineering"},
    "Habr: Чистый код":                {"url": "https://habr.com/ru/rss/hubs/complete_code/articles/",         "category": "Engineering"},
    "Habr: TDD":                       {"url": "https://habr.com/ru/rss/hubs/tdd/articles/",                   "category": "Engineering"},
    "Habr: Тестирование":              {"url": "https://habr.com/ru/rss/hubs/it_testing/articles/",            "category": "Engineering"},
    "Habr: Тестирование веба":         {"url": "https://habr.com/ru/rss/hubs/web_testing/articles/",           "category": "Engineering"},
    "Habr: Тестирование мобильных":    {"url": "https://habr.com/ru/rss/hubs/mobile_testing/articles/",        "category": "Engineering"},
    "Habr: Параллельное программирование": {"url": "https://habr.com/ru/rss/hubs/parallel_programming/articles/", "category": "Engineering"},
    "Habr: Функциональное программирование": {"url": "https://habr.com/ru/rss/hubs/funcprog/articles/",        "category": "Engineering"},
    "Habr: Техническое писательство":  {"url": "https://habr.com/ru/rss/hubs/technical_writing/articles/",     "category": "Engineering"},
    "Habr: IT-стандарты":              {"url": "https://habr.com/ru/rss/hubs/itstandarts/articles/",           "category": "Engineering"},
    "Habr: Разработка под Windows":    {"url": "https://habr.com/ru/rss/hubs/win_dev/articles/",               "category": "Engineering"},

    # Cloud & DevOps
    "Habr: DevOps":          {"url": "https://habr.com/ru/rss/hubs/devops/articles/",         "category": "Cloud & DevOps"},
    "Habr: Виртуализация":   {"url": "https://habr.com/ru/rss/hubs/virtualization/articles/", "category": "Cloud & DevOps"},

    # Data
    "Habr: Data Engineering": {"url": "https://habr.com/ru/rss/hubs/data_engineering/articles/", "category": "Data"},
    "Habr: DWH":               {"url": "https://habr.com/ru/rss/hubs/dwh/articles/",              "category": "Data"},
    "Habr: Статистика":        {"url": "https://habr.com/ru/rss/hubs/statistics/articles/",       "category": "Data"},
    "Habr: Веб-аналитика":     {"url": "https://habr.com/ru/rss/hubs/weban/articles/",            "category": "Data"},

    # Security
    "Habr: Информационная безопасность": {"url": "https://habr.com/ru/rss/hubs/infosecurity/articles/",      "category": "Security"},
    "Habr: Криптография":                {"url": "https://habr.com/ru/rss/hubs/crypto/articles/",            "category": "Security"},
    "Habr: Реверс-инжиниринг":           {"url": "https://habr.com/ru/rss/hubs/reverse-engineering/articles/", "category": "Security"},

    # Design
    "Habr: Usability": {"url": "https://habr.com/ru/rss/hubs/usability/articles/",       "category": "Design"},
    "Habr: Анализ и проектирование": {"url": "https://habr.com/ru/rss/hubs/analysis_design/articles/", "category": "Design"},

    # Management
    "Habr: PM":                   {"url": "https://habr.com/ru/rss/hubs/pm/articles/",              "category": "Management"},
    "Habr: Продуктовый PM":       {"url": "https://habr.com/ru/rss/hubs/productpm/articles/",       "category": "Management"},
    "Habr: Agile":                {"url": "https://habr.com/ru/rss/hubs/agile/articles/",           "category": "Management"},
    "Habr: Управление разработкой":{"url": "https://habr.com/ru/rss/hubs/dev_management/articles/", "category": "Management"},
    "Habr: HR Management":        {"url": "https://habr.com/ru/rss/hubs/hr_management/articles/",   "category": "Management"},
    "Habr: GTD":                  {"url": "https://habr.com/ru/rss/hubs/gtd/articles/",             "category": "Management"},
    "Habr: Карьера":              {"url": "https://habr.com/ru/rss/hubs/career/articles/",          "category": "Management"},
    "Habr: Стартапы":             {"url": "https://habr.com/ru/rss/hubs/startuprise/articles/",     "category": "Management"},
    "Habr: Бизнес-модели":        {"url": "https://habr.com/ru/rss/hubs/business_models/articles/", "category": "Management"},
    "Habr: Законы и бизнес":      {"url": "https://habr.com/ru/rss/hubs/business-laws/articles/",   "category": "Management"},
    "Habr: Продажи":              {"url": "https://habr.com/ru/rss/hubs/sales/articles/",           "category": "Management"},

    # Tech News
    "Habr: IT-компании":    {"url": "https://habr.com/ru/rss/hubs/itcompanies/articles/",   "category": "Tech News"},
    "Habr: Будущее здесь":  {"url": "https://habr.com/ru/rss/hubs/futurenow/articles/",     "category": "Tech News"},
    "Habr: Научпоп":        {"url": "https://habr.com/ru/rss/hubs/popular_science/articles/", "category": "Tech News"},
    "Habr: Хай-тек":        {"url": "https://habr.com/ru/rss/hubs/hi/articles/",            "category": "Tech News"},
    "Habr: Исследования":   {"url": "https://habr.com/ru/rss/hubs/research/articles/",      "category": "Tech News"},

    # ══════════════════════════════════════════════════════════════
    # HABR — корпоративные блоги
    # ══════════════════════════════════════════════════════════════

    "Habr: Авито":          {"url": "https://habr.com/ru/rss/companies/avito/articles/",          "category": "Case Studies"},
    "Habr: VK":             {"url": "https://habr.com/ru/rss/companies/vk/articles/",             "category": "Tech News"},
    "Habr: VK Tech":        {"url": "https://habr.com/ru/rss/companies/vktech/articles/",         "category": "Engineering"},
    "Habr: Сбер":           {"url": "https://habr.com/ru/rss/companies/sberbank/articles/",       "category": "Case Studies"},
    "Habr: МТС":            {"url": "https://habr.com/ru/rss/companies/ru_mts/articles/",         "category": "Tech News"},
    "Habr: МТС AI":         {"url": "https://habr.com/ru/rss/companies/mts_ai/articles/",         "category": "AI & ML"},
    "Habr: МТС Web Services":{"url": "https://habr.com/ru/rss/companies/mws/articles/",           "category": "Cloud & DevOps"},
    "Habr: Райффайзенбанк": {"url": "https://habr.com/ru/rss/companies/raiffeisenbank/articles/", "category": "Case Studies"},
    "Habr: Газпромбанк":    {"url": "https://habr.com/ru/rss/companies/gazprombank/articles/",    "category": "Case Studies"},
    "Habr: Билайн Cloud":   {"url": "https://habr.com/ru/rss/companies/beeline_cloud/articles/",  "category": "Cloud & DevOps"},
    "Habr: X5 Tech":        {"url": "https://habr.com/ru/rss/companies/x5tech/articles/",         "category": "Case Studies"},
    "Habr: ЦИАН":           {"url": "https://habr.com/ru/rss/companies/cian/articles/",           "category": "Case Studies"},
    "Habr: Точка":          {"url": "https://habr.com/ru/rss/companies/tochka/articles/",         "category": "Case Studies"},
    "Habr: Додо Пицца":     {"url": "https://habr.com/ru/rss/companies/dododev/articles/",        "category": "Case Studies"},
    "Habr: Redmadrobot":    {"url": "https://habr.com/ru/rss/companies/redmadrobot/articles/",    "category": "Engineering"},
    "Habr: Simbirsoft":     {"url": "https://habr.com/ru/rss/companies/simbirsoft/articles/",     "category": "Engineering"},
    "Habr: OTUS":           {"url": "https://habr.com/ru/rss/companies/otus/articles/",           "category": "Engineering"},
    "Habr: YADRO":          {"url": "https://habr.com/ru/rss/companies/yadro/articles/",          "category": "Engineering"},
    "Habr: Jet Infosystems": {"url": "https://habr.com/ru/rss/companies/jetinfosystems/articles/","category": "Engineering"},
    "Habr: Олег Бунин":     {"url": "https://habr.com/ru/rss/companies/oleg-bunin/articles/",    "category": "Engineering"},
    "Habr: CleverPumpkin":  {"url": "https://habr.com/ru/rss/companies/cleverpumpkin/articles/",  "category": "Engineering"},
    "Habr: ODS":            {"url": "https://habr.com/ru/rss/companies/ods/articles/",            "category": "Data"},
    "Habr: Редакция":       {"url": "https://habr.com/ru/rss/companies/habr/articles/",           "category": "Tech News"},

    # ══════════════════════════════════════════════════════════════
    # GITHUB
    # ══════════════════════════════════════════════════════════════

    "GitHub: Insights":           {"url": "https://github.blog/news-insights/feed/",         "category": "Tech News"},
    "GitHub: AI & ML":            {"url": "https://github.blog/ai-and-ml/feed/",             "category": "AI & ML"},
    "GitHub: Developer Skills":   {"url": "https://github.blog/developer-skills/feed/",      "category": "Engineering"},
    "GitHub: Engineering":        {"url": "https://github.blog/engineering/feed/",            "category": "Engineering"},
    "GitHub: Open Source":        {"url": "https://github.blog/open-source/feed/",           "category": "Engineering"},
    "GitHub: Security":           {"url": "https://github.blog/security/feed/",              "category": "Security"},
    "GitHub: Enterprise":         {"url": "https://github.blog/enterprise-software/feed/",   "category": "Tools"},

    # ══════════════════════════════════════════════════════════════
    # GOOGLE
    # ══════════════════════════════════════════════════════════════

    "Google Blog":                {"url": "https://blog.google/rss/",                                                         "category": "Tech News"},
    "Google DeepMind":            {"url": "https://deepmind.google/blog/rss.xml",                                             "category": "AI & ML"},
    "Google Research":            {"url": "https://research.google/blog/rss/",                                                "category": "AI & ML"},
    "Google Developers":          {"url": "https://developers.googleblog.com/feeds/posts/default/?alt=rss",                   "category": "Engineering"},
    "Google Workspace":           {"url": "https://blog.google/products-and-platforms/products/workspace/rss/",               "category": "Tools"},
    "Google Ads & Commerce":      {"url": "https://blog.google/products/ads-commerce/rss/",                                  "category": "Tools"},

    "Google Cloud: AI & ML":                  {"url": "https://cloudblog.withgoogle.com/products/ai-machine-learning/rss/",          "category": "AI & ML"},
    "Google Cloud: Application Development":  {"url": "https://cloudblog.withgoogle.com/products/application-development/rss/",      "category": "Engineering"},
    "Google Cloud: API Management":           {"url": "https://cloudblog.withgoogle.com/products/api-management/rss/",               "category": "Cloud & DevOps"},
    "Google Cloud: Application Modernization":{"url": "https://cloudblog.withgoogle.com/products/application-modernization/rss/",    "category": "Cloud & DevOps"},
    "Google Cloud: Compute":                  {"url": "https://cloudblog.withgoogle.com/products/compute/rss/",                      "category": "Cloud & DevOps"},
    "Google Cloud: Containers & Kubernetes":  {"url": "https://cloudblog.withgoogle.com/products/containers-kubernetes/rss/",        "category": "Cloud & DevOps"},
    "Google Cloud: DevOps & SRE":             {"url": "https://cloudblog.withgoogle.com/products/devops-sre/rss/",                   "category": "Cloud & DevOps"},
    "Google Cloud: Infrastructure":           {"url": "https://cloudblog.withgoogle.com/products/infrastructure/rss/",               "category": "Cloud & DevOps"},
    "Google Cloud: Infrastructure Modernization": {"url": "https://cloudblog.withgoogle.com/products/infrastructure-modernization/rss/", "category": "Cloud & DevOps"},
    "Google Cloud: Chrome Enterprise":        {"url": "https://cloudblog.withgoogle.com/products/chrome-enterprise/rss/",            "category": "Tools"},
    "Google Cloud: Data Analytics":           {"url": "https://cloudblog.withgoogle.com/products/data-analytics/rss/",               "category": "Data"},
    "Google Cloud: Databases":                {"url": "https://cloudblog.withgoogle.com/products/databases/rss/",                    "category": "Data"},
    "Google Cloud: Storage & Data Transfer":  {"url": "https://cloudblog.withgoogle.com/products/storage-data-transfer/rss/",        "category": "Data"},
    "Google Cloud: Threat Intelligence":      {"url": "https://cloudblog.withgoogle.com/topics/threat-intelligence/rss/",            "category": "Security"},
    "Google Cloud: Startups":                 {"url": "https://cloudblog.withgoogle.com/topics/startups/rss/",                      "category": "Case Studies"},

    # ══════════════════════════════════════════════════════════════
    # MICROSOFT AZURE
    # ══════════════════════════════════════════════════════════════

    "Microsoft Azure: Blog":             {"url": "https://azure.microsoft.com/en-us/blog/feed/",                                       "category": "Cloud & DevOps"},
    "Microsoft Azure: AI":               {"url": "https://azure.microsoft.com/en-us/blog/audience/ai-professionals/feed/",             "category": "AI & ML"},
    "Microsoft Azure: Data":             {"url": "https://azure.microsoft.com/en-us/blog/audience/data-professionals/feed/",           "category": "Data"},
    "Microsoft Azure: Developers":       {"url": "https://azure.microsoft.com/en-us/blog/audience/developers/feed/",                   "category": "Engineering"},
    "Microsoft Azure: IT Implementors":  {"url": "https://azure.microsoft.com/en-us/blog/audience/it-implementors/feed/",              "category": "Cloud & DevOps"},
    "Microsoft Azure: Business":         {"url": "https://azure.microsoft.com/en-us/blog/audience/business-decision-makers/feed/",     "category": "Management"},
    "Microsoft Azure: Best Practices":   {"url": "https://azure.microsoft.com/en-us/blog/content-type/best-practices/feed/",           "category": "Cloud & DevOps"},
    "Microsoft Azure: Customer Stories": {"url": "https://azure.microsoft.com/en-us/blog/content-type/customer-stories/feed/",         "category": "Case Studies"},

    # ══════════════════════════════════════════════════════════════
    # ATLASSIAN
    # ══════════════════════════════════════════════════════════════

    # Engineering
    "Atlassian: Engineering":          {"url": "https://www.atlassian.com/blog/atlassian-engineering/feed", "category": "Engineering"},
    "Atlassian: Continuous Delivery":  {"url": "https://www.atlassian.com/blog/continuous-delivery/feed",  "category": "Engineering"},
    "Atlassian: Developer":            {"url": "https://www.atlassian.com/blog/developer/feed",             "category": "Engineering"},
    "Atlassian: Git":                  {"url": "https://www.atlassian.com/blog/git/feed",                  "category": "Engineering"},
    "Atlassian: DevOps":               {"url": "https://www.atlassian.com/blog/devops/feed",               "category": "Cloud & DevOps"},

    # Management
    "Atlassian: Agile":                {"url": "https://www.atlassian.com/blog/agile/feed",             "category": "Management"},
    "Atlassian: Project Management":   {"url": "https://www.atlassian.com/blog/project-management/feed","category": "Management"},
    "Atlassian: Leadership":           {"url": "https://www.atlassian.com/blog/leadership/feed",         "category": "Management"},
    "Atlassian: Teamwork":             {"url": "https://www.atlassian.com/blog/teamwork/feed",           "category": "Management"},
    "Atlassian: Productivity":         {"url": "https://www.atlassian.com/blog/productivity/feed",       "category": "Management"},
    "Atlassian: Strategy":             {"url": "https://www.atlassian.com/blog/strategy/feed",           "category": "Management"},
    "Atlassian: Work Management":      {"url": "https://www.atlassian.com/blog/work-management/feed",    "category": "Management"},
    "Atlassian: Communication":        {"url": "https://www.atlassian.com/blog/communication/feed",      "category": "Management"},
    "Atlassian: Distributed Work":     {"url": "https://www.atlassian.com/blog/distributed-work/feed",  "category": "Management"},
    "Atlassian: Focus":                {"url": "https://www.atlassian.com/blog/focus/feed",              "category": "Management"},

    # Tools
    "Atlassian: Jira":                    {"url": "https://www.atlassian.com/blog/jira/feed",                    "category": "Tools"},
    "Atlassian: Confluence":              {"url": "https://www.atlassian.com/blog/confluence/feed",              "category": "Tools"},
    "Atlassian: Trello":                  {"url": "https://www.atlassian.com/blog/trello/feed",                  "category": "Tools"},
    "Atlassian: Bitbucket":               {"url": "https://www.atlassian.com/blog/bitbucket/feed",               "category": "Tools"},
    "Atlassian: Jira Service Management": {"url": "https://www.atlassian.com/blog/jira-service-management/feed", "category": "Tools"},
    "Atlassian: Jira Product Discovery":  {"url": "https://www.atlassian.com/blog/jira-product-discovery/feed",  "category": "Tools"},
    "Atlassian: Jira Align":              {"url": "https://www.atlassian.com/blog/jira-align/feed",              "category": "Tools"},
    "Atlassian: Loom":                    {"url": "https://www.atlassian.com/blog/loom/feed",                    "category": "Tools"},
    "Atlassian: Statuspage":              {"url": "https://www.atlassian.com/blog/statuspage/feed",              "category": "Tools"},
    "Atlassian: Bamboo":                  {"url": "https://www.atlassian.com/blog/bamboo/feed",                  "category": "Tools"},
    "Atlassian: IT Service Management":   {"url": "https://www.atlassian.com/blog/it-service-management/feed",   "category": "Tools"},
    "Atlassian: Enterprise":              {"url": "https://www.atlassian.com/blog/enterprise/feed",              "category": "Tools"},
    "Atlassian: Add-ons":                 {"url": "https://www.atlassian.com/blog/add-ons/feed",                 "category": "Tools"},
    "Atlassian: Access":                  {"url": "https://www.atlassian.com/blog/access/feed",                  "category": "Tools"},

    # Other
    "Atlassian: AI":              {"url": "https://www.atlassian.com/blog/artificial-intelligence/feed", "category": "AI & ML"},
    "Atlassian: Design":          {"url": "https://www.atlassian.com/blog/design/feed",                  "category": "Design"},
    "Atlassian: Inside Atlassian":{"url": "https://www.atlassian.com/blog/inside-atlassian/feed",        "category": "Case Studies"},
    "Atlassian: Announcements":   {"url": "https://www.atlassian.com/blog/announcements/feed",           "category": "Tech News"},

    # ══════════════════════════════════════════════════════════════
    # TOPTAL
    # ══════════════════════════════════════════════════════════════

    "Toptal: Project Management":     {"url": "https://www.toptal.com/project-managers/blog.rss",       "category": "Management"},
    "Toptal: Product Management":     {"url": "https://www.toptal.com/product-managers/blog.rss",        "category": "Management"},
    "Toptal: Management Consulting":  {"url": "https://www.toptal.com/management-consultants/blog.rss",  "category": "Management"},
    "Toptal: Engineering":            {"url": "https://www.toptal.com/developers/blog.rss",              "category": "Engineering"},

    # ══════════════════════════════════════════════════════════════
    # ENGINEERING BLOGS
    # ══════════════════════════════════════════════════════════════

    "The Pragmatic Engineer": {"url": "https://blog.pragmaticengineer.com/rss/",                         "category": "Engineering"},
    "Meta Engineering":       {"url": "https://engineering.fb.com/feed/",                                "category": "Engineering"},
    "Stripe Blog":            {"url": "https://stripe.com/blog/feed.rss",                               "category": "Engineering"},
    "Cloudflare Blog":        {"url": "https://blog.cloudflare.com/rss/",                               "category": "Engineering"},
    "GitLab Blog":            {"url": "https://about.gitlab.com/atom.xml",                              "category": "Engineering"},
    "GitLab Releases":        {"url": "https://about.gitlab.com/releases.xml",                          "category": "Tech News"},
    "CSS-Tricks":             {"url": "https://feeds.feedburner.com/CssTricks",                         "category": "Engineering"},

    # ══════════════════════════════════════════════════════════════
    # AI & ML
    # ══════════════════════════════════════════════════════════════

    "Nvidia Developer Blog":  {"url": "https://developer.nvidia.com/blog/feed",      "category": "AI & ML"},
    "BAIR Blog":              {"url": "http://bair.berkeley.edu/blog/feed.xml",       "category": "AI & ML"},
    "Amazon Science":         {"url": "https://www.amazon.science/index.rss",         "category": "AI & ML"},
    # "OpenAI Engineering":   {"url": "https://openai.com/news/engineering/rss.xml",  "category": "AI & ML"},  # нужен VPN
    # "OpenAI News":          {"url": "https://openai.com/news/rss.xml",              "category": "AI & ML"},  # нужен VPN

    # ══════════════════════════════════════════════════════════════
    # AWS (нужен VPN из России)
    # ══════════════════════════════════════════════════════════════

    # "AWS: Blog":                 {"url": "https://aws.amazon.com/ru/blogs/aws/feed/",                              "category": "Tech News"},
    # "AWS: Insights":             {"url": "https://aws.amazon.com/ru/blogs/aws-insights/feed/",                    "category": "Tech News"},
    # "AWS: DevOps":               {"url": "https://aws.amazon.com/ru/blogs/devops/feed/",                          "category": "Cloud & DevOps"},
    # "AWS: Infrastructure":       {"url": "https://aws.amazon.com/ru/blogs/infrastructure-and-automation/feed/",   "category": "Cloud & DevOps"},
    # "AWS: Open Source":          {"url": "https://aws.amazon.com/ru/blogs/opensource/feed/",                      "category": "Engineering"},
    # "AWS: Business Intelligence":{"url": "https://aws.amazon.com/ru/blogs/business-intelligence/feed/",           "category": "Data"},

    # ══════════════════════════════════════════════════════════════
    # TECH MEDIA
    # ══════════════════════════════════════════════════════════════

    "MIT Technology Review":  {"url": "https://www.technologyreview.com/feed",         "category": "Tech News"},
    "Hacker News":            {"url": "http://news.ycombinator.com/rss",               "category": "Tech News"},
    "TechCrunch Startups":    {"url": "https://techcrunch.com/category/startups/feed/",  "category": "Tech News"},
    "The Verge":              {"url": "http://www.theverge.com/rss/full.xml",           "category": "Tech News"},
    "Forbes Entrepreneurs":   {"url": "https://www.forbes.com/innovation/feed/",          "category": "Management"},
    "Product Hunt":           {"url": "http://www.producthunt.com/feed",                "category": "Tools"},

    # ══════════════════════════════════════════════════════════════
    # DESIGN
    # ══════════════════════════════════════════════════════════════

    "UX Planet":    {"url": "https://uxplanet.org/feed",               "category": "Design"},
    "Slack Design": {"url": "https://slack.design/feed/",              "category": "Design"},
    "Figma Blog":   {"url": "https://www.figma.com/blog/feed/atom.xml","category": "Design"},

    # ══════════════════════════════════════════════════════════════
    # TOOLS
    # ══════════════════════════════════════════════════════════════

    "Grammarly Blog": {"url": "https://www.grammarly.com/blog/feed/", "category": "Tools"},

    # ══════════════════════════════════════════════════════════════
    # РОССИЙСКИЕ
    # ══════════════════════════════════════════════════════════════

    "Сбербанк":     {"url": "https://sberbs.ru/blogs/blog.atom",    "category": "Case Studies"},
}

# Описания источников для каталога (ключ — домен)
RSS_SOURCE_DESCRIPTIONS = {
    "www.atlassian.com":                    "Всё о продуктивности команд и инструментах для совместной работы.",
    "cloudblog.withgoogle.com":             "Как проектировать, масштабировать и защищать облачные системы.",
    "azure.microsoft.com":                  "Облачные решения для разработчиков и бизнеса.",
    "github.blog":                          "Жизнь разработчика: инструменты, тренды, культура.",
    "www.toptal.com":                       "Опыт лучших специалистов в управлении и разработке продуктов.",
    "blog.google":                          "Что делает Google и куда движутся технологии.",
    "news.ycombinator.com":                 "Самое обсуждаемое в мире технологий и стартапов.",
    "techcrunch.com":                       "Новости стартапов, венчурных инвестиций и технологий.",
    "www.forbes.com":                       "Истории предпринимателей и бизнес-инсайты.",
    "www.theverge.com":                     "Технологии, наука и культура — взгляд редакции.",
    "www.producthunt.com":                  "Лучшие новые продукты и инструменты каждый день.",
    "blog.pragmaticengineer.com":           "Карьера и технологии — взгляд изнутри крупных компаний.",
    "engineering.fb.com":                   "Как Meta решает инженерные задачи в масштабе миллиардов пользователей.",
    "stripe.com":                           "Инжиниринг платёжной инфраструктуры от команды Stripe.",
    "blog.cloudflare.com":                  "Сети, безопасность и производительность интернета.",
    "shopifyengineering.myshopify.com":     "Как Shopify строит платформу для миллионов магазинов.",
    "feeds.feedburner.com":                 "Советы и приёмы фронтенд-разработки.",
    "developer.nvidia.com":                 "GPU-вычисления, CUDA и нейросети от Nvidia.",
    "bair.berkeley.edu":                    "Исследования в области ИИ от Беркли.",
    "www.amazon.science":                   "Научные публикации и исследования команд Amazon.",
    "uxplanet.org":                         "UX-дизайн: паттерны, кейсы и практические советы.",
    "slack.design":                         "Дизайн-процесс и система дизайна команды Slack.",
    "www.mindtheproduct.com":               "Продуктовый менеджмент: методологии, кейсы, карьера.",
    "www.grammarly.com":                    "NLP, продуктовые решения и инженерия от команды Grammarly.",
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
# LaBSE — мультиязычная, 768d, 512 токенов (vs 128 у paraphrase-multilingual-mpnet-base-v2)
EMBEDDING_MODEL_NAME = "sentence-transformers/LaBSE"
# Старая модель (128 токенов — чанки обрезались, качество эмбеддингов снижено):
# EMBEDDING_MODEL_NAME = "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"

# Rerank для QA: cross-encoder (можно заменить на мультиязычный аналог при необходимости)
QA_RERANK_MODEL_NAME = "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"

# Извлечение текста: параметры
DEFAULT_TEXT_EXTRACTION_RETRIES = 3  # Количество попыток при ошибке
DEFAULT_TEXT_EXTRACTION_SLEEP = 2.0  # Задержка между попытками (секунды)
DEFAULT_TEXT_MIN_LENGTH = 300  # Минимальная длина текста для успешного извлечения

# GigaChat: конфигурация
GIGACHAT_CREDENTIALS = os.environ.get("GIGACHAT_CREDENTIALS", "")
GIGACHAT_MODEL = "GigaChat"  # Модель GigaChat
GIGACHAT_VERIFY_SSL = False  # Проверка SSL сертификатов

# Если False — GigaChat пропускается и сразу используется BART-fallback.
# Удобно для тестирования fallback без отключения интернета.
# Управляется переменной окружения: GIGACHAT_SUMMARIZATION_ENABLED=false python3 -m src.main
GIGACHAT_SUMMARIZATION_ENABLED: bool = (
    os.environ.get("GIGACHAT_SUMMARIZATION_ENABLED", "true").strip().lower() != "false"
)

# BART fallback: модель для суммаризации когда GigaChat недоступен.
# sshleifer/distilbart-cnn-6-6 — английский, ~400 MB, ~90% качества bart-large-cnn, в 2 раза быстрее
# facebook/bart-large-cnn      — английский, ~1.6 GB, высокое качество
# cointegrated/rut5-base-absum   — русский, ~250 MB, T5-based, в ~10x быстрее mBART на CPU (используется автоматически для RU-статей)
# IlyaGusev/mbart_ru_sum_gazeta  — русский, ~2.3 GB, mBART, высокое качество но крайне медленный на CPU (~50 мин/статья)
BART_SUMMARIZATION_MODEL = "sshleifer/distilbart-cnn-6-6"
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
POSTGRES_HOST = os.environ.get("POSTGRES_HOST", "localhost")
POSTGRES_PORT = int(os.environ.get("POSTGRES_PORT", "5432"))
POSTGRES_DB = os.environ.get("POSTGRES_DB", "postgres")
# По умолчанию — текущий пользователь macOS/Linux (как у Homebrew Postgres). Переопределение: POSTGRES_USER=...
POSTGRES_USER = os.environ.get("POSTGRES_USER") or getpass.getuser()
POSTGRES_PASSWORD = os.environ.get("POSTGRES_PASSWORD", "")

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
# LaBSE поддерживает 256 токенов (vs 128 у paraphrase-multilingual-mpnet-base-v2)
RAG_CHUNK_MAX_TOKENS = 256
RAG_CHUNK_OVERLAP_TOKENS = 50

# Дайджест (4 раздела без графа): кластеризация + LLM-описание/классификация
DIGEST_N_CLUSTERS = 15  # число кластеров KMeans (можно None для авто по HDBSCAN)
DIGEST_MAX_ITEMS_PER_SECTION = 5  # макс. кластеров в каждом разделе (key_trends, methods, tools, case_studies)
DIGEST_MAX_ARTICLES_PER_CLUSTER = 3  # макс. статей (по link) в блоке
DIGEST_LLM_LANGUAGE = "ru"  # "ru" | "en"
DIGEST_TYPICAL_CHUNKS_PER_CLUSTER = 5  # сколько чанков отдавать в LLM для описания кластера

# JWT-аутентификация
JWT_SECRET = os.environ.get("JWT_SECRET", "atlas-dev-secret-change-in-prod")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_DAYS = 7

# CORS: допустимые origins (через запятую в env)
ALLOWED_ORIGINS = os.environ.get(
    "ALLOWED_ORIGINS", "http://localhost:5173,http://localhost:8000"
).split(",")

# Ограничение регистрации: список разрешённых email через запятую.
# Если пустая строка — регистрация открыта (локальная разработка).
# Пример: ALLOWED_EMAILS=user1@example.com,user2@example.com
_raw = os.environ.get("ALLOWED_EMAILS", "").strip()
ALLOWED_EMAILS: set[str] = (
    {e.strip().lower() for e in _raw.split(",") if e.strip()}
    if _raw else set()
)

