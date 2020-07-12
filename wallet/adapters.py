import datetime
import decimal
import typing as t
import uuid

import asyncpg
from databases import Database
from pydantic.types import UUID4
from sqlalchemy import Table, and_, or_

import enums
import models


# noinspection PyPropertyAccess
class WalletDatabaseAdapter:
    def __init__(
            self,
            db_model: t.Type[models.WalletDB],
            database: Database,
            table: Table,
    ):
        self.db_model = db_model
        self.database = database
        self.table = table
        
    async def create(self, wallet: models.WalletCreate, user_id: UUID4) -> UUID4:
        query = self.table.insert(values={
            'id': uuid.uuid4(),
            'user_id': user_id,
            'name': wallet.name,
            'balance': decimal.Decimal(0),
        }).returning(self.table.c.id)
        try:
            return await self.database.fetch_val(query)
        except asyncpg.UniqueViolationError:
            raise ValueError('Wallet with this name already exists')

    async def get(self, wallet_id: UUID4) -> t.Optional[models.WalletDB]:
        query = self.table.select().where(self.table.c.id == wallet_id)
        wallet_dict = await self.database.fetch_one(query)
        return self.db_model(**wallet_dict) if wallet_dict else None

    async def get_many(self, user_id: UUID4) -> t.List[models.WalletDB]:
        query = self.table.select().where(
            self.table.c.user_id == user_id,
        ).with_only_columns([
            self.table.c.id,
            self.table.c.name,
        ])
        wallet_dicts = await self.database.fetch_all(query)
        return [self.db_model(**wallet_dict) for wallet_dict in wallet_dicts]

    async def lock(self, wallet_id: UUID4) -> t.Optional[models.WalletDB]:
        query = self.table.select(for_update=True).where(
            self.table.c.id == wallet_id,
        ).with_only_columns([
            self.table.c.id,
            self.table.c.user_id,
            self.table.c.balance,
        ])
        wallet_dict = await self.database.fetch_one(query)
        return self.db_model(**wallet_dict) if wallet_dict else None

    async def increase_balance(self, wallet_id: UUID4, delta: decimal.Decimal) -> decimal.Decimal:
        return await self._alter_balance(wallet_id, delta)

    async def decrease_balance(self, wallet_id: UUID4, delta: decimal.Decimal) -> decimal.Decimal:
        return await self._alter_balance(wallet_id, -delta)

    async def _alter_balance(self, wallet_id: UUID4, delta: decimal.Decimal) -> decimal.Decimal:
        query = self.table.update(
            self.table.c.id == wallet_id
        ).values(
            balance=self.table.c.balance + delta
        ).returning(self.table.c.balance)
        return await self.database.fetch_val(query)


# noinspection PyPropertyAccess
class TransactionDatabaseAdapter:
    def __init__(
            self,
            db_model: t.Type[models.TransactionDB],
            database: Database,
            table: Table,
    ):
        self.db_model = db_model
        self.database = database
        self.table = table

    async def create(self, transaction: models.TransactionDB) -> UUID4:
        query = self.table.insert(values=transaction.dict(exclude={'id'}))
        return await self.database.execute(query)

    async def get_many(
            self,
            wallet_id: UUID4,
            from_timestamp: datetime.datetime = None,
            to_timestamp: datetime.datetime = None,
            transfer_side: enums.TransferSide = None,
    ) -> t.List[models.TransactionDB]:
        and_conditions = []
        or_conditions = []
        if not transfer_side or transfer_side is enums.TransferSide.deposit:
            or_conditions.append(self.table.c.recipient_wallet_id == wallet_id)
        if not transfer_side or transfer_side is enums.TransferSide.withdraw:
            or_conditions.append(self.table.c.sender_wallet_id == wallet_id)
        and_conditions.append(or_(*or_conditions))
        if from_timestamp:
            and_conditions.append(self.table.c.timestamp >= from_timestamp)
        if to_timestamp:
            and_conditions.append(self.table.c.timestamp <= to_timestamp)

        query = self.table.select(and_(
            *and_conditions
        )).order_by(self.table.c.timestamp)

        transaction_dicts = await self.database.fetch_all(query)
        return [models.TransactionDB(**transaction_dict) for transaction_dict in transaction_dicts]
