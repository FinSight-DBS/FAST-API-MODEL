from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class CustomerRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def update_base_persona(self, customer_id: str, persona: str) -> None:
        await self.db.execute(
            text("UPDATE customer SET base_persona = :persona WHERE id = :customer_id"),
            {"persona": persona, "customer_id": customer_id},
        )
        await self.db.commit()
