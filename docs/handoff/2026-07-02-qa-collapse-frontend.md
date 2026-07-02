# 前端交接:问答必须折叠(答案收在下箭头里)+ 名字翻译原则

## 问题1:预设问答答案要收起、点箭头展开(部分藏品现在平铺)

**现状**:
- ✅ **馆藏点卡(ObjectContent 路径)**:`GuideQuestionList` 已是正确手风琴——默认收起、点 `›` 展开 `⌄`、再点收起。**这就是标准。**
- ✗ **识别(拍照)路径**(`guide_page.dart` 的 `_result` 分支):问答另走一套(硬编码 `l10n.guideQ1/Q2` + `_qa`/`_QaEntry` 追问聊天),**不是折叠**,答案平铺在问题后。

**要做**:识别路径的**预设问答**也用 `GuideQuestionList`(手风琴,答案默认收起、点箭头展开),与馆藏路径一致。
- 后端 `suggested_questions` 返 `[{question, answer}]` 是对的,直接喂 `GuideQuestionList`。
- 识别路径目前用硬编码 guideQ1/Q2——应改为消费后端的 `suggested_questions`(需识别结果能拿到 qid → 查 content 端点;或识别路径统一走 ObjectContent)。这块与"识别→接 ObjectContent"是同一件事,可一并规划。

## 问题2(答后端已确认,前端知会):名字翻译是显示级,QID 才是匹配键

- `title`/`artist`(含中文译名)**纯显示**;**识别/查询/一切匹配都以 QID 为键**,不靠标题文本。
- 所以前端**别用 title/artist 文本做任何匹配/去重/跳转键**,一律用 qid。机器译名可能非权威、可能变,只配拿来显示。
