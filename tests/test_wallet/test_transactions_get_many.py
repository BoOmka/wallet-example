import csv
import datetime
import decimal
import uuid

import pytest
from sqlalchemy import and_, or_

import tables
from models import TransactionDB
from tests.factories import make_wallet_json
from tests.utils import async_mock, call_args_to_sql_strings, compile_sql_statement, get


WALLET_ID = str(uuid.uuid4())
COUNTERPARTY_WALLET_ID = str(uuid.uuid4())


@pytest.mark.parametrize(
    'args, condition',
    (
            (
                    'from_timestamp=2020-01-01%2000%3A00%3A01&to_timestamp=2020-01-01%2000%3A00%3A10',
                    and_(
                        or_(
                            tables.transactions.c.recipient_wallet_id == WALLET_ID,
                            tables.transactions.c.sender_wallet_id == WALLET_ID,
                        ),
                        tables.transactions.c.timestamp >= datetime.datetime(2020, 1, 1, 0, 0, 1),
                        tables.transactions.c.timestamp <= datetime.datetime(2020, 1, 1, 0, 0, 10),
                    ),
            ),
            (
                    'from_timestamp=2020-01-01%2000%3A00%3A01&to_timestamp=2020-01-01%2000%3A00%3A10&side=deposit',
                    and_(
                        tables.transactions.c.recipient_wallet_id == WALLET_ID,
                        tables.transactions.c.timestamp >= datetime.datetime(2020, 1, 1, 0, 0, 1),
                        tables.transactions.c.timestamp <= datetime.datetime(2020, 1, 1, 0, 0, 10),
                    )
            ),
            (
                    'from_timestamp=2020-01-01%2000%3A00%3A01&to_timestamp=2020-01-01%2000%3A00%3A10&side=withdraw',
                    and_(
                        tables.transactions.c.sender_wallet_id == WALLET_ID,
                        tables.transactions.c.timestamp >= datetime.datetime(2020, 1, 1, 0, 0, 1),
                        tables.transactions.c.timestamp <= datetime.datetime(2020, 1, 1, 0, 0, 10),
                    )
            ),
            (
                    'from_timestamp=2020-01-01%2000%3A00%3A01&side=withdraw',
                    and_(
                        tables.transactions.c.sender_wallet_id == WALLET_ID,
                        tables.transactions.c.timestamp >= datetime.datetime(2020, 1, 1, 0, 0, 1),
                    )
            ),
            (
                    'to_timestamp=2020-01-01%2000%3A00%3A01',
                    and_(
                        or_(
                            tables.transactions.c.recipient_wallet_id == WALLET_ID,
                            tables.transactions.c.sender_wallet_id == WALLET_ID,
                        ),
                        tables.transactions.c.timestamp <= datetime.datetime(2020, 1, 1, 0, 0, 1),
                    )
            ),
    )
)
def test_get__wallet_exists_and_owned_args__returns_wallet_list(args, condition, database, user, test_app):
    wallet_data = make_wallet_json(wallet_id=WALLET_ID, user_id=user.id)
    transactions = [
        TransactionDB(
            id=1,
            sender_wallet_id=None,
            recipient_wallet_id=WALLET_ID,
            value=decimal.Decimal(1),
            timestamp=datetime.datetime(2020, 1, 1, 0, 0, 1),
        ).dict(),
        TransactionDB(
            id=2,
            sender_wallet_id=COUNTERPARTY_WALLET_ID,
            recipient_wallet_id=WALLET_ID,
            value=decimal.Decimal(2),
            timestamp=datetime.datetime(2020, 1, 1, 0, 0, 2),
        ).dict(),
        TransactionDB(
            id=3,
            sender_wallet_id=WALLET_ID,
            recipient_wallet_id=COUNTERPARTY_WALLET_ID,
            value=decimal.Decimal(1),
            timestamp=datetime.datetime(2020, 1, 1, 0, 0, 3),
        ).dict(),
    ]

    database.fetch_one = async_mock(return_value=wallet_data)
    database.fetch_all = async_mock(return_value=transactions)

    response = get(test_app, f'/wallet/{WALLET_ID}/operations?{args}')

    select_stmt = compile_sql_statement(
        tables.transactions.select(
            condition
        ).with_only_columns([
            tables.transactions.c.id,
            tables.transactions.c.sender_wallet_id,
            tables.transactions.c.recipient_wallet_id,
            tables.transactions.c.value,
            tables.transactions.c.timestamp,
        ]).order_by(tables.transactions.c.timestamp)
    )

    assert call_args_to_sql_strings(database.fetch_all.mock.call_args_list)[0] == select_stmt

    assert response.status_code == 200
    assert response.headers['Content-Type'] == 'text/csv; charset=utf-8'
    csv_obj = csv.reader(response.content.decode().rstrip('\r\n').split('\r\n'))
    lines = list(csv_obj)
    assert lines[0] == ['id', 'sender_wallet_id', 'recipient_wallet_id', 'value', 'timestamp']
    assert lines[1:] == [
        ['1', 'EXTERNAL_DEPOSIT', WALLET_ID, '1', '2020-01-01 00:00:01'],
        ['2', COUNTERPARTY_WALLET_ID, WALLET_ID, '2', '2020-01-01 00:00:02'],
        ['3', WALLET_ID, COUNTERPARTY_WALLET_ID, '1', '2020-01-01 00:00:03'],
    ]


def test_get__wallet_exists_not_owned__returns_error(database, user, test_app):
    wallet_data = make_wallet_json(wallet_id=WALLET_ID)

    database.fetch_one = async_mock(return_value=wallet_data)

    response = get(test_app, f'/wallet/{WALLET_ID}/operations')

    assert database.fetch_all.mock.call_count == 0
    assert response.status_code == 403
    assert response.json()['detail'][0]['msg'] == 'User does not own the wallet'


def test_get__wallet_does_not_exist__returns_error(database, user, test_app):
    wallet_data = None

    database.fetch_one = async_mock(return_value=wallet_data)

    response = get(test_app, f'/wallet/{WALLET_ID}/operations')

    assert database.fetch_all.mock.call_count == 0
    assert response.status_code == 404
    assert response.json()['detail'][0]['entity'] == 'wallet'
