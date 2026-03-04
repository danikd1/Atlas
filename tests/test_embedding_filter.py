"""
Тесты для модуля embedding_filter.
"""
import numpy as np
import pandas as pd
import pytest
from sentence_transformers import SentenceTransformer

from src.embedding_filter import (
    apply_embedding_filter,
    build_topic_embedding,
    filter_articles_by_embedding,
    get_embedding_model,
)


class TestGetEmbeddingModel:
    """Тесты для функции get_embedding_model."""
    
    def test_get_embedding_model_returns_model(self):
        """Проверяет, что функция возвращает экземпляр SentenceTransformer."""
        model = get_embedding_model()
        assert isinstance(model, SentenceTransformer)
    
    def test_get_embedding_model_custom_name(self):
        """Проверяет загрузку модели с кастомным именем."""
        # Используем ту же модель, что и по умолчанию
        from config.config import EMBEDDING_MODEL_NAME
        model = get_embedding_model(EMBEDDING_MODEL_NAME)
        assert isinstance(model, SentenceTransformer)


class TestBuildTopicEmbedding:
    """Тесты для функции build_topic_embedding."""
    
    @pytest.fixture
    def model(self):
        """Фикстура для модели эмбеддингов."""
        return get_embedding_model()
    
    @pytest.fixture
    def keywords_config(self):
        """Фикстура для конфигурации ключевых слов."""
        return {
            "strong": ["dora", "cicd", "devops"],
            "weak": ["agile", "kanban"]
        }
    
    @pytest.fixture
    def topic_descriptions(self):
        """Фикстура для описаний топиков."""
        return [
            "Статьи про DevOps метрики и CI/CD пайплайны.",
            "Материалы про процессы доставки и стабильность релизов."
        ]
    
    def test_build_topic_embedding_shape(self, model, keywords_config, topic_descriptions):
        """Проверяет форму topic embedding."""
        topic_embedding = build_topic_embedding(keywords_config, model, topic_descriptions)
        
        assert isinstance(topic_embedding, np.ndarray)
        assert topic_embedding.ndim == 1
        assert topic_embedding.shape[0] > 0
    
    def test_build_topic_embedding_normalized(self, model, keywords_config, topic_descriptions):
        """Проверяет, что topic embedding нормализован."""
        topic_embedding = build_topic_embedding(keywords_config, model, topic_descriptions)
        
        norm = np.linalg.norm(topic_embedding)
        assert abs(norm - 1.0) < 1e-6  # Должен быть нормализован
    
    def test_build_topic_embedding_invalid_config(self, model):
        """Проверяет обработку некорректной конфигурации."""
        with pytest.raises(ValueError):
            build_topic_embedding({}, model)  # keywords_config игнорируется, но topic_descriptions обязателен


class TestApplyEmbeddingFilter:
    """Тесты для функции apply_embedding_filter."""
    
    @pytest.fixture
    def model(self):
        """Фикстура для модели эмбеддингов."""
        return get_embedding_model()
    
    @pytest.fixture
    def topic_embedding(self, model):
        """Фикстура для topic embedding."""
        keywords_config = {
            "strong": ["dora", "cicd"],
            "weak": ["agile"]
        }
        topic_descriptions = [
            "Статьи про DevOps метрики и CI/CD пайплайны.",
            "Материалы про процессы доставки и стабильность релизов."
        ]
        return build_topic_embedding(keywords_config, model, topic_descriptions)
    
    @pytest.fixture
    def sample_df(self):
        """Фикстура для тестового DataFrame."""
        return pd.DataFrame({
            "title": ["DevOps метрики и CI/CD", "Как приготовить борщ"],
            "summary": ["Статья о DORA метриках", "Рецепт вкусного супа"]
        })
    
    def test_apply_embedding_filter_adds_columns(self, model, topic_embedding, sample_df):
        """Проверяет, что функция добавляет колонки embed_similarity и embed_ok."""
        result = apply_embedding_filter(sample_df, topic_embedding, model)
        
        assert "embed_similarity" in result.columns
        assert "embed_ok" in result.columns
        assert len(result) == len(sample_df)
    
    def test_apply_embedding_filter_empty_df(self, model, topic_embedding):
        """Проверяет обработку пустого DataFrame."""
        empty_df = pd.DataFrame()
        result = apply_embedding_filter(empty_df, topic_embedding, model)
        
        assert result.empty
    
    def test_apply_embedding_filter_missing_columns(self, model, topic_embedding):
        """Проверяет обработку DataFrame без нужных колонок."""
        invalid_df = pd.DataFrame({"wrong_column": ["test"]})
        
        with pytest.raises(ValueError):
            apply_embedding_filter(invalid_df, topic_embedding, model)
    
    def test_apply_embedding_filter_threshold(self, model, topic_embedding, sample_df):
        """Проверяет работу порога фильтрации."""
        result = apply_embedding_filter(
            sample_df, topic_embedding, model, threshold=0.9
        )
        
        # С высоким порогом большинство статей должно быть отклонено
        assert "embed_ok" in result.columns
        assert result["embed_similarity"].min() >= -1.0
        assert result["embed_similarity"].max() <= 1.0


class TestFilterArticlesByEmbedding:
    """Тесты для функции filter_articles_by_embedding."""
    
    @pytest.fixture
    def model(self):
        """Фикстура для модели эмбеддингов."""
        return get_embedding_model()
    
    @pytest.fixture
    def keywords_config(self):
        """Фикстура для конфигурации ключевых слов."""
        return {
            "strong": ["dora", "cicd", "devops"],
            "weak": ["agile", "kanban"]
        }
    
    @pytest.fixture
    def topic_descriptions(self):
        """Фикстура для описаний топиков."""
        return [
            "Статьи про DevOps метрики и CI/CD пайплайны.",
            "Материалы про процессы доставки и стабильность релизов."
        ]
    
    @pytest.fixture
    def sample_df(self):
        """Фикстура для тестового DataFrame."""
        return pd.DataFrame({
            "title": ["DevOps метрики и CI/CD", "Как приготовить борщ"],
            "summary": ["Статья о DORA метриках", "Рецепт вкусного супа"]
        })
    
    def test_filter_articles_by_embedding_returns_tuple(self, model, keywords_config, topic_descriptions, sample_df):
        """Проверяет, что функция возвращает кортеж (DataFrame, stats)."""
        df_result, stats = filter_articles_by_embedding(
            sample_df, keywords_config, model, topic_descriptions=topic_descriptions
        )
        
        assert isinstance(df_result, pd.DataFrame)
        assert isinstance(stats, dict)
    
    def test_filter_articles_by_embedding_stats(self, model, keywords_config, topic_descriptions, sample_df):
        """Проверяет структуру статистики."""
        df_result, stats = filter_articles_by_embedding(
            sample_df, keywords_config, model, topic_descriptions=topic_descriptions
        )
        
        assert "total_articles" in stats
        assert "passed" in stats
        assert "rejected" in stats
        assert "min_similarity" in stats
        assert "mean_similarity" in stats
        assert "max_similarity" in stats
        assert "time_elapsed_sec" in stats
        
        assert stats["total_articles"] == len(sample_df)
        assert stats["passed"] + stats["rejected"] == stats["total_articles"]
    
    def test_filter_articles_by_embedding_empty_df(self, model, keywords_config, topic_descriptions):
        """Проверяет обработку пустого DataFrame."""
        empty_df = pd.DataFrame()
        df_result, stats = filter_articles_by_embedding(
            empty_df, keywords_config, model, topic_descriptions=topic_descriptions
        )
        
        assert df_result.empty
        assert stats["total_articles"] == 0
        assert stats["passed"] == 0
    
    def test_filter_articles_by_embedding_missing_columns(self, model, keywords_config, topic_descriptions):
        """Проверяет обработку DataFrame без нужных колонок."""
        invalid_df = pd.DataFrame({"wrong_column": ["test"]})
        
        with pytest.raises(ValueError):
            filter_articles_by_embedding(invalid_df, keywords_config, model, topic_descriptions=topic_descriptions)

