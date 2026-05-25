import uuid
from datetime import date, datetime
from sqlalchemy import String, Date, BigInteger, Integer, Text, DateTime, func, Numeric, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from src.core.db import Base
from src.domain.entity.report import WeeklyReport


class WeeklyReportTable(Base):
    __tablename__ = "weekly_reports"
    __table_args__ = (UniqueConstraint("customer_id", "report_date", name="uq_weekly_customer_date"),)

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    customer_id: Mapped[str] = mapped_column(UUID(as_uuid=False), nullable=False, index=True)
    report_date: Mapped[date] = mapped_column(Date, nullable=False)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    persona: Mapped[str] = mapped_column(String(50), nullable=False)
    wants_ratio: Mapped[float] = mapped_column(Numeric(5, 4), nullable=False)
    needs_ratio: Mapped[float] = mapped_column(Numeric(5, 4), nullable=False)
    total_expenses: Mapped[int] = mapped_column(BigInteger, nullable=False)
    anomaly_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    report_text: Mapped[str] = mapped_column(Text, nullable=False)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def to_domain(self) -> WeeklyReport:
        return WeeklyReport(
            id=self.id,
            customer_id=self.customer_id,
            report_date=self.report_date,
            period_start=self.period_start,
            persona=self.persona,
            wants_ratio=float(self.wants_ratio),
            needs_ratio=float(self.needs_ratio),
            total_expenses=self.total_expenses,
            anomaly_count=self.anomaly_count,
            report_text=self.report_text,
            generated_at=self.generated_at,
        )

    @classmethod
    def from_domain(cls, r: WeeklyReport) -> "WeeklyReportTable":
        return cls(
            id=r.id,
            customer_id=r.customer_id,
            report_date=r.report_date,
            period_start=r.period_start,
            persona=r.persona,
            wants_ratio=r.wants_ratio,
            needs_ratio=r.needs_ratio,
            total_expenses=r.total_expenses,
            anomaly_count=r.anomaly_count,
            report_text=r.report_text,
        )
