"""API v1 initialization"""

from fastapi import APIRouter

from app.api.v1.endpoints import (
    auth,
    chat,
    content,
    history,
    museums,
    payment,
    recognition,
    recognize_global,
    search,
)

api_router = APIRouter()

# Include authentication endpoints (OAuth/login)
api_router.include_router(auth.router, tags=["authentication"])

# Include recognition endpoints
api_router.include_router(
    recognition.router, prefix="/recognition", tags=["recognition"]
)

# Include content endpoints (AI explanation + TTS)
api_router.include_router(content.router, prefix="/content", tags=["content"])

# Include chat endpoints (Voice Q&A)
api_router.include_router(chat.router, prefix="/chat", tags=["chat"])

# Include history endpoints
api_router.include_router(history.router, prefix="/history", tags=["history"])

# Include payment endpoints (IAP verification & benefits)
api_router.include_router(payment.router, prefix="/payment", tags=["payment"])

# Include museum pack endpoints (馆藏目录/讲解，第1步数据地基)
api_router.include_router(museums.router, prefix="/museums", tags=["museums"])

# Include global recognition endpoint (POST /recognize, museum 可选跨馆识别)
api_router.include_router(recognize_global.router, tags=["recognition"])

# Include search endpoints (全局 /search + 馆域 /museums/{slug}/search;加法契约)
api_router.include_router(search.router, tags=["search"])

__all__ = ["api_router"]
