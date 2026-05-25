from typing import Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class CustomerRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_monthly_income(self, customer_id: str) -> float:
        result = await self.db.execute(
            text("SELECT monthly_income FROM customer WHERE id = :customer_id"),
            {"customer_id": customer_id},
        )
        row = result.fetchone()
        if row and row[0] is not None:
            return float(row[0])
        return 0.0

    async def update_base_persona(self, customer_id: str, persona: str) -> None:
        await self.db.execute(
            text("UPDATE customer SET base_persona = :persona WHERE id = :customer_id"),
            {"persona": persona, "customer_id": customer_id},
        )
        await self.db.commit()
