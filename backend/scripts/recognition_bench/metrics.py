"""检索与指标:余弦近邻(同qid多参考图取最大分)+Top-k/阈值扫/Top1-Top2间距/百分位。
纯 numpy,2k 量级精确搜索毫秒级(spec:不上 FAISS/pgvector)。"""

from __future__ import annotations

import numpy as np


def rank(q: np.ndarray, vecs: np.ndarray, qids: list[str]) -> list[tuple[str, float]]:
    scores = vecs @ q  # 均已单位化,点积即余弦
    best: dict[str, float] = {}
    for qid, s in zip(qids, scores):
        if s > best.get(qid, -2.0):
            best[qid] = float(s)
    return sorted(best.items(), key=lambda kv: -kv[1])


def topk_hit(ranked: list[tuple[str, float]], true_qid: str, k: int) -> bool:
    return any(qid == true_qid for qid, _ in ranked[:k])


def sweep(in_top1: list[float], ooc_top1: list[float]) -> list[dict]:
    rows = []
    for t in [round(0.50 + 0.05 * i, 2) for i in range(10)]:
        rows.append(
            {
                "threshold": t,
                "in_accept_rate": (
                    sum(s >= t for s in in_top1) / len(in_top1) if in_top1 else 0.0
                ),
                "ooc_accept_rate": (
                    sum(s >= t for s in ooc_top1) / len(ooc_top1) if ooc_top1 else 0.0
                ),
            }
        )
    return rows


def margins(ranked_list: list[list[tuple[str, float]]]) -> list[float]:
    out = []
    for ranked in ranked_list:
        if len(ranked) >= 2:
            out.append(ranked[0][1] - ranked[1][1])
        elif ranked:
            out.append(ranked[0][1])
    return out


def pctl(values: list[float], p: float) -> float:
    return float(np.percentile(np.asarray(values, dtype=np.float64), p))
