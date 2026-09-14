"""闸删掉首句后,剩下的正文若开头悬空 → 整段挂起,不发布半截正文。

这个错法是**静默**的:段照发,接地率还很好看(0.75-0.89 全在阈值之上),
只有真正去读正文的人才会发现它从半截开始 —— 而没人会逐段读 24000 段。

⚠️ 这个文件的对照组比用例本身更重要。#557 上线的第一版判据是「首句被删就挂起」,
prod 47 件重跑实测**拦下 23 段,其中 17 段完全自洽** —— 大量段的首句被删后
第二句恰好独立成立(技法描述段尤其如此)。下面 `test_keeps_*` 那组就是从那
17 段里取的真实开头,它们必须放行。
"""

import json

import pytest

from app.services.enrichment.quality import QualityGate, _opening_is_orphaned


class _Verdicts:
    def __init__(self, verdicts):
        self._v = verdicts

    def __call__(self, system, user):
        if "grounding judge" in system.lower():
            return json.dumps({"verdicts": self._v})
        return json.dumps({"conflicts": []})


def _gate(verdicts):
    return QualityGate(_Verdicts(verdicts))


# ---- 判据本身:真断裂要拦 --------------------------------------------------


@pytest.mark.parametrize(
    "opening",
    [
        "He had a personal connection to rural life, having grown up in Ornans.",
        "His profile reveals a thoughtful demeanor, accentuated by a beard.",
        "Their flowing garments and tender expressions convey a warmth.",
        "She was the only female artist to exhibit in the first show.",
        "moment of tension between two chess players.",  # 小写 = 被腰斩
    ],
)
def test_orphaned_openings_are_caught(opening):
    assert _opening_is_orphaned(opening) is True


@pytest.mark.parametrize(
    "opening",
    [
        "The rich texture of his brown suit contrasts with the headscarf.",  # 代词在句中
        "This choice allowed Courbet to experiment with texture.",  # This + 抽象名词
        "Sentier de la Mi-côte' is that it was painted on-site.",  # 句中引号被切开
    ],
)
def test_known_misses_are_documented_not_silently_forgotten(opening):
    """这三种断法**故意不拦** —— 每补一种都要加正则分支,而每个分支都带着
    误杀好开头的风险(上一版想一网打尽,误杀了 17 段)。漏 3 段 > 误杀 17 段。

    这条用例存在的意义是:如果哪天有人加了分支把它们拦住了,这里会变红,
    逼他重新做一次误杀评估,而不是默默收紧。
    """
    assert _opening_is_orphaned(opening) is False


# ---- 对照组:自洽的开头必须放行 --------------------------------------------


@pytest.mark.parametrize(
    "opening",
    [
        # 下面 6 条是 #557 第一版判据在 prod 上**误杀**的真实开头
        "The artist's brushwork is meticulous, capturing the textures of the foliage.",
        "The rich, deep red of Madame Ehrler's gown is achieved through layered brushwork.",
        "The painting was executed during a period when Ingres was striving to lead.",
        "The prominent mustache and curly hair of Dumas Jr. are expertly rendered.",
        "A cake named 'Carpeaux' was created in tribute to the artist.",
        "One figure stands with her back to us, draped in a cloth.",  # her 有同句先行词
        # It/Its/This 指作品本身 —— 段落就展示在作品页上,指代成立(全库 46 段)
        "It was commissioned for the coronation of Charles X.",
        "Its significance lies in how it bridges two traditions.",
        "This painting quickly found its home at the Petit Palais.",
    ],
)
def test_self_contained_openings_are_kept(opening):
    assert _opening_is_orphaned(opening) is False


def test_empty_body_is_not_orphaned():
    assert _opening_is_orphaned(None) is False
    assert _opening_is_orphaned("") is False


# ---- 接到闸上 --------------------------------------------------------------


def test_section_is_held_when_the_surviving_opening_is_orphaned():
    """存活率 0.75 > 阈值 0.6,唯独开头悬空 —— 仍不发布。

    真实案例(Q2842423 雷诺阿《沃拉尔肖像》):介绍沃拉尔是谁的首句被删,
    发出去的第一句是「His profile reveals…」,读者不知道 His 是谁。
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


def test_section_publishes_when_the_surviving_opening_stands_on_its_own():
    """首句被删但第二句自洽 → 照常发布。

    **这条是这个文件的核心对照组**:没有它,退回 #557 那版「首句被删就挂起」
    也能让上面那条变绿,而那一版在 prod 上误杀了 17 段好内容。
    """
    body = (
        "Lorrain painted this view for Pope Urban VIII in 1639. "
        "The artist's brushwork is meticulous, capturing the lush foliage. "
        "The composition draws the eye toward the harbour. "
        "Warm hues suggest either dawn or dusk."
    )
    r = _gate([False, True, True, True]).check_section("material", "facts", body)
    assert r.grounding_ratio == 0.75
    assert r.status == "published"
    assert r.body.startswith("The artist's brushwork")


def test_section_publishes_when_the_opening_survives():
    """首句留住 → 中间句被删不影响发布。"""
    body = (
        "In 1865, Alfred Sisley painted this avenue of chestnut trees. "
        "Sisley exhibited it at the Salon of 1867. "
        "The trees frame an expanse of blue sky."
    )
    r = _gate([True, False, True]).check_section("material", "facts", body)
    assert r.status == "published"
    assert r.body.startswith("In 1865")


def test_single_sentence_body_whose_only_sentence_is_dropped():
    """只有一句且被删 → body 为空,原本就挂起;别让新判据在空 body 上炸掉。"""
    r = _gate([False]).check_section("material", "facts", "Manet invented photography.")
    assert r.body is None
    assert r.status == "needs_review"
