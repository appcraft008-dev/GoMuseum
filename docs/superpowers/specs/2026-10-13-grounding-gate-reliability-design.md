# 接地闸可靠性(P1-9B)设计

日期:2026-10-13 · 状态:待用户审阅 · 台账:`docs/ops/backlog.md` 第三节 P1-9B

## 1. 为什么做

10-13 摸底(只读,复核判官 gpt-4o 逐句要求引材料原文、程序核对引文确在材料里;判官先用 6 句已知正负样本验过全对;判官标出的 111 句逐条人工对照材料分类)。

**A. prod 已发布英文段随机 100 段 / 531 句**

| 类别 | 句 | 段 | 例 |
|---|---|---|---|
| 明确事实错 | 3 | 3 | 高更 1889「刚从马克萨斯回来」;「Paul Guillaume 1929 委托」(材料是收藏) |
| 编造经历/影响/评价/委托 | 23 | 19 | 「influenced generations」「reception was mixed」「not commissioned」 |
| 编造外观(材料无视觉信息) | 47 | 20 | 「vibrant reds and golds」 |
| 解读/轻度修饰(规则允许) | 32 | — | |
| 判官误标 | 6 | — | |

分段集中:significance 7/8、background 6/18 有编造经历;analysis 15/25 编外观。

**B. 随机 30 件按现行流程重生成 + 现行闸(不落库)**

- 闸删 93 句,约 27 句其实有出处(~29%)。**出处只在法语材料里的句子被删率 15%,英语 6%**。
- 闸放行 518 句里 87 句无出处(17%):编外观 46(analysis 37),编经历/评价 41(background 21、guide 13)。

**外观类的向前现状**:生成流程 9 月下旬起已在预取里看图写描述(`pipeline.py` `f_vis`),近 30 天新生成件 ≥95% 有 `visual_description_en`。B 里编外观的都是没有视觉材料的老件。所以向前要补的是「没视觉材料时别写外观」的兜底,不是新建视觉能力。

## 2. 范围

**做**:只改**以后新生成**的内容(批量 generate 与懒生成共用同一条管线)。

**不做**:
- 存量不改、不重判、不重生成(用户 10-13 定)。只按 §6 划线标记,以后单独立项。
- 不碰译文忠实度闸(`check_faithfulness`)、问答闸的阈值、`GROUNDING_THRESHOLD`。
- 不换判官模型,除非 §5 评测证明提示词修法不够,且换之前先报成本给用户定。

## 3. 三处修法

### 3.1 经历/影响/评价/委托 算事实(生成侧 + 闸侧)

- **闸** `prompts.py:_ENTAILMENT_SYSTEM` 的 FACTUAL CLAIM 定义里点名:影响/传承(influenced, inspired, paved the way, legacy)、接受与评价(reception, acclaim, praised, mixed reviews)、委托与收藏(commissioned, acquired, owned)、生涯定位(pivotal, turning point, established his reputation)。这些都要材料支持,否则删。
- **生成** `prompts.py` 的 background / significance 段指令:只写材料明说的经历/影响/评价;材料没说就不写这一类,不要用常识补。按 9-13 铭文转写的教训(禁令要长在它约束的那一拍上),约束写在**那一拍**的指令里(「background 的最后一点陈述材料里的事实」那一拍),不追加在末尾的禁令清单。

### 3.2 外观描写算事实,没视觉材料就不写赏析

- **闸**:FACTUAL CLAIM 里「what is depicted」扩写为:作品外观(颜色、构图、光线、笔触、质感、画面里有什么)是事实,只能由 `[VISIBLE IN THE ARTWORK]` 块或材料原文支持;语气再柔和也不归 IMPRESSION。
- **生成**:`pipeline.py` 取段列表处(`sections = sections_for(o.category)`),材料里没有 `visual_description_*` 时去掉 `analysis`。guide 不去掉,它由 3.2 的闸规则兜底;guide 指令补一句「没有 [VISIBLE IN THE ARTWORK] 时不描述画面细节」。
- 不新增看图调用:预取里已有 `f_vis`。

### 3.3 非英语材料的支撑要认

- **闸**:提示词说明 MATERIAL 可能含法语等其他语言;被非英语材料支撑的句子同样算有出处。
- 若 §5 评测里法语支撑组误删率仍明显高于英语组,升级为「只对被判删的句子用 gpt-4o 复判一次」(仅复判删除项,成本按删除句数计),上线前报成本给用户定。

## 4. 不改的接口

`QualityGate.check_section(material, facts, body)` 签名、返回 `SectionQuality`、存活率与阈值、`persist_gated_sections` 全不变。改动只在提示词文本与 `pipeline.py` 一处段列表过滤。API 契约无变化,App 无感。

## 5. 评测:人为破坏样本组(上线门槛)

**样本来源**:摸底 B 的 30 件(固定种子 20261013),用现行流程生成的英文草稿逐句拆开。正负样本的答案靠构造,不靠人审对错。

| 组 | 构造 | 期望 |
|---|---|---|
| P-en | 判官判 supported 且引文程序核实在材料里、引文为英文 | 留 |
| P-fr | 同上,引文为法语 | 留 |
| P-frame | 判官判 framing/impression 的句子 | 留 |
| N-legacy | 在 P 句后拼接一句模板化的编造:影响/评价/委托/生涯定位,每类若干模板,随机替换人名年份 | 删 |
| N-contra | 把 P 句里的年份、人名、地名换成材料里没有的值 | 删 |
| N-visual | 无视觉材料的件:插入颜色/构图/光线句;有视觉材料的件:把描述里的颜色或物体换成没出现的 | 删 |

**指标**:每组的「判错率」(P 组=误删率,N 组=漏判率)。每种判法用 t=0 各跑 2 遍,报两遍和交集。

**对照**:现行闸(基线)vs 新提示词闸,同一批样本。

**上线门槛**(相对基线,不自拍绝对阈值):
1. N-legacy、N-visual 漏判率各降到基线的一半以下;N-contra 不升。
2. P-en、P-frame 误删率不高于基线 +2 个百分点(t=0 实测约 5% 抖动)。
3. P-fr 误删率降到不高于 P-en 的基线水平;做不到 → 走 3.3 的 gpt-4o 复判升级,先报成本。

**代理指标核对(纪律 32)**:门槛过了之后,再拿这 30 件做一次「只统计不生效」:新旧闸下各段 published/needs_review 的变化。重点看 background、significance、guide 会不会大批挂起(内容变少)。结果报给用户再上线。guide 挂起 = 这件没讲解,任何一件 guide 由发布变挂起都要逐件说明。

评测脚本放 `backend/scripts/eval_grounding_gate.py`(入仓库,以后改闸复用),样本集存 R2 或 scratchpad,不进仓库(含材料原文)。

## 6. 存量标记(A 方案)

- 新闸上 prod 的那天记为**划线日 D**,写进台账 P1-9B 行与最近关闭说明。
- 旧闸生成的存量 = `object_content_sections` 里 `language='en'`、`status='published'`、`generated_at < D` 的段。译文跟它的英文原文走:英文段在线前,它的各语言译文都算旧闸产物(译文 `generated_at` 常常更晚,不能单看译文)。
- 不写库、不加字段。以后要修,就在这批里跑摸底同款复核(B 方案),只重生成有问题的段,并按纪律 37 先报音频作废数。
- 10-13 摸底:prod 已发布英文 3839 段、译文 32160 段 `generated_at` 全部非空,条件可用。

## 7. 测试

- 单测:`pipeline` 段列表在无 `visual_description_*` 时不含 `analysis`、有则含;提示词关键约束存在(防回退,断言点名的词在 `_ENTAILMENT_SYSTEM` 里)。
- 评测脚本自检:基线闸在 N 组上的漏判率 > 0(证明样本组能把闸判错);一个永远返回「全留」的假闸在 N 组漏判率 100%、一个永远「全删」的假闸在 P 组误删率 100%(证明指标能失败)。
- 全量 unit + integration 通过。

## 8. 上线

feature → staging(CI)→ staging 上懒生成 3 件人工看一眼形式(空段/乱码,不审事实)→ 用户合 staging→main → 记录划线日 D。成本:提示词修法零增量;去掉无视觉材料件的 analysis 会略降成本。
