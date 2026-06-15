# backend/app/main.py
import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.api.v1 import api_router
from app.core.config import settings
from app.core.database import init_db
from app.core.rate_limit import limiter

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)

# 默认 SECRET_KEY 仅限开发；生产启动直接拒绝
_DEFAULT_SECRET = "gomuseum-jwt-secret-key-change-in-production-2024"
if settings.ENVIRONMENT == "production":
    if settings.SECRET_KEY == _DEFAULT_SECRET or len(settings.SECRET_KEY) < 32:
        raise RuntimeError(
            "Production requires a strong SECRET_KEY (>=32 chars, non-default). "
            "Generate one with: openssl rand -hex 48"
        )
    if settings.ALLOWED_ORIGINS.strip() == "*":
        raise RuntimeError(
            "Production requires explicit ALLOWED_ORIGINS (comma-separated domains)"
        )
    if settings.DEBUG:
        raise RuntimeError("DEBUG must be disabled in production")

app = FastAPI(
    title="GoMuseum API",
    description="Backend API service for GoMuseum project - Artwork Recognition",
    version="0.1.0",
    docs_url="/api/docs" if settings.ENVIRONMENT != "production" else None,
    redoc_url="/api/redoc" if settings.ENVIRONMENT != "production" else None,
    openapi_url="/api/openapi.json" if settings.ENVIRONMENT != "production" else None,
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS：开发放开，生产白名单
_origins = (
    ["*"]
    if settings.ALLOWED_ORIGINS.strip() == "*"
    else [o.strip() for o in settings.ALLOWED_ORIGINS.split(",") if o.strip()]
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API v1 router
app.include_router(api_router, prefix="/api/v1")


@app.on_event("startup")
async def startup_event():
    """Initialize database on startup"""
    logger.info("Starting up GoMuseum API...")
    try:
        init_db()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database: {str(e)}")


@app.get("/")
def root():
    """Root endpoint"""
    return {
        "message": "Welcome to GoMuseum API",
        "docs": "/api/docs",
        "version": "0.1.0",
    }


@app.get("/api/health/")
def health_check(request: Request):
    """健康检查端点，用于docker-compose验收脚本"""
    return {"status": "ok"}


@app.get("/api/info/")
def project_info():
    """项目信息端点"""
    return {
        "project": "GoMuseum",
        "version": "0.1.0",
        "description": "An AI-powered museum guide platform.",
        "features": ["artwork_recognition", "ai_powered", "caching"],
    }
