# 藏品内容富化机制 — 设计文档

> 创建于 2026-06-17。把"事实"加工成"有质量的分段讲解 + 音频"的**可复制机制**。
> 以奥赛为样板，目标是一套完整、牢固、可无大改复制到所有博物馆的基础模板。
> 上接富化管线 v1（事实/元数据，见 [[enrichment-pipeline-v1]]）与 TTS 音频落库
> 基础设施（[[tts-audio-persistence]]）。架构原则承 `docs/architecture/data-and-content-architecture.md`。

## 1. 背景与问题

富化管线 v1 把藏品的**事实/元数据**（标题、作者、年代、材质、藏地、`sources`）规模化入库，
但**没有生成讲解叙事**。实测 prod：`/api/v1/museums/orsay/objects/{qid}/content` 返回
`{"tabs": []}`——点进藏品**一段讲解都没有**。缺的是三层：

1. **段落骨架**：`section_types` + `category_sections`（"一幅画有哪些段落"）未 seed 进 prod。
2. **讲解正文（body）**：未生成。
3. **音频**：未生成（落库基础设施已就绪，缺内容）。

**核心认知（来自讨论）**：内容富化**不是"拉一次数据源就完备"，本质是质量工程**。
而且管理员/开发者**不是艺术史专家，无法人工审核内容正确性**——这否决了"靠人审对错"的所有方案。
因此质量必须**设计进生成流程**，而非事后人审。

本机制以奥赛为**样板点**：不仅富化奥赛，更是**以后复制到所有馆的基础模板**，
故必须完整（预生成 + 懒生成都在）、牢固（不阻塞、幂等、可平滑升级）。

## 2. 目标与非目标

**目标**：一套可复制的藏品内容富化机制——
- 把事实接地（grounded）生成为分段讲解 body + 音频，正确性靠构造保证；
- 两种触发：批量预生成（top-N）+ 懒生成（长尾首次打开时按需）；
- 环境感知（staging 样本审形式安全 → prod 全量）、幂等、按馆可配置；
- 前端分段藏品详情页作为消费者，端到端闭环。

**非目标（留 v2+）**：
- Wikidata/Wikipedia 之外的馆开放数据连接器（Joconde/Europeana/Met）——接口预留，v1 不实现。
- 文字高亮、逐句级 provenance（见 §13b，前向兼容预留，不实现）。
- Wikipedia pageviews / App 埋点作为人气信号（v1 用现成 sitelinks）。
（注：多语言**不是**非目标——它是 v1 核心，英语轴心 + 配置驱动翻译，见 §13。）
- 专门的后台 worker 容器（v1 用进程内异步 + Redis 锁，契约预留可平滑升级）。
- 管理后台 UI（人工只审 staging 报告，不建 admin 界面）。

## 3. 第一原则：正确性靠"构造"，不靠"人审对错"

1. **严格 grounded 生成**：生成讲解时**只喂给模型来源明确的材料**（Wikidata 结构化事实 +
   Wikipedia 词条正文摘录），明确指令"只能依据这些材料写，不许用自身知识补充"。
   产出是"把给定材料改写成讲解"，不是"凭印象讲"。
2. **留 provenance**：记录生成所依据的源材料（用到的 Wikipedia 页 id/url + 哪些事实），
   v1 落在**对象级** `MuseumObject.sources` JSONB（已有，无需新列）；段级仅用现有
   `status`/`model`/`source=ai_generated`/`generated_at` 标记。逐句级引用留 v2。
3. **自动事实一致性门（机器审，不需懂艺术）**：生成后用一遍 LLM 做**蕴含校验**——逐句判断
   "能否从给定材料推出"，**不支持的句子删除**。在无人懂这幅画的前提下挡住编造。
4. **宁缺毋滥**：源数据太薄 → 只写确凿的一小段，甚至标"待完善"；**绝不脑补凑字数**。
5. **人只审"形式与安全"**（非专家可操作）：有无空段/乱码/语言错/冒犯内容——**不审事实对错**。
6. **用户反馈兜底纠错（规模化真值）**：App 放"报错/纠正"入口，真正在现场或懂行的人报错 →
   被报内容重新生成/复核。单个管理员做不到、群体能做到。（接路线图反馈入口，本 spec 仅预留，
   入口实现属反馈闭环任务。）

## 4. 架构总览

```
事实层(v1已有)         事实补全           grounded生成        质量门            音频          落库
MuseumObject.sources → +Wikipedia正文 → 分段body草稿 → 蕴含校验+宁缺毋滥 → TTS → object_content_sections
(Wikidata骨架)         +中文标签补全                  (删不支持句/标待完善)        (R2 audio_key)
```

- **生成器统一一份**（`ContentEnricher`），**批量 CLI 与懒生成端点都调它**，幂等。
- 管线沿用 v1 形态：在 onboard CLI 上加 **GENERATE 阶段**（事实补全 + 生成 + 校验 + 落 body）
  与 **TTS 阶段**（body 定稿后按段生成音频落 R2），staging 样本金丝雀 → prod 全量。

## 5. 数据源策略

- **Wikidata（骨架）**：v1 已有，提供结构化事实（作者/年代/材质/尺寸/藏地/depicts/sitelinks）。
- **Wikipedia 词条正文（叙事血肉）**：v1 新增 `WikipediaSource`——按对象的 Wikidata sitelink
  找到对应 Wikipedia 页，拉**正文摘录**（REST `page/summary` + `page/related` 或 extract API）。
  这是 grounded 生成的质量天花板来源。**中文条目优先**（zh.wikipedia），无则取英文条目做素材。
- **馆开放数据（可插拔加分源，v1 不实现）**：Joconde/data.culture.gouv.fr、Europeana、
  Met/Rijksmuseum API。沿用 v1 的 `Source` ABC + 合并优先级（[[enrichment-pipeline-v1]]），
  加一个连接器即接入，不改主流程。
- **覆盖率现实**：非每件都有 Wikipedia 条目。有 → 内容厚；无 → 按"宁缺毋滥"出薄内容或标待完善。
  名作通常都有，正好覆盖用户最常看的。

## 6. 段落骨架（沿用现成，必须 seed 进 prod）

`backend/scripts/seed_sections.py` 已定义 6 段（绘画类），**幂等 upsert**，但**未在 prod/staging 跑过**：

| code | 中文 | 英文 | sort |
|---|---|---|---|
| overview | 通用描述 | Overview | 10 |
| artist | 作者介绍 | The Artist | 20 |
| background | 创作背景 | Background | 30 |
| analysis | 艺术分析 | Analysis | 40 |
| significance | 文化意义 | Significance | 50 |
| facts | 趣闻轶事 | Facts | 60 |

机制第一步：**在 staging + prod 容器内跑 `seed_sections.py`**，让 `object_content` 端点能返回 tabs。
不新发明段落集合。注：现有 `content_repo.FIELD_MAP` 只映射 5 段（缺 artist），新生成器需产出全 6 段。

## 7. grounded 生成服务（`ContentEnricher`，统一一份）

**输入**：一个 MuseumObject（含 sources 事实）+ 该对象**最丰富语言源**的 Wikipedia 正文摘录
（如奥赛优先 fr，+ en）+ 目标语言集。
**处理**：
1. 组装"材料包"（结构化事实 + Wikipedia 正文），明确标注每条来源。
2. **英语轴心生成**：一次 LLM 调用产出**英语**全部 6 段草稿（system prompt 强约束：只依据材料、
   分段、缺料则留空该段）。
3. 逐段过**蕴含校验**（见 §8）→ 得到已验证的英语权威正文。
4. **翻译铺语言**：对配置语言集里的其余语言，逐语言**翻译该权威正文** + 译文忠实校验。
5. 返回 `{language: {section_code: body|None}, provenance, model, status}`。
**输出落库**：新增/扩展 `content_repo` 落库函数，按 (object, language, section_code) upsert
body + status + model（`source=ai_generated`、`generated_at`）；对象级 provenance 写 `sources`；
body 为 None 的段不发布（标 `needs_review` 或不建行）。
**幂等**：已 `published` 的 (段, 语言) 默认跳过，除非 `--force` 或源更新；加语言只补缺的。
**统一一份、两触发**：批量 CLI 与懒生成端点都调它（懒生成可按当前语言优先、其余语言后台续翻）。

## 8. 质量门

- **自动蕴含校验**：对每段 body，第二次 LLM 调用（便宜模型）逐句判断"能否由材料推出"，
  剔除不支持句。剔除后该段太薄/空 → 标 `needs_review`，**不发布**。
- **完整性/格式检查**（纯代码）：无 null、无空白乱码、语言正确（各语言段确为该语言）。
- **人工只审形式安全**：staging 跑样本生成 → 产出**审阅报告**（`report.py` 扩展：列每段前若干字、
  哪些标 needs_review、覆盖率），人眼扫"有无空段/乱码/冒犯"，**不审事实对错**。
- **用户反馈兜底**：被报错的 (object, language, section) 置回 `needs_review` 触发重生成（v1 预留状态，
  入口实现单列）。

## 9. 成本策略

- **一次性 + 永久落库**：body/audio 一件作品只生成一次，之后所有用户读 DB/R2，**零重复调用**。
  这是最大的成本控制。
- **便宜模型**：grounded 生成是"受约束的改写"轻任务，用 gpt-4o-mini / Claude Haiku 档；
  蕴含校验同样用便宜模型。顶配模型只在开发期调 prompt / 抽验时用。
- **批量 API 折扣**：离线批量走 batch 接口（约 5 折）。
- **按人气分层**：top-N 预生成；长尾懒生成（首次打开才花钱，没人看不花）。
- **量级**：英语权威正文每件**只生成+校验一次**；其余语言是廉价翻译+译文校验。Orsay 246 件 ×
  (1 英语生成 + 1 校验 + N 翻译 + N 译文校验)，便宜模型 + 批量折扣，全语言一次性**百元美金以内量级**，永久落库。
- **运行时是 API，不是 Claude 订阅会话**：机制必须可自动化 + 支持懒生成运行时，订阅会话无法当
  生产运行时（且不符订阅用途）。**Claude（开发助手）用于开发期打磨 prompt、抽验样本、设计校验**，
  不当批量生成运行时。

## 10. 人气信号

- **v1：Wikidata sitelinks 数**（`wikibase:sitelinks`，已入库为 `MuseumObject.popularity`，
  `loader.select_sample` / `museum_repo` 已按它降序）。"top-N"现成。性质 = 名气/编辑覆盖度代理。
- **巧合支撑设计**：sitelinks 高 ≈ 有丰富 Wikipedia 条目 ≈ 用户最想看 —— 三者重合，
  top-N 预生成既选中最爱看的、又选中最能生成出好内容的。
- **future（非 v1）**：Wikipedia pageviews（真实读者流量）、App 埋点（实际扫/点开）逐步取代代理值。

## 11. 两种触发 + 生成状态机

**生成状态**（`object_content_sections.status`，已有字段，扩展取值）：
`absent`（无行/未生成）→ `generating`（生成中）→ `published`（已发布）/ `needs_review`（待人工/待完善）。

**批量预生成（CLI）**：`onboard <slug> generate --target staging|prod [--top-n N] [--lang zh] [--force]`
遍历 top-N 对象 → `ContentEnricher` → 落库。随后 `onboard <slug> tts ...` 为已 published 的段生成音频。

**懒生成（端点，做牢，无新设施）**：
1. 详情页请求 `object_content`，某对象内容为 `absent`。
2. 端点**立即返回**带 `status: generating` 的占位（不阻塞）；同时**异步后台任务**
   （FastAPI BackgroundTasks，LLM 调用为 I/O 等待型、不占事件循环）跑 `ContentEnricher` + TTS。
3. **Redis 去重锁**（key 按 `qid:lang`）：并发打开同一作品只生成一次，其余等待复用。
4. **App 轮询**：详情页见 `generating` → 过几秒重拉，`published` 后显示。
5. **可平滑升级**：将来换专门 worker 容器，对外契约（status + 轮询）不变。

**幂等/防重**：`generating` 状态 + Redis 锁防重复入队；失败/卡死 → 超时回退 `absent` 可重试。

## 12. 音频

- body 定稿（`published`）后，按段调 **已上线的 `persist_section_audio`**（[[tts-audio-persistence]]）
  生成 TTS（OpenAI `tts-1`，mp3）→ 落 R2 + 写 `audio_key`。
- **文件粒度 = 每 (对象, 语言, 段落) 一个 mp3**（key `object-audio/{qid}/{lang}/{section}.mp3`）。
  不同语言/段落 = 不同文字 = 各一份；一段只存**一份规范音频**（`audio_key` 不编码 voice/speed）。
- **音色统一品牌讲解员**：OpenAI 语音是**跨语言通用音色**（念哪种语言由文字决定，不由语音决定），
  故全语言默认用**同一把品牌音色**（一致、可识别）；`VOICE_MAPPING` 是纯配置，换音色/给某语言配
  不同音色 = 改配置、零代码；**新语言无音色映射 → 优雅退回全局默认音色**。
- 批量：`onboard <slug> tts` 阶段；懒生成：body 落库后同一后台任务续跑 TTS。
- body 变更（重生成）→ 现有 `persist_explanation` 已会清 `audio_key`，音频随之重生成。
- **播放速率**：纯前端播放控制（just_audio `setSpeed`，本机变速，不重生成、不产生新文件、不碰后端）。
  详情页播放器给 0.75/1/1.25/1.5x 控件，富化机制/数据为它**零额外工作**。

## 13. 多语言（英语轴心 + 配置驱动翻译）

**主市场是欧洲多语言（en/fr/de/es/it…），中文是开发/次要语言。** 架构 = **接地生成一次 + 翻译铺语言**：

- **英语轴心（canonical）**：每对象**接地素材取最丰富语言源**（如奥赛法国艺术优先 fr.wikipedia +
  英文维基 + Wikidata 一起喂给模型），产出**一份英语权威正文**，**蕴含校验一次**（正确性建立）。
- **其余语言 = 翻译该权威正文** + 一道"译文是否忠于原文"的校验防漂移。各语言事实一致。
- **语言全参数化 + 配置驱动**：目标语言是参数，语言集合放配置（全局默认 + `museums.yaml` 覆盖），
  代码**零硬编码语言**；校验/落库/音频/详情页全部按语言循环。
- **加语言 = 零代码、幂等**：扩配置列表 + 重跑，已生成语言跳过、只补缺的。可"一上来配全套一次跑全"，
  也可"先 en+fr 验证、再扩列表重跑补齐"——都不改代码。加非默认集里的语言**无任何特殊**（同一代码路径；
  唯一触点 TTS 音色已优雅降级）。
- **标签/标题补全**归"事实补全"：`title_zh`/`title_xx` 等缺失（今日事故根因，见
  [[enrichment-data-frontend-contract]]）在生成前补（对应语言 Wikipedia 标题优先）。后端 `museum_repo`
  已有 title_zh 兜底，本机制从源头补全减少兜底依赖。
- **默认语言集是运营旋钮、非架构**：示例默认 `en, fr, de, es, it, zh`，随时可改、零代码影响。
- **人工审仍只审形式安全**（语言对不对/有无乱码，非母语可判），多语言不重新引入"人审对错"难题。

## 13b. 前向兼容扩展点（现在不建，但样板不得阻断）

以下功能 v1 不实现，但样板必须保证"以后加不破坏架构、可对所有已建馆回填"：

- **文字高亮（朗读时高亮当前词/句）**：需"文字↔音频时间轴对齐数据"。设计为**纯叠加产物**——
  每段一个可选 marks 文件（R2 同级 `object-audio/{qid}/{lang}/{section}.marks.json`），
  **body 与 mp3 原封不动**。对齐用 **forced-alignment（事后对齐既有"音频+已知文字"，如 WhisperX/aeneas），
  不依赖 TTS 返回时间戳**——故可对**所有已生成的馆就地回填，无需重跑 body/音频**。前端播放器已暴露
  `positionStream`，高亮 = 当前位置 + marks → 高亮词句。**v1 仅保留约定（按段存音频、body 为干净纯文本、
  预留同级 marks），不写代码、不做任何阻断它的设计。**
- 不变量：音频按段落存、body 为可对齐纯文本、key 方案支持同级兄弟产物——已天然满足。

## 14. 管线形态与 CLI

沿用 v1 onboard CLI，加阶段：
- `onboard <slug> seed-sections`（或直接跑 `seed_sections.py`）：导入段落骨架（staging+prod 各一次）。
- `onboard <slug> generate --target ... [--top-n] [--langs ...] [--force]`：批量生成（英语轴心 + 翻译铺
  配置语言集）。`--langs` 缺省取配置默认集；幂等只补缺语言。
- `onboard <slug> tts --target ... [--top-n] [--langs ...]`：为 published 段按语言生成音频。
- **金丝雀流程**：staging 跑样本（top-N 小样）→ `report.py` 审阅报告人工审形式安全 → prod 全量。
- **幂等**：已 published 跳过（除非 --force）。
- 容器内执行：`docker exec gomuseum_{staging,prod}_backend python scripts/onboard.py ...`。

## 15. 前端：分段藏品详情页（消费者）

- **入口**：馆藏清单（`MuseumPage`）点藏品 → **改为 push 详情页**（现状 push `/guide` 实时重生成，
  浪费且不落库）。识别流（拍照）仍走 guide。
- **页面**：消费 `GET /museums/{slug}/objects/{qid}/content?language={当前语言}` → 分 tab 展示各段
  `{section_code,label,icon,body,audio_url}`；每段一个**播放键**：`audio_url` 有则
  `TtsService.play(audio_url)`（R2 直链可直接播）；段 body 为空/`needs_review` → 显示"待完善"。
- **语言**：取 App 当前语言（i18n locale）传 `language` 参数；后端按语言返回对应译文。
- **播放器控件**：播放/暂停 + 速率 0.75/1/1.25/1.5x（`TtsService.setSpeed`，纯本机变速）。
- **生成中态**：响应 `status: generating` → 显示"讲解生成中"，定时重拉直至 published。
- 复用既有 `TtsService`、go_router；新增详情页 + 数据层（Clean Architecture）。

## 16. 可复制性（样板的关键）

**复制到新馆 = 配置 + 跑命令，无主流程改动**：
- **全局配置**：目标语言集（默认 `en,fr,de,es,it,zh`）、品牌音色、模型档位——馆无关、随时可改。
- **每馆配置**（`museums.yaml`）：slug、Wikidata 馆 QID、类别过滤、fetch/sample 规模、语言集覆盖（可选）。
- **通用机制**：源连接器、生成器、翻译、校验、状态机、CLI、详情页——全部馆无关、语言无关。
- 加新馆：`museums.yaml` 加一条 → `onboard <new> fetch/seed-sections/generate/tts` → staging 审 → prod。
- 加新源（如 Joconde）：实现一个 `Source` 连接器，按合并优先级接入，主流程不动。

## 17. 测试策略

- **生成器**：mock LLM + 固定材料包 → 断言只产出给定段、缺料段为 None、provenance 正确。
- **蕴含校验**：mock 判定器 → 断言剔除不支持句、剔空标 needs_review。
- **状态机/懒生成**：端点 `absent` → 返回 generating + 入队（mock 后台任务）；Redis 锁去重；
  `published` 后正常返回 body+audio_url。
- **CLI**：generate/tts 幂等（已 published 跳过）、--force 重生成、--top-n 选取正确。
- **前端**：详情页解析 tabs、generating 态轮询、audio_url 播放、待完善降级。
- **金丝雀报告**：样本生成 → 报告含覆盖率/needs_review 计数。

## 18. 实现分期（写计划时拆为多份）

机制较大，按依赖分期，每期可独立交付、测试：
1. **骨架 + WikipediaSource + 事实补全**：seed_sections 上 prod；WikipediaSource 连接器；标签补全。
2. **grounded 生成器（英语轴心 + 翻译铺语言）+ 蕴含/译文校验 + 落库**：`ContentEnricher`；
   批量 CLI `generate`；金丝雀报告。
3. **TTS 阶段**：CLI `tts` 批量（按语言、统一品牌音色）；接已上线 `persist_section_audio`。
4. **懒生成端点**：状态机 + 异步后台 + Redis 锁 + 轮询契约。
5. **前端分段详情页**：消费 object_content；播放；生成中态；馆藏入口改向。

## 19. 验收标准

- staging 跑 Orsay top-N 样本生成 → 报告无空段/乱码，needs_review 计数合理；人工审形式安全通过。
- prod 全量生成后，`object_content` 对 top-N 返回非空 tabs，每段 body 接地可溯源、音频可播。
- 详情页对已生成藏品分段展示 + 每段可播；对未生成长尾首次打开触发懒生成、轮询后显示。
- 同一藏品二次请求 body/audio 复用、零重复 LLM/TTS 调用。
- 加一个假想新馆（仅改 museums.yaml + 跑命令）能走通 fetch→seed→generate→tts，无需改主流程代码。
