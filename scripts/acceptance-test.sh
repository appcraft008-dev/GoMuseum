#!/bin/bash
# scripts/acceptance-test.sh
# 项目初始化验收测试脚本

set -e

echo "🧪 项目初始化验收测试开始..."

# 加载nvm环境(如果存在)
if [ -s "$HOME/.nvm/nvm.sh" ]; then
    export NVM_DIR="$HOME/.nvm"
    [ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
fi

# ================================
# 1. 检查目录结构
# ================================
echo "📁 检查目录结构..."

required_dirs=("frontend" "backend" "scripts" ".github")
optional_dirs=("shared" "docker" "docs")

for dir in "${required_dirs[@]}"; do
    if [ -d "$dir" ]; then
        echo "✅ 必需目录 $dir 存在"
    else
        echo "❌ 必需目录 $dir 缺失"
        exit 1
    fi
done

for dir in "${optional_dirs[@]}"; do
    if [ -d "$dir" ]; then
        echo "✅ 可选目录 $dir 存在"
    else
        echo "⚠️  可选目录 $dir 缺失 (跳过，不影响验收)"
    fi
done

# ================================
# 2. 检查配置文件
# ================================
echo "⚙️ 检查配置文件..."
required_files=("package.json" "docker-compose.yml" ".env.example" ".gitignore")

for file in "${required_files[@]}"; do
    if [ -f "$file" ]; then
        echo "✅ $file 文件存在"
    else
        echo "❌ $file 文件缺失"
        exit 1
    fi
done

# ================================
# 3. 检查前端依赖 (Flutter)
# ================================
echo "📦 检查前端依赖..."
if [ -d "frontend/gomuseum_app" ]; then
    cd frontend/gomuseum_app
    echo "→ 执行 flutter pub get..."
    if flutter pub get; then
        echo "✅ Flutter 依赖安装成功"
    else
        echo "❌ Flutter 依赖安装失败"
        exit 1
    fi
    cd ../..
else
    echo "⚠️  未找到 frontend/gomuseum_app，跳过前端依赖检查"
fi

# ================================
# 4. 检查后端依赖 (pip / Poetry)
# ================================
echo "📦 检查后端依赖..."
if [ -d "backend" ]; then
    cd backend

    # 优先使用requirements.txt
    if [ -f "requirements.txt" ]; then
        if [ -s "requirements.txt" ] && grep -v '^\s*#' requirements.txt | grep . > /dev/null; then
            echo "→ 检测到 requirements.txt，执行 pip install..."
            if python3 -m pip install -r requirements.txt --quiet; then
                echo "✅ 后端依赖 (pip) 安装成功"
            else
                echo "❌ 后端依赖安装失败"
                cd ..
                exit 1
            fi
        else
            echo "⚠️  requirements.txt 为空或仅包含注释，跳过依赖安装"
        fi
    elif [ -f "pyproject.toml" ] && command -v poetry &> /dev/null; then
        echo "→ 检测到 Poetry 配置，执行 poetry install..."
        if poetry install --no-root; then
            echo "✅ 后端依赖 (Poetry) 安装成功"
        else
            echo "❌ 后端依赖安装失败"
            cd ..
            exit 1
        fi
    else
        echo "⚠️  backend 中未找到可用的依赖管理工具，跳过依赖检查"
    fi
    cd ..
else
    echo "⚠️  backend 目录缺失，跳过后端依赖检查"
fi

# ================================
# 5. Docker 服务检查 (可选)
# ================================
if [ -f "docker-compose.yml" ]; then
    echo "🚀 检查 docker-compose 服务..."
    docker-compose up -d
    sleep 5

    # 假设 FastAPI 有健康检查路由 /healthz
    if curl -f http://localhost:8000/healthz > /dev/null 2>&1; then
        echo "✅ 后端 API 服务正常"
    else
        echo "⚠️  后端 API 服务未响应 (可选检查)"
    fi

    docker-compose down
else
    echo "⚠️  未找到 docker-compose.yml，跳过服务检查"
fi

echo "🎉 项目初始化验收测试完成！"

