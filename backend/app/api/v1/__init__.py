"""API v1 initialization"""

from fastapi import APIRouter
from app.api.v1.endpoints import recognition, explanation

api_router = APIRouter()

# Include recognition endpoints
api_router.include_router(
    recognition.router, prefix="/recognition", tags=["recognition"]
)

# Include explanation endpoints (Step 2)
api_router.include_router(
    explanation.router, prefix="/explanation", tags=["explanation"]
)

__all__ = ["api_router"]
