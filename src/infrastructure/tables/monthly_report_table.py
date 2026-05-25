import uuid
from datetime import datetime
from sqlalchemy import String, BigInteger, Text, DateTime, func, Numeric, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column
from src.core.db import Base
from src.domain.entity.report import MonthlyReport


class MonthlyReportTable(Base):
    __tablename__ = "monthly_reports"
    __table_args__ = (UniqueConstraint("customer_id", "target_month", name="uq_monthly_customer_month"),)

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    customer_id: Mapped[str] = mapped_column(UUID(as_uuid=False), nullable=False, index=True)
    target_month: Mapped[str] = mapped_column(String(7), nullable=False)
    persona: Mapped[str] = mapped_column(String(20), nullable=False)
    prev_persona: Mapped[str] = mapped_column(String(20), nullable=True)
    savings_rate: Mapped[float] = mapped_column(Numeric(6, 4), nullable=False)
    wants_ratio: Mapped[float] = mapped_column(Numeric(5, 4), nullable=False)
    needs_ratio: Mapped[float] = mapped_column(Numeric(5, 4), nullable=False)
    wants_amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    needs_amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    savings_amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    behavioral_features: Mapped[dict] = mapped_column(JSONB, nullable=True)
    report_text: Mapped[str] = mapped_column(Text, nullable=False)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def to_domain(self) -> MonthlyReport:
        return MonthlyReport(
            id=self.id,
            customer_id=self.customer_id,
            target_month=self.target_month,
            persona=self.persona,
            prev_persona=self.prev_persona,
            savings_rate=float(self.savings_rate),
            wants_ratio=float(self.wants_ratio),
            needs_ratio=float(self.needs_ratio),
            wants_amount=self.wants_amount,
            needs_amount=self.needs_amount,
            savings_amount=self.savings_amount,
            behavioral_features=self.behavioral_features or {},
            report_text=self.report_text,
            generated_at=self.generated_at,
        )

    @classmethod
    def from_domain(cls, r: MonthlyReport) -> "MonthlyReportTable":
        return cls(
            id=r.id,
            customer_id=r.customer_id,
            target_month=r.target_month,
            persona=r.persona,
            prev_persona=r.prev_persona,
            savings_rate=r.savings_rate,
            wants_ratio=r.wants_ratio,
            needs_ratio=r.needs_ratio,
            wants_amount=r.wants_amount,
            needs_amount=r.needs_amount,
            savings_amount=r.savings_amount,
            behavioral_features=r.behavioral_features,
            report_text=r.report_text,
        )
