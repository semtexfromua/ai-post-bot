from fastapi import FastAPI

from app.api.health import router as health_router
from app.api.v1.router import api_v1_router
from app.core.logging import configure_logging

configure_logging()

app = FastAPI(title="M4 AI Telegram Bot")
app.include_router(health_router)
app.include_router(api_v1_router, prefix="/api/v1")
