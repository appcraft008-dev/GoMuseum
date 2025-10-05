"""
Configuration module for GoMuseum backend
Loads environment variables and provides application settings
"""

from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""

    # Application
    APP_NAME: str = "GoMuseum API"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False

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
            return self.DATABASE_URL.replace('postgresql+asyncpg://', 'postgresql://')
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
    ANTHROPIC_MODEL: str = "claude-3-5-sonnet-20241022"  # 正确的模型名
    ANTHROPIC_TIMEOUT: int = 30

    # AI Performance
    AI_STRATEGY_TIMEOUT: int = 30  # 增加到30秒，给AI足够时间响应
    AI_TOTAL_TIMEOUT: int = 60  # 总超时60秒
    ENABLE_CLAUDE_FALLBACK: bool = True

    # Image Processing
    MAX_IMAGE_SIZE_MB: int = 10
    ALLOWED_IMAGE_FORMATS: list = ["JPEG", "PNG"]
    IMAGE_COMPRESSION_QUALITY: int = 85
    MAX_IMAGE_WIDTH: int = 1024

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
