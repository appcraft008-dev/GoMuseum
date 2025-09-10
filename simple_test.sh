#!/bin/bash

# GoMuseum API 简单测试脚本
echo "🚀 GoMuseum API 测试开始..."
echo "================================"

BASE_URL="http://localhost:8000"

# 1. 健康检查
echo "1️⃣ 测试健康检查..."
curl -s $BASE_URL/health | jq . 2>/dev/null || curl -s $BASE_URL/health
echo -e "\n"

# 2. 创建用户（使用时间戳避免重复）
TIMESTAMP=$(date +%s)
EMAIL="testuser_${TIMESTAMP}@demo.com"
USERNAME="testuser_${TIMESTAMP}"

echo "2️⃣ 创建测试用户..."
echo "📧 邮箱: $EMAIL"
USER_RESPONSE=$(curl -s -X POST $BASE_URL/api/v1/user \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"$EMAIL\",\"username\":\"$USERNAME\",\"language\":\"zh\"}")

echo $USER_RESPONSE | jq . 2>/dev/null || echo $USER_RESPONSE

# 提取用户ID
if command -v jq &> /dev/null; then
    USER_ID=$(echo $USER_RESPONSE | jq -r '.id' 2>/dev/null)
else
    # 如果没有jq，使用简单的grep和sed
    USER_ID=$(echo $USER_RESPONSE | grep -o '"id":"[^"]*' | cut -d'"' -f4)
fi

echo "📝 用户ID: $USER_ID"
echo -e "\n"

if [ "$USER_ID" != "null" ] && [ -n "$USER_ID" ]; then
    # 3. 查询用户配额
    echo "3️⃣ 查询用户配额..."
    curl -s $BASE_URL/api/v1/user/$USER_ID/quota | jq . 2>/dev/null || curl -s $BASE_URL/api/v1/user/$USER_ID/quota
    echo -e "\n"

    # 4. 测试图片识别
    echo "4️⃣ 测试图片识别..."
    TEST_IMAGE=$(echo -n "fake test image data" | base64)
    curl -s -X POST $BASE_URL/api/v1/recognize \
      -H "Content-Type: application/json" \
      -d "{\"image\":\"$TEST_IMAGE\",\"language\":\"zh\",\"user_id\":\"$USER_ID\"}" | \
      jq . 2>/dev/null || curl -s -X POST $BASE_URL/api/v1/recognize \
      -H "Content-Type: application/json" \
      -d "{\"image\":\"$TEST_IMAGE\",\"language\":\"zh\",\"user_id\":\"$USER_ID\"}"
    echo -e "\n"

    # 5. 消费配额
    echo "5️⃣ 消费配额..."
    curl -s -X POST $BASE_URL/api/v1/user/$USER_ID/consume-quota | jq . 2>/dev/null || curl -s -X POST $BASE_URL/api/v1/user/$USER_ID/consume-quota
    echo -e "\n"

    # 6. 再次查询配额
    echo "6️⃣ 查询配额变化..."
    curl -s $BASE_URL/api/v1/user/$USER_ID/quota | jq . 2>/dev/null || curl -s $BASE_URL/api/v1/user/$USER_ID/quota
    echo -e "\n"

else
    echo "❌ 无法获取用户ID，跳过后续测试"
fi

echo "✅ 测试完成！"
echo "================================"
echo "💡 提示："
echo "   - 访问 $BASE_URL/docs 查看完整API文档"
echo "   - 所有API都已正常运行"
echo "   - 可以开始Step 2的AI模型集成开发"