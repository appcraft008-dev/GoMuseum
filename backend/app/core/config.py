"""
Configuration module for GoMuseum backend
Loads environment variables and provides application settings
"""

from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""

    # Application
    APP_NAME: str = "GoMuseum API"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False
    ENVIRONMENT: str = "development"  # development / staging / production
    ALLOWED_ORIGINS: str = "*"  # 逗号分隔的 CORS 白名单，生产必须配置具体域名

    # 内容缓存与 AI 成本控制
    TTS_CACHE_DIR: str = "./tts_cache"
    EXPLANATION_CACHE_TTL_DAYS: int = 30
    OPENAI_DAILY_CALL_LIMIT: int = 2000

    # Security (JWT)
    SECRET_KEY: str = "gomuseum-jwt-secret-key-change-in-production-2024"

    # Database
    DATABASE_URL: Optional[str] = None
    POSTGRES_USER: str = "gomuseum"
    POSTGRES_PASSWORD: str = "gomuseum123"
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "gomuseum_db"

    def get_database_url(self) -> str:
        """Get database URL, prefer DATABASE_URL env var, fallback to constructed URL"""
        if self.DATABASE_URL:
            # Convert asyncpg URL to sync psycopg2 URL
            return self.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
        return (
            f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    # Redis
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: Optional[str] = None

    # OpenAI
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o"
    OPENAI_TIMEOUT: int = 30

    # Anthropic Claude (fallback)
    ANTHROPIC_API_KEY: Optional[str] = None
    ANTHROPIC_MODEL: str = (
        "claude-sonnet-4-6"  # 在线视觉模型（旧的 3-5-sonnet-20241022 已 404 下线）
    )
    ANTHROPIC_TIMEOUT: int = 30

    # OAuth providers
    GOOGLE_CLIENT_ID: Optional[str] = None
    APPLE_CLIENT_ID: Optional[str] = None
    APPLE_TEAM_ID: Optional[str] = None
    APPLE_KEY_ID: Optional[str] = None
    APPLE_PRIVATE_KEY_PATH: Optional[str] = None

    # Object storage (images / audio)
    STORAGE_BACKEND: str = "local"  # "local" | "r2"
    STORAGE_LOCAL_DIR: str = "var/assets"  # local 实现落盘目录
    STORAGE_PUBLIC_BASE_URL: str = (
        "http://localhost:8000/assets"  # local public_url 前缀
    )
    R2_ENDPOINT_URL: str = ""
    R2_ACCESS_KEY_ID: str = ""
    R2_SECRET_ACCESS_KEY: str = ""
    R2_BUCKET: str = "gomuseum-assets"
    R2_PUBLIC_BASE_URL: str = ""

    # AI Performance
    AI_STRATEGY_TIMEOUT: int = 30  # 增加到30秒，给AI足够时间响应
    AI_TOTAL_TIMEOUT: int = 60  # 总超时60秒
    ENABLE_CLAUDE_FALLBACK: bool = True

    # Image Processing
    MAX_IMAGE_SIZE_MB: int = 10
    ALLOWED_IMAGE_FORMATS: list = ["JPEG", "PNG"]
    IMAGE_COMPRESSION_QUALITY: int = 85
    MAX_IMAGE_WIDTH: int = 1024

    # Recognition (向量引擎)
    RECOG_HIGH: float = 0.85
    RECOG_LOW: float = 0.72
    RECOG_MODEL_KEY: str = "models/dinov2_vits14.onnx"
    RECOG_MODEL_SHA256: str = ""
    RECOG_MODEL_CACHE: str = "/tmp/gomuseum_models"

    # Cache
    CACHE_TTL_SECONDS: int = 86400  # 24 hours

    # Performance
    REQUEST_TIMEOUT_SECONDS: int = 5

    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()


# Global settings instance
settings = get_settings()
