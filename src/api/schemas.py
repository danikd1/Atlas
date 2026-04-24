# -*- coding: utf-8 -*-
"""Pydantic-схемы для API (запросы/ответы)."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, EmailStr, Field


# ─── Auth ──────────────────────────────────────────────────────────────────


class AuthRegister(BaseModel):
    email: EmailStr = Field(..., description="Email пользователя")
    password: str = Field(..., min_length=6, description="Пароль (мин. 6 символов)")


class AuthLogin(BaseModel):
    email: str
    password: str


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserInfo(BaseModel):
    id: int
    email: str
    created_at: Optional[datetime] = None


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=6)


# ─── Router ──────���─────────────────────────────────────────────────────────


class RouterRequest(BaseModel):
    """Запрос к роутеру: подбор узлов таксономии по тексту на естественном языке."""

    query: str = Field(
        ...,
        min_length=1,
        description="Запрос пользователя на естественном языке. Роутер сопоставит его с таксономией и вернёт подходящий узел (Discipline / GA / Activity).",
        examples=["Как DevOps-инструменты помогают ускорить релизный цикл?"],
    )

    model_config = {
        "json_schema_extra": {
            "example": {"query": "Как DevOps-инструменты помогают ускорить релизный цикл?"}
        }
    }


class RouterResponse(BaseModel):
    """Ответ роутера с результатом сопоставления запроса с таксономией."""

    status: str = Field(
        description="Статус сопоставления: `matched` — найден узел, `not_found` — узел не определён, `clarification_needed` — требуется уточнение.",
        examples=["matched"],
    )
    selection: Optional[Dict[str, Optional[str]]] = Field(
        default=None,
        description="Найденный узел таксономии: discipline, ga, activity. Присутствует при status=matched.",
        examples=[{"discipline": "Engineering", "ga": "DevOps", "activity": "CI/CD"}],
    )
    clarification_question: Optional[str] = Field(
        default=None,
        description="Уточняющий вопрос к пользователю. Присутствует при status=clarification_needed.",
    )
    confidence: float = Field(
        default=0.0,
        description="Уверенность модели в выборе узла (0.0–1.0).",
        examples=[0.92],
    )
    reasoning: Optional[str] = Field(
        default=None,
        description="Пояснение модели: почему выбран данный узел таксономии.",
    )
    user_query: str = Field(
        default="",
        description="Исходный запрос пользователя, переданный в роутер.",
    )


class RssCollectRequest(BaseModel):
    """Параметры запуска сбора статей из RSS-лент."""

    hours_back: Optional[int] = Field(
        default=None,
        gt=0,
        description="Глубина выборки по времени (часов назад). Если не указано — используется значение из config (DEFAULT_HOURS_BACK).",
        examples=[168],
    )
    limit_per_feed: Optional[int] = Field(
        default=None,
        gt=0,
        description="Максимальное количество статей на ленту. Если не указано — из config.",
        examples=[30],
    )

    model_config = {
        "json_schema_extra": {
            "example": {"hours_back": 168, "limit_per_feed": 30}
        }
    }


class RssCollectResponse(BaseModel):
    """Результат сбора статей из RSS-лент."""

    success: bool = Field(description="Признак успешного завершения сбора.")
    new_articles: int = Field(
        default=0,
        description="Количество новых уникальных статей, добавленных в базу.",
        examples=[14],
    )
    total_parsed: int = Field(
        default=0,
        description="Суммарное количество записей, перебранных из RSS-лент.",
        examples=[87],
    )
    duplicates_skipped: int = Field(
        default=0,
        description="Пропущено дублей в рамках текущего запуска.",
        examples=[3],
    )
    already_processed_skipped: int = Field(
        default=0,
        description="Пропущено статей, уже сохранённых в БД в предыдущих запусках.",
        examples=[70],
    )
    feeds_processed: int = Field(
        default=0,
        description="Количество обработанных RSS-лент.",
        examples=[12],
    )
    feeds_failed: int = Field(
        default=0,
        description="Количество лент, завершившихся с ошибкой.",
        examples=[0],
    )
    time_elapsed_sec: float = Field(
        default=0.0,
        description="Время выполнения сбора (секунды).",
        examples=[8.34],
    )
    message: str = Field(
        default="",
        description="Человекочитаемое сообщение о результате.",
        examples=["Сбор завершён. Новых статей: 14."],
    )



class QARequest(BaseModel):
    """Запрос к Q&A-ассистенту по конкретной коллекции."""

    question: str = Field(
        ...,
        min_length=1,
        description="Вопрос пользователя на естественном языке в рамках выбранной коллекции.",
        examples=["Какие практики CI/CD наиболее эффективны для микросервисной архитектуры?"],
    )
    collection_id: int = Field(
        ...,
        gt=0,
        description="Идентификатор коллекции, по материалам которой формируется ответ.",
        examples=[3],
    )
    options: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Дополнительные параметры: top_k (количество фрагментов для retrieval), rerank (включить переранжирование) и др.",
        examples=[{"top_k": 5, "rerank": True}],
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "question": "Какие практики CI/CD наиболее эффективны для микросервисной архитектуры?",
                "collection_id": 3,
                "options": {"top_k": 5, "rerank": True},
            }
        }
    }


class QASource(BaseModel):
    """Источник, использованный при формировании ответа Q&A-ассистента."""

    link: str = Field(description="URL исходной статьи.", examples=["https://martinfowler.com/articles/microservices.html"])
    title: str = Field(description="Заголовок статьи-источника.", examples=["Microservices — Martin Fowler"])
    snippet: Optional[str] = Field(
        default=None,
        description="Релевантный фрагмент текста из статьи, использованный как контекст.",
    )


class QAResponse(BaseModel):
    """Ответ Q&A-ассистента с текстом ответа и ссылками на источники."""

    status: str = Field(
        description="Статус выполнения: `ok` — ответ сформирован, `error` — произошла ошибка.",
        examples=["ok"],
    )
    answer: Optional[str] = Field(
        default=None,
        description="Сформированный ответ на вопрос пользователя с опорой на материалы коллекции.",
    )
    sources: List[QASource] = Field(
        default=[],
        description="Список источников (статей), использованных для построения ответа.",
    )
    error: Optional[str] = Field(
        default=None,
        description="Описание ошибки. Присутствует только при status=error.",
    )


class CollectionItem(BaseModel):
    """Коллекция знаний — набор статей, привязанных к узлу таксономии."""

    id: int = Field(description="Уникальный идентификатор коллекции.", examples=[3])
    name: str = Field(description="Название коллекции.", examples=["DevOps практики"])
    description: Optional[str] = Field(default=None, description="Краткое описание коллекции.", examples=["Статьи о гибких методологиях разработки: Agile, Scrum, спринты."])
    discipline: Optional[str] = Field(default=None, description="Дисциплина (верхний уровень таксономии).", examples=["Engineering"])
    ga: Optional[str] = Field(default=None, description="Направление (второй уровень таксономии).", examples=["DevOps"])
    activity: Optional[str] = Field(default=None, description="Активность (третий уровень таксономии).", examples=["CI/CD"])
    collection_key: str = Field(description="Уникальный строковый ключ коллекции.", examples=["engineering__devops__cicd"])
    created_at: Optional[datetime] = Field(default=None, description="Дата и время создания коллекции.")
    updated_at: Optional[datetime] = Field(default=None, description="Дата и время последнего изменения.")
    last_refreshed_at: Optional[datetime] = Field(default=None, description="Дата и время последнего обновления данных коллекции пайплайном.")
    article_count: Optional[int] = Field(default=None, description="Количество уникальных статей в коллекции.")

    model_config = {"from_attributes": True}


class CollectionArticle(BaseModel):
    """Статья в составе коллекции."""

    link: str = Field(description="URL исходной статьи.", examples=["https://dev.to/example-article"])
    title: Optional[str] = Field(default=None, description="Заголовок статьи.", examples=["Understanding GitOps"])
    summary: Optional[str] = Field(default=None, description="Краткая аннотация статьи, сформированная LLM.")
    source: Optional[str] = Field(default=None, description="Название источника (домен или RSS-лента).", examples=["dev.to"])
    published_at: Optional[datetime] = Field(default=None, description="Дата публикации статьи в источнике.")


class FeedValidateRequest(BaseModel):
    """Запрос на валидацию RSS-ленты по URL перед сохранением."""
    url: str = Field(..., description="URL RSS-ленты для проверки.", examples=["https://habr.com/ru/rss/hubs/python/articles/"])
    gigachat_credentials: Optional[str] = Field(default=None, description="API-ключ GigaChat для генерации описания и категории.")
    gigachat_model: Optional[str] = Field(default=None)


class FeedValidateResponse(BaseModel):
    """Результат валидации RSS-ленты."""
    valid: bool = Field(description="True если URL является рабочим RSS/Atom фидом.")
    name: Optional[str] = Field(default=None, description="Название ленты из тега <title>.")
    description: Optional[str] = Field(default=None, description="Описание ленты из тега <description>.")
    favicon_url: Optional[str] = Field(default=None, description="URL логотипа сайта.")
    suggested_category: Optional[str] = Field(default=None, description="Категория предложенная GigaChat — пользователь может изменить.")
    error: Optional[str] = Field(default=None, description="Текст ошибки если valid=False.")


class FeedCreate(BaseModel):
    """Данные для создания новой подписки на ленту."""
    url: str = Field(..., description="URL RSS-ленты.")
    name: str = Field(..., description="Название ленты.")
    favicon_url: Optional[str] = Field(default=None, description="URL логотипа — берётся из ответа /validate.")
    description: Optional[str] = Field(default=None, description="Описание ленты — берётся из ответа /validate.")
    category: Optional[str] = Field(default=None, description="Категория ленты — берётся из suggested_category или задаётся пользователем вручную.")
    folder_id: Optional[int] = Field(default=None, description="ID папки в боковой панели (опционально).")


class FeedBatchCreate(BaseModel):
    """Данные для массовой подписки на ленты."""
    feeds: list[FeedCreate] = Field(..., description="Список лент для подписки.")


class FeedItem(BaseModel):
    """Лента пользователя — данные для отображения в боковой панели."""
    id: int = Field(description="Уникальный ID ленты.")
    url: str = Field(description="URL RSS-ленты.")
    name: str = Field(description="Название ленты.")
    favicon_url: Optional[str] = Field(default=None, description="URL логотипа.")
    description: Optional[str] = Field(default=None, description="Описание ленты.")
    category: Optional[str] = Field(default=None, description="Категория ленты.")
    enabled: bool = Field(description="Активна ли лента (участвует ли в сборе).")
    error_count: int = Field(default=0, description="Кол-во подряд идущих ошибок при сборе.")
    last_fetched_at: Optional[datetime] = Field(default=None, description="Когда последний раз успешно обновлялась.")
    last_error: Optional[str] = Field(default=None, description="Текст последней ошибки.")
    folder_id: Optional[int] = Field(default=None, description="ID папки в боковой панели.")
    hidden: bool = Field(default=False, description="Скрыта ли лента из боковой панели.")
    unread_count: int = Field(default=0, description="Количество непрочитанных статей.")
    created_at: Optional[datetime] = Field(default=None, description="Дата подписки пользователя.")

    model_config = {"from_attributes": True}


class ArticleItem(BaseModel):
    """Статья в списке ленты."""
    id: int = Field(description="ID статьи в processed_articles.")
    link: str = Field(description="URL оригинальной статьи.")
    title: Optional[str] = Field(default=None, description="Заголовок статьи.")
    summary: Optional[str] = Field(default=None, description="Краткое описание.")
    published_at: Optional[datetime] = Field(default=None, description="Дата публикации.")
    source: Optional[str] = Field(default=None, description="Название источника.")
    feed_id: Optional[int] = Field(default=None, description="ID ленты в которой опубликована статья.")
    is_read: bool = Field(default=False, description="Прочитана ли статья текущим пользователем.")
    is_saved: bool = Field(default=False, description="Добавлена ли статья в закладки.")

    model_config = {"from_attributes": True}


class ArticleReadRequest(BaseModel):
    """Запрос на пометку статьи прочитанной."""
    link: str = Field(..., description="URL статьи.")


class BookmarkRequest(BaseModel):
    """Запрос на добавление/удаление закладки."""
    link: str = Field(..., description="URL статьи.")


class SummarizeRequest(BaseModel):
    """Параметры запроса AI-резюме статьи."""
    gigachat_credentials: Optional[str] = Field(default=None)
    gigachat_model: Optional[str] = Field(default=None)


class SummarizeResponse(BaseModel):
    """Ответ эндпоинта суммаризации статьи."""
    ai_summary: Optional[str] = Field(
        default=None,
        description="AI-резюме статьи (3–4 предложения). null если не удалось извлечь текст.",
    )
    cached: bool = Field(
        default=False,
        description="True если резюме было взято из кэша (БД), False если только что сгенерировано.",
    )
    error: Optional[str] = Field(
        default=None,
        description="Описание ошибки. Присутствует если ai_summary=null.",
    )


class ArticleDetail(BaseModel):
    """Полные данные статьи для Reader mode."""
    id: int = Field(description="ID статьи в processed_articles.")
    link: str = Field(description="URL оригинальной статьи.")
    title: Optional[str] = Field(default=None, description="Заголовок статьи.")
    summary: Optional[str] = Field(default=None, description="Краткое описание.")
    full_text: Optional[str] = Field(default=None, description="Полный текст. null если извлечь не удалось.")
    published_at: Optional[datetime] = Field(default=None, description="Дата публикации.")
    source: Optional[str] = Field(default=None, description="Название источника.")
    is_read: bool = Field(default=False, description="Прочитана ли статья.")
    is_saved: bool = Field(default=False, description="Добавлена ли статья в закладки.")

    model_config = {"from_attributes": True}


class FeedUpdate(BaseModel):
    """Изменяемые поля подписки на ленту."""
    name: Optional[str] = Field(default=None, description="Новое название.")
    enabled: Optional[bool] = Field(default=None, description="Включить или выключить ленту.")
    folder_id: Optional[int] = Field(default=None, description="Переместить в папку (None = корень).")
    hidden: Optional[bool] = Field(default=None, description="Скрыть ленту из боковой панели без отписки.")


class FolderCreate(BaseModel):
    """Данные для создания папки."""
    name: str = Field(description="Название папки.")
    favicon_url: Optional[str] = Field(default=None, description="Favicon для папок созданных из каталога.")


class FolderItem(BaseModel):
    """Папка пользователя в боковой панели."""
    id: int
    name: str
    position: int = 0
    favicon_url: Optional[str] = None
    model_config = {"from_attributes": True}


class FolderUpdate(BaseModel):
    """Изменяемые поля папки."""
    name: Optional[str] = Field(default=None, description="Новое название папки.")
    position: Optional[int] = Field(default=None, description="Новая позиция в боковой панели.")


class CatalogFeedItem(BaseModel):
    """Лента из каталога — расширяет FeedItem статистикой и флагом подписки."""
    id: int = Field(description="Уникальный ID ленты.")
    url: str = Field(description="URL RSS-ленты.")
    name: str = Field(description="Название ленты.")
    favicon_url: Optional[str] = Field(default=None, description="URL логотипа.")
    description: Optional[str] = Field(default=None, description="Описание ленты.")
    category: Optional[str] = Field(default=None, description="Категория ленты (AI & ML, Engineering, и т.д.).")
    enabled: bool = Field(description="Активна ли лента.")
    error_count: int = Field(default=0, description="Кол-во подряд идущих ошибок при сборе.")
    last_fetched_at: Optional[datetime] = Field(default=None, description="Когда последний раз обновлялась.")
    subscribers: int = Field(default=0, description="Кол-во пользователей подписанных на ленту.")
    posts_per_week: int = Field(default=0, description="Среднее кол-во постов в неделю за последние 30 дней.")
    last_post_at: Optional[datetime] = Field(default=None, description="Дата последней статьи из ленты.")
    is_subscribed: bool = Field(default=False, description="Подписан ли текущий пользователь на ленту.")
    source_description: Optional[str] = Field(default=None, description="Описание источника (домена).")

    model_config = {"from_attributes": True}


class FeedQARequest(BaseModel):
    """Запрос QA по статьям из лент (без RAG-коллекций)."""
    feed_ids: List[int] = Field(default=[], description="ID лент пользователя.")
    collection_id: Optional[int] = Field(default=None, description="ID BERTopic-коллекции (приоритет над feed_ids).")
    question: str = Field(..., min_length=1, description="Вопрос пользователя.")
    from_date: Optional[datetime] = Field(default=None, description="Начало периода (ISO 8601).")
    to_date: Optional[datetime] = Field(default=None, description="Конец периода (ISO 8601).")
    top_k: int = Field(default=12, ge=1, le=40, description="Количество статей-источников для контекста.")
    gigachat_credentials: Optional[str] = Field(default=None, description="GigaChat API-ключ пользователя.")
    gigachat_model: Optional[str] = Field(default=None, description="Модель GigaChat.")

    model_config = {
        "json_schema_extra": {
            "example": {"feed_ids": [1, 2, 3], "question": "Какие новые LLM вышли за последний месяц?"}
        }
    }


class FeedQASourceItem(BaseModel):
    """Источник в ответе QA по лентам."""
    link: str
    title: str
    feed_name: str
    published_at: Optional[datetime] = None
    snippet: str
    article_id: int = 0


class FeedQAResponse(BaseModel):
    """Ответ QA по лентам."""
    status: str
    answer: Optional[str] = None
    sources: List[FeedQASourceItem] = []
    article_count: int = 0
    error: Optional[str] = None


class FeedDigestRequest(BaseModel):
    """Запрос дайджеста по статьям из лент."""
    feed_ids: List[int] = Field(default=[], description="ID лент пользователя.")
    collection_id: Optional[int] = Field(default=None, description="ID BERTopic-коллекции (приоритет над feed_ids).")
    from_date: Optional[datetime] = Field(default=None, description="Начало периода.")
    to_date: Optional[datetime] = Field(default=None, description="Конец периода.")
    gigachat_credentials: Optional[str] = Field(default=None, description="GigaChat API-ключ пользователя.")
    gigachat_model: Optional[str] = Field(default=None, description="Модель GigaChat.")

    model_config = {
        "json_schema_extra": {
            "example": {"feed_ids": [1, 2, 3]}
        }
    }


def serialize_digest_section_item(obj: Any) -> Any:
    """Сериализация элемента раздела дайджеста (datetime -> str)."""
    if hasattr(obj, "isoformat"):
        return obj.isoformat()
    if isinstance(obj, dict):
        return {k: serialize_digest_section_item(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [serialize_digest_section_item(x) for x in obj]
    return obj


# ── BERTopic API ───────────────────────────────────────────────────────────

class BertopicRunRequest(BaseModel):
    min_topic_size: int = Field(default=5, ge=2, description="Минимальный размер темы (статей).")
    n_categories: int = Field(default=10, ge=2, description="Количество мета-категорий KMeans.")
    skip_rag: bool = Field(default=True, description="Пропустить генерацию RAG-чанков (быстрее).")
    source_filter: Optional[str] = Field(default=None, description="Фильтр по источнику (ILIKE).")
    limit: Optional[int] = Field(default=None, ge=100, description="Лимит статей (по умолчанию все статьи подписок пользователя, рекомендуется не более 5000).")
    days_back: Optional[int] = Field(default=None, ge=1, description="Статьи за последние N дней (None = все).")
    gigachat_credentials: Optional[str] = Field(default=None, description="GigaChat API-ключ пользователя.")
    gigachat_model: Optional[str] = Field(default=None, description="Модель GigaChat.")


class BertopicRunResponse(BaseModel):
    task_id: str
    status: str
    message: str


class BertopicStatusResponse(BaseModel):
    task_id: str
    status: str          # pending | running | done | error
    progress: float      # 0.0 – 1.0
    message: str
    error: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    started_at: Optional[str] = None


class BertopicTopicItem(BaseModel):
    id: int                          # collection.id
    name: str
    description: Optional[str] = None
    keywords: Optional[str] = None   # "word1, word2, word3, ..."
    bertopic_topic_id: Optional[int] = None
    article_count: int
    model_version: Optional[str] = None


class BertopicTopicsResponse(BaseModel):
    topics: List[BertopicTopicItem]
    total: int


# ── GigaChat credentials test ──────────────────────────────────────────────

class GigaChatTestRequest(BaseModel):
    credentials: str = Field(..., description="GigaChat API-ключ для проверки.")
    model: Optional[str] = Field(default=None, description="Модель GigaChat (опционально).")


class GigaChatTestResponse(BaseModel):
    ok: bool = Field(description="True если подключение успешно.")
    error: Optional[str] = Field(default=None, description="Описание ошибки если ok=False.")

