"""文本质量指标:用**已知好/坏两组**证明指标有判别力。

判定类工具自己要先过判定:一个分不出套话和正常文本的指标,会每次都说
"一切正常" —— 那比没有指标更糟,因为它让人以为这件事已经有人看着了。
所以每个指标都成对测:模板化的一组必须显著差于多样的一组。
"""

from scripts.text_quality_report import (
    anchor_rate,
    banned_phrase_rate,
    cross_work_ngrams,
    head_diversity,
)

# 实测从 prod 抓到的套话骨架(2026-09-13,guide 段 63.8% 这么开头)
TEMPLATED = [
    "Take a moment to really look at the figure on the left. "
    "These details matter because they reveal the artist's intent. "
    "As you stand here, think about the stories this place holds.",
    "Take a moment to really look at the horse in the centre. "
    "These details matter because they reveal the mood of the scene. "
    "As you stand here, think about the stories these walls hold.",
    "Take a moment to really look at the light on the water. "
    "These details matter because they reveal a careful hand. "
    "As you stand here, think about the stories behind the frame.",
]
VARIED = [
    "Napoleon crowned himself in 1804, and David painted it twice. "
    "The second version hangs in Versailles.",
    "Courbet was 29 when he finished this, and the Salon rejected it. "
    "Proudhon defended him in print.",
    "The marble came from Carrara in 1622, shipped up the Tiber on a barge "
    "to Rome for Bernini.",
]


def _rows(bodies):
    return [("Q%d" % i, b) for i, b in enumerate(bodies)]


def test_head_diversity_separates_templated_from_varied():
    t_uniq, t_total, _ = head_diversity(TEMPLATED)
    v_uniq, v_total, _ = head_diversity(VARIED)
    assert t_uniq == 1 and t_total == 3, "三段同一开头应坍缩成 1 种"
    assert v_uniq == 3, "三段不同开头应是 3 种"
    assert t_uniq / t_total < v_uniq / v_total


def test_head_diversity_reports_the_offending_opener():
    """光有比率不够 —— 得说出**是哪句**,否则拿不到可操作的改动。"""
    _, total, top3 = head_diversity(TEMPLATED)
    head, count = top3[0]
    assert count == total
    assert head.startswith("take a moment to really look")


def test_cross_work_ngrams_counts_works_not_occurrences():
    """同一短语在一件里重复十次只算一件。

    否则长文本会自己刷高排名,把真正的跨作品套话压下去 —— 而跨作品复用
    才是"万能句"的定义。
    """
    same_work = [("Q1", "the composition is carefully structured " * 10)]
    three_works = _rows(
        [
            "the composition is carefully structured here",
            "the composition is carefully structured again",
            "the composition is carefully structured once more",
        ]
    )
    assert cross_work_ngrams(same_work)[0][0] == 1
    top = dict((g, n) for n, g in cross_work_ngrams(three_works))
    assert top["the composition is carefully structured"] == 3


def test_cross_work_ngrams_flags_the_templated_group():
    t = cross_work_ngrams(_rows(TEMPLATED))
    v = cross_work_ngrams(_rows(VARIED))
    assert t[0][0] == 3, "套话组应有 5-gram 命中全部 3 件"
    assert v[0][0] == 1, "多样组不该有任何跨作品 5-gram"


def test_anchor_rate_separates_concrete_from_hollow():
    """事实锚点:年份/数字/非句首专名。套话组几乎为零,具体组大部分命中。

    具体组到不了 100% —— 见下面那条已知局限的测试。对 A/B 无影响
    (两组用同一把尺子),但**绝对值不能当合格线看**。
    """
    t_a, t_t = anchor_rate(TEMPLATED)
    v_a, v_t = anchor_rate(VARIED)
    assert t_t > 0 and v_t > 0
    assert t_a / t_t < 0.2, f"套话组锚点率应极低,实际 {t_a}/{t_t}"
    assert v_a / v_t >= 0.75, f"具体组锚点率应明显高,实际 {v_a}/{v_t}"
    assert v_a / v_t > 3 * (t_a / t_t + 0.01), "两组差距应是量级而非微差"


def test_known_limitation_proper_noun_at_sentence_start_is_missed():
    """**已知局限,故意留着**:句首专名不算锚点,所以这句被低估。

    "Proudhon defended him in print." 信息很具体,但 Proudhon 在句首。
    要分开它和 "Paintings can be moving." 得上 NER,不值当 —— 指标宁可
    偏保守(低估),也不要把每句话都判成"有锚点"(那样指标直接废掉)。
    这条测试存在的意义是:以后看到绝对值偏低,先想起这里,别去调阈值。
    """
    a, t = anchor_rate(["Proudhon defended him in print."])
    assert (a, t) == (0, 1)


def test_sentence_initial_capital_is_not_an_anchor():
    """句首大写是语法不是信息。把它当专有名词会让每句话都"有锚点",
    指标直接废掉(这是第一版的 bug,靠这条钉住)。
    """
    a, t = anchor_rate(["Paintings can be moving. Sculptures can be too."])
    assert t == 2 and a == 0


def test_banned_phrase_rate_separates_the_two_groups():
    assert banned_phrase_rate(TEMPLATED) == (3, 3)
    assert banned_phrase_rate(VARIED) == (0, 3)


def test_every_banned_phrase_reaches_both_prompts():
    """清单与 prompt 必须同源,而且是**两个** prompt —— 往清单加一条而某个
    prompt 的拼接漏了,就会出现"报告在统计一条模型从没被禁过的短语",两边
    都显示"通过"。

    为什么必须是两个:黑名单最初只接在头条(guide)上,深度段的 _SYSTEM 没接,
    于是 analysis 段套话命中率 94% 完全没被管到。这正是 category_sections
    那个 bug 的形状(一侧有、一侧没有),所以用测试钉住而不是靠记得。
    """
    from app.services.enrichment.prompts import (
        _DEFAULT_GUIDE_SYSTEM,
        _SYSTEM,
        BANNED_PHRASES,
    )

    for name, prompt in (
        ("深度段 _SYSTEM", _SYSTEM),
        ("头条 guide", _DEFAULT_GUIDE_SYSTEM),
    ):
        missing = [p for p in BANNED_PHRASES if p not in prompt]
        assert not missing, f"{name} 缺这些禁用句: {missing}"
    assert len(BANNED_PHRASES) >= 6


def test_prompts_do_not_hand_the_model_copyable_stock_phrases():
    """prompt **自己举的措辞级例句会变成输出模板** —— 实测过一次:
    深度段 _SYSTEM 曾举例 'notice the red in the corner' 和
    'the brushwork feels restless',结果 analysis 477 段里 "notice how" 命中
    363 段(76%)、"brushwork feels" 64 段(13%,6 段连 "feels restless" 都没改),
    而不讲技法的 background/facts/significance **全为 0**。

    所以"允许引导语"这条语义要保留(接地闸靠它区分事实句与引导句),
    但只能讲类别,不能给可抄的措辞。
    """
    from app.services.enrichment.prompts import _DEFAULT_GUIDE_SYSTEM, _SYSTEM

    for prompt in (_SYSTEM, _DEFAULT_GUIDE_SYSTEM):
        low = prompt.lower()
        for leaked in ("notice the red in the corner", "brushwork feels restless"):
            assert leaked not in low, f"prompt 又把可抄的例句交给模型了: {leaked}"


def test_banned_phrase_detection_uses_the_shared_list(monkeypatch):
    """报告查的就是 prompts 里那份清单,不是手抄的副本。"""
    import app.services.enrichment.prompts as P

    monkeypatch.setattr(P, "BANNED_PHRASES", ["zzz unique marker"])
    assert banned_phrase_rate(["a zzz unique marker b"]) == (1, 1)
    assert banned_phrase_rate(["take a moment to look"]) == (0, 1)


def test_short_fragments_do_not_dilute_the_anchor_rate():
    """片段/标点残渣不计入分母,否则一段的锚点率会被切碎的短句拉低。"""
    a, t = anchor_rate(["Yes. No. David painted this in 1801 for the Salon."])
    assert t == 1 and a == 1
