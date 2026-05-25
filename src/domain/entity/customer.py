from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional


@dataclass
class Customer:
    id: str
    full_name: str
    date_of_birth: Optional[date] = None
    mothers_maiden_name: Optional[str] = None
    demographic_segment: Optional[str] = None
    monthly_income: float = 0.0
    savings_goal: float = 0.0
    base_persona: Optional[str] = None
    is_dynamic: bool = False
    current_wants_ratio: float = 0.0
    current_needs_ratio: float = 0.0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
