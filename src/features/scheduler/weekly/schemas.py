from datetime import date
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator


class WeeklySchedulerRequest(BaseModel):
    customer_ids: List[str] = Field(default=[], description="Kosong = semua customer aktif")
    reference_date: Optional[date] = Field(default=None)
    dry_run: bool = Field(default=False)

    @field_validator("customer_ids")
    @classmethod
    def limit_batch_size(cls, v: List[str]) -> List[str]:
        if len(v) > 500:
            raise ValueError("customer_ids maksimal 500. Untuk semua customer, kirim list kosong []")
        return v


class WeeklyJobResponse(BaseModel):
    job_id: str
    status: str
    customer_count: int
    message: str


class AnomalyItem(BaseModel):
    transaction_id: str
    customer_id: str
    timestamp: str
    sub_category: str
    amount: float
    mae: float
    threshold: float
    ratio: float
    context: str


class WeeklyReportResult(BaseModel):
    customer_id: str
    period_start: date
    report_date: date
    wants_ratio: float
    needs_ratio: float
    total_expenses: float
    anomaly_count: int
    anomaly_list: List[AnomalyItem]
    report_text: str
    persona: str
    generated_at: str
