from fastapi import APIRouter

from app.api.v1.routers import sources

api_v1_router = APIRouter()
api_v1_router.include_router(sources.router)
