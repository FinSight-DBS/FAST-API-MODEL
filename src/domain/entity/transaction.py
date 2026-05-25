from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class Transaction:
    id: str
    customer_id: str
    transaction_type: str
    sub_category: str
    amount: int
    transaction_timestamp: datetime
    running_balance: int = 0
    description: str = ""
    notes: str = ""
    day_of_week: int = 0
    day_of_month: int = 0
    hour: int = 0
    main_category: Optional[str] = None
    account_id: Optional[str] = None
