# FastAPI Example App

FastAPI-Users:

- GitHub https://github.com/fastapi-users/fastapi-users
- Docs https://fastapi-users.github.io/fastapi-users/latest/

FastAPI Base app:

- https://github.com/mahenzon/FastAPI-base-app

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

# ЗАДАЧИ

1. добавить refresh токен 
2. написать на celery/schedule/cron очистку таблицы access_tokens от устаревших токенов
3. назначить для десериализации и сериализации по умолчанию с использованием jsonb формата (написан на rust)
4. добавить подтверждение по email
7. подумать над логикой выдачи ролей пользователям, если оставить выбор за пользователем, все будут админами, нам нужна система которая будет проверять, можно сделать так, назначить на определенного человека статус суперюзера, и он уже будет выдавать кому надо роль администратора, но как это реализовать правильно надо еще подумать
8. у нас выдается аксес токен только после входа в зарегистрированный аккаунт, можно сделать чтобы при регистрации тоже выдавался, что думаешь

9. решить ошибку в backend/core/schemas/user.py, описание в TODO внутри комментария (просто чекни)
10. решить вопрос в backend/core/schemas/user.py, описано в TODO
11. контроллер /api/v1/users/me выдает ошибку (такую же как ниже)
12. контроллер /api/v1/auth/logout выдает ошибку: 
`sqlalchemy.exc.ProgrammingError: (sqlalchemy.dialects.postgresql.asyncpg.ProgrammingError) <class 'asyncpg.exceptions.UndefinedFunctionError'>: operator does not exist: uuid = bigint
HINT:  No operator matches the given name and argument types. You might need to add explicit type casts.
[SQL: SELECT users.email, users.hashed_password, users.is_active, users.is_superuser, users.is_verified, users.username, users.role, users.id
FROM users
WHERE users.id = $1::BIGINT]
[parameters: (2140135120920776520886332186080348797,)]
(Background on this error at: https://sqlalche.me/e/20/f405)` при попытке выйти из аккаунте 
13. контроллер /api/v1/users/me (patch), такая же ошибка 
14. контроллер /api/v1/users/{user_id}, также 
15. контроллер /api/v1/users/{user_id} (patch), также 
16. контроллер /api/v1/users/{user_id} (delete), также 
17. контроллер /api/v1/messages, также 
18. контроллер /api/v1/messages/secrets, также 
19. контроллер /api/v1/auth/request-verify-token возвращает null и токен верификации с uuid пользователя в терминал (сообщение от user_manager)
20. контроллер /api/v1/auth/verify возвращает 400 ошибку, как с указанным токеном, так и без него 
21. контроллер /api/v1/auth/forgot-password возвращает 400 ошибку, вместе с токеном сброса и uuid пользователя в терминал (сообщение от user_manager), в самом ответе идет null
22. контроллер /api/v1/auth/reset-password возвращает 400 ошибку, как с использованием reset-токена, так и без него 

---

МОДУЛЬ 2

# Реализовать профиль

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

МОДУЛЬ 4

# Реализовать админку

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

# COMPLETED

5. добавить поле username (внутри которого будут поля first_name, last_name, patronymic or middle_name) 
class UserUsername(BaseModel):
class User(Base, IdUuidPkMixin, SQLAlchemyBaseUserTable[UserIdType]):

1. уменьшено время жизни access токена с 3600 секунд до 600-300
class AccessToken(BaseModel):
lifetime_seconds: int = 600
class CookieConfig(BaseModel):
lifetime_seconds: int = 600

6.  проверить, идет ли проверка повторного пароля для проверку на фронтенде, если нет, ввести новое поле в схеме для валидации
role: UserRole
password_confirm: str
