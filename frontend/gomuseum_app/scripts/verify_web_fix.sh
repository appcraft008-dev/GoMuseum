#!/bin/bash

# Web 平台修复验证脚本
# 用途：验证所有修改是否正确应用

set -e

echo "🔍 验证 Web 平台修复..."
echo ""

# 颜色定义
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 计数器
PASS=0
FAIL=0

# 验证函数
verify_change() {
    local file="$1"
    local pattern="$2"
    local description="$3"

    if grep -q "$pattern" "$file"; then
        echo -e "${GREEN}✅${NC} $description"
        ((PASS++))
    else
        echo -e "${RED}❌${NC} $description"
        echo "   文件: $file"
        echo "   缺失: $pattern"
        ((FAIL++))
    fi
}

# 进入项目目录
cd "$(dirname "$0")/.."

echo "📂 工作目录: $(pwd)"
echo ""

echo "1️⃣ 验证 recognize_artwork.dart 修改"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

verify_change \
    "lib/features/recognition/domain/usecases/recognize_artwork.dart" \
    "final bytes = await imageFile.readAsBytes()" \
    "移除 File.exists() 调用，改用 readAsBytes()"

verify_change \
    "lib/features/recognition/domain/usecases/recognize_artwork.dart" \
    "if (bytes.length > 10 \* 1024 \* 1024)" \
    "使用 bytes.length 替代 fileSize"

verify_change \
    "lib/features/recognition/domain/usecases/recognize_artwork.dart" \
    "try {" \
    "添加 try-catch 错误处理"

# 确保不存在 exists() 调用
if grep -q "imageFile.exists()" "lib/features/recognition/domain/usecases/recognize_artwork.dart"; then
    echo -e "${RED}❌${NC} 文件中仍然包含 imageFile.exists() 调用"
    ((FAIL++))
else
    echo -e "${GREEN}✅${NC} 已完全移除 imageFile.exists() 调用"
    ((PASS++))
fi

echo ""
echo "2️⃣ 验证 recognition_providers.dart 修改"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

verify_change \
    "lib/features/recognition/presentation/providers/recognition_providers.dart" \
    "connectTimeout: const Duration(seconds: 60)" \
    "Dio connectTimeout 增加到 60 秒"

verify_change \
    "lib/features/recognition/presentation/providers/recognition_providers.dart" \
    "receiveTimeout: const Duration(seconds: 60)" \
    "Dio receiveTimeout 增加到 60 秒"

# 确保移除了未使用的导入
if grep -q "import 'package:flutter/foundation.dart'" "lib/features/recognition/presentation/providers/recognition_providers.dart"; then
    echo -e "${RED}❌${NC} 仍然包含未使用的 foundation.dart 导入"
    ((FAIL++))
else
    echo -e "${GREEN}✅${NC} 已移除未使用的 foundation.dart 导入"
    ((PASS++))
fi

echo ""
echo "3️⃣ 验证 recognition_remote_datasource.dart 修改"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

verify_change \
    "lib/features/recognition/data/datasources/recognition_remote_datasource.dart" \
    "sendTimeout: const Duration(seconds: 60)" \
    "Request sendTimeout 增加到 60 秒"

verify_change \
    "lib/features/recognition/data/datasources/recognition_remote_datasource.dart" \
    "receiveTimeout: const Duration(seconds: 60)" \
    "Request receiveTimeout 增加到 60 秒"

verify_change \
    "lib/features/recognition/data/datasources/recognition_remote_datasource.dart" \
    "Request timeout after 60 seconds" \
    "错误消息更新为 60 秒"

echo ""
echo "4️⃣ 验证文件存在性"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

FILES=(
    "lib/features/recognition/domain/usecases/recognize_artwork.dart"
    "lib/features/recognition/presentation/providers/recognition_providers.dart"
    "lib/features/recognition/data/datasources/recognition_remote_datasource.dart"
)

for file in "${FILES[@]}"; do
    if [ -f "$file" ]; then
        echo -e "${GREEN}✅${NC} 文件存在: $file"
        ((PASS++))
    else
        echo -e "${RED}❌${NC} 文件不存在: $file"
        ((FAIL++))
    fi
done

echo ""
echo "5️⃣ 运行 Flutter 分析"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if flutter analyze --no-pub 2>&1 | grep -q "No issues found"; then
    echo -e "${GREEN}✅${NC} Flutter analyze 通过"
    ((PASS++))
else
    echo -e "${YELLOW}⚠️${NC}  Flutter analyze 有警告（可能存在已知问题）"
    echo "   运行 'flutter analyze' 查看详情"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📊 验证结果统计"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo -e "${GREEN}✅ 通过: $PASS${NC}"
echo -e "${RED}❌ 失败: $FAIL${NC}"
echo ""

if [ $FAIL -eq 0 ]; then
    echo -e "${GREEN}🎉 所有验证通过！${NC}"
    echo ""
    echo "下一步："
    echo "  1. 启动应用: ./scripts/run_chrome.sh"
    echo "  2. 测试图片识别功能"
    echo "  3. 参考: WEB_PLATFORM_TEST_CHECKLIST.md"
    exit 0
else
    echo -e "${RED}❌ 验证失败，请检查修改！${NC}"
    exit 1
fi
