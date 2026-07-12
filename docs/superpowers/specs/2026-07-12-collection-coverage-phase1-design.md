# 藏品覆盖率机制 Phase 1 设计（分层收录 + 展陈证据 + KPI 埋点）

> 2026-07-12 brainstorm 定稿（用户 + ChatGPT 建议 + 实测数据三方汇流）。App 第二核心支柱：
> 用户可见艺术品覆盖率。与识别机制（第一支柱，已上 prod）配套。
> 待用户指令后执行（prod 发布收官确认无问题后）。

## 北极星与原则（回写主契约）

- **KPI 换轴（北极星）**：评价一个馆的接入质量，不看"导入多少件"，看
  **"用户走进博物馆实际拍摄一件眼前藏品时，被正确识别的概率"**（现场识别成功率）。
- **现场覆盖率 > 馆藏总量**：分母 = 常设在展（奥赛 ~3-4 千），不是全馆藏（15 万）。
- **优先级 P0-P3**：常设展厅 > 高频轮换/官方重点 > 临展（schema 预留、运营 Phase 3）> 库房。
- **投入 ∝ 触达概率 × 识别失败风险**：不给每件藏品同等成本；二维一张高质量主图即够，
  三维按触达优先补多视角。
- **展陈状态动态化**：绝不做静态布尔；状态+证据+置信度+核验时间，可更新可过期可追溯。
- **零代码 ≠ 零人工**：核心（流量证据+Wikidata）任何馆开箱即用；区域/馆方适配器=可选增强；
  人工只处理少量异常，绝不进主流程。
- **自家识别流量是最强传感器**：别人预测游客动线，我们直接测量——每次识别尝试都是
  "什么在被拍"的证据。冷启动用静态信号，运行后自校准。

## ① 分层收录（"有图才收录"升级为三层）

| 层 | 定义 | 能力 | 收录来源 |
|---|---|---|---|
| **视觉可识别层** | 有自由版权图 | 向量识别+文字+搜索+列表展示 | 现状（P18/官方开放图/未来飞轮） |
| **文字可识别层** | 有 Wikidata 条目无图 | 墙签 OCR/馆藏号/标题搜索命中；讲解懒生成照常 | **本期新增**：catalog 收全条目（P18 改 OPTIONAL） |
| **需求层** | 连条目都没有 | unrecognized + 记需求聚合 | 现状（R5） |

- **命中路径判定（构造性）**：无图=无向量=DINOv2 够不着；文字层只被墙签 OCR/编号/搜索命中。
- **列表策略（用户已拍板 a）**：无图 stub **不出现在馆藏浏览列表**（列表=逛的场景，密度优先）；
  `list_objects` 及分类计数显式过滤"有图"。识别/搜索命中不受影响。
- **馆页双数字（加法字段）**：`在线图录 2,045 件 · 档案条目 5,345 件（可识别/搜索）`——
  数字与列表所见一致 + 档案规模作为覆盖力卖点。museum pack 加 `catalog_count`/`archive_count`。
- **讲解页 hero（无图件）**：
  - 识别路径 → **用户自己刚拍的照片当 hero**（仅会话内前端回显，不上传不落库，零权利问题；
    未来照片飞轮 ToS 授权后可转正为参考图）；
  - 搜索/直达路径（手里无照片）→ **类目占位图**（雕塑剪影/画框图形+标题排版，
    暖纸手册语言，一套类目图全馆通用）。
  - 前端解析禁裸强转照旧（thumbnail 本就可空）。

## ② KPI/证据埋点（Phase 1 第一优先，一表两吃）

新表 `recognition_events`（迁移）：
`id / museum_slug(可空) / phash / outcome(match|candidates|unrecognized) / top_qid(可空) /
top_score(可空) / confirmed_qid(可空) / language / engine(vector|vector_crops|text|none) / created_at`

- **服务端**：recognize 每次调用落一行（在现有 demands 记录旁，同事务外不阻断主流程，失败只记日志）。
- **确认信号（标注飞轮起点）**：新增加法端点 `POST /api/v1/recognize/confirm`
  `{phash, qid}`——前端确认卡点选时 fire-and-forget 调用，回填 `confirmed_qid`。
  一行前端改动，从第一天积累"真实照片→确认身份"数据。
- **两吃**：(1) KPI：现场识别成功率 = (match + confirmed candidates) / 总尝试，按馆聚合；
  (2) 展陈证据：某 qid 近期在馆内被确认识别 = 最强 "CONFIRMED_ON_DISPLAY" 证据（见③）。
- 隐私：只存 phash（已有需求记录同规格），不存照片。

## ③ 展陈状态与证据接口

- `museum_objects.attributes["display"]`（JSONB 键，零迁移加法）：
  ```json
  {"status": "CONFIRMED_ON_DISPLAY | LIKELY_ON_DISPLAY | TEMPORARY_EXHIBITION | NOT_ON_DISPLAY | UNKNOWN",
   "location": "salle 14(自由文本)", "confidence": 0.9,
   "evidence": [{"source": "recognition_traffic|wikidata_p276|joconde|<adapter>",
                  "type": "confirmed_scan|location_claim|...", "at": "ISO时间", "detail": "..."}],
   "verified_at": "ISO时间"}
  ```
  默认 UNKNOWN；`TEMPORARY_EXHIBITION` 枚举预留（临展运营 = Phase 3）。
- **证据源（按普适性）**：
  1. **自家识别流量**（普适零适配器）：近 N 天内 confirmed/match ≥ 1 次 → CONFIRMED_ON_DISPLAY；
  2. **Wikidata P276**（普适稀疏）：catalog 时顺带收，location_claim 证据 → LIKELY；
  3. **区域适配器（可选样板：Joconde）**：法国文化部开放数据 API（非爬虫、覆盖全法博物馆、
     P347 匹配键已在收）——打磨"区域适配器"模式供他国复用；本期只做接口+Joconde 一个实现。
- 状态汇总规则（简单优先）：有 confirmed_scan 近期证据 → CONFIRMED；只有 location_claim → LIKELY；
  全无 → UNKNOWN。定期任务/报告 CLI 时重算，不做实时。

## ④ 三维 view 自动治理（纯自动，无人审依赖）

- **入索引门槛**：view 与该件 primary 相似度 ≥ 0.4 才建向量（进识别索引）；
- **< 0.25 自动删除**（图行+向量；实测该区间全为非本体图：习作/版画/无关照片）；
- **0.25-0.4 隔离区**：改写 `ObjectImage.role="view_quarantine"`（复用现有 role 列，零迁移）——
  图留档、不进索引、不上详情页图集（图集查询按 role 白名单）；错杀的极端角度由照片飞轮
  （Phase 3）自然补回；
- 隔离区清单可被报告 CLI 列出（可选运营动作，非流程依赖）；
- 执行点：`vet_view_images` 升级为执行此策略（现有 --dry-run 保留）+ 物化嵌入钩子对
  role=view 增加同规则前置闸（新图入库即治理）。

## ⑤ 覆盖率报告（上新馆配方最后一步 + 馆统计字段）

CLI `onboard <slug> coverage-report`：
```
落库总数(档案) / 有图(向量数核对) / 无图(文字层) / 雕塑多视角件数+view数+隔离区
展陈状态分布(CONFIRMED/LIKELY/UNKNOWN) / 三层口径对照(常设在展估值 vs 覆盖率)
KPI: 现场识别成功率(近30天, recognition_events 聚合; 无数据显"待累计")
```
同时把关键数字写入 `museums` 表统计字段（JSONB `stats`，加法）——馆页双数字、
未来运营面板都从这里读，不重算。

## 范围外（Phase 2/3，本 spec 只记方向）

- **Phase 2（自校准）**：识别流量→优先级回灌（图片补齐工作队列按 触达×失败率 排序）；
  官方开放图源适配器（CC0 馆：大都会/荷兰国立/盖蒂——图直接当最高质量参考图）。
- **Phase 3（扩面）**：临展实体（起止时间+独立目录）；用户照片飞轮
  （ToS 授权→确认照片转正参考图，三维视角空间由真实客流铺满）；区域适配器框架固化。

## 契约回写清单（实现完成后）

- 分层收录原则（替换"有图才收录"硬规则①，保留其版权边界语义）；
- 北极星 KPI 口径 + 上新馆验收标准换轴；
- 展陈状态模型与证据源三层；
- 上新馆配方更新：catalog(含无图)→names→images→backfill→views→vet(自动治理)→coverage-report；
- 馆页双数字 API 面（museum pack 加法字段）；`/recognize/confirm` 端点 API 面。

## 实施顺序（写 plan 时按此拆 task）

1. KPI/证据埋点（表+服务端落点+confirm 端点+前端一行）——**最先**（数据越早越值钱）；
2. catalog 收无图 stub（P18 OPTIONAL）+ 列表/计数过滤 + 馆页双数字；
3. 无图 hero（前端：用户照片回显 + 类目占位图）；
4. 展陈状态 JSONB + 证据接口 + 流量/P276 两个普适源；
5. view 自动治理（vet 升级+入库闸）；
6. Joconde 区域适配器样板；
7. 覆盖率报告 CLI + museums.stats；
8. 契约回写 + staging 全量跑 + 验收。
