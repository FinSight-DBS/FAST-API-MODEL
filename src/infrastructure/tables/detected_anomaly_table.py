import uuid
from datetime import datetime
from sqlalchemy import String, BigInteger, Text, DateTime, func, Double
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from src.core.db import Base
from src.domain.entity.report import DetectedAnomaly


class DetectedAnomalyTable(Base):
    __tablename__ = "detected_anomalies"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    transaction_id: Mapped[str] = mapped_column(UUID(as_uuid=False), nullable=False)
    customer_id: Mapped[str] = mapped_column(UUID(as_uuid=False), nullable=False, index=True)
    weekly_report_id: Mapped[str] = mapped_column(UUID(as_uuid=False), nullable=False)
    sub_category: Mapped[str] = mapped_column(String(50), nullable=False)
    amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    mae: Mapped[float] = mapped_column(Double, nullable=False)
    threshold_val: Mapped[float] = mapped_column(Double, nullable=False)
    ratio: Mapped[float] = mapped_column(Double, nullable=False)
    anomaly_context: Mapped[str] = mapped_column(Text, nullable=True)
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def to_domain(self) -> DetectedAnomaly:
        return DetectedAnomaly(
            id=self.id,
            transaction_id=self.transaction_id,
            customer_id=self.customer_id,
            weekly_report_id=self.weekly_report_id,
            sub_category=self.sub_category,
            amount=self.amount,
            mae=self.mae,
            threshold_val=self.threshold_val,
            ratio=self.ratio,
            anomaly_context=self.anomaly_context,
            detected_at=self.detected_at,
        )

    @classmethod
    def from_domain(cls, a: DetectedAnomaly) -> "DetectedAnomalyTable":
        return cls(
            id=a.id or str(uuid.uuid4()),
            transaction_id=a.transaction_id,
            customer_id=a.customer_id,
            weekly_report_id=a.weekly_report_id,
            sub_category=a.sub_category,
            amount=a.amount,
            mae=a.mae,
            threshold_val=a.threshold_val,
            ratio=a.ratio,
            anomaly_context=a.anomaly_context,
        )
