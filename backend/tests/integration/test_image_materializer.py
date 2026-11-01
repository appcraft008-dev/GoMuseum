"""物化器:下载→两档(thumb480/large1600 JPEG q82)→R2→署名→image_key(基础键)。
网络/存储全注入离线测。spec 2026-07-03 图像自存。"""

import io

import pytest
from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.artist import Artist
from app.models.museum import Museum
from app.models.museum_object import MuseumObject, ObjectImage
from app.services.enrichment.materializer import (
    image_base_key,
    materialize_images,
    materialize_object_images,
)
from app.services.object_importer import upsert_museum, upsert_object


def _jpeg_bytes(w=64, h=48):
    buf = io.BytesIO()
    Image.new("RGB", (w, h), (200, 30, 30)).save(buf, format="JPEG")
    return buf.getvalue()


class _Storage:
    def __init__(self):
        self.puts = {}

    def put(self, key, data, content_type):
        self.puts[key] = (data, content_type)

    def exists(self, key):
        return key in self.puts

    def public_url(self, key):
        return f"https://cdn.example/{key}"


@pytest.fixture()
def session():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(
        bind=engine,
        tables=[
            Artist.__table__,
            Museum.__table__,
            MuseumObject.__table__,
            ObjectImage.__table__,
        ],
    )
    s = sessionmaker(bind=engine)()
    m = upsert_museum(s, {"slug": "orsay", "name_en": "Orsay"})
    upsert_object(
        s,
        m.id,
        {
            "qid": "Q1",
            "title_en": "A",
            "popularity": 9,
            "images": ["https://img/a.jpg", "https://img/b.jpg"],
        },
    )
    upsert_object(
        s,
        m.id,
        {"qid": "Q2", "title_en": "B", "popularity": 5, "image": "https://img/c.jpg"},
    )
    s.commit()
    yield s


def test_image_base_key():
    assert image_base_key("Q1", 0) == "images/Q1/0"


def test_materialize_object_images_two_tiers_and_credit(session):
    st = _Storage()
    o = session.query(MuseumObject).filter_by(qid="Q1").one()
    out = materialize_object_images(
        session,
        o,
        fetch_bytes=lambda url: _jpeg_bytes(2000, 1500),
        storage=st,
        fetch_meta=lambda url: {"license": "CC BY-SA 4.0", "credit": "Photo: X"},
    )
    assert out["done"] == 2
    rows = (
        session.query(ObjectImage)
        .filter_by(object_id=o.id)
        .order_by(ObjectImage.sort)
        .all()
    )
    assert rows[0].image_key == "images/Q1/0"
    assert rows[1].image_key == "images/Q1/1"
    assert rows[0].license == "CC BY-SA 4.0" and rows[0].credit == "Photo: X"
    assert set(st.puts) == {
        "images/Q1/0_thumb.jpg",
        "images/Q1/0_large.jpg",
        "images/Q1/1_thumb.jpg",
        "images/Q1/1_large.jpg",
    }
    thumb = Image.open(io.BytesIO(st.puts["images/Q1/0_thumb.jpg"][0]))
    large = Image.open(io.BytesIO(st.puts["images/Q1/0_large.jpg"][0]))
    assert max(thumb.size) <= 480 and max(large.size) <= 1600
    assert st.puts["images/Q1/0_thumb.jpg"][1] == "image/jpeg"


def test_materialize_failure_leaves_key_empty(session):
    def boom(url):
        raise RuntimeError("network down")

    o = session.query(MuseumObject).filter_by(qid="Q1").one()
    out = materialize_object_images(
        session, o, fetch_bytes=boom, storage=_Storage(), fetch_meta=lambda u: {}
    )
    assert out["failed"] == 2 and out["done"] == 0
    assert all(
        r.image_key is None
        for r in session.query(ObjectImage).filter_by(object_id=o.id)
    )


def test_materialize_unreadable_image_skipped(session):
    o = session.query(MuseumObject).filter_by(qid="Q1").one()
    out = materialize_object_images(
        session,
        o,
        fetch_bytes=lambda url: b"<svg>not a bitmap</svg>",
        storage=_Storage(),
        fetch_meta=lambda u: {},
    )
    assert out["skipped"] == 2 and out["done"] == 0


def test_materialize_images_museum_wide_idempotent(session):
    st = _Storage()
    kw = dict(
        fetch_bytes=lambda url: _jpeg_bytes(),
        storage=st,
        fetch_meta=lambda url: {},
    )
    out = materialize_images(session, "orsay", **kw)
    assert out["done"] == 3  # Q1×2 + Q2×1
    out2 = materialize_images(session, "orsay", **kw)
    assert out2["done"] == 0  # 已有 key 跳过(幂等)


def test_materialize_images_unknown_museum(session):
    assert materialize_images(
        session, "nope", fetch_bytes=lambda u: b"", storage=_Storage()
    ) == {"error": "unknown museum"}


def test_default_fetch_uses_wikimedia_width_param(monkeypatch):
    # 名作原图可达 70MB+:Special:FilePath 加 ?width=1600 用 Wikimedia 服务端缩放,
    # 带宽降一个量级且根除超大跳过(库尔贝《画家的工作室》教训)
    import app.services.enrichment.materializer as mat

    seen = {}

    class _Resp:
        content = b"ok"

        def raise_for_status(self):
            pass

    def fake_get(url, **kw):
        seen["url"] = url
        return _Resp()

    monkeypatch.setattr("requests.get", fake_get)
    mat._default_fetch_bytes(
        "https://commons.wikimedia.org/wiki/Special:FilePath/Foo%20Bar.jpg"
    )
    assert seen["url"].endswith("?width=1600")
    # 非 Special:FilePath 的 URL 原样(不乱加参数)
    mat._default_fetch_bytes("https://example.com/x.jpg")
    assert seen["url"] == "https://example.com/x.jpg"


def test_materialize_skips_download_when_r2_already_has_files(session):
    # 共桶场景(staging 先物化过,prod 只需填 DB):两档文件已在 → 免下载/缩放/上传
    st = _Storage()
    st.puts["images/Q2/0_thumb.jpg"] = (b"x", "image/jpeg")
    st.puts["images/Q2/0_large.jpg"] = (b"x", "image/jpeg")

    def no_download(url):
        raise AssertionError("不应下载:桶里已有")

    o = session.query(MuseumObject).filter_by(qid="Q2").one()
    out = materialize_object_images(
        session,
        o,
        fetch_bytes=no_download,
        storage=st,
        fetch_meta=lambda u: {"license": "Public domain", "credit": "c"},
    )
    assert out["done"] == 1
    row = session.query(ObjectImage).filter_by(object_id=o.id).one()
    assert row.image_key == "images/Q2/0"
    assert row.license == "Public domain"  # meta 仍补(prod DB 自己的署名)


def test_fetch_meta_clips_overlong_credit(monkeypatch):
    # Commons 部分署名是多段落说明(英法双语+联系方式),超 varchar(255) 会
    # StringDataRightTruncation 崩掉整轮物化(2026-07-25 卢浮宫 1369/10159 处崩)
    from app.services.enrichment import materializer as mz

    long_credit = "Marie-Lan Nguyen " + "x" * 600

    class _R:
        def raise_for_status(self):
            pass

        def json(self):
            return {
                "query": {
                    "pages": {
                        "1": {
                            "imageinfo": [
                                {
                                    "extmetadata": {
                                        "Artist": {"value": long_credit},
                                        "LicenseShortName": {
                                            "value": "CC BY 2.5 " + "y" * 300
                                        },
                                    }
                                }
                            ]
                        }
                    }
                }
            }

    import requests

    monkeypatch.setattr(requests, "get", lambda *a, **k: _R())  # 函数内 import
    out = mz._default_fetch_meta("http://commons/x.jpg")
    assert len(out["credit"]) == 255  # 截到列宽
    assert len(out["license"]) == 128
    assert out["credit"].startswith("Marie-Lan Nguyen")  # 保留有效署名前缀


def test_photo_author_picks_who_took_the_photo():
    from app.services.enrichment.materializer import photo_author as pa

    assert pa("Photograph by Rama", "Own work", "Rama") == "Photograph by Rama"
    assert pa("", "Miniwark (2006)", "Miniwark") == "Miniwark (2006)"
    assert pa("", "Marie-Lan Nguyen (2010)", "Jastrow") == "Marie-Lan Nguyen (2010)"
    assert pa("", "Own work, Siren-Com, 11 November 2009", "Siren-Com") == "Siren-Com"
    assert pa("", "Own work", "Janmad") == "Janmad"
    # 认不准就不猜,留给人看
    assert pa("", "Own work", "Rotatebot") is None
    assert pa("", "Own work", "File Upload Bot (Magnus Manske)") is None
    assert pa("", "Own work", "Talbot") == "Talbot"  # 名字里带 bot 的真人
    assert pa("", "Web Gallery of Art: Image Info about artwork", "Diomede") is None
    assert pa("", "http://www.cagnes-tourisme.com/x", "Someone") is None
    assert pa("", "fr:Image:Coysevox1.jpg, picture taken by fr:U", "Rotatebot") is None
    assert pa("", "", "Someone") is None


def _meta(license_, artist="Claude Monet", author="Janmad"):
    return lambda u: {"license": license_, "credit": artist, "photo_author": author}


def test_cc_image_credits_photographer_when_artist_field_is_the_painter(session):
    m = session.query(Museum).first()
    o = upsert_object(session, m.id, {"qid": "Q77", "artist_en": "Claude Monet"})
    session.add(ObjectImage(object_id=o.id, source_url="http://x/a.jpg", sort=0))
    session.flush()
    materialize_object_images(
        session,
        o,
        fetch_bytes=lambda u: _jpeg_bytes(),
        storage=_Storage(),
        fetch_meta=_meta("CC BY-SA 4.0"),
    )
    assert session.query(ObjectImage).filter_by(object_id=o.id).one().credit == "Janmad"


def test_public_domain_and_real_photographer_credit_unchanged(session):
    m = session.query(Museum).first()
    a = upsert_object(session, m.id, {"qid": "Q78", "artist_en": "Claude Monet"})
    b = upsert_object(session, m.id, {"qid": "Q79", "artist_en": "Claude Monet"})
    for o in (a, b):
        session.add(ObjectImage(object_id=o.id, source_url="http://x/a.jpg", sort=0))
    session.flush()
    kw = dict(fetch_bytes=lambda u: _jpeg_bytes(), storage=_Storage())
    materialize_object_images(session, a, fetch_meta=_meta("Public domain"), **kw)
    materialize_object_images(
        session, b, fetch_meta=_meta("CC BY 3.0", artist="Mbzt"), **kw
    )
    row = lambda o: session.query(ObjectImage).filter_by(object_id=o.id).one()
    assert row(a).credit == "Claude Monet"  # 公有领域不要求署摄影师
    assert row(b).credit == "Mbzt"  # Artist 本来就是摄影师


def test_fetch_meta_returns_photo_author(monkeypatch):
    import requests

    from app.services.enrichment import materializer as mz

    class _R:
        def raise_for_status(self):
            pass

        def json(self):
            return {
                "query": {
                    "pages": {
                        "1": {
                            "imageinfo": [
                                {
                                    "user": "Janmad",
                                    "extmetadata": {
                                        "Artist": {"value": "Claude Monet"},
                                        "Credit": {"value": "<i>Own work</i>"},
                                        "LicenseShortName": {"value": "CC BY 3.0"},
                                    },
                                }
                            ]
                        }
                    }
                }
            }

    monkeypatch.setattr(requests, "get", lambda *a, **k: _R())
    assert mz._default_fetch_meta("http://c/x.jpg")["photo_author"] == "Janmad"


def test_backfill_plan_changes_only_painter_credits_on_cc_images(session):
    from scripts.backfill_photo_credit import plan

    m = session.query(Museum).first()
    base = "https://commons.wikimedia.org/wiki/Special:FilePath/"
    for qid, name, lic, credit in (
        ("Q81", "A.jpg", "CC BY 3.0", "Claude Monet"),  # 要改
        ("Q82", "B.jpg", "CC BY 3.0", "Mbzt"),  # 已是摄影师
        ("Q83", "C.jpg", "Public domain", "Claude Monet"),  # 不要求署名
        ("Q84", "D.jpg", "CC BY 3.0", "Claude Monet"),  # 认不准
    ):
        o = upsert_object(session, m.id, {"qid": qid, "artist_en": "Claude Monet"})
        session.add(
            ObjectImage(
                object_id=o.id,
                source_url=base + name,
                sort=0,
                license=lic,
                credit=credit,
            )
        )
    session.flush()

    class _R:
        def __init__(self, titles):
            self.titles = titles

        def raise_for_status(self):
            pass

        def json(self):
            return {
                "query": {
                    "pages": [
                        {
                            "title": t,
                            "imageinfo": [
                                {
                                    "user": "Rotatebot" if "D.jpg" in t else "Janmad",
                                    "extmetadata": {"Credit": {"value": "Own work"}},
                                }
                            ],
                        }
                        for t in self.titles
                    ]
                }
            }

    change, unsure = plan(
        session, get=lambda url, params, **k: _R(params["titles"].split("|"))
    )
    assert [(r.source_url[-5:], new) for r, new in change] == [("A.jpg", "Janmad")]
    assert [r.source_url[-5:] for r in unsure] == ["D.jpg"]
    assert all(r.credit == "Claude Monet" for r, _ in change)  # 计划不落库
