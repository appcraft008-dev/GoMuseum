"""反馈报告的核心是**按人去重**,不是数行数。

这是 spec 里「已知错法 1」的钉子:双击提交、或"请求已到达但客户端超时、用户点了
重试",都会造重复行。而这份报告的全部用处是「第三个人报同一件事就浮上来」——
数行数会让**一个人点三下**看起来和**三个人各报一次**一样急。
"""

import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from app.models.feedback import Feedback  # noqa: E402
from app.models.museum_object import MuseumObject  # noqa: E402

from feedback_report import build  # noqa: E402  isort:skip


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Feedback.__table__.create(bind=engine)
    MuseumObject.__table__.create(bind=engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


def add(db, device, **kw):
    db.add(
        Feedback(
            scope=kw.pop("scope", "object"),
            kind=kw.pop("kind", "content_wrong"),
            qid=kw.pop("qid", "Q1"),
            language=kw.pop("language", "zh-hant"),
            device_id=device,
            **kw,
        )
    )
    db.commit()


def test_同一个人报三次只算一个人(db):
    for _ in range(3):
        add(db, "dev-A")

    row = build(db, days=30)["objects"][0]
    assert row["people"] == 1, "数了行数 → 一个人点三下会伪装成三个人在报"
    assert row["rows"] == 3  # 重复行仍然看得见，便于发现客户端重试问题


def test_三个人各报一次算三个人(db):
    """对照组:只测上面那条的话,一个恒返回 1 的实现也全绿。"""
    for dev in ("dev-A", "dev-B", "dev-C"):
        add(db, dev)

    row = build(db, days=30)["objects"][0]
    assert row["people"] == 3
    assert row["rows"] == 3


def test_按人数排序而不是按行数(db):
    """🔴 关键:一个人刷 5 次的件,不该排在三个人各报一次的件前面。"""
    for _ in range(5):
        add(db, "dev-spam", qid="Q_NOISY")
    for dev in ("dev-A", "dev-B", "dev-C"):
        add(db, dev, qid="Q_REAL")

    objects = build(db, days=30)["objects"]
    assert objects[0]["qid"] == "Q_REAL", "按行数排 → 刷屏的件挤掉了真问题"
    assert objects[0]["people"] == 3
    assert objects[1]["qid"] == "Q_NOISY"
    assert objects[1]["people"] == 1


def test_不同语种分开统计(db):
    """10 语是 10 份独立内容,zh-hant 的问题和 en 的不是一回事。"""
    add(db, "dev-A", language="zh-hant")
    add(db, "dev-B", language="en")

    objects = build(db, days=30)["objects"]
    assert len(objects) == 2
    assert {o["language"] for o in objects} == {"zh-hant", "en"}


def test_app级与藏品级分开(db):
    add(db, "dev-A")
    add(db, "dev-B", scope="app", kind="app_crash", qid=None, language=None)

    r = build(db, days=30)
    assert len(r["objects"]) == 1
    assert len(r["app"]) == 1
    assert r["app"][0]["kind"] == "app_crash"
