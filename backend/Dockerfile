# ========= 基础镜像 =========
FROM python:3.11-slim AS base

# 设置环境变量
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    POETRY_VERSION=2.2.1 \
    POETRY_VIRTUALENVS_CREATE=false

WORKDIR /app

# ========= 安装依赖 =========
FROM base AS builder

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 安装 Poetry
RUN pip install "poetry==$POETRY_VERSION"

# 拷贝依赖文件
COPY pyproject.toml poetry.lock* ./

# 安装依赖（不安装 dev-dependencies，生产模式更轻量）
RUN poetry install --no-root --only main

# ========= 运行镜像 =========
FROM base AS runtime

# 安装运行时依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# 拷贝 Poetry 环境
COPY --from=builder /usr/local /usr/local

# 拷贝项目
COPY . .

# 默认端口
EXPOSE 8000

# ========= 启动命令 =========
# 开发模式：支持热重载
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# 如果生产部署，改成下面这个（多 worker + 高并发）
# CMD ["gunicorn", "-k", "uvicorn.workers.UvicornWorker", "app.main:app", "--bind", "0.0.0.0:8000", "--workers", "4"]

