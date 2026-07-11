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


def test_text_chain_exact_title_returns_candidates_not_match(session):
    # 文字链即便标题精确相等(score=1.0)也只出确认卡:名字对上≠就是这件(同名撞车实证)。
    out = recognize(
        session,
        "orsay",
        _jpeg(),
        language="zh",
        identify_fn=_vision(
            [{"title": "The Origin of the World", "artist": "Gustave Courbet"}]
        ),
    )
    assert out["outcome"] == "candidates"
    assert out["match"] is None
    top = out["candidates"][0]
    assert top["qid"] == "Q334138"
    assert top["score"] == 1.0  # 精确相等仍不直判
    assert top["title"] == "世界的起源"  # 按 language 显示名
    assert top["thumbnail"].endswith("_thumb.jpg")


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
    assert out["outcome"] == "candidates"  # 文字链(含 label)不直判,一律确认卡
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


def _benefits_tables(session):
    from app.models.user_benefits import UserBenefits

    UserBenefits.__table__.create(bind=session.get_bind(), checkfirst=True)
    return UserBenefits


def test_billing_match_consumes_one(session):
    # 计费规则(用户批准):match/candidates 扣1;unrecognized 不扣;缓存命中不扣;超额 402
    from app.services.recognition.service import recognize_billed

    UB = _benefits_tables(session)
    out = recognize_billed(
        session,
        "orsay",
        _jpeg(),
        user_id=None,
        device_id="dev1",
        identify_fn=_vision(
            [{"title": "The Origin of the World", "artist": "Gustave Courbet"}]
        ),
    )
    assert out["outcome"] == "candidates"  # 文字链→确认卡,仍计费
    b = session.query(UB).one()
    assert b.recognition_quota == 9  # 10 - 1(candidates 也扣)


def test_billing_unrecognized_free(session):
    from app.services.recognition.service import recognize_billed

    UB = _benefits_tables(session)
    out = recognize_billed(
        session,
        "orsay",
        _jpeg(),
        user_id=None,
        device_id="dev1",
        identify_fn=_vision([]),
    )
    assert out["outcome"] == "unrecognized"
    assert session.query(UB).one().recognition_quota == 10  # 不扣


def test_billing_quota_exhausted_raises_before_gpt(session):
    import pytest as _pytest

    from app.services.benefits_service import BenefitsService
    from app.services.recognition.service import QuotaExceededError, recognize_billed

    _benefits_tables(session)

    def must_not_call(*a, **kw):
        raise AssertionError("超额时不应调 GPT")

    b = BenefitsService(session).get_or_create_benefits(None, "dev1")
    b.recognition_quota = 0
    session.commit()
    with _pytest.raises(QuotaExceededError):
        recognize_billed(
            session,
            "orsay",
            _jpeg(),
            user_id=None,
            device_id="dev1",
            identify_fn=must_not_call,
        )


def test_billing_cache_hit_free(session):
    from app.services.recognition.service import recognize_billed

    UB = _benefits_tables(session)

    class _FakeRedis:
        def __init__(self):
            self.store = {}

        def get(self, k):
            return self.store.get(k)

        def setex(self, k, ttl, v):
            self.store[k] = v

    r = _FakeRedis()
    img = _jpeg()
    kw = dict(
        user_id=None,
        device_id="dev1",
        identify_fn=_vision(
            [{"title": "The Origin of the World", "artist": "Gustave Courbet"}]
        ),
        redis=r,
    )
    recognize_billed(session, "orsay", img, **kw)
    recognize_billed(session, "orsay", img, **kw)  # 第二次走缓存
    assert session.query(UB).one().recognition_quota == 9  # 只扣了一次
