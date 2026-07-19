# names 的 Batch 模式设计(成本工程②,50% off + 免长时盯守)

> 2026-07-19 定稿。背景:names 显示名翻译走 gpt-4o,是上馆成本 98%(橘园实测 $0.59/$0.60);
> 卢浮宫 18.4k 件同步跑 ~60h+$75。OpenAI Batch API 半价 + 异步,规模馆的刚需。
> 本 spec = A(Batch 模式);B(卢浮宫 v1)单独 spec,消费本件。已实测部门清单备好
> (12 收藏实体,绘画部 Q3044768=10.3k 最大)。

## 原则

- **质量零变化**:同 prompt(`build_name_translation_prompt`)同模型(gpt-4o),只是打包提交;
  回填复用现有 `_fill_i18n` 合并语义 + 剥书名号清洗。
- **只 Batch 化 translate_name 段**(作品标题+作者名翻译=成本大头);权威标签抓取(网络,免费)
  保持同步;国籍/代表作 i18n 小项保持同步(量小,YAGNI)。
- **失败不发明新机制**:失败行=该实体该语言仍缺 → 现有 names 幂等重跑自动补。

## §1 CLI 形态

```
onboard <slug> names --target prod --use-batch          # 全新跑
onboard <slug> names --target prod --use-batch --batch-job <id>   # 断点续传(跳过收集/提交,直接轮询+回填)
```

单命令四阶段:**收集**(全馆扫缺语言 → JSONL,每行 `custom_id = "<entity_type>|<key>|<lang>"`,
entity_type∈{title,artist},key=对象qid/作者qid)→ **提交**(`client.batches.create`,
endpoint=/v1/chat/completions,completion_window=24h)→ **轮询**(每 60s 查 status,
detached+日志挂着,纪律⑥)→ **回填**(下载 output,逐行解析 custom_id 定位实体,
剥号清洗后合并写库,分批 commit 纪律②)。

- **job 状态落盘** `/tmp/<slug>_names_batch.json`(job_id + 提交时间 + 计数)——中途死
  `--batch-job` 续,不重付费;
- 不带 `--use-batch` = 现行同步路径原样(小馆/增量补漏);
- staging 护栏兼容:`--use-batch` 同样受 `staging_limit`(小样本收集→小 JSONL→真提交,
  这正是全链验证方式)。

## §2 记账与价目

回填时逐行读 batch output 的 usage → `record_llm_usage("names", "gpt-4o@batch", in, out)`;
`llm_cost_report.PRICES` 加 `"gpt-4o@batch": (1.25, 5.00)`(半价)——报告如实反映折扣。

## §3 实现落点

- 新模块 `backend/app/services/enrichment/batch_names.py`:
  - `collect_missing(db, slug, langs) -> list[BatchTask]`(dataclass: custom_id/system/user)
    ——扫描逻辑与 backfill_display_names 的"缺判定"同源(按语言维度);
  - `submit(tasks, client) -> job_id`(写 JSONL→files.create→batches.create);
  - `poll(job_id, client) -> output_lines`(60s 间隔,终态 completed/failed/expired);
  - `apply(db, lines) -> dict`(custom_id 反解析→剥号→合并 title_i18n/name_i18n→分批 commit;
    坏行跳过计数)。全部注入可测(fake client)。
- `onboard.py` cmd_names 加 `--use-batch/--batch-job` wiring。

## §4 验证

- 单测(fake client/sqlite):收集只收缺的(权威标签在的语言不进 JSONL)/custom_id 往返解析/
  回填合并+剥号/坏行跳过/job 状态落盘续传;
- **真钱全链验证:staging 护栏内小样本**(≤50 件)真提交一次 Batch 走通四阶段;
- 验收:同批数据 Batch vs 同步产出抽查一致;`llm_cost_report` 显示 `gpt-4o@batch` 半价行;
  断点续传实测(kill 后 --batch-job 恢复)。

## 非目标(留 B/后续)

- 卢浮宫多部门 QID 配置/上馆(spec B);
- generate/translate 的 Batch 化(懒生成是用户等待路径,⛔契约红线不 Batch;
  全馆 translate 补语种若未来需要再扩,同构复用本模块)。
