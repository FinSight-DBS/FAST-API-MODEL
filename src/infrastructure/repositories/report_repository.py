import uuid
from typing import List, Optional
from sqlalchemy import select, delete
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from src.domain.entity.report import WeeklyReport, MonthlyReport, DetectedAnomaly
from src.domain.entity.i_report_repository import IReportRepository
from src.infrastructure.tables.weekly_report_table import WeeklyReportTable
from src.infrastructure.tables.monthly_report_table import MonthlyReportTable
from src.infrastructure.tables.detected_anomaly_table import DetectedAnomalyTable


class ReportRepository(IReportRepository):
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def upsert_weekly_report(self, report: WeeklyReport) -> str:
        report_id = report.id or str(uuid.uuid4())
        stmt = pg_insert(WeeklyReportTable).values(
            id=report_id,
            customer_id=report.customer_id,
            report_date=report.report_date,
            period_start=report.period_start,
            persona=report.persona,
            wants_ratio=report.wants_ratio,
            needs_ratio=report.needs_ratio,
            total_expenses=report.total_expenses,
            anomaly_count=report.anomaly_count,
            report_text=report.report_text,
        ).on_conflict_do_update(
            constraint="uq_weekly_customer_date",
            set_={
                "persona": report.persona,
                "wants_ratio": report.wants_ratio,
                "needs_ratio": report.needs_ratio,
                "total_expenses": report.total_expenses,
                "anomaly_count": report.anomaly_count,
                "report_text": report.report_text,
                "generated_at": "NOW()",
            },
        ).returning(WeeklyReportTable.id)
        result = await self.db.execute(stmt)
        await self.db.commit()
        return result.scalar_one()

    async def upsert_monthly_report(self, report: MonthlyReport) -> str:
        report_id = report.id or str(uuid.uuid4())
        stmt = pg_insert(MonthlyReportTable).values(
            id=report_id,
            customer_id=report.customer_id,
            target_month=report.target_month,
            persona=report.persona,
            prev_persona=report.prev_persona,
            savings_rate=report.savings_rate,
            wants_ratio=report.wants_ratio,
            needs_ratio=report.needs_ratio,
            wants_amount=report.wants_amount,
            needs_amount=report.needs_amount,
            savings_amount=report.savings_amount,
            behavioral_features=report.behavioral_features,
            report_text=report.report_text,
        ).on_conflict_do_update(
            constraint="uq_monthly_customer_month",
            set_={
                "persona": report.persona,
                "prev_persona": report.prev_persona,
                "savings_rate": report.savings_rate,
                "wants_ratio": report.wants_ratio,
                "needs_ratio": report.needs_ratio,
                "wants_amount": report.wants_amount,
                "needs_amount": report.needs_amount,
                "savings_amount": report.savings_amount,
                "behavioral_features": report.behavioral_features,
                "report_text": report.report_text,
                "generated_at": "NOW()",
            },
        ).returning(MonthlyReportTable.id)
        result = await self.db.execute(stmt)
        await self.db.commit()
        return result.scalar_one()

    async def save_anomalies(self, anomalies: List[DetectedAnomaly]) -> None:
        if not anomalies:
            return
        rows = [
            DetectedAnomalyTable(
                id=str(uuid.uuid4()),
                transaction_id=a.transaction_id,
                customer_id=a.customer_id,
                weekly_report_id=a.weekly_report_id,
                sub_category=a.sub_category,
                amount=a.amount,
                mae=a.mae,
                threshold_val=a.threshold_val,
                ratio=a.ratio,
                anomaly_context=a.anomaly_context,
            )
            for a in anomalies
        ]
        self.db.add_all(rows)
        await self.db.commit()

    async def get_latest_monthly_persona(self, customer_id: str) -> Optional[str]:
        result = await self.db.execute(
            select(MonthlyReportTable.persona)
            .where(MonthlyReportTable.customer_id == customer_id)
            .order_by(MonthlyReportTable.target_month.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()
