from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator
from typing import List, Optional
import os
import secrets

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)
    
    # Application
    app_name: str = "GoMuseum API"
    app_version: str = "1.0.0"
    environment: str = "development"
    debug: bool = True
    
    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    allowed_hosts: List[str] = Field(
        default_factory=lambda: 
        ["localhost", "127.0.0.1"] if os.getenv("ENVIRONMENT", "development") == "development"
        else os.getenv("ALLOWED_HOSTS", "").split(",") if os.getenv("ALLOWED_HOSTS") 
        else ["localhost"]
    )
    
    # Security
    secret_key: str = Field(default_factory=lambda: os.getenv("SECRET_KEY", secrets.token_urlsafe(32)))
    access_token_expire_minutes: int = 60 * 24 * 7  # 7 days
    
    @field_validator('secret_key')
    @classmethod 
    def validate_secret_key(cls, v):
        if not v or len(v) < 32:
            raise ValueError("SECRET_KEY must be at least 32 characters long")
        return v
    
    # Database
    database_url: str = Field(default="sqlite:///./gomuseum.db")  # Use SQLite by default for development
    database_echo: bool = False
    
    # Redis Cache
    redis_url: str = "redis://localhost:6379"
    cache_ttl: int = 3600  # 1 hour
    
    # AI Services
    openai_api_key: str = ""
    openai_model: str = "gpt-4-vision-preview"
    openai_temperature: float = 0.3
    openai_max_tokens: int = 500
    
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-3-vision-20240229"
    
    # Business Logic
    free_quota_limit: int = 5
    max_image_size: int = 10 * 1024 * 1024  # 10MB
    max_image_resolution: int = 2048  # pixels
    recognition_timeout: int = 30  # seconds
    
    # Cache Settings
    local_cache_size_mb: int = 200
    cache_expiry_hours: int = 24
    max_cache_items: int = 1000
    
    # Image Processing
    image_quality: int = 85
    thumbnail_size: int = 300
    
    # Monitoring
    enable_metrics: bool = True
    log_level: str = "INFO"
    
    @property
    def database_url_sync(self) -> str:
        """Synchronous database URL for Alembic"""
        return self.database_url.replace("postgresql://", "postgresql+psycopg2://")
    
    @property
    def is_production(self) -> bool:
        return self.environment == "production"
    
    @property
    def is_development(self) -> bool:
        return self.environment == "development"

# Create global settings instance
settings = Settings()