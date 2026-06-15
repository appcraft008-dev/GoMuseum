---
description: 按分支规范创建 PR（feature/hotfix→staging，staging→main），免去手动进 GitHub
---

为当前分支创建 Pull Request，遵循项目分支规范 `feature/* | hotfix/* → staging → main`。

执行步骤：

1. 跑 `git branch --show-current` 取当前分支，`git status --short` 确认无未提交改动（有则提示用户先提交）。
2. 按分支名决定 base：
   - `feature/*` 或 `hotfix/*` → base = `staging`
   - `staging` → base = `main`
   - `main` → 拒绝：main 不提 PR，提示用户。
   - 其它分支名 → 询问用户目标 base。
3. `git push -u origin <当前分支>`（若远端还没有该分支）。
4. 用 `gh pr create --base <base> --head <当前分支>` 创建 PR：
   - 标题：取该分支相对 base 的提交里最有代表性的一条，或让用户确认。
   - 正文：用 `git log <base>..HEAD --oneline` 自动汇总改动要点，附 `## Summary` 和 `## Test Plan`。
   - 若 `$ARGUMENTS` 提供了标题，用它作为 PR 标题。
5. 返回 PR 链接给用户。

注意：

- 合并策略是 squash merge（在 GitHub 合并时选择，PR 创建阶段无需处理）。
- 向 `main` 的 PR 只能从 `staging` 发起（否则 branch-guard workflow 会让 CI 失败）。
- 不要自动合并 PR；创建后交给用户审阅。
