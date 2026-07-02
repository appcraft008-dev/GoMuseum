# 问答去重 + analysis lane 收重叠 + 作者卡展示顺序 — 设计

> **状态**:设计定稿(2026-07-01)。下一步 writing-plans。
> **背景**:用户审 4 件名作发现:① 重点问答几乎全在复读解说/模块(问答生成没拿到已讲内容)② analysis 深度模块和解说重(都讲符号)③ 作者卡要固定结构展示顺序。

## 1. 问答去重(#1,后端核心)

**根因**:`build_qa_prompt(material, category)` 没拿到解说+模块 → 问答不知已讲啥 → 4 条全重复。

**改**:
- `build_qa_prompt(material, category, covered=None)`:`covered` = 解说+模块已发布正文拼接;加指令"游客已被告知以下内容〔covered〕;**只问其答案 NOT 已在其中**的问题,延伸而非复述;宁可少问/空。"
- `QASuggester._generate_en(material, facts, category, covered)` 与 `.suggest(..., covered=None)` 透传。
- `pipeline`:QA 调用处传 `covered = "\n\n".join(en_published.values())`(此时 en_published 已含 guide+模块)。

## 2. analysis lane 收重叠(#3,后端)

**根因**:解说"引导观察"已点符号(猫/花/手);analysis 又复述同一批符号。

**改 analysis role**(SECTION_ROLES):从"Guided LOOKING: composition/technique/what to notice"改为聚焦**怎么画的(craft)**、明确不复述解说已点的符号:
> "HOW it's painted — the craft: brushwork, paint handling, light & colour, composition structure, scale. Explain technique and choices. Do NOT re-list the symbols/subjects the headline guide already pointed out; go beyond naming them to how the painting achieves its effect."

(guide = 看什么/含义;analysis = 怎么画成的/技法。互斥更清。)

## 3. 作者卡固定展示顺序(#2,前端交接)

后端 `artist` 对象字段已全(name/birth/death/nationality/notable_works/bio)。**前端**按固定顺序展示:**姓名 → 生卒年 → 国籍(籍贯)→ 主要作品 → 生平(bio)**,结构化字段在前、bio 在后。写交接。无后端改动。

## 4. 非目标

- 生卒"年月"(现存年,用户未要求改)、notable_works 上游标签瑕疵("The Fif")、问答字数(用户认可现状)、深度模块字数再调(用户认可)、配源 round2。

## 5. 契约 / 迁移

无端点字段改动、无迁移。重生成后问答不再复述、analysis 聚焦技法。

## 6. 测试

- `build_qa_prompt`:传 covered → user 含 covered + "只问没讲过"指令;covered=None 不报错。
- `QASuggester`:`_generate_en`/`suggest` 接受并透传 covered(注入 fake complete 捕获 user 验证含 covered)。
- `pipeline`:QA 调用传入 en_published 拼接(集成:覆盖文本进了 prompt)。
- analysis role 文案含 "craft"/"brushwork"、不含旧 "what to notice" 措辞(或断言关键词)。
- 全量回归无破。

## 7. 改动文件

- `backend/app/services/enrichment/prompts.py`(build_qa_prompt +covered+指令)
- `backend/app/services/enrichment/qa_suggester.py`(suggest/_generate_en 透传 covered)
- `backend/app/services/enrichment/pipeline.py`(QA 调用传 covered=en_published 拼接)
- `backend/app/services/enrichment/category_config.py`(analysis role 收技法)
- `docs/handoff/2026-07-01-artist-card-order-frontend.md`(作者卡固定展示顺序)
- 测试:`test_prompts.py`、`test_qa_suggester.py`、`test_generate_pipeline.py`、`test_category_config.py`
- 回写主文档(问答去重 + analysis=技法 lane)
