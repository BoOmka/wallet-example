import datetime
import decimal
import uuid

import freezegun
import pytest

import models
from tests.factories import make_wallet_json
from tests.utils import async_mock, call_args_to_sql_strings, compile_sql_statement, post


WALLET_ID = str(uuid.uuid4())
DEPOSIT_VALUE = decimal.Decimal('10.0001')

SELECT_FOR_UPDATE_STMT = compile_sql_statement(
    models.wallets.select(
        models.wallets.c.id == WALLET_ID,
        for_update=True,
    ).with_only_columns([
        models.wallets.c.id,
        models.wallets.c.user_id,
        models.wallets.c.balance,
    ])
)
UPDATE_BALANCE_STMT = compile_sql_statement(
    models.wallets.update(
        models.wallets.c.id == WALLET_ID
    ).values(
        balance=models.wallets.c.balance + DEPOSIT_VALUE
    ).returning(models.wallets.c.balance),
    literal_binds=False
)


def make_insert_transaction_stmt():
    return compile_sql_statement(
        models.transactions.insert(values={
            'sender_wallet_id': None,
            'recipient_wallet_id': WALLET_ID,
            'value': DEPOSIT_VALUE,
            'timestamp': datetime.datetime.utcnow()
        }),
        literal_binds=False
    )


@freezegun.freeze_time(datetime.datetime(2020, 1, 1, 0, 0, 0))
def test_deposit__own_wallet__returns_value_and_new_balance(database, user, test_app):
    wallet_data = make_wallet_json(wallet_id=WALLET_ID, user_id=user.id)
    database.fetch_one = async_mock(return_value=wallet_data)
    database.fetch_val = async_mock(return_value=decimal.Decimal('110.0001'))

    response = post(test_app, f'/wallet/{WALLET_ID}/deposit', json={'value': str(DEPOSIT_VALUE)})

    fetch_one_sql_args = call_args_to_sql_strings(database.fetch_one.mock.call_args_list)
    assert database.fetch_one.mock.call_count == 1
    assert SELECT_FOR_UPDATE_STMT in fetch_one_sql_args

    fetch_val_sql_args = call_args_to_sql_strings(database.fetch_val.mock.call_args_list, literal_binds=False)
    assert database.fetch_val.mock.call_count == 1
    assert UPDATE_BALANCE_STMT in fetch_val_sql_args

    execute_sql_args = call_args_to_sql_strings(database.execute.mock.call_args_list, literal_binds=False)
    assert database.execute.mock.call_count == 1
    assert make_insert_transaction_stmt() in execute_sql_args

    assert response.status_code == 200
    assert response.json() == {
        'balance': '110.0001',
        'value': '10.0001',
    }


@freezegun.freeze_time(datetime.datetime(2020, 1, 1, 0, 0, 0))
def test_deposit__stranger_wallet__returns_value_only(database, user, test_app):
    wallet_data = make_wallet_json(wallet_id=WALLET_ID)
    database.fetch_one = async_mock(return_value=wallet_data)
    database.fetch_val = async_mock(return_value=decimal.Decimal('110.0001'))

    response = post(test_app, f'/wallet/{WALLET_ID}/deposit', json={'value': str(DEPOSIT_VALUE)})

    fetch_one_sql_args = call_args_to_sql_strings(database.fetch_one.mock.call_args_list)
    assert database.fetch_one.mock.call_count == 1
    assert SELECT_FOR_UPDATE_STMT in fetch_one_sql_args

    fetch_val_sql_args = call_args_to_sql_strings(database.fetch_val.mock.call_args_list, literal_binds=False)
    assert database.fetch_val.mock.call_count == 1
    assert UPDATE_BALANCE_STMT in fetch_val_sql_args

    execute_sql_args = call_args_to_sql_strings(database.execute.mock.call_args_list, literal_binds=False)
    assert database.execute.mock.call_count == 1
    assert make_insert_transaction_stmt() in execute_sql_args

    assert response.status_code == 200
    assert response.json() == {
        'value': '10.0001',
        'balance': None,
    }


def test_deposit__wallet_does_not_exist__returns_error(database, user, test_app):
    database.fetch_one = async_mock(return_value=None)
    database.fetch_val = async_mock(return_value=decimal.Decimal('110.0001'))

    response = post(test_app, f'/wallet/{WALLET_ID}/deposit', json={'value': str(DEPOSIT_VALUE)})

    fetch_one_sql_args = call_args_to_sql_strings(database.fetch_one.mock.call_args_list)
    assert database.fetch_one.mock.call_count == 1
    assert SELECT_FOR_UPDATE_STMT in fetch_one_sql_args
    assert database.execute.mock.call_count == 0

    assert response.status_code == 404
    assert response.json()['detail'][0]['entity'] == 'wallet'


def test_deposit__negative_deposit__returns_error(database, user, test_app):
    deposit_value = decimal.Decimal(-10)

    database.fetch_one = async_mock(return_value=None)
    database.fetch_val = async_mock(return_value=decimal.Decimal('110.0001'))

    response = post(test_app, f'/wallet/{WALLET_ID}/deposit', json={'value': str(deposit_value)})

    assert database.fetch_one.mock.call_count == 0
    assert database.execute.mock.call_count == 0

    assert response.status_code == 422
    assert response.json()['detail'][0]['msg'] == 'Must be positive'


@pytest.mark.parametrize(
    'deposit_value, expected_status_code',
    (
            (decimal.Decimal('0.00000001'), 200),
            (decimal.Decimal('0.00000000999'), 422),
            (decimal.Decimal('0.000000001'), 422),
    )
)
def test_deposit__decimals__returns_error(deposit_value, expected_status_code, database, user, test_app):
    wallet_data = make_wallet_json(wallet_id=WALLET_ID, user_id=user.id)
    database.fetch_one = async_mock(return_value=wallet_data)
    database.fetch_val = async_mock(return_value=decimal.Decimal('110.0001'))

    response = post(test_app, f'/wallet/{WALLET_ID}/deposit', json={'value': str(deposit_value)})

    assert response.status_code == expected_status_code
