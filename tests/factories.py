import decimal
import typing as t
import uuid
from random import randint

from pydantic import UUID4

import models


def make_wallet_json(
        wallet_id: t.Union[str, UUID4] = str(uuid.uuid4()),
        user_id: t.Union[str, UUID4] = str(uuid.uuid4()),
        name: str = f'wallet{randint(1, 999)}',
        balance: decimal.Decimal = decimal.Decimal(0),
) -> t.Dict[str, t.Any]:
    return models.WalletDB(
        id=str(wallet_id),
        user_id=str(user_id),
        name=name,
        balance=balance,
    ).dict()
