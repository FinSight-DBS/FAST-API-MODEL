import logging
import uuid
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import List, Optional

import pandas as pd

from src.core.db import AsyncSessionLocal
from src.domain.entity.report import WeeklyReport
from src.infrastructure.repositories.report_repository import ReportRepository
from src.infrastructure.repositories.transaction_repository import TransactionRepository
from src.ml.autoencoder_service import detect_anomalies, preprocess_for_autoencoder
from src.ml.model_loader import get_autoencoder_meta
from src.ml.nlp_service import classify_p2p_transactions, map_main_category
from src.ml.rag_service import build_weekly_context, call_llm

logger = logging.getLogger(__name__)

CHUNK_SIZE = 50


@dataclass
class RunWeeklyRequest:
    job_id: str
    customer_ids: List[str] = field(default_factory=list)
    reference_date: Optional[date] = None
    dry_run: bool = False


class RunWeeklyUseCase:
    async def execute(self, request: RunWeeklyRequest) -> None:
        job_id = request.job_id
        logger.info(f"[{job_id}] Weekly pipeline started")
        reference_date = request.reference_date or date.today()
        period_end = reference_date
        period_start = reference_date - timedelta(days=7)

        async with AsyncSessionLocal() as db:
            trx_repo = TransactionRepository(db)
            report_repo = ReportRepository(db)

            customer_ids = request.customer_ids or await trx_repo.find_active_customer_ids()
            logger.info(f"[{job_id}] Processing {len(customer_ids)} customers")

            for chunk_start in range(0, len(customer_ids), CHUNK_SIZE):
                chunk = customer_ids[chunk_start: chunk_start + CHUNK_SIZE]
                await self._process_chunk(
                    job_id, chunk, period_start, period_end, trx_repo, report_repo, request.dry_run
                )

        logger.info(f"[{job_id}] Weekly pipeline completed")

    async def _process_chunk(
        self,
        job_id: str,
        customer_ids: List[str],
        period_start: date,
        period_end: date,
        trx_repo: TransactionRepository,
        report_repo: ReportRepository,
        dry_run: bool,
    ) -> None:
        transactions = await trx_repo.find_debit_last_7_days(customer_ids, period_end)
        if not transactions:
            logger.info(f"[{job_id}] No transactions for chunk {customer_ids[:3]}...")
            return

        df = pd.DataFrame([vars(t) for t in transactions])
        baseline_txns = await trx_repo.find_all_for_baseline(customer_ids)
        df_baseline = pd.DataFrame([vars(t) for t in baseline_txns]) if baseline_txns else df.copy()

        df = classify_p2p_transactions(df)
        df = map_main_category(df)

        try:
            preprocessing_meta, model_meta = get_autoencoder_meta()
            X_scaled = preprocess_for_autoencoder(df, preprocessing_meta)
            has_ae = True
        except Exception as e:
            logger.warning(f"[{job_id}] AE preprocessing failed: {e}")
            has_ae = False
            model_meta = None
            X_scaled = None

        for customer_id in customer_ids:
            customer_df = df[df["customer_id"] == customer_id]
            if customer_df.empty:
                logger.warning(f"[{job_id}] No data for customer {customer_id}, skipping")
                continue
            try:
                await self._generate_report(
                    job_id, customer_id, customer_df,
                    df if has_ae else None,
                    None if not has_ae else X_scaled[df["customer_id"] == customer_id],
                    model_meta,
                    df_baseline, period_start, period_end, report_repo, dry_run,
                )
            except Exception as e:
                logger.error(f"[{job_id}] Failed for customer {customer_id}: {e}", exc_info=True)

    async def _generate_report(
        self,
        job_id: str,
        customer_id: str,
        customer_df: pd.DataFrame,
        full_df,
        X_customer,
        model_meta,
        df_baseline: pd.DataFrame,
        period_start: date,
        period_end: date,
        report_repo: ReportRepository,
        dry_run: bool,
    ) -> None:
        report_id = str(uuid.uuid4())

        total_expenses = int(customer_df["amount"].sum())
        wants_nom = int(customer_df[customer_df["main_category"] == "wants"]["amount"].sum())
        needs_nom = int(customer_df[customer_df["main_category"] == "needs"]["amount"].sum())
        wants_ratio = wants_nom / total_expenses if total_expenses > 0 else 0.0
        needs_ratio = needs_nom / total_expenses if total_expenses > 0 else 0.0

        anomali_list = []
        if X_customer is not None and model_meta is not None:
            customer_full_df = full_df[full_df["customer_id"] == customer_id]
            customer_baseline = (
                df_baseline[df_baseline["customer_id"] == customer_id]
                if not df_baseline.empty
                else customer_full_df
            )
            _, anomalies = detect_anomalies(
                customer_full_df, X_customer, model_meta, customer_baseline, report_id
            )
            anomali_list = anomalies

        persona = await report_repo.get_latest_monthly_persona(customer_id) or "Unconflicted"
        saldo_terakhir = float(customer_df["running_balance"].iloc[-1]) if not customer_df.empty else 0.0

        top_anomalies = sorted(
            anomali_list, key=lambda a: a.mae / (a.threshold_val + 1e-9), reverse=True
        )[:3]

        context = build_weekly_context(
            user_id=customer_id,
            user_name=customer_id,
            persona=persona,
            gaji=0.0,
            saldo_terakhir=saldo_terakhir,
            wants_ratio=wants_ratio,
            needs_ratio=needs_ratio,
            wants_amount=float(wants_nom),
            needs_amount=float(needs_nom),
            total_pengeluaran=float(total_expenses),
            anomali_list=[
                {
                    "kategori": a.sub_category,
                    "nominal": a.amount,
                    "timestamp": str(a.detected_at or ""),
                    "context": a.anomaly_context,
                }
                for a in top_anomalies
            ],
            period_start=str(period_start),
            period_end=str(period_end),
        )

        try:
            report_text = await call_llm(context, is_monthly=False)
        except Exception as e:
            logger.error(f"[{job_id}] LLM call failed for {customer_id}: {e}")
            report_text = f"[LLM unavailable] {context}"

        report = WeeklyReport(
            id=report_id,
            customer_id=customer_id,
            report_date=period_end,
            period_start=period_start,
            persona=persona,
            wants_ratio=wants_ratio,
            needs_ratio=needs_ratio,
            total_expenses=total_expenses,
            anomaly_count=len(anomali_list),
            report_text=report_text,
        )

        if not dry_run:
            saved_id = await report_repo.upsert_weekly_report(report)
            if anomali_list:
                for a in anomali_list:
                    a.weekly_report_id = saved_id
                await report_repo.save_anomalies(anomali_list)
            logger.info(f"[{job_id}] Saved weekly report {saved_id} for {customer_id}")
        else:
            logger.info(f"[{job_id}] DRY RUN — skipping DB write for {customer_id}")
