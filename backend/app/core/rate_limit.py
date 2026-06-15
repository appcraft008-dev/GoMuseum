"""全局速率限制器（slowapi，按客户端 IP）

测试/本地可通过环境变量 RATE_LIMIT_ENABLED=0 关闭。
"""

import os

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(
    key_func=get_remote_address,
    enabled=os.getenv("RATE_LIMIT_ENABLED", "1") != "0",
)
