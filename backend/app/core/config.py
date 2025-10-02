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
    POSTGRES_USER: str = "gomuseum"
    POSTGRES_PASSWORD: str = "gomuseum123"
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "gomuseum_db"

    @property
    def DATABASE_URL(self) -> str:
        """Construct database URL from components"""
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
    ANTHROPIC_MODEL: str = "claude-3-5-sonnet-20241022"
    ANTHROPIC_TIMEOUT: int = 2

    # AI Performance
    AI_STRATEGY_TIMEOUT: int = 3
    AI_TOTAL_TIMEOUT: int = 5
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
