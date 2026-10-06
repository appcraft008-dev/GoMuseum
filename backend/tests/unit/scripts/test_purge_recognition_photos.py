# tests/unit/scripts/test_purge_recognition_photos.py
"""S5 照片生命周期:超过 90 天或 status=done → 删对象 + image_key 置空;行(元数据)保留。"""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.recognition_photo_feedback import RecognitionPhotoFeedback as R
from scripts.purge_recognition_photos import purge


class _Store:
    def __init__(self, keys):
        self.objs = set(keys)
        self.deleted = []

    def delete(self, key):
        self.deleted.append(key)
        self.objs.discard(key)


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    R.__table__.create(bind=engine)
    return sessionmaker(bind=engine)()


NOW = datetime(2026, 10, 6, tzinfo=timezone.utc)


def _row(db, key, age_days, status="new"):
    r = R(
        phash="p",
        trigger="found",
        image_key=key,
        status=status,
        created_at=NOW - timedelta(days=age_days),
    )
    db.add(r)
    db.commit()
    return r


def test_purges_old_and_done_keeps_fresh(db):
    old = _row(db, "k-old", 91)
    done = _row(db, "k-done", 3, status="done")
    fresh = _row(db, "k-fresh", 3)
    store = _Store({"k-old", "k-done", "k-fresh"})
    assert purge(db, store, now=NOW) == 2
    db.expire_all()
    assert old.image_key is None and done.image_key is None
    assert fresh.image_key == "k-fresh"
    assert store.objs == {"k-fresh"}
    assert db.query(R).count() == 3  # 元数据保留


def test_purge_skips_already_purged(db):
    _row(db, None, 200)
    store = _Store(set())
    assert purge(db, store, now=NOW) == 0
    assert store.deleted == []


def test_purge_sweeps_orphan_objects_older_than_retention(db):
    """桶写成功、库写失败、补偿删除也失败 → 桶里有对象但没有行。
    「最长 90 天」不能有例外:超过保存期且无行引用的对象也要删。"""
    _row(db, "k-ref", 100)  # 有行引用,走正常路径

    class _Listing(_Store):
        def list_keys(self, prefix):
            assert prefix == "recognition-feedback/"
            yield "recognition-feedback/orphan-old.jpg", 1, NOW - timedelta(days=95)
            yield "recognition-feedback/orphan-new.jpg", 1, NOW - timedelta(days=2)

    store = _Listing(
        {
            "k-ref",
            "recognition-feedback/orphan-old.jpg",
            "recognition-feedback/orphan-new.jpg",
        }
    )
    purge(db, store, now=NOW)
    assert "recognition-feedback/orphan-old.jpg" in store.deleted
    assert "recognition-feedback/orphan-new.jpg" not in store.deleted


def test_purge_continues_after_one_delete_fails(db):
    a = _row(db, "k-a", 100)
    b = _row(db, "k-b", 100)

    class _Flaky(_Store):
        def delete(self, key):
            if key == "k-a":
                raise ConnectionError("r2")
            super().delete(key)

    store = _Flaky({"k-a", "k-b"})
    assert purge(db, store, now=NOW) == 1
    db.expire_all()
    assert a.image_key == "k-a"  # 删失败的留着,下次再删
    assert b.image_key is None


def test_purge_survives_listing_network_error(db):
    """孤儿扫描时 R2 抖动(boto3 抛 ClientError 等):按行清理照常提交,脚本不崩。"""
    old = _row(db, "k-old", 100)

    class _ListBoom(_Store):
        def list_keys(self, prefix):
            raise ConnectionError("r2 throttled")
            yield  # pragma: no cover  (generator)

    store = _ListBoom({"k-old"})
    assert purge(db, store, now=NOW) == 1
    db.expire_all()
    assert old.image_key is None
