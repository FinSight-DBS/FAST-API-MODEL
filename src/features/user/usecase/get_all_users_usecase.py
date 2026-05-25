from dataclasses import dataclass, field
from typing import List

from src.domain.entity.customer import Customer
from src.infrastructure.repositories.customer_repository import CustomerRepository
from src.infrastructure.tables.customer_table import CustomerTable
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


@dataclass
class GetAllUsersRequest:
    pass


@dataclass
class GetAllUsersResult:
    users: List[Customer] = field(default_factory=list)


class GetAllUsersUseCase:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def execute(self, request: GetAllUsersRequest) -> GetAllUsersResult:
        result = await self.db.execute(select(CustomerTable))
        customers = [row.to_domain() for row in result.scalars().all()]
        return GetAllUsersResult(users=customers)
