"""向量前置编排:DINOv2 三档 + 馆内回退全局 + GPT 兜底降级。
既有 GPT 链语义见 tests/integration/test_recognize_flow.py(原样全过);此处专测向量路径。"""

import io
import json
import threading
import time

import fakeredis
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
from app.services.image_service import ImageService
from app.services.object_importer import upsert_museum, upsert_object
from app.services.recognition import matcher
from app.services.recognition import service as svc
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


def test_close_runner_up_downgrades_match_to_candidates(session):
    # 2026-10-04 橘园《晨与柳树》被姊妹作《晴晨与柳树》以 0.875 直判:第二名紧咬时不直判
    vq = _FakeVQ([("Q334138", 0.88), ("Q152509", 0.86)])
    out = recognize(
        session, "orsay", _jpeg(), embed_fn=lambda b: "V", vector_query_fn=vq
    )
    assert out["outcome"] == "candidates"
    assert [c["qid"] for c in out["candidates"]] == ["Q334138", "Q152509"]


def test_clear_runner_up_gap_still_matches(session):
    vq = _FakeVQ([("Q334138", 0.88), ("Q152509", 0.80)])
    out = recognize(
        session, "orsay", _jpeg(), embed_fn=lambda b: "V", vector_query_fn=vq
    )
    assert out["outcome"] == "match"


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


def test_candidate_band_canvas_lifts_to_match(session):
    # 画框挤占:全帧只到候选档(0.80)→ 画布候选重查命中 HIGH → match;已 ≥LOW 不跑金字塔
    canvas, crops = _Counter(_one_crop), _Counter(_one_crop)
    vq = _FakeVQ([("Q334138", 0.80)], [("Q334138", 0.90)])
    out = recognize(
        session,
        "orsay",
        _jpeg(),
        embed_fn=lambda b: "V",
        embed_canvas_fn=canvas,
        embed_crops_fn=crops,
        vector_query_fn=vq,
    )
    assert canvas.n == 1 and crops.n == 0
    assert out["outcome"] == "match"
    assert out["match"]["confidence"] == 0.9
    assert session.query(RecognitionEvent).one().engine == "vector_canvas"


def test_fullframe_high_skips_canvas(session):
    canvas = _Counter(_one_crop)
    vq = _FakeVQ([("Q334138", 0.90)])
    out = recognize(
        session,
        "orsay",
        _jpeg(),
        embed_fn=lambda b: "V",
        embed_canvas_fn=canvas,
        vector_query_fn=vq,
    )
    assert canvas.n == 0  # 直判快路径不多算
    assert out["outcome"] == "match"


def test_canvas_still_low_runs_crop_pyramid(session):
    # 画布候选仍 < LOW → 照旧跑金字塔,三路取 MAX
    vq = _FakeVQ([("Q334138", 0.50)], [("Q334138", 0.60)], [("Q334138", 0.90)])
    out = recognize(
        session,
        "orsay",
        _jpeg(),
        embed_fn=lambda b: "V",
        embed_canvas_fn=_one_crop,
        embed_crops_fn=_one_crop,
        vector_query_fn=vq,
    )
    assert len(vq.calls) == 3
    assert out["outcome"] == "match"
    assert session.query(RecognitionEvent).one().engine == "vector_crops"


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


# --- 识别耗时(S1):record_event 收计时 + recognize() 各阶段打点 ---


def test_record_event_stores_timing(session):
    from app.services.recognition.events import record_event

    record_event(
        session,
        museum_slug="orsay",
        phash="p1",
        outcome="match",
        top_qid="Q334138",
        top_score=0.9,
        language="en",
        engine="vector",
        duration_ms=1234,
        timings={"prep": 10, "embed": 1200},
    )
    ev = session.query(RecognitionEvent).one()
    assert ev.duration_ms == 1234
    assert ev.timings == {"prep": 10, "embed": 1200}


def test_record_event_without_timing(session):
    from app.services.recognition.events import record_event

    record_event(
        session,
        museum_slug="orsay",
        phash="p2",
        outcome="match",
        top_qid="Q334138",
        top_score=0.9,
        language="en",
        engine="vector",
    )
    ev = session.query(RecognitionEvent).one()
    assert ev.duration_ms is None and ev.timings is None


def test_event_timing_vector_hit(session):
    vq = _FakeVQ([("Q334138", 0.95)])
    recognize(session, "orsay", _jpeg(), embed_fn=lambda b: "V", vector_query_fn=vq)
    ev = session.query(RecognitionEvent).one()
    assert isinstance(ev.duration_ms, int) and ev.duration_ms >= 0
    assert {"prep", "embed", "vq", "vector_out"} <= set(ev.timings)
    # 没跑的阶段不出现(否则分位数被 0 稀释)
    assert not {"gpt", "canvas", "crops", "cache_get"} & set(ev.timings)
    assert all(isinstance(v, int) and v >= 0 for v in ev.timings.values())


def test_event_timing_attributes_slow_gpt(session):
    import time

    slow = _vision([{"title": "Nope", "artist": "X"}])

    def slow_identify(*a, **k):
        time.sleep(0.05)
        return slow(*a, **k)

    recognize(
        session,
        "orsay",
        _jpeg(),
        embed_fn=lambda b: None,  # 引擎不可用 → GPT 链
        identify_fn=slow_identify,
    )
    ev = session.query(RecognitionEvent).filter_by(engine="text").one()
    assert ev.timings["gpt"] >= 40
    assert ev.duration_ms >= ev.timings["gpt"]
    assert "match" in ev.timings


def test_event_timing_cache_hit(session):
    class _FakeRedis:
        def __init__(self):
            self.store = {}

        def get(self, k):
            return self.store.get(k)

        def setex(self, k, ttl, v):
            self.store[k] = v

    r = _FakeRedis()
    vq = _FakeVQ([("Q334138", 0.95)])
    img = _jpeg()
    recognize(
        session, "orsay", img, embed_fn=lambda b: "V", vector_query_fn=vq, redis=r
    )
    recognize(
        session, "orsay", img, embed_fn=lambda b: "V", vector_query_fn=vq, redis=r
    )
    ev = session.query(RecognitionEvent).filter_by(engine="cache").one()
    assert {"prep", "cache_get"} <= set(ev.timings)
    assert "embed" not in ev.timings
    assert isinstance(ev.duration_ms, int)


def test_event_timing_redis_timeout_attributed_to_cache_get(session):
    # Redis 超时(prod socket_timeout=5s)那段必须记在 cache_get,不能算到 embed 头上
    import time

    class _SlowBrokenRedis:
        def get(self, k):
            time.sleep(0.05)
            raise TimeoutError("redis timeout")

        def setex(self, k, ttl, v):
            pass

    vq = _FakeVQ([("Q334138", 0.95)])
    recognize(
        session,
        "orsay",
        _jpeg(),
        embed_fn=lambda b: "V",
        vector_query_fn=vq,
        redis=_SlowBrokenRedis(),
    )
    ev = session.query(RecognitionEvent).one()
    assert ev.timings["cache_get"] >= 40
    assert ev.timings["embed"] < 40


@pytest.mark.real_recog_redis
def test_default_redis_cache_actually_hits(session):
    """回归:prod 缓存曾因 _get_redis 恒 None 从未命中。走**默认**客户端(不传 redis=),
    同一张图第二次必须是 engine=cache。本机/CI 没 Redis 就跳过。"""
    import redis as redis_lib

    from app.core.config import settings
    from app.services.recognition import service

    # 有没有 Redis 要**独立**判断:用被测的 _get_redis 判,bug 本身就会让用例 skip 而不是红
    r = redis_lib.Redis(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        db=settings.REDIS_DB,
        password=settings.REDIS_PASSWORD,
        socket_connect_timeout=1,
    )
    try:
        r.ping()
    except Exception:
        pytest.skip("no local redis")
    if hasattr(service, "_redis_state"):
        service._redis_state.update(client=None, failed_at=None)
    img = _jpeg()
    keys = []
    try:
        for _ in range(2):
            out = recognize(
                session,
                "orsay",
                img,
                embed_fn=lambda b: "V",
                vector_query_fn=lambda db, v, m: [("Q334138", 0.95)],
            )
        keys = r.keys("recog3:orsay:*")
        assert out["outcome"] == "match"
        engines = [e.engine for e in session.query(RecognitionEvent).all()]
        assert engines == ["vector", "cache"]
    finally:
        for k in keys or r.keys("recog3:orsay:*"):
            r.delete(k)


# ---------- S2 同键在途合并 ----------
def _ckey(img, slug="orsay", language="zh"):
    return svc._cache_key(slug, ImageService.generate_hash(img), language, None)


@pytest.fixture()
def fast_poll(monkeypatch):
    monkeypatch.setattr(svc, "_WAIT_POLL_S", 0.02)


def test_first_request_takes_and_releases_lock(session):
    r = fakeredis.FakeRedis(decode_responses=True)
    img = _jpeg()
    vq = _FakeVQ([("Q334138", 0.95)])
    recognize(
        session, "orsay", img, embed_fn=lambda b: "V", vector_query_fn=vq, redis=r
    )
    assert r.get(_ckey(img)) is not None
    assert not r.exists(svc._inflight_key(_ckey(img)))


def test_inflight_waiter_reuses_first_result(session, fast_poll):
    """同键已在算:第二个请求不重算,拿首请求写进缓存的结果。"""
    r = fakeredis.FakeRedis(decode_responses=True)
    img = _jpeg()
    ck = _ckey(img)
    first_out = {
        "outcome": "unrecognized",
        "match": None,
        "candidates": [],
        "label_text": None,
        "reason": "no_candidates",
        "phash": "x",
    }
    r.set(svc._inflight_key(ck), "1")

    def finish_first():
        r.setex(ck, 60, json.dumps(first_out))
        r.delete(svc._inflight_key(ck))

    threading.Timer(0.1, finish_first).start()
    embed = _Counter(lambda b: "V")
    out = recognize(
        session, "orsay", img, embed_fn=embed, redis=r, identify_fn=_vision()
    )
    assert embed.n == 0  # 没重算
    assert out["outcome"] == "unrecognized"
    assert out["_billed"] == "inflight"
    ev = session.query(RecognitionEvent).one()
    assert ev.engine == "cache"
    assert "inflight_wait" in ev.timings


def test_inflight_lock_gone_without_cache_waiter_computes(
    session, fast_poll, monkeypatch
):
    """首请求结束但缓存没写上(写缓存异常被吞):等待者看到锁消失就自己算,不等满上限。"""
    monkeypatch.setattr(svc, "_WAIT_CAP_S", 5)
    r = fakeredis.FakeRedis(decode_responses=True)
    img = _jpeg()
    ck = _ckey(img)
    r.set(svc._inflight_key(ck), "1")
    threading.Timer(0.1, lambda: r.delete(svc._inflight_key(ck))).start()
    vq = _FakeVQ([("Q334138", 0.95)])
    embed = _Counter(lambda b: "V")
    t0 = time.monotonic()
    out = recognize(session, "orsay", img, embed_fn=embed, vector_query_fn=vq, redis=r)
    assert time.monotonic() - t0 < 2  # 锁一消失就收敛,不是等满上限才自算
    assert embed.n == 1
    assert out["outcome"] == "match"
    assert session.query(RecognitionEvent).one().engine == "vector"


def test_inflight_wait_cap_then_computes(session, fast_poll, monkeypatch):
    """首请求一直不结束(进程卡死):等到上限后自己算。"""
    monkeypatch.setattr(svc, "_WAIT_CAP_S", 0.2)
    r = fakeredis.FakeRedis(decode_responses=True)
    img = _jpeg()
    r.set(svc._inflight_key(_ckey(img)), "1")
    vq = _FakeVQ([("Q334138", 0.95)])
    embed = _Counter(lambda b: "V")
    out = recognize(session, "orsay", img, embed_fn=embed, vector_query_fn=vq, redis=r)
    assert embed.n == 1
    assert out["outcome"] == "match"


def test_lock_released_when_compute_raises(session):
    r = fakeredis.FakeRedis(decode_responses=True)
    img = _jpeg()

    def boom(db, vec, museum_id):
        raise RuntimeError("vector index down")

    with pytest.raises(RuntimeError):
        recognize(
            session, "orsay", img, embed_fn=lambda b: "V", vector_query_fn=boom, redis=r
        )
    assert not r.exists(svc._inflight_key(_ckey(img)))


def test_lock_released_when_cache_write_fails(session):
    class _NoWrite(fakeredis.FakeRedis):
        def setex(self, *a, **k):
            raise ConnectionError("write failed")

    r = _NoWrite(decode_responses=True)
    img = _jpeg()
    vq = _FakeVQ([("Q334138", 0.95)])
    out = recognize(
        session, "orsay", img, embed_fn=lambda b: "V", vector_query_fn=vq, redis=r
    )
    assert out["outcome"] == "match"  # 写缓存失败不影响首请求
    assert not r.exists(svc._inflight_key(_ckey(img)))
