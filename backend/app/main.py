# backend/app/main.py
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import api_router
from app.core.database import init_db

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)

app = FastAPI(
    title="GoMuseum API",
    description="Backend API service for GoMuseum project - Artwork Recognition",
    version="0.1.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

# 允许跨域（前端访问）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 可以改成前端的实际域名
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
def health_check():
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
