FROM python:3.11-slim

WORKDIR /app

# Системные зависимости для trafilatura, lxml и компиляции пакетов
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# CPU-версия torch вместо CUDA — экономим ~4 GB на образе
# Должна устанавливаться ДО остальных пакетов чтобы pip не подтянул CUDA-версию
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# ML-модели кэшируются здесь — пробрасывается как volume в docker-compose.yml
# чтобы не скачивать заново при каждом пересборке образа
ENV HF_HOME=/app/.cache/huggingface
ENV PYTHONUNBUFFERED=1

# Дефолтная команда — API. Воркеры переопределяют через command: в docker-compose.yml
CMD ["uvicorn", "src.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
