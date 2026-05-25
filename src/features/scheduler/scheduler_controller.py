import uuid
from datetime import date

from fastapi import APIRouter, BackgroundTasks, Depends

from src.features.scheduler.monthly.schemas import MonthlyJobResponse, MonthlySchedulerRequest
from src.features.scheduler.scheduler_dependencies import (
    get_run_monthly_use_case,
    get_run_weekly_use_case,
    verify_internal_key,
)
from src.features.scheduler.usecase.run_monthly_usecase import RunMonthlyRequest, RunMonthlyUseCase
from src.features.scheduler.usecase.run_weekly_usecase import RunWeeklyRequest, RunWeeklyUseCase
from src.features.scheduler.weekly.schemas import WeeklyJobResponse, WeeklySchedulerRequest

scheduler_router = APIRouter(prefix="/scheduler", tags=["scheduler"])


@scheduler_router.post("/weekly", response_model=WeeklyJobResponse, status_code=202)
async def trigger_weekly(
    req: WeeklySchedulerRequest,
    background_tasks: BackgroundTasks,
    _: None = Depends(verify_internal_key),
    use_case: RunWeeklyUseCase = Depends(get_run_weekly_use_case),
):
    job_id = f"weekly-{date.today()}-{uuid.uuid4().hex[:6]}"
    request = RunWeeklyRequest(
        job_id=job_id,
        customer_ids=req.customer_ids,
        reference_date=req.reference_date,
        dry_run=req.dry_run,
    )
    background_tasks.add_task(use_case.execute, request)
    return WeeklyJobResponse(
        job_id=job_id,
        status="queued",
        customer_count=len(req.customer_ids),
        message="Weekly scheduler job queued successfully",
    )


@scheduler_router.post("/monthly", response_model=MonthlyJobResponse, status_code=202)
async def trigger_monthly(
    req: MonthlySchedulerRequest,
    background_tasks: BackgroundTasks,
    _: None = Depends(verify_internal_key),
    use_case: RunMonthlyUseCase = Depends(get_run_monthly_use_case),
):
    if req.target_month:
        target_month_str = req.target_month
    else:
        today = date.today()
        if today.month == 1:
            year, month = today.year - 1, 12
        else:
            year, month = today.year, today.month - 1
        target_month_str = f"{year:04d}-{month:02d}"

    job_id = f"monthly-{target_month_str}-{uuid.uuid4().hex[:6]}"
    request = RunMonthlyRequest(
        job_id=job_id,
        customer_ids=req.customer_ids,
        target_month=target_month_str,
        dry_run=req.dry_run,
    )
    background_tasks.add_task(use_case.execute, request)
    return MonthlyJobResponse(
        job_id=job_id,
        status="queued",
        customer_count=len(req.customer_ids),
        target_month=target_month_str,
        message="Monthly scheduler job queued successfully",
    )


@scheduler_router.get("/health")
async def health():
    from src.ml.model_loader import get_autoencoder, get_clustering_pipeline, get_nlp_pipeline

    status: dict = {"status": "ok", "models": {}}
    for name, loader in [
        ("nlp", get_nlp_pipeline),
        ("autoencoder", get_autoencoder),
        ("clustering", get_clustering_pipeline),
    ]:
        try:
            loader()
            status["models"][name] = "loaded"
        except Exception as e:
            status["models"][name] = f"error: {str(e)[:60]}"
    return status
