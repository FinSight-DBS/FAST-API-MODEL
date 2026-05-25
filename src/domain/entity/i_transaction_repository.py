from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date
from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    from src.domain.entity.transaction import Transaction


class ITransactionRepository(ABC):
    @abstractmethod
    async def find_debit_last_7_days(
        self, user_ids: List[str], reference_date: date
    ) -> List["Transaction"]: ...

    @abstractmethod
    async def find_debit_in_month(
        self, user_ids: List[str], month_start: date, month_end: date
    ) -> List["Transaction"]: ...

    @abstractmethod
    async def find_all_for_baseline(
        self, user_ids: List[str], lookback_days: int = 90
    ) -> List["Transaction"]: ...

    @abstractmethod
    async def find_active_user_ids(self) -> List[str]: ...
