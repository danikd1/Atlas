"""
Модуль для построения LangGraph workflow фильтрации релевантности статей.

Использует LangGraph для построения workflow с двумя агентами:
1. Фильтрация по заголовкам
2. Фильтрация по полному тексту (для неопределенных статей)
"""
import logging
from typing import List, Literal, Optional, TypedDict

import pandas as pd
from langgraph.graph import END, START, StateGraph

from config.config import (
    DEFAULT_RELEVANCE_TEMPERATURE,
    DEFAULT_TEXT_CLEAN_MAX_CHARS,
)
from src.core.constants import RelevanceStatus
from .tools.llm_utils import clean_text_for_llm, create_gigachat_client
from .tools.prompt_loader import format_prompt, load_prompt
from .tools.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)


# Описание состояния графа
class ArticleState(TypedDict):
    """Состояние для LangGraph workflow."""
    df: pd.DataFrame  # датафрейм со статьями
    undecided_idx: List[int]  # индексы строк, для которых ещё надо смотреть полный текст


def _create_title_filter_node(client, rate_limiter: Optional[RateLimiter] = None):
    """Создает узел title_filter с привязанным клиентом."""
    def title_filter_node(state: ArticleState) -> ArticleState:
        """
        Агент 1: решает по заголовкам.
        
        Классифицирует статьи на:
        - relevant: релевантные (можно сразу принять)
        - irrelevant: нерелевантные (можно сразу отклонить)
        - need_fulltext: нужен полный текст для решения
        
        Args:
            state: Состояние графа
            
        Returns:
            Обновленное состояние с колонкой 'relevance_title'
        """
        df = state["df"].copy()
        
        # Список статей для LLM (используем реальные индексы датафрейма)
        items = []
        for idx, row in df.iterrows():
            items.append(f"[index={idx}] {row['title']}")
        
        articles_block = "\n".join(items)
        
        # Загружаем промпты из файлов
        system_prompt = load_prompt("title_filter_system")
        user_prompt_template = load_prompt("title_filter_user")
        user_prompt = format_prompt(user_prompt_template, articles_block=articles_block)
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        
        # Rate limiting
        if rate_limiter:
            rate_limiter.wait_if_needed()
        
        try:
            result = client.chat({"messages": messages, "temperature": DEFAULT_RELEVANCE_TEMPERATURE})
            raw_answer = result.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"Ошибка при обращении к GigaChat в title_filter: {e}")
            # В случае ошибки все статьи помечаем как need_fulltext
            df["relevance_title"] = RelevanceStatus.NEED_FULLTEXT.value
            state["df"] = df
            state["undecided_idx"] = list(df.index)
            return state
        
        # Разбираем TSV
        title_decisions = {}
        for line in raw_answer.splitlines():
            line = line.strip()
            if not line:
                continue
            parts = line.split("\t")
            if len(parts) != 2:
                continue
            idx_str, decision = parts
            try:
                idx = int(idx_str)
            except ValueError:
                continue
            decision = decision.strip().lower()
            # Проверяем через Enum
            try:
                status = RelevanceStatus(decision)
                title_decisions[idx] = status.value
            except ValueError:
                logger.warning(f"Неизвестный статус релевантности: {decision}")
                continue
        
        # Записываем решения в датафрейм
        df["relevance_title"] = RelevanceStatus.NEED_FULLTEXT.value  # значение по умолчанию
        for idx, decision in title_decisions.items():
            if idx in df.index:
                df.at[idx, "relevance_title"] = decision
        
        # Индексы, которые нужно передать второму агенту
        undecided = [
            idx for idx, val in df["relevance_title"].items()
            if val == RelevanceStatus.NEED_FULLTEXT.value
        ]
        
        state["df"] = df
        state["undecided_idx"] = undecided
        
        return state
    
    return title_filter_node


def _create_fulltext_filter_node(client, rate_limiter: Optional[RateLimiter] = None):
    """Создает узел fulltext_filter с привязанным клиентом."""
    def fulltext_filter_node(state: ArticleState) -> ArticleState:
        """
        Агент 2: решает по полному тексту.
        
        Обрабатывает только статьи, помеченные как 'need_fulltext' после первого агента.
        
        Args:
            state: Состояние графа
            
        Returns:
            Обновленное состояние с колонкой 'relevance_fulltext'
        """
        df = state["df"].copy()
        undecided = state["undecided_idx"]
        
        if not undecided:
            # Нечего делать
            return state
        
        logger.info(f"Обработка {len(undecided)} статей по полному тексту...")
        
        for idx in undecided:
            row = df.loc[idx]
            title = row["title"]
            full_text = row.get("full_text")
            
            # Проверяем что full_text не None
            if full_text is None:
                logger.warning(f"full_text is None для статьи {idx}, помечаем как irrelevant")
                df.at[idx, "relevance_fulltext"] = RelevanceStatus.IRRELEVANT.value
                continue
            
            cleaned_text = clean_text_for_llm(full_text, max_chars=DEFAULT_TEXT_CLEAN_MAX_CHARS)
            
            # Загружаем промпты из файлов
            system_prompt_template = load_prompt("fulltext_filter_system")
            relevance_guidelines = load_prompt("relevance_guidelines")
            system_prompt = format_prompt(system_prompt_template, relevance_guidelines=relevance_guidelines)
            
            user_prompt_template = load_prompt("fulltext_filter_user")
            user_prompt = format_prompt(user_prompt_template, title=title, cleaned_text=cleaned_text)
            
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]
            
            # Rate limiting
            if rate_limiter:
                rate_limiter.wait_if_needed()
            
            try:
                result = client.chat({"messages": messages, "temperature": DEFAULT_RELEVANCE_TEMPERATURE})
                answer = result.choices[0].message.content.strip().lower()
            except Exception as e:
                logger.error(f"Ошибка при обращении к GigaChat для index={idx}: {e}")
                answer = RelevanceStatus.IRRELEVANT.value
            
            # Проверяем ответ через Enum
            if RelevanceStatus.RELEVANT.value in answer and RelevanceStatus.IRRELEVANT.value not in answer:
                final = RelevanceStatus.RELEVANT.value
            elif RelevanceStatus.IRRELEVANT.value in answer and RelevanceStatus.RELEVANT.value not in answer:
                final = RelevanceStatus.IRRELEVANT.value
            else:
                # если что-то странное вернул — считаем нерелевантным
                final = RelevanceStatus.IRRELEVANT.value
            
            df.at[idx, "relevance_fulltext"] = final
        
        state["df"] = df
        return state
    
    return fulltext_filter_node


def route_after_title(state: ArticleState) -> Literal["fulltext_filter", END]:
    """
    Роутинг: идти ли ко 2-му агенту.
    
    Если остались 'need_fulltext', идём в fulltext_filter, иначе END.
    """
    if state["undecided_idx"]:
        return "fulltext_filter"
    return END


def build_relevance_workflow(
    client,
    rate_limiter: Optional[RateLimiter] = None
) -> StateGraph:
    """
    Строит LangGraph workflow для фильтрации релевантности.
    
    Args:
        client: Клиент GigaChat (обязательный параметр)
        rate_limiter: Rate limiter для управления задержками
        
    Returns:
        Скомпилированный граф
    """
    workflow = StateGraph(ArticleState)
    
    title_node = _create_title_filter_node(client, rate_limiter)
    fulltext_node = _create_fulltext_filter_node(client, rate_limiter)
    
    workflow.add_node("title_filter", title_node)
    workflow.add_node("fulltext_filter", fulltext_node)
    
    workflow.add_edge(START, "title_filter")
    workflow.add_conditional_edges(
        "title_filter",
        route_after_title,
        {
            "fulltext_filter": "fulltext_filter",
            END: END,
        },
    )
    
    workflow.add_edge("fulltext_filter", END)
    
    return workflow.compile()


def compute_final_relevance(row: pd.Series) -> str:
    """
    Вычисляет финальную релевантность статьи на основе решений обоих агентов.
    
    Args:
        row: Строка DataFrame со статьей
        
    Returns:
        'relevant' или 'irrelevant'
    """
    title_decision = row.get("relevance_title", RelevanceStatus.NEED_FULLTEXT.value)
    fulltext_decision = row.get("relevance_fulltext", None)
    
    if title_decision == RelevanceStatus.RELEVANT.value:
        return RelevanceStatus.RELEVANT.value
    if title_decision == RelevanceStatus.IRRELEVANT.value:
        return RelevanceStatus.IRRELEVANT.value
    
    if title_decision == RelevanceStatus.NEED_FULLTEXT.value and fulltext_decision:
        if fulltext_decision == RelevanceStatus.RELEVANT.value:
            return RelevanceStatus.RELEVANT.value
        if fulltext_decision == RelevanceStatus.IRRELEVANT.value:
            return RelevanceStatus.IRRELEVANT.value
    
    # fallback
    return RelevanceStatus.IRRELEVANT.value


def filter_articles_by_relevance(
    df: pd.DataFrame,
    client,
    rate_limiter: Optional[RateLimiter] = None
) -> pd.DataFrame:
    """
    Фильтрует статьи по релевантности используя LLM workflow.
    
    Args:
        df: DataFrame со статьями (должен содержать колонки 'title' и 'full_text')
        client: Клиент GigaChat (обязательный параметр)
        rate_limiter: Rate limiter для управления задержками
        
    Returns:
        DataFrame с добавленными колонками 'relevance_title', 'relevance_fulltext', 'relevance_final'
        и отфильтрованный только по релевантным статьям
        
    Raises:
        ValueError: Если DataFrame не содержит нужные колонки
    """
    if "title" not in df.columns:
        raise ValueError("DataFrame должен содержать колонку 'title'")
    
    if "full_text" not in df.columns:
        raise ValueError("DataFrame должен содержать колонку 'full_text'")
    
    if df.empty:
        logger.warning("Пустой DataFrame на входе relevance-фильтра")
        return pd.DataFrame()
    
    # Создаем workflow
    article_graph = build_relevance_workflow(client, rate_limiter)
    
    # Начальное состояние
    initial_state: ArticleState = {
        "df": df.copy(),
        "undecided_idx": []  # заполнится внутри title_filter_node
    }
    
    # Запускаем workflow
    logger.info(f"Запуск LLM-фильтрации релевантности для {len(df)} статей...")
    final_state = article_graph.invoke(initial_state)
    
    df_with_relevance = final_state["df"]
    
    # Вычисляем финальную релевантность
    df_with_relevance["relevance_final"] = df_with_relevance.apply(compute_final_relevance, axis=1)
    
    # Оставляем только релевантные статьи
    df_relevant = df_with_relevance[df_with_relevance["relevance_final"] == RelevanceStatus.RELEVANT.value].copy()
    
    logger.info(f"✅ LLM-фильтрация завершена: {len(df_relevant)}/{len(df)} статей релевантны")
    
    return df_relevant
