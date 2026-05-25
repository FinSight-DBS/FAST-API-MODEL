import logging
from typing import List, Tuple

import numpy as np
import pandas as pd

from src.ml.model_loader import get_autoencoder, get_autoencoder_meta
from src.domain.entity.report import DetectedAnomaly

logger = logging.getLogger(__name__)

MIN_Z = 3


def preprocess_for_autoencoder(df: pd.DataFrame, meta: dict) -> np.ndarray:
    ohe = meta["ohe"]
    scaler = meta["scaler"]
    kat_cap = meta["kat_cap"]
    z_stats = meta["z_stats"]
    FEAT = meta["feature_cols"]
    OHE_COLS = meta["ohe_cols"]

    df = df.copy()
    df = df.rename(
        columns={
            "sub_category": "kategori_detail",
            "customer_id": "id_user",
            "amount": "nominal",
        }
    )

    df["hour"] = pd.to_datetime(df["transaction_timestamp"]).dt.hour
    df["hour_sin"] = np.sin(2 * np.pi * df["hour"] / 24)
    df["hour_cos"] = np.cos(2 * np.pi * df["hour"] / 24)

    df["nominal"] = df["nominal"].clip(upper=df["kategori_detail"].map(kat_cap))
    df["nominal"] = np.log1p(df["nominal"])

    df[OHE_COLS] = ohe.transform(df[["kategori_detail"]])

    tmp = df[["id_user", "kategori_detail", "nominal"]].merge(
        z_stats, on=["id_user", "kategori_detail"], how="left"
    )
    valid = tmp["z_count"].ge(MIN_Z) & tmp["z_mean"].notna()
    df["nominal_z_user_kat"] = np.where(
        valid,
        (tmp["nominal"] - tmp["z_mean"]) / (tmp["z_std"].fillna(0) + 1e-9),
        0.0,
    )

    scaled = scaler.transform(df[FEAT])
    for i, col in enumerate(FEAT):
        df[f"{col}_scaled"] = scaled[:, i]

    df["nominal_z_user_kat_scaled"] = df["nominal_z_user_kat_scaled"].clip(-5, 5)

    SCALED_COLS = [f"{c}_scaled" for c in FEAT]
    return df[SCALED_COLS].values.astype(np.float32)


def detect_anomalies(
    df: pd.DataFrame,
    X_scaled: np.ndarray,
    model_meta: dict,
    df_baseline: pd.DataFrame,
    weekly_report_id: str,
) -> Tuple[pd.DataFrame, List[DetectedAnomaly]]:
    try:
        autoencoder = get_autoencoder()
    except Exception as e:
        logger.warning(f"Autoencoder not available: {e}")
        df["is_anomaly"] = 0
        return df, []

    threshold_uk = model_meta["threshold_user_kat"]
    threshold_kat = model_meta["threshold_kat"]

    X_rec = autoencoder.predict(X_scaled, verbose=0)
    mae = np.abs(X_scaled - X_rec).mean(axis=1)

    df = df.copy()
    df["mae"] = mae

    _median_thr = float(np.median(list(threshold_uk.values())))
    df["threshold"] = df.apply(
        lambda r: threshold_uk.get(
            (r["customer_id"], r["sub_category"]),
            threshold_kat.get(r["sub_category"], _median_thr),
        ),
        axis=1,
    )

    user_cat_mean = (
        df_baseline.groupby(["customer_id", "sub_category"])["amount"]
        .mean()
        .rename("mean_amount")
        .reset_index()
    )
    cat_mean = df_baseline.groupby("sub_category")["amount"].mean().to_dict()

    df = df.merge(user_cat_mean, on=["customer_id", "sub_category"], how="left")
    df["mean_amount"] = df["mean_amount"].fillna(df["sub_category"].map(cat_mean))

    df["is_anomaly"] = (
        (df["mae"] > df["threshold"]) & (df["amount"] > df["mean_amount"])
    ).astype(int)

    anomaly_rows = df[df["is_anomaly"] == 1]
    anomalies = []
    for _, row in anomaly_rows.iterrows():
        context = _build_anomaly_context(row, df_baseline)
        anomalies.append(
            DetectedAnomaly(
                transaction_id=str(row["id"]),
                customer_id=str(row["customer_id"]),
                weekly_report_id=weekly_report_id,
                sub_category=str(row["sub_category"]),
                amount=int(row["amount"]),
                mae=float(row["mae"]),
                threshold_val=float(row["threshold"]),
                ratio=float(row["mae"] / (row["threshold"] + 1e-9)),
                anomaly_context=context,
            )
        )

    return df, anomalies


def _build_anomaly_context(row: pd.Series, df_baseline: pd.DataFrame) -> str:
    z_lookup = (
        df_baseline.groupby(["customer_id", "sub_category"])["amount"].mean().to_dict()
    )
    customer_id = str(row["customer_id"])
    sub_category = str(row["sub_category"])
    amount = float(row["amount"])
    timestamp = pd.Timestamp(row["transaction_timestamp"])
    mae = float(row.get("mae", 0))
    threshold = float(row.get("threshold", 0))
    z_score = float(row.get("amount_z_customer_kat", 0))

    hour = timestamp.hour

    def describe_hour(h: int) -> str:
        if h < 6:
            return f"dini hari ({h:02d}:xx)"
        if h < 12:
            return f"pagi ({h:02d}:xx)"
        if h < 15:
            return f"siang ({h:02d}:xx)"
        if h < 19:
            return f"sore ({h:02d}:xx)"
        return f"malam ({h:02d}:xx)"

    parts = []
    baseline = z_lookup.get((customer_id, sub_category))
    if baseline and baseline > 0:
        ratio = amount / baseline
        parts.append(
            f"Nominal Rp {amount:,.0f} ({ratio:.1f}x rata-rata historis "
            f"user di {sub_category}: Rp {baseline:,.0f})"
        )
    if abs(z_score) >= 2.0:
        lbl = "sangat tinggi" if z_score > 0 else "sangat rendah"
        parts.append(
            f"Z-score {z_score:+.2f} — nominal {lbl} dibanding pola historis user ini"
        )

    parts.append(
        f"Waktu transaksi {describe_hour(hour)} — jam yang tidak lazim untuk {sub_category}"
    )

    seen: set = set()
    unique = []
    for p in parts:
        if p not in seen:
            seen.add(p)
            unique.append(p)
    return " | ".join(unique)
