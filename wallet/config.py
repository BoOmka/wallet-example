from decouple import config

JWT_SECRET = config('JWT_SECRET', default='SECRET')

POSTGRES_HOST = config('POSTGRES_HOST', default='127.0.0.1:5432')
POSTGRES_USER = config('POSTGRES_USER', default='wallet')
POSTGRES_PASSWORD = config('POSTGRES_PASSWORD', default='wallet')
POSTGRES_DB = config('POSTGRES_DB', default='wallet')

POSTGRES_DSN = f'postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}/{POSTGRES_DB}'
