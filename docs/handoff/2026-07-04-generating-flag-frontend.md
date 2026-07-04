# 交接（前端）：懒生成等待提示三态化（`generating` 字段）

> 后端已先行（staging）：content 端点新增**加法字段** `generating: bool`——true = 该件正在懒生成/懒翻译（信号源=后端任务锁，精确可靠）。
> 解决 #162 轮询的三个隐患：真 empty 件被骗着转圈、轮询固定次数瞎猜、失败后无重试入口。

## 字段

`GET /api/v1/museums/{slug}/objects/{qid}/content?language=xx` 响应新增：
```json
{ "status": "ready | empty | stub", "generating": true, ... }
```
老字段全部不变（纯加法）。

## 要改：轮询判断从"只看 status"升级为三态

| 条件 | UI | 轮询 |
|---|---|---|
| `generating == true` | 「讲解生成中，约 1-3 分钟」（现有文案） | **继续轮询**（不设固定次数上限，以 generating 为准；安全兜底可设 15 分钟硬顶） |
| `generating == false` 且 `status == "empty"` 且无内容 | 「该藏品资料不足，暂无讲解」——**不转圈不骗人** | **立刻停止** |
| `generating == false` 且 `status == "stub"` 且无内容 | 「讲解暂未生成」＋**重试入口**（重新请求 content 即再次触发懒生成） | 停止，等用户点重试 |
| 有内容（guide/tabs 非空） | 正常渲染 | 停止 |

注意区分：`status=empty` 在生成**进行中**也会出现（内容还没落库）——所以判断顺序必须**先看 `generating`**，再看 status。

## 边界说明

- 懒翻译（切语言后内容缺）同样会置 `generating=true`（同一把锁），三态逻辑天然覆盖，无需特判
- 失败场景：后端生成失败会清锁 → `generating` 变 false、内容仍缺 → 落到"重试"态；用户点重试 = 重新拉 content（后端自动再触发）
- 老 App 兼容：不读该字段则行为照旧，无风险

## staging 验证法

1. 找一件"待完善"的藏品点开 → 应显示"生成中"且 `generating=true`（可用 curl 复核）
2. 等 2-3 分钟内容出现 → 轮询自动停
3. 无材料的 empty 件（问后端要样本 qid）→ 应直接显示"资料不足"，不转圈

## 相关

- 契约：`docs/architecture/museum-api-contract.md` §content_status（generating 字段说明）
- 后端实现：`lazy.lock_active`（任务锁即信号）
