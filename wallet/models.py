import datetime
import decimal
import typing as t

from fastapi_users import models
from pydantic import BaseModel as PydanticBaseModel, UUID4, validator


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
