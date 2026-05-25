import re
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


class MonthlySchedulerRequest(BaseModel):
    customer_ids: List[str] = Field(default=[])
    target_month: Optional[str] = Field(
        default=None, description="Format YYYY-MM. Default: bulan lalu"
    )
    dry_run: bool = Field(default=False)

    @field_validator("target_month")
    @classmethod
    def validate_target_month(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not re.match(r"^\d{4}-\d{2}$", v):
            raise ValueError("target_month harus format YYYY-MM, contoh: 2025-04")
        return v


class MonthlyJobResponse(BaseModel):
    job_id: str
    status: str
    customer_count: int
    target_month: str
    message: str


class BehavioralFeatures(BaseModel):
    wants_ratio: float
    fixed_costs_ratio: float
    savings_rate: float
    wants_frequency: float
    small_leaks_ratio: float
    night_owl_spending: float
    weekend_surge: float
    early_month_depletion: float
    balance_volatility: float
    survival_mode_days: int


class MonthlyReportResult(BaseModel):
    customer_id: str
    target_month: str
    persona: str
    prev_persona: Optional[str]
    savings_rate: float
    wants_ratio: float
    needs_ratio: float
    behavioral_features: BehavioralFeatures
    report_text: str
    generated_at: str
