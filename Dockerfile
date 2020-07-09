FROM python:3.8.3

COPY . /app

RUN pip install pipenv
WORKDIR /app
RUN pipenv install

CMD pipenv run python -O /app/wallet/main.py
