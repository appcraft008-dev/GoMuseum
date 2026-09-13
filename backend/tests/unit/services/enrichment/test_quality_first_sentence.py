"""闸删掉首句 → 整段挂起,不发布半截正文。

这个错法是**静默**的:段照发,接地率还很好看(0.75-0.88 全在阈值之上),
只有真正去读正文的人才会发现它从半截开始 —— 而没人会逐段读 24000 段。

2026-09-13 prod 全库实测:删过句的 12 段 guide 里 4 段开头坏掉(33%),
没删句的 39 段 0 段。下面三条用例就是那批里的真实开头。
"""

import json

from app.services.enrichment.quality import QualityGate


class _Verdicts:
    def __init__(self, verdicts):
        self._v = verdicts

    def __call__(self, system, user):
        if "grounding judge" in system.lower():
            return json.dumps({"verdicts": self._v})
        return json.dumps({"conflicts": []})


def _gate(verdicts):
    return QualityGate(_Verdicts(verdicts))


def test_first_sentence_dropped_holds_the_section_even_above_threshold():
    """存活率 0.75 > 阈值 0.6,唯独首句被删 —— 仍不发布。

    真实案例(Q2842423 雷诺阿《沃拉尔肖像》):开头介绍沃拉尔是谁的那句被删,
    发布出去的正文第一句是「His profile reveals…」,读者不知道 His 是谁。
    """
    body = (
        "Ambroise Vollard was a dealer who shaped modern art. "
        "His profile reveals a thoughtful demeanor. "
        "The warm palette envelops him. "
        "Renoir's brushwork adds a lively texture."
    )
    r = _gate([False, True, True, True]).check_section("material", "facts", body)
    assert r.grounding_ratio == 0.75, "存活率照常记录真实值"
    assert r.status == "needs_review"
    assert r.body is not None, "正文保留下来,挂起可逆 —— 材料补足后重生成能救回"


def test_whole_first_paragraph_dropped_also_holds():
    """首段整段被删也算首句被删 —— 剩下的从第二段开头起,同样没有上下文。

    ⚠️ 存活率必须**高于**阈值(这里 3/4=0.75),否则它本来就会挂起,
    这条用例就测不到新判据 —— 第一版正是这么写的,撤掉修复照样绿。
    """
    body = (
        "This woodcut shows the Visitation.\n\n"
        "To the left, a bearded man stands in a doorway. "
        "A small dog rests near the steps. "
        "The background shows a mountainous landscape."
    )
    r = _gate([False, True, True, True]).check_section("material", "facts", body)
    assert r.grounding_ratio == 0.75, "存活率高于阈值,只因首句被删而挂起"
    assert r.status == "needs_review"


def test_section_publishes_when_the_opening_survives():
    """首句留住 → 中间句被删不影响发布。

    这条是上面两条的对照组:没有它,把判据写成"删过任何句子就挂起"
    (过严,会砍掉一半正常内容)也能让前两条变绿。
    """
    body = (
        "In 1865, Alfred Sisley painted this avenue of chestnut trees. "
        "Sisley exhibited it at the Salon of 1867. "
        "The trees frame an expanse of blue sky."
    )
    r = _gate([True, False, True]).check_section("material", "facts", body)
    assert r.grounding_ratio > 0.6
    assert r.status == "published"
    assert r.body.startswith("In 1865")


def test_single_sentence_body_whose_only_sentence_is_dropped():
    """只有一句且被删 → body 为空,原本就挂起;别让新判据在 keep 为空时炸掉。"""
    r = _gate([False]).check_section("material", "facts", "Manet invented photography.")
    assert r.body is None
    assert r.status == "needs_review"
