# FastAPI App

FastAPI-Users:

- GitHub https://github.com/fastapi-users/fastapi-users
- Docs https://fastapi-users.github.io/fastapi-users/latest/

FastAPI Base app:

- https://github.com/mahenzon/FastAPI-base-app

# Miro
- [ссылка](https://miro.com/welcomeonboard/a1NwdEkvV3N5eWlOSXlCT1MyV1hSamlsbUQ0UjlEVm5ia2ZkQkRtNy9xM1Vqcng0WmZ3RWUyY1NTcndrVTFvNzQ2THFzTDZkVUdlNDg1dXFJRGZ6TkxaTk9XdnkxNHViaDJqUGpXc3RqdDZaay9wZWtmTGN3bEpvSDBxMVJmb0ZNakdSWkpBejJWRjJhRnhhb1UwcS9BPT0hdjE=?share_link_id=942239675421)

Run with usage of env params:

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

Запуск cron для очистки таблицы access_tokens от устаревших токенов 
```psql 
crontab -e

*/5 * * * * psql "postgresql://user:password@localhost:5432/shop" \
-c "DELETE FROM access_tokens WHERE created_at < now() - interval '600 seconds';"
```

# Тесты 
- `Перед запуском тестов сменить тип данных с JSONB на JSON в поле username для таблицы базы данных User`
- backend/core/models/user.py

# МОДУЛЬ 2 (`будут перенесены в miro`)

## Реализовать профиль

- фио
- email
- возраст
- пол (уточнить у заказчика)
- аватарка (уточнить у заказчика)
- описание (уточнить у заказчика)
- список курсов
- прогресс бар в процентах по каждому курсу
- полная история попыток прохождения тестов с указанием полученный результатов (баллов/оценок)
- возможность посмотреть и скачать полученный сертификат pdf
- написано в тз что надо сделать полноценный дашборд с курсами, статистикой и файлами (уточнить у заказчика)

---

# МОДУЛЬ 4 (`будут перенесены в miro`)

## Реализовать админку

- возможность администратора выдавать роли любому пользователю, также их понижать
- возможность открывать доступ к курсам для пользователя или группы пользователей
- возможность просматривать данные профиля (фио, email, статус верификации)
- возможность создания, редактирования и удаления курсов или блоков
- возможность загружать видео, текстовые материалы и файлы
- возможность создавать тесты (разные вопросы, выборы вариантов)
- возможность настраивать правильный ответы для автоматической проверки
- возможность администратора и инспектора (менеджера) создавать тесты где будет открываться интерфейс для написания ответа пользователем на определенный вопрос (для ручной проверки)
- возможность для администратора и инспектора выставлять статус "Зачет" или "Незачет"
- возможность оставлять комментарии к ответу (почему ответ был не зачтен или рекомендации)
- возможность просмотреть сколько людей какой курс начали и сколько закончили
- возможность просмотривать средние баллы за все тесты по каждому курсу
- возможность просмотреть на каких вопросах возникает чаще всего затруднение у пользователей, где они часто допускают ошибку/ошбики
