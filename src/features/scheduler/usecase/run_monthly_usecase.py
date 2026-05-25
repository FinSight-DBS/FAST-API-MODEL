import logging
import uuid
from calendar import monthrange
from dataclasses import dataclass, field
from datetime import date
from typing import List

import pandas as pd

from src.core.db import AsyncSessionLocal
from src.domain.entity.report import MonthlyReport
from src.infrastructure.repositories.customer_repository import CustomerRepository
from src.infrastructure.repositories.report_repository import ReportRepository
from src.infrastructure.repositories.transaction_repository import TransactionRepository
from src.ml.clustering_service import compute_monthly_features, predict_persona
from src.ml.nlp_service import classify_p2p_transactions, map_main_category
from src.ml.rag_service import build_monthly_context, call_llm

logger = logging.getLogger(__name__)
CHUNK_SIZE = 50


@dataclass
class RunMonthlyRequest:
    job_id: str
    target_month: str
    customer_ids: List[str] = field(default_factory=list)
    dry_run: bool = False


class RunMonthlyUseCase:
    async def execute(self, request: RunMonthlyRequest) -> None:
        job_id = request.job_id
        target_month_str = request.target_month
        logger.info(f"[{job_id}] Monthly pipeline started for {target_month_str}")

        year, month = map(int, target_month_str.split("-"))
        _, last_day = monthrange(year, month)
        month_start = date(year, month, 1)
        month_end = date(year, month, last_day) + pd.Timedelta(days=1).to_pytimedelta()

        async with AsyncSessionLocal() as db:
            trx_repo = TransactionRepository(db)
            report_repo = ReportRepository(db)
            customer_repo = CustomerRepository(db)

            customer_ids = (
                request.customer_ids or await trx_repo.find_active_customer_ids()
            )
            logger.info(
                f"[{job_id}] Processing {len(customer_ids)} customers for {target_month_str}"
            )

            for chunk_start in range(0, len(customer_ids), CHUNK_SIZE):
                chunk = customer_ids[chunk_start : chunk_start + CHUNK_SIZE]
                await self._process_chunk(
                    job_id,
                    chunk,
                    month_start,
                    month_end,
                    target_month_str,
                    trx_repo,
                    report_repo,
                    customer_repo,
                    request.dry_run,
                )

        logger.info(f"[{job_id}] Monthly pipeline completed")

    async def _process_chunk(
        self,
        job_id: str,
        customer_ids: List[str],
        month_start: date,
        month_end,
        target_month_str: str,
        trx_repo: TransactionRepository,
        report_repo: ReportRepository,
        customer_repo: CustomerRepository,
        dry_run: bool,
    ) -> None:
        transactions = await trx_repo.find_debit_in_month(
            customer_ids, month_start, month_end
        )
        if not transactions:
            logger.info(f"[{job_id}] No transactions for chunk")
            return

        df = pd.DataFrame([vars(t) for t in transactions])
        df_all = df.copy()

        df = classify_p2p_transactions(df)
        df = map_main_category(df)

        df_debit = df[df["transaction_type"] == "debit"].copy()

        for customer_id in customer_ids:
            customer_debit = df_debit[df_debit["customer_id"] == customer_id]
            customer_all = df_all[df_all["customer_id"] == customer_id]
            if customer_debit.empty:
                logger.warning(f"[{job_id}] No debit data for {customer_id}")
                continue
            try:
                await self._generate_report(
                    job_id,
                    customer_id,
                    customer_debit,
                    customer_all,
                    target_month_str,
                    report_repo,
                    customer_repo,
                    dry_run,
                )
            except Exception as e:
                logger.error(
                    f"[{job_id}] Failed for customer {customer_id}: {e}", exc_info=True
                )

    async def _generate_report(
        self,
        job_id: str,
        customer_id: str,
        customer_debit: pd.DataFrame,
        customer_all: pd.DataFrame,
        target_month_str: str,
        report_repo: ReportRepository,
        customer_repo: CustomerRepository,
        dry_run: bool,
    ) -> None:
        report_id = str(uuid.uuid4())
        prev_persona = await report_repo.get_latest_monthly_persona(customer_id)
        gaji = await customer_repo.get_monthly_income(customer_id)

        prev_month_balance = (
            float(customer_all["running_balance"].iloc[0])
            if not customer_all.empty
            else 0.0
        )
        saldo_akhir = (
            float(customer_all["running_balance"].iloc[-1])
            if not customer_all.empty
            else 0.0
        )

        features = compute_monthly_features(
            df_debit=customer_debit,
            df_all=customer_all,
            gaji=gaji,
            prev_month_balance=prev_month_balance,
        )
        persona_baru = predict_persona(features)

        total_pengeluaran = int(customer_debit["amount"].sum())
        wants_nom = int(
            customer_debit[customer_debit["main_category"] == "wants"]["amount"].sum()
        )
        needs_nom = int(
            customer_debit[customer_debit["main_category"] == "needs"]["amount"].sum()
        )
        consumable_total = wants_nom + needs_nom
        wants_ratio = wants_nom / consumable_total if consumable_total > 0 else 0.0
        needs_ratio = needs_nom / consumable_total if consumable_total > 0 else 0.0

        investasi_nom = int(
            customer_debit[customer_debit["sub_category"] == "Investasi & Finansial"][
                "amount"
            ].sum()
        )
        delta_saldo = saldo_akhir - prev_month_balance
        savings_amount = investasi_nom + max(int(delta_saldo), 0)
        savings_rate = features["savings_rate"]

        context = build_monthly_context(
            user_id=customer_id,
            user_name=customer_id,
            persona_baru=persona_baru,
            persona_lama=prev_persona,
            gaji=gaji,
            saldo_akhir=saldo_akhir,
            savings_rate=savings_rate,
            wants_ratio=wants_ratio,
            needs_ratio=needs_ratio,
            wants_amount=float(wants_nom),
            needs_amount=float(needs_nom),
            savings_amount=float(savings_amount),
            behavioral_features=features,
            target_month=target_month_str,
        )

        try:
            report_text = await call_llm(context, is_monthly=True)
        except Exception as e:
            logger.error(f"[{job_id}] LLM failed for {customer_id}: {e}")
            report_text = f"[LLM unavailable] {context}"

        report = MonthlyReport(
            id=report_id,
            customer_id=customer_id,
            target_month=target_month_str,
            persona=persona_baru,
            prev_persona=prev_persona,
            savings_rate=savings_rate,
            wants_ratio=wants_ratio,
            needs_ratio=needs_ratio,
            wants_amount=wants_nom,
            needs_amount=needs_nom,
            savings_amount=savings_amount,
            behavioral_features=features,
            report_text=report_text,
        )

        if not dry_run:
            saved_id = await report_repo.upsert_monthly_report(report)
            try:
                await customer_repo.update_base_persona(customer_id, persona_baru)
            except Exception as e:
                logger.warning(
                    f"[{job_id}] Failed to update persona for {customer_id}: {e}"
                )
            logger.info(
                f"[{job_id}] Saved monthly report {saved_id} for {customer_id}, persona={persona_baru}"
            )
        else:
            logger.info(f"[{job_id}] DRY RUN — skipping DB write for {customer_id}")
