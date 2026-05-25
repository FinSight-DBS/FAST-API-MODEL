import json
import logging
import pickle
from functools import lru_cache

import joblib
import tensorflow as tf

from src.core.config import settings

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_nlp_pipeline():
    logger.info("Loading NLP pipeline...")
    with open(settings.NLP_TOKENIZER_PATH, "rb") as f:
        vectorizer = pickle.load(f)
    with open(settings.NLP_MODEL_PATH, "rb") as f:
        model = pickle.load(f)
    logger.info("NLP pipeline loaded.")
    return vectorizer, model


@lru_cache(maxsize=1)
def get_autoencoder():
    logger.info("Loading autoencoder model...")
    model = tf.keras.models.load_model(settings.AUTOENCODER_MODEL_PATH, compile=False)
    logger.info("Autoencoder loaded.")
    return model


@lru_cache(maxsize=1)
def get_autoencoder_meta():
    base = settings.AUTOENCODER_MODEL_PATH.rsplit("/", 1)[0]
    logger.info(f"Loading autoencoder meta from {base}...")
    preprocessing_meta = joblib.load(f"{base}/preprocessing_meta.pkl")
    model_meta = joblib.load(f"{base}/model_meta.pkl")
    return preprocessing_meta, model_meta


@lru_cache(maxsize=1)
def get_clustering_pipeline():
    base = settings.KMEANS_MODEL_PATH.rsplit("/", 1)[0]
    logger.info(f"Loading clustering pipeline from {base}...")
    scaler = joblib.load(f"{base}/scaler_all.pkl")
    umap_model = joblib.load(f"{base}/umap_all.pkl")
    kmeans = joblib.load(settings.KMEANS_MODEL_PATH)
    with open(settings.KMEANS_LABEL_MAP_PATH) as f:
        label_map = json.load(f)
    return scaler, umap_model, kmeans, {int(k): v for k, v in label_map.items()}


def preload_all_models():
    """Call at startup to warm up all models into memory."""
    try:
        get_nlp_pipeline()
    except Exception as e:
        logger.error(f"Failed to load NLP pipeline: {e}")
    try:
        get_autoencoder()
        get_autoencoder_meta()
    except Exception as e:
        logger.error(f"Failed to load autoencoder: {e}")
    try:
        get_clustering_pipeline()
    except Exception as e:
        logger.error(f"Failed to load clustering pipeline: {e}")
