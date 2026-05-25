from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from src.domain.entity.enums import AccountStatusEnum


@dataclass
class Account:
    id: str
    customer_id: str
    account_number: str
    status: AccountStatusEnum
    balance: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
