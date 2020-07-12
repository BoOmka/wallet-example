import datetime
import decimal
import uuid

import freezegun

import tables
from tests.factories import make_wallet_json
from tests.utils import async_mock, call_args_to_sql_strings, compile_sql_statement, post


SENDER_WALLET_ID = str(uuid.uuid4())
RECIPIENT_WALLET_ID = str(uuid.uuid4())
TRANSFER_VALUE = decimal.Decimal(10)

DECREMENT_SENDER_BALANCE_STMT = compile_sql_statement(
    tables.wallets.update(
        tables.wallets.c.id == SENDER_WALLET_ID
    ).values(
        balance=tables.wallets.c.balance + (-TRANSFER_VALUE),
    ).returning(tables.wallets.c.balance)
)
INCREMENT_RECIPIENT_BALANCE_STMT = compile_sql_statement(
    tables.wallets.update(
        tables.wallets.c.id == RECIPIENT_WALLET_ID
    ).values(
        balance=tables.wallets.c.balance + TRANSFER_VALUE,
    ).returning(tables.wallets.c.balance)
)


def make_insert_transaction_stmt():
    return compile_sql_statement(
        tables.transactions.insert(values={
            'sender_wallet_id': SENDER_WALLET_ID,
            'recipient_wallet_id': RECIPIENT_WALLET_ID,
            'value': TRANSFER_VALUE,
            'timestamp': datetime.datetime.utcnow(),
        })
    )


@freezegun.freeze_time(datetime.datetime(2020, 1, 1, 0, 0, 0))
def test__user_owns_sender_wallet_recipient_exists_sufficient_funds__returns_new_balance(database, user, test_app):
    sender_wallet_data = make_wallet_json(wallet_id=SENDER_WALLET_ID, user_id=user.id, balance=decimal.Decimal(100))
    recipient_wallet_data = make_wallet_json(wallet_id=RECIPIENT_WALLET_ID)

    database.fetch_one = async_mock(side_effect=[
        sender_wallet_data,
        recipient_wallet_data,
    ])
    database.fetch_val = async_mock(return_value=decimal.Decimal(90))

    response = post(
        test_app,
        f'/wallet/{SENDER_WALLET_ID}/transfer-to/{RECIPIENT_WALLET_ID}',
        json={'value': str(TRANSFER_VALUE)},
    )

    fetch_val_sql_args = call_args_to_sql_strings(database.fetch_val.mock.call_args_list)
    assert database.fetch_val.mock.call_count == 2
    assert DECREMENT_SENDER_BALANCE_STMT in fetch_val_sql_args
    assert INCREMENT_RECIPIENT_BALANCE_STMT in fetch_val_sql_args

    execute_sql_args = call_args_to_sql_strings(database.execute.mock.call_args_list)
    assert database.execute.mock.call_count == 1
    assert make_insert_transaction_stmt() in execute_sql_args

    assert response.status_code == 200
    assert response.json() == {
        'balance': '90',
        'value': '10',
    }


def test__sender_insufficient_funds__returns_error(database, user, test_app):
    sender_wallet_data = make_wallet_json(wallet_id=SENDER_WALLET_ID, user_id=user.id, balance=decimal.Decimal(1))
    recipient_wallet_data = make_wallet_json(wallet_id=RECIPIENT_WALLET_ID)

    database.fetch_one = async_mock(side_effect=[
        sender_wallet_data,
        recipient_wallet_data,
    ])
    database.fetch_val = async_mock(return_value=decimal.Decimal(90))

    response = post(
        test_app,
        f'/wallet/{SENDER_WALLET_ID}/transfer-to/{RECIPIENT_WALLET_ID}',
        json={'value': str(TRANSFER_VALUE)},
    )
    assert database.execute.mock.call_count == 0
    assert response.status_code == 400
    assert response.json()['detail'][0]['msg'] == 'Insufficient funds'


def test__user_does_not_own_sender__returns_error(database, user, test_app):
    sender_wallet_data = make_wallet_json(wallet_id=SENDER_WALLET_ID, balance=decimal.Decimal(100))
    recipient_wallet_data = make_wallet_json(wallet_id=RECIPIENT_WALLET_ID)

    database.fetch_one = async_mock(side_effect=[
        sender_wallet_data,
        recipient_wallet_data,
    ])
    database.fetch_val = async_mock(return_value=decimal.Decimal(90))

    response = post(
        test_app,
        f'/wallet/{SENDER_WALLET_ID}/transfer-to/{RECIPIENT_WALLET_ID}',
        json={'value': str(TRANSFER_VALUE)},
    )

    assert database.execute.mock.call_count == 0
    assert response.status_code == 403
    assert response.json()['detail'][0]['msg'] == 'User does not own the sender wallet'


def test__sender_does_not_exist__returns_error(database, user, test_app):
    sender_wallet_data = None
    recipient_wallet_data = make_wallet_json(wallet_id=RECIPIENT_WALLET_ID)

    database.fetch_one = async_mock(side_effect=[
        sender_wallet_data,
        recipient_wallet_data,
    ])
    database.fetch_val = async_mock(return_value=decimal.Decimal(90))

    response = post(
        test_app,
        f'/wallet/{SENDER_WALLET_ID}/transfer-to/{RECIPIENT_WALLET_ID}',
        json={'value': str(TRANSFER_VALUE)},
    )

    assert database.execute.mock.call_count == 0
    assert response.status_code == 404
    assert response.json()['detail'][0]['entity'] == 'sender_wallet'


def test__recipient_does_not_exist__returns_error(database, user, test_app):
    sender_wallet_data = make_wallet_json(wallet_id=SENDER_WALLET_ID, user_id=user.id, balance=decimal.Decimal(100))
    recipient_wallet_data = None

    database.fetch_one = async_mock(side_effect=[
        sender_wallet_data,
        recipient_wallet_data,
    ])
    database.fetch_val = async_mock(return_value=decimal.Decimal(90))

    response = post(
        test_app,
        f'/wallet/{SENDER_WALLET_ID}/transfer-to/{RECIPIENT_WALLET_ID}',
        json={'value': str(TRANSFER_VALUE)},
    )

    assert response.status_code == 404
    assert response.json()['detail'][0]['entity'] == 'recipient_wallet'


def test__recipient_is_sender__returns_error(database, user, test_app):
    sender_wallet_data = make_wallet_json(wallet_id=SENDER_WALLET_ID, user_id=user.id, balance=decimal.Decimal(100))
    recipient_wallet_data = sender_wallet_data

    database.fetch_one = async_mock(side_effect=[
        sender_wallet_data,
        recipient_wallet_data,
    ])
    database.fetch_val = async_mock(return_value=decimal.Decimal(90))

    response = post(
        test_app,
        f'/wallet/{SENDER_WALLET_ID}/transfer-to/{SENDER_WALLET_ID}',
        json={'value': str(TRANSFER_VALUE)},
    )

    assert response.status_code == 400
    assert response.json()['detail'][0]['msg'] == 'Cannot transfer to self'
