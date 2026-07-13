"""向量前置编排:DINOv2 三档 + 馆内回退全局 + GPT 兜底降级。
既有 GPT 链语义见 tests/integration/test_recognize_flow.py(原样全过);此处专测向量路径。"""

import io

import numpy as np
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.artist import Artist
from app.models.museum import Museum
from app.models.museum_object import MuseumObject, ObjectImage
from app.models.recognition_demand import RecognitionDemand
from app.models.recognition_event import RecognitionEvent
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
            RecognitionEvent.__table__,
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


def test_museum_low_no_global_fallback(session):
    # 馆域调用向量 miss → 不回退全局(老 App 前向兼容:跨馆 qid = 404 死胡同),直落 GPT 链
    identify = _Counter(
        _vision([{"title": "The Origin of the World", "artist": "Gustave Courbet"}])
    )
    vq = _FakeVQ([("Q334138", 0.40)])  # top < LOW
    out = recognize(
        session,
        "orsay",
        _jpeg(),
        embed_fn=lambda b: "V",
        vector_query_fn=vq,
        identify_fn=identify,
    )
    orsay_id = session.query(Museum).filter_by(slug="orsay").one().id
    assert vq.calls == [orsay_id]  # 只查馆内一次,绝不查 None(全局)
    assert identify.n == 1  # GPT 链兜底
    assert out["outcome"] == "candidates"  # 文字链不直判,一律确认卡
    assert out["candidates"][0]["qid"] == "Q334138"


def test_vector_all_miss_falls_to_gpt(session):
    identify = _Counter(
        _vision([{"title": "The Origin of the World", "artist": "Gustave Courbet"}])
    )
    vq = _FakeVQ([])  # 馆内空
    out = recognize(
        session,
        "orsay",
        _jpeg(),
        embed_fn=lambda b: "V",
        vector_query_fn=vq,
        identify_fn=identify,
    )
    assert identify.n == 1  # 落到 GPT 链
    assert out["outcome"] == "candidates"  # 文字链不直判,一律确认卡
    assert out["candidates"][0]["qid"] == "Q334138"


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
    assert out["outcome"] == "candidates"  # 文字链不直判,一律确认卡


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


def _one_crop(b):
    """1 行的伪 crop 矩阵(内容无关,查询由 vector_query_fn 伪造)。"""
    return np.zeros((1, 3), dtype=np.float32)


def test_lowscore_crop_pyramid_high_hit_skips_gpt(session):
    # 全景式拍法:全帧低分(0.50)→ 裁剪金字塔重查命中 HIGH → match,GPT 不被调用
    identify = _Counter(_vision([{"title": "SHOULD NOT BE USED"}]))
    vq = _FakeVQ([("Q334138", 0.50)], [("Q334138", 0.90)])
    out = recognize(
        session,
        "orsay",
        _jpeg(),
        embed_fn=lambda b: "V",
        embed_crops_fn=_one_crop,
        vector_query_fn=vq,
        identify_fn=identify,
    )
    assert out["outcome"] == "match"
    assert out["match"]["qid"] == "Q334138"
    assert out["match"]["confidence"] == 0.9  # 跨全帧+裁剪取 MAX
    assert identify.n == 0


def test_lowscore_crops_also_low_falls_to_gpt(session):
    identify = _Counter(
        _vision([{"title": "The Origin of the World", "artist": "Gustave Courbet"}])
    )
    vq = _FakeVQ([("Q334138", 0.50)], [("Q334138", 0.60)])  # 裁剪仍 < LOW
    crops = _Counter(_one_crop)
    out = recognize(
        session,
        "orsay",
        _jpeg(),
        embed_fn=lambda b: "V",
        embed_crops_fn=crops,
        vector_query_fn=vq,
        identify_fn=identify,
    )
    assert crops.n == 1
    assert identify.n == 1  # 向量全 miss → GPT 兜底
    assert out["outcome"] == "candidates"


def test_fullframe_ok_skips_crop_pyramid(session):
    # 快路径:全帧已 ≥ LOW → 不跑金字塔(embed_crops_fn 不被调用)
    crops = _Counter(_one_crop)
    vq = _FakeVQ([("Q334138", 0.80)])
    out = recognize(
        session,
        "orsay",
        _jpeg(),
        embed_fn=lambda b: "V",
        embed_crops_fn=crops,
        vector_query_fn=vq,
    )
    assert crops.n == 0  # 快路径未变
    assert out["outcome"] == "candidates"


def test_crop_pyramid_failure_falls_to_gpt(session):
    identify = _Counter(
        _vision([{"title": "The Origin of the World", "artist": "Gustave Courbet"}])
    )
    vq = _FakeVQ([("Q334138", 0.50)])  # 全帧低分,裁剪失败后无二次查询
    out = recognize(
        session,
        "orsay",
        _jpeg(),
        embed_fn=lambda b: "V",
        embed_crops_fn=lambda b: None,  # 裁剪/推理失败
        vector_query_fn=vq,
        identify_fn=identify,
    )
    assert identify.n == 1  # 不崩,落 GPT 链
    assert out["outcome"] == "candidates"


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
    assert out["outcome"] == "candidates"  # 文字链(含 label)不直判,一律确认卡


# --- 埋点(recognition_events)+ 响应 phash ---


def test_records_event_vector(session):
    vq = _FakeVQ([("Q334138", 0.95)])
    out = recognize(
        session, "orsay", _jpeg(), embed_fn=lambda b: "V", vector_query_fn=vq
    )
    ev = session.query(RecognitionEvent).one()
    assert ev.engine == "vector"
    assert ev.outcome == "match"
    assert ev.top_qid == "Q334138"
    assert ev.top_score == 0.95
    assert ev.museum_slug == "orsay"
    assert ev.phash == out["phash"]


def test_records_event_vector_crops(session):
    # 全帧低分触发裁剪金字塔命中 → engine=vector_crops
    vq = _FakeVQ([("Q334138", 0.50)], [("Q334138", 0.90)])
    recognize(
        session,
        "orsay",
        _jpeg(),
        embed_fn=lambda b: "V",
        embed_crops_fn=_one_crop,
        vector_query_fn=vq,
    )
    ev = session.query(RecognitionEvent).one()
    assert ev.engine == "vector_crops"
    assert ev.outcome == "match"


def test_records_event_text(session):
    out = recognize(
        session,
        "orsay",
        _jpeg(),
        embed_fn=lambda b: None,  # 引擎不可用 → GPT 链
        identify_fn=_vision([{"title": "Nope", "artist": "X"}]),
    )
    ev = session.query(RecognitionEvent).filter_by(engine="text").one()
    assert ev.outcome == out["outcome"]
    assert ev.phash == out["phash"]


def test_records_event_cache(session):
    class _FakeRedis:
        def __init__(self):
            self.store = {}

        def get(self, k):
            return self.store.get(k)

        def setex(self, k, ttl, v):
            self.store[k] = v

    r = _FakeRedis()
    vq = _FakeVQ([("Q334138", 0.95)], [("Q334138", 0.95)])
    img = _jpeg()
    recognize(
        session, "orsay", img, embed_fn=lambda b: "V", vector_query_fn=vq, redis=r
    )
    recognize(
        session, "orsay", img, embed_fn=lambda b: "V", vector_query_fn=vq, redis=r
    )
    engines = [e.engine for e in session.query(RecognitionEvent).all()]
    assert engines.count("vector") == 1
    assert engines.count("cache") == 1


def test_response_has_phash(session):
    vq = _FakeVQ([("Q334138", 0.95)])
    out = recognize(
        session, "orsay", _jpeg(), embed_fn=lambda b: "V", vector_query_fn=vq
    )
    assert isinstance(out["phash"], str) and out["phash"]


def test_legacy_cache_entry_hit_gets_phash(session):
    # 升级前写入的旧缓存值不含 phash → 命中返回时也必须带(三档都带 phash 的兼容修复)
    import json

    from app.services.image_service import ImageService

    class _FakeRedis:
        def __init__(self, store):
            self.store = store

        def get(self, k):
            return self.store.get(k)

        def setex(self, k, ttl, v):
            self.store[k] = v

    img = _jpeg()
    sha = ImageService.generate_hash(img)
    legacy = {
        "outcome": "match",
        "match": {"qid": "Q334138", "confidence": 0.95},
        "candidates": [],
        "label_text": None,
        "reason": None,
    }  # 无 phash 键
    r = _FakeRedis({f"recog3:orsay:zh:{sha}": json.dumps(legacy)})
    out = recognize(session, "orsay", img, redis=r)
    assert isinstance(out["phash"], str) and out["phash"]


def test_open_upright_applies_exif_orientation():
    """手机竖拍JPEG像素横存+EXIF Orientation=6:解码必须转正(实证0.85→0.47崩塌)。"""
    import io as _io

    from PIL import Image

    from app.services.recognition.service import _open_upright

    img = Image.new("RGB", (400, 200), (10, 20, 30))  # 横存像素
    buf = _io.BytesIO()
    exif = Image.Exif()
    exif[274] = 6  # Orientation: Rotate 90 CW
    img.save(buf, format="JPEG", exif=exif)
    out = _open_upright(buf.getvalue())
    assert out.size == (200, 400)  # 转正后为竖图


def test_open_upright_no_exif_passthrough():
    import io as _io

    from PIL import Image

    from app.services.recognition.service import _open_upright

    img = Image.new("RGB", (400, 200))
    buf = _io.BytesIO()
    img.save(buf, format="JPEG")
    assert _open_upright(buf.getvalue()).size == (400, 200)
