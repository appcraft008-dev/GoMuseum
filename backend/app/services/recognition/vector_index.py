"""向量索引(识别的查询侧):全量 embedding → numpy 矩阵,余弦 Top-k。

生成侧存的向量已单位化,点积即余弦(不再归一化)。
纯 numpy 精确检索(spec:不上 FAISS/pgvector),2k 量级毫秒级。
进程内 TTL 缓存:全库单矩阵一次加载,馆过滤用布尔掩码切片。
过期不阻塞(同搜索索引):本次用旧矩阵、后台重载;进程内首次靠启动预热。
"""

from __future__ import annotations

import logging
import threading
import time

import numpy as np
from sqlalchemy import func

from app.models.museum_object import MuseumObject
from app.models.object_embedding import ObjectEmbedding
from app.services.recognition.embedder import MODEL_NAME

_INDEX_TTL = 600  # 秒:到期只查指纹,变了才重载
_FULL_RELOAD_S = 6 * 3600  # 兜底:最多 6h 也全量重载一次
_cache: tuple | None = None  # (ts, mat, qids, museum_ids, 指纹, 全量加载时刻)
_refresh_lock = threading.Lock()
_refreshing = False
logger = logging.getLogger(__name__)


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


def _fingerprint(db) -> tuple:
    """向量只增删不原地改 → (行数, 最近 created_at);矩阵还带作品 qid/馆 → 只摘要这两列
    (懒生成写描述/状态不该触发重载,见 index_digest)。"""
    from app.services.index_digest import column_digest

    return (
        tuple(db.query(func.count(), func.max(ObjectEmbedding.created_at)).one()),
        column_digest(db, MuseumObject.id, MuseumObject.qid, MuseumObject.museum_id),
    )


def _refresh(db) -> None:
    """到期刷新:指纹没变且全量加载不满 6h → 只续期(prod 全量重载 CPU 1.55s,和请求抢 GIL)。"""
    global _cache
    fp = _fingerprint(db)
    now = time.time()
    c = _cache
    if c and len(c) > 5 and c[4] == fp and now - c[5] < _FULL_RELOAD_S:
        _cache = (now, *c[1:])
        return
    _cache = (time.time(), *_load(db), fp, now)
    logger.info("vector index reloaded: %d in %.1fs", len(_cache[2]), time.time() - now)


def _refresh_async() -> None:
    """后台重载(自带 session)。失败留旧矩阵,下次过期再试。"""
    global _refreshing
    with _refresh_lock:
        if _refreshing:
            return
        _refreshing = True

    def _run():
        global _refreshing
        try:
            from app.core.database import SessionLocal

            db2 = SessionLocal()
            try:
                _refresh(db2)
            finally:
                db2.close()
        except Exception:
            logger.exception("vector index refresh failed, keeping stale index")
        finally:
            _refreshing = False

    threading.Thread(target=_run, daemon=True, name="vector-index-refresh").start()


def warm_vector_index() -> None:
    """启动预热:prod 4 万条向量全量加载 ~2.3s,别让进程内第一个识别用户等。"""
    _refresh_async()


def _get(db) -> tuple:
    """过期时返回旧矩阵并触发后台重载(prod 闲置 >10 分钟后首个识别 vq 曾 53/53 次 >1s)。
    只有缓存为空(冷启/invalidate)才同步加载。"""
    global _cache
    if _cache:
        if time.time() - _cache[0] >= _INDEX_TTL:
            _refresh_async()
        return _cache[1], _cache[2], _cache[3]
    mat, qids, museum_ids = _load(db)
    _cache = (time.time(), mat, qids, museum_ids)  # 空表也缓存,TTL 到期再刷
    return mat, qids, museum_ids


def query_index(
    db, vec: np.ndarray, museum_id=None, visible=None
) -> list[tuple[str, float]]:
    """查询向量 → [(qid, score)] 同 qid 取最大分、降序。空(或过滤后为空)→ []。
    visible:可见馆 id 集合(None=不限),查询时过滤 —— 索引本身不带可见性。"""
    mat, qids, museum_ids = _get(db)
    if len(qids) == 0:
        return []
    if museum_id is not None or visible is not None:
        mask = np.array(
            [
                (museum_id is None or mid == museum_id)
                and (visible is None or mid in visible)
                for mid in museum_ids
            ]
        )
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
