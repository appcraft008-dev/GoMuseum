"""评测:合成向量端到端——分桶指标/阈值裁决/非名作单独达标逻辑。"""

import numpy as np

from scripts.recognition_bench.run_eval import evaluate


def _u(v):
    v = np.asarray(v, dtype=np.float32)
    return v / np.linalg.norm(v)


def test_evaluate_verdict_pass():
    index = (np.stack([_u([1, 0]), _u([0, 1])]), ["Q1", "Q2"])
    queries = [
        {
            "vec": _u([0.99, 0.01]),
            "true_qid": "Q1",
            "source": "real",
            "fame": "famous",
            "dim": "2d",
            "ms": 100.0,
        },
        {
            "vec": _u([0.02, 0.98]),
            "true_qid": "Q2",
            "source": "synthetic",
            "fame": "nonfamous",
            "dim": "3d",
            "ms": 120.0,
        },
        {
            "vec": _u([0.6, 0.6]),
            "true_qid": None,
            "source": "ooc",
            "fame": None,
            "dim": None,
            "ms": 90.0,
        },  # 库外:top1=cos45°≈0.707
    ]
    r = evaluate(index, queries)
    assert r["buckets"]["ALL"]["top1"] == 1.0
    assert r["buckets"]["fame=nonfamous"]["top1"] == 1.0
    assert r["verdict"]["nonfamous_ok"] is True
    assert r["latency_p50_ms"] == 100.0
    # 库外 top1≈0.707 → 压住误接受的最低阈值档 = 0.75;库内分都>0.97 → pass
    assert r["verdict"]["pass"] is True and r["verdict"]["chosen_threshold"] == 0.75


def test_evaluate_fails_when_nonfamous_bucket_bad():
    index = (np.stack([_u([1, 0]), _u([0, 1])]), ["Q1", "Q2"])
    queries = [
        {
            "vec": _u([0.99, 0.01]),
            "true_qid": "Q1",
            "source": "real",
            "fame": "famous",
            "dim": "2d",
            "ms": 100.0,
        },
        {
            "vec": _u([0.99, 0.01]),
            "true_qid": "Q2",
            "source": "synthetic",
            "fame": "nonfamous",
            "dim": "2d",
            "ms": 100.0,
        },  # 非名作认错
    ]
    r = evaluate(index, queries)
    assert r["verdict"]["nonfamous_ok"] is False and r["verdict"]["pass"] is False
