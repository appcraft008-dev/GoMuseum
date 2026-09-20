"""OpenAI 客户端工厂。

⚠️ 模块名是历史遗留 —— 它原本还装着 `ContentGenerationService`(给已退役的
`POST /content/explanation` 生成讲解用)。那个端点在 2026-09-20 安全审计里下线后
整个类连同 `PROMPT_TEMPLATES`、单例工厂一并删除(约 310 行),只剩下面这个客户端工厂 ——
它被 `enrichment/vision.py`、`enrichment/content_enricher.py`、
`recognition/vision.py` 三处共用,是真正还活着的那部分。

没有改模块名:三处调用点 + 六处测试 patch 路径都写着这个名字,改名是与本次
安全修复无关的动线扰动。
"""

import logging
import threading

from app.core.config import settings

logger = logging.getLogger(__name__)

# Lazy import OpenAI。client 按线程本地缓存:httpx 连接池不跨线程安全——
# 并发生成线程(lazy _SEM=2、qa‖翻译)共享单例会撞池报 APIConnectionError(staging 实证);
# 线程内顺序复用(每调用 asyncio.run 换 loop)已被 prod 大量调用证明可行。
_openai_tl = threading.local()


def _get_openai_client():
    """Lazy load OpenAI client(每线程一个实例)"""
    if getattr(_openai_tl, "client", None) is None:
        try:
            from openai import AsyncOpenAI

            _openai_tl.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
            logger.info("OpenAI client initialized for content generation")
        except ImportError:
            logger.warning("openai package not installed")
            _openai_tl.client = None
        except Exception as e:
            logger.error(f"Failed to initialize OpenAI client: {e}")
            _openai_tl.client = None
    return _openai_tl.client
