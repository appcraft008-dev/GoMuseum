"""料探针：材料撑不起的 lane 不生成。

判定器本身的准确度靠 prod 标定（注入技法段的合成正样本 8/10 判 true，
剥到只剩标签的负样本 10/10 判三项全 false）——那不是单测能测的。
这里锁的是**接线**：哪些段被闸、fail-open 走不走通、判定通道是不是 0 温。
"""

import pytest

from app.services.enrichment.category_config import MATERIAL_PROBE_LANES
from app.services.enrichment.content_enricher import ContentEnricher

SECTIONS = ["background", "analysis", "significance", "facts"]
OBJ = {"title_en": "X", "artist_en": "Y", "category": "painting", "attributes": {}}


def _enricher(probe_reply, gen=lambda s, u: "{}"):
    calls = []

    def probe(system, user):
        calls.append((system, user))
        return probe_reply

    e = ContentEnricher(gen, probe_complete=probe)
    return e, calls


def test_drops_lanes_without_material():
    e, _ = _enricher('{"technique": false, "legacy": false, "anecdote": true}')
    # background 不受闸（材料的本质就是事件年表，它的料一直够）
    assert e.sections_with_material(OBJ, SECTIONS) == ["background", "facts"]


def test_keeps_everything_when_material_is_rich():
    e, _ = _enricher('{"technique": true, "legacy": true, "anecdote": true}')
    assert e.sections_with_material(OBJ, SECTIONS) == SECTIONS


def test_guide_and_background_never_gated():
    e, _ = _enricher('{"technique": false, "legacy": false, "anecdote": false}')
    assert e.sections_with_material(OBJ, ["guide", "background"]) == [
        "guide",
        "background",
    ]


def test_fail_open_on_probe_error():
    # 判定挂了不该让内容凭空少一截
    def boom(system, user):
        raise RuntimeError("openai down")

    e = ContentEnricher(lambda s, u: "{}", probe_complete=boom)
    assert e.sections_with_material(OBJ, SECTIONS) == SECTIONS


def test_fail_open_on_garbage_reply():
    e, _ = _enricher("not json at all")
    assert e.sections_with_material(OBJ, SECTIONS) == SECTIONS


def test_missing_key_drops_that_lane_only():
    # 缺 key ≠ true。只有显式 true 才留（探针偏保守是刻意的）
    e, _ = _enricher('{"technique": true}')
    assert e.sections_with_material(OBJ, SECTIONS) == ["background", "analysis"]


def test_no_probe_call_when_no_gated_lane():
    e, calls = _enricher('{"technique": true}')
    assert e.sections_with_material(OBJ, ["guide"]) == ["guide"]
    assert calls == []  # 省一次调用


def test_probe_uses_separate_channel_not_generation():
    gen_calls = []
    e, probe_calls = _enricher(
        '{"technique": true, "legacy": true, "anecdote": true}',
        gen=lambda s, u: gen_calls.append(1) or "{}",
    )
    e.sections_with_material(OBJ, SECTIONS)
    assert len(probe_calls) == 1 and gen_calls == []


def test_probe_prompt_carries_the_material():
    e, calls = _enricher('{"technique": true, "legacy": true, "anecdote": true}')
    obj = {**OBJ, "attributes": {"extract_en": "刻意放进材料里的一句话"}}
    e.sections_with_material(obj, SECTIONS)
    assert "刻意放进材料里的一句话" in calls[0][1]


def test_lane_map_covers_exactly_the_three_measured_lanes():
    assert MATERIAL_PROBE_LANES == {
        "analysis": "technique",
        "significance": "legacy",
        "facts": "anecdote",
    }


@pytest.mark.parametrize("falsy", ["false", '"true"', "null", "1"])
def test_only_boolean_true_counts(falsy):
    # 字符串 "true"/数字 1 都不算 —— 探针宁可保守，但不能被类型糊弄
    e, _ = _enricher('{"technique": %s, "legacy": false, "anecdote": false}' % falsy)
    assert "analysis" not in e.sections_with_material(OBJ, SECTIONS)
