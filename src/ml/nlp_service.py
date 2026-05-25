import re
import logging
from typing import List
import pandas as pd

from src.ml.model_loader import get_nlp_pipeline

logger = logging.getLogger(__name__)

P2P_CATEGORY = "Transfer P2P"

CATEGORY_MAP = {
    "Transportasi": "needs",
    "Tagihan & Utilitas": "needs",
    "Kesehatan & Perawatan Diri": "needs",
    "Groceries & Kebutuhan Pokok": "needs",
    "Belanja Online & Fashion": "wants",
    "Produktivitas & Digital": "wants",
    "F&B dan Nongkrong": "wants",
    "Hiburan & Langganan": "wants",
    "Transfer P2P": "wants",
    "Investasi & Finansial": "savings",
    "Pendapatan Bulanan": None,
    "Pemasukan Tambahan": None,
}


def _clean(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def classify_p2p_transactions(df: pd.DataFrame) -> pd.DataFrame:
    mask = df["sub_category"] == P2P_CATEGORY
    if not mask.any():
        return df

    try:
        vectorizer, model = get_nlp_pipeline()
    except Exception as e:
        logger.warning(f"NLP model not available, skipping P2P reclassification: {e}")
        return df

    p2p_rows = df[mask].copy()
    texts = (
        (p2p_rows["description"].fillna("") + " " + p2p_rows["notes"].fillna(""))
        .apply(_clean)
        .tolist()
    )

    vecs = vectorizer.transform(texts)
    predictions = model.predict(vecs)

    df = df.copy()
    df.loc[mask, "sub_category"] = predictions
    return df


def map_main_category(df: pd.DataFrame) -> pd.DataFrame:
    """Map sub_category to main_category (needs/wants/savings/None)."""
    df = df.copy()
    df["main_category"] = df["sub_category"].map(CATEGORY_MAP)
    return df
