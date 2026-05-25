"""
FastAPI application entry point for FinSight AI orchestration layer.
NestJS owns authentication; this service is internal only.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.core.error_handler import add_global_exception_handlers
from src.features.scheduler.scheduler_controller import scheduler_router
from src.features.user.user_controller import user_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("FinSight FastAPI starting — preloading ML models...")
    from src.ml.model_loader import preload_all_models
    preload_all_models()
    logger.info("ML models preloaded.")
    yield
    logger.info("FinSight FastAPI shutting down.")


app = FastAPI(title="FinSight FastAPI", version="1.0.0", lifespan=lifespan)
add_global_exception_handlers(app)

app.include_router(scheduler_router)
app.include_router(user_router)
