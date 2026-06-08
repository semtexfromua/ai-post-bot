from fastapi import APIRouter

from app.api.v1.routers import keywords, posts, sources

api_v1_router = APIRouter()
api_v1_router.include_router(sources.router)
api_v1_router.include_router(keywords.router)
api_v1_router.include_router(posts.router)
