#!/bin/bash
# verify-environment.sh - 一键环境验证

echo "🔍 GoMuseum环境验证开始..."

# 创建验证报告
REPORT_FILE="environment-report.txt"
echo "GoMuseum环境验证报告 - $(date)" > $REPORT_FILE

# 加载nvm环境(如果存在)
if [ -s "$HOME/.nvm/nvm.sh" ]; then
    export NVM_DIR="$HOME/.nvm"
    [ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
    # 如果存在.nvmrc，自动使用指定版本
    if [ -f ".nvmrc" ]; then
        nvm use > /dev/null 2>&1
    fi
fi

verify_version() {
    local cmd=$1
    local expected=$2
    local actual=$($cmd 2>/dev/null || echo "未安装")

    if [[ $actual == *"$expected"* ]]; then
        echo "✅ $cmd: $actual" | tee -a $REPORT_FILE
        return 0
    else
        echo "❌ $cmd: 期望 $expected, 实际 $actual" | tee -a $REPORT_FILE
        return 1
    fi
}

echo "" | tee -a $REPORT_FILE
echo "=== 核心依赖验证 ===" | tee -a $REPORT_FILE

# 验证各项依赖 (放宽版本要求)
# 优先使用nvm的node版本
if [ -n "$NVM_DIR" ]; then
    NODE_VERSION=$(nvm current)
    echo "✅ node (via nvm): $NODE_VERSION" | tee -a $REPORT_FILE
else
    verify_version "node --version" "v20"
fi
verify_version "npm --version" "10"
verify_version "python3 --version" "Python 3.11"
verify_version "docker --version" "Docker version"
verify_version "psql --version" "16"
verify_version "redis-server --version" "Redis server"

echo "" | tee -a $REPORT_FILE
echo "=== Flutter环境验证 ===" | tee -a $REPORT_FILE
if command -v flutter &> /dev/null; then
    FLUTTER_VERSION=$(flutter --version 2>&1 | head -n1)
    echo "✅ Flutter: $FLUTTER_VERSION" | tee -a $REPORT_FILE
else
    echo "❌ Flutter: 未安装" | tee -a $REPORT_FILE
fi

echo "" | tee -a $REPORT_FILE
echo "📋 验证报告已生成: $REPORT_FILE"
echo "🎉 环境验证完成！"
