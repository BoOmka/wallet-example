from enum import Enum


class TransferSide(str, Enum):
    deposit = 'deposit'
    withdraw = 'withdraw'
