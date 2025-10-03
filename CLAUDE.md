# Claude Code 项目规则 (claude.md)

## 代码风格

- Python 遵循 PEP8。
- 使用 black 和 isort 保持一致格式。
- Flutter 代码必须通过 flutter format 和 flutter analyze。

## Commit 规范

- 所有提交遵循 Conventional Commits：
  - `feat: 新功能`
  - `fix: 修复`
  - `docs: 文档`
  - `style: 风格调整`
  - `refactor: 重构`
  - `test: 测试`
  - `chore: 构建/工具`

rules:

- 所有 Python 代码必须通过 Black 格式化
- 所有 TS/React 代码必须通过 ESLint + Prettier
- Git 提交信息必须符合 Conventional Commits
- 写功能必须包含相应的测试文件

# Claude Code Rules (GoMuseum)

## 全局开发规范

- Python: Black + Flake8，必须通过 CI
- Flutter: `analysis_options.yaml`
- Git Flow: feature/\* → staging → main，main 分支受保护
- 测试覆盖率目标：单元 ≥80%，集成 ≥70%，总体 ≥75%
- 严禁提交明文密码/API key，统一使用 `.env`

## 项目初始化规则

- 目录结构：backend(FastAPI) / frontend(Flutter Clean Architecture) / deployment / monitoring / docs / scripts / tools / .github
- 配置文件：`.env.example`、`docker-compose.*.yml`、`pyproject.toml`、`pubspec.yaml`、`Makefile`
- 基础代码：后端 API/DB/认证框架，前端依赖注入/网络层/路由/国际化
- 开发工具：pre-commit hooks、pytest、flutter test、VSCode 配置

## 验收要求

- `verify-environment.sh`、`acceptance-test.sh` 必须通过
- `flutter analyze && flutter test` ✅
- `pytest --cov` ✅
- Docker Compose 启动 PostgreSQL + Redis + 前后端 ✅
- GitHub Actions CI/CD 工作流变绿 ✅

## 说明

- 本文件定义项目范围规则
- 具体开发可调用 `/agents` 下的专业 agent（如 backend-expert、flutter-architect、devops-specialist），Claude Code 将优先使用全局 agent，若无则按本文件中的角色说明临时扮演
