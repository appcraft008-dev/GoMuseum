#!/bin/bash

# GoMuseum系统健康检查脚本
# 用途：在启动应用前检查系统时间、Docker状态等关键配置

set -e

echo "========================================="
echo "  GoMuseum 系统健康检查"
echo "========================================="
echo ""

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

ERRORS=0
WARNINGS=0

# 1. 检查系统时间
echo "📅 检查系统时间..."
CURRENT_YEAR=$(date +%Y)
CURRENT_DATE=$(date +"%Y-%m-%d %H:%M:%S")

echo "   当前时间: $CURRENT_DATE"

if [ "$CURRENT_YEAR" -gt 2025 ]; then
    echo -e "${RED}❌ 错误: 系统时间异常！当前年份是 $CURRENT_YEAR${NC}"
    echo "   这可能是系统时间设置错误，请检查系统时间设置"
    echo "   修复方法: 系统偏好设置 → 日期与时间 → 设置正确日期"
    ERRORS=$((ERRORS + 1))
elif [ "$CURRENT_YEAR" -lt 2024 ]; then
    echo -e "${YELLOW}⚠️  警告: 系统时间可能过旧，当前年份是 $CURRENT_YEAR${NC}"
    WARNINGS=$((WARNINGS + 1))
else
    echo -e "${GREEN}✅ 系统时间正常${NC}"
fi

echo ""

# 2. 检查Docker是否运行
echo "🐳 检查Docker状态..."
if command -v docker &> /dev/null; then
    if docker info &> /dev/null; then
        echo -e "${GREEN}✅ Docker正在运行${NC}"

        # 检查Docker时间同步
        HOST_TIMESTAMP=$(date +%s)
        DOCKER_TIMESTAMP=$(docker run --rm alpine date +%s 2>/dev/null || echo "0")

        if [ "$DOCKER_TIMESTAMP" != "0" ]; then
            TIME_DIFF=$((HOST_TIMESTAMP - DOCKER_TIMESTAMP))
            TIME_DIFF_ABS=${TIME_DIFF#-}  # 绝对值

            echo "   宿主机时间戳: $HOST_TIMESTAMP"
            echo "   Docker时间戳:  $DOCKER_TIMESTAMP"
            echo "   时间差: ${TIME_DIFF}秒"

            if [ $TIME_DIFF_ABS -gt 60 ]; then
                echo -e "${YELLOW}⚠️  警告: Docker容器时间与宿主机相差 ${TIME_DIFF}秒${NC}"
                echo "   建议重启Docker Desktop以同步时间"
                WARNINGS=$((WARNINGS + 1))
            else
                echo -e "${GREEN}✅ Docker时间同步正常${NC}"
            fi
        fi
    else
        echo -e "${RED}❌ 错误: Docker未运行${NC}"
        echo "   请启动Docker Desktop"
        ERRORS=$((ERRORS + 1))
    fi
else
    echo -e "${RED}❌ 错误: Docker未安装${NC}"
    ERRORS=$((ERRORS + 1))
fi

echo ""

# 3. 检查必需的环境变量
echo "🔑 检查环境配置..."
if [ -f ".env" ]; then
    echo -e "${GREEN}✅ .env文件存在${NC}"

    # 检查关键变量
    source .env

    if [ -z "$OPENAI_API_KEY" ]; then
        echo -e "${YELLOW}⚠️  警告: OPENAI_API_KEY未设置${NC}"
        WARNINGS=$((WARNINGS + 1))
    fi

    if [ -z "$DATABASE_URL" ]; then
        echo -e "${YELLOW}⚠️  警告: DATABASE_URL未设置${NC}"
        WARNINGS=$((WARNINGS + 1))
    fi
else
    echo -e "${YELLOW}⚠️  警告: .env文件不存在${NC}"
    echo "   请从.env.example复制并配置: cp .env.example .env"
    WARNINGS=$((WARNINGS + 1))
fi

echo ""

# 4. 检查Docker Compose配置
echo "📋 检查Docker Compose配置..."
if [ -f "docker-compose.yml" ]; then
    echo -e "${GREEN}✅ docker-compose.yml存在${NC}"

    # 验证配置语法
    if docker-compose config &> /dev/null; then
        echo -e "${GREEN}✅ Docker Compose配置有效${NC}"
    else
        echo -e "${RED}❌ 错误: Docker Compose配置无效${NC}"
        ERRORS=$((ERRORS + 1))
    fi
else
    echo -e "${RED}❌ 错误: docker-compose.yml不存在${NC}"
    ERRORS=$((ERRORS + 1))
fi

echo ""

# 5. 检查端口占用
echo "🔌 检查端口占用..."
PORTS=("8000" "5432" "6379" "3000")
PORT_NAMES=("Backend" "PostgreSQL" "Redis" "Frontend")

for i in "${!PORTS[@]}"; do
    PORT="${PORTS[$i]}"
    NAME="${PORT_NAMES[$i]}"

    if lsof -Pi :$PORT -sTCP:LISTEN -t &> /dev/null; then
        PID=$(lsof -Pi :$PORT -sTCP:LISTEN -t)
        echo -e "${YELLOW}⚠️  警告: 端口 $PORT ($NAME) 已被占用 (PID: $PID)${NC}"
        WARNINGS=$((WARNINGS + 1))
    else
        echo -e "${GREEN}✅ 端口 $PORT ($NAME) 可用${NC}"
    fi
done

echo ""

# 总结
echo "========================================="
echo "  健康检查完成"
echo "========================================="
echo ""

if [ $ERRORS -eq 0 ] && [ $WARNINGS -eq 0 ]; then
    echo -e "${GREEN}🎉 所有检查通过！系统状态良好${NC}"
    exit 0
elif [ $ERRORS -eq 0 ]; then
    echo -e "${YELLOW}⚠️  发现 $WARNINGS 个警告${NC}"
    echo "   系统可以启动，但建议修复警告项"
    exit 0
else
    echo -e "${RED}❌ 发现 $ERRORS 个错误和 $WARNINGS 个警告${NC}"
    echo "   请修复错误后再启动系统"
    exit 1
fi
