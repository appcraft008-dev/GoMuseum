"""识别编排:vision(注入)→匹配→三档分流→记需求。R1:身份只来自目录命中。
spec 2026-07-03-recognition-design。"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.artist import Artist
from app.models.museum import Museum
from app.models.museum_object import MuseumObject, ObjectImage
from app.models.recognition_demand import RecognitionDemand
from app.services.object_importer import upsert_museum, upsert_object
from app.services.recognition import matcher
from app.services.recognition.service import recognize


def _jpeg():
    import io

    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (64, 64), (10, 20, 30)).save(buf, format="JPEG")
    return buf.getvalue()


@pytest.fixture()
def session():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(
        bind=engine,
        tables=[
            Museum.__table__,
            MuseumObject.__table__,
            ObjectImage.__table__,
            Artist.__table__,
            RecognitionDemand.__table__,
        ],
    )
    s = sessionmaker(bind=engine)()
    m = upsert_museum(s, {"slug": "orsay", "name_en": "Orsay"})
    upsert_object(
        s,
        m.id,
        {
            "qid": "Q334138",
            "title_en": "The Origin of the World",
            "artist_en": "Gustave Courbet",
            "category": "painting",
            "images": ["https://img/a.jpg"],
            "attributes": {
                "title_i18n": {
                    "en": "The Origin of the World",
                    "zh": "世界的起源",
                }
            },
        },
    )
    o = s.query(MuseumObject).filter_by(qid="Q334138").one()
    img = s.query(ObjectImage).filter_by(object_id=o.id).one()
    img.image_key = "images/Q334138/0"
    upsert_object(
        s,
        m.id,
        {
            "qid": "Q152509",
            "title_en": "Luncheon on the Grass",
            "artist_en": "Édouard Manet",
            "category": "painting",
            "attributes": {"title_i18n": {"en": "Luncheon on the Grass"}},
        },
    )
    s.commit()
    matcher._index_cache.clear()
    yield s
    matcher._index_cache.clear()


def _vision(candidates=None, label=None):
    def fake(image_b64, mode="artwork", complete=None):
        return {
            "candidates": candidates or [],
            "label_text": label,
            "self_confidence": "medium",
        }

    return fake


def test_high_confidence_direct_match(session):
    out = recognize(
        session,
        "orsay",
        _jpeg(),
        language="zh",
        identify_fn=_vision(
            [{"title": "The Origin of the World", "artist": "Gustave Courbet"}]
        ),
    )
    assert out["outcome"] == "match"
    assert out["match"]["qid"] == "Q334138"
    assert out["match"]["title"] == "世界的起源"  # 按 language 显示名
    assert out["match"]["thumbnail"].endswith("_thumb.jpg")
    assert out["candidates"] == []


def test_mid_confidence_returns_candidates(session):
    out = recognize(
        session,
        "orsay",
        _jpeg(),
        identify_fn=_vision([{"title": "Origin of World painting", "artist": None}]),
    )
    assert out["outcome"] == "candidates"
    assert 1 <= len(out["candidates"]) <= 3
    assert out["candidates"][0]["qid"] == "Q334138"
    assert 0 < out["candidates"][0]["score"] < 1
    assert out["match"] is None


def test_unmatched_records_demand(session):
    out = recognize(
        session,
        "orsay",
        _jpeg(),
        identify_fn=_vision([{"title": "Starry Night", "artist": "Van Gogh"}]),
    )
    assert out["outcome"] == "unrecognized"
    assert out["reason"] in ("not_in_catalog", "low_confidence")
    assert session.query(RecognitionDemand).count() == 1


def test_vision_empty_reason_no_candidates(session):
    out = recognize(session, "orsay", _jpeg(), identify_fn=_vision([]))
    assert out["outcome"] == "unrecognized" and out["reason"] == "no_candidates"


def test_label_mode_passed_through_and_label_text_returned(session):
    seen = {}

    def fake(image_b64, mode="artwork", complete=None):
        seen["mode"] = mode
        return {
            "candidates": [],
            "label_text": "The Origin of the World\nGustave Courbet",
            "self_confidence": "high",
        }

    out = recognize(session, "orsay", _jpeg(), mode="label", identify_fn=fake)
    assert seen["mode"] == "label"
    assert out["outcome"] == "match"  # 墙签行直接匹配命中
    assert "Origin" in out["label_text"]


def test_unknown_museum_returns_none(session):
    assert recognize(session, "nope", _jpeg(), identify_fn=_vision([])) is None


def test_artist_name_does_not_hijack_portrait_titles(session):
    # staging 真实误配:候选作者名"Pierre-Auguste Renoir"被当标题探针,
    # 劫持了巴齐耶《奥古斯特·雷诺阿像》(以画家为题的肖像)。作者名只加分,不当标题匹配。
    m = session.query(Museum).filter_by(slug="orsay").one()
    upsert_object(
        session,
        m.id,
        {
            "qid": "Q12142552",
            "title_en": "Auguste Renoir",  # 肖像画:标题=画家名
            "artist_en": "Frédéric Bazille",
            "category": "painting",
            "attributes": {"title_i18n": {"en": "Auguste Renoir"}},
        },
    )
    upsert_object(
        session,
        m.id,
        {
            "qid": "Q683274",
            "title_en": "Bal du moulin de la Galette",
            "artist_en": "Pierre-Auguste Renoir",
            "category": "painting",
            "attributes": {"title_i18n": {"en": "Bal du moulin de la Galette"}},
        },
    )
    session.commit()
    matcher._index_cache.clear()
    out = recognize(
        session,
        "orsay",
        _jpeg(),
        identify_fn=_vision(
            [
                {
                    "title": "Dance at Le Moulin de la Galette",
                    "artist": "Auguste Renoir",  # GPT 常给短名:与肖像标题精确相等
                }
            ]
        ),
    )
    assert out["outcome"] in ("match", "candidates")
    top_qid = (out["match"] or out["candidates"][0])["qid"]
    assert top_qid == "Q683274"  # 舞会,不是雷诺阿肖像
