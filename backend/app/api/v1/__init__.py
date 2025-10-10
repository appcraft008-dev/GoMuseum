"""API v1 initialization"""

from fastapi import APIRouter
from app.api.v1.endpoints import recognition, content, chat, history, payment

api_router = APIRouter()

# Include recognition endpoints
api_router.include_router(
    recognition.router, prefix="/recognition", tags=["recognition"]
)

# Include content endpoints (AI explanation + TTS)
api_router.include_router(
    content.router, prefix="/content", tags=["content"]
)

# Include chat endpoints (Voice Q&A)
api_router.include_router(
    chat.router, prefix="/chat", tags=["chat"]
)

# Include history endpoints
api_router.include_router(
    history.router, prefix="/history", tags=["history"]
)

# Include payment endpoints (IAP verification & benefits)
api_router.include_router(
    payment.router, prefix="/payment", tags=["payment"]
)

__all__ = ["api_router"]
