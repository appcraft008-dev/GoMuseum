#!/bin/bash

# Chrome 平台运行脚本
# 用途：启动 Flutter Web 应用在 Chrome 浏览器中

set -e

echo "🚀 启动 Flutter Web 应用 (Chrome)..."
echo ""
echo "修复内容："
echo "  ✅ 移除 Web 不兼容的 File.exists() 调用"
echo "  ✅ 增加超时时间到 60 秒"
echo ""
echo "测试步骤："
echo "  1. 等待应用启动"
echo "  2. 点击'选择图片'按钮"
echo "  3. 选择艺术品图片（JPEG/PNG，<10MB）"
echo "  4. 等待识别结果（最多 60 秒）"
echo ""
echo "热重载："
echo "  - 按 'r' 键进行热重载"
echo "  - 按 'R' 键进行热重启"
echo "  - 按 'q' 键退出"
echo ""

cd "$(dirname "$0")/.."
flutter run -d chrome --web-port=8080
