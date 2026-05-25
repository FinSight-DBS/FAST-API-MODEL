from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional

from src.domain.entity.enums import PersonaEnum


@dataclass
class WeeklyReport:
    customer_id: str
    report_date: date
    period_start: date
    persona: str
    wants_ratio: float
    needs_ratio: float
    total_expenses: int
    anomaly_count: int
    report_text: str
    id: Optional[str] = None
    generated_at: Optional[datetime] = None


@dataclass
class MonthlyReport:
    customer_id: str
    target_month: str
    persona: PersonaEnum
    prev_persona: Optional[PersonaEnum]
    savings_rate: float
    wants_ratio: float
    needs_ratio: float
    wants_amount: int
    needs_amount: int
    savings_amount: int
    behavioral_features: dict
    report_text: str
    id: Optional[str] = None
    generated_at: Optional[datetime] = None


@dataclass
class DetectedAnomaly:
    transaction_id: str
    customer_id: str
    weekly_report_id: str
    sub_category: str
    amount: int
    mae: float
    threshold_val: float
    ratio: float
    anomaly_context: str
    id: Optional[str] = None
    detected_at: Optional[datetime] = None
