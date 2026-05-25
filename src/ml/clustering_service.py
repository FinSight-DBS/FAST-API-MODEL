import logging
from typing import Optional

import numpy as np
import pandas as pd

from src.ml.model_loader import get_clustering_pipeline

logger = logging.getLogger(__name__)

COLS_TO_LOG = [
    "wants_frequency",
    "weekend_surge",
    "balance_volatility",
    "survival_mode_days",
]


def compute_monthly_features(
    df_debit: pd.DataFrame,
    df_all: pd.DataFrame,
    gaji: float,
    prev_month_balance: float,
) -> dict:
    total_pengeluaran = df_debit["amount"].sum()
    total_trx = max(len(df_debit), 1)

    wants_nom = df_debit[df_debit["main_category"] == "wants"]["amount"].sum()
    needs_nom = df_debit[df_debit["main_category"] == "needs"]["amount"].sum()

    wants_ratio = wants_nom / total_pengeluaran if total_pengeluaran > 0 else 0
    fixed_costs_ratio = needs_nom / total_pengeluaran if total_pengeluaran > 0 else 0

    investasi_nom = df_debit[df_debit["sub_category"] == "Investasi & Finansial"][
        "amount"
    ].sum()
    saldo_akhir = (
        df_all["running_balance"].iloc[-1] if len(df_all) else prev_month_balance
    )
    delta_saldo = saldo_akhir - prev_month_balance
    savings_rate = (investasi_nom + delta_saldo) / gaji if gaji > 0 else 0

    wants_count = df_debit[df_debit["main_category"] == "wants"].shape[0]
    wants_frequency = wants_count / total_trx

    small_leaks_ratio = df_debit[df_debit["amount"] < 30_000].shape[0] / total_trx

    if "hour" in df_debit.columns:
        night_trx = df_debit[(df_debit["hour"] >= 22) | (df_debit["hour"] <= 4)].shape[
            0
        ]
    else:
        night_trx = 0
    night_owl_spending = night_trx / total_trx

    if "day_of_week" in df_debit.columns:
        weekend_data = df_debit[df_debit["day_of_week"] >= 5]
        weekday_data = df_debit[df_debit["day_of_week"] < 5]
        avg_wknd = weekend_data["amount"].mean() if not weekend_data.empty else 0
        avg_wkdy = weekday_data["amount"].mean() if not weekday_data.empty else 0
        weekend_surge = (
            avg_wknd / avg_wkdy if avg_wkdy > 0 else (1 if avg_wknd > 0 else 0)
        )
    else:
        weekend_surge = 1.0

    if "day_of_month" in df_debit.columns:
        early_nom = df_debit[df_debit["day_of_month"] <= 5]["amount"].sum()
    else:
        early_nom = 0
    early_month_depletion = early_nom / gaji if gaji > 0 else 0

    if len(df_all) > 1:
        daily_bal = df_all.groupby(
            pd.to_datetime(df_all["transaction_timestamp"]).dt.date
        )["running_balance"].last()
        balance_volatility = daily_bal.std() / gaji if gaji > 0 else 0
        survival_mode_days = int((daily_bal < 0.15 * gaji).sum())
    else:
        balance_volatility = 0
        survival_mode_days = 0

    return {
        "wants_ratio": float(wants_ratio),
        "fixed_costs_ratio": float(fixed_costs_ratio),
        "savings_rate": float(savings_rate),
        "wants_frequency": float(wants_frequency),
        "small_leaks_ratio": float(small_leaks_ratio),
        "night_owl_spending": float(night_owl_spending),
        "weekend_surge": float(weekend_surge),
        "early_month_depletion": float(early_month_depletion),
        "balance_volatility": float(balance_volatility),
        "survival_mode_days": int(survival_mode_days),
    }


ALL_FEATURES = [
    "wants_ratio",
    "fixed_costs_ratio",
    "savings_rate",
    "wants_frequency",
    "small_leaks_ratio",
    "night_owl_spending",
    "weekend_surge",
    "early_month_depletion",
    "balance_volatility",
    "survival_mode_days",
]


def predict_persona(features: dict) -> str:
    try:
        scaler, umap_model, kmeans, label_map = get_clustering_pipeline()
    except Exception as e:
        logger.warning(f"Clustering model unavailable, defaulting to Unconflicted: {e}")
        return "Unconflicted"

    try:
        feats = features.copy()
        for col in COLS_TO_LOG:
            feats[col] = np.log1p(feats[col])

        arr = np.array([[feats[c] for c in ALL_FEATURES]])
        arr_scaled = scaler.transform(arr)
        arr_umap = umap_model.transform(arr_scaled)
        cluster_id = int(kmeans.predict(arr_umap)[0])
        return label_map[cluster_id]
    except Exception as e:
        logger.warning(f"Persona prediction failed: {e}")
        return "Unconflicted"
