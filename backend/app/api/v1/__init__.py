"""API v1 initialization"""

from fastapi import APIRouter
from app.api.v1.endpoints import recognition

api_router = APIRouter()

# Include recognition endpoints
api_router.include_router(
    recognition.router, prefix="/recognition", tags=["recognition"]
)

__all__ = ["api_router"]
