#!/bin/bash

# 时间戳修复测试脚本
# 用于验证代码优化后timestamp功能正常工作

set -e

echo "========================================="
echo "  时间戳修复功能测试"
echo "========================================="
echo ""

# 颜色定义
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

TESTS_PASSED=0
TESTS_FAILED=0

# 测试函数
run_test() {
    local test_name=$1
    local test_command=$2
    local expected_pattern=$3

    echo -n "测试: $test_name ... "

    result=$(eval "$test_command" 2>&1)

    if echo "$result" | grep -q "$expected_pattern"; then
        echo -e "${GREEN}✅ 通过${NC}"
        TESTS_PASSED=$((TESTS_PASSED + 1))
        return 0
    else
        echo -e "${RED}❌ 失败${NC}"
        echo "   期望: $expected_pattern"
        echo "   实际: $result"
        TESTS_FAILED=$((TESTS_FAILED + 1))
        return 1
    fi
}

# 检查容器是否运行
echo "检查容器状态..."
if ! docker ps --format '{{.Names}}' | grep -q gomuseum-backend; then
    echo -e "${RED}❌ Backend容器未运行${NC}"
    echo "请先启动: docker-compose up -d"
    exit 1
fi

if ! docker ps --format '{{.Names}}' | grep -q gomuseum-db; then
    echo -e "${RED}❌ PostgreSQL容器未运行${NC}"
    echo "请先启动: docker-compose up -d"
    exit 1
fi

echo -e "${GREEN}✅ 容器运行中${NC}"
echo ""

# 测试1：检查数据库迁移状态
echo "📋 测试1：数据库迁移状态"
run_test \
    "检查Alembic当前版本" \
    "docker exec gomuseum-backend alembic current 2>&1" \
    "004"

echo ""

# 测试2：检查timestamp列配置
echo "📋 测试2：timestamp列配置"
run_test \
    "timestamp列使用now()默认值" \
    "docker exec gomuseum-db psql -U postgres -d gomuseum -t -c \"SELECT column_default FROM information_schema.columns WHERE table_name = 'recognition_results' AND column_name = 'timestamp';\" 2>&1" \
    "now()"

echo ""

# 测试3：测试插入记录（不提供timestamp）
echo "📋 测试3：插入记录测试"

TEST_HASH="test_hash_$(date +%s)_$(openssl rand -hex 16)"

INSERT_SQL="
INSERT INTO recognition_results (
    image_hash,
    artwork_name,
    artist,
    period,
    description,
    confidence
) VALUES (
    '$TEST_HASH',
    'Test Artwork',
    'Test Artist',
    'Modern',
    'Test Description',
    0.95
) RETURNING timestamp;
"

echo "   插入测试记录（不提供timestamp）..."
INSERTED_TIMESTAMP=$(docker exec gomuseum-db psql -U postgres -d gomuseum -t -c "$INSERT_SQL" 2>&1 | tr -d ' ')

if [ -n "$INSERTED_TIMESTAMP" ]; then
    echo -e "   ${GREEN}✅ 插入成功${NC}"
    echo "   生成的timestamp: $INSERTED_TIMESTAMP"
    TESTS_PASSED=$((TESTS_PASSED + 1))

    # 验证时间戳是否合理（应该是2024年）
    if echo "$INSERTED_TIMESTAMP" | grep -q "2024"; then
        echo -e "   ${GREEN}✅ 时间戳年份正确（2024）${NC}"
        TESTS_PASSED=$((TESTS_PASSED + 1))
    else
        echo -e "   ${RED}❌ 时间戳年份异常${NC}"
        TESTS_FAILED=$((TESTS_FAILED + 1))
    fi
else
    echo -e "   ${RED}❌ 插入失败${NC}"
    TESTS_FAILED=$((TESTS_FAILED + 1))
fi

echo ""

# 测试4：验证约束不会因时间戳问题而失败
echo "📋 测试4：约束检查"

CONSTRAINT_TEST_HASH="constraint_test_$(date +%s)_$(openssl rand -hex 16)"

CONSTRAINT_SQL="
INSERT INTO recognition_results (
    image_hash,
    artwork_name,
    artist,
    period,
    description,
    confidence
) VALUES (
    '$CONSTRAINT_TEST_HASH',
    'Constraint Test',
    'Test Artist',
    'Modern',
    'Constraint test description',
    0.88
);
"

echo "   测试约束检查（使用数据库默认时间）..."
CONSTRAINT_RESULT=$(docker exec gomuseum-db psql -U postgres -d gomuseum -c "$CONSTRAINT_SQL" 2>&1)

if echo "$CONSTRAINT_RESULT" | grep -q "INSERT 0 1"; then
    echo -e "   ${GREEN}✅ 约束检查通过，插入成功${NC}"
    TESTS_PASSED=$((TESTS_PASSED + 1))
elif echo "$CONSTRAINT_RESULT" | grep -q "check_timestamp_not_future"; then
    echo -e "   ${RED}❌ 约束检查失败：timestamp超出范围${NC}"
    echo "   这说明时间戳修复未生效或系统时间仍然错误"
    TESTS_FAILED=$((TESTS_FAILED + 1))
else
    echo -e "   ${YELLOW}⚠️  插入失败，但不是因为时间戳约束${NC}"
    echo "   错误信息: $CONSTRAINT_RESULT"
    TESTS_FAILED=$((TESTS_FAILED + 1))
fi

echo ""

# 测试5：比较数据库now()和插入的timestamp
echo "📋 测试5：时间戳一致性"

COMPARE_SQL="
SELECT
    now() as db_now,
    (SELECT timestamp FROM recognition_results WHERE image_hash = '$TEST_HASH') as record_timestamp,
    EXTRACT(EPOCH FROM (now() - (SELECT timestamp FROM recognition_results WHERE image_hash = '$TEST_HASH'))) as diff_seconds;
"

echo "   比较数据库now()和记录timestamp..."
COMPARE_RESULT=$(docker exec gomuseum-db psql -U postgres -d gomuseum -t -c "$COMPARE_SQL" 2>&1)

if [ -n "$COMPARE_RESULT" ]; then
    echo "   $COMPARE_RESULT"

    # 提取时间差（秒）
    DIFF=$(echo "$COMPARE_RESULT" | awk -F'|' '{print $3}' | tr -d ' ')

    # 检查时间差是否在合理范围内（60秒内）
    if [ -n "$DIFF" ]; then
        DIFF_ABS=$(echo "$DIFF" | awk '{if ($1 < 0) print -$1; else print $1}')

        if [ "$(echo "$DIFF_ABS < 60" | bc)" -eq 1 ]; then
            echo -e "   ${GREEN}✅ 时间戳与now()差异在合理范围内（${DIFF}秒）${NC}"
            TESTS_PASSED=$((TESTS_PASSED + 1))
        else
            echo -e "   ${YELLOW}⚠️  时间戳差异较大（${DIFF}秒）${NC}"
            TESTS_FAILED=$((TESTS_FAILED + 1))
        fi
    fi
fi

echo ""

# 清理测试数据
echo "🧹 清理测试数据..."
docker exec gomuseum-db psql -U postgres -d gomuseum -c "
    DELETE FROM recognition_results
    WHERE image_hash IN ('$TEST_HASH', '$CONSTRAINT_TEST_HASH');
" > /dev/null 2>&1

echo -e "${GREEN}✅ 测试数据已清理${NC}"
echo ""

# 总结
echo "========================================="
echo "  测试总结"
echo "========================================="
echo ""

TOTAL_TESTS=$((TESTS_PASSED + TESTS_FAILED))
echo "总测试数: $TOTAL_TESTS"
echo -e "通过: ${GREEN}$TESTS_PASSED${NC}"
echo -e "失败: ${RED}$TESTS_FAILED${NC}"

echo ""

if [ $TESTS_FAILED -eq 0 ]; then
    echo -e "${GREEN}🎉 所有测试通过！时间戳修复成功！${NC}"
    echo ""
    echo "修复内容："
    echo "✅ 数据库迁移已完成"
    echo "✅ timestamp使用数据库服务器端默认值now()"
    echo "✅ 插入记录时无需提供timestamp"
    echo "✅ 约束检查正常工作"
    echo "✅ 时间戳与数据库时间一致"
    exit 0
else
    echo -e "${RED}❌ 部分测试失败${NC}"
    echo ""
    echo "建议："
    echo "1. 检查数据库迁移是否成功执行"
    echo "   docker exec -it gomuseum-backend alembic upgrade head"
    echo ""
    echo "2. 验证系统时间是否已修正为2024年"
    echo "   ./scripts/verify-time.sh"
    echo ""
    echo "3. 检查容器日志"
    echo "   docker-compose logs backend"
    echo "   docker-compose logs db"
    exit 1
fi
