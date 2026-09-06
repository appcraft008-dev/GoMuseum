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

    # Google Play Developer API 服务账号(校验购买收据)。可以是 JSON 文件路径,
    # 也可以是 JSON 字符串本身(容器里用环境变量注入更方便)。
    # ⚠️ **不配置就一律拒绝购买**,绝不回退到"当作有效"——此前 verify_google_receipt
    # 是 mock,对任何 purchase_token 都返回 valid=True,等于把 €7.99 白送。
    GOOGLE_PLAY_SERVICE_ACCOUNT: Optional[str] = None
    GOOGLE_PLAY_PACKAGE_NAME: str = "com.gomuseum.app"

    # ── Play RTDN(退款通知)入口鉴权 ─────────────────────────────────────
    # 首选 OIDC:Pub/Sub 用指定服务账号签一个 JWT 放进 `Authorization: Bearer`,
    # 我们验签 + 核对 audience 与签发者邮箱。
    # **这是唯一能让密钥离开 URL 的办法** —— Pub/Sub 推送发不了自定义 header,
    # 能带的只有它自己签的 OIDC 令牌。
    #
    # ⚠️ 为什么必须离开 query string:URL 会原样写进 nginx / uvicorn 的 access log,
    # 于是这把"能伪造退款通知的钥匙"以明文躺在日志、日志备份、以及任何看得到
    # 日志的人眼前,而且永不轮换。OIDC 令牌则是**每条消息现签、几分钟就过期**。
    PLAY_RTDN_AUDIENCE: Optional[str] = None  # 建推送订阅时填的 audience
    PLAY_RTDN_SERVICE_ACCOUNT_EMAIL: Optional[str] = None  # 该订阅的签发服务账号

    # 过渡期的老方案:URL 上的共享密钥(?token=...)。两者都没配则拒绝一切请求。
    #
    # ⚠️ 切换顺序**不能反**:先部署本次代码 → 再把 Pub/Sub 订阅改成 OIDC →
    # 确认真的收得到通知 → 最后才清空这个变量并轮换旧密钥。
    # 反过来(先清空再改订阅)= 这期间的退款通知全被 403 拒收,Pub/Sub 重试若干天
    # 后丢弃 —— 退款不撤权益,又变回持续漏钱。
    PLAY_RTDN_TOKEN: Optional[str] = None
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

    # ── 发信(找回密码 / 邮箱验证)────────────────────────────────────────
    # 用 SMTP 而不是某一家的 HTTP API:Resend / SendGrid / Mailgun / Postmark
    # 全都提供 SMTP,换服务商只改这几个变量 —— 零代码改动、零新依赖(stdlib smtplib)。
    #
    # ⚠️ **不配置就没有找回密码**(端点返 503),绝不"假装发出去了" ——
    # 那会让用户守着一封永远不来的邮件,而我们这侧一切正常。
    SMTP_HOST: Optional[str] = None
    SMTP_PORT: int = 587
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    SMTP_STARTTLS: bool = True  # 587 用 STARTTLS;465 请设 False(隐式 TLS)
    MAIL_FROM: str = "GoMuseum <noreply@gomuseum.app>"

    # 邮件里那条链接指向哪。**必须外网可达**;重置页由 API 自己吐(同源、免 CORS、
    # 免发网站,已装的老 App 也能用)。留空则回退到请求自身的 base_url。
    PUBLIC_API_BASE_URL: Optional[str] = None

    # 链接有效期。短到够用就行 —— 这封信是账号的**万能钥匙**。
    PASSWORD_RESET_TTL_MINUTES: int = 30
    EMAIL_VERIFY_TTL_MINUTES: int = 1440  # 24h,验证邮箱不急

    # AI Performance
    AI_STRATEGY_TIMEOUT: int = 30  # 增加到30秒，给AI足够时间响应
    AI_TOTAL_TIMEOUT: int = 60  # 总超时60秒
    ENABLE_CLAUDE_FALLBACK: bool = True

    # Image Processing
    # 免费层跨馆识别次数(单一真相源;此前散在模型 default / benefits_service /
    # entitlement_service 三处,改一处漏两处)。2026-07-28 由 10 收紧到 5:
    # 更早撞墙=用户还在馆里、还兴奋时看到付费页,转化时机更好。边际成本近零,
    # 5 和 10 都便宜,真正差别只在转化 → 上线后看 ops_report 的
    # "额度耗尽→付费页→购买" 转化率再调。⚠️ 改这里只影响**新用户**
    # (quota 是每行剩余数),不回收老用户额度。
    FREE_RECOGNITION_QUOTA: int = 5

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
