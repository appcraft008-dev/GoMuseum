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
    assert "Do NOT begin it with 'As you…'" in G


def test_closing_constraint_sits_in_beat_five():
    """约束必须写在第 (5) 拍**里面**,不能挪到 prompt 末尾当一条独立禁令。

    根因就是"禁令离指令太远":模型执行的是那一拍的指示。
    这里用位置断言钉住 —— 挪走了这条会红。
    """
    i_beat5 = G.index("(5) stop when the throughline is complete")
    i_opening = G.index("OPENING:")
    for rule in (
        "Do NOT begin it with 'As you…'",
        "must NOT be a question to the visitor",
        "catalogue data",
    ):
        assert i_beat5 < G.index(rule) < i_opening, f"结尾约束必须在第(5)拍里: {rule}"


def test_opening_constraints_still_there():
    """加法不能把原有的开头约束挤掉(它们是 #543 用 A/B 换来的)。"""
    assert "BANNED OPENINGS" in G
    assert "Do NOT open by inviting the visitor to look or pause." in G


def test_closing_beat_does_not_ask_for_a_memory_point_or_a_question():
    """2026-09-26 A/B(小皇宫 TOP20 + 留出 10 件,只英文)三轮:

    - 原版「end on a memory point **or an open question**」→ 问句收尾 30/30。
    - 只禁问句、保留 memory point → 问句 0,但 ~25/30 变成
      「The image of X … lingers in the mind / Remember the image of…」——
      **"memory point" 这个词本身就是模板种子**。
    - 改成「再补一个没讲过的事实」→ 模型去凑事实,闸删最后一句 10 次(旧 3 次),
      没删的变成念目录(measures X by Y cm / housed in the Petit Palais)。
    最终版:没有单独的收尾拍,主线讲完就停、不为收尾加新事实。
    """
    beat5 = G[G.index("(5)") : G.index("OPENING:")]
    assert "memory point" not in beat5
    assert "open question" not in beat5
    assert "adds no new fact just to have an ending" in beat5


def test_opening_keeps_title_artist_year_out_of_the_frame():
    """原版首句「必须带年份/人名」被执行成「In {年}, {作者} captured…」(15/20)。
    只禁这个框架 → 10/20;首句不放年份 → 又长出「In 'TITLE,' ARTIST presents…」。
    最终:从主体本身开头,标题/作者/年份不作句子框架(A/B 两组都 0)。
    约束必须在 OPENING 段里,不在末尾。
    """
    i_open = G.index("OPENING:")
    i_rule = G.index("NOT with the title, artist or year as the frame")
    i_banned = G.index("BANNED OPENINGS")
    assert i_open < i_rule < i_banned


def test_beat_three_bans_the_these_details_subject():
    """第(3)拍「explain why those details matter」被执行成「These details…」(10/20)。"""
    i3 = G.index("(3) explain why those details matter")
    i4 = G.index("(4)")
    assert i3 < G.index("'These details…'") < i4
