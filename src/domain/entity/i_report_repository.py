from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, List, Optional

if TYPE_CHECKING:
    from src.domain.entity.report import DetectedAnomaly, MonthlyReport, WeeklyReport


class IReportRepository(ABC):
    @abstractmethod
    async def upsert_weekly_report(self, report: "WeeklyReport") -> str: ...

    @abstractmethod
    async def upsert_monthly_report(self, report: "MonthlyReport") -> str: ...

    @abstractmethod
    async def save_anomalies(self, anomalies: List["DetectedAnomaly"]) -> None: ...

    @abstractmethod
    async def get_latest_monthly_persona(self, user_id: str) -> Optional[str]: ...

    @abstractmethod
    async def find_weekly_report(
        self, customer_id: str, period_start, period_end
    ) -> Optional[str]: ...
