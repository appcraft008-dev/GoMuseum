# GoMuseum 自动化验收测试指南

**文档版本**: 1.0
**创建日期**: 2025年10月10日
**适用范围**: Step 1-2-3 MVP功能验收

---

## 📋 概述

本文档介绍如何使用自动化验收测试脚本,在提交代码到GitHub之前验证Step 1-2-3的所有关键功能,确保CI能够通过。

### 验收覆盖范围

- ✅ **Step 1**: 图像识别功能 (后端API + 数据库 + AI集成)
- ✅ **Step 2**: 感知哈希缓存优化 (跨用户智能缓存)
- ✅ **Step 3**: UI界面开发 (Flutter组件 + 路由 + 国际化)

---

## 🚀 快速开始

### 1. 运行验收测试

```bash
# 从项目根目录运行
./scripts/acceptance-test-step1-2-3.sh
```

### 2. 查看结果

脚本会自动检查所有关键功能,并在最后显示:

```
╔════════════════════════════════════════╗
║  ✓ 验收测试通过 - 可以安全提交代码!  ║
╚════════════════════════════════════════╝

建议的Git提交流程:
  1. git add .
  2. git commit -m "feat: complete Step 1-2-3 MVP features"
  3. git push origin feature/step3-ui-develop
```

**或者** (如果有错误):

```
╔════════════════════════════════════════╗
║  ✗ 验收测试失败 - 请修复错误后重试!  ║
╚════════════════════════════════════════╝

发现 3 个错误,请检查以下日志:
  - /tmp/pytest_*.log (后端测试)
  - /tmp/flutter_*.log (Flutter)
```

---

## 🧪 测试检查项

### 阶段 0: 环境验证

- [x] Node.js 安装检查
- [x] Python 安装检查
- [x] Flutter 安装检查
- [x] Docker 安装检查 (可选)
- [x] Git分支检查
- [x] 未提交修改检查

### Step 1: 后端识别功能

#### 1.1 环境检查
- [x] Python虚拟环境存在 (`.venv/`)
- [x] 虚拟环境激活成功
- [x] 关键依赖安装 (fastapi, imagehash, pytest)

#### 1.2 代码质量
- [x] Black 格式检查 (`black --check app/ tests/`)
- [x] Flake8 语法检查 (`flake8 app/ --max-line-length=100`)

#### 1.3 单元测试
- [x] `test_image_service.py` 测试通过
- [x] `test_cache_service.py` 测试通过
- [x] `test_recognition_service.py` 测试通过

#### 1.4 测试覆盖率
- [x] 总覆盖率 ≥85%
- [x] 提取并显示实际覆盖率百分比

#### 1.5 关键文件检查
验证以下文件存在:
- `app/api/v1/endpoints/recognition.py`
- `app/services/recognition_service.py`
- `app/services/ai_service.py`
- `app/services/cache_service.py`
- `app/services/image_service.py`
- `app/models/recognition_result.py`
- `tests/unit/services/test_recognition_service.py`

#### 1.6 数据库迁移
- [x] `alembic/versions/` 目录存在
- [x] 至少3个迁移文件 (001, 002, 003)

### Step 2: 缓存优化

#### 2.1 ImageHash库检查
- [x] `imagehash` 库安装并可导入
- [x] 显示ImageHash版本号

#### 2.2 感知哈希测试
- [x] `TestPerceptualHash` 测试通过 (10个测试)

#### 2.3 缓存服务覆盖率
- [x] `cache_service.py` 覆盖率 ≥90%

#### 2.4 关键功能验证
检查以下函数存在:
- [x] `generate_perceptual_hash()` in `image_service.py`
- [x] `hash_similarity()` in `image_service.py`
- [x] `get_similar_cached_result()` in `cache_service.py`

### Step 3: Flutter UI

#### 3.1 依赖管理
- [x] `flutter pub get` 成功
- [x] `go_router` 添加到 `pubspec.yaml`

#### 3.2 国际化
- [x] `flutter gen-l10n` 成功
- [x] 检查翻译完整性警告

#### 3.3 代码分析
- [x] `flutter analyze` 通过 (无error)
- [x] 统计error数量

#### 3.4 UI组件检查
验证16个核心文件存在:
- **主题系统** (4个): colors.dart, typography.dart, dimensions.dart, app_theme.dart
- **布局组件** (3个): app_scaffold.dart, bottom_navigation_widget.dart, app_bar_widget.dart
- **反馈组件** (3个): loading_widget.dart, error_widget.dart, empty_state_widget.dart
- **按钮组件** (1个): primary_button.dart
- **卡片组件** (1个): artwork_card.dart
- **页面** (1个): home_page.dart
- **路由** (1个): app_router.dart
- **国际化** (2个): app_en.arb, app_zh.arb

#### 3.5 国际化语言
- [x] 统计国际化文件数量 (目标6种)
- [x] 检查 EN/ZH/FR/DE/ES/IT

#### 3.6 路由集成
- [x] `GoRouter` 在 `app_router.dart` 中配置
- [x] `main.dart` 使用 `MaterialApp.router`
- [x] `main.dart` 集成主题系统

#### 3.7 Flutter测试
- [x] 查找并运行 `test/` 目录下的测试
- [x] 如果无测试则给出警告

#### 3.8 构建检查
- [x] `flutter build web` 配置验证 (非致命检查)

### 综合验收

#### 跨Step集成
- [x] 检查完成报告文档
  - `STEP1_COMPLETION_REPORT.md`
  - `STEP2_CACHE_OPTIMIZATION_COMPLETION.md`
  - `STEP3_UI_COMPLETION_REPORT.md`
- [x] 检查项目文档 (`README.md`)
- [x] 检查配置文件 (`.env.example`, `docker-compose.yml`)
- [x] 检查GitHub Actions CI配置

---

## 📊 测试报告

### 报告格式

脚本运行完成后会生成:

1. **屏幕输出**: 彩色实时输出,显示每个检查项的结果
2. **统计摘要**: 通过/失败/警告数量
3. **详细报告文件**: `acceptance-test-report-YYYYMMDD-HHMMSS.txt`
4. **日志文件**: `/tmp/pytest_*.log`, `/tmp/flutter_*.log`

### 报告示例

```
========================================
验收测试报告
========================================

测试统计:
  ✓ 通过: 45
  ✗ 失败: 0
  ⚠ 警告: 3

测试时间: 2025-10-10 14:30:22
当前分支: feature/step3-ui-develop

详细日志:
  - Backend测试: /tmp/pytest_*.log
  - Flutter分析: /tmp/flutter_*.log
```

---

## 🔧 故障排查

### 常见问题

#### 1. Python虚拟环境未激活

**错误信息**:
```
[✗ FAIL] 无法激活虚拟环境
```

**解决方法**:
```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # macOS/Linux
# 或
.venv\Scripts\activate  # Windows

pip install -e ".[dev,test]"
```

#### 2. ImageHash未安装

**错误信息**:
```
[✗ FAIL] imagehash 未安装
```

**解决方法**:
```bash
cd backend
source .venv/bin/activate
pip install imagehash
```

#### 3. Flutter依赖缺失

**错误信息**:
```
[✗ FAIL] Flutter依赖安装失败
```

**解决方法**:
```bash
cd frontend/gomuseum_app
flutter clean
flutter pub get
flutter pub run build_runner build --delete-conflicting-outputs
```

#### 4. 测试覆盖率不足

**错误信息**:
```
[⚠ WARN] 测试覆盖率 <85%
```

**解决方法**:
- 检查 `/tmp/pytest_coverage.log` 查看未覆盖的代码
- 补充测试用例
- 运行 `pytest --cov-report=html` 生成详细报告

#### 5. Flutter analyze错误

**错误信息**:
```
[✗ FAIL] Flutter analyze 发现 3 个错误
```

**解决方法**:
- 查看 `/tmp/flutter_analyze.log`
- 修复代码错误
- 运行 `flutter analyze` 验证

#### 6. 国际化文件缺失

**错误信息**:
```
[⚠ WARN] 仅有 2 种语言 (目标6种)
```

**解决方法**:
- 复制 `lib/l10n/app_en.arb` 为模板
- 创建 `app_fr.arb`, `app_de.arb`, `app_es.arb`, `app_it.arb`
- 翻译所有键值对
- 运行 `flutter gen-l10n`

---

## 🎯 最佳实践

### 提交前检查流程

```bash
# 1. 运行验收测试
./scripts/acceptance-test-step1-2-3.sh

# 2. 如果通过,查看修改
git status
git diff

# 3. 添加文件
git add .

# 4. 提交
git commit -m "feat: complete Step 1-2-3 MVP features

- Step 1: Image recognition with AI fallback
- Step 2: Perceptual hash cache optimization
- Step 3: Complete UI interface with 6 languages

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>"

# 5. 推送
git push origin feature/step3-ui-develop
```

### CI/CD集成

可以将此脚本集成到GitHub Actions:

```yaml
# .github/workflows/acceptance-test.yml
name: Acceptance Test

on: [push, pull_request]

jobs:
  acceptance:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - name: Setup Flutter
        uses: subosito/flutter-action@v2
        with:
          flutter-version: '3.35.5'
      - name: Run Acceptance Tests
        run: ./scripts/acceptance-test-step1-2-3.sh
```

---

## 📝 维护

### 更新脚本

当新增功能时,需要更新脚本:

1. **添加新检查项**: 在相应的Step section添加检查逻辑
2. **更新文件列表**: 修改 `STEP*_FILES` 数组
3. **调整阈值**: 根据实际情况调整覆盖率要求
4. **测试脚本**: 运行并验证所有检查项正常

### 版本历史

| 版本 | 日期 | 变更说明 |
|-----|------|---------|
| 1.0 | 2025-10-10 | 初始版本,支持Step 1-2-3验收 |

---

## 🆘 获取帮助

### 联系方式

- **GitHub Issues**: 报告脚本问题或功能请求
- **项目文档**: 查看 `docs/development/` 目录
- **技术支持**: tech@gomuseum.com

### 有用的命令

```bash
# 查看脚本帮助
./scripts/acceptance-test-step1-2-3.sh --help

# 仅运行后端测试
cd backend && pytest tests/ -v

# 仅运行Flutter分析
cd frontend/gomuseum_app && flutter analyze

# 生成测试覆盖率报告
cd backend && pytest --cov=app --cov-report=html
open htmlcov/index.html

# 清理临时文件
rm -f /tmp/pytest_*.log /tmp/flutter_*.log
```

---

**最后更新**: 2025年10月10日
**脚本路径**: `scripts/acceptance-test-step1-2-3.sh`
**文档版本**: 1.0
