#!/bin/bash
# 手工验收快速启动脚本

set -e

echo "🚀 GoMuseum Step 1 手工验收环境启动"
echo "===================================="
echo ""

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# 检查Docker服务
echo "📦 检查Docker服务..."
if ! docker ps > /dev/null 2>&1; then
    echo -e "${RED}❌ Docker未运行,请先启动Docker${NC}"
    exit 1
fi

# 检查并启动PostgreSQL和Redis
if ! docker ps | grep -q gomuseum-db; then
    echo "启动PostgreSQL..."
    docker-compose up -d db
fi

if ! docker ps | grep -q gomuseum-redis; then
    echo "启动Redis..."
    docker-compose up -d redis
fi

echo -e "${GREEN}✅ Docker服务已启动${NC}"
echo ""

# 检查Python环境
echo "🐍 检查Python环境..."
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Python3未安装${NC}"
    exit 1
fi

PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
echo -e "${GREEN}✅ Python ${PYTHON_VERSION}${NC}"
echo ""

# 检查Flutter环境
echo "📱 检查Flutter环境..."
if ! command -v flutter &> /dev/null; then
    echo -e "${YELLOW}⚠️  Flutter未安装,前端验收将无法进行${NC}"
else
    FLUTTER_VERSION=$(flutter --version | head -n1 | cut -d' ' -f2)
    echo -e "${GREEN}✅ Flutter ${FLUTTER_VERSION}${NC}"
fi
echo ""

# 运行数据库迁移
echo "🗄️  运行数据库迁移..."
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT/backend"
if alembic upgrade head > /dev/null 2>&1; then
    echo -e "${GREEN}✅ 数据库迁移完成${NC}"
else
    echo -e "${YELLOW}⚠️  数据库迁移可能已运行过${NC}"
fi
cd "$PROJECT_ROOT"
echo ""

# 验证API配置
echo "🔑 验证API配置..."
if grep -q "sk-proj-" "$PROJECT_ROOT/backend/.env" && [ -n "$(grep OPENAI_API_KEY "$PROJECT_ROOT/backend/.env" | grep sk-proj-)" ]; then
    echo -e "${GREEN}✅ OpenAI API Key已配置${NC}"
else
    echo -e "${RED}❌ OpenAI API Key未配置${NC}"
    echo "请先配置API keys,查看: API_KEYS_SETUP_GUIDE.md"
    exit 1
fi
echo ""

# 显示启动说明
echo "===================================="
echo "✅ 环境准备完成!"
echo ""
echo "📋 接下来的步骤:"
echo ""
echo "1️⃣  启动后端服务 (新Terminal窗口):"
echo "   cd backend"
echo "   uvicorn app.main:app --reload"
echo ""
echo "2️⃣  启动Flutter应用 (另一个新Terminal窗口):"
echo "   cd frontend/gomuseum_app"
echo "   flutter run -d chrome    # Chrome浏览器"
echo "   # 或"
echo "   flutter run              # iOS/Android模拟器"
echo ""
echo "3️⃣  开始手工验收:"
echo "   打开文件: MANUAL_ACCEPTANCE_GUIDE.md"
echo "   按照验收清单逐项测试"
echo ""
echo "===================================="
echo ""
echo "📚 相关文档:"
echo "  - 手工验收指南: MANUAL_ACCEPTANCE_GUIDE.md"
echo "  - API配置指南: API_KEYS_SETUP_GUIDE.md"
echo "  - 完成报告: STEP1_FINAL_ACCEPTANCE.md"
echo ""
echo "❓ 需要帮助?"
echo "  - 查看后端日志: docker-compose logs -f"
echo "  - 查看API文档: http://localhost:8000/docs"
echo "  - 测试API连接: python3 backend/test_api_connection.py"
echo ""
echo "🎉 祝验收顺利!"
