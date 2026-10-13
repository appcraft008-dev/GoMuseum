"""评测脚本的纯逻辑:判官解析、写作要求切换与恢复、配对共用 guide、汇总计数。不打网。"""

import pytest

from app.services.enrichment import category_config as cc
from scripts import eval_section_roles as ev

MAT = "[FACTS]\n- year: 1658\n(extract_en) A maid pours milk into an earthenware bowl."


def test_parse_audit_missing_items_are_not_supported():
    items = [{"type": "fact", "verdict": "supported", "quote": "A maid pours milk"}]
    out = ev.parse_audit(items, ["s1", "s2"], MAT)
    assert out[0]["quote_found"] is True
    assert out[1]["verdict"] is None and out[1]["quote_found"] is False


def test_parse_audit_quote_must_be_in_material():
    items = [{"type": "fact", "verdict": "supported", "quote": "painted in Delft"}]
    assert ev.parse_audit(items, ["s"], MAT)[0]["quote_found"] is False


def test_roles_patched_restores_even_on_error():
    before = cc.SECTION_ROLES["background"]["role"]
    with pytest.raises(RuntimeError):
        with ev.roles_patched({"background": {"role": "X", "max_chars": 1}}):
            assert cc.section_role("background")["role"] == "X"
            raise RuntimeError
    assert cc.SECTION_ROLES["background"]["role"] == before


class _Enricher:
    def __init__(self):
        self.guides = 0

    def generate_default_guide(self, obj, facts, chars):
        self.guides += 1
        return "Guide sentence one. Guide sentence two."

    def generate_canonical(self, obj, sections, guide=None):
        # 用当前生效的写作要求区分两组:新要求下 facts 返回空
        new = "EMPTY STRING" in cc.section_role("facts")["role"]
        return {
            "background": "Made in 1658. It was well received.",
            "facts": None if new else "Interestingly, x.",
        }


class _Gate:
    def check_section(self, material, facts, body):
        from app.services.enrichment.quality import SectionQuality

        return SectionQuality(body=body, status="published", grounding_ratio=1.0)


def _auditor(material, sentences):
    return [
        {
            "sentence": s,
            "type": "fact",
            "verdict": (
                "unsupported"
                if "well received" in s or "Interestingly" in s
                else "supported"
            ),
            "quote": "",
            "quote_found": False,
            "claim": s,
        }
        for s in sentences
    ]


def test_run_pair_shares_one_guide_and_labels_status():
    job = dict(
        qid="Q1",
        obj={},
        material=MAT,
        facts="",
        sections=["background", "facts"],
        chars=(270, 420),
    )
    en = _Enricher()
    new_roles = {"facts": {"role": "ONLY ... EMPTY STRING", "max_chars": 200}}
    old_roles = {"facts": {"role": "ONE surprising anecdote.", "max_chars": 200}}
    recs = ev.run_pair(
        job, 0, en, _Gate(), _auditor, {"old": old_roles, "new": new_roles}
    )
    assert en.guides == 1  # 两组共用同一份 guide
    by = {(r["arm"], r["section"]): r for r in recs}
    assert by[("old", "facts")]["status"] == "published"
    assert by[("new", "facts")]["status"] == "empty"
    assert by[("old", "background")]["unsupported"] == ["It was well received."]


def test_summarize_counts_per_arm_and_section():
    recs = [
        dict(
            qid="Q1",
            rep=0,
            arm="old",
            section="facts",
            status="published",
            kept=2,
            unsupported=["a"],
        ),
        dict(
            qid="Q1",
            rep=0,
            arm="new",
            section="facts",
            status="empty",
            kept=0,
            unsupported=[],
        ),
        dict(
            qid="Q2",
            rep=0,
            arm="new",
            section="facts",
            status="needs_review",
            kept=1,
            unsupported=["b"],
        ),
    ]
    s = ev.summarize(recs)
    assert s["old"]["facts"] == {
        "published": 1,
        "needs_review": 0,
        "empty": 0,
        "unsupported": 1,
    }
    assert s["new"]["facts"] == {
        "published": 0,
        "needs_review": 1,
        "empty": 1,
        "unsupported": 1,
    }
