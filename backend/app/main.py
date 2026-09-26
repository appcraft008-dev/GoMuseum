# backend/app/main.py
import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

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

# 音频损失闸在 web 进程里只记账不拦(契约纪律 37):用户请求不该因它报错,
# web 侧的损失照样进 audio_invalidations,由每日盘点兜。脚本进程默认拦截。
from app.services.audio_guard import set_record_only  # noqa: E402

set_record_only()

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

# 信任 nginx 转发的 X-Forwarded-For，让 slowapi 拿到真实访客 IP。
#
# 没有这段时，按 IP 限流**全站共享一个桶**：nginx 在宿主机 proxy_pass 到
# 127.0.0.1:8100，流量经 docker-proxy 进容器，uvicorn 看到的对端是网桥网关
# （prod 实测 172.22.0.1），不在它默认的 forwarded-allow-ips（仅 127.0.0.1）里，
# 于是 X-Forwarded-For 被丢弃。2026-09-18 实测 prod access log 全量 19997 条，
# 客户端 IP 只有 127.0.0.1（容器内健康检查）和 172.22.0.1（全部外部流量），
# 零个真实访客 IP —— guest_login 的 5/hour 等于「全站每小时 5 个新游客」。
# 零真实用户所以一直没炸，会正好在放量时显现。
#
# ⛔ **绝不能用 `"*"`**。uvicorn 0.37 的 _TrustedHosts：
#     if self.always_trust: return x_forwarded_for_hosts[0]   # 取最左端
# 而 nginx 用的是 `$proxy_add_x_forwarded_for`（追加语义）——攻击者发
# `X-Forwarded-For: 1.2.3.4`，nginx 转成 `1.2.3.4, <真实IP>`，取 [0] 就是伪造值，
# 每个请求换个假 IP 即可无限刷 register/guest_login。比现在的「全站一个桶」更糟。
# 指定网段才会走 `for host in reversed(...)` 那条分支：从右往左取第一个不可信的
# host = nginx 记下的真实 IP，左边伪造的那段被忽略。
TRUSTED_PROXY_HOSTS = ["127.0.0.1", "172.16.0.0/12"]
"""可信代理来源。`172.16.0.0/12` 覆盖 docker 全部网桥网段（默认 bridge 172.17/16、
compose 项目网络 172.18–172.31），网络重建换了网关 IP 也不用改。
配错的失效方向是安全的：回落到现状（全站一个桶），不会变成可伪造。"""

app.add_middleware(ProxyHeadersMiddleware, trusted_hosts=TRUSTED_PROXY_HOSTS)

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
    try:
        # 搜索索引预热(后台线程,不阻塞启动):构建随藏品量涨,prod 实测 24k 条目
        # 7.2s——不预热则进程内第一个搜索用户要等这 7 秒。
        from app.services.search.inprocess import warm_search_index

        warm_search_index()
        logger.info("Search index warm-up started")
    except Exception:
        logger.exception("Search index warm-up failed (will build on first query)")


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
