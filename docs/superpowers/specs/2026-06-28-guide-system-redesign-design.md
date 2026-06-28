# 藏品讲解体系重构 — 设计

> **状态**:整体愿景定稿 + 阶段1 详细设计(2026-06-28 brainstorm)。下一步 writing-plans 出阶段1 实现计划。
> **关系**:扩展 `2026-06-17-artwork-content-enrichment-mechanism-design.md` 与 `2026-06-28-engaging-audio-guide-content-design.md`(导览prompt+三类闸在本体系中被复用为"讲法"+"事实接地")。

## 1. 愿景:三层体验 + 模块库

GoMuseum = 一位知识可靠、懂观察、说话自然、能按游客兴趣逐层展开的私人导览员。**博物馆负责事实,AI 负责讲法。**

- **第一层 默认标准讲解**:识别后先得一段短而完整的现场导览,只围绕**一个核心观点**,~1分钟看懂这件最值得看的地方。
- **第二层 预设常见问题**:每件 3-6 个最有价值的问题,讲解后推荐 2-3 个,低成本继续深入,与默认讲解不重复。
- **第三层 AI 自由问答**:个性化追问,复用同一知识底座,争议必 hedge("可能/研究者认为/仍有争议")。
- **原 6 模块**(通用描述/作者介绍/创作背景/艺术分析/文化意义/趣闻轶事)**不删**,降级为:后台知识组织 + 各层生成素材 + 前台"更多内容"可选深度模块。**前台展示哪些 = 按藏品类型与内容价值动态决定**,不强制凑齐。

## 2. 子系统拆解 + 路线图

| # | 子系统 | 阶段 |
|---|---|---|
| 默认标准讲解 | 单主线·5拍·长度分级 | **阶段1** |
| 预设问题重定位 | 3-6个·讲后荐2-3·去重 | 阶段1(前端为主) |
| 跨模块去重 | 务实(轻) | 阶段1 |
| 证据包 | fact/mainstream/contested/inference/unverified 分类底座 | 阶段2(地基) |
| 模块库+动态选择 | 6模块按件动态选/收编 | 阶段3 |
| AI 自由问答 /ask | 多轮·复用证据包·hedge | 阶段3 |
| 两段式质量评估 | 事实质量 + 讲解质量 | 阶段2-3 |

**渐进式**(对齐用户建议):阶段1 加法置顶默认讲解+推荐问题、保留旧模块在下面;阶段2 建证据包重生成;阶段3 按点击率/收听完成率收编模块 + /ask。

---

## 3. 阶段1 详细设计(本期实现)

### 3.1 默认标准讲解(新生成物)

- **单主线·5拍结构**:快速进入看点 → 引导观察 1-2 个具体细节 → 解释这些细节为什么重要 → 补必要背景 → 记忆点/开放问题收尾。**只围绕一个核心观点**,不追求覆盖全部知识。
- **长度分级(已 ×1.5)**:普通件 **270-420** 中文字、重点件 **420-675** 字。长度是目标非硬限,料薄可短。
- **重点件判定**:`popularity >= GUIDE_KEY_THRESHOLD`(默认 30,可调;复用既有 popularity/sitelinks,零新数据)。
- **生成**:新 prompt(导览导演声音,复用 `2026-06-28-engaging-audio-guide` 的口吻+三类许可),从对象材料**一次独立生成调用** `generate_default_guide(material, facts, tier, langs)`。复用三类接地闸 + 翻译(保腔调)。
- **去重(务实)**:prompt 告知"这是头条,深度细节在更多内容里,别铺所有事实",使其天然是单主线头条而非 6 模块缩写。全面跨模块去重留阶段3。

### 3.2 材料:现有 + 作者实体抓取

现有材料 = Wikipedia 全文(作品条目,≤5000字/语)+ Joconde 结构化事实 + Wikidata 基础。**名作充足(实测 10K 字),长尾薄。**

**本期加:作者实体抓取**(修"作者段空" + 喂肥默认讲解的"谁做的/背景"拍):
- SPARQL(`wikidata.py`/`wikidata_catalog.py`)在查作品时**同时取 P170 作者实体的 QID + 作者 en/country-lang 维基条目标题**,落进 stub 路由(`artist_wiki_titles`)。
- 逐件材料富化(`material.fetch_object_material`)**额外抓作者 Wikipedia extract**(复用 WikipediaSource,用 artist_wiki_titles),存为 `artist_extract_{lang}`。
- `build_material` 把 `artist_extract_*` 纳入材料(标注为"关于作者")。

**博物馆官方源 + 完整分类证据包 = 阶段2**,本期不做。

### 3.3 数据模型 + 契约(纯加法)

- 默认讲解落库**复用 `ObjectContentSection`**,`section_code="guide"`、`language=各语种`(走现有 persist/三类闸/翻译)。
- `get_object_content` 加顶层字段 `default_guide: {body, audio_url}`(从 tabs 抽出单列;无则 null)。
- 老的 `tabs`(6模块)+ `suggested_questions` 原样保留 → 前台收进"更多内容" + 推荐问题。
- **前向兼容**:纯加字段,老 App 忽略;无迁移(复用既有表)。

### 3.4 前后端分工

- **后端(本 session)**:作者实体材料 + `generate_default_guide` + `guide` 段落落库 + 契约 `default_guide` 字段 + prod/staging 重生成。
- **前端(另 session,交接文字另附)**:讲解页顶部渲染 `default_guide`(+音频位)→ 其后展示 2-3 个推荐问题(取 `suggested_questions` 前 2-3)→ 6 模块 + 其余问答收进"更多内容"折叠区。

### 3.5 非目标(阶段1 不做)

证据包/分类信息、模块动态选择、/ask 多轮、两段式独立质量评估、overview 退役(与 default_guide 重叠,留阶段3)、博物馆官方源、TTS 音频(audio_url 暂 null)。

## 4. 测试 / 验证

- **单测(注入式)**:`generate_default_guide` 按 tier 选长度目标、prompt 含 5拍结构+单主线+去重提示;作者材料进 `build_material`;契约 `default_guide` 字段。
- **集成**:generate 端到端产出 guide 段 + 三语;get_object_content 返回 default_guide。
- **验证**:staging 重生成几件 → APK 看"1分钟看懂"(单主线、有看点引导、不啰嗦、作者拍不空)。满意 → prod 重生成 TOP-N → 按点击/收听率为阶段3 收编模块铺路。

## 5. 改动文件(阶段1 后端)

- `sources/wikidata.py` / `sources/wikidata_catalog.py`(SPARQL 取作者 QID+维基标题)
- `catalog_source.py`(StubRecord 加 `artist_wiki_titles`)/ `catalog_loader.py`(落库路由)
- `material.py`(逐件抓作者 Wikipedia)/ `content_enricher.build_material`(纳入 artist_extract_*)
- `prompts.py`(`build_default_guide_prompt`)/ `content_enricher` 或新 `default_guide.py`(`generate_default_guide`)
- `pipeline.generate_object`(增产 guide 段)/ `category_config`(GUIDE_KEY_THRESHOLD + 长度档)
- `museum_repo.get_object_content`(`default_guide` 字段)+ 契约活文档更新
