"""Pytest 全局配置：测试环境关闭速率限制"""

import os

os.environ.setdefault("RATE_LIMIT_ENABLED", "0")
