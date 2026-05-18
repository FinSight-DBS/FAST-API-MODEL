"""
Main FastAPI application entry point for FinSight.

Auth routes from the original template have been removed.
NestJS owns authentication; this service is an internal AI orchestration layer.
"""

from fastapi import FastAPI

from src.core.error_handler import add_global_exception_handlers

app = FastAPI(title="FinSight FastAPI", version="1.0.0")
add_global_exception_handlers(app)

# Feature routers are registered here as they are implemented.
# Example: app.include_router(scheduler_router)
