#!/bin/bash

# 时间验证脚本
# 用于验证系统、容器、数据库的时间一致性

set -e

echo "========================================="
echo "  GoMuseum 时间同步验证"
echo "========================================="
echo ""

# 颜色定义
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

# 1. 宿主机时间
echo "1️⃣  宿主机时间:"
HOST_DATE=$(date)
HOST_YEAR=$(date +%Y)
echo "   $HOST_DATE"
echo "   年份: $HOST_YEAR"

if [ "$HOST_YEAR" == "2024" ]; then
    echo -e "   ${GREEN}✅ 年份正确${NC}"
else
    echo -e "   ${RED}❌ 年份异常（期望2024）${NC}"
fi

echo ""

# 2. Backend容器时间
echo "2️⃣  Backend容器时间:"
if docker ps --format '{{.Names}}' | grep -q gomuseum-backend; then
    BACKEND_DATE=$(docker exec gomuseum-backend date 2>/dev/null || echo "容器未运行")
    BACKEND_YEAR=$(docker exec gomuseum-backend date +%Y 2>/dev/null || echo "N/A")
    echo "   $BACKEND_DATE"
    echo "   年份: $BACKEND_YEAR"

    if [ "$BACKEND_YEAR" == "2024" ]; then
        echo -e "   ${GREEN}✅ 年份正确${NC}"
    elif [ "$BACKEND_YEAR" == "N/A" ]; then
        echo -e "   ${RED}❌ 容器未运行${NC}"
    else
        echo -e "   ${RED}❌ 年份异常（期望2024）${NC}"
    fi
else
    echo -e "   ${YELLOW}⚠️  Backend容器未运行${NC}"
fi

echo ""

# 3. PostgreSQL容器时间
echo "3️⃣  PostgreSQL容器时间:"
if docker ps --format '{{.Names}}' | grep -q gomuseum-db; then
    DB_DATE=$(docker exec gomuseum-db date 2>/dev/null || echo "容器未运行")
    DB_YEAR=$(docker exec gomuseum-db date +%Y 2>/dev/null || echo "N/A")
    echo "   $DB_DATE"
    echo "   年份: $DB_YEAR"

    if [ "$DB_YEAR" == "2024" ]; then
        echo -e "   ${GREEN}✅ 年份正确${NC}"
    elif [ "$DB_YEAR" == "N/A" ]; then
        echo -e "   ${RED}❌ 容器未运行${NC}"
    else
        echo -e "   ${RED}❌ 年份异常（期望2024）${NC}"
    fi
else
    echo -e "   ${YELLOW}⚠️  PostgreSQL容器未运行${NC}"
fi

echo ""

# 4. 数据库now()函数
echo "4️⃣  数据库now()函数:"
if docker ps --format '{{.Names}}' | grep -q gomuseum-db; then
    DB_NOW=$(docker exec gomuseum-db psql -U postgres -d gomuseum -t -c "SELECT now();" 2>/dev/null || echo "查询失败")
    echo "   $DB_NOW"

    if echo "$DB_NOW" | grep -q "2024"; then
        echo -e "   ${GREEN}✅ 数据库时间正确${NC}"
    else
        echo -e "   ${RED}❌ 数据库时间异常${NC}"
    fi

    # 额外检查：显示时区
    DB_TIMEZONE=$(docker exec gomuseum-db psql -U postgres -d gomuseum -t -c "SHOW timezone;" 2>/dev/null || echo "查询失败")
    echo "   时区: $DB_TIMEZONE"
else
    echo -e "   ${YELLOW}⚠️  PostgreSQL容器未运行${NC}"
fi

echo ""

# 5. Python应用时间
echo "5️⃣  Python应用时间生成:"
if docker ps --format '{{.Names}}' | grep -q gomuseum-backend; then
    PYTHON_TIME=$(docker exec gomuseum-backend python -c "from datetime import datetime; print('UTC now:', datetime.utcnow())" 2>/dev/null || echo "执行失败")
    echo "   $PYTHON_TIME"

    if echo "$PYTHON_TIME" | grep -q "2024"; then
        echo -e "   ${GREEN}✅ Python时间正确${NC}"
    else
        echo -e "   ${RED}❌ Python时间异常${NC}"
    fi
else
    echo -e "   ${YELLOW}⚠️  Backend容器未运行${NC}"
fi

echo ""

# 6. 时间戳比较
echo "6️⃣  时间戳差异分析:"
if docker ps --format '{{.Names}}' | grep -q gomuseum-backend && docker ps --format '{{.Names}}' | grep -q gomuseum-db; then
    # 获取宿主机时间戳
    HOST_TS=$(date +%s)

    # 获取容器时间戳
    BACKEND_TS=$(docker exec gomuseum-backend date +%s 2>/dev/null || echo "0")
    DB_TS=$(docker exec gomuseum-db date +%s 2>/dev/null || echo "0")

    echo "   宿主机时间戳:   $HOST_TS"
    echo "   Backend时间戳:  $BACKEND_TS"
    echo "   Database时间戳: $DB_TS"

    # 计算差异
    BACKEND_DIFF=$((HOST_TS - BACKEND_TS))
    DB_DIFF=$((HOST_TS - DB_TS))

    BACKEND_DIFF_ABS=${BACKEND_DIFF#-}
    DB_DIFF_ABS=${DB_DIFF#-}

    echo ""
    echo "   宿主机 vs Backend: ${BACKEND_DIFF}秒"
    echo "   宿主机 vs Database: ${DB_DIFF}秒"

    if [ $BACKEND_DIFF_ABS -le 2 ] && [ $DB_DIFF_ABS -le 2 ]; then
        echo -e "   ${GREEN}✅ 所有时间同步（差异≤2秒）${NC}"
    elif [ $BACKEND_DIFF_ABS -le 60 ] && [ $DB_DIFF_ABS -le 60 ]; then
        echo -e "   ${YELLOW}⚠️  时间差异较小（差异≤60秒），可接受${NC}"
    else
        echo -e "   ${RED}❌ 时间差异过大，建议重启Docker容器${NC}"
    fi
else
    echo -e "   ${YELLOW}⚠️  容器未全部运行，无法比较${NC}"
fi

echo ""

# 7. 检查recognition_results表的timestamp默认值
echo "7️⃣  检查timestamp列配置:"
if docker ps --format '{{.Names}}' | grep -q gomuseum-db; then
    TIMESTAMP_DEFAULT=$(docker exec gomuseum-db psql -U postgres -d gomuseum -t -c "
        SELECT column_default
        FROM information_schema.columns
        WHERE table_name = 'recognition_results'
        AND column_name = 'timestamp';
    " 2>/dev/null || echo "查询失败")

    echo "   timestamp默认值: $TIMESTAMP_DEFAULT"

    if echo "$TIMESTAMP_DEFAULT" | grep -q "now()"; then
        echo -e "   ${GREEN}✅ 已配置为数据库服务器端时间（now()）${NC}"
    else
        echo -e "   ${YELLOW}⚠️  未使用服务器端默认值，建议运行迁移${NC}"
        echo "   执行: docker exec -it gomuseum-backend alembic upgrade head"
    fi
else
    echo -e "   ${YELLOW}⚠️  PostgreSQL容器未运行${NC}"
fi

echo ""

# 总结
echo "========================================="
echo "  验证总结"
echo "========================================="
echo ""

if [ "$HOST_YEAR" == "2024" ] && [ "$BACKEND_YEAR" == "2024" ] && [ "$DB_YEAR" == "2024" ]; then
    echo -e "${GREEN}🎉 所有时间验证通过！${NC}"
    echo "   - 宿主机、容器、数据库时间均为2024年"
    echo "   - 系统可以正常运行"
    exit 0
else
    echo -e "${RED}❌ 时间验证失败！${NC}"
    echo ""
    echo "修复建议："
    echo "1. 修正macOS系统时间："
    echo "   系统偏好设置 → 日期与时间 → 设置为2024年"
    echo ""
    echo "2. 重启Docker容器："
    echo "   cd /Users/hongyang/Projects/GoMuseum"
    echo "   docker-compose down"
    echo "   docker-compose up -d"
    echo ""
    echo "3. 重新运行此脚本验证"
    exit 1
fi
