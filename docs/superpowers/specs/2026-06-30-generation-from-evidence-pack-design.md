# 从证据包生成 + 去重(阶段2a)— 设计

> **状态**:设计定稿(2026-06-30 brainstorm)。下一步 writing-plans。
> **主文档**:`docs/architecture/museum-api-contract.md`(路线图阶段2)。完成回写。
> **关系**:消费阶段1 的 `evidence_pack`;实现内容体系的"去重 lane + 从证据包生成"。本期(2a)**不含** flagged 争议 hedge(2b)、两段式质量评估(2c)、配源 round2。

## 1. 背景与目标

用户验收阶段1 后指出:**内容不够丰富 + 深度模块仍重复**(默认讲解/artist/background/significance 反复讲同一头条)。根因:① guide/模块各自独立从同一材料生成 → 收敛同一角度;② 生成只用 `build_material(attributes)`,**没用上证据包的富属性**(P88委托人/P180描绘/作者材料)。

**目标**:① 生成改从**证据包**取料(用上富属性 → 更丰富);② **去重**——guide 先生成(头条),模块单调用时带 guide 互知 + 锐化 lane + "深化非复述、只会重复就返空";③ overview 退役(与头条重复)。

## 2. 机制(上一轮已定:单调用互知)

1. **调换顺序**:`generate_object` 先生成默认讲解(头条)→ 再生成模块(现为反序)。
2. **模块单调用**(`generate_canonical` 一次产全部模块)**带 guide + 证据包 + 锐化 lane**:
   - prompt 传入默认讲解原文:"游客已听过这段头条;每个模块只补它没深挖的、你那条 lane 的内容,彼此不重复,**能深则深;若只会重复头条/他段就返空字符串**。"
   - lane 锐化(主文档分工表):`artist`=作者其人 / `background`=史实链事件 / `analysis`=看什么(构图技法/视觉细节)/ `significance`=影响与遗产 / `facts`=一个趣闻。
3. 接地闸(三类)+ 翻译(保腔调)沿用;返空段不发布,前端隐空 = 动态。

## 3. 证据包→生成材料

`build_material(obj)` **改为 pack 感知**:
- `obj` 携带 `evidence_pack`(经 `_row_to_obj` 补入)。
- 有 pack:渲染 `facts`(按 `topic` 分组,每条 `(topic) claim: value`,含富属性 P88/P180/P186…)+ `narrative` 块(Wikipedia 作品/作者,标源)。富属性 = 旧 build_material 没有的增量 → **丰富来源**。
- 无 pack:回退现有 attributes 渲染(向后兼容)。
- `flagged` 本期**不渲染**(hedge 留 2b)。

默认讲解 `generate_default_guide` 与模块 `generate_canonical` 都经 `build_material(obj)`,故都自动吃上 pack(无需各自改)。

## 4. 去重 prompt(`build_generation_prompt`)

签名加 `guide: str | None`。system 在现有"导览导演"基础上加:头条已覆盖、各 lane 互斥、深化非复述、只会重复就返空。user 里每段 lane 描述用锐化后的 `SECTION_ROLES`,并附 `facts` 的 topic 分组提示(各段聚焦自己 topic 的事实)。`generate_canonical(obj, sections, guide=None)` 透传。

## 5. overview 退役

- `SECTIONS_BY_CATEGORY` 各类目移除 `overview`(不再生成)。
- **Alembic 迁移**删 `category_sections` 里 `section_code='overview'` 的行(使其不再作为 tab;`section_types` 的 overview 行保留无害)。默认讲解即新"开场"。
- 既有对象 DB 里的 overview 段落体保留但不再出现在 tabs。

## 6. 非目标(本期)

flagged 争议 hedge(2b)、动态模块的"按料跳过生成"(本期靠返空+前端隐空已够)、两段式质量评估 2c、配源 round2(Europeana/馆方策展文)、prod 重生成(staging 验证满意后,与后续一起上 prod 生成一次)。

## 7. 诚实预期

2a 主升**深度 + 去重**(露出的模块更聚焦、不复述、用上富属性)。材料本就薄的件,去重后模块可能更少(空的隐去)。**把"量"再提靠配源**(round2),非本期。

## 8. 契约 / 迁移

- 无 API 端点字段改动(tabs/facts 形状不变;overview 不在 tabs 是数据层变化)。
- 一个迁移:删 overview 的 category_sections 行。

## 9. 测试

- `build_material` pack 感知:有 pack → 渲染富属性+narrative(分 topic);无 pack → 回退 attributes(注入式,离线)。
- `build_generation_prompt`:含 guide 互知 + 锐化 lane + "返空/不复述"指令 + topic 分组。
- `generate_canonical(guide=...)`:透传 guide;集成:generate_object 先 guide 后模块、模块吃 pack。
- overview 退役:SECTIONS_BY_CATEGORY 无 overview;迁移删 category_sections 行;get_object_content tabs 不含 overview。
- 全量回归无破。

## 10. 改动文件

- `backend/app/services/enrichment/content_enricher.py`(build_material pack 感知;generate_canonical +guide)
- `backend/app/services/enrichment/prompts.py`(build_generation_prompt +guide+锐化lane+去重指令)
- `backend/app/services/enrichment/category_config.py`(SECTION_ROLES 锐化;SECTIONS_BY_CATEGORY 移除 overview)
- `backend/app/services/enrichment/pipeline.py`(generate_object 调序:guide 先;传 guide 给 generate_canonical)
- `backend/alembic/versions/*_retire_overview_tab.py`(删 category_sections overview 行)
- 测试:`test_content_enricher.py`、`test_prompts.py`、`test_generate_pipeline.py`、`test_seed_sections.py`(overview 移除)、`test_pack_and_content_facts.py`(tabs 不含 overview)
- 完成回写主文档(overview 退役 + 生成从证据包)
