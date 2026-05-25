from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class Customer:
    id: str
    full_name: str
    base_persona: Optional[str] = None
    monthly_income: float = 0.0
    savings_goal: float = 0.0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
