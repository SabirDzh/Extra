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
8. В файле `middlewares/requests_count_middleware.py` удалить все и сменить на Prometheus + Grafana
9. у нас выдается аксес токен только после входа в зарегистрированный аккаунт, можно сделать чтобы при регистрации тоже выдавался, что думаешь

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
