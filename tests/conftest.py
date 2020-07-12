from imp import reload

import pytest
from fastapi_users.password import get_password_hash
from starlette.testclient import TestClient

from models import UserDB
from tests.utils import AsyncContextManagerMock, async_mock


@pytest.fixture
def user() -> UserDB:
    return UserDB(
        email="king.arthur@camelot.bt", hashed_password=get_password_hash("guinevere"),
    )


@pytest.fixture(scope='function')
def user(mocker):
    user = UserDB(
        id='561eb287-d449-4dc6-9268-40ff31e70bed',
        email='admin@example.net',
        hashed_password='$2b$12$DNhL2..WKnJvEvsN9sBBVO9XGiLUYprDxCn/bLC6ZIaCI4CGOzbX2',
    )
    fastapi_users_mock = mocker.patch('fastapi_users.FastAPIUsers')
    fastapi_users_mock.return_value.get_current_user.return_value = user

    return user


@pytest.fixture(scope='function')
def database(mocker):
    database = mocker.patch('databases.Database')
    database.return_value.transaction = AsyncContextManagerMock()
    database.return_value.fetch_all = async_mock()
    database.return_value.fetch_one = async_mock()
    database.return_value.fetch_val = async_mock()
    database.return_value.execute = async_mock()
    return database.return_value


@pytest.fixture(scope='function')
def test_app():
    import wallet.main
    reload(wallet.main)
    client = TestClient(wallet.main.app)
    yield client
