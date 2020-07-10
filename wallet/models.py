import datetime
import decimal
import typing
import uuid

import sqlalchemy
from fastapi_users import models
from fastapi_users.db import SQLAlchemyBaseUserTable
from fastapi_users.db.sqlalchemy import GUID
from pydantic import BaseModel, UUID4, validator
from sqlalchemy import Column, DECIMAL, Integer, String, TIMESTAMP, Index
from sqlalchemy.ext.declarative import DeclarativeMeta, declarative_base

import config


Base: DeclarativeMeta = declarative_base()


# Declarative tables
class UserTable(Base, SQLAlchemyBaseUserTable):
    pass


class WalletTable(Base):
    __tablename__ = 'wallet'

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    user_id = Column(GUID)
    name = Column(String, unique=True)
    balance = Column(DECIMAL)


class TransactionTable(Base):
    __tablename__ = 'transaction'

    id = Column(Integer, primary_key=True, autoincrement=True)
    sender_wallet_id = Column(GUID, nullable=True)
    recipient_wallet_id = Column(GUID)
    value = Column(DECIMAL)
    timestamp = Column(TIMESTAMP)

    __table_args__ = (
        Index('sender_wallet_id_timestamp_idx', 'sender_wallet_id', 'timestamp'),
        Index('recipient_wallet_id_timestamp_idx', 'recipient_wallet_id', 'timestamp'),
    )


# Table instances
users = UserTable.__table__
wallets = WalletTable.__table__
transactions = TransactionTable.__table__


# Pydantic models
class ErrorDetails(BaseModel):
    details: str


class User(models.BaseUser):
    pass


class UserCreate(models.BaseUserCreate):
    pass


class UserUpdate(User, models.BaseUserUpdate):
    pass


class UserDB(User, models.BaseUserDB):
    pass


class Wallet(BaseModel):
    id: UUID4
    name: str
    balance: decimal.Decimal


class WalletCreate(BaseModel):
    name: str


class WalletDeposit(BaseModel):
    value: decimal.Decimal

    @validator('value')
    def value_must_be_positive(cls, v: decimal.Decimal):
        if v <= decimal.Decimal(0):
            raise ValueError('Must be positive')
        return v

    @validator('value')
    def value_must_have_8_decimals(cls, v: decimal.Decimal):
        if abs(v.as_tuple().exponent) > 8:
            raise ValueError('Must have at most 8 decimal places')
        return v


class WalletTransfer(WalletDeposit):
    pass


class WalletValueBalance(BaseModel):
    value: decimal.Decimal
    balance: typing.Optional[decimal.Decimal]


class WalletId(BaseModel):
    id: UUID4


class WalletListItem(BaseModel):
    id: UUID4
    name: str


class WalletList(BaseModel):
    wallets: typing.List[WalletListItem]


class Transaction(BaseModel):
    id: int
    sender_wallet_id: int
    recipient_wallet_id: int
    value: decimal.Decimal
    timestamp: datetime.datetime


if __name__ == '__main__':
    engine = sqlalchemy.create_engine(config.POSTGRES_DSN, )
    Base.metadata.create_all(engine)
