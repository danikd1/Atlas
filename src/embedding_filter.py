"""
Модуль фильтрации статей с использованием эмбеддингов.

Обеспечивает:
- Построение topic embedding из ключевых слов и описаний топиков
- Фильтрацию статей по сходству с topic embedding
"""
import logging
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from sentence_transformers import SentenceTransformer

from config.config import (
    DEFAULT_EMBED_BATCH_SIZE,
    DEFAULT_EMBED_THRESHOLD,
    EMBEDDING_MODEL_NAME,
)

logger = logging.getLogger(__name__)


def get_embedding_model(model_name: str = EMBEDDING_MODEL_NAME) -> SentenceTransformer:
    """
    Создает экземпляр модели для эмбеддингов.
    
    Args:
        model_name: Название модели для загрузки
        
    Returns:
        Экземпляр SentenceTransformer
        
    Raises:
        RuntimeError: Если не удалось загрузить модель
    """
    try:
        logger.info(f"Загрузка модели эмбеддингов: {model_name}")
        model = SentenceTransformer(model_name)
        logger.info("✅ Модель загружена")
        return model
    except Exception as e:
        error_msg = f"Ошибка загрузки модели эмбеддингов '{model_name}': {e}"
        logger.error(error_msg)
        raise RuntimeError(error_msg) from e


def build_topic_embedding(
    keywords_config: Dict[str, List[str]],
    model: SentenceTransformer,
    topic_descriptions: Optional[List[str]] = None,
) -> np.ndarray:
    """
    Строит topic embedding только из описаний топиков.
    
    Args:
        keywords_config: Конфигурация ключевых слов (сохраняется для совместимости, не используется)
        model: Модель для эмбеддингов (обязательный параметр)
        topic_descriptions: Описания топиков (из таксономии по D/GA/A).
                           Должен быть непустым списком строк.
        
    Returns:
        Нормализованный topic embedding (вектор)
        
    Raises:
        ValueError: Если входные данные некорректны
        RuntimeError: Если не удалось построить embedding
    """
    if topic_descriptions is None:
        raise ValueError("topic_descriptions должен быть непустым списком описаний топиков")
    
    # Нормализуем и фильтруем описания
    proto_texts = [
        str(t).strip()
        for t in topic_descriptions
        if isinstance(t, str) and t.strip()
    ]
    if not proto_texts:
        raise ValueError("topic_descriptions не содержит ни одного непустого текстового описания")
    
    try:
        # Получаем эмбеддинги
        proto_embs = model.encode(proto_texts, normalize_embeddings=True)
        
        # Усредняем и нормализуем
        topic_embedding = proto_embs.mean(axis=0)
        topic_embedding /= np.linalg.norm(topic_embedding)
        
        logger.info(f"✅ Topic embedding построен, shape: {topic_embedding.shape}")
        return topic_embedding
    except Exception as e:
        error_msg = f"Ошибка при построении topic embedding: {e}"
        logger.error(error_msg)
        raise RuntimeError(error_msg) from e


def apply_embedding_filter(
    df_input: pd.DataFrame,
    topic_embedding: np.ndarray,
    model: SentenceTransformer,
    text_column: str = "embed_text",
    threshold: float = DEFAULT_EMBED_THRESHOLD,
    batch_size: int = DEFAULT_EMBED_BATCH_SIZE,
    show_progress_bar: bool = False
) -> pd.DataFrame:
    """
    Применяет embedding-фильтр к статьям.
    
    Args:
        df_input: DataFrame со статьями (должен содержать колонки 'title' и 'summary')
        topic_embedding: Эмбеддинг топика для сравнения
        model: Модель для эмбеддингов (обязательный параметр)
        text_column: Название колонки с текстом для оценки
        threshold: Порог сходства
        batch_size: Размер батча для обработки
        show_progress_bar: Показывать ли прогресс-бар
        
    Returns:
        DataFrame с добавленными колонками 'embed_similarity' и 'embed_ok'
        
    Raises:
        ValueError: Если входные данные некорректны
        RuntimeError: Если не удалось получить эмбеддинги
    """
    if df_input is None or df_input.empty:
        logger.warning("Пустой DataFrame на входе embedding-фильтра")
        return pd.DataFrame()
    
    if "title" not in df_input.columns or "summary" not in df_input.columns:
        raise ValueError("DataFrame должен содержать колонки 'title' и 'summary'")
    
    df_input = df_input.copy()
    
    # Создаем колонку с текстом для эмбеддинга, если её нет
    if text_column not in df_input.columns:
        df_input[text_column] = (
            df_input["title"].fillna("") + " " + df_input["summary"].fillna("")
        ).str.lower()
    
    texts = df_input[text_column].tolist()
    
    try:
        # Получаем эмбеддинги статей
        logger.info(f"Получение эмбеддингов для {len(texts)} статей...")
        article_embeds = model.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=show_progress_bar,
            normalize_embeddings=True
        )
        
        # Вычисляем сходство
        sims = np.dot(article_embeds, topic_embedding)
        
        df_input["embed_similarity"] = sims
        df_input["embed_ok"] = df_input["embed_similarity"] >= threshold
        
        logger.info(f"👉 Всего статей на входе: {len(df_input)}")
        logger.info(f"✅ Прошло эмбеддинг-фильтр: {int(df_input['embed_ok'].sum())}")
        logger.info(f"🔎 min/mean/max: {float(sims.min()):.3f} / {float(sims.mean()):.3f} / {float(sims.max()):.3f}")
        
        return df_input
    except Exception as e:
        error_msg = f"Ошибка при генерации эмбеддингов статей: {e}"
        logger.error(error_msg)
        raise RuntimeError(error_msg) from e


def filter_articles_by_embedding(
    df: pd.DataFrame,
    keywords_config: Dict[str, List[str]],
    model: SentenceTransformer,
    topic_descriptions: Optional[List[str]] = None,
    threshold: float = DEFAULT_EMBED_THRESHOLD,
    batch_size: int = DEFAULT_EMBED_BATCH_SIZE
) -> Tuple[pd.DataFrame, Dict]:
    """
    Фильтрует статьи по сходству с topic embedding.

    Args:
        df: DataFrame со статьями (должен содержать колонки 'title' и 'summary')
        keywords_config: Конфигурация ключевых слов (обязательный параметр)
        model: Модель для эмбеддингов (обязательный параметр)
        topic_descriptions: Описания топиков из таксономии (по выбранным D/GA/A). Если None — [].
        threshold: Порог сходства для фильтрации
        batch_size: Размер батча для обработки

    Returns:
        Tuple[отфильтрованный_DataFrame, статистика]
        
    Raises:
        ValueError: Если входные данные некорректны
        RuntimeError: Если не удалось построить embedding или применить фильтр
    """
    import time
    start_time = time.time()
    
    # Валидация входных данных
    if df is None or df.empty:
        return pd.DataFrame(), {
            "total_articles": 0,
            "passed": 0,
            "rejected": 0,
            "min_similarity": 0.0,
            "mean_similarity": 0.0,
            "max_similarity": 0.0,
            "time_elapsed_sec": 0
        }
    
    if "title" not in df.columns or "summary" not in df.columns:
        raise ValueError("DataFrame должен содержать колонки 'title' и 'summary'")
    
    # Построение topic embedding (ключевые слова + описания топиков из таксономии)
    logger.info("Построение topic embedding...")
    topic_embedding = build_topic_embedding(
        keywords_config, model, topic_descriptions=topic_descriptions
    )
    
    # Применение фильтра
    df_filtered = apply_embedding_filter(
        df,
        topic_embedding,
        model=model,
        threshold=threshold,
        batch_size=batch_size
    )
    
    # Разделение на прошедшие и отклоненные
    df_pass = df_filtered[df_filtered["embed_ok"] == True].copy()
    df_rejected = df_filtered[df_filtered["embed_ok"] == False].copy()
    
    end_time = time.time()
    elapsed = end_time - start_time
    
    stats = {
        "total_articles": len(df),
        "passed": len(df_pass),
        "rejected": len(df_rejected),
        "min_similarity": float(df_filtered["embed_similarity"].min()) if len(df_filtered) > 0 else 0.0,
        "mean_similarity": float(df_filtered["embed_similarity"].mean()) if len(df_filtered) > 0 else 0.0,
        "max_similarity": float(df_filtered["embed_similarity"].max()) if len(df_filtered) > 0 else 0.0,
        "time_elapsed_sec": elapsed
    }
    
    logger.info(f"Фильтрация завершена: {len(df_pass)}/{len(df)} статей прошло фильтр")
    
    return df_pass, stats
