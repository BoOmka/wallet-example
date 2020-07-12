import uuid

from fastapi_users.db import SQLAlchemyBaseUserTable
from fastapi_users.db.sqlalchemy import GUID
from sqlalchemy import Column, String, DECIMAL, Integer, TIMESTAMP, Index
from sqlalchemy.ext.declarative import DeclarativeMeta, declarative_base


Base: DeclarativeMeta = declarative_base()


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


users = UserTable.__table__
wallets = WalletTable.__table__
transactions = TransactionTable.__table__
