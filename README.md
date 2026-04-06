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