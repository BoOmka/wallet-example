cd wallet || return 1
pipenv run python tools/create_tables.py
pipenv run python tools/create_users.py
pipenv run python -O main.py
