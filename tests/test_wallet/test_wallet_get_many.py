import uuid

from tests.utils import async_mock


def test_get__called__returns_wallet_list(database, user, test_app):
    wallet_list = [
        {
            'id': str(uuid.uuid4()),
            'name': 'wallet1'
        },
        {
            'id': str(uuid.uuid4()),
            'name': 'wallet2'
        }
    ]
    database.fetch_all = async_mock(return_value=wallet_list)
    response = test_app.get('/wallet?args=a&kwargs=b')

    assert response.status_code == 200
    assert response.json() == {
        'wallets': wallet_list
    }
