import csv
import datetime
import typing as t
from io import StringIO

from pydantic.types import UUID4

import enums
import models


def make_csv_stream(transactions: t.List[models.TransactionDB]) -> StringIO:
    io = StringIO()
    writer = csv.DictWriter(io, fieldnames=models.TransactionDB.__fields__)
    writer.writeheader()
    for transaction in transactions:
        if not transaction.sender_wallet_id:
            transaction.sender_wallet_id = 'EXTERNAL_DEPOSIT'
        writer.writerow(transaction.dict())
    io.seek(0)
    return io


def make_filename(
        wallet_id: UUID4,
        from_timestamp: datetime.datetime,
        to_timestamp: datetime.datetime,
        side: enums.TransferSide,
) -> str:
    filename_suffixes = [str(wallet_id)]

    if from_timestamp:
        filename_suffixes.append('from' + str(from_timestamp).replace(' ', '_'))

    if to_timestamp:
        filename_suffixes.append('to' + str(to_timestamp).replace(' ', '_'))

    if not side:
        filename_suffixes.append('both')
    elif side is enums.TransferSide.deposit:
        filename_suffixes.append(side.value)
    elif side is enums.TransferSide.withdraw:
        filename_suffixes.append(side.value)
    filename_suffix = '-'.join(filename_suffixes)
    filename = f'export-{filename_suffix}.csv'
    return filename
