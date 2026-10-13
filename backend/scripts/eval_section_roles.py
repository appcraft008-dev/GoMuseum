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
        return parse_audit(
            (_parse_json(raw) or {}).get("items") or [], sentences, material
        )

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
            draft = enricher.generate_canonical(
                job["obj"], job["sections"], guide=guide
            )
        for code in job["sections"]:
            body = (draft or {}).get(code)
            if not body:
                recs.append(
                    dict(
                        qid=job["qid"],
                        rep=rep,
                        arm=arm,
                        section=code,
                        status="empty",
                        kept=0,
                        unsupported=[],
                    )
                )
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
            r["section"],
            {"published": 0, "needs_review": 0, "empty": 0, "unsupported": 0},
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
            .join(
                ObjectContentSection, ObjectContentSection.object_id == MuseumObject.id
            )
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
    from app.services.enrichment.content_enricher import (
        ContentEnricher,
        default_complete,
    )
    from app.services.enrichment.quality import QualityGate

    ap = argparse.ArgumentParser()
    ap.add_argument("--new-config", required=True)
    ap.add_argument("--n", type=int, default=30)
    ap.add_argument("--reps", type=int, default=3)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    ch = "eval_section_roles"
    enricher = ContentEnricher(
        lambda s, u, model="gpt-4o-mini": default_complete(s, u, model, channel=ch)
    )
    gate = QualityGate(
        lambda s, u, model="gpt-4o-mini": default_complete(
            s, u, model, channel=ch, temperature=0
        )
    )
    auditor = make_auditor(
        lambda s, u: default_complete(s, u, "gpt-4o", channel=ch, temperature=0)
    )
    arms = {"old": OLD_ROLES, "new": _load_roles(a.new_config)}
    jobs = _jobs(a.n)

    # ponytail: 整体串行——两组切换写作要求改的是模块级 dict,并发会串组。30×3 件约 1 小时;要快再按组分进程。
    records = []
    for rep in range(a.reps):
        for j in jobs:
            try:
                records += run_pair(j, rep, enricher, gate, auditor, arms)
            except Exception as e:  # 单件失败不中断整批,记下来
                records.append(
                    dict(
                        qid=j["qid"],
                        rep=rep,
                        arm="error",
                        section="-",
                        status="error",
                        kept=0,
                        unsupported=[],
                        error=repr(e),
                    )
                )
    summary = summarize([r for r in records if r["arm"] != "error"])
    with open(a.out, "w") as f:
        json.dump(
            {"summary": summary, "records": records}, f, ensure_ascii=False, indent=1
        )
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    print("errors", sum(r["arm"] == "error" for r in records))
    return 0


if __name__ == "__main__":
    sys.exit(main())
