#!/bin/bash

# GoMuseum 启动脚本
# 用于快速启动开发环境

echo "🚀 GoMuseum 开发环境启动脚本"
echo "=================================="

# 检查 Docker
if ! command -v docker &> /dev/null; then
    echo "❌ Docker 未安装，请先安装 Docker"
    exit 1
fi

# 检查Docker服务是否运行
if ! docker info > /dev/null 2>&1; then
    echo "🐳 Docker服务未运行，正在启动 Docker Desktop..."
    open /Applications/Docker.app
    echo "⏳ 等待Docker服务启动（可能需要30-60秒）..."
    
    # 等待Docker服务启动，最多等待2分钟
    for i in {1..24}; do
        if docker info > /dev/null 2>&1; then
            echo "✅ Docker服务启动成功"
            break
        fi
        echo -n "."
        sleep 5
    done
    
    if ! docker info > /dev/null 2>&1; then
        echo "❌ Docker服务启动失败，请手动启动Docker Desktop"
        exit 1
    fi
fi

# 检查 docker-compose 或 docker compose
if command -v docker-compose &> /dev/null; then
    DOCKER_COMPOSE_CMD="docker-compose"
elif docker compose version > /dev/null 2>&1; then
    DOCKER_COMPOSE_CMD="docker compose"
else
    echo "❌ Docker Compose 未安装或不可用"
    exit 1
fi

# 检查环境变量文件
if [ ! -f .env ]; then
    echo "⚠️  .env 文件不存在，从模板创建..."
    cp .env.example .env
    echo "✅ 已创建 .env 文件，请编辑填入API密钥"
    echo "📝 需要配置的主要变量："
    echo "   - OPENAI_API_KEY: OpenAI API密钥"
    echo "   - ANTHROPIC_API_KEY: Anthropic API密钥"
    echo ""
fi

# 创建必要的目录
echo "📁 创建必要的目录..."
mkdir -p logs/nginx
mkdir -p postgres_data
mkdir -p redis_data

# 启动服务
echo "🐳 启动 Docker 服务..."
$DOCKER_COMPOSE_CMD up -d

# 等待服务启动
echo "⏳ 等待服务启动..."
sleep 10

# 检查服务状态
echo "🔍 检查服务状态..."
$DOCKER_COMPOSE_CMD ps

# 等待API服务健康检查通过
echo "🏥 等待API服务启动..."
for i in {1..12}; do
    if curl -f http://localhost:8000/health > /dev/null 2>&1; then
        echo "✅ API服务运行正常"
        break
    fi
    echo -n "."
    sleep 5
done

# 最终健康检查
if curl -f http://localhost:8000/health > /dev/null 2>&1; then
    echo ""
    echo "🎯 所有服务启动成功！"
else
    echo ""
    echo "❌ API服务健康检查失败，查看详细日志："
    echo "   $DOCKER_COMPOSE_CMD logs api"
    echo ""
    echo "🔧 常见解决方案："
    echo "   1. 等待更长时间：API可能还在启动中"
    echo "   2. 重启API服务：$DOCKER_COMPOSE_CMD restart api"
    echo "   3. 检查端口冲突：lsof -i :8000"
    echo "   4. 查看完整日志：$DOCKER_COMPOSE_CMD logs -f api"
fi

# 显示访问地址
echo ""
echo "🎉 GoMuseum 开发环境启动完成！"
echo "=================================="
echo "📊 API文档:     http://localhost:8000/docs"
echo "🏥 健康检查:    http://localhost:8000/health"
echo "🗃️  数据库:      localhost:5432 (gomuseum/gomuseum123)"
echo "🔄 Redis:       localhost:6379"
echo ""
echo "🔧 有用的命令："
echo "   查看日志:      docker-compose logs -f api"
echo "   重启API:      docker-compose restart api" 
echo "   停止服务:      docker-compose down"
echo "   进入数据库:    docker-compose exec postgres psql -U gomuseum -d gomuseum"
echo ""
echo "📝 下一步："
echo "   1. 编辑 .env 文件配置API密钥"
echo "   2. 访问 http://localhost:8000/docs 测试API"
echo "   3. 开始 Step 2 - 实现AI识别功能"