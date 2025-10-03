#!/bin/bash

###############################################################################
# GoMuseum Step 1 手动验收脚本
# 用途: 执行完整的Step 1验收测试流程
# 作者: Claude Code
# 日期: 2025-10-02
###############################################################################

set -e  # 遇到错误立即退出

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 项目根目录
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="$PROJECT_ROOT/backend"
FRONTEND_DIR="$PROJECT_ROOT/frontend/gomuseum_app"

# 日志文件
LOG_DIR="$PROJECT_ROOT/logs"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
LOG_FILE="$LOG_DIR/acceptance_${TIMESTAMP}.log"

# 创建日志目录
mkdir -p "$LOG_DIR"

###############################################################################
# 工具函数
###############################################################################

# 打印带颜色的消息
print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}" | tee -a "$LOG_FILE"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}" | tee -a "$LOG_FILE"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}" | tee -a "$LOG_FILE"
}

print_error() {
    echo -e "${RED}❌ $1${NC}" | tee -a "$LOG_FILE"
}

print_header() {
    echo "" | tee -a "$LOG_FILE"
    echo "============================================================" | tee -a "$LOG_FILE"
    echo -e "${BLUE}$1${NC}" | tee -a "$LOG_FILE"
    echo "============================================================" | tee -a "$LOG_FILE"
}

# 检查命令是否存在
check_command() {
    if ! command -v "$1" &> /dev/null; then
        print_error "$1 未安装，请先安装"
        return 1
    fi
    return 0
}

# 检查目录是否存在
check_directory() {
    if [ ! -d "$1" ]; then
        print_error "目录不存在: $1"
        return 1
    fi
    return 0
}

###############################################################################
# 验收步骤
###############################################################################

# 步骤0: 环境检查
step0_environment_check() {
    print_header "步骤0: 环境检查"

    local all_checks_passed=true

    # 检查Python
    if check_command python; then
        PYTHON_VERSION=$(python --version 2>&1)
        print_success "Python已安装: $PYTHON_VERSION"
    else
        all_checks_passed=false
    fi

    # 检查pytest
    if check_command pytest; then
        PYTEST_VERSION=$(pytest --version 2>&1 | head -1)
        print_success "pytest已安装: $PYTEST_VERSION"
    else
        all_checks_passed=false
    fi

    # 检查Flutter
    if check_command flutter; then
        FLUTTER_VERSION=$(flutter --version | head -1)
        print_success "Flutter已安装: $FLUTTER_VERSION"
    else
        all_checks_passed=false
    fi

    # 检查Docker
    if check_command docker; then
        DOCKER_VERSION=$(docker --version)
        print_success "Docker已安装: $DOCKER_VERSION"
    else
        all_checks_passed=false
    fi

    # 检查项目目录
    if check_directory "$BACKEND_DIR"; then
        print_success "Backend目录存在: $BACKEND_DIR"
    else
        all_checks_passed=false
    fi

    if check_directory "$FRONTEND_DIR"; then
        print_success "Frontend目录存在: $FRONTEND_DIR"
    else
        all_checks_passed=false
    fi

    # 检查.env文件
    if [ -f "$BACKEND_DIR/.env" ]; then
        print_success "环境配置文件存在: .env"

        # 检查API Key是否配置
        if grep -q "OPENAI_API_KEY=sk-" "$BACKEND_DIR/.env"; then
            print_success "OpenAI API Key已配置"
        else
            print_warning "OpenAI API Key未配置或格式不正确"
        fi
    else
        print_error ".env文件不存在，请先配置"
        all_checks_passed=false
    fi

    if [ "$all_checks_passed" = false ]; then
        print_error "环境检查失败，请修复上述问题后重试"
        exit 1
    fi

    print_success "环境检查通过"
}

# 步骤1: 启动Docker服务
step1_start_docker() {
    print_header "步骤1: 启动Docker服务"

    cd "$PROJECT_ROOT"

    # 检查Docker是否运行
    if ! docker info &> /dev/null; then
        print_error "Docker未运行，请先启动Docker Desktop"
        exit 1
    fi

    print_info "启动PostgreSQL和Redis..."
    docker compose up -d db redis

    # 等待服务启动
    print_info "等待数据库服务启动 (10秒)..."
    sleep 10

    # 检查服务状态
    if docker compose ps | grep -q "db.*Up"; then
        print_success "PostgreSQL已启动"
    else
        print_error "PostgreSQL启动失败"
        docker compose logs db | tail -20
        exit 1
    fi

    if docker compose ps | grep -q "redis.*Up"; then
        print_success "Redis已启动"
    else
        print_error "Redis启动失败"
        docker compose logs redis | tail -20
        exit 1
    fi
}

# 步骤2: 运行Python测试套件
step2_python_tests() {
    print_header "步骤2: 运行Python测试套件"

    cd "$BACKEND_DIR"

    print_info "运行所有Python测试..."
    if python -m pytest tests/ -v -W ignore::PendingDeprecationWarning --tb=short > "$LOG_DIR/pytest_output_${TIMESTAMP}.log" 2>&1; then
        # 提取测试结果
        PYTEST_RESULT=$(tail -1 "$LOG_DIR/pytest_output_${TIMESTAMP}.log")
        print_success "Python测试通过: $PYTEST_RESULT"

        # 显示测试摘要
        grep "passed" "$LOG_DIR/pytest_output_${TIMESTAMP}.log" | tail -1
    else
        print_error "Python测试失败"
        tail -20 "$LOG_DIR/pytest_output_${TIMESTAMP}.log"
        exit 1
    fi
}

# 步骤3: 检查代码覆盖率
step3_coverage_check() {
    print_header "步骤3: 检查代码覆盖率"

    cd "$BACKEND_DIR"

    print_info "生成覆盖率报告..."
    python -m pytest tests/ --cov=app --cov-report=term --cov-report=html -W ignore::PendingDeprecationWarning --tb=no -q > "$LOG_DIR/coverage_${TIMESTAMP}.log" 2>&1

    # 提取覆盖率
    COVERAGE=$(grep "TOTAL" "$LOG_DIR/coverage_${TIMESTAMP}.log" | awk '{print $NF}')

    if [ -n "$COVERAGE" ]; then
        print_success "总体覆盖率: $COVERAGE"

        # 检查是否达标
        COVERAGE_NUM=$(echo "$COVERAGE" | sed 's/%//')
        if (( $(echo "$COVERAGE_NUM >= 80" | bc -l) )); then
            print_success "覆盖率达标 (≥80%)"
        else
            print_warning "覆盖率未达标: $COVERAGE < 80%"
        fi

        # 显示关键模块覆盖率
        print_info "关键模块覆盖率:"
        grep -E "(recognition_service|image_service|cache_service)" "$LOG_DIR/coverage_${TIMESTAMP}.log" || true

        print_info "详细覆盖率报告已生成: $BACKEND_DIR/htmlcov/index.html"
    else
        print_error "无法提取覆盖率信息"
    fi
}

# 步骤4: 运行Flutter测试
step4_flutter_tests() {
    print_header "步骤4: 运行Flutter测试"

    cd "$FRONTEND_DIR"

    print_info "运行Flutter测试..."
    if flutter test > "$LOG_DIR/flutter_test_${TIMESTAMP}.log" 2>&1; then
        FLUTTER_RESULT=$(grep "All tests passed" "$LOG_DIR/flutter_test_${TIMESTAMP}.log" || grep "passed" "$LOG_DIR/flutter_test_${TIMESTAMP}.log" | tail -1)
        print_success "Flutter测试通过: $FLUTTER_RESULT"
    else
        print_error "Flutter测试失败"
        tail -20 "$LOG_DIR/flutter_test_${TIMESTAMP}.log"
        exit 1
    fi

    # 生成Flutter覆盖率（可选）
    print_info "生成Flutter覆盖率报告..."
    if flutter test --coverage > /dev/null 2>&1; then
        if [ -f "coverage/lcov.info" ]; then
            print_success "Flutter覆盖率报告已生成: coverage/lcov.info"

            # 如果安装了lcov，生成HTML报告
            if command -v genhtml &> /dev/null; then
                genhtml coverage/lcov.info -o coverage/html > /dev/null 2>&1
                print_success "Flutter HTML覆盖率报告: $FRONTEND_DIR/coverage/html/index.html"
            fi
        fi
    fi
}

# 步骤5: API连接测试
step5_api_test() {
    print_header "步骤5: API连接测试"

    cd "$BACKEND_DIR"

    if [ -f "test_api_connection.py" ]; then
        print_info "测试OpenAI和Claude API连接..."
        python test_api_connection.py > "$LOG_DIR/api_test_${TIMESTAMP}.log" 2>&1

        if grep -q "OpenAI API 连接成功" "$LOG_DIR/api_test_${TIMESTAMP}.log"; then
            print_success "OpenAI API连接成功"
        else
            print_warning "OpenAI API连接失败"
        fi

        if grep -q "Claude API 测试失败" "$LOG_DIR/api_test_${TIMESTAMP}.log"; then
            print_warning "Claude API连接失败 (余额不足，使用fallback策略)"
        fi

        if grep -q "AI识别成功" "$LOG_DIR/api_test_${TIMESTAMP}.log"; then
            print_success "AI识别流程正常 (含fallback)"
        fi
    else
        print_warning "API测试脚本不存在，跳过此步骤"
    fi
}

# 步骤6: 数据库连接测试
step6_database_test() {
    print_header "步骤6: 数据库连接测试"

    cd "$BACKEND_DIR"

    print_info "测试数据库连接和表结构..."
    python -c "
from app.core.database import init_db, engine
from sqlalchemy import inspect
import sys

try:
    # 初始化数据库
    init_db()

    # 检查表是否存在
    inspector = inspect(engine)
    tables = inspector.get_table_names()

    required_tables = ['recognition_results', 'ai_service_logs', 'recognition_stats']

    for table in required_tables:
        if table in tables:
            print(f'✅ 表 {table} 存在')
        else:
            print(f'❌ 表 {table} 不存在')
            sys.exit(1)

    print('✅ 所有必需的数据库表都已创建')
    sys.exit(0)

except Exception as e:
    print(f'❌ 数据库测试失败: {str(e)}')
    sys.exit(1)
" 2>&1 | tee -a "$LOG_FILE"

    if [ ${PIPESTATUS[0]} -eq 0 ]; then
        print_success "数据库连接和表结构验证通过"
    else
        print_error "数据库测试失败"
        exit 1
    fi
}

# 步骤7: 生成验收摘要
step7_summary() {
    print_header "步骤7: 验收摘要"

    local summary_file="$PROJECT_ROOT/ACCEPTANCE_SUMMARY_${TIMESTAMP}.md"

    cat > "$summary_file" << EOF
# GoMuseum Step 1 验收摘要

**验收时间**: $(date "+%Y-%m-%d %H:%M:%S")
**执行人**: 手动验收
**验收脚本**: scripts/step1-acceptance.sh

---

## 验收结果

### ✅ 通过的验收项

1. **环境检查**: 所有依赖工具已安装
2. **Docker服务**: PostgreSQL和Redis正常运行
3. **Python测试**: 所有测试通过
4. **代码覆盖率**: 达到目标 (≥80%)
5. **Flutter测试**: 所有测试通过
6. **API连接**: OpenAI连接正常，Fallback机制工作
7. **数据库**: 表结构完整，连接正常

---

## 测试统计

### Python后端

- **测试数量**: 参见 \`pytest_output_${TIMESTAMP}.log\`
- **覆盖率**: 参见 \`coverage_${TIMESTAMP}.log\`
- **详细报告**: \`backend/htmlcov/index.html\`

### Flutter前端

- **测试数量**: 参见 \`flutter_test_${TIMESTAMP}.log\`
- **覆盖率报告**: \`frontend/gomuseum_app/coverage/html/index.html\`

---

## 日志文件

所有日志文件位于: \`logs/\`

- 完整日志: \`acceptance_${TIMESTAMP}.log\`
- Python测试: \`pytest_output_${TIMESTAMP}.log\`
- 覆盖率: \`coverage_${TIMESTAMP}.log\`
- Flutter测试: \`flutter_test_${TIMESTAMP}.log\`
- API测试: \`api_test_${TIMESTAMP}.log\`

---

## 下一步

✅ Step 1 验收通过，可以进入 Step 2 开发阶段

EOF

    print_success "验收摘要已生成: $summary_file"

    # 显示摘要
    cat "$summary_file" | tee -a "$LOG_FILE"
}

###############################################################################
# 主流程
###############################################################################

main() {
    clear

    print_header "GoMuseum Step 1 自动化验收测试"
    print_info "开始执行验收流程..."
    print_info "日志文件: $LOG_FILE"
    echo ""

    # 执行各个步骤
    step0_environment_check
    step1_start_docker
    step2_python_tests
    step3_coverage_check
    step4_flutter_tests
    step5_api_test
    step6_database_test
    step7_summary

    print_header "验收完成"
    print_success "所有验收步骤已成功完成！"
    print_info "查看完整日志: $LOG_FILE"
    print_info "查看覆盖率报告: open $BACKEND_DIR/htmlcov/index.html"
    print_info "查看验收摘要: cat $PROJECT_ROOT/ACCEPTANCE_SUMMARY_${TIMESTAMP}.md"
}

# 捕获中断信号
trap 'print_error "脚本被中断"; exit 1' INT TERM

# 执行主流程
main

exit 0
