# SberAgency Crawler

Пайплайн для сбора, фильтрации и суммаризации статей с Habr.

## Возможности

- 📥 Сбор статей из RSS-лент Habr
- 🔍 Фильтрация по ключевым словам с лемматизацией (таксономия D/GA/A)
- 🎯 Фильтрация по эмбеддингам (topic embedding из описаний топиков в таксономии)
- 📄 Извлечение полного текста статей
- 📝 Суммаризация статей с помощью LLM (GigaChat)

## Установка

1. Клонируйте репозиторий (или используйте существующий проект)

2. Установите зависимости:
```bash
pip3 install -r requirements.txt
```

3. Настройте таксономию и выбор узлов: ключевые слова и описания топиков задаются в `data/taxonomy.json` (узлы D/GA/A); выбранные узлы для пайплайна — в `config.config.TAXONOMY_SELECTION`.

## Использование

### Запуск пайплайна из командной строки

По умолчанию используются узлы таксономии из `config.config.TAXONOMY_SELECTION`:

```bash
python3 -m src.main
```

**Запрос через агента-роутера (LangGraph + GigaChat):** если передать `--query`, агент по запросу на естественном языке выберет узлы D/GA/A, и пайплайн запустится с этой выборкой:

```bash
python3 main.py --query "как определить границы MVP"
```

При необходимости уточнения агент вернёт вопрос; при `status=not_found` пайплайн запустится с `TAXONOMY_SELECTION` из config.

**Только тест роутера (без пайплайна):** посмотреть, как агент определяет узлы и почему он выбрал именно их:

```bash
python3 main.py --router-only --query "как определить границы MVP"
```

Или напрямую модуль роутера:

```bash
python3 -m src.agents.router "как определить границы MVP"
```

В выводе: выбранные D/GA/A, уверенность (confidence), нужное ли уточнение и поле **«Почему выбран этот узел»** (reasoning от LLM).

Результаты сохраняются в `outputs/articles_filtered.csv`.

## Структура проекта

```
SberAgencyCrawler/
├── src/
│   ├── main.py                 # Точка входа пайплайна
│   ├── rss_parser.py           # Парсинг RSS-лент
│   ├── taxonomy.py             # Таксономия D/GA/A, ключевые слова, topic_descriptions, domain block для роутера
│   ├── agents/
│   │   ├── router_prompt.py    # Системный промпт роутера
│   │   └── router.py           # Агент-роутер (LangGraph + GigaChat), выбор D/GA/A по запросу
│   ├── keywords.py             # Утилиты для плоского формата ключевых слов (legacy)
│   ├── lemmatization_filter.py  # Фильтрация с лемматизацией
│   ├── embedding_filter.py     # Фильтрация по эмбеддингам
│   ├── tools/
│   │   ├── text_extraction.py  # Извлечение текста
│   │   ├── llm_utils.py        # Утилиты для LLM
│   │   ├── prompt_loader.py    # Загрузка промптов
│   │   └── rate_limiter.py     # Ограничение частоты запросов
│   └── core/
│       └── constants.py        # Константы и Enums
├── config/
│   └── config.py               # Конфигурация пайплайна
├── data/
│   ├── taxonomy.json           # Таксономия (D/GA/A), ключевые слова и topic_descriptions
│   └── prompts.json            # Промпты для LLM
├── outputs/                    # Результаты работы
└── requirements.txt            # Зависимости
```

## Конфигурация

Основные параметры настраиваются в `config/config.py`:

- `RSS_FEEDS` - словарь RSS-лент для парсинга
- `TAXONOMY_SELECTION` - выбранные узлы таксономии (discipline, ga, activity) для фильтрации
- `DEFAULT_HOURS_BACK` - окно времени для сбора статей (по умолчанию 72 часа)
- `DEFAULT_EMBED_THRESHOLD` - порог для фильтрации по эмбеддингам
- `GIGACHAT_CREDENTIALS` - учетные данные для GigaChat API

## Технологии

- **Python 3.10+**
- **pandas** - обработка данных
- **feedparser** - парсинг RSS
- **pymorphy3** - лемматизация русского текста
- **sentence-transformers** - генерация эмбеддингов
- **trafilatura** - извлечение текста из веб-страниц
- **gigachat** - LLM для суммаризации

## Лицензия

Проект для внутреннего использования.
