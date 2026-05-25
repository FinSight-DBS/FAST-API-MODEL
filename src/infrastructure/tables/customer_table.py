import uuid
from datetime import datetime

from sqlalchemy import String, Boolean, Numeric, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.core.db import Base
from src.domain.entity.customer import Customer


class CustomerTable(Base):
    __tablename__ = "customer"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    full_name: Mapped[str] = mapped_column(String, nullable=False)
    base_persona: Mapped[str] = mapped_column(String(20), nullable=True)
    monthly_income: Mapped[float] = mapped_column(Numeric(15, 2), nullable=True, default=0)
    savings_goal: Mapped[float] = mapped_column(Numeric(15, 2), nullable=True, default=0)
    is_dynamic: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    def to_domain(self) -> Customer:
        return Customer(
            id=self.id,
            full_name=self.full_name,
            base_persona=self.base_persona,
            monthly_income=float(self.monthly_income or 0),
            savings_goal=float(self.savings_goal or 0),
            created_at=self.created_at,
            updated_at=self.updated_at,
        )
