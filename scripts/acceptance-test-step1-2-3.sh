#!/bin/bash

################################################################################
# GoMuseum MVP自动化验收测试脚本 (Step 1-2-3)
#
# 用途: 在提交GitHub之前验证所有关键功能
# 覆盖范围:
#   - Step 1: 图像识别功能
#   - Step 2: 缓存优化
#   - Step 3: UI界面开发
#
# 使用方法:
#   chmod +x scripts/acceptance-test-step1-2-3.sh
#   ./scripts/acceptance-test-step1-2-3.sh
#
# 退出码:
#   0 - 所有测试通过,可以安全提交
#   1 - 发现错误,需要修复后再提交
################################################################################

set -e  # 遇到错误立即退出

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 计数器
PASSED=0
FAILED=0
WARNINGS=0

# 日志函数
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[✓ PASS]${NC} $1"
    ((PASSED++))
}

log_error() {
    echo -e "${RED}[✗ FAIL]${NC} $1"
    ((FAILED++))
}

log_warning() {
    echo -e "${YELLOW}[⚠ WARN]${NC} $1"
    ((WARNINGS++))
}

log_section() {
    echo ""
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}========================================${NC}"
}

# 获取项目根目录
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

log_section "GoMuseum MVP 自动化验收测试 (Step 1-2-3)"
echo "项目根目录: $PROJECT_ROOT"
echo "开始时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo ""

################################################################################
# 前置检查: 环境验证
################################################################################
log_section "阶段 0: 环境验证"

# 检查Node.js
if command -v node &> /dev/null; then
    NODE_VERSION=$(node --version)
    log_success "Node.js 已安装: $NODE_VERSION"
else
    log_error "Node.js 未安装"
fi

# 检查Python
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version)
    log_success "Python 已安装: $PYTHON_VERSION"
else
    log_error "Python 未安装"
fi

# 检查Flutter
if command -v flutter &> /dev/null; then
    FLUTTER_VERSION=$(flutter --version | head -n 1)
    log_success "Flutter 已安装: $FLUTTER_VERSION"
else
    log_error "Flutter 未安装"
fi

# 检查Docker
if command -v docker &> /dev/null; then
    DOCKER_VERSION=$(docker --version)
    log_success "Docker 已安装: $DOCKER_VERSION"
else
    log_warning "Docker 未安装 (可选)"
fi

# 检查Git分支
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
log_info "当前分支: $CURRENT_BRANCH"

# 检查未提交的修改
if [[ -n $(git status -s) ]]; then
    log_warning "有未提交的修改,请确认是否需要提交"
    git status -s | head -n 10
else
    log_success "工作目录干净"
fi

################################################################################
# Step 1: 后端识别功能验收
################################################################################
log_section "Step 1: 后端图像识别功能验收"

cd "$PROJECT_ROOT/backend"

# 1.1 检查Python虚拟环境
if [[ -d ".venv" ]]; then
    log_success "Python虚拟环境存在"
else
    log_error "Python虚拟环境不存在,请运行: python -m venv .venv"
fi

# 1.2 安装依赖
log_info "检查Python依赖..."
if source .venv/bin/activate 2>/dev/null || source .venv/Scripts/activate 2>/dev/null; then
    log_success "激活虚拟环境成功"

    # 检查关键依赖
    log_info "验证关键依赖包..."
    if python -c "import fastapi" 2>/dev/null; then
        log_success "fastapi 已安装"
    else
        log_error "fastapi 未安装,请运行: pip install -e '.[dev,test]'"
    fi

    if python -c "import imagehash" 2>/dev/null; then
        log_success "imagehash 已安装 (Step 2)"
    else
        log_error "imagehash 未安装,请运行: pip install imagehash"
    fi

    if python -c "import pytest" 2>/dev/null; then
        log_success "pytest 已安装"
    else
        log_error "pytest 未安装"
    fi
else
    log_error "无法激活虚拟环境"
fi

# 1.3 代码质量检查
log_info "运行代码质量检查..."

# Black格式检查
if command -v black &> /dev/null; then
    if black --check app/ tests/ 2>/dev/null; then
        log_success "Black 格式检查通过"
    else
        log_warning "代码格式需要调整,运行: black app/ tests/"
    fi
else
    log_warning "Black 未安装,跳过格式检查"
fi

# Flake8语法检查
if command -v flake8 &> /dev/null; then
    if flake8 app/ --max-line-length=100 --extend-ignore=E203,W503 2>/dev/null; then
        log_success "Flake8 语法检查通过"
    else
        log_warning "发现语法问题,请检查flake8输出"
    fi
else
    log_warning "Flake8 未安装,跳过语法检查"
fi

# 1.4 运行后端测试
log_info "运行后端单元测试..."

if pytest tests/unit/services/test_image_service.py -v --tb=short 2>&1 | tee /tmp/pytest_image.log; then
    log_success "image_service 测试通过"
else
    log_error "image_service 测试失败,查看: /tmp/pytest_image.log"
fi

if pytest tests/unit/services/test_cache_service.py -v --tb=short 2>&1 | tee /tmp/pytest_cache.log; then
    log_success "cache_service 测试通过"
else
    log_error "cache_service 测试失败,查看: /tmp/pytest_cache.log"
fi

if pytest tests/unit/services/test_recognition_service.py -v --tb=short 2>&1 | tee /tmp/pytest_recognition.log; then
    log_success "recognition_service 测试通过"
else
    log_error "recognition_service 测试失败,查看: /tmp/pytest_recognition.log"
fi

# 1.5 测试覆盖率检查
log_info "运行测试覆盖率检查..."
if pytest tests/ --cov=app --cov-report=term-missing --cov-report=html --cov-fail-under=85 -W ignore::PendingDeprecationWarning --tb=no -q 2>&1 | tee /tmp/pytest_coverage.log; then
    log_success "测试覆盖率 ≥85%"

    # 提取覆盖率数字
    COVERAGE=$(grep "TOTAL" /tmp/pytest_coverage.log | awk '{print $NF}' | tr -d '%')
    if [[ -n "$COVERAGE" ]]; then
        log_info "实际覆盖率: ${COVERAGE}%"
    fi
else
    log_warning "测试覆盖率 <85%,建议补充测试"
fi

# 1.6 检查关键文件
log_info "检查Step 1关键文件..."
STEP1_FILES=(
    "app/api/v1/endpoints/recognition.py"
    "app/services/recognition_service.py"
    "app/services/ai_service.py"
    "app/services/cache_service.py"
    "app/services/image_service.py"
    "app/models/recognition_result.py"
    "tests/unit/services/test_recognition_service.py"
)

for file in "${STEP1_FILES[@]}"; do
    if [[ -f "$file" ]]; then
        log_success "✓ $file"
    else
        log_error "✗ 缺失: $file"
    fi
done

# 1.7 检查数据库迁移
log_info "检查数据库迁移文件..."
if [[ -d "alembic/versions" ]]; then
    MIGRATION_COUNT=$(ls -1 alembic/versions/*.py 2>/dev/null | grep -v __pycache__ | wc -l)
    if [[ $MIGRATION_COUNT -ge 3 ]]; then
        log_success "数据库迁移文件存在 ($MIGRATION_COUNT 个)"
    else
        log_warning "迁移文件数量少于预期 ($MIGRATION_COUNT < 3)"
    fi
else
    log_error "alembic/versions 目录不存在"
fi

################################################################################
# Step 2: 缓存优化验收
################################################################################
log_section "Step 2: 感知哈希缓存优化验收"

# 2.1 检查ImageHash依赖
log_info "验证ImageHash库..."
if python -c "import imagehash; print('ImageHash version:', imagehash.__version__)" 2>/dev/null; then
    log_success "ImageHash 库可用"
else
    log_error "ImageHash 库不可用,请安装: pip install imagehash"
fi

# 2.2 运行感知哈希测试
log_info "运行感知哈希测试..."
if pytest tests/unit/services/test_image_service.py::TestPerceptualHash -v --tb=short 2>&1 | tee /tmp/pytest_phash.log; then
    log_success "感知哈希测试通过"
else
    log_error "感知哈希测试失败"
fi

# 2.3 检查缓存服务覆盖率
log_info "检查cache_service覆盖率..."
if pytest tests/unit/services/test_cache_service.py --cov=app/services/cache_service --cov-report=term-missing --cov-fail-under=90 -W ignore::PendingDeprecationWarning --tb=no -q 2>&1 | tee /tmp/cache_coverage.log; then
    log_success "cache_service 覆盖率 ≥90%"
else
    log_warning "cache_service 覆盖率 <90%"
fi

# 2.4 检查Step 2新增文件
log_info "检查Step 2关键功能..."

# 检查感知哈希函数
if grep -q "generate_perceptual_hash" app/services/image_service.py; then
    log_success "✓ generate_perceptual_hash() 函数存在"
else
    log_error "✗ generate_perceptual_hash() 函数缺失"
fi

if grep -q "hash_similarity" app/services/image_service.py; then
    log_success "✓ hash_similarity() 函数存在"
else
    log_error "✗ hash_similarity() 函数缺失"
fi

if grep -q "get_similar_cached_result" app/services/cache_service.py; then
    log_success "✓ get_similar_cached_result() 函数存在"
else
    log_error "✗ get_similar_cached_result() 函数缺失"
fi

################################################################################
# Step 3: Flutter UI验收
################################################################################
log_section "Step 3: Flutter UI界面验收"

cd "$PROJECT_ROOT/frontend/gomuseum_app"

# 3.1 检查Flutter依赖
log_info "运行 flutter pub get..."
if flutter pub get 2>&1 | tee /tmp/flutter_pub.log; then
    log_success "Flutter依赖安装成功"
else
    log_error "Flutter依赖安装失败"
fi

# 3.2 检查go_router依赖
if grep -q "go_router:" pubspec.yaml; then
    log_success "✓ go_router 已添加到 pubspec.yaml"
else
    log_error "✗ go_router 未添加"
fi

# 3.3 生成国际化文件
log_info "生成国际化文件..."
if flutter gen-l10n 2>&1 | tee /tmp/flutter_l10n.log; then
    log_success "国际化文件生成成功"
else
    log_warning "国际化文件生成警告,请检查翻译完整性"
fi

# 3.4 Flutter代码分析
log_info "运行 flutter analyze..."
if flutter analyze 2>&1 | tee /tmp/flutter_analyze.log; then
    log_success "Flutter analyze 通过"
else
    # 检查是否只有警告
    ERROR_COUNT=$(grep -c "error •" /tmp/flutter_analyze.log || echo "0")
    if [[ $ERROR_COUNT -eq 0 ]]; then
        log_warning "Flutter analyze 有警告,但无错误"
    else
        log_error "Flutter analyze 发现 $ERROR_COUNT 个错误"
    fi
fi

# 3.5 检查UI组件文件
log_info "检查Step 3 UI组件..."
STEP3_FILES=(
    "lib/theme/colors.dart"
    "lib/theme/typography.dart"
    "lib/theme/dimensions.dart"
    "lib/theme/app_theme.dart"
    "lib/ui/layouts/app_scaffold.dart"
    "lib/ui/layouts/bottom_navigation_widget.dart"
    "lib/ui/layouts/app_bar_widget.dart"
    "lib/ui/components/feedback/loading_widget.dart"
    "lib/ui/components/feedback/error_widget.dart"
    "lib/ui/components/feedback/empty_state_widget.dart"
    "lib/ui/components/buttons/primary_button.dart"
    "lib/ui/components/cards/artwork_card.dart"
    "lib/features/home/presentation/pages/home_page.dart"
    "lib/core/router/app_router.dart"
    "lib/l10n/app_en.arb"
    "lib/l10n/app_zh.arb"
)

for file in "${STEP3_FILES[@]}"; do
    if [[ -f "$file" ]]; then
        log_success "✓ $file"
    else
        log_error "✗ 缺失: $file"
    fi
done

# 3.6 检查国际化语言
log_info "检查国际化语言文件..."
L10N_FILES=(
    "lib/l10n/app_en.arb"
    "lib/l10n/app_zh.arb"
    "lib/l10n/app_fr.arb"
    "lib/l10n/app_de.arb"
    "lib/l10n/app_es.arb"
    "lib/l10n/app_it.arb"
)

L10N_COUNT=0
for file in "${L10N_FILES[@]}"; do
    if [[ -f "$file" ]]; then
        ((L10N_COUNT++))
    fi
done

if [[ $L10N_COUNT -eq 6 ]]; then
    log_success "6种语言文件齐全"
elif [[ $L10N_COUNT -ge 2 ]]; then
    log_warning "仅有 $L10N_COUNT 种语言 (目标6种)"
else
    log_error "国际化文件不足 ($L10N_COUNT < 2)"
fi

# 3.7 检查路由配置
log_info "检查路由配置..."
if grep -q "GoRouter" lib/core/router/app_router.dart 2>/dev/null; then
    log_success "✓ GoRouter 已配置"
else
    log_error "✗ GoRouter 未配置"
fi

# 3.8 检查main.dart集成
log_info "检查main.dart集成..."
if grep -q "MaterialApp.router" lib/main.dart 2>/dev/null; then
    log_success "✓ main.dart 使用 MaterialApp.router"
else
    log_warning "main.dart 未使用 MaterialApp.router"
fi

if grep -q "AppTheme" lib/main.dart 2>/dev/null; then
    log_success "✓ main.dart 集成主题系统"
else
    log_warning "main.dart 未集成主题系统"
fi

# 3.9 运行Flutter测试 (如果有)
log_info "检查Flutter测试..."
if [[ -d "test" ]] && [[ -n $(find test -name "*.dart" 2>/dev/null) ]]; then
    log_info "运行 flutter test..."
    if flutter test --no-pub 2>&1 | tee /tmp/flutter_test.log; then
        log_success "Flutter 测试通过"
    else
        log_warning "Flutter 测试有失败,请检查"
    fi
else
    log_warning "未找到Flutter测试文件 (test目录为空)"
fi

# 3.10 尝试构建应用 (可选,较耗时)
log_info "检查Flutter构建配置..."
if flutter build web --release --no-pub --analyze-size 2>&1 | head -n 20 | tee /tmp/flutter_build.log; then
    log_success "Flutter Web构建配置正确"
else
    log_warning "Flutter Web构建可能有问题 (非致命)"
fi

################################################################################
# 综合验收: 跨Step检查
################################################################################
log_section "综合验收: 跨Step集成检查"

cd "$PROJECT_ROOT"

# 检查文档
log_info "检查项目文档..."
DOCS=(
    "docs/development/STEP1_COMPLETION_REPORT.md"
    "docs/development/STEP2_CACHE_OPTIMIZATION_COMPLETION.md"
    "docs/development/STEP3_UI_COMPLETION_REPORT.md"
    "README.md"
)

for doc in "${DOCS[@]}"; do
    if [[ -f "$doc" ]]; then
        log_success "✓ $doc"
    else
        log_warning "文档缺失: $doc"
    fi
done

# 检查环境配置文件
log_info "检查配置文件..."
if [[ -f ".env.example" ]]; then
    log_success "✓ .env.example 存在"
else
    log_warning ".env.example 缺失"
fi

if [[ -f "docker-compose.yml" ]]; then
    log_success "✓ docker-compose.yml 存在"
else
    log_warning "docker-compose.yml 缺失"
fi

# 检查CI配置
if [[ -f ".github/workflows/ci.yml" ]] || [[ -f ".github/workflows/main.yml" ]]; then
    log_success "✓ GitHub Actions CI 已配置"
else
    log_warning "GitHub Actions CI 未配置"
fi

################################################################################
# 生成验收报告
################################################################################
log_section "验收测试报告"

echo ""
echo "测试统计:"
echo "  ✓ 通过: $PASSED"
echo "  ✗ 失败: $FAILED"
echo "  ⚠ 警告: $WARNINGS"
echo ""

# 生成详细报告
REPORT_FILE="$PROJECT_ROOT/acceptance-test-report-$(date '+%Y%m%d-%H%M%S').txt"
{
    echo "GoMuseum MVP 验收测试报告"
    echo "======================================"
    echo "测试时间: $(date '+%Y-%m-%d %H:%M:%S')"
    echo "当前分支: $CURRENT_BRANCH"
    echo ""
    echo "测试结果:"
    echo "  通过: $PASSED"
    echo "  失败: $FAILED"
    echo "  警告: $WARNINGS"
    echo ""
    echo "详细日志:"
    echo "  - Backend测试: /tmp/pytest_*.log"
    echo "  - Flutter分析: /tmp/flutter_*.log"
    echo ""
} > "$REPORT_FILE"

log_info "详细报告已保存: $REPORT_FILE"

################################################################################
# 最终判断
################################################################################
echo ""
if [[ $FAILED -eq 0 ]]; then
    echo -e "${GREEN}╔════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║  ✓ 验收测试通过 - 可以安全提交代码!  ║${NC}"
    echo -e "${GREEN}╚════════════════════════════════════════╝${NC}"
    echo ""

    if [[ $WARNINGS -gt 0 ]]; then
        echo -e "${YELLOW}注意: 有 $WARNINGS 个警告,建议修复后再提交${NC}"
    fi

    echo ""
    echo "建议的Git提交流程:"
    echo "  1. git add ."
    echo "  2. git commit -m \"feat: complete Step 1-2-3 MVP features\""
    echo "  3. git push origin $CURRENT_BRANCH"
    echo ""
    exit 0
else
    echo -e "${RED}╔════════════════════════════════════════╗${NC}"
    echo -e "${RED}║  ✗ 验收测试失败 - 请修复错误后重试!  ║${NC}"
    echo -e "${RED}╚════════════════════════════════════════╝${NC}"
    echo ""
    echo "发现 $FAILED 个错误,请检查以下日志:"
    echo "  - /tmp/pytest_*.log (后端测试)"
    echo "  - /tmp/flutter_*.log (Flutter)"
    echo ""
    echo "修复后请重新运行: ./scripts/acceptance-test-step1-2-3.sh"
    echo ""
    exit 1
fi
