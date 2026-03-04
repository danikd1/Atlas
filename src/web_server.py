"""
Веб-сервер для отображения результатов пайплайна и метрик.

Использует FastAPI для API и Server-Sent Events для прогресса в реальном времени.
"""
import asyncio
import json
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, List, Optional

import pandas as pd
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel

from .embedding_filter import filter_articles_by_embedding, get_embedding_model
from .lemmatization_filter import filter_articles_by_keywords
from .taxonomy import get_keywords_config_for_selection, get_topic_descriptions_for_selection, load_taxonomy
from .tools.llm_utils import create_gigachat_client, format_summary_text, summarize_article
from .rss_parser import collect_articles_for_window
from .tools.rate_limiter import RateLimiter
from .tools.text_extraction import add_full_text_column
from config.config import (
    DEFAULT_EMBED_THRESHOLD,
    DEFAULT_HOURS_BACK,
    DEFAULT_LIMIT_PER_FEED,
    DEFAULT_LLM_SLEEP,
    GENERIC_SINGLE_LEMMAS,
    RSS_FEEDS,
    TAXONOMY_SELECTION,
)

logger = logging.getLogger(__name__)

app = FastAPI(title="SberAgency Crawler", version="1.0.0")

# Глобальное состояние для прогресса
_pipeline_progress: Dict = {}
_pipeline_result: Optional[Dict] = None
_progress_queues: Dict[str, asyncio.Queue] = {}  # Словарь очередей для разных сессий
_current_progress: Dict = {}  # Текущий прогресс для polling
_executor = ThreadPoolExecutor(max_workers=2)


def run_pipeline_with_progress(progress_callback: Optional[Callable] = None, hours_back: Optional[int] = None) -> Dict:
    """
    Запускает пайплайн с поддержкой отслеживания прогресса.
    
    Args:
        progress_callback: Функция для отправки обновлений прогресса
        hours_back: Окно времени в часах (по умолчанию DEFAULT_HOURS_BACK)
        
    Returns:
        Словарь с результатами пайплайна
    """
    if hours_back is None:
        hours_back = DEFAULT_HOURS_BACK
    global _pipeline_result
    
    pipeline_start = time.time()
    result = {
        "status": "running",
        "stages": [],
        "digest": [],
        "statistics": {},
        "error": None
    }
    
    def send_progress(stage: str, status: str, message: str = "", data: Optional[Dict] = None):
        """Отправляет обновление прогресса."""
        if progress_callback:
            progress_callback({
                "stage": stage,
                "status": status,  # "started", "completed", "error"
                "message": message,
                "data": data or {},
                "timestamp": datetime.now().isoformat()
            })
    
    try:
        # Этап 1: Сбор статей из RSS-лент
        send_progress("rss_collection", "started", "Сбор статей из RSS-лент...")
        stage1_start = time.time()
        
        df_articles, stats_rss = collect_articles_for_window(
            hours_back,
            limit_per_feed=DEFAULT_LIMIT_PER_FEED,
            rss_feeds=RSS_FEEDS
        )
        
        stage1_time = time.time() - stage1_start
        send_progress("rss_collection", "completed", 
                     f"Собрано {stats_rss['unique_articles']} статей за {stage1_time:.2f} сек",
                     {"time": stage1_time, "articles": stats_rss['unique_articles']})
        result["stages"].append({
            "name": "RSS сбор",
            "time": stage1_time,
            "articles": stats_rss['unique_articles']
        })
        
        # Этап 2: Фильтрация по ключевым словам (ключевые слова из таксономии)
        send_progress("keywords_filter", "started", "Фильтрация по ключевым словам...")
        stage2_start = time.time()
        taxonomy = load_taxonomy()
        keywords_config = get_keywords_config_for_selection(taxonomy, TAXONOMY_SELECTION)
        df_filtered, stats_keywords = filter_articles_by_keywords(
            df_articles,
            keywords_config=keywords_config,
            generic_single_lemmas=GENERIC_SINGLE_LEMMAS
        )
        
        stage2_time = time.time() - stage2_start
        send_progress("keywords_filter", "completed",
                     f"Прошло фильтр: {stats_keywords['passed']} статей",
                     {"time": stage2_time, "passed": stats_keywords['passed']})
        result["stages"].append({
            "name": "Фильтрация по ключевым словам",
            "time": stage2_time,
            "passed": stats_keywords['passed']
        })
        
        # Этап 3: Фильтрация по эмбеддингам (ключевые слова и topic_descriptions из таксономии)
        send_progress("embedding_filter", "started", "Фильтрация по эмбеддингам...")
        stage3_start = time.time()
        topic_descriptions = get_topic_descriptions_for_selection(taxonomy, TAXONOMY_SELECTION)
        embed_model = get_embedding_model()
        df_embedding, stats_embedding = filter_articles_by_embedding(
            df_filtered,
            keywords_config=keywords_config,
            model=embed_model,
            topic_descriptions=topic_descriptions,
            threshold=DEFAULT_EMBED_THRESHOLD
        )
        
        stage3_time = time.time() - stage3_start
        send_progress("embedding_filter", "completed",
                     f"Прошло фильтр: {stats_embedding['passed']} статей",
                     {"time": stage3_time, "passed": stats_embedding['passed']})
        result["stages"].append({
            "name": "Фильтрация по эмбеддингам",
            "time": stage3_time,
            "passed": stats_embedding['passed']
        })
        
        # Сортируем и берем топ-6
        send_progress("top6_selection", "started", "Выбор топ-6 статей...")
        df_embedding_sorted = df_embedding.sort_values("embed_similarity", ascending=False)
        df_top6 = df_embedding_sorted.head(6).copy()
        send_progress("top6_selection", "completed", f"Отобрано {len(df_top6)} статей")
        
        # Этап 4: Извлечение полного текста
        send_progress("text_extraction", "started", "Извлечение полного текста...")
        stage4_start = time.time()
        
        df_with_text = add_full_text_column(df_top6)
        
        stage4_time = time.time() - stage4_start
        successful_texts = sum(1 for t in df_with_text["full_text"] if t is not None)
        send_progress("text_extraction", "completed",
                     f"Извлечено текстов: {successful_texts}/{len(df_with_text)}",
                     {"time": stage4_time, "successful": successful_texts})
        result["stages"].append({
            "name": "Извлечение текста",
            "time": stage4_time,
            "successful": successful_texts
        })
        
        df_relevant = df_with_text
        
        # Этап 5: Суммаризация
        send_progress("summarization", "started", "Суммаризация статей...")
        stage5_start = time.time()
        
        giga_client = create_gigachat_client()
        rate_limiter = RateLimiter(delay_seconds=DEFAULT_LLM_SLEEP)
        
        summaries = []
        total_relevant = len(df_relevant)
        digest_items = []
        
        for idx, (_, row) in enumerate(df_relevant.iterrows(), 1):
            title = row["title"]
            link = row["link"]
            full_text = row.get("full_text")
            similarity = row.get("embed_similarity", 0.0)
            
            send_progress("summarization", "progress",
                         f"Суммаризация [{idx}/{total_relevant}]: {title[:50]}...",
                         {"current": idx, "total": total_relevant})
            
            if full_text is None:
                summary = "Не удалось получить текст статьи для суммаризации."
            else:
                summary = summarize_article(
                    title=title,
                    full_text=full_text,
                    client=giga_client,
                    rate_limiter=rate_limiter
                )
            
            summaries.append(summary)
            
            digest_items.append({
                "title": title,
                "link": link,
                "summary": summary,
                "similarity": float(similarity)
            })
        
        df_relevant["summary"] = summaries
        stage5_time = time.time() - stage5_start
        
        send_progress("summarization", "completed",
                     f"Суммаризировано {len(summaries)} статей",
                     {"time": stage5_time, "count": len(summaries)})
        result["stages"].append({
            "name": "Суммаризация",
            "time": stage5_time,
            "count": len(summaries)
        })
        
        # Сохранение результата
        project_root = Path(__file__).parent.parent
        outputs_dir = project_root / "outputs"
        outputs_dir.mkdir(exist_ok=True)
        output_file = outputs_dir / "articles_filtered.csv"
        df_relevant.to_csv(output_file, index=False, encoding='utf-8')
        
        total_time = time.time() - pipeline_start
        
        result["status"] = "completed"
        result["digest"] = digest_items
        result["statistics"] = {
            "total_time": total_time,
            "total_articles": len(df_articles),
            "final_articles": len(df_relevant),
            "output_file": str(output_file)
        }
        
        send_progress("pipeline", "completed", f"Пайплайн завершен за {total_time:.2f} сек")
        
        _pipeline_result = result
        return result
        
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Ошибка в пайплайне: {e}", exc_info=True)
        send_progress("pipeline", "error", error_msg)
        result["status"] = "error"
        result["error"] = error_msg
        _pipeline_result = result
        return result


@app.get("/", response_class=HTMLResponse)
async def index():
    """Главная страница с UI."""
    html_content = """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SberAgency Crawler - Дайджест статей</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        
        .container {
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            border-radius: 12px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            overflow: hidden;
        }
        
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            text-align: center;
        }
        
        .header h1 {
            font-size: 2.5em;
            margin-bottom: 10px;
        }
        
        .controls {
            padding: 20px;
            background: #f8f9fa;
            border-bottom: 1px solid #dee2e6;
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
        }
        
        button {
            padding: 12px 24px;
            font-size: 16px;
            border: none;
            border-radius: 6px;
            cursor: pointer;
            font-weight: 600;
            transition: all 0.3s;
        }
        
        .btn-primary {
            background: #667eea;
            color: white;
        }
        
        .btn-primary:hover:not(:disabled) {
            background: #5568d3;
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
        }
        
        .btn-secondary {
            background: #6c757d;
            color: white;
        }
        
        .btn-secondary:hover:not(:disabled) {
            background: #5a6268;
        }
        
        button:disabled {
            opacity: 0.6;
            cursor: not-allowed;
        }
        
        .progress-section {
            padding: 20px;
            background: #f8f9fa;
            border-bottom: 1px solid #dee2e6;
        }
        
        .progress-item {
            padding: 12px;
            margin: 8px 0;
            background: white;
            border-radius: 6px;
            border-left: 4px solid #dee2e6;
            transition: all 0.3s;
        }
        
        .progress-item.started {
            border-left-color: #ffc107;
        }
        
        .progress-item.completed {
            border-left-color: #28a745;
        }
        
        .progress-item.error {
            border-left-color: #dc3545;
        }
        
        .progress-item-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 4px;
        }
        
        .progress-item-name {
            font-weight: 600;
            color: #333;
        }
        
        .progress-item-status {
            font-size: 0.9em;
            padding: 4px 8px;
            border-radius: 4px;
            font-weight: 500;
        }
        
        .status-started {
            background: #fff3cd;
            color: #856404;
        }
        
        .status-completed {
            background: #d4edda;
            color: #155724;
        }
        
        .status-error {
            background: #f8d7da;
            color: #721c24;
        }
        
        .progress-item-message {
            color: #666;
            font-size: 0.9em;
        }
        
        .content {
            padding: 30px;
        }
        
        .metrics-section {
            margin-bottom: 40px;
        }
        
        .metrics-section h2 {
            color: #333;
            margin-bottom: 20px;
            font-size: 1.8em;
        }
        
        .metrics-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        
        .metric-card {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.1);
        }
        
        .metric-card h3 {
            font-size: 0.9em;
            opacity: 0.9;
            margin-bottom: 8px;
        }
        
        .metric-card .value {
            font-size: 2em;
            font-weight: bold;
        }
        
        .digest-section h2 {
            color: #333;
            margin-bottom: 20px;
            font-size: 1.8em;
        }
        
        .article-card {
            background: white;
            border: 1px solid #dee2e6;
            border-radius: 8px;
            padding: 20px;
            margin-bottom: 20px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            transition: transform 0.2s, box-shadow 0.2s;
        }
        
        .article-card:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 16px rgba(0,0,0,0.15);
        }
        
        .article-title {
            font-size: 1.3em;
            font-weight: 600;
            color: #667eea;
            margin-bottom: 10px;
        }
        
        .article-title a {
            color: inherit;
            text-decoration: none;
        }
        
        .article-title a:hover {
            text-decoration: underline;
        }
        
        .article-link {
            color: #6c757d;
            font-size: 0.9em;
            margin-bottom: 12px;
            word-break: break-all;
        }
        
        .article-link a {
            color: #667eea;
            text-decoration: none;
        }
        
        .article-similarity {
            display: inline-block;
            background: #e9ecef;
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 0.85em;
            color: #495057;
            margin-bottom: 12px;
        }
        
        .article-summary {
            color: #495057;
            line-height: 1.6;
            white-space: pre-wrap;
        }
        
        .empty-state {
            text-align: center;
            padding: 60px 20px;
            color: #6c757d;
        }
        
        .empty-state-icon {
            font-size: 4em;
            margin-bottom: 20px;
        }
        
        .loading {
            display: inline-block;
            width: 20px;
            height: 20px;
            border: 3px solid rgba(255,255,255,.3);
            border-radius: 50%;
            border-top-color: white;
            animation: spin 1s ease-in-out infinite;
        }
        
        @keyframes spin {
            to { transform: rotate(360deg); }
        }
        
        .stats-table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 20px;
        }
        
        .stats-table th,
        .stats-table td {
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #dee2e6;
        }
        
        .stats-table th {
            background: #f8f9fa;
            font-weight: 600;
            color: #495057;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🚀 SberAgency Crawler</h1>
            <p>Дайджест статей с Habr</p>
        </div>
        
        <div class="controls">
            <div style="display: flex; align-items: center; gap: 15px; flex-wrap: wrap;">
                <button class="btn-primary" id="btnRun" onclick="runPipeline()">
                    ▶ Запустить пайплайн
                </button>
                <button class="btn-secondary" id="btnEvaluate" onclick="showMetricsPage()">
                    📊 Оценить метрики
                </button>
                <button class="btn-secondary" onclick="loadLastResult()">
                    📋 Загрузить последний результат
                </button>
                <div style="display: flex; align-items: center; gap: 10px; background: white; padding: 10px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                    <label for="hoursBack" style="font-weight: 600; color: #495057; white-space: nowrap;">
                        ⏰ Период сбора:
                    </label>
                    <div style="display: flex; gap: 5px; align-items: center;">
                        <button 
                            type="button" 
                            class="time-preset-btn" 
                            onclick="setHoursBack(6)"
                            title="Последние 6 часов"
                        >
                            6ч
                        </button>
                        <button 
                            type="button" 
                            class="time-preset-btn active" 
                            onclick="setHoursBack(24)"
                            title="Последние 24 часа"
                        >
                            24ч
                        </button>
                        <button 
                            type="button" 
                            class="time-preset-btn" 
                            onclick="setHoursBack(48)"
                            title="Последние 48 часов"
                        >
                            48ч
                        </button>
                        <button 
                            type="button" 
                            class="time-preset-btn" 
                            onclick="setHoursBack(72)"
                            title="Последние 72 часа"
                        >
                            72ч
                        </button>
                        <input 
                            type="number" 
                            id="hoursBack" 
                            value="24" 
                            min="1" 
                            max="168" 
                            onchange="updateTimePresetButtons()"
                            style="padding: 8px 12px; border: 2px solid #dee2e6; border-radius: 6px; font-size: 16px; width: 80px; text-align: center;"
                            placeholder="часы"
                        />
                        <span style="color: #6c757d; font-size: 0.9em;">часов назад</span>
                    </div>
                </div>
            </div>
        </div>
        
        <style>
            .time-preset-btn {
                padding: 6px 12px;
                border: 2px solid #dee2e6;
                border-radius: 6px;
                background: white;
                color: #495057;
                font-size: 14px;
                font-weight: 600;
                cursor: pointer;
                transition: all 0.2s;
            }
            
            .time-preset-btn:hover {
                border-color: #667eea;
                background: #f0f4ff;
                color: #667eea;
            }
            
            .time-preset-btn.active {
                background: #667eea;
                color: white;
                border-color: #667eea;
            }
        </style>
        
        <div class="progress-section" id="progressSection" style="display: none;">
            <h3 style="margin-bottom: 15px;">Прогресс выполнения:</h3>
            <div id="progressList"></div>
        </div>
        
        <div class="content">
            <div class="metrics-section" id="metricsSection" style="display: none;">
                <h2>📊 Метрики пайплайна</h2>
                <div class="metrics-grid" id="metricsGrid"></div>
                <table class="stats-table" id="statsTable"></table>
            </div>
            
            <div class="digest-section" id="digestSection" style="display: none;">
                <h2>📋 Дайджест статей</h2>
                <div id="digestList"></div>
            </div>
            
            <div class="empty-state" id="emptyState">
                <div class="empty-state-icon">📰</div>
                <h3>Пайплайн еще не запущен</h3>
                <p>Нажмите "Запустить пайплайн" для начала работы</p>
            </div>
        </div>
    </div>
    
    <script>
        function setHoursBack(hours) {
            document.getElementById('hoursBack').value = hours;
            updateTimePresetButtons();
        }
        
        function updateTimePresetButtons() {
            const hours = parseInt(document.getElementById('hoursBack').value) || 24;
            const buttons = document.querySelectorAll('.time-preset-btn');
            buttons.forEach(btn => {
                const btnText = btn.textContent.trim();
                const btnHours = parseInt(btnText.replace('ч', ''));
                if (btnHours === hours) {
                    btn.classList.add('active');
                } else {
                    btn.classList.remove('active');
                }
            });
        }
        
        function runPipeline() {
            const btnRun = document.getElementById('btnRun');
            const btnEvaluate = document.getElementById('btnEvaluate');
            const progressSection = document.getElementById('progressSection');
            const progressList = document.getElementById('progressList');
            const emptyState = document.getElementById('emptyState');
            
            btnRun.disabled = true;
            btnEvaluate.disabled = true;
            progressSection.style.display = 'block';
            progressList.innerHTML = '';
            emptyState.style.display = 'none';
            
            // Очищаем предыдущие результаты
            document.getElementById('metricsSection').style.display = 'none';
            document.getElementById('digestSection').style.display = 'none';
            
            // Получаем значение часов назад из поля ввода
            const hoursBackInput = document.getElementById('hoursBack');
            const hoursBack = parseInt(hoursBackInput.value) || 24;
            
            // Валидация
            if (hoursBack < 1 || hoursBack > 168) {
                alert('Окно времени должно быть от 1 до 168 часов (7 дней)');
                btnRun.disabled = false;
                btnEvaluate.disabled = false;
                return;
            }
            
            // Запускаем пайплайн через POST и затем опрашиваем прогресс
            fetch('/api/pipeline/start', { 
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ hours_back: hoursBack })
            })
                .then(response => response.json())
                .then(data => {
                    if (data.status === 'started') {
                        // Начинаем опрос прогресса
                        pollProgress();
                    } else {
                        alert('Ошибка запуска пайплайна: ' + (data.error || 'Неизвестная ошибка'));
                        btnRun.disabled = false;
                        btnEvaluate.disabled = false;
                    }
                })
                .catch(error => {
                    console.error('Error starting pipeline:', error);
                    alert('Ошибка запуска пайплайна');
                    btnRun.disabled = false;
                    btnEvaluate.disabled = false;
                });
        }
        
        function pollProgress() {
            fetch('/api/pipeline/progress')
                .then(response => response.json())
                .then(data => {
                    if (data.progress) {
                        // Обновляем прогресс для каждого этапа
                        Object.keys(data.progress).forEach(stage => {
                            updateProgress(data.progress[stage]);
                        });
                        
                        // Проверяем, завершен ли пайплайн
                        const pipelineProgress = data.progress['pipeline'];
                        if (pipelineProgress && pipelineProgress.status === 'completed') {
                            loadLastResult();
                            document.getElementById('btnRun').disabled = false;
                            document.getElementById('btnEvaluate').disabled = false;
                            return; // Прекращаем опрос
                        } else if (pipelineProgress && pipelineProgress.status === 'error') {
                            document.getElementById('btnRun').disabled = false;
                            document.getElementById('btnEvaluate').disabled = false;
                            return; // Прекращаем опрос
                        }
                    }
                    
                    // Продолжаем опрос каждые 500мс
                    setTimeout(pollProgress, 500);
                })
                .catch(error => {
                    console.error('Error polling progress:', error);
                    setTimeout(pollProgress, 1000); // Повторяем через 1 сек при ошибке
                });
        }
        
        function updateProgress(data) {
            const progressList = document.getElementById('progressList');
            const itemId = `progress-${data.stage}`;
            let item = document.getElementById(itemId);
            
            if (!item) {
                item = document.createElement('div');
                item.id = itemId;
                item.className = 'progress-item';
                progressList.appendChild(item);
            }
            
            item.className = `progress-item ${data.status}`;
            item.innerHTML = `
                <div class="progress-item-header">
                    <span class="progress-item-name">${getStageName(data.stage)}</span>
                    <span class="progress-item-status status-${data.status}">
                        ${getStatusText(data.status)}
                    </span>
                </div>
                <div class="progress-item-message">${data.message || ''}</div>
            `;
        }
        
        function getStageName(stage) {
            const names = {
                'rss_collection': '📥 Сбор статей из RSS',
                'keywords_filter': '🔍 Фильтрация по ключевым словам',
                'embedding_filter': '🎯 Фильтрация по эмбеддингам',
                'top6_selection': '📊 Выбор топ-6 статей',
                'text_extraction': '📄 Извлечение полного текста',
                'summarization': '📝 Суммаризация статей',
                'pipeline': '🚀 Пайплайн'
            };
            return names[stage] || stage;
        }
        
        function getStatusText(status) {
            const texts = {
                'started': '⏳ Выполняется',
                'completed': '✅ Завершено',
                'progress': '🔄 В процессе',
                'error': '❌ Ошибка'
            };
            return texts[status] || status;
        }
        
        async function loadLastResult() {
            try {
                const response = await fetch('/api/pipeline/result');
                const data = await response.json();
                
                if (data.status === 'completed') {
                    displayResults(data);
                }
            } catch (error) {
                console.error('Error loading result:', error);
            }
        }
        
        function displayResults(data) {
            // Показываем метрики
            const metricsSection = document.getElementById('metricsSection');
            const metricsGrid = document.getElementById('metricsGrid');
            const statsTable = document.getElementById('statsTable');
            
            metricsSection.style.display = 'block';
            
            // Метрики в карточках
            metricsGrid.innerHTML = `
                <div class="metric-card">
                    <h3>Всего статей собрано</h3>
                    <div class="value">${data.statistics.total_articles || 0}</div>
                </div>
                <div class="metric-card">
                    <h3>Финальных статей</h3>
                    <div class="value">${data.statistics.final_articles || 0}</div>
                </div>
                <div class="metric-card">
                    <h3>Время выполнения</h3>
                    <div class="value">${(data.statistics.total_time || 0).toFixed(1)}с</div>
                </div>
            `;
            
            // Таблица этапов
            let tableHTML = '<thead><tr><th>Этап</th><th>Время</th><th>Результат</th></tr></thead><tbody>';
            data.stages.forEach(stage => {
                tableHTML += `<tr>
                    <td>${stage.name}</td>
                    <td>${stage.time.toFixed(2)}с</td>
                    <td>${formatStageResult(stage)}</td>
                </tr>`;
            });
            tableHTML += '</tbody>';
            statsTable.innerHTML = tableHTML;
            
            // Показываем дайджест
            const digestSection = document.getElementById('digestSection');
            const digestList = document.getElementById('digestList');
            const emptyState = document.getElementById('emptyState');
            
            if (data.digest && data.digest.length > 0) {
                digestSection.style.display = 'block';
                emptyState.style.display = 'none';
                
                digestList.innerHTML = data.digest.map((article, idx) => `
                    <div class="article-card">
                        <div class="article-title">
                            <a href="${article.link}" target="_blank">${article.title}</a>
                        </div>
                        <div class="article-link">
                            <a href="${article.link}" target="_blank">${article.link}</a>
                        </div>
                        <div class="article-similarity">
                            📊 Сходство: ${article.similarity.toFixed(3)}
                        </div>
                        <div class="article-summary">${formatSummary(article.summary)}</div>
                    </div>
                `).join('');
            } else {
                digestSection.style.display = 'none';
            }
        }
        
        function formatStageResult(stage) {
            if (stage.articles) return `${stage.articles} статей`;
            if (stage.passed) return `${stage.passed} прошло`;
            if (stage.successful !== undefined) return `${stage.successful} успешно`;
            if (stage.count) return `${stage.count} суммаризировано`;
            return '-';
        }
        
        function formatSummary(summary) {
            if (!summary) return '';
            // Экранируем HTML и форматируем переносы строк
            return summary
                .replace(/&/g, '&amp;')
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;')
                .split('\\n')
                .map(p => p.trim())
                .filter(p => p)
                .join('<br>');
        }
        
        function showMetricsPage() {
            // Открываем страницу метрик в новой вкладке
            window.open('/metrics', '_blank');
        }
    </script>
</body>
</html>
    """
    return HTMLResponse(content=html_content)


class PipelineStartRequest(BaseModel):
    hours_back: int = DEFAULT_HOURS_BACK


@app.post("/api/pipeline/start")
async def start_pipeline(request: PipelineStartRequest):
    """Запускает пайплайн в фоновом режиме."""
    global _current_progress
    
    # Получаем параметры из тела запроса
    hours_back = request.hours_back
    
    # Валидация
    if hours_back < 1 or hours_back > 168:
        return JSONResponse(
            {"status": "error", "message": "Окно времени должно быть от 1 до 168 часов (7 дней)"},
            status_code=400
        )
    
    # Сбрасываем прогресс
    _current_progress = {}
    
    def send_progress(data: Dict):
        """Обновляет глобальный прогресс."""
        _current_progress[data["stage"]] = data
    
    # Запускаем пайплайн в отдельном потоке
    def run_pipeline_thread():
        try:
            run_pipeline_with_progress(send_progress, hours_back=hours_back)
        except Exception as e:
            logger.error(f"Ошибка в пайплайне: {e}", exc_info=True)
            _current_progress["pipeline"] = {
                "stage": "pipeline",
                "status": "error",
                "message": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    thread = threading.Thread(target=run_pipeline_thread)
    thread.daemon = True
    thread.start()
    
    return JSONResponse({"status": "started", "message": f"Пайплайн запущен (окно: {hours_back} ч)"})


@app.get("/api/pipeline/progress")
async def get_pipeline_progress():
    """Возвращает текущий прогресс выполнения пайплайна."""
    return JSONResponse({"progress": _current_progress})


@app.get("/api/pipeline/result")
async def get_pipeline_result():
    """Возвращает последний результат выполнения пайплайна."""
    global _pipeline_result
    
    if _pipeline_result is None:
        return JSONResponse({"status": "no_result", "message": "Пайплайн еще не запускался"})
    
    return JSONResponse(_pipeline_result)


@app.get("/metrics", response_class=HTMLResponse)
async def metrics_page():
    """Страница с метриками всех этапов."""
    html_content = """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Метрики пайплайна - SberAgency Crawler</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        
        .container {
            max-width: 1400px;
            margin: 0 auto;
            background: white;
            border-radius: 12px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            overflow: hidden;
        }
        
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            text-align: center;
        }
        
        .header h1 {
            font-size: 2.5em;
            margin-bottom: 10px;
        }
        
        .controls {
            padding: 20px;
            background: #f8f9fa;
            border-bottom: 1px solid #dee2e6;
            text-align: center;
        }
        
        button {
            padding: 12px 24px;
            font-size: 16px;
            border: none;
            border-radius: 6px;
            cursor: pointer;
            font-weight: 600;
            transition: all 0.3s;
            background: #667eea;
            color: white;
        }
        
        button:hover:not(:disabled) {
            background: #5568d3;
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
        }
        
        button:disabled {
            opacity: 0.6;
            cursor: not-allowed;
        }
        
        .content {
            padding: 30px;
        }
        
        .loading {
            text-align: center;
            padding: 40px;
            color: #6c757d;
        }
        
        .stage-block {
            background: white;
            border: 1px solid #dee2e6;
            border-radius: 8px;
            padding: 30px;
            margin-bottom: 30px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }
        
        .stage-title {
            font-size: 1.8em;
            color: #667eea;
            margin-bottom: 25px;
            padding-bottom: 15px;
            border-bottom: 3px solid #667eea;
        }
        
        .metric-section {
            margin-bottom: 30px;
        }
        
        .metric-section h3 {
            font-size: 1.3em;
            color: #333;
            margin-bottom: 15px;
        }
        
        .metric-section h4 {
            font-size: 1.1em;
            color: #495057;
            margin-top: 20px;
            margin-bottom: 10px;
        }
        
        .metric-question {
            background: #f8f9fa;
            border-left: 4px solid #667eea;
            padding: 15px;
            margin: 15px 0;
            border-radius: 4px;
            font-style: italic;
            color: #495057;
        }
        
        .metric-explanation {
            line-height: 1.8;
            color: #495057;
            margin: 15px 0;
        }
        
        .metric-formula {
            background: #e9ecef;
            padding: 15px;
            border-radius: 6px;
            margin: 15px 0;
            font-family: 'Courier New', monospace;
            font-size: 1.1em;
            font-weight: 600;
            color: #667eea;
        }
        
        .metric-visual {
            background: #fff3cd;
            border-left: 4px solid #ffc107;
            padding: 15px;
            margin: 15px 0;
            border-radius: 4px;
        }
        
        .metric-value-highlight {
            font-weight: 700;
            font-size: 1.2em;
            color: #667eea;
        }
        
        .metric-value-good {
            color: #28a745;
            font-weight: 700;
        }
        
        .metric-value-medium {
            color: #ffc107;
            font-weight: 700;
        }
        
        .metric-value-bad {
            color: #dc3545;
            font-weight: 700;
        }
        
        .loading-spinner {
            display: inline-block;
            width: 40px;
            height: 40px;
            border: 4px solid rgba(102, 126, 234, 0.3);
            border-radius: 50%;
            border-top-color: #667eea;
            animation: spin 1s ease-in-out infinite;
            margin: 20px auto;
        }
        
        @keyframes spin {
            to { transform: rotate(360deg); }
        }
        
        .error-message {
            background: #f8d7da;
            color: #721c24;
            padding: 15px;
            border-radius: 6px;
            margin: 20px 0;
        }
        
        .metrics-table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 20px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }
        
        .metrics-table th,
        .metrics-table td {
            padding: 15px;
            text-align: left;
            border-bottom: 1px solid #dee2e6;
        }
        
        .metrics-table th {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            font-weight: 600;
            position: sticky;
            top: 0;
        }
        
        .metrics-table tr:hover {
            background: #f8f9fa;
        }
        
        .metrics-table td {
            background: white;
        }
        
        .metric-value {
            font-weight: 600;
            font-size: 1.1em;
        }
        
        .metric-good {
            color: #28a745;
        }
        
        .metric-medium {
            color: #ffc107;
        }
        
        .metric-bad {
            color: #dc3545;
        }
        
        .show-details-btn {
            padding: 6px 12px;
            font-size: 14px;
            border: 2px solid #667eea;
            border-radius: 6px;
            background: white;
            color: #667eea;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s;
        }
        
        .show-details-btn:hover {
            background: #667eea;
            color: white;
        }
        
        .visual-details {
            display: none;
            margin-top: 20px;
            padding: 20px;
            background: #f8f9fa;
            border-radius: 8px;
        }
        
        .visual-details.show {
            display: block;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📊 Метрики пайплайна</h1>
            <p>Оценка качества фильтрации на размеченном датасете</p>
        </div>
        
        <div class="controls">
            <button id="btnEvaluate" onclick="evaluateMetrics()">
                🔄 Запустить оценку метрик
            </button>
        </div>
        
        <div class="content">
            <div id="loadingSection" class="loading" style="display: none;">
                <div class="loading-spinner"></div>
                <p>Вычисление метрик...</p>
            </div>
            
            <div id="errorSection" style="display: none;"></div>
            
            <div id="metricsSection" style="display: none;">
                <table class="metrics-table">
                    <thead>
                        <tr>
                            <th>Этап</th>
                            <th>TP</th>
                            <th>FP</th>
                            <th>TN</th>
                            <th>FN</th>
                            <th>Precision</th>
                            <th>Recall</th>
                            <th>FPR</th>
                            <th>Статей</th>
                            <th>Действия</th>
                        </tr>
                    </thead>
                    <tbody id="metricsBody">
                    </tbody>
                </table>
                <div id="metricsStages">
                    <!-- Блоки "Наглядно" для каждого этапа будут добавлены здесь -->
                </div>
            </div>
        </div>
    </div>
    
    <script>
        async function evaluateMetrics() {
            const btnEvaluate = document.getElementById('btnEvaluate');
            const loadingSection = document.getElementById('loadingSection');
            const metricsSection = document.getElementById('metricsSection');
            const errorSection = document.getElementById('errorSection');
            
            btnEvaluate.disabled = true;
            loadingSection.style.display = 'block';
            metricsSection.style.display = 'none';
            errorSection.style.display = 'none';
            
            try {
                const response = await fetch('/api/metrics/evaluate', { method: 'POST' });
                const data = await response.json();
                
                if (data.error) {
                    throw new Error(data.error);
                }
                
                // Отображаем метрики
                displayMetrics(data);
                loadingSection.style.display = 'none';
                metricsSection.style.display = 'block';
            } catch (error) {
                console.error('Error evaluating metrics:', error);
                errorSection.innerHTML = `
                    <div class="error-message">
                        <strong>Ошибка при оценке метрик:</strong><br>
                        ${error.message}
                    </div>
                `;
                errorSection.style.display = 'block';
                loadingSection.style.display = 'none';
            } finally {
                btnEvaluate.disabled = false;
            }
        }
        
        function displayMetrics(data) {
            const metricsBody = document.getElementById('metricsBody');
            const metricsStages = document.getElementById('metricsStages');
            const stages = [
                { key: 'baseline', num: 0, name: 'Базовый (все статьи)' },
                { key: 'keywords', num: 1, name: 'Фильтрация по ключевым словам' },
                { key: 'embedding', num: 2, name: 'Фильтрация по эмбеддингам (на всем датасете)' },
                { key: 'combined', num: 3, name: 'Комбинированный (boolean + embedding)' }
            ];
            
            // Создаем таблицу
            let tableHTML = '';
            let detailsHTML = '';
            
            stages.forEach(stage => {
                const metrics = data[stage.key];
                if (!metrics) return;
                
                const precision = metrics.precision || 0;
                const recall = metrics.recall || 0;
                const fpr = metrics.fpr || 0;
                
                const stageId = `stage-${stage.num}`;
                
                // Строка таблицы
                tableHTML += `
                    <tr>
                        <td><strong>${stage.num}. ${stage.name}</strong></td>
                        <td>${metrics.TP || 0}</td>
                        <td>${metrics.FP || 0}</td>
                        <td>${metrics.TN || 0}</td>
                        <td>${metrics.FN || 0}</td>
                        <td class="metric-value ${getMetricClass(precision)}">${precision.toFixed(4)}</td>
                        <td class="metric-value ${getMetricClass(recall)}">${recall.toFixed(4)}</td>
                        <td class="metric-value ${getMetricClass(1 - fpr)}">${fpr.toFixed(4)}</td>
                        <td>${metrics.predicted_positive || metrics.total || 0}</td>
                        <td>
                            <button class="show-details-btn" onclick="toggleDetails('${stageId}')">
                                📊 Показать "Наглядно"
                            </button>
                        </td>
                    </tr>
                `;
                
                // Блок "Наглядно" (скрыт по умолчанию)
                detailsHTML += renderVisualDetails(stageId, stage.num, stage.name, metrics);
            });
            
            metricsBody.innerHTML = tableHTML;
            metricsStages.innerHTML = detailsHTML;
        }
        
        function toggleDetails(stageId) {
            const detailsBlock = document.getElementById(stageId);
            const button = event.target;
            
            if (detailsBlock.classList.contains('show')) {
                detailsBlock.classList.remove('show');
                button.textContent = '📊 Показать "Наглядно"';
            } else {
                detailsBlock.classList.add('show');
                button.textContent = '❌ Скрыть "Наглядно"';
            }
        }
        
        function renderVisualDetails(stageId, stageNum, stageName, metrics) {
            const TP = metrics.TP || 0;
            const FP = metrics.FP || 0;
            const TN = metrics.TN || 0;
            const FN = metrics.FN || 0;
            const TP_PLUS_FP = TP + FP;
            const TP_PLUS_FN = TP + FN;
            const FP_PLUS_TN = FP + TN;
            
            const precision = metrics.precision || 0;
            const recall = metrics.recall || 0;
            const fpr = metrics.fpr || 0;
            
            const PRECISION_PCT_INT = Math.round(precision * 100);
            const RECALL_PCT_INT = Math.round(recall * 100);
            const FPR_PCT_INT = Math.round(fpr * 100);
            
            const precisionClass = getMetricClass(precision);
            const recallClass = getMetricClass(recall);
            const fprClass = getMetricClass(1 - fpr); // Инвертируем для FPR (меньше = лучше)
            
            return `
                <div id="${stageId}" class="visual-details">
                    <div class="stage-block">
                        <div class="stage-title">Этап ${stageNum}: ${stageName}</div>
                        
                        <div class="metric-section">
                            <h3>Precision (точность) — "насколько чистый итоговый список"</h3>
                            <h4>Наглядно</h4>
                            <div class="metric-visual">
                                Представь, что ты показываешь людям дайджест из ${TP_PLUS_FP} статей.<br><br>
                                <strong>Примерно <span class="metric-value-${precisionClass}">${PRECISION_PCT_INT}%</span> статей будут реально полезными</strong>, 
                                а <strong><span class="metric-value-${precisionClass}">${100 - PRECISION_PCT_INT}%</span> — мусор</strong>.
                            </div>
                        </div>
                        
                        <div class="metric-section">
                            <h3>Recall (полнота) — "сколько полезного ты не потерял"</h3>
                            <h4>Наглядно</h4>
                            <div class="metric-visual">
                                Ты находишь <strong>~<span class="metric-value-${recallClass}">${RECALL_PCT_INT}%</span> всего полезного</strong>, 
                                но <strong>~<span class="metric-value-${recallClass}">${100 - RECALL_PCT_INT}%</span> полезных статей</strong> отсекаются вместе с мусором.
                            </div>
                        </div>
                        
                        <div class="metric-section">
                            <h3>FPR (False Positive Rate) — "какая доля мусора пролезла"</h3>
                            <h4>Наглядно</h4>
                            <div class="metric-visual">
                                Из ${FP_PLUS_TN} нерелевантных статей система пропустила только ${FP} —<br><br>
                                то есть "уровень протечки мусора" около <strong><span class="metric-value-${fprClass}">${FPR_PCT_INT}%</span></strong>.
                            </div>
                        </div>
                        
                        <div class="confusion-matrix">
                            <h4>Матрица ошибок (Confusion Matrix)</h4>
                            <table class="confusion-table">
                                <thead>
                                    <tr>
                                        <th></th>
                                        <th>Предсказано: Релевантно</th>
                                        <th>Предсказано: Нерелевантно</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    <tr>
                                        <th>Реально: Релевантно</th>
                                        <td class="tp">TP = ${TP}<br><small>True Positive</small></td>
                                        <td class="fn">FN = ${FN}<br><small>False Negative</small></td>
                                    </tr>
                                    <tr>
                                        <th>Реально: Нерелевантно</th>
                                        <td class="fp">FP = ${FP}<br><small>False Positive</small></td>
                                        <td class="tn">TN = ${TN}<br><small>True Negative</small></td>
                                    </tr>
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>
            `;
        }
        
        function getMetricClass(value) {
            if (value >= 0.8) return 'metric-good';
            if (value >= 0.5) return 'metric-medium';
            return 'metric-bad';
        }
    </script>
</body>
</html>
    """
    return HTMLResponse(content=html_content)


@app.post("/api/metrics/evaluate")
async def evaluate_metrics_endpoint():
    """Запускает оценку метрик на размеченном датасете."""
    try:
        from evaluate_metrics import evaluate_pipeline
        metrics = evaluate_pipeline()
        return JSONResponse(metrics)
    except Exception as e:
        logger.error(f"Ошибка при оценке метрик: {e}", exc_info=True)
        return JSONResponse({"error": str(e)}, status_code=500)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

