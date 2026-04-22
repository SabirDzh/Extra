# Extra Backend

## About
`extra_backend` — backend-сервис на FastAPI с асинхронным стеком (SQLAlchemy + PostgreSQL), системой миграций Alembic, кэшированием в Redis и набором API/интеграционных тестов.

Основные технологии:
- FastAPI
- SQLAlchemy 2.x (async)
- PostgreSQL
- Alembic
- Redis
- Poetry
- Pytest

Дополнительно:
- FastAPI Users: [GitHub](https://github.com/fastapi-users/fastapi-users), [Docs](https://fastapi-users.github.io/fastapi-users/latest/)
- Базовый шаблон: [FastAPI Base app](https://github.com/mahenzon/FastAPI-base-app)
- Miro: [ссылка](https://miro.com/welcomeonboard/a1NwdEkvV3N5eWlOSXlCT1MyV1hSamlsbUQ0UjlEVm5ia2ZkQkRtNy9xM1Vqcng0WmZ3RWUyY1NTcndrVTFvNzQ2THFzTDZkVUdlNDg1dXFJRGZ6TkxaTk9XdnkxNHViaDJqUGpXc3RqdDZaay9wZWtmTGN3bEpvSDBxMVJmb0ZNakdSWkpBejJWRjJhRnhhb1UwcS9BPT0hdjE=?share_link_id=942239675421)

## Table of Contents
- [About](#about)
- [Project Structure](#project-structure)
- [Requirements](#requirements)
- [Environment Variables](#environment-variables)
- [Run Project (Step-by-Step)](#run-project-step-by-step)
- [Migrations](#migrations)
- [Testing](#testing)
- [API Docs](#api-docs)
- [CI/CD (GitHub Actions)](#cicd-github-actions)
- [Useful Commands](#useful-commands)

## Project Structure
Ключевые директории:
- `backend/api` — роуты и зависимости API
- `backend/core` — конфиг, модели, схемы, auth
- `backend/crud` — бизнес-логика
- `backend/alembic` — миграции
- `backend/tests` — тесты

## Requirements
- Python 3.12+
- Poetry 2+
- Docker + Docker Compose (для локального PostgreSQL/Redis/Maildev)

## Environment Variables
Приложение читает переменные из:
- `backend/.env.template`
- `backend/.env` (приоритетнее, если существует)

### Быстрый старт `.env`

Из корня проекта:

```bash
cp backend/.env.template backend/.env
```

Для запуска с локальным `docker-compose.yml` приведи `backend/.env` к рабочим значениям:

```env
APP_CONFIG__DB__URL=postgresql+asyncpg://user:password@localhost:5432/shop
APP_CONFIG__DB__ECHO=1
APP_CONFIG__GUNICORN__WORKERS=1
APP_CONFIG__ACCESS_TOKEN__RESET_PASSWORD_TOKEN_SECRET=change_me_reset_secret
APP_CONFIG__ACCESS_TOKEN__VERIFICATION_TOKEN_SECRET=change_me_verification_secret
```

## Run Project (Step-by-Step)

### 1. Установить зависимости Python

Из корня проекта:

```bash
poetry install --no-interaction --no-ansi --no-root
```

### 2. Поднять инфраструктуру (PostgreSQL, Redis, Maildev)

```bash
docker compose up -d
```

Порты:
- Postgres: `5432`
- Redis: `6379`
- Maildev UI: `1080`
- Maildev SMTP: `1025`

### 3. Применить миграции

```bash
cd backend
poetry run alembic upgrade head

# or 

alembic upgrade head
```

### 4. Запустить приложение

Вариант A (через gunicorn, ближе к production):

```bash
cd backend
poetry run python run_main.py

# or 

python run_main.py
```

Вариант B (dev-режим uvicorn):

```bash
cd backend
poetry run python main.py

# or 

python main.py 
```

### 5. Проверить, что API работает

```bash
curl http://localhost:8000/docs 
```

## Migrations

Все команды выполнять из директории `backend/`.

### Применить миграции

```bash
poetry run alembic upgrade head

# or 

alembic upgrade head 
```

### Создать новую миграцию

```bash
poetry run alembic revision --autogenerate -m "your message"
poetry run alembic upgrade head 

# or 

alembic revision --autogenerate -m "your message"
alembic upgrade head 
```

## Testing

Запуск всех тестов (из корня проекта):

```bash
PYTHONPATH=backend poetry run pytest backend/tests

# or 

python -m pytest 
```

Запуск конкретной папки тестов:

```bash
PYTHONPATH=backend poetry run pytest backend/tests/views -q
```

## API Docs
После запуска проекта Swagger доступен по адресу:

- [http://localhost:8000/docs](http://localhost:8000/docs)
- [http://localhost:8000/redoc](http://localhost:8000/redoc)

## CI/CD (GitHub Actions)

В репозитории добавлены workflow-файлы:

- `.github/workflows/ci.yml`
  - запускается на `push` и `pull_request`
  - ставит Python 3.12 и Poetry
  - устанавливает зависимости
  - запускает тесты: `PYTHONPATH=backend poetry run pytest backend/tests`

- `.github/workflows/cd.yml`
  - запускается на `push` в `main`, на теги `v*` и вручную (`workflow_dispatch`)
  - собирает Docker-образ из `backend/Dockerfile`
  - публикует образ в GHCR: `ghcr.io/<owner>/<repo>`

### Optional auto-deploy

`cd.yml` содержит необязательный `deploy` job, который выполняется только если заданы GitHub Secrets:
- `DEPLOY_HOST`
- `DEPLOY_USER`
- `DEPLOY_SSH_KEY`
- `DEPLOY_SCRIPT`
- `DEPLOY_PORT` (опционально, по умолчанию `22`)

В `DEPLOY_SCRIPT` передается переменная `IMAGE`:

```text
ghcr.io/<owner>/<repo>:main
```

## Useful Commands

Запустить только инфраструктуру:

```bash
docker compose up -d pg redis maildev
```

Остановить инфраструктуру:

```bash
docker compose down
```

Пересобрать Docker-образ приложения:

```bash
docker build -f backend/Dockerfile -t extra_backend:test .
```
