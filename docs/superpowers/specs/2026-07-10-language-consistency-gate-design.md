# 语言一致性闸 设计

**目标（用户定，核心差异点）**：用户用什么语言，就只看到什么语言，**零混杂**。所有用户可见的生成/翻译文本（讲解 guide / 深度模块 / 问答 / 作者 bio / 藏品简介）在语言 X 下必须真的是语言 X，不混入别的语言。

**背景**：内容从多语言源材料（法语 Joconde / 英法 Wikidata）生成，LLM 有时镜像源语言或翻译漏词跑偏。已知事故：作者 bio 出法语、zh 问答混英文问题。此前用"查中文→查法语"的打地鼠式补丁，治标不治本。本设计从根源统一解决。

**核心原则**：**语言无关**——检测行为派生自 `DEFAULT_LANGUAGES`，绝不硬编语言名单；未来加语言自动覆盖（同"加语言=加配置"）。

---

## 架构（4 块）

### ① 检测器 `lang_detect.text_in_language(text, lang) -> bool`

判断 text 是否真的是 lang。纯离线、确定性、不调 API。

- **非拉丁字形语言**（zh/ja/ko/zh-hant，未来 ar/ru/el…）：**字形检测**——text 必须以目标字形为主；混入的小写拉丁词串（非专有名词）= 污染 → False。非拉丁语言集是配置（当前 zh/ja/ko/zh-hant），加新非拉丁语言加一行。
- **拉丁字母语言**（en/fr/de/es/it/pl…）：**lingua 语言识别**——检测器候选集 = `DEFAULT_LANGUAGES` 中 lingua 支持的语言；文本主导语言必须 = 目标语。lingua 离线、对短文本比 langdetect 稳。
- **候选集派生**：`DEFAULT_LANGUAGES` 是唯一真相源；加语言 → 候选集自动含之 → 闸自动覆盖，零代码。
- **防误报（硬要求）**：只管**散文内容**（讲解/深度/bio/问答正文）；**不管专有名词/短标题/人名**（那些单独本地化，短文本检测不稳）。阈值(起始值,实现时调)：拉丁——lingua 检测的主导语言≠目标语 **且**置信度≥0.7 才判 False；非拉丁——目标字形字符占比 <60% 判 False。极短文本（<15 字符 或 <3 词）→ 一律放行（宁漏不误杀名字/短标题）。
- **lingua 覆盖边界**：未来语言若不在 lingua 支持集内 → 退字形检测（非拉丁）或放行（拉丁），绝不崩。

### ② 接入现有闸/重试（一处统一，全通道覆盖）

复用现有"faithfulness → gpt-4o 重试 → needs_review"机制，语言检测作为**并列的一道确定性闸**（比问 LLM 更快更准）：

- **翻译路径**（`translator.translate_object` / `translate_section`）：译文 → `text_in_language(译文, lang)` → 不符 → gpt-4o 重译 → 再检测 → 仍不符 → 该段 `needs_review`（不发布，宁缺毋滥）。与现有 faithfulness 检测并列（任一不过即重试/挡）。
- **en 轴心**（`QualityGate.check_section`/`gate`）：en 段须英文；不是 → needs_review。
- **问答**（`translate_qa_items`）：问句 + 答案须目标语；不符按翻译路径处理。
- **作者 bio**：`bio_en_usable` 及 bio 各语言校验改用 `text_in_language`，**删除打地鼠的 `_CJK`/`_FRENCH_SIG`**（检测器统一取代）。

### ③ 存量全库重扫重生成

命令/脚本：扫全库所有语言所有已发布内容（含 bio），过 `text_in_language`，污染的 → 重生成/重译（走 ② 的闸）。幂等可重跑。**staging 先跑验证，prod 等用户发话**。

### ④ 契约硬原则 + checklist⑦

- 契约主体加原则：**「语言一致性：用什么语言只看到什么语言，零混杂」**——所有用户可见文本必过语言一致性闸；语言无关派生自 DEFAULT_LANGUAGES。
- 加语言 checklist⑦（质量验收）纳入：加语言时语言一致性闸必须对新语言生效（候选集含之）。

## 数据流（翻译一段到 zh）

```
en 段 → translate_section(zh) → text_in_language(译文, "zh")?
  ├ 是 → faithfulness 检测 → 发布
  └ 否(混英文) → gpt-4o 重译 → 再 text_in_language?
        ├ 是 → 发布
        └ 否 → needs_review(不发布,前端不显该段)
```

## 错误处理 / 边界

- 检测器异常（lingua 加载失败等）→ 放行（fail-open，不阻断内容产出）+ 记日志。
- 专有名词/短文本 → 放行（防误杀）。
- 检测器不确定（置信度低）→ 放行。
- needs_review 的段：前端不显（现有 published-only 过滤已在）；存量重扫可再战。

## 测试

- **检测器**：zh 混英文残片→False；en 全法语→False；正常 zh/en/fr/ja/ko 各语→True；专名/短文本（"Monet"/"1855"）→True（不误杀）；未来语言（不在 lingua 集）→不崩、按兜底。
- **翻译路径**：注入污染译文→触发 gpt-4o 重试；仍污染→needs_review。
- **bio**：法语 bio→检测器判坏→重生成路径（取代 _FRENCH_SIG，行为等价或更广）。
- **存量重扫**：构造污染件→脚本找出（幂等）。
- **语言无关**：检测器对 DEFAULT_LANGUAGES 每一门都生效（参数化测试）。

## 依赖

- 新增 `lingua-language-detector`（2.1.1，纯 Python 离线，poetry lock）。

## 分期

- **P1**（核心）：`lang_detect` 检测器 + 翻译路径接入 + bio 改用检测器 + en 轴心闸。
- **P2**：存量全库重扫重生成（staging）。
- **P3**：契约原则 + checklist⑦ + 前端无需改动（needs_review 已过滤）。
