# -*- coding: utf-8 -*-
"""Pydantic-схемы для API (запросы/ответы)."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


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


class PipelineRunRequest(BaseModel):
    """Параметры запуска пайплайна обработки статей (фильтрация, эмбеддинги, суммаризация, RAG).

    RSS-сбор в этом эндпоинте НЕ выполняется — используйте POST /api/rss/collect
    для обновления данных из источников.
    """

    taxonomy_selection: Optional[Dict[str, Optional[str]]] = Field(
        default=None,
        description="Узел таксономии для фильтрации (discipline, ga, activity). Если не передан, используется конфигурация по умолчанию.",
        examples=[{"discipline": "Engineering", "ga": "DevOps", "activity": None}],
    )
    collection_name: Optional[str] = Field(
        default=None,
        description="Название создаваемой коллекции. Если не указано, генерируется автоматически на основе таксономии.",
        examples=["DevOps практики"],
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "taxonomy_selection": {"discipline": "Engineering", "ga": "DevOps", "activity": None},
                "collection_name": "DevOps практики",
            }
        }
    }


class PipelineRunResponse(BaseModel):
    """Результат выполнения пайплайна."""

    success: bool = Field(description="Признак успешного завершения пайплайна.")
    articles_count: int = Field(
        default=0,
        description="Количество статей, прошедших все этапы фильтрации и сохранённых в базу знаний.",
        examples=[42],
    )
    message: str = Field(
        default="",
        description="Человекочитаемое сообщение о результате выполнения.",
        examples=["Пайплайн завершён. Обработано статей: 42."],
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


class FeedValidateResponse(BaseModel):
    """Результат валидации RSS-ленты."""
    valid: bool = Field(description="True если URL является рабочим RSS/Atom фидом.")
    name: Optional[str] = Field(default=None, description="Название ленты из тега <title>.")
    favicon_url: Optional[str] = Field(default=None, description="URL логотипа сайта.")
    error: Optional[str] = Field(default=None, description="Текст ошибки если valid=False.")


class FeedCreate(BaseModel):
    """Данные для создания новой подписки на ленту."""
    url: str = Field(..., description="URL RSS-ленты.")
    name: str = Field(..., description="Название ленты.")
    favicon_url: Optional[str] = Field(default=None, description="URL логотипа — берётся из ответа /validate.")
    folder_id: Optional[int] = Field(default=None, description="ID папки в боковой панели (опционально).")


class FeedItem(BaseModel):
    """Лента пользователя — данные для отображения в боковой панели."""
    id: int = Field(description="Уникальный ID ленты.")
    url: str = Field(description="URL RSS-ленты.")
    name: str = Field(description="Название ленты.")
    favicon_url: Optional[str] = Field(default=None, description="URL логотипа.")
    enabled: bool = Field(description="Активна ли лента (участвует ли в сборе).")
    error_count: int = Field(default=0, description="Кол-во подряд идущих ошибок при сборе.")
    last_fetched_at: Optional[datetime] = Field(default=None, description="Когда последний раз успешно обновлялась.")
    last_error: Optional[str] = Field(default=None, description="Текст последней ошибки.")
    folder_id: Optional[int] = Field(default=None, description="ID папки в боковой панели.")

    model_config = {"from_attributes": True}


class FeedUpdate(BaseModel):
    """Изменяемые поля подписки на ленту."""
    name: Optional[str] = Field(default=None, description="Новое название.")
    enabled: Optional[bool] = Field(default=None, description="Включить или выключить ленту.")
    folder_id: Optional[int] = Field(default=None, description="Переместить в папку (None = корень).")


class CatalogFeedItem(BaseModel):
    """Лента из каталога — расширяет FeedItem статистикой и флагом подписки."""
    id: int = Field(description="Уникальный ID ленты.")
    url: str = Field(description="URL RSS-ленты.")
    name: str = Field(description="Название ленты.")
    favicon_url: Optional[str] = Field(default=None, description="URL логотипа.")
    enabled: bool = Field(description="Активна ли лента.")
    error_count: int = Field(default=0, description="Кол-во подряд идущих ошибок при сборе.")
    last_fetched_at: Optional[datetime] = Field(default=None, description="Когда последний раз обновлялась.")
    subscribers: int = Field(default=0, description="Кол-во пользователей подписанных на ленту.")
    posts_per_week: int = Field(default=0, description="Среднее кол-во постов в неделю за последние 30 дней.")
    last_post_at: Optional[datetime] = Field(default=None, description="Дата последней статьи из ленты.")
    is_subscribed: bool = Field(default=False, description="Подписан ли текущий пользователь на ленту.")

    model_config = {"from_attributes": True}


def serialize_digest_section_item(obj: Any) -> Any:
    """Сериализация элемента раздела дайджеста (datetime -> str)."""
    if hasattr(obj, "isoformat"):
        return obj.isoformat()
    if isinstance(obj, dict):
        return {k: serialize_digest_section_item(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [serialize_digest_section_item(x) for x in obj]
    return obj
