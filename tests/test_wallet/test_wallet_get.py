import decimal
import uuid

from tests.utils import async_mock, get


def test_get__exists__returns_wallet(database, user, test_app):
    wallet_id = str(uuid.uuid4())
    wallet_data = {
        'id': wallet_id,
        'user_id': user.id,
        'name': 'wallet1',
        'balance': decimal.Decimal(10),
    }
    database.fetch_one = async_mock(return_value=wallet_data)
    response = get(test_app, f'/wallet/{wallet_id}')

    assert response.status_code == 200
    assert response.json() == {
        'id': wallet_id,
        'name': 'wallet1',
        'balance': '10',
    }


def test_get__does_not_exist__returns_error(database, user, test_app):
    wallet_id = str(uuid.uuid4())
    database.fetch_one = async_mock(return_value=None)
    response = get(test_app, f'/wallet/{wallet_id}')

    assert response.status_code == 404
    assert response.json()['detail'][0]['entity'] == 'wallet'


def test_get__not_owned__returns_error(database, user, test_app):
    wallet_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())
    wallet_data = {
        'id': wallet_id,
        'user_id': user_id,
        'name': 'wallet1',
        'balance': decimal.Decimal(10),
    }
    database.fetch_one = async_mock(return_value=wallet_data)
    response = get(test_app, f'/wallet/{wallet_id}')

    assert response.status_code == 403
    assert response.json()['detail'][0]['msg'] == 'User does not own the wallet'
