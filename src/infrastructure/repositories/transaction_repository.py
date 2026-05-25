from datetime import date, timedelta
from typing import List
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from src.domain.entity.transaction import Transaction
from src.domain.entity.i_transaction_repository import ITransactionRepository
from src.infrastructure.tables.transaction_table import TransactionTable


class TransactionRepository(ITransactionRepository):
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def find_debit_last_7_days(
        self, customer_ids: List[str], reference_date: date
    ) -> List[Transaction]:
        cutoff = reference_date - timedelta(days=7)
        result = await self.db.execute(
            select(TransactionTable).where(
                and_(
                    TransactionTable.transaction_type == "debit",
                    TransactionTable.transaction_timestamp >= cutoff,
                    TransactionTable.transaction_timestamp <= reference_date,
                    TransactionTable.customer_id.in_(customer_ids),
                )
            )
        )
        return [row.to_domain() for row in result.scalars().all()]

    async def find_debit_in_month(
        self, customer_ids: List[str], month_start: date, month_end: date
    ) -> List[Transaction]:
        result = await self.db.execute(
            select(TransactionTable).where(
                and_(
                    TransactionTable.transaction_timestamp >= month_start,
                    TransactionTable.transaction_timestamp < month_end,
                    TransactionTable.customer_id.in_(customer_ids),
                )
            )
        )
        return [row.to_domain() for row in result.scalars().all()]

    async def find_all_for_baseline(
        self, customer_ids: List[str], lookback_days: int = 90
    ) -> List[Transaction]:
        from datetime import datetime

        cutoff = datetime.utcnow().date() - timedelta(days=lookback_days)
        result = await self.db.execute(
            select(TransactionTable).where(
                and_(
                    TransactionTable.transaction_type == "debit",
                    TransactionTable.transaction_timestamp >= cutoff,
                    TransactionTable.customer_id.in_(customer_ids),
                )
            )
        )
        return [row.to_domain() for row in result.scalars().all()]

    async def find_active_user_ids(self) -> List[str]:
        result = await self.db.execute(select(TransactionTable.customer_id).distinct())
        return list(result.scalars().all())

    async def find_active_customer_ids(self) -> List[str]:
        return await self.find_active_user_ids()
