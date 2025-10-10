# GoMuseum UI Package v1.0

## 包含内容

- `docs/GoMuseum-UI-Design-v1.0.md`：完整设计方案
- `tokens/gomuseum.tokens.json`：Figma Tokens（Tokens Studio 兼容）
- `assets/i18n/en.arb`、`assets/i18n/zh.arb`：多语言样例
- `lib/theme/*`、`lib/ui/*`、`lib/widgets/*`：Flutter 主题与 UI 骨架（示例占位，便于 Claude Code/Codex 直接接线）

## 使用方法

1. **Figma**：Tokens Studio 插件导入 `tokens/gomuseum.tokens.json`；按文档建立组件与页面。
2. **Flutter**：将 `lib/` 和 `assets/` 拷贝到项目；在 `MaterialApp(theme: buildAppTheme())` 引入主题；配置 i18n。
3. **订阅与语音**：按 `TODO` 钩子接入 IAP/GPB、TTS 与语音识别服务。

## 说明

- 本包中的代码为 UI 占位与演示用途，不包含业务逻辑与联网。
- 设计与实现保持模块化，便于后续扩展“离线包/禁拍照模式/AR/路线规划”等。
