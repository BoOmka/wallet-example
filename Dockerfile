FROM python:3.8.3

COPY . /app

RUN pip install pipenv
WORKDIR /app
RUN pipenv install

WORKDIR /app/wallet
ENV PYTHONPATH "${PYTHONPATH}:/app/wallet"
ENV APP_PORT "8080"
ENV POSTGRES_HOST "postgres:5432"

CMD pipenv run python tools/create_tables.py && pipenv run python tools/create_users.py && pipenv run python -O main.py
