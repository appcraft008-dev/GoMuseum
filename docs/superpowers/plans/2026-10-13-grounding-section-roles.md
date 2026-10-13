# 四段写作要求「材料没说就留空」 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 background / analysis / facts / material-technique 四段的写作要求改成「只写材料明说的，没有就返回空」。用真实生成的 A/B 评测证明编造减半、内容不靠挂起变少。上线时给存量划线并存快照。

**Architecture:** 只改 `category_config.SECTION_ROLES` 里四段的 `role` 文本，闸、guide、翻译都不动。新增两个仓库脚本：
- `eval_section_roles.py`：在 prod 容器里新旧写作要求配对生成、过现行闸、复核，只读不落库。
- `snapshot_grounding_baseline.py`：上线时存 sha 快照。

**Tech Stack:** Python 3.13 / SQLAlchemy / pytest。LLM 走 `default_complete`。

**Spec:** `docs/superpowers/specs/2026-10-13-grounding-gate-reliability-design.md`

## Global Constraints

- 不动 `_ENTAILMENT_SYSTEM`、`QualityGate`、`GROUNDING_THRESHOLD`、guide 提示词、翻译与忠实度闸（spec §3）。
- 存量不改、不重判、不重生成；只按 §6 划线 + 快照，不写库、不加字段。
- 评测在 prod 只读：不调用任何 `persist_*`，不 commit。LLM 用量记 channel `eval_section_roles`。
- 评测和快照的输出（含材料原文或正文 sha）不进仓库。
- 上线门槛（spec §5）：
  - 四段闸放行的人工确认无出处句总数降到旧写法一半以下。
  - 四段「发布 + 主动留空」不少于旧写法的「发布」。
  - guide 状态变化逐件说明。
  - 结果报给用户再上线。
- worktree 里 husky 钩子不跑：提交前手动跑 `black` + `isort --profile black`，推送前 `black --check`。
- 本地测试命令：`/Users/hongyang/Library/Caches/pypoetry/virtualenvs/gomuseum-backend-eWQPCnDy-py3.13/bin/python -m pytest -q --no-cov -p no:cacheprovider`（下文记作 `$PY -m pytest …`）。
- 每次 commit 结尾带：
  ```
  Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_01EQgJmCjbBm5Z2hmZMXmurZ
  ```

## Review Focus

- 新写作要求让 guide 之外的**所有**段都返回空时：`content_status` 仍由 guide 决定为 ready，不能因为深度段全空变成 empty。由 Task 1 的管线测试钉住。
- 评测里新旧两组必须用**同一份 guide**（每件每遍生成一次，两组共用），否则差异混进 guide 的随机性。由 Task 2 的 `run_pair` 测试钉住。
- 判官返回条目少于句子数或不是 JSON 时：缺的句子记 `verdict=None`，不能当成「有出处」。由 Task 2 的 `parse_audit` 测试钉住。
- 两组切换写作要求是改一个模块级 dict：一组跑完必须恢复原值，异常也要恢复，否则同进程后续调用全用错的要求。由 Task 2 的 `roles_patched` 测试钉住。
- 快照里同一段的正文 sha 必须和 DB 里 body 逐字节对应（utf-8，不做 strip），否则以后比对「正文没变」会全部误判。由 Task 4 测试钉住。

---

### Task 1: 四段写作要求改成「材料没说就留空」

**Files:**
- Modify: `backend/app/services/enrichment/category_config.py:277-283`（background、analysis）、`:300-303`（facts）、`:312-315`（material-technique）
- Test: `backend/tests/unit/services/enrichment/test_category_config.py`
- Test: `backend/tests/integration/test_generate_pipeline.py`（追加一条）

**Interfaces:**
- Produces: `SECTION_ROLES[code]["role"]`，四段都含子串 `"MATERIAL explicitly states"` 和 `"EMPTY STRING"`。Task 2 的 `OLD_ROLES` 保存本 Task 改动**前**的原文。

- [ ] **Step 1: 写失败测试**（追加到 `test_category_config.py` 末尾）

```python
import pytest


@pytest.mark.parametrize("code", ["background", "analysis", "facts", "material-technique"])
def test_lane_only_from_material_or_empty(code):
    """10-13 P1-9B:照 significance 的做法,材料没说就留空,不许用常识/风格补。"""
    from app.services.enrichment.category_config import SECTION_ROLES

    role = SECTION_ROLES[code]["role"]
    assert "MATERIAL explicitly states" in role
    assert "EMPTY STRING" in role


def test_background_no_longer_demands_commission_and_reception():
    """旧要求「who commissioned it… the reception」逼模型编委托和评价(摸底 B background 21 句)。"""
    from app.services.enrichment.category_config import SECTION_ROLES

    assert "who commissioned it" not in SECTION_ROLES["background"]["role"]


def test_analysis_technique_only_when_stated():
    """摸底 B:编外观 46 句里 42 句出自有看图描述的件——照片给不出笔触。"""
    from app.services.enrichment.category_config import SECTION_ROLES

    assert "NOT evidence of brushwork" in SECTION_ROLES["analysis"]["role"]
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && $PY -m pytest tests/unit/services/enrichment/test_category_config.py -k "lane_only or commission or technique_only"`
Expected: 6 failed（4 个参数化 + 2 个）

- [ ] **Step 3: 改写四段 role**（`max_chars` 不动）

```python
    "background": {
        # 10-13 P1-9B:原文「who commissioned it… the reception as events」逼模型在材料没有时编委托/评价
        # (摸底 B:闸放行的 background 无出处句 21 句)。照 significance 10-12 的做法改成材料没说就留空。
        "role": (
            "The work's HISTORY as concrete events — ONLY what the MATERIAL explicitly states: "
            "when it was made, who commissioned or acquired it, where it was shown, how it was "
            "received, provenance. Include only the items the material actually gives; do NOT "
            "fill gaps from general knowledge, style or period (no guessed commissions, no "
            "'well-received' or 'mixed reception' unless stated). If the material states none of "
            "this, return an EMPTY STRING for this section. NOT why-it-matters (that's "
            "significance), NOT how-to-look (that's analysis)."
        ),
        "max_chars": 380,
    },
    "analysis": {
        # 10-13 P1-9B:原文要求 brushwork/paint handling,照片描述给不出技法 → 编(摸底 B 37 句)。
        "role": (
            "HOW it looks and how it's made — ONLY what the MATERIAL explicitly states, "
            "including the [VISIBLE IN THE ARTWORK] description: colours, composition, figures "
            "and objects, light, scale. Describe technique (brushwork, paint handling, layering) "
            "ONLY when the material states it; a photograph description is NOT evidence of "
            "brushwork. Do NOT re-list the symbols/subjects the headline guide already pointed "
            "out; go beyond naming them. If the material gives neither a visual description nor "
            "technique, return an EMPTY STRING for this section."
        ),
        "max_chars": 380,
    },
```

```python
    "facts": {
        # 10-13 P1-9B:「ONE surprising anecdote」在材料没有轶事时催出「Interestingly, …」加编造修饰
        # (摸底 B facts 14/30 段被闸挂起)。
        "role": (
            "ONE surprising anecdote or curiosity that the MATERIAL explicitly states and no other "
            "lane covers. If the material has no such specific fact, return an EMPTY STRING for "
            "this section — do NOT write generic 'Interestingly, …' observations or embellish a "
            "plain fact with unstated context."
        ),
        "max_chars": 200,
    },
```

```python
    "material-technique": {
        "role": (
            "Guided looking at how it was made — only the material and craft the MATERIAL "
            "explicitly states (medium, technique, details in the [VISIBLE IN THE ARTWORK] "
            "description). Do NOT infer technique from the medium alone. If the material states "
            "none of this, return an EMPTY STRING for this section."
        ),
        "max_chars": 200,
    },
```

- [ ] **Step 4: 写管线测试**(Review Focus 第 1 条):深度段全返回空、guide 已发布 → `content_status` 仍为 ready

追加到 `backend/tests/integration/test_generate_pipeline.py` 末尾(复用该文件的 `session` fixture、`_FakeEnricher`、`_FakeGate`、`_FakeTranslator`、`generate_object`):

```python
def test_all_deep_sections_empty_keeps_ready_with_guide(session):
    """10-13 P1-9B:新写作要求下深度段可能全返回空;guide 已发布时这件仍是 ready。"""
    from app.models.content import ObjectContentSection
    from app.models.museum_object import MuseumObject
    from app.services.enrichment.quality import SectionQuality

    class _Enr(_FakeEnricher):
        def generate_default_guide(self, obj, facts, target_chars):
            return "Guide hook."

        def generate_canonical(self, obj, sections, guide=None):
            return {code: None for code in sections}

    class _G(_FakeGate):
        def check_section(self, m, f, b):
            return SectionQuality(
                body=b, status="published", grounding_ratio=1.0, conflicts=[], score=1.0
            )

        def gate(self, m, f, draft):  # 与 QualityGate.gate 同语义:空段跳过
            return {c: self.check_section(m, f, b) for c, b in draft.items() if b}

    generate_object(
        session,
        "Q1",
        enricher=_Enr(),
        gate=_G(),
        translator=_FakeTranslator(),
        target_langs=["en"],
        model="m",
    )
    o = session.query(MuseumObject).filter_by(qid="Q1").one()
    assert o.content_status == "ready"
    codes = {
        s.section_code
        for s in session.query(ObjectContentSection).filter_by(
            object_id=o.id, language="en"
        )
    }
    assert codes == {"guide"}
```

这条测试锁住的是**现有**行为(Task 1 不改管线),所以写完直接通过是预期的:它是防回退护栏,不是 RED→GREEN。在 ledger 记一条 `Ruling: Task 1 Step 4 测试先于实现即通过——锁现有行为`。

- [ ] **Step 5: 跑测试确认通过**

Run: `cd backend && $PY -m pytest tests/unit/services/enrichment/ tests/integration/test_generate_pipeline.py`
Expected: 全部 PASS。`test_analysis_lane_focuses_craft_not_symbols` 仍过（新 analysis 文本含 `brushwork` 与 `headline`）；`test_section_roles_are_distinct_lanes` 仍过（background 含 `history`/`event`）。

- [ ] **Step 6: 格式化 + 全量 unit + 提交**

```bash
cd backend && $PY -m black app tests && $PY -m isort --profile black app/services/enrichment/category_config.py tests/unit/services/enrichment/
$PY -m pytest tests/unit 2>&1 | tail -2
git add app/services/enrichment/category_config.py tests/unit/services/enrichment/test_category_config.py tests/integration/test_generate_pipeline.py
git commit -m "feat(enrichment): 背景/赏析/小知识/材料工艺只写材料明说的,没有就留空(P1-9B)"
```

---

### Task 2: A/B 评测脚本 `eval_section_roles.py`

**Files:**
- Create: `backend/scripts/eval_section_roles.py`
- Test: `backend/tests/unit/scripts/test_eval_section_roles.py`

**Interfaces:**
- Consumes: Task 1 改动后的 `category_config.py`。评测时把这个文件 `docker cp` 到 prod 容器 `/tmp/category_config_new.py`，用 `--new-config` 加载它的 `SECTION_ROLES`。
- Produces:
  - `parse_audit(items: list, sentences: list[str], material: str) -> list[dict]`：每条含 `sentence,type,verdict,quote,quote_found,claim`。
  - `roles_patched(roles: dict)`：上下文管理器。
  - `run_pair(job, rep, enricher, gate, auditor, arms: dict) -> list[dict]`：每条记录含 `qid,rep,arm,section,status,kept,unsupported`，其中 status ∈ published / needs_review / empty。
  - `summarize(records: list[dict]) -> dict`。
  - CLI：`python scripts/eval_section_roles.py --new-config PATH --n 30 --reps 3 --out PATH`。

- [ ] **Step 1: 写失败测试** `backend/tests/unit/scripts/test_eval_section_roles.py`

```python
"""评测脚本的纯逻辑:判官解析、写作要求切换与恢复、配对共用 guide、汇总计数。不打网。"""

import pytest

from scripts import eval_section_roles as ev
from app.services.enrichment import category_config as cc

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
        return {"background": "Made in 1658. It was well received.", "facts": None if new else "Interestingly, x."}


class _Gate:
    def check_section(self, material, facts, body):
        from app.services.enrichment.quality import SectionQuality

        return SectionQuality(body=body, status="published", grounding_ratio=1.0)


def _auditor(material, sentences):
    return [
        {"sentence": s, "type": "fact", "verdict": "unsupported" if "well received" in s or "Interestingly" in s else "supported", "quote": "", "quote_found": False, "claim": s}
        for s in sentences
    ]


def test_run_pair_shares_one_guide_and_labels_status():
    job = dict(qid="Q1", obj={}, material=MAT, facts="", sections=["background", "facts"], chars=(270, 420))
    en = _Enricher()
    new_roles = {k: dict(v) for k, v in cc.SECTION_ROLES.items()}
    new_roles["facts"] = {"role": "ONLY ... EMPTY STRING", "max_chars": 200}
    old_roles = {"facts": {"role": "ONE surprising anecdote.", "max_chars": 200}}
    recs = ev.run_pair(job, 0, en, _Gate(), _auditor, {"old": old_roles, "new": new_roles})
    assert en.guides == 1  # 两组共用同一份 guide
    by = {(r["arm"], r["section"]): r for r in recs}
    assert by[("old", "facts")]["status"] == "published"
    assert by[("new", "facts")]["status"] == "empty"
    assert by[("old", "background")]["unsupported"] == ["It was well received."]


def test_summarize_counts_per_arm_and_section():
    recs = [
        dict(qid="Q1", rep=0, arm="old", section="facts", status="published", kept=2, unsupported=["a"]),
        dict(qid="Q1", rep=0, arm="new", section="facts", status="empty", kept=0, unsupported=[]),
        dict(qid="Q2", rep=0, arm="new", section="facts", status="needs_review", kept=1, unsupported=["b"]),
    ]
    s = ev.summarize(recs)
    assert s["old"]["facts"] == {"published": 1, "needs_review": 0, "empty": 0, "unsupported": 1}
    assert s["new"]["facts"] == {"published": 0, "needs_review": 1, "empty": 1, "unsupported": 1}
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && $PY -m pytest tests/unit/scripts/test_eval_section_roles.py`
Expected: ERROR `ModuleNotFoundError: scripts.eval_section_roles`

- [ ] **Step 3: 实现** `backend/scripts/eval_section_roles.py`

```python
"""段落写作要求 A/B 评测(P1-9B,spec docs/superpowers/specs/2026-10-13-grounding-gate-reliability-design.md §5)。

在 prod 容器里只读运行:同一批件,新旧写作要求各生成一遍深度段,**共用同一份 guide**,
都过现行接地闸,再用 gpt-4o 判官逐句复核闸放行的句子。不调用任何 persist,不落库。

判官要求每句给材料原文引文,程序核对引文确在材料里(quote_found)。判官标出的
无出处句要人工逐条核对后才算数 —— 本脚本只产出候选,不产出结论。

用法(prod 容器内):
  python scripts/eval_section_roles.py --new-config /tmp/category_config_new.py \
      --n 30 --reps 3 --out /tmp/eval_roles.json
"""

import argparse
import contextlib
import importlib.util
import json
import random
import re
import sys

sys.path.insert(0, "/app")

from app.services.enrichment import category_config as cc  # noqa: E402

SEED = 20261013
TARGET = ("background", "analysis", "facts", "material-technique")

# Task 1 改动前的原文(逐字),作为对照组
OLD_ROLES = {
    "background": {
        "role": "The work's HISTORY as concrete events: when, who commissioned it, where shown, the reception as events, provenance. NOT why-it-matters (that's significance), NOT how-to-look (that's analysis).",
        "max_chars": 380,
    },
    "analysis": {
        "role": "HOW it's painted — the craft: brushwork, paint handling, light & colour, composition structure, scale. Explain technique and the choices behind the effect. Do NOT re-list the symbols/subjects the headline guide already pointed out; go beyond naming them to how the painting achieves its impact.",
        "max_chars": 380,
    },
    "facts": {
        "role": "ONE surprising anecdote/curiosity not covered by other lanes.",
        "max_chars": 200,
    },
    "material-technique": {
        "role": "Guided looking at how it was made: material and craft a visitor can notice.",
        "max_chars": 200,
    },
}

AUDIT_SYS = (
    "You audit sentences from a museum audio guide against the SOURCE MATERIAL the guide was "
    "written from. For EACH numbered sentence return an object:\n"
    '{"i": n, "type": "fact"|"visual"|"framing"|"impression", "verdict": '
    '"supported"|"unsupported"|"contradicted"|"n/a", "quote": "...", "claim": "..."}\n'
    "- type fact = any checkable claim about the work, artist, history, influence, reception, "
    "dates, names, places, techniques. Claims about influence/legacy ('inspired X', "
    "'influenced countless artists') ARE facts.\n"
    "- type visual = a claim about what the artwork looks like (colours, objects, composition, "
    "texture, background), even if phrased softly.\n"
    "- framing = directions to the listener, transitions, rhetorical questions with no claim.\n"
    "- impression = purely subjective feeling that implies no checkable fact.\n"
    "- For fact/visual: verdict supported ONLY if the material states it; give in `quote` the "
    "shortest VERBATIM span (copied exactly) from the material that supports it. If the "
    "sentence has several claims, ALL must be supported. If any part is missing from the "
    "material → unsupported, and put that part in `claim`. If the material says otherwise → "
    "contradicted. Real-world truth does not matter; only the material.\n"
    "- For framing/impression: verdict n/a.\n"
    'Return STRICT JSON: {"items": [...]} one per sentence, same order.'
)


def _norm(t) -> str:
    return re.sub(r"\s+", " ", t or "").strip().lower()


def parse_audit(items: list, sentences: list[str], material: str) -> list[dict]:
    """判官输出 → 每句一条。缺条目/非 dict → verdict None(绝不当成有出处)。"""
    m = _norm(material)
    out = []
    for i, s in enumerate(sentences):
        it = items[i] if i < len(items) and isinstance(items[i], dict) else {}
        q = _norm(it.get("quote"))
        out.append(
            {
                "sentence": s,
                "type": it.get("type"),
                "verdict": it.get("verdict"),
                "quote": it.get("quote"),
                "quote_found": bool(q) and q in m,
                "claim": it.get("claim"),
            }
        )
    return out


def make_auditor(complete):
    from app.services.enrichment.content_enricher import _parse_json

    def auditor(material: str, sentences: list[str]) -> list[dict]:
        if not sentences:
            return []
        numbered = "\n".join(f"{i + 1}. {s}" for i, s in enumerate(sentences))
        raw = complete(AUDIT_SYS, f"MATERIAL:\n{material}\n\nSENTENCES:\n{numbered}")
        return parse_audit((_parse_json(raw) or {}).get("items") or [], sentences, material)

    return auditor


@contextlib.contextmanager
def roles_patched(roles: dict):
    """临时替换 SECTION_ROLES 里给定的段;退出(含异常)时逐个恢复。"""
    saved = {k: cc.SECTION_ROLES.get(k) for k in roles}
    try:
        cc.SECTION_ROLES.update(roles)
        yield
    finally:
        for k, v in saved.items():
            if v is None:
                cc.SECTION_ROLES.pop(k, None)
            else:
                cc.SECTION_ROLES[k] = v


def _is_unsupported(r: dict) -> bool:
    return r["type"] in ("fact", "visual") and r["verdict"] in (
        "unsupported",
        "contradicted",
    )


def run_pair(job, rep, enricher, gate, auditor, arms: dict) -> list[dict]:
    """一件一遍:生成一次 guide,两组共用;各组生成深度段 → 过闸 → 复核放行句。"""
    from app.services.enrichment.quality import _split_sentences

    guide = enricher.generate_default_guide(job["obj"], job["facts"], job["chars"])
    recs = []
    for arm, roles in arms.items():
        with roles_patched({k: roles[k] for k in TARGET if k in roles}):
            draft = enricher.generate_canonical(job["obj"], job["sections"], guide=guide)
        for code in job["sections"]:
            body = (draft or {}).get(code)
            if not body:
                recs.append(dict(qid=job["qid"], rep=rep, arm=arm, section=code, status="empty", kept=0, unsupported=[]))
                continue
            q = gate.check_section(job["material"], job["facts"], body)
            kept = _split_sentences(q.body or "")
            audit = auditor(job["material"], kept)
            recs.append(
                dict(
                    qid=job["qid"],
                    rep=rep,
                    arm=arm,
                    section=code,
                    status=q.status,
                    kept=len(kept),
                    unsupported=[r["sentence"] for r in audit if _is_unsupported(r)],
                    audit=audit,
                )
            )
    return recs


def summarize(records: list[dict]) -> dict:
    out: dict = {}
    for r in records:
        c = out.setdefault(r["arm"], {}).setdefault(
            r["section"], {"published": 0, "needs_review": 0, "empty": 0, "unsupported": 0}
        )
        c[r["status"]] = c.get(r["status"], 0) + 1
        c["unsupported"] += len(r["unsupported"])
    return out


def _load_roles(path: str) -> dict:
    spec = importlib.util.spec_from_file_location("category_config_new", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return {k: mod.SECTION_ROLES[k] for k in TARGET}


def _jobs(n: int) -> list[dict]:
    from app.core.database import SessionLocal
    from app.models.content import ObjectContentSection
    from app.models.museum_object import MuseumObject
    from app.services.enrichment.category_config import guide_target_chars, sections_for
    from app.services.enrichment.content_enricher import build_material
    from app.services.enrichment.pipeline import _facts_text, _row_to_obj

    db = SessionLocal()
    try:
        qids = [
            q
            for (q,) in db.query(MuseumObject.qid)
            .join(ObjectContentSection, ObjectContentSection.object_id == MuseumObject.id)
            .filter(
                ObjectContentSection.language == "en",
                ObjectContentSection.section_code == "guide",
                ObjectContentSection.status == "published",
            )
            .order_by(MuseumObject.qid)
            .distinct()
        ]
        random.seed(SEED)  # 与 10-13 摸底 B 同一批件
        jobs = []
        for q in random.sample(qids, n):
            o = db.query(MuseumObject).filter_by(qid=q).one()
            obj = _row_to_obj(o)
            jobs.append(
                dict(
                    qid=q,
                    obj=obj,
                    material=build_material(obj),
                    facts=_facts_text(obj),
                    sections=sections_for(o.category),
                    chars=guide_target_chars(o.popularity),
                )
            )
        return jobs
    finally:
        db.close()


def main() -> int:
    from app.services.enrichment.content_enricher import ContentEnricher, default_complete
    from app.services.enrichment.quality import QualityGate

    ap = argparse.ArgumentParser()
    ap.add_argument("--new-config", required=True)
    ap.add_argument("--n", type=int, default=30)
    ap.add_argument("--reps", type=int, default=3)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    ch = "eval_section_roles"
    enricher = ContentEnricher(lambda s, u, model="gpt-4o-mini": default_complete(s, u, model, channel=ch))
    gate = QualityGate(lambda s, u, model="gpt-4o-mini": default_complete(s, u, model, channel=ch, temperature=0))
    auditor = make_auditor(lambda s, u: default_complete(s, u, "gpt-4o", channel=ch, temperature=0))
    arms = {"old": OLD_ROLES, "new": _load_roles(a.new_config)}
    jobs = _jobs(a.n)

    # ponytail: 整体串行——两组切换写作要求改的是模块级 dict,并发会串组。30×3 件约 1 小时;要快再按组分进程。
    records = []
    for rep in range(a.reps):
        for j in jobs:
            try:
                records += run_pair(j, rep, enricher, gate, auditor, arms)
            except Exception as e:  # 单件失败不中断整批,记下来
                records.append(dict(qid=j["qid"], rep=rep, arm="error", section="-", status="error", kept=0, unsupported=[], error=repr(e)))
    summary = summarize([r for r in records if r["arm"] != "error"])
    with open(a.out, "w") as f:
        json.dump({"summary": summary, "records": records}, f, ensure_ascii=False, indent=1)
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    print("errors", sum(r["arm"] == "error" for r in records))
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

注：status=error 的记录在 main 里先过滤掉，不进 `summarize`。

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && $PY -m pytest tests/unit/scripts/test_eval_section_roles.py`
Expected: 6 passed

- [ ] **Step 5: 格式化 + 提交**

```bash
cd backend && $PY -m black scripts/eval_section_roles.py tests/unit/scripts/test_eval_section_roles.py && $PY -m isort --profile black scripts/eval_section_roles.py tests/unit/scripts/test_eval_section_roles.py
$PY -m pytest tests/unit 2>&1 | tail -2
git add scripts/eval_section_roles.py tests/unit/scripts/test_eval_section_roles.py
git commit -m "test(eval): 段落写作要求 A/B 评测脚本(配对共用 guide,只读)"
```

---

### Task 3: 跑评测、人工核对、报用户（门槛，停）

**Files:** 无代码改动。输出在会话 scratchpad。

- [ ] **Step 1: 冒烟**：最小样本跑通整条流程

在 prod 容器里（`docker cp` 脚本和 Task 1 的 `category_config.py` 到 `/tmp`），先跑一个最小样本，确认整条流程能跑：

```bash
ssh -i ~/.ssh/deepmeeting_deploy root@38.242.207.219 \
  'docker exec gomuseum_prod_backend sh -c "cd /app && nice -n 19 python /tmp/eval_section_roles.py --new-config /tmp/category_config_new.py --n 2 --reps 1 --out /tmp/eval_smoke.json"'
```
Expected: 打印 summary，`errors 0`。

- [ ] **Step 2: 正式跑**（后台，`docker exec -d`，nice 19）：`--n 30 --reps 3 --out /tmp/eval_roles.json`，跑完拷回 scratchpad。

- [ ] **Step 2b: 判官抖动**（spec §8）：取 old 组 rep 0 中 10 段非空记录，用同一判官再复核一次，比较两次标出的无出处句集合

```python
# prod 容器内:python -c 下执行(或存成 /tmp/jitter.py)
import json, sys; sys.path.insert(0, "/tmp"); sys.path.insert(0, "/app")
from eval_section_roles import make_auditor
from app.services.enrichment.content_enricher import default_complete
d = json.load(open("/tmp/eval_roles.json"))
recs = [r for r in d["records"] if r["arm"] == "old" and r["rep"] == 0 and r.get("audit")][:10]
from eval_section_roles import _jobs
mats = {j["qid"]: j["material"] for j in _jobs(30)}
aud = make_auditor(lambda s, u: default_complete(s, u, "gpt-4o", channel="eval_section_roles", temperature=0))
same = tot = 0
for r in recs:
    a2 = aud(mats[r["qid"]], [x["sentence"] for x in r["audit"]])
    s1 = set(r["unsupported"])
    s2 = {x["sentence"] for x in a2 if x["type"] in ("fact", "visual") and x["verdict"] in ("unsupported", "contradicted")}
    same += len(s1 & s2); tot += len(s1 | s2)
print("jitter agreement", same, "/", tot)
```

- [ ] **Step 3: 人工核对**：两组闸放行、判官标为无出处的句子，逐条对照材料，用摸底同一套类别标注（E/U/M/I/V/F）。只有 E/U/V 计入「无出处」。另抽 5 句判官判「有出处」的句子核对。

- [ ] **Step 4: 按门槛出表**：
  - 四段各自新旧两组的 E/U/V 句数，3 遍各自的数字和均值。
  - 四段的发布 / 挂起 / 主动留空计数。
  - guide 状态有没有变（guide 两组共用，这里应为全同；不同就是 bug）。
  - 判官误标率。

  报给用户，**停下等用户决定**是否上线。

---

### Task 4: 存量快照脚本 `snapshot_grounding_baseline.py`

**Files:**
- Create: `backend/scripts/snapshot_grounding_baseline.py`
- Test: `backend/tests/unit/scripts/test_snapshot_grounding_baseline.py`

**Interfaces:**
- Produces:
  - `build_snapshot(db) -> dict`，键为 `sections`、`questions`、`museums`。
  - `sha(text: str | None) -> str | None`：utf-8，不 strip。
  - CLI：`python scripts/snapshot_grounding_baseline.py --out PATH.json.gz`。

- [ ] **Step 1: 写失败测试**

```python
"""存量划线快照(spec §6):sha 必须与 DB 正文逐字节对应,以后才能判「正文没变」。"""

import gzip
import hashlib
import json
from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.content import (
    CategorySection,
    ObjectContentSection,
    ObjectSuggestedQuestion,
    SectionType,
)
from app.models.museum import Museum
from app.models.museum_object import MuseumObject
from scripts import snapshot_grounding_baseline as snap


@pytest.fixture()
def db():
    e = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(
        bind=e,
        tables=[Museum.__table__, MuseumObject.__table__, SectionType.__table__, CategorySection.__table__, ObjectContentSection.__table__, ObjectSuggestedQuestion.__table__],
    )
    s = sessionmaker(bind=e)()
    yield s
    s.close()


def test_sha_is_exact_bytes_no_strip():
    assert snap.sha(" a\n") == hashlib.sha256(" a\n".encode("utf-8")).hexdigest()
    assert snap.sha(None) is None


def test_snapshot_only_published_en_sections_and_published_questions(db):
    m = Museum(slug="m", name_en="M", description_i18n={"en": "Intro.", "fr": "Intro FR."})
    db.add(m)
    db.commit()
    o = MuseumObject(museum_id=m.id, qid="Q1")
    db.add(o)
    db.commit()
    db.add_all(
        [
            ObjectContentSection(object_id=o.id, language="en", section_code="guide", body="G.", status="published", generated_at=datetime(2026, 10, 1)),
            ObjectContentSection(object_id=o.id, language="en", section_code="facts", body="F.", status="needs_review"),
            ObjectContentSection(object_id=o.id, language="fr", section_code="guide", body="G fr.", status="published"),
            ObjectSuggestedQuestion(object_id=o.id, language="en", sort=1, question="q", answer="A.", status="published"),
            ObjectSuggestedQuestion(object_id=o.id, language="en", sort=2, question="q2", answer="B.", status="needs_review"),
        ]
    )
    db.commit()
    s = snap.build_snapshot(db)
    assert [(r["qid"], r["section"]) for r in s["sections"]] == [("Q1", "guide")]
    assert s["sections"][0]["sha"] == snap.sha("G.")
    assert s["sections"][0]["generated_at"] == "2026-10-01T00:00:00"
    assert [(r["qid"], r["language"], r["sort"]) for r in s["questions"]] == [("Q1", "en", 1)]
    assert s["questions"][0]["sha"] == snap.sha("q\nA.")
    assert s["museums"] == [{"slug": "m", "sha": {"en": snap.sha("Intro."), "fr": snap.sha("Intro FR.")}}]


def test_cli_writes_gzip_json(db, tmp_path, monkeypatch):
    monkeypatch.setattr(snap, "_session", lambda: db)
    out = tmp_path / "s.json.gz"
    assert snap.main(["--out", str(out)]) == 0
    doc = json.loads(gzip.decompress(out.read_bytes()))
    assert set(doc) >= {"at", "sections", "questions", "museums"}
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && $PY -m pytest tests/unit/scripts/test_snapshot_grounding_baseline.py`
Expected: ERROR `ModuleNotFoundError`

- [ ] **Step 3: 实现**

```python
"""存量划线快照(P1-9B spec §6):新写作要求上 prod 当天跑一次,存旧产物的指纹。

以后判断某段是不是旧写作要求的产物:id 在快照里且正文 sha 没变。
不靠 generated_at —— 修补脚本(如 fix_guide_museum_ending.py)走 _upsert_section 会刷新它,
内容却还是旧的。只读,不写库。

用法(prod 容器):
  python scripts/snapshot_grounding_baseline.py --out /tmp/grounding-baseline-<D>.json.gz
然后拷到宿主机 /opt/gomuseum/backups/。
"""

import argparse
import gzip
import hashlib
import json
import sys
from datetime import datetime, timezone

sys.path.insert(0, "/app")


def sha(text):
    return None if text is None else hashlib.sha256(text.encode("utf-8")).hexdigest()


def build_snapshot(db) -> dict:
    from app.models.content import ObjectContentSection, ObjectSuggestedQuestion
    from app.models.museum import Museum
    from app.models.museum_object import MuseumObject

    sections = [
        {
            "id": str(s.id),
            "qid": qid,
            "section": s.section_code,
            "generated_at": s.generated_at.isoformat() if s.generated_at else None,
            "sha": sha(s.body),
        }
        for s, qid in db.query(ObjectContentSection, MuseumObject.qid)
        .join(MuseumObject, MuseumObject.id == ObjectContentSection.object_id)
        .filter(ObjectContentSection.language == "en", ObjectContentSection.status == "published")
        .order_by(MuseumObject.qid, ObjectContentSection.section_code)
    ]
    questions = [
        {
            "id": str(q.id),
            "qid": qid,
            "language": q.language,
            "sort": q.sort,
            "sha": sha(f"{q.question}\n{q.answer}"),
        }
        for q, qid in db.query(ObjectSuggestedQuestion, MuseumObject.qid)
        .join(MuseumObject, MuseumObject.id == ObjectSuggestedQuestion.object_id)
        .filter(ObjectSuggestedQuestion.status == "published")
        .order_by(MuseumObject.qid, ObjectSuggestedQuestion.language, ObjectSuggestedQuestion.sort)
    ]
    museums = [
        {"slug": m.slug, "sha": {k: sha(v) for k, v in sorted((m.description_i18n or {}).items())}}
        for m in db.query(Museum).order_by(Museum.slug)
        if m.description_i18n
    ]
    return {"sections": sections, "questions": questions, "museums": museums}


def _session():
    from app.core.database import SessionLocal

    return SessionLocal()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    db = _session()
    try:
        doc = {"at": datetime.now(timezone.utc).isoformat(), **build_snapshot(db)}
    finally:
        db.close()
    with open(a.out, "wb") as f:
        f.write(gzip.compress(json.dumps(doc, ensure_ascii=False).encode("utf-8")))
    print(f"sections {len(doc['sections'])} questions {len(doc['questions'])} museums {len(doc['museums'])} → {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

测试里的 `db` fixture 是 test 的 session，`main` 的 `finally: db.close()` 会把它关掉。sqlite 内存库加 StaticPool，关 session 不丢数据，测试照样能过；如果实测会影响后续断言，把 `test_cli_writes_gzip_json` 放到文件最后即可。

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && $PY -m pytest tests/unit/scripts/test_snapshot_grounding_baseline.py`
Expected: 3 passed

- [ ] **Step 5: 格式化 + 全量 + 提交**

```bash
cd backend && $PY -m black scripts tests && $PY -m isort --profile black scripts/snapshot_grounding_baseline.py tests/unit/scripts/test_snapshot_grounding_baseline.py
$PY -m pytest tests/unit tests/integration 2>&1 | tail -2
git add scripts/snapshot_grounding_baseline.py tests/unit/scripts/test_snapshot_grounding_baseline.py
git commit -m "feat(ops): 存量划线快照脚本(正文 sha,不靠 generated_at)"
```

---

### Task 5: 上 staging、上线、划线（用户批准后）

**Files:**
- Modify: `docs/ops/backlog.md`（P1-9B 行）

- [ ] **Step 1**：Task 3 用户批准后，推分支，向 staging 提 PR（spec、plan、Task 1/2/4 一起）。CI 全绿后合 staging（`--squash --delete-branch`）。
- [ ] **Step 2**：staging 部署后，选 3 件没生成过的作品触发懒生成，看形式：空段、乱码、四段是否有合理的主动留空。不审事实。
- [ ] **Step 3**：报用户，等用户合 staging→main。**合 main 前**先确认 prod 没有在跑的批量生成任务：`docker exec gomuseum_prod_backend ps` 不可用，改查宿主机 `ps aux | grep -E "onboard|generate"` 和 `/opt/gomuseum` 下的 nohup 日志。
- [ ] **Step 4**：prod 部署完成后，取 Deploy run 的完成时间作为 **D**（UTC）。在 prod 容器跑快照脚本，输出拷到 `/opt/gomuseum/backups/grounding-baseline-<D>.json.gz`，核对计数：英文已发布段约 3839 段，具体以当天为准。
- [ ] **Step 5**：开一个 docs PR 更新台账 P1-9B 行，写明：
  - 第 1 步已上线，划线 D 和快照路径。
  - 旧产物的判定规则（快照 id + sha 一致；译文跟英文原文）。
  - 第 2 步（改闸）待定，以及它的触发条件。
