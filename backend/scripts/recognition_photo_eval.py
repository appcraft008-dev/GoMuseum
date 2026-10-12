"""识别评测(只读):带标答案的照片 → 各裁块门槛下的结局对比。

照片来源:
- 照片反馈:按 phash 查 `recognition_photo_feedbacks`(标签 `recognition_photo_eval_labels.tsv`,
  答案 `-` = 库里认不出的照片,应交 AI;多个可接受答案用 `|` 分隔)。未标注但 found/corrected
  带 answer_qid 的行自动当正样本。照片 90 天或处理完即删(S5),删了的行自动跳过。
- `--extra manifest.json`:[{path, true_qid}](true_qid 为 null = 库外图),如 recognition_bench 测试集
  的 real 组(他人实拍)。⚠️ 该测试集的 ooc 组 52 件 10-12 核实已全部入卢浮库,不能再当库外图。

向量三档(全帧/画框/金字塔)每张各算一次,门槛策略在内存里重放,与 service._compute 同逻辑。
不写识别事件、不写缓存、不调 GPT、不删照片。

用法:docker exec gomuseum_prod_backend nice -n 19 python scripts/recognition_photo_eval.py
"""

import argparse
import json
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

LABELS = Path(__file__).with_name("recognition_photo_eval_labels.tsv")


def _merge(ranked, lists):
    agg = dict(ranked)
    for lst in lists:
        for q, s in lst:
            if s > agg.get(q, -2.0):
                agg[q] = s
    return sorted(agg.items(), key=lambda kv: -kv[1])


def replay(full, canvas, crops, crops_below, high):
    """重放 service._compute 的向量门槛。canvas/crops = 每个子图的 ranked 列表,None = 该档无产出。
    ponytail: 与 _compute 的两行门槛手抄同步;改那边的门槛时这里同改。"""
    ranked = full
    if canvas is not None and (not ranked or ranked[0][1] < high):
        ranked = _merge(ranked, canvas)
    if crops is not None and (not ranked or ranked[0][1] < crops_below):
        ranked = _merge(ranked, crops)
    return ranked


def verdict(ranked, answers, low, high, margin):
    """同 service._vector_out 的定档,再按答案判对错。answers 空 = 库里认不出的照片。"""
    if not ranked or ranked[0][1] < low:
        return "交AI(对)" if not answers else "交AI"
    close = len(ranked) > 1 and ranked[0][1] - ranked[1][1] < margin
    if ranked[0][1] >= high and not close:
        return "直判对" if ranked[0][0] in answers else "直判错"
    shown = [q for q, s in ranked[:3] if s >= low]
    if not answers:
        return "候选噪音"
    hit = next((i for i, q in enumerate(shown) if q in answers), None)
    return "候选全错" if hit is None else f"候选含答案(第{hit + 1})"


def _load_labels():
    out = {}
    for line in LABELS.read_text().splitlines():
        phash, ans, note = (line.split("\t") + [""])[:3]
        out[phash] = (set() if ans == "-" else set(ans.split("|")), note)
    return out


def _samples(db, extra):
    """→ [(名, image_bytes, 答案集合, museum_id)]"""
    from app.models.museum import Museum
    from app.models.recognition_photo_feedback import RecognitionPhotoFeedback as R
    from app.services.storage.photo_feedback import get_photo_feedback_storage

    labels = _load_labels()
    mid = {m.slug: m.id for m in db.query(Museum).all()}
    store = get_photo_feedback_storage()
    seen, out, gone = set(), [], 0
    rows = db.query(R).filter(R.image_key.isnot(None)).order_by(R.created_at.desc())
    for r in rows:  # 同一张照片取最新一行
        if r.phash in seen:
            continue
        seen.add(r.phash)
        if r.phash in labels:
            ans, note = labels[r.phash]
        elif r.trigger in ("found", "corrected") and r.answer_qid:
            ans, note = {r.answer_qid}, "反馈自带答案"
        else:
            continue
        try:
            b = store.get(r.image_key)
        except Exception:
            gone += 1
            continue
        out.append((f"{r.phash} {note[:40]}", b, ans, mid.get(r.museum_slug)))
    missing = len(set(labels) - seen)
    print(f"照片反馈 {len(out)} 张;标签里已删图/找不到 {missing + gone} 张")
    for item in json.loads(Path(extra).read_text()) if extra else []:
        q = item.get("true_qid")
        name = f"extra {Path(item['path']).parent.name}/{Path(item['path']).name}"
        out.append((name, Path(item["path"]).read_bytes(), {q} if q else set(), None))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--extra", help="额外图集 manifest.json:[{path, true_qid}]")
    args = ap.parse_args()

    from app.core.config import settings
    from app.core.database import SessionLocal
    from app.services.recognition.service import (
        _default_embed,
        _default_embed_canvas,
        _default_embed_crops,
    )
    from app.services.recognition.vector_index import query_index

    th = dict(
        low=settings.RECOG_LOW, high=settings.RECOG_HIGH, margin=settings.RECOG_MARGIN
    )
    policies = {"现在(<LOW 才裁块)": th["low"], "改后(<HIGH 就裁块)": th["high"]}
    print("门槛", th)
    db = SessionLocal()
    try:
        samples = _samples(db, args.extra)
        res = {p: Counter() for p in policies}
        by_group = {p: {} for p in policies}
        changed, crops_ms = [], []
        for name, b, ans, museum_id in samples:

            def q(v):
                return query_index(db, v, museum_id)

            v = _default_embed(b)
            if v is None:
                continue
            full = q(v)
            cv = _default_embed_canvas(b)
            canvas = [q(x) for x in cv] if cv is not None else None
            t = time.perf_counter()
            kv = _default_embed_crops(b)
            crops = [q(x) for x in kv] if kv is not None else None
            crops_ms.append((time.perf_counter() - t) * 1000)
            group = "库里有" if ans else "库里认不出"
            vs = {}
            for p, below in policies.items():
                vs[p] = verdict(
                    replay(full, canvas, crops, below, th["high"]), ans, **th
                )
                res[p][vs[p]] += 1
                by_group[p].setdefault(group, Counter())[vs[p]] += 1
            if len(set(vs.values())) > 1:
                changed.append((name, " → ".join(vs.values())))
    finally:
        db.close()

    for p in policies:
        print(f"\n## {p}")
        for g, c in by_group[p].items():
            n = sum(c.values())
            print(f"  {g} {n} 张:" + ",".join(f"{k} {v}" for k, v in c.most_common()))
    print(f"\n## 两种策略结局不同的 {len(changed)} 张")
    for name, d in changed:
        print(f"  {name}  {d}")
    if crops_ms:
        crops_ms.sort()
        print(
            f"\n裁块耗时 p50 {crops_ms[len(crops_ms) // 2]:.0f}ms"
            f" p90 {crops_ms[int(len(crops_ms) * 0.9)]:.0f}ms(评测机负载下,仅供参考)"
        )


if __name__ == "__main__":
    main()
