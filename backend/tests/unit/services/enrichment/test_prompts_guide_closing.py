"""guide 结尾那一拍必须带约束。

这条守的不是措辞,是**一个已经复现过两次的失效模式**:
prompt 对开头约束得极细、对结尾只有一句话,模型就在结尾上用同一个公式 ——
而禁用词清单拦不住它(实测 45% 的 guide 违反自己 prompt 里的禁用词)。

删掉这段约束不会有任何报错:文本照写、接地闸照过(引导句不作事实主张,
闸的规则明写 FRAMING → KEEP),只有套话率会悄悄涨回去。
"""

from app.services.enrichment.prompts import _DEFAULT_GUIDE_SYSTEM as G


def test_closing_beat_forbids_second_person_lead_in():
    """第 5 拍必须明确禁止「As you…」这类第二人称过渡。

    实测:只加这一条,套话命中 6/10 → 0/10;而改第(1)拍、收紧"可自由引导"
    两个变体都无效(5/10)。
    """
    assert "do NOT begin the closing with" in G
    assert "'As you…'" in G


def test_closing_constraint_sits_in_beat_five():
    """约束必须写在第 (5) 拍**里面**,不能挪到 prompt 末尾当一条独立禁令。

    根因就是"禁令离指令太远":模型执行的是那一拍的指示。
    这里用位置断言钉住 —— 挪走了这条会红。
    """
    i_beat5 = G.index("(5) end on a memory point")
    i_rule = G.index("do NOT begin the closing with")
    i_opening = G.index("OPENING:")
    assert i_beat5 < i_rule < i_opening, "结尾约束必须紧跟在第(5)拍之后"


def test_opening_constraints_still_there():
    """加法不能把原有的开头约束挤掉(它们是 #543 用 A/B 换来的)。"""
    assert "BANNED OPENINGS" in G
    assert "Do NOT open by inviting the visitor to look or pause." in G
