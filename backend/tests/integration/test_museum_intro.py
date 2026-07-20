"""馆介绍生成:按语言幂等补缺/gate失败不落/无材料skip;封面:否决件跳过选下一件。"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.museum import Museum
from app.models.museum_object import MuseumObject, ObjectImage
from app.services.enrichment.museum_intro import generate_museum_intro, select_cover
from app.services.enrichment.quality import SectionQuality
from app.services.object_importer import upsert_museum, upsert_object


@pytest.fixture()
def session():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(
        bind=engine,
        tables=[Museum.__table__, MuseumObject.__table__, ObjectImage.__table__],
    )
    s = sessionmaker(bind=engine)()
    upsert_museum(s, {"slug": "orsay", "name_en": "Orsay", "qid": "Q23402"})
    s.commit()
    yield s


class _Gate:
    def __init__(self, ok=True):
        self.ok = ok

    def check_section(self, material, facts, body):
        return SectionQuality(
            body=body if self.ok else None,
            status="published" if self.ok else "needs_review",
            grounding_ratio=1.0,
            conflicts=[],
            score=1.0,
        )


class _Tr:
    def translate_section(self, body, lang, **kw):
        return f"{lang}:{body}"


def _mat(qid, **kw):
    return {"extract_en": "Housed in a 1900 railway station..."}


def test_generates_en_and_fills_langs(session):
    out = generate_museum_intro(
        session,
        "orsay",
        complete=lambda s, u: "A grand museum intro.",
        gate=_Gate(),
        translator=_Tr(),
        langs=["en", "zh", "ja"],
        fetch_material=_mat,
    )
    m = session.query(Museum).one()
    assert m.description_i18n["en"] == "A grand museum intro."
    assert m.description_i18n["zh"].startswith("zh:")
    assert out["generated"] is True and set(out["translated"]) == {"zh", "ja"}


def test_idempotent_fills_missing_language_only(session):
    m = session.query(Museum).one()
    m.description_i18n = {"en": "Existing.", "zh": "已有。"}
    session.commit()
    called = {"gen": 0}

    def complete(s, u):
        called["gen"] += 1
        return "regen"

    out = generate_museum_intro(
        session,
        "orsay",
        complete=complete,
        gate=_Gate(),
        translator=_Tr(),
        langs=["en", "zh", "ja"],
        fetch_material=_mat,
    )
    m = session.query(Museum).one()
    assert called["gen"] == 0  # en 在 → 不重生成(完整性按语言维度)
    assert m.description_i18n["zh"] == "已有。"  # 已有不动
    assert m.description_i18n["ja"] == "ja:Existing."  # 只补缺
    assert out["translated"] == ["ja"]


def test_gate_fail_writes_nothing(session):
    generate_museum_intro(
        session,
        "orsay",
        complete=lambda s, u: "bad",
        gate=_Gate(ok=False),
        translator=_Tr(),
        langs=["en", "zh"],
        fetch_material=_mat,
    )
    assert (session.query(Museum).one().description_i18n or {}) == {}


def test_no_material_skips(session):
    out = generate_museum_intro(
        session,
        "orsay",
        complete=lambda s, u: "x",
        gate=_Gate(),
        translator=_Tr(),
        langs=["en"],
        fetch_material=lambda qid, **kw: {"extract_en": None},
    )
    assert out["skipped"] == "no_material"


def _add_obj(s, qid, title, pop, key="k"):
    m = s.query(Museum).one()
    o = upsert_object(s, m.id, {"qid": qid, "title_en": title, "category": "painting"})
    o.popularity = pop
    img = ObjectImage(object_id=o.id, role="primary", source_url="u", image_key=key)
    s.add(img)
    s.commit()
    return o


def test_cover_rejects_then_picks_next(session):
    _add_obj(session, "Q1", "L'Origine du monde", 99, key="imgA")
    _add_obj(session, "Q2", "Water Lilies", 50, key="imgB")

    def judge(system, user):
        return (
            '{"appropriate": false}' if "Origine" in user else '{"appropriate": true}'
        )

    key = select_cover(
        session, "orsay", complete=judge, fetch_building_photo=lambda qid: None
    )
    assert key == "imgB"
    assert session.query(Museum).one().cover_image_key == "imgB"


def test_cover_judge_error_skips_conservatively(session):
    _add_obj(session, "Q1", "Top", 99, key="imgA")
    _add_obj(session, "Q2", "Second", 50, key="imgB")

    def judge(system, user):
        if "Top" in user:
            raise RuntimeError("llm down")
        return '{"appropriate": true}'

    assert (
        select_cover(
            session, "orsay", complete=judge, fetch_building_photo=lambda qid: None
        )
        == "imgB"
    )


def test_cover_idempotent(session):
    m = session.query(Museum).one()
    m.cover_image_key = "fixed"
    session.commit()
    assert select_cover(session, "orsay", complete=lambda s, u: 1 / 0) == "fixed"


class _FakeStorage:
    def __init__(self):
        self.put_calls = []

    def exists(self, key):
        return False

    def put(self, key, data, content_type):
        self.put_calls.append(key)


def _fake_bytes(url):
    import io

    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (800, 600), color="white").save(buf, format="JPEG")
    return buf.getvalue()


def test_cover_prefers_building_photo_skips_safety_gate(session):
    # 建筑照优先,不经安全闸(complete 若被调用会 1/0 报错——证明确实跳过)
    storage = _FakeStorage()
    key = select_cover(
        session,
        "orsay",
        complete=lambda s, u: 1 / 0,
        fetch_building_photo=lambda qid: "http://commons.wikimedia.org/x.jpg",
        storage=storage,
        fetch_bytes=_fake_bytes,
    )
    assert key == "images/Q23402/0"
    assert storage.put_calls == [
        "images/Q23402/0_thumb.jpg",
        "images/Q23402/0_large.jpg",
    ]
    assert session.query(Museum).filter_by(slug="orsay").one().cover_image_key == key


def test_cover_falls_back_to_artwork_when_no_building_photo(session):
    _add_obj(session, "Q1", "Water Lilies", 50, key="imgB")
    key = select_cover(
        session,
        "orsay",
        complete=lambda s, u: '{"appropriate": true}',
        fetch_building_photo=lambda qid: None,  # 无建筑照
    )
    assert key == "imgB"  # 走回原藏品逻辑


def test_cover_falls_back_to_artwork_when_materialize_fails(session):
    _add_obj(session, "Q1", "Water Lilies", 50, key="imgB")

    def _boom(url):
        raise RuntimeError("network down")

    key = select_cover(
        session,
        "orsay",
        complete=lambda s, u: '{"appropriate": true}',
        fetch_building_photo=lambda qid: "http://x.jpg",
        fetch_bytes=_boom,
        storage=_FakeStorage(),
    )
    assert key == "imgB"  # 建筑照下载失败不开天窗,回落藏品


def test_cover_no_qid_skips_building_photo(session):
    m = session.query(Museum).filter_by(slug="orsay").one()
    m.qid = None
    session.commit()
    called = {"n": 0}

    def _fbp(qid):
        called["n"] += 1
        return "http://x.jpg"

    key = select_cover(
        session, "orsay", complete=lambda s, u: 1 / 0, fetch_building_photo=_fbp
    )
    assert called["n"] == 0 and key is None  # 无qid跳过建筑照;无藏品可退→None
