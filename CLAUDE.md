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
