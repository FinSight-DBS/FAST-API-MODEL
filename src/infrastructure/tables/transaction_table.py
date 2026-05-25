from datetime import datetime
from typing import Optional
from sqlalchemy import String, BigInteger, Integer, DateTime, func
from sqlalchemy.dialects.postgresql import UUID, ENUM
from sqlalchemy.orm import Mapped, mapped_column
from src.core.db import Base
from src.domain.entity.enums import MainCategoryEnum, TransactionTypeEnum
from src.domain.entity.transaction import Transaction
import uuid

_trx_type_enum = ENUM(
    "debit",
    "credit",
    name="transactions_transaction_type_enum",
    create_type=False,
)
_main_category_enum = ENUM(
    "wants",
    "needs",
    "savings",
    name="transactions_main_category_enum",
    create_type=False,
)


class TransactionTable(Base):
    __tablename__ = "transactions"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    customer_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), nullable=False, index=True
    )
    account_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False), nullable=True
    )
    transaction_type: Mapped[str] = mapped_column(_trx_type_enum, nullable=False)
    main_category: Mapped[Optional[str]] = mapped_column(
        _main_category_enum, nullable=True
    )
    sub_category: Mapped[str] = mapped_column(String(50), nullable=False)
    amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    running_balance: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    description: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    notes: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    transaction_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    day_of_week: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    day_of_month: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    hour: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    def to_domain(self) -> Transaction:
        return Transaction(
            id=self.id,
            customer_id=self.customer_id,
            account_id=self.account_id,
            transaction_type=TransactionTypeEnum(self.transaction_type),
            main_category=MainCategoryEnum(self.main_category)
            if self.main_category
            else None,
            sub_category=self.sub_category,
            amount=self.amount,
            running_balance=self.running_balance,
            description=self.description,
            notes=self.notes,
            transaction_timestamp=self.transaction_timestamp,
            day_of_week=self.day_of_week,
            day_of_month=self.day_of_month,
            hour=self.hour,
        )

    @classmethod
    def from_domain(cls, t: Transaction) -> "TransactionTable":
        return cls(
            id=t.id,
            customer_id=t.customer_id,
            account_id=t.account_id,
            transaction_type=t.transaction_type,
            main_category=t.main_category,
            sub_category=t.sub_category,
            amount=t.amount,
            running_balance=t.running_balance,
            description=t.description,
            notes=t.notes,
            transaction_timestamp=t.transaction_timestamp,
            day_of_week=t.day_of_week,
            day_of_month=t.day_of_month,
            hour=t.hour,
        )
