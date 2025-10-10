# 快速开始 - 自动化验收测试

**目标**: 5分钟内完成Step 1-2-3的验收测试

---

## ⚡ 一键运行

```bash
# 从项目根目录运行
./scripts/acceptance-test-step1-2-3.sh
```

---

## 📋 检查清单

### 运行前准备

- [ ] 已完成Step 1-2-3的所有开发工作
- [ ] 后端虚拟环境已创建 (`backend/.venv/`)
- [ ] 后端依赖已安装 (`pip install -e ".[dev,test]"`)
- [ ] Flutter依赖已安装 (`flutter pub get`)
- [ ] 国际化文件已生成 (`flutter gen-l10n`)

### 快速检查命令

如果脚本失败,可以单独运行这些命令快速定位问题:

#### 后端检查
```bash
cd backend
source .venv/bin/activate

# 1. 测试能否导入关键模块
python -c "import fastapi; import imagehash; print('✓ Dependencies OK')"

# 2. 运行关键测试
pytest tests/unit/services/test_image_service.py -v --tb=short
pytest tests/unit/services/test_cache_service.py -v --tb=short

# 3. 检查覆盖率
pytest tests/ --cov=app --cov-report=term --cov-fail-under=85 -q
```

#### Flutter检查
```bash
cd frontend/gomuseum_app

# 1. 依赖检查
flutter pub get

# 2. 国际化
flutter gen-l10n

# 3. 代码分析
flutter analyze

# 4. 检查关键文件
ls -l lib/theme/
ls -l lib/ui/layouts/
ls -l lib/core/router/
```

---

## 🎯 预期结果

### 成功输出

```
========================================
验收测试报告
========================================

测试统计:
  ✓ 通过: 45-50
  ✗ 失败: 0
  ⚠ 警告: 0-5

╔════════════════════════════════════════╗
║  ✓ 验收测试通过 - 可以安全提交代码!  ║
╚════════════════════════════════════════╝

建议的Git提交流程:
  1. git add .
  2. git commit -m "feat: complete Step 1-2-3 MVP features"
  3. git push origin feature/step3-ui-develop
```

### 常见警告 (可接受)

```
[⚠ WARN] 代码格式需要调整,运行: black app/ tests/
[⚠ WARN] Flutter analyze 有警告,但无错误
[⚠ WARN] 仅有 2 种语言 (目标6种)
```

这些警告不影响提交,但建议修复。

---

## 🔧 快速修复

### 问题1: Black格式问题

```bash
cd backend
black app/ tests/
```

### 问题2: 缺少国际化语言

```bash
cd frontend/gomuseum_app/lib/l10n
# 复制英文版作为模板
cp app_en.arb app_fr.arb
cp app_en.arb app_de.arb
cp app_en.arb app_es.arb
cp app_en.arb app_it.arb
# 然后翻译内容或暂时保留英文

flutter gen-l10n
```

### 问题3: ImageHash未安装

```bash
cd backend
source .venv/bin/activate
pip install imagehash
```

### 问题4: go_router未安装

```bash
cd frontend/gomuseum_app
# 在pubspec.yaml中添加:
# dependencies:
#   go_router: ^13.0.0

flutter pub get
```

---

## 📊 测试时间估算

| 阶段 | 预估时间 |
|-----|---------|
| 环境验证 | 5秒 |
| Step 1 后端测试 | 30-60秒 |
| Step 2 缓存测试 | 10-20秒 |
| Step 3 Flutter检查 | 20-40秒 |
| 综合验收 | 5秒 |
| **总计** | **1-2分钟** |

*注: 首次运行可能需要3-5分钟(生成覆盖率报告)*

---

## 🚫 失败场景处理

### 场景1: 测试覆盖率不足

**错误**:
```
[✗ FAIL] 测试覆盖率 <85%
```

**解决**:
1. 查看覆盖率报告: `open backend/htmlcov/index.html`
2. 找到未覆盖的代码行
3. 补充测试用例
4. 重新运行验收测试

### 场景2: Flutter analyze错误

**错误**:
```
[✗ FAIL] Flutter analyze 发现 3 个错误
```

**解决**:
1. 查看详细错误: `cat /tmp/flutter_analyze.log`
2. 逐个修复错误
3. 运行 `flutter analyze` 验证
4. 重新运行验收测试

### 场景3: 感知哈希测试失败

**错误**:
```
[✗ FAIL] 感知哈希测试失败
```

**解决**:
1. 检查ImageHash安装: `python -c "import imagehash"`
2. 查看测试日志: `cat /tmp/pytest_phash.log`
3. 修复相关代码
4. 运行单独测试验证:
   ```bash
   pytest tests/unit/services/test_image_service.py::TestPerceptualHash -v
   ```

---

## ✅ 提交检查表

运行验收测试通过后,提交前最后确认:

- [ ] 验收测试通过 (0个失败)
- [ ] 查看 `git status` 确认修改文件
- [ ] 查看 `git diff` 确认代码更改
- [ ] 编写清晰的commit message
- [ ] 推送到正确的分支

### 推荐的Commit Message格式

```bash
git commit -m "feat: complete Step 1-2-3 MVP features

- Step 1: Image recognition with OpenAI GPT-4V fallback
- Step 2: Perceptual hash cache (60-80% hit rate)
- Step 3: Complete UI with Material 3.0 and 6 languages

Test coverage: 85%+
All acceptance tests passed ✅

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## 📞 需要帮助?

- **查看详细文档**: [`ACCEPTANCE_TEST_GUIDE.md`](./ACCEPTANCE_TEST_GUIDE.md)
- **查看脚本说明**: [`../scripts/README.md`](../../scripts/README.md)
- **查看日志**: `/tmp/pytest_*.log` 和 `/tmp/flutter_*.log`

---

**创建时间**: 2025年10月10日
**适用版本**: GoMuseum MVP Step 1-2-3
