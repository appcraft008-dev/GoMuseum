# GoMuseum 脚本工具集

本目录包含GoMuseum项目的自动化脚本和工具。

---

## 📋 脚本列表

### 1. 自动化验收测试

**文件**: `acceptance-test-step1-2-3.sh`

**用途**: 在提交代码前验证Step 1-2-3的所有关键功能,确保CI能通过。

**使用方法**:

```bash
# 从项目根目录运行
./scripts/acceptance-test-step1-2-3.sh
```

**检查内容**:

- ✅ Step 1: 后端识别功能 (API + AI + 数据库)
- ✅ Step 2: 感知哈希缓存优化
- ✅ Step 3: Flutter UI界面
- ✅ 环境配置和依赖
- ✅ 代码质量 (Black, Flake8, Flutter analyze)
- ✅ 测试覆盖率 (目标85%+)

**输出**:

- 实时彩色输出 (通过/失败/警告)
- 详细报告文件 `acceptance-test-report-*.txt`
- 日志文件 `/tmp/pytest_*.log` 和 `/tmp/flutter_*.log`

**退出码**:

- `0` - 所有测试通过,可以安全提交
- `1` - 发现错误,需要修复

**文档**: 详见 [`docs/development/ACCEPTANCE_TEST_GUIDE.md`](../docs/development/ACCEPTANCE_TEST_GUIDE.md)

---

### 2. 环境验证脚本

**文件**: `verify-environment.sh`

**用途**: 验证开发环境是否正确配置。

**使用方法**:

```bash
./scripts/verify-environment.sh
```

**检查内容**:

- Node.js, npm, Python, Docker, PostgreSQL, Redis, Flutter

---

## 🚀 快速开始

### 第一次使用

```bash
# 1. 给脚本添加执行权限 (仅需一次)
chmod +x scripts/*.sh

# 2. 运行环境验证
./scripts/verify-environment.sh

# 3. 运行验收测试
./scripts/acceptance-test-step1-2-3.sh
```

### 日常使用

```bash
# 每次提交代码前运行
./scripts/acceptance-test-step1-2-3.sh

# 如果通过,提交代码
git add .
git commit -m "your commit message"
git push
```

---

## 📊 测试统计示例

```
========================================
验收测试报告
========================================

测试统计:
  ✓ 通过: 45
  ✗ 失败: 0
  ⚠ 警告: 3

╔════════════════════════════════════════╗
║  ✓ 验收测试通过 - 可以安全提交代码!  ║
╚════════════════════════════════════════╝
```

---

## 🔧 故障排查

### 常见问题

1. **权限错误**: `chmod +x scripts/*.sh`
2. **虚拟环境问题**: `cd backend && python -m venv .venv`
3. **依赖缺失**:
   - 后端: `pip install -e ".[dev,test]"`
   - 前端: `flutter pub get`

详细排查指南请查看验收测试文档。

---

## 📝 添加新脚本

当你创建新的脚本时:

1. 添加执行权限: `chmod +x scripts/your-script.sh`
2. 在本文件中添加文档
3. 遵循Shell脚本最佳实践:
   - 使用 `set -e` (遇到错误立即退出)
   - 添加详细注释
   - 提供清晰的错误提示
   - 使用颜色区分输出级别

---

**维护者**: GoMuseum开发团队
**最后更新**: 2025年10月10日
