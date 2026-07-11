"""向量前置编排:DINOv2 三档 + 馆内回退全局 + GPT 兜底降级。
既有 GPT 链语义见 tests/integration/test_recognize_flow.py(原样全过);此处专测向量路径。"""

import io

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
    orsay = upsert_museum(s, {"slug": "orsay", "name_en": "Orsay"})
    upsert_object(
        s,
        orsay.id,
        {
            "qid": "Q334138",
            "title_en": "The Origin of the World",
            "artist_en": "Gustave Courbet",
            "category": "painting",
            "attributes": {"title_i18n": {"en": "The Origin of the World"}},
        },
    )
    upsert_object(
        s,
        orsay.id,
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


class _Counter:
    """记录调用次数的 fake 包装(identify_fn/embed_fn 断言用)。"""

    def __init__(self, fn):
        self.n = 0
        self.fn = fn

    def __call__(self, *a, **k):
        self.n += 1
        return self.fn(*a, **k)


class _FakeVQ:
    """按调用序返回预设结果,并记录每次的 museum_id 入参。"""

    def __init__(self, *returns):
        self.returns = list(returns)
        self.calls = []

    def __call__(self, db, vec, museum_id):
        self.calls.append(museum_id)
        return self.returns[len(self.calls) - 1]


def _vision(candidates=None, label=None):
    def fake(image_b64, mode="artwork", complete=None):
        return {
            "candidates": candidates or [],
            "label_text": label,
            "self_confidence": "medium",
        }

    return fake


def test_vector_high_hit_skips_gpt(session):
    identify = _Counter(_vision([{"title": "SHOULD NOT BE USED"}]))
    vq = _FakeVQ([("Q334138", 0.95)])
    out = recognize(
        session,
        "orsay",
        _jpeg(),
        embed_fn=lambda b: "V",
        vector_query_fn=vq,
        identify_fn=identify,
    )
    assert out["outcome"] == "match"
    assert identify.n == 0  # 向量命中,GPT 不被调用
    assert out["match"]["qid"] == "Q334138"
    assert out["match"]["museum"] == "orsay"
    assert out["match"]["confidence"] == 0.95
    assert out["label_text"] is None and out["reason"] is None


def test_vector_mid_returns_candidates(session):
    vq = _FakeVQ([("Q334138", 0.80), ("Q152509", 0.75)])
    out = recognize(
        session, "orsay", _jpeg(), embed_fn=lambda b: "V", vector_query_fn=vq
    )
    assert out["outcome"] == "candidates"
    assert 1 <= len(out["candidates"]) <= 3
    for c in out["candidates"]:
        assert c["score"] >= 0.72  # RECOG_LOW
        assert c["museum"] == "orsay"
    assert out["match"] is None


def test_museum_low_then_global_high(session):
    # 馆内 top<LOW → None → 全局再查(museum_id=None)命中 HIGH
    vq = _FakeVQ([("Q334138", 0.40)], [("Q152509", 0.93)])
    out = recognize(
        session, "orsay", _jpeg(), embed_fn=lambda b: "V", vector_query_fn=vq
    )
    orsay_id = session.query(Museum).filter_by(slug="orsay").one().id
    assert vq.calls == [orsay_id, None]  # 先馆 id,再全局
    assert out["outcome"] == "match"
    assert out["match"]["qid"] == "Q152509"


def test_vector_all_miss_falls_to_gpt(session):
    identify = _Counter(
        _vision([{"title": "The Origin of the World", "artist": "Gustave Courbet"}])
    )
    vq = _FakeVQ([], [])  # 馆内 + 全局都空
    out = recognize(
        session,
        "orsay",
        _jpeg(),
        embed_fn=lambda b: "V",
        vector_query_fn=vq,
        identify_fn=identify,
    )
    assert identify.n == 1  # 落到 GPT 链
    assert out["outcome"] == "match"
    assert out["match"]["qid"] == "Q334138"


def test_engine_down_gpt_only(session):
    identify = _Counter(
        _vision([{"title": "The Origin of the World", "artist": "Gustave Courbet"}])
    )
    vq = _FakeVQ()  # 不应被调用
    out = recognize(
        session,
        "orsay",
        _jpeg(),
        embed_fn=lambda b: None,  # 引擎不可用
        vector_query_fn=vq,
        identify_fn=identify,
    )
    assert vq.calls == []  # vec 为 None,向量层跳过
    assert identify.n == 1
    assert out["outcome"] == "match"


def test_global_slug_none_records_demand_null_museum(session):
    out = recognize(
        session,
        None,  # 全局
        _jpeg(),
        embed_fn=lambda b: None,
        identify_fn=_vision([{"title": "Nonexistent Artwork", "artist": "Nobody"}]),
    )
    assert out["outcome"] == "unrecognized"
    row = session.query(RecognitionDemand).one()
    assert row.museum_slug is None


def test_cache_key_global_prefix(session):
    class _FakeRedis:
        def __init__(self):
            self.keys = []

        def get(self, k):
            return None

        def setex(self, k, ttl, v):
            self.keys.append(k)

    r = _FakeRedis()
    recognize(
        session,
        None,
        _jpeg(),
        embed_fn=lambda b: None,
        identify_fn=_vision([]),
        redis=r,
    )
    assert any(k.startswith("recog3:global:") for k in r.keys)


def test_label_mode_skips_vector(session):
    embed = _Counter(lambda b: "V")
    identify = _Counter(_vision(label="The Origin of the World\nGustave Courbet"))
    out = recognize(
        session,
        "orsay",
        _jpeg(),
        mode="label",
        embed_fn=embed,
        identify_fn=identify,
    )
    assert embed.n == 0  # label 模式不走向量
    assert identify.n == 1
    assert out["outcome"] == "match"
