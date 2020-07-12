import asyncio
import logging

import databases
from asyncpg import UniqueViolationError
from fastapi_users.db import SQLAlchemyUserDatabase
from fastapi_users.password import get_password_hash

import config
import models
import tables


_LOGGER = logging.getLogger(__name__)


async def main():
    _LOGGER.info('Connecting...')
    database = databases.Database(config.POSTGRES_DSN)
    await database.connect()
    _LOGGER.info('Connected!')

    user_db = SQLAlchemyUserDatabase(models.UserDB, database, tables.users)

    test_users = [
        models.UserCreate(
            email='test1@test.test',
            password='test',
        ),
        models.UserCreate(
            email='test2@test.test',
            password='test',
        )
    ]

    _LOGGER.info('Creating users test1 and test2...')
    for user in test_users:
        hashed_password = get_password_hash(user.password)
        db_user = models.UserDB(
            **user.create_update_dict(), hashed_password=hashed_password
        )
        try:
            await user_db.create(db_user)
        except UniqueViolationError:
            _LOGGER.info(f'User {user.email} already exists')

    _LOGGER.info('Successfully created users')
    await database.disconnect()


if __name__ == '__main__':
    asyncio.run(main())
