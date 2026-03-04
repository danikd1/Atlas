"""
Скрипт для оценки метрик пайплайна на размеченном датасете.

Загружает metrik.xlsx, прогоняет через каждый этап пайплайна
и считает метрики (Precision, Recall, FPR) после каждого этапа.
"""
import pandas as pd
from typing import Dict, Tuple

from src.embedding_filter import filter_articles_by_embedding, get_embedding_model
from src.lemmatization_filter import filter_articles_by_keywords
from src.taxonomy import get_keywords_config_for_selection, get_topic_descriptions_for_selection, load_taxonomy
from config.config import (
    DEFAULT_EMBED_THRESHOLD,
    GENERIC_SINGLE_LEMMAS,
    TAXONOMY_SELECTION,
)


def calculate_metrics(y_true: pd.Series, y_pred: pd.Series) -> Dict[str, float]:
    """
    Вычисляет метрики классификации.
    
    Args:
        y_true: Истинные метки (1 = релевантно, 0 = нерелевантно)
        y_pred: Предсказанные метки (1 = релевантно, 0 = нерелевантно)
        
    Returns:
        Словарь с метриками: precision, recall, fpr
    """
    # Подсчет TP, FP, TN, FN
    TP = ((y_true == 1) & (y_pred == 1)).sum()
    FP = ((y_true == 0) & (y_pred == 1)).sum()
    TN = ((y_true == 0) & (y_pred == 0)).sum()
    FN = ((y_true == 1) & (y_pred == 0)).sum()
    
    # Метрики
    precision = TP / (TP + FP) if (TP + FP) > 0 else 0.0
    recall = TP / (TP + FN) if (TP + FN) > 0 else 0.0
    fpr = FP / (FP + TN) if (FP + TN) > 0 else 0.0
    
    return {
        "TP": int(TP),
        "FP": int(FP),
        "TN": int(TN),
        "FN": int(FN),
        "precision": precision,
        "recall": recall,
        "fpr": fpr,
        "total": len(y_true),
        "predicted_positive": int(TP + FP),
        "actual_positive": int(TP + FN),
    }


def evaluate_pipeline():
    """
    Загружает размеченный датасет и прогоняет через пайплайн,
    вычисляя метрики после каждого этапа.
    """
    print("="*80)
    print("📊 ОЦЕНКА МЕТРИК ПАЙПЛАЙНА")
    print("="*80)
    print()
    
    # Загрузка размеченного датасета
    print("📥 Загрузка размеченного датасета...")
    df_ground_truth = pd.read_excel("metrik.xlsx")
    
    # Подготовка данных для пайплайна
    # Переименовываем колонки под формат пайплайна
    df_articles = pd.DataFrame({
        "title": df_ground_truth["Title"],
        "summary": df_ground_truth["Summary"],
        "link": df_ground_truth["Link"],
    })
    
    # Ground truth метки
    y_true = df_ground_truth["Label (1/0)"]
    
    print(f"   ✓ Загружено статей: {len(df_articles)}")
    print(f"   ✓ Релевантных (Label=1): {y_true.sum()}")
    print(f"   ✓ Нерелевантных (Label=0): {(y_true == 0).sum()}")
    print()
    
    # Этап 0: Базовый (все статьи проходят)
    print("="*80)
    print("Этап 0: Базовый (все статьи)")
    print("="*80)
    y_pred_baseline = pd.Series([1] * len(df_articles), index=df_articles.index)
    metrics_baseline = calculate_metrics(y_true, y_pred_baseline)
    print_metrics(metrics_baseline)
    print()
    
    # Этап 1: Фильтрация по ключевым словам (ключевые слова из таксономии)
    print("="*80)
    print("Этап 1: Фильтрация по ключевым словам (лемматизация)")
    print("="*80)
    taxonomy = load_taxonomy()
    keywords_config = get_keywords_config_for_selection(taxonomy, TAXONOMY_SELECTION)
    topic_descriptions = get_topic_descriptions_for_selection(taxonomy, TAXONOMY_SELECTION)
    df_keywords, stats_keywords = filter_articles_by_keywords(
        df_articles,
        keywords_config=keywords_config,
        generic_single_lemmas=GENERIC_SINGLE_LEMMAS
    )
    
    # Создаем предсказания: 1 если статья прошла фильтр, 0 если нет
    y_pred_keywords = pd.Series(0, index=df_articles.index)
    y_pred_keywords[df_keywords.index] = 1
    
    metrics_keywords = calculate_metrics(y_true, y_pred_keywords)
    print_metrics(metrics_keywords)
    print()
    
    # Этап 2: Фильтрация по эмбеддингам (на ВСЕМ датасете, те же ключевые слова из таксономии)
    print("="*80)
    print("Этап 2: Фильтрация по эмбеддингам (на всем датасете)")
    print("="*80)
    embed_model = get_embedding_model()
    
    # Применяем embedding-фильтр ко ВСЕМУ датасету для правильной оценки метрик
    df_embedding, stats_embedding = filter_articles_by_embedding(
        df_articles,  # Используем весь датасет, а не df_keywords
        keywords_config=keywords_config,
        model=embed_model,
        topic_descriptions=topic_descriptions,
        threshold=DEFAULT_EMBED_THRESHOLD
    )
    
    # Создаем предсказания: 1 если статья прошла фильтр, 0 если нет
    y_pred_embedding = pd.Series(0, index=df_articles.index)
    y_pred_embedding[df_embedding.index] = 1
    
    metrics_embedding = calculate_metrics(y_true, y_pred_embedding)
    print_metrics(metrics_embedding)
    print()
    
    # Этап 3: Комбинированный (boolean + embedding)
    print("="*80)
    print("Этап 3: Комбинированный фильтр (boolean + embedding)")
    print("="*80)
    
    # Применяем embedding-фильтр к результатам boolean-фильтра
    df_combined, stats_combined = filter_articles_by_embedding(
        df_keywords,
        keywords_config=keywords_config,
        model=embed_model,
        topic_descriptions=topic_descriptions,
        threshold=DEFAULT_EMBED_THRESHOLD
    )
    
    # Создаем предсказания: 1 если статья прошла оба фильтра, 0 если нет
    y_pred_combined = pd.Series(0, index=df_articles.index)
    y_pred_combined[df_combined.index] = 1
    
    metrics_combined = calculate_metrics(y_true, y_pred_combined)
    print_metrics(metrics_combined)
    print()
    
    # Итоговая сводка
    print("="*80)
    print("📊 ИТОГОВАЯ СВОДКА МЕТРИК")
    print("="*80)
    print()
    print(f"{'Этап':<45} {'Precision':<12} {'Recall':<12} {'FPR':<12} {'Статей':<10}")
    print("-" * 90)
    print(f"{'0. Базовый (все статьи)':<45} {metrics_baseline['precision']:<12.4f} {metrics_baseline['recall']:<12.4f} {metrics_baseline['fpr']:<12.4f} {metrics_baseline['total']:<10}")
    print(f"{'1. Фильтрация по ключевым словам':<45} {metrics_keywords['precision']:<12.4f} {metrics_keywords['recall']:<12.4f} {metrics_keywords['fpr']:<12.4f} {metrics_keywords['predicted_positive']:<10}")
    print(f"{'2. Фильтрация по эмбеддингам (на всем датасете)':<45} {metrics_embedding['precision']:<12.4f} {metrics_embedding['recall']:<12.4f} {metrics_embedding['fpr']:<12.4f} {metrics_embedding['predicted_positive']:<10}")
    print(f"{'3. Комбинированный (boolean + embedding)':<45} {metrics_combined['precision']:<12.4f} {metrics_combined['recall']:<12.4f} {metrics_combined['fpr']:<12.4f} {metrics_combined['predicted_positive']:<10}")
    print()
    
    return {
        "baseline": metrics_baseline,
        "keywords": metrics_keywords,
        "embedding": metrics_embedding,
        "combined": metrics_combined,
    }


def print_metrics(metrics: Dict[str, float]) -> None:
    """Выводит метрики в читаемом формате."""
    print(f"   TP (True Positive):  {metrics['TP']}")
    print(f"   FP (False Positive): {metrics['FP']}")
    print(f"   TN (True Negative):  {metrics['TN']}")
    print(f"   FN (False Negative): {metrics['FN']}")
    print()
    print(f"   Precision = TP / (TP + FP) = {metrics['TP']} / ({metrics['TP']} + {metrics['FP']}) = {metrics['precision']:.4f}")
    print(f"   Recall    = TP / (TP + FN) = {metrics['TP']} / ({metrics['TP']} + {metrics['FN']}) = {metrics['recall']:.4f}")
    print(f"   FPR       = FP / (FP + TN) = {metrics['FP']} / ({metrics['FP']} + {metrics['TN']}) = {metrics['fpr']:.4f}")
    print()
    print(f"   Всего статей: {metrics['total']}")
    print(f"   Предсказано релевантных: {metrics['predicted_positive']}")
    print(f"   Фактически релевантных: {metrics['actual_positive']}")


if __name__ == "__main__":
    evaluate_pipeline()

