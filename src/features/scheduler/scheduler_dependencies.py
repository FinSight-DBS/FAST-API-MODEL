from fastapi import Header, HTTPException

from src.core.config import settings
from src.features.scheduler.usecase.run_monthly_usecase import RunMonthlyUseCase
from src.features.scheduler.usecase.run_weekly_usecase import RunWeeklyUseCase


def verify_internal_key(x_internal_key: str = Header(...)) -> None:
    if x_internal_key != settings.INTERNAL_API_KEY:
        raise HTTPException(status_code=403, detail="Forbidden")


def get_run_weekly_use_case() -> RunWeeklyUseCase:
    return RunWeeklyUseCase()


def get_run_monthly_use_case() -> RunMonthlyUseCase:
    return RunMonthlyUseCase()
