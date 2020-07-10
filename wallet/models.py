import datetime
import decimal

import sqlalchemy
from fastapi_users import models
from fastapi_users.db import SQLAlchemyBaseUserTable
from fastapi_users.db.sqlalchemy import GUID
from pydantic import BaseModel, UUID4
from sqlalchemy import Column, DECIMAL, Integer, String, TIMESTAMP
from sqlalchemy.ext.declarative import DeclarativeMeta, declarative_base

import config


Base: DeclarativeMeta = declarative_base()


# Declarative tables
class UserTable(Base, SQLAlchemyBaseUserTable):
    pass


class WalletTable(Base):
    __tablename__ = 'wallet'

    id = Column(GUID, primary_key=True)
    user_id = Column(GUID)
    name = Column(String)
    balance = Column(DECIMAL)


class TransactionTable(Base):
    __tablename__ = 'transaction'
    id = Column(Integer, primary_key=True)
    sender_wallet_id = Column(GUID)
    recipient_wallet_id = Column(GUID)
    value = Column(DECIMAL)
    timestamp = Column(TIMESTAMP)


# Table instances
users = UserTable.__table__
wallets = WalletTable.__table__
transactions = TransactionTable.__table__


# Pydantic models
class User(models.BaseUser):
    pass


class UserCreate(models.BaseUserCreate):
    pass


class UserUpdate(User, models.BaseUserUpdate):
    pass


class UserDB(User, models.BaseUserDB):
    pass


class Wallet(BaseModel):
    id: int
    user_id: UUID4
    name: str
    balance: decimal.Decimal


class Transaction(BaseModel):
    id: int
    sender_wallet_id: int
    recipient_wallet_id: int
    value: decimal.Decimal
    timestamp: datetime.datetime


if __name__ == '__main__':
    engine = sqlalchemy.create_engine(config.POSTGRES_DSN, )
    Base.metadata.create_all(engine)
