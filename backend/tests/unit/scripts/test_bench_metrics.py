"""检索(同qid多图取最大分)与指标(topk/阈值扫/间距/百分位),纯numpy。"""

import numpy as np

from scripts.recognition_bench.metrics import margins, pctl, rank, sweep, topk_hit


def _unit(v):
    v = np.asarray(v, dtype=np.float32)
    return v / np.linalg.norm(v)


def test_rank_aggregates_max_per_qid():
    vecs = np.stack([_unit([1, 0]), _unit([0.9, 0.1]), _unit([0, 1])])
    ranked = rank(_unit([1, 0]), vecs, ["A", "A", "B"])
    assert ranked[0][0] == "A" and ranked[1][0] == "B"
    assert abs(ranked[0][1] - 1.0) < 1e-6  # A 取两张图中的最大分
    assert len(ranked) == 2  # 去重


def test_topk_hit():
    ranked = [("A", 0.9), ("B", 0.8)]
    assert topk_hit(ranked, "B", 3) and not topk_hit(ranked, "B", 1)


def test_sweep_rates():
    rows = sweep(in_top1=[0.9, 0.9, 0.6], ooc_top1=[0.55, 0.85])
    row_08 = next(r for r in rows if abs(r["threshold"] - 0.80) < 1e-9)
    assert abs(row_08["in_accept_rate"] - 2 / 3) < 1e-9
    assert abs(row_08["ooc_accept_rate"] - 1 / 2) < 1e-9


def test_margins_and_pctl():
    assert margins([[("A", 0.9), ("B", 0.7)], [("C", 0.5)]]) == [
        0.9 - 0.7,
        0.5,
    ]
    assert pctl([1.0, 2.0, 3.0, 4.0], 50) == 2.5
