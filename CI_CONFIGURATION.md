# GoMuseum CI/CD 配置说明

**更新时间**: 2025-10-02
**状态**: ✅ 完整测试覆盖

---

## 🎯 CI流程概览

当代码push到 `main`, `staging`, 或 `feature/**` 分支时，GitHub Actions会自动触发以下5个任务：

```
security-scan → build-check → ┬─ backend-tests → ┐
                               ├─ flutter-tests → ├─ ci-status
                               └─ sonarcloud    → ┘
```

---

## 📋 任务详情

### 1. Security Scan (安全扫描)

- **工具**: Trivy
- **扫描范围**: 整个文件系统
- **输出**: trivy-results.sarif (保存为artifact)
- **超时**: 10分钟

### 2. Build Check (构建检查)

- **运行环境**: Node.js 22.20.0
- **检查项**:
  - ✅ npm依赖安装 (`npm ci`)
  - ✅ ESLint代码检查 (`npm run lint`)
  - ✅ Node/npm版本验证
- **超时**: 5分钟

### 3. Backend Tests (Python后端测试) ⭐ 核心

- **运行环境**: Python 3.11 + PostgreSQL 16 + Redis 7
- **测试内容**:
  - ✅ 316个单元测试 (`pytest -v`)
  - ✅ 代码覆盖率: 85.31%
  - ✅ 核心服务100%覆盖率
- **数据库服务**:
  - PostgreSQL: `localhost:5432` (健康检查: pg_isready)
  - Redis: `localhost:6379` (健康检查: redis-cli ping)
- **覆盖率上传**: Codecov (flags: backend)
- **超时**: 10分钟

**环境变量**:

```bash
DATABASE_URL: postgresql://gomuseum:gomuseum_pwd@localhost:5432/gomuseum_db
REDIS_URL: redis://localhost:6379/0
```

### 4. Flutter Tests (前端测试) ⭐ 核心

- **运行环境**: Flutter 3.35.5 (stable)
- **测试内容**:
  - ✅ 59个单元测试 (`flutter test`)
  - ✅ 覆盖率报告生成 (`--coverage`)
- **覆盖率上传**: Codecov (flags: flutter)
- **超时**: 10分钟

### 5. SonarCloud (代码质量分析)

- **工具**: SonarCloud
- **分析内容**: 代码质量、安全漏洞、技术债
- **依赖**: build-check
- **超时**: 10分钟

### 6. CI Status Check (最终状态检查)

- **检查范围**: 所有前置任务
- **失败条件**: 任何核心任务失败
- **成功输出**:
  ```
  ✅ All CI checks passed!
  📊 Test Summary:
    - Backend: 316 Python tests
    - Frontend: 59 Flutter tests
    - Coverage: 85.31%
  ```

---

## 🔍 测试覆盖详情

### Python后端 (316个测试)

- **test_recognition_service.py**: 22个测试 (100%覆盖率)
- **test_image_service.py**: 20个测试 (100%覆盖率)
- **test_cache_service.py**: 40个测试 (100%覆盖率)
- **其他服务**: 234个测试

### Flutter前端 (59个测试)

- **recognition功能**: 48个测试
  - RecognizeArtworkUseCase: 10个测试
  - RecognitionRepositoryImpl: 9个测试
  - RecognitionProvider: 12个测试
  - RecognitionRemoteDataSource: 13个测试
  - RecognitionLocalDataSource: 4个测试
- **widget测试**: 1个测试

---

## ⚙️ 本地运行CI测试

### 完整验收测试

```bash
bash scripts/step1-acceptance.sh
```

### 单独运行后端测试

```bash
cd backend
pytest -v --cov=app --cov-report=term-missing -W ignore::PendingDeprecationWarning
```

### 单独运行前端测试

```bash
cd frontend/gomuseum_app
flutter test --coverage
```

### 运行Linting检查

```bash
npm run lint
```

---

## 📊 所需Secrets

在GitHub仓库设置中需要配置以下secrets：

| Secret名称      | 用途              | 必需    |
| --------------- | ----------------- | ------- |
| `SONAR_TOKEN`   | SonarCloud分析    | ✅ 是   |
| `CODECOV_TOKEN` | Codecov覆盖率上传 | ⚠️ 推荐 |

---

## 🚨 CI失败排查

### 1. Backend Tests失败

**可能原因**:

- PostgreSQL服务未就绪
- 依赖包安装失败
- 测试用例失败

**排查步骤**:

```bash
# 本地运行测试
docker-compose up -d db redis
cd backend
pytest -v --tb=short
```

### 2. Flutter Tests失败

**可能原因**:

- Flutter版本不匹配
- 依赖包问题
- 测试用例失败

**排查步骤**:

```bash
cd frontend/gomuseum_app
flutter clean
flutter pub get
flutter test
```

### 3. Linting失败

**可能原因**:

- ESLint配置问题
- 代码风格不符合规范

**排查步骤**:

```bash
npm run lint        # 查看错误
npm run lint:fix    # 自动修复
```

### 4. package-lock.json缺失

**解决方案**:

```bash
# 确保package-lock.json已提交
git add package-lock.json
git commit -m "chore: add package-lock.json for CI"
```

---

## ✅ CI成功标准

所有以下条件必须满足：

- ✅ Security Scan: 无高危漏洞
- ✅ Build Check: ESLint通过
- ✅ Backend Tests: 316/316测试通过
- ✅ Flutter Tests: 59/59测试通过
- ✅ Coverage: ≥85%
- ⚠️ SonarCloud: 代码质量通过（可选）

---

## 📈 持续改进

### 已完成

- ✅ 添加PostgreSQL和Redis服务
- ✅ 完整的Python后端测试
- ✅ 完整的Flutter前端测试
- ✅ 代码覆盖率上传
- ✅ ESLint代码检查
- ✅ 最终状态检查

### 待优化

- [ ] 添加性能测试
- [ ] 添加端到端测试
- [ ] 优化CI运行时间
- [ ] 添加依赖缓存

---

## 📚 相关文档

- **验收脚本**: `scripts/step1-acceptance.sh`
- **手动验收指南**: `MANUAL_ACCEPTANCE_GUIDE.md`
- **覆盖率报告**: `COVERAGE_IMPROVEMENT_REPORT.md`
