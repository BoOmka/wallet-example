import uuid

import asyncpg

from tests.utils import async_mock


def test_create__created__returns_uuid(database, user, test_app):
    wallet_id = str(uuid.uuid4())
    data = {
        'name': 'some-name',
    }
    database.fetch_val = async_mock(return_value=wallet_id)

    response = test_app.post('/wallet?args=a&kwargs=b', json=data)

    assert response.status_code == 200
    assert response.json() == {
        'id': wallet_id
    }


def test_create__unique_violation__returns_error(database, user, test_app):
    data = {
        'name': 'some-name',
    }
    database.fetch_val = async_mock(side_effect=asyncpg.UniqueViolationError())

    response = test_app.post('/wallet?args=a&kwargs=b', json=data)

    assert response.status_code == 409
    assert response.json() == {
        'detail': 'Wallet with this name already exists'
    }
