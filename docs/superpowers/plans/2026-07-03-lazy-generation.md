# 懒生成（路线图 3c）——stub 首次访问触发后台生成

> 结论回写主契约（工作纪律）。本文=设计记录。

## 目标

长尾藏品（`content_status=stub`，扩目录后 ~1800 件）不预生成；**用户首次点开时现场触发**，几分钟后再看即 `ready`。生成成本从"全馆预付"变"按需付"。

## 设计（最懒可用）

- **触发**：`GET /{slug}/objects/{qid}/content` 命中 `content_status == "stub"` → 尝试拿锁 → 拿到则 FastAPI `BackgroundTasks` 调度后台生成。`empty` **不**触发（已试过无可接地材料，防循环烧钱）。
- **锁**：`attributes["lazy_lock_at"]`（ISO 时间戳），TTL 10 分钟（进程崩溃自愈）。乐观读写：竞态窗口极小，撞了最多浪费一次生成费（落库幂等）。**不对外暴露 generating 状态**——stub 期间前端照旧显"待完善"，生成完刷新即 ready，老 App 零感知（契约形状零变化）。
- **并发上限**：进程级 `threading.Semaphore(2)`，拿不到立即放弃并清锁（下次访问重试）——保护 API 响应与 OpenAI 限速。
- **组件装配**：从 onboard 抽 `build_generation_components(slug)` 工厂（enrichment/factory.py），onboard `generate` 与懒生成共用，语言=馆配置 `languages`。
- **完成**：`generate_object` 自身置 `ready`/`empty`；runner 收尾清锁。

## 验证

- 单测（离线，注入 fake runner/组件）：锁的拿/拒/过期；stub 触发一次、ready/empty 不触发；完成清锁。
- staging 端到端：curl 点一件真实 stub → 等待 → 再取 = ready + 正文。

## 不做（YAGNI）

- 任务队列/Celery（无此基建，BackgroundTasks 够用；量大再说）。
- 前端"生成中"提示与自动刷新（另起前端任务；后端前向兼容先行）。
- empty 重试管理界面。
