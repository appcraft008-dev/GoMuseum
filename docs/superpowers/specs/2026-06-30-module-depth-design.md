# 模块深度提升(按热度分档)— 设计

> **状态**:设计定稿(2026-06-30 brainstorm)。下一步 writing-plans。
> **主文档**:`docs/architecture/museum-api-contract.md`(内容体系)。完成回写。
> **背景**:用户反馈"名作的模块太短"——明明有料(维基全文+富属性)却被 `SECTION_ROLES.max_chars` 上限卡死(background 仅 280 字 ≈ 两三句)。

## 1. 目标

抬高深度模块字数上限,并**按热度分档**(镜像默认讲解的 `guide_target_chars`/`GUIDE_KEY_THRESHOLD=30`):名作(热度≥30)给高上限、能深则深;普通件中等;薄件本就没料、自然到不了上限(空的被隐)。**上限是天花板不是地板**——有料才填满,不硬撑注水。

## 2. 字数档(中文字)

`SECTION_ROLES.max_chars` 改为**普通档**值;`section_target_chars(code, popularity)` 对**重点件 ×1.5**:

| 模块 | 普通(base) | 重点(×1.5) |
|---|---|---|
| artist | 260 | 390 |
| background | 380 | 570 |
| analysis | 380 | 570 |
| significance | 240 | 360 |
| facts | 200 | 300 |

(其余 code 如 material-technique/context/maker/use 同步适度抬高 base;沿用 ×1.5 档。)

## 3. 机制

- **`category_config`**:`SECTION_ROLES.max_chars` 改为 base 值;加 `section_target_chars(code, popularity:int|None)->int` = `base * (1.5 if popularity>=GUIDE_KEY_THRESHOLD else 1.0)`(取整)。
- **`build_generation_prompt(material, sections, category, guide=None, popularity=None)`**:各段的"aim ~X"改用 `section_target_chars(code, popularity)`;并加一句**"深 = 用材料里的具体事实/细节铺开,绝不凑字/注水"**。
- **`generate_canonical(obj, sections, guide=None)`**:从 `obj["popularity"]` 取热度,传给 prompt。
- **`_row_to_obj`**:补 `popularity`(对象行已有 `.popularity`)。

## 4. 安全(不会注水)

- 上限=天花板:薄件没料 → 填不满 → 照样短(材料天然限长)。
- **接地闸(三类)+ 2a 去重已兜底**:没接地的注水句被砍、重复头条/他段的被砍。所以"抬上限"只让**有料的名作**铺开,不会把薄件硬撑。

## 5. 非目标

配源 round2(薄件提量,下一步)、2b hedge、guide 长度档(已有,不动)、TTS。

## 6. 契约 / 迁移

无端点字段改动、无迁移(纯生成参数)。重生成后名作模块变长,薄件不变。

## 7. 测试

- `section_target_chars`:重点件(pop≥30)= base×1.5;普通件 = base;None→base。
- `build_generation_prompt`:popularity 传入 → user 里各段 aim 用分档值;含"具体细节不注水"指令;无 popularity 缺省不报错。
- `generate_canonical`:从 obj["popularity"] 取并透传(捕获 user 验证)。
- `_row_to_obj`:含 popularity。
- 全量回归无破。

## 8. 改动文件

- `backend/app/services/enrichment/category_config.py`(base 上限 + `section_target_chars`)
- `backend/app/services/enrichment/prompts.py`(build_generation_prompt +popularity+分档+不注水指令)
- `backend/app/services/enrichment/content_enricher.py`(generate_canonical 取 obj popularity 透传)
- `backend/app/services/enrichment/pipeline.py`(_row_to_obj 补 popularity)
- 测试:`test_category_config.py`、`test_prompts.py`、`test_content_enricher.py`
- 回写主文档(模块按热度分档深度)
