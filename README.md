# Atlas

## Запуск локально через Docker

### 1. Клонировать репозиторий

```bash
git clone https://github.com/danikd1/Atlas.git
cd Atlas
```

### 2. Создать `.env` файл

```bash
cp .env.example .env
```

Открыть `.env` и заполнить:

```
POSTGRES_PASSWORD= минимум 16 символов
JWT_SECRET= случайная строка 32_символа   # python3 -c "import secrets; print(secrets.token_hex(32))"
GIGACHAT_CREDENTIALS= ключ из личного кабинета sber
ALLOWED_ORIGINS=http://localhost
ALLOWED_EMAILS=***@email.com
```

### 3. Запустить

```bash
docker compose up --build
```

Первый запуск занимает ~10 - скачиваются модели. Последующие запуски быстрее, модели будут захешированны.

### 4. Открыть в браузере

```
http://localhost
```
