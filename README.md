# Тестовое задание Billing

### Запуск
#### docker-compose:
```shell script
docker-compose up -d --build
```
#### На хосте:
```shell script
docker run -d \
    --name postgres \
    -e POSTGRES_USER=wallet \
    -e POSTGRES_PASSWORD=wallet \
    -e POSTGRES_DB=wallet \
    -e PGDATA=/var/lib/postgresql/data/pgdata \
    postgres
pipenv install
pipenv run python ./wallet/tools/create_tables.py
pipenv run python ./wallet/tools/create_users.py
pipenv run python ./wallet/main.py
```


Порт приложения по-умолчанию: `8080`

Документация OpenAPI доступна по корневому пути.

Автоматически создаётся два пользователя. Для простоты тестирования можно использовать заранее сгенерированные долгоживущие JWT: 
- test1@test.test: `eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ1c2VyX2lkIjoiNDM1YzFhZjMtODYwYi00ZGI4LThjZmItM2U0ZTM5ZjY5MDM2IiwiYXVkIjoiZmFzdGFwaS11c2VyczphdXRoIiwiZXhwIjoxOTA5OTI2NDY5fQ.YhO8qcPO2Pogz39ycXU9CK8_6-HtnSOwuR1rFsvGUyo`
- test2@test.test: `eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ1c2VyX2lkIjoiYWU2MDhhMTMtOTE5ZC00ZjUxLWI5NDQtMzA3ODY2NDY0OTNlIiwiYXVkIjoiZmFzdGFwaS11c2VyczphdXRoIiwiZXhwIjoxOTA5OTI2Njg2fQ.f9Zl-tCc36fPNGFp2rWwMpktZo93DwuVRYjAXVuZlcY`


Либо можно воспользоваться эндпоинтом `/auth/jwt/login` (пароль у обоих пользователей `test`):
```shell script
curl -X POST "http://0.0.0.0:8080/auth/jwt/login" -H "accept: application/json" -H "Content-Type: application/x-www-form-urlencoded" -d "username={email}&password={password}"
```

