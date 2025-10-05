#!/bin/bash

# 验证平台兼容性修复
# 此脚本验证 Web 和原生平台都能正确编译

set -e

echo "=========================================="
echo "验证平台兼容性修复"
echo "=========================================="
echo ""

# 进入前端目录
cd "$(dirname "$0")/.."

echo "1. 运行 Flutter 分析..."
flutter analyze

echo ""
echo "2. 构建 Web 平台..."
flutter build web --release

echo ""
echo "3. 构建 macOS 平台..."
flutter build macos --debug

echo ""
echo "=========================================="
echo "所有平台验证成功！"
echo "=========================================="
echo ""
echo "修复总结："
echo "- 移除了 RecognitionResultModel 中的平台特定依赖"
echo "- 创建了平台特定的转换器扩展"
echo "- 使用条件导入实现平台特定的数据源"
echo "- Web 平台使用桩实现，原生平台使用 Drift 数据库"
echo ""
