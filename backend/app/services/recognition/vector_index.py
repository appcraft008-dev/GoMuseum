"""向量索引(识别的查询侧):全量 embedding → numpy 矩阵,余弦 Top-k。

生成侧存的向量已单位化,点积即余弦(不再归一化)。
纯 numpy 精确检索(spec:不上 FAISS/pgvector),2k 量级毫秒级。
进程内 TTL 缓存:全库单矩阵一次加载,馆过滤用布尔掩码切片。
"""

from __future__ import annotations

import time

import numpy as np

from app.models.museum_object import MuseumObject
from app.models.object_embedding import ObjectEmbedding
from app.services.recognition.embedder import MODEL_NAME

_INDEX_TTL = 600  # 秒
_cache: tuple | None = None  # (ts, mat, qids, museum_ids)


def invalidate() -> None:
    """清空缓存(测试 / embed 钩子写入新向量后调用)。"""
    global _cache
    _cache = None


def _load(db) -> tuple:
    """全量加载 → (mat[N,D] float32, qids[N], museum_ids[N])。qid 为空的展品跳过。"""
    rows = (
        db.query(ObjectEmbedding.vec, MuseumObject.qid, MuseumObject.museum_id)
        .join(MuseumObject, ObjectEmbedding.object_id == MuseumObject.id)
        .filter(ObjectEmbedding.model == MODEL_NAME, MuseumObject.qid.isnot(None))
        .all()
    )
    if not rows:
        return np.empty((0, 0), dtype=np.float32), [], []
    mat = np.vstack([np.frombuffer(r.vec, dtype=np.float32) for r in rows])
    qids = [r.qid for r in rows]
    museum_ids = [r.museum_id for r in rows]
    return mat, qids, museum_ids


def _get(db) -> tuple:
    global _cache
    if _cache and time.time() - _cache[0] < _INDEX_TTL:
        return _cache[1], _cache[2], _cache[3]
    mat, qids, museum_ids = _load(db)
    _cache = (time.time(), mat, qids, museum_ids)  # 空表也缓存,TTL 到期再刷
    return mat, qids, museum_ids


def query_index(db, vec: np.ndarray, museum_id=None) -> list[tuple[str, float]]:
    """查询向量 → [(qid, score)] 同 qid 取最大分、降序。空(或过滤后为空)→ []。"""
    mat, qids, museum_ids = _get(db)
    if len(qids) == 0:
        return []
    if museum_id is not None:
        mask = np.array([mid == museum_id for mid in museum_ids])
        if not mask.any():
            return []
        mat = mat[mask]
        qids = [q for q, keep in zip(qids, mask) if keep]

    scores = mat @ np.asarray(vec, dtype=np.float32)
    best: dict[str, float] = {}
    for qid, s in zip(qids, scores):
        if s > best.get(qid, -2.0):
            best[qid] = float(s)
    return sorted(best.items(), key=lambda kv: -kv[1])
