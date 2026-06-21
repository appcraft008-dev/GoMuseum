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

## 架构约束与原则（项目级硬约束，开发不得走偏）

### 前后端解耦 · 契约为边界

- **边界 = API 契约**。后端与前端经稳定契约通信、各自独立演进。判断"某改动归后端还是前端"：
  **它需不需要改契约（新数据/新字段/新端点）？需要 → 后端这侧的契约改动是后端任务；纯呈现（布局/tab/连播/滚动方式）→ 纯前端，不碰后端。**
- **纯 UI/呈现变化绝不回改后端**；只有"需要新数据/新功能"才动契约。

### 契约前向兼容 · 加法优先（**最高优先级，违反会炸线上**）

- **后端升级必须前向兼容当前已部署/老前端**（尤其 Play 审核中、用户已装的 App）。后端可先行、独立部署。
- **只许加法（additive）**：新端点不动老端点；**新增字段不破坏老解析**。
- **破坏性变更（改字段语义/删字段）→ 版本化端点**（`/v2/...`），让老 App 继续走老的。永远优先加法，而非修改。
- **server-driven 优先**：能用"改后端、免 Play 审核"解决的，不靠发新 App 版本。
- ⚠️ 教训（2026-06-16 事故）：富化数据把 `title_zh` 变 null，破了已装 App 的 `as String` 强转 → 馆藏页整页崩。

### 升级场景（标准三类）

1. **后端升级**（提供新数据/新功能，前向兼容不破前端）→ 之后**前端升级**配合用新功能。
2. **前端升级**（纯 UI，不涉功能、不改契约）。
3. **纯后端升级**（仅架构/重构，无新功能，契约不变，前端无感）。
   （第四类破坏性契约变更 → 避免；必须时走版本化端点。）

### 数据契约容错（前后端两侧都要做）

- **Flutter 解析 API 字段：禁止裸 `as String`**（及其它非空强转）。可能缺的字段一律 `as T? ?? <fallback>`。
- **后端对易缺字段给回退**（富化/多语言数据天然缺字段，如缺中文标题 → 回退英文/qid）。
- 详见记忆 `enrichment-data-frontend-contract`。

### AI 内容质量原则（本项目是 AI 内容产品）

- **正确性靠构造，不靠人审对错**：AI 生成内容必须**接地（grounded）于来源明确的事实/材料**，**不许脑补**，可溯源；
  自动事实一致性校验删不支持内容；**宁缺毋滥**（源薄则少写/标待完善，不凑字）。
- **人只审形式安全**（空段/乱码/语言/冒犯），**不审事实对错**（管理员非领域专家）；错漏靠**用户反馈兜底**。
- **生成一次、永久落库**：AI 产出（讲解/音频等）必须持久化（DB/对象存储），**不得每次请求重复调用 AI 重付费**。
- 生成内容**原创表达、不照搬**有版权的源文（如 Wikipedia CC-BY-SA）；只取事实。

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

## 分支与 CI/CD 规范

### 分支模型（三层）

- `main`：生产分支，受保护。**禁止直推/force-push**，只接受来自 `staging` 的 PR。
- `staging`：集成/预发分支，受保护。禁止直推，接受来自 `feature/*`（及 `hotfix/*`）的 PR。
- `feature/{描述}`：开发分支，可自由 push。命名 `feature/<kebab-描述>`。
- `hotfix/{描述}`：线上紧急修复分支（见下方生命周期"例外"）。

### PR 流向（唯一允许路径）

    feature/{*}  ──PR──▶  staging  ──PR──▶  main

- 向 `main` 提 PR 的 head **必须是 `staging`**（`branch-guard` workflow 强制，违者 CI 直接失败）。
- 所有 PR 一律 **Squash Merge**，主干上每个 PR 只留一条干净提交。

### feature 分支生命周期（默认串行开发）

- 默认同一时间只推进**一个** `feature/*`，避免多分支并行混乱。
- 一个 feature 合并入 `staging` 且 CI/CD 完成后：**立即删除该 feature 分支**
  （合并时用 `gh pr merge --delete-branch`，或 `git push origin --delete <branch>` + 本地 `git branch -d`）。
  ⚠️ 仓库级 `delete_branch_on_merge` 已**关闭**——否则 `staging→main` 合并会把 `staging` 也删掉。
  feature 分支靠合并时的 `--delete-branch` 逐个删，`staging`/`main` 永不自动删。
- 回到 `staging`、确定下一个特性/修复后，**从最新 `staging` 切出新的 `feature/*`** 再动手。
- **例外**：不能等的线上紧急修复用 `hotfix/*` 分支并行处理，同样 PR→staging→main，完成即删。

### CI/CD 触发（按改动分流的 CI + 全自动 path-aware 部署）

**CI（只在 PR 上跑，按改动分流）**

- **CI 仅在 `pull_request`（目标 `staging`/`main`）时跑**——合并前的唯一质量门；合并后的 push **不再重复跑 CI**（去重）。
- **按改动分流**：`changes` job（`dorny/paths-filter`）检测改了 backend/frontend/workflow；`backend-tests` 仅在后端(或 workflow)改动时跑、`flutter-tests` 仅在前端(或 workflow)改动时跑；`ci-status` 把 **skipped 视为通过**。gitleaks/Trivy/build-check 无条件跑（安全扫描 + PR 锚点）。
- `feature/*` / `hotfix/*` 的 push 不触发远端 CI——快速反馈交给本地钩子。
- CI 用 `concurrency: cancel-in-progress: true`（同分支新提交取消旧 CI）。

**CD（push 触发，自动 + path-aware）**

- **push `staging`（合并后）→ 自动部署 staging**（端口 8101）；**push `main`（合并后）→ 自动部署 prod**（端口 8100）。
- **path-aware**：仅当 `backend/**` 改动时才部署（只改前端/文档/workflow 不触发，避免 no-op）；`workflow_dispatch` 手动部署对任一环境**强制执行**（兜底）。
- Deploy 用 `concurrency: cancel-in-progress: false`（同目标串行，防并发 compose recreate 撞名残留）。

**自动同步**

- 合入 `main` 后，`sync-main-to-staging` 自动把 main 同步回 staging（带 `[skip ci]`），**取代手动 force-sync**。

> ⚠️ GitHub 坑：改 `.github/workflows/` 本身的提交/PR 有时不自动触发任何 workflow——补推一个**不改 workflow 的普通提交**（如 `git commit --allow-empty`）重触发即可。

### 本地提交前检查（让远端 CI 专注 UC 正确性，而非格式）

- ⚠️ husky 钩子必须**可执行**（`chmod +x .husky/pre-commit .husky/pre-push`）；否则被 git 忽略、格式化静默不跑，导致一路 `--no-verify`。
- **pre-commit**（仅改动文件，快，只做**格式化**不做 lint）：
  - `backend/**/*.py` → black + isort
  - `**/*.dart` → dart format
  - `*.{js,ts,jsx,tsx,json,md,yml,yaml}` → eslint --fix + prettier
  - （flake8 等 lint 不放进阻塞钩子：存量代码违规多、且 CI 不跑 flake8；需要时单独跑 `flake8 backend`。）
- **pre-push**（兜底，防未格式化代码上远端）：black --check、dart format --set-exit-if-changed；**不跑全量测试**。
- 本地需安装：`black isort`（后端）与 Dart/Flutter SDK（前端）；缺失时 pre-push 会跳过对应检查。
- 严禁提交明文密码/API key/`.env`/虚拟环境（`.venv`）/构建产物；`.gitignore` 与 `.dockerignore` 必须覆盖。
- CI 用 **gitleaks**（扫密钥）+ **Trivy**（扫依赖漏洞）双重防护。

### 提 PR

- 用 `/pr` slash 命令创建 PR（按当前分支自动选 base：`feature|hotfix → staging`，`staging → main`），无需进 GitHub 页面。

### 受保护分支规则（main 与 staging 一致）

- 必须经 PR、CI 状态检查全绿、分支与 base 同步后方可合并；禁止直推与 force-push。
