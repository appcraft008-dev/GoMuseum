# 博物馆介绍 + 封面设计（description_i18n + cover_image）

> 2026-07-18 定稿(brainstorm + Fable review 修订)。目标:每馆一段 AI 生成接地介绍 + 一张得体封面,
> **上新馆自动有**(零代码,配方加一步)。上第二家馆(Rijksmuseum)的 enabler,Play 发版加分项。

## 决策记录

- **内容形态 = 纯叙事单段**(~150-250 字钩子,default_guide 的现场导览调):馆的历史/定位/镇馆之宝/风格,
  稳定事实(建馆年份等)**溶进叙事**,不单列结构化字段。**绝不碰开放时间/票价**(易变运营数据,AI 脏补比没有更伤;
  也保零代码上新馆——不引入逐馆运营数据维护)。
- **生成 = 复用富化管线**(方案 A):新 museum-intro prompt + `QualityGate` 接地校验 + `ContentTranslator`
  铺语言(继承语言一致性闸/显示名真相)。不写独立生成器(质量闸/翻译重写=重复,放弃=降质破契约)。
- **预生成而非懒生成**(归类理由,契约"成本分界"原则):馆介绍=**门面类内容**(馆页高频入口,总成本封顶
  =馆数×几分钱)→ 归"图=门面必须预物化"侧,不走艺术品的懒生成侧。
- **封面 = 后端 LLM 得体性筛选**(server-driven 优先):内容安全判断必须后端可控——选错改后端立即生效,
  不用发版等 Play 审核。前端拿 top 件的"最懒方案"被否:前端无信息判断得体性。

## §1 数据模型 + 契约面(全加法)

- `Museum.description_i18n`(新 JSON 列,迁移):`{lang: 叙事文本}`。
- `Museum.cover_image_key`(新列):选定封面的 R2 image key(或 null)。
- 馆包 `get_museum_pack` 加两字段:
  - `description`:按 `language` 解析 `description_i18n[lang]`,缺则回退 en → 任一已有 → `null`;
  - `cover_image`:`cover_image_key` 的 R2 直链,**full 档**(hero 大图,thumb 会糊),无则 `null`。
- 前端契约容错老规矩:两字段 `as String?`,null 时整块隐藏。老 App 不读不炸。

## §2 生成:onboard 子命令 `intro`

`python scripts/onboard.py <slug> intro --target <env>`,与 catalog/names/generate 并列(进上新馆配方)。

**介绍生成流程**:
1. 接地材料:馆 qid(museums.yaml `wikidata_qid`,现成)→ Wikidata sitelinks → Wikipedia extract。
   ⚠️ 实现注意:艺术品 extract 走 `attributes.wiki_titles` 管道,馆没有——sitelinks 查询需小补一个
   fetch 函数(照 `sources/wikipedia.py` 模式,`wbgetentities` 或 WDQS)。另抓 Wikidata 基本事实
   (成立年/建筑/馆藏领域 label)喂叙事。
2. en 轴心生成:`ContentEnricher` 走新 `build_museum_intro_prompt`(~150-250 字,钩子调,
   grounded 不脑补,原创表达不照搬)。
3. `QualityGate.check_section` 接地校验:**gate 不过 = 该语言不落库**(不引入 needs_review 状态机——
   就一段文字,失败重跑,宁缺毋滥;馆包回退逻辑兜显示)。
4. `ContentTranslator` 铺 `resolve_languages(cfg.languages)`(**馆配置驱动,不硬编 10 语**)。
5. 落 `description_i18n`。

**幂等 = 按语言维度补缺**(契约"完整性判断按语言维度"统摄原则):en 已有 → 只给缺的语言纯翻译补;
全齐才跳过;`--force` 整段重生成。加语言后重跑 intro 自动补新语言。

**封面选择流程**(同命令顺带):
1. 取该馆 top-10 热度、有 R2 图(`image_key` 非空)的藏品;
2. 逐件 LLM 得体性判定(**纯文本**:标题/作者/分类,不用 vision):
   古典/宗教/神话题材裸体=艺术惯例**可接受**;写实露骨性描绘(如《世界的起源》)**不可**;
3. 第一个通过的固化 `cover_image_key`;全不过 → null(前端隐藏);
4. 幂等:已有封面跳过;`--force` 重选。

**成本**:每馆 1 次生成 + (N-1) 次翻译 + ≤10 次得体性判定 ≈ 几分钱,一次性。
**staging**:零操作——`sync_staging_from_prod` 已搬 museums 表,prod 生成的介绍/封面随搬运自动到 staging。

## §3 前端呈现(独立交接,不阻塞后端)

推荐**折叠 hero**而非 tab:馆列表页顶部封面图 + 介绍卡(默认收起 1-2 行 + 展开),藏品列表仍是主视图
(用户是来看藏品的,tab 把列表降级成次要视图、多一次 tap)。tab↔hero 前端可自行改,后端零改动。
交接文档随实现出。

## §4 测试 + 验收

- 单测(fake enricher/gate/translator):`description_i18n` 落库;按语言补缺幂等(en 在只补缺语);
  gate 失败该语言不落;封面判定否决件被跳过、通过件固化;馆包两字段解析 + 回退 + null。
- 迁移:两列加法不破现有。
- staging 端到端:prod 跑 `intro` → 搬运到 staging → 馆包返回中文介绍非空、封面非《世界的起源》类。

## 契约回写清单(实现完成后)

- 端点 2(馆包)API 面加 `description`/`cover_image` 两字段(null 语义);
- 上新馆配方加 `intro` 步(catalog→names→images→**intro**→coverage-report);
- 原则一句:馆介绍=门面类预生成内容(成本分界);封面=后端得体性筛选(server-driven)。
