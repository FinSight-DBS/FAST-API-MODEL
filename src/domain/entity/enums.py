from enum import Enum


class AccountStatusEnum(str, Enum):
    ACTIVE = "active"
    CLOSED = "closed"


class CredentialStatusEnum(str, Enum):
    ACTIVE = "active"
    LOCKED = "locked"
    SUSPENDED = "suspended"


class MainCategoryEnum(str, Enum):
    WANTS = "wants"
    NEEDS = "needs"
    SAVINGS = "savings"


class PersonaEnum(str, Enum):
    TIGHTWAD = "Tightwad"
    UNCONFLICTED = "Unconflicted"
    SPENDTHRIFT = "Spendthrift"


class TransactionTypeEnum(str, Enum):
    DEBIT = "debit"
    CREDIT = "credit"
