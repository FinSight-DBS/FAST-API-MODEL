import uuid
from datetime import date, datetime
from typing import Optional

from sqlalchemy import String, Boolean, Numeric, DateTime, Date, func
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
    date_of_birth: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    mothers_maiden_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    demographic_segment: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    monthly_income: Mapped[float] = mapped_column(
        Numeric(15, 2), nullable=True, default=0
    )
    savings_goal: Mapped[float] = mapped_column(
        Numeric(15, 2), nullable=True, default=0
    )
    base_persona: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    is_dynamic: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    current_wants_ratio: Mapped[float] = mapped_column(
        Numeric(5, 4), nullable=True, default=0
    )
    current_needs_ratio: Mapped[float] = mapped_column(
        Numeric(5, 4), nullable=True, default=0
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    def to_domain(self) -> Customer:
        return Customer(
            id=self.id,
            full_name=self.full_name,
            date_of_birth=self.date_of_birth,
            mothers_maiden_name=self.mothers_maiden_name,
            demographic_segment=self.demographic_segment,
            monthly_income=float(self.monthly_income or 0),
            savings_goal=float(self.savings_goal or 0),
            base_persona=self.base_persona,
            is_dynamic=self.is_dynamic,
            current_wants_ratio=float(self.current_wants_ratio or 0),
            current_needs_ratio=float(self.current_needs_ratio or 0),
            created_at=self.created_at,
            updated_at=self.updated_at,
        )
