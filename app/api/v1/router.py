from fastapi import APIRouter
from app.api.v1.chat import router as chat_router
from app.api.v1.approve import router as approve_router
from app.api.v1.health import router as health_router

api_router = APIRouter()

api_router.include_router(health_router, prefix="/health", tags=["Health"])
api_router.include_router(chat_router, tags=["Chat"])
api_router.include_router(approve_router, tags=["Approval"])
