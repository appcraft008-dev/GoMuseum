"""评测:测试集 → 分桶指标 + 阈值扫 + 判定(spec ⑤:非名作桶必须单独达标) + markdown 报告。"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np

from scripts.recognition_bench.metrics import margins, pctl, rank, sweep, topk_hit

DATA = Path(__file__).parent / "data"
TOP1_LINE, TOP3_LINE, OOC_LINE = 0.85, 0.95, 0.05


def _bucket_stats(rows):
    n = len(rows)
    return {
        "n": n,
        "top1": sum(r["hit1"] for r in rows) / n if n else None,
        "top3": sum(r["hit3"] for r in rows) / n if n else None,
    }


def evaluate(index, queries):
    vecs, qids = index
    in_rows, ooc_top1, ranked_all, lat = [], [], [], []
    for q in queries:
        ranked = rank(q["vec"], vecs, qids)
        lat.append(q["ms"])
        if q["true_qid"] is None:
            ooc_top1.append(ranked[0][1] if ranked else 0.0)
            continue
        ranked_all.append(ranked)
        in_rows.append(
            {
                **q,
                "top1_score": ranked[0][1] if ranked else 0.0,
                "hit1": topk_hit(ranked, q["true_qid"], 1),
                "hit3": topk_hit(ranked, q["true_qid"], 3),
            }
        )
    buckets = {"ALL": _bucket_stats(in_rows)}
    for key in ("source", "fame", "dim"):
        for val in sorted({r[key] for r in in_rows if r[key]}):
            buckets[f"{key}={val}"] = _bucket_stats(
                [r for r in in_rows if r[key] == val]
            )
    for r in in_rows:  # 组合桶(报告矩阵用)
        combo = f"{r['source']}|{r['fame']}|{r['dim']}"
        buckets.setdefault(
            combo,
            _bucket_stats(
                [x for x in in_rows if f"{x['source']}|{x['fame']}|{x['dim']}" == combo]
            ),
        )
    correct_top1 = [r["top1_score"] for r in in_rows if r["hit1"]]
    sw = sweep(correct_top1, ooc_top1)
    chosen = next(
        (row["threshold"] for row in sw if row["ooc_accept_rate"] <= OOC_LINE), None
    )
    mg = margins(ranked_all)
    nf = buckets.get("fame=nonfamous") or {"top1": None, "top3": None}
    verdict = {
        "top1_ok": (buckets["ALL"]["top1"] or 0) >= TOP1_LINE,
        "top3_ok": (buckets["ALL"]["top3"] or 0) >= TOP3_LINE,
        "ooc_ok": chosen is not None,
        "nonfamous_ok": (nf["top1"] or 0) >= TOP1_LINE
        and (nf["top3"] or 0) >= TOP3_LINE,
        "chosen_threshold": chosen,
    }
    verdict["pass"] = all(
        verdict[k] for k in ("top1_ok", "top3_ok", "ooc_ok", "nonfamous_ok")
    )
    return {
        "buckets": buckets,
        "sweep": sw,
        "margin_p50": pctl(mg, 50) if mg else None,
        "margin_p10": pctl(mg, 10) if mg else None,
        "latency_p50_ms": pctl(lat, 50) if lat else None,
        "latency_p95_ms": pctl(lat, 95) if lat else None,
        "verdict": verdict,
    }


def render_report(results: dict, preset: str) -> str:
    v = results["verdict"]
    lines = [
        f"# recognition bench report — {preset}",
        "",
        f"**verdict: {'PASS ✅' if v['pass'] else 'FAIL ❌'}** "
        f"(top1_ok={v['top1_ok']} top3_ok={v['top3_ok']} ooc_ok={v['ooc_ok']} "
        f"nonfamous_ok={v['nonfamous_ok']} chosen_threshold={v['chosen_threshold']})",
        "",
        f"margin p50={results['margin_p50']} p10={results['margin_p10']} | "
        f"latency p50={results['latency_p50_ms']}ms p95={results['latency_p95_ms']}ms",
        "",
        "| bucket | n | top1 | top3 |",
        "|---|---|---|---|",
    ]
    for k, b in results["buckets"].items():
        t1 = f"{b['top1']:.3f}" if b["top1"] is not None else "-"
        t3 = f"{b['top3']:.3f}" if b["top3"] is not None else "-"
        lines.append(f"| {k} | {b['n']} | {t1} | {t3} |")
    lines += ["", "| threshold | in_accept | ooc_accept |", "|---|---|---|"]
    for row in results["sweep"]:
        lines.append(
            f"| {row['threshold']:.2f} | {row['in_accept_rate']:.3f} "
            f"| {row['ooc_accept_rate']:.3f} |"
        )
    return "\n".join(lines) + "\n"


def main():
    preset = sys.argv[1]
    from PIL import Image

    from scripts.recognition_bench.build_index import load_index
    from scripts.recognition_bench.embed import OnnxEmbedder

    onnx = {"dinov2": "dinov2_vits14.onnx", "clip": "clip_vitb32.onnx"}[preset]
    embedder = OnnxEmbedder(str(DATA / onnx), preset)
    vecs, qids, model = load_index(DATA / f"index_{preset}.npz")
    assert model == preset, f"index model {model} != {preset}"
    rows = json.loads((DATA / "testset.json").read_text())
    queries = []
    for r in rows:
        if r["path"].endswith("_ref.jpg"):
            continue  # 官方图本尊不当查询
        img = Image.open(r["path"])
        t0 = time.perf_counter()
        vec = embedder.embed(img)
        queries.append({**r, "vec": vec, "ms": (time.perf_counter() - t0) * 1000})
    results = evaluate((vecs, qids), queries)
    report = render_report(results, preset)
    (DATA / f"report_{preset}.md").write_text(report)
    print(report)


if __name__ == "__main__":
    main()
