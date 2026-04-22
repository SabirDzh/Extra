# FastAPI App

## 📑 Содержимое

- [FastAPI-Users](#fastapi-users)
- [FastAPI Base app](#fastapi-base-app)
- [Miro](#miro)
- [Run with usage of env params](#run-with-usage-of-env-params)
- [Cron](#cron)
- [Docs](#docs)
- [Migrations](#migrations)
- [Create migration](#create-migration)
- [🧪 Тестирование](#-тестирование)
- [Git](#git)

---

FastAPI-Users:

- GitHub https://github.com/fastapi-users/fastapi-users
- Docs https://fastapi-users.github.io/fastapi-users/latest/

FastAPI Base app:

- https://github.com/mahenzon/FastAPI-base-app

# Miro
- [ссылка](https://miro.com/welcomeonboard/a1NwdEkvV3N5eWlOSXlCT1MyV1hSamlsbUQ0UjlEVm5ia2ZkQkRtNy9xM1Vqcng0WmZ3RWUyY1NTcndrVTFvNzQ2THFzTDZkVUdlNDg1dXFJRGZ6TkxaTk9XdnkxNHViaDJqUGpXc3RqdDZaay9wZWtmTGN3bEpvSDBxMVJmb0ZNakdSWkpBejJWRjJhRnhhb1UwcS9BPT0hdjE=?share_link_id=942239675421)

## Run with usage of env params:

```shell
./run

# or

python run_main.py
```

or

```shell
  gunicorn main:main_app --workers 4 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
  ```

```shell
http OPTIONS http://localhost:8000/api/v1/auth/login 'Access-Control-Request-Method:GET' 'Origin: http://localhost:8000'
```

## Cron 

Запуск cron для очистки таблицы access_tokens от устаревших токенов 
```psql 
crontab -e

*/5 * * * * psql "postgresql://user:password@localhost:5432/shop" \
-c "DELETE FROM access_tokens WHERE created_at < now() - interval '36600 seconds';"
```

## Docs
После запуска проекта можно перейти к swagger-документации

```bash
http://localhost:8000/docs
```

## Migrations 
Запуск докера и миграций для базы данных

```bash
cd extra_backend/

source .venv/bin/activate 
# or
. .venv/bin/acitvate

docker-compose up -d

cd backend/

alembic upgrade head 
```

## Create migration
```bash 
cd backend/

alembic revision --autogenerate -m "your message"

alembic upgrade head
```

---

## 🧪 Тестирование

Проект содержит набор автоматических тестов в папке `tests/`.

### 📦 Используемые инструменты
- pytest
- pytest-asyncio (для асинхронных тестов)
- httpx (для тестирования API)

---

### 🚀 Запуск тестов

Из корня проекта (`backend/`):

```bash
pytest
# or 
python -m pytest
```

## Git 
```bash 
git remote add origin <repo url>

git branch <your branch name>

git checkout <your branch name>

git pull origin zr_dev 

git push -u origin <your branch name>
```

## CI/CD (GitHub Actions)

В репозитории добавлены workflow-файлы:

- `.github/workflows/ci.yml`:
  - запускается на `push` и `pull_request`;
  - ставит Python 3.12 и Poetry;
  - устанавливает зависимости;
  - запускает `pytest` из директории `backend/`.

- `.github/workflows/cd.yml`:
  - запускается на `push` в `main`, на теги `v*` и вручную через `workflow_dispatch`;
  - собирает Docker-образ из `backend/Dockerfile`;
  - публикует образ в GitHub Container Registry (`ghcr.io/<owner>/<repo>`).

### Опциональный авто-деплой на сервер

`cd.yml` содержит необязательный job `deploy`, который выполняется только если заданы секреты:

- `DEPLOY_HOST`
- `DEPLOY_USER`
- `DEPLOY_SSH_KEY`
- `DEPLOY_SCRIPT`
- `DEPLOY_PORT` (опционально, по умолчанию `22`)

Переменная окружения `IMAGE` передается в `DEPLOY_SCRIPT` автоматически и содержит:

```text
ghcr.io/<owner>/<repo>:main
```
