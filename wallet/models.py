import datetime
import decimal
import typing as t
import uuid

import sqlalchemy
from fastapi_users import models
from fastapi_users.db import SQLAlchemyBaseUserTable
from fastapi_users.db.sqlalchemy import GUID
from pydantic import BaseModel as PydanticBaseModel, UUID4, validator
from sqlalchemy import Column, DECIMAL, Index, Integer, String, TIMESTAMP
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
class BaseModel(PydanticBaseModel):
    class Config:
        json_encoders = {decimal.Decimal: str}


class ErrorDetails(BaseModel):
    detail: t.List[t.Dict[str, t.Any]]


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


class WalletDB(Wallet):
    id: t.Optional[UUID4]
    user_id: t.Optional[UUID4]
    name: t.Optional[str]
    balance: t.Optional[decimal.Decimal]


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
    balance: t.Optional[decimal.Decimal]


class WalletId(BaseModel):
    id: UUID4


class WalletListItem(BaseModel):
    id: UUID4
    name: str


class WalletList(BaseModel):
    wallets: t.List[WalletListItem]


class TransactionDB(BaseModel):
    id: t.Optional[int]
    sender_wallet_id: t.Optional[t.Union[UUID4, str]]
    recipient_wallet_id: t.Optional[UUID4]
    value: t.Optional[decimal.Decimal]
    timestamp: t.Optional[datetime.datetime]


if __name__ == '__main__':  # pragma: no cover
    engine = sqlalchemy.create_engine(config.POSTGRES_DSN)
    Base.metadata.create_all(engine)
