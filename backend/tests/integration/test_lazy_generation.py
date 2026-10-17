"""懒生成(路线图3c):stub 首次访问触发后台生成。锁=attributes.lazy_lock_at(TTL);
empty/ready 不触发;完成清锁。runner 注入,离线可测。plan 2026-07-03-lazy-generation。"""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.content import ObjectContentSection
from app.models.museum import Museum
from app.models.museum_object import MuseumObject, ObjectImage
from app.services.enrichment.lazy import maybe_trigger, try_acquire_lock
from app.services.object_importer import upsert_museum, upsert_object


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
            ObjectContentSection.__table__,
        ],
    )
    s = sessionmaker(bind=engine)()
    m = upsert_museum(s, {"slug": "orsay", "name_en": "Orsay"})
    upsert_object(s, m.id, {"qid": "Q1", "title_en": "A", "category": "painting"})
    o = s.query(MuseumObject).filter_by(qid="Q1").one()
    o.content_status = "stub"
    # 有图才点火(方案 B 2026-10-11);已物化,不触发懒补图
    s.add(
        ObjectImage(
            object_id=o.id,
            role="primary",
            sort=0,
            source_url="https://x/q1.jpg",
            image_key="images/Q1/0",
        )
    )
    s.commit()
    yield s


def _obj(s):
    return s.query(MuseumObject).filter_by(qid="Q1").one()


def test_acquire_lock_on_stub(session):
    assert try_acquire_lock(session, _obj(session)) is True
    assert _obj(session).attributes.get("lazy_lock_at")  # 锁已落库


def test_second_acquire_within_ttl_rejected(session):
    assert try_acquire_lock(session, _obj(session)) is True
    assert try_acquire_lock(session, _obj(session)) is False


def test_stale_lock_reacquired(session):
    o = _obj(session)
    stale = (datetime.now(timezone.utc) - timedelta(minutes=11)).isoformat()
    o.attributes = {**(o.attributes or {}), "lazy_lock_at": stale}
    session.commit()
    assert try_acquire_lock(session, _obj(session)) is True


def test_non_stub_never_acquires(session):
    o = _obj(session)
    for status in ("ready", "empty", "generating"):
        o.content_status = status
        session.commit()
        assert try_acquire_lock(session, _obj(session)) is False


def test_maybe_trigger_schedules_runner_for_stub(session):
    scheduled = []
    maybe_trigger(
        session,
        "Q1",
        schedule=lambda fn, *a: scheduled.append(a),
        environment="staging",
        language="fr",
    )
    assert scheduled == [("Q1", "fr")]  # stub → 调度一次(透传请求语言=优先翻译)


def test_maybe_trigger_skips_ready_and_locked(session):
    scheduled = []
    o = _obj(session)
    o.content_status = "ready"
    session.commit()
    maybe_trigger(
        session,
        "Q1",
        schedule=lambda fn, *a: scheduled.append(a),
        environment="staging",
    )
    assert scheduled == []
    o.content_status = "stub"
    session.commit()
    maybe_trigger(
        session,
        "Q1",
        schedule=lambda fn, *a: scheduled.append(a),
        environment="staging",
    )
    maybe_trigger(
        session,
        "Q1",
        schedule=lambda fn, *a: scheduled.append(a),
        environment="staging",
    )
    assert len(scheduled) == 1  # 第二次被锁拒


def test_maybe_trigger_disabled_outside_deploy_env(session):
    # development/测试环境不触发(防误连库/误烧 LLM 费)
    scheduled = []
    maybe_trigger(
        session,
        "Q1",
        schedule=lambda fn, *a: scheduled.append(a),
        environment="development",
    )
    assert scheduled == []
    assert not (_obj(session).attributes or {}).get("lazy_lock_at")


def _publish(s, qid, lang, code="guide", body="Body."):
    o = s.query(MuseumObject).filter_by(qid=qid).one()
    s.add(
        ObjectContentSection(
            object_id=o.id,
            language=lang,
            section_code=code,
            body=body,
            status="published",
        )
    )
    s.commit()


def test_maybe_trigger_lazy_translate_when_language_missing(session):
    # ready 但请求语言缺、有 en 轴心 → 调度单语言懒翻译(不重生成)
    import app.services.enrichment.lazy as lazy

    o = _obj(session)
    o.content_status = "ready"
    session.commit()
    _publish(session, "Q1", "en")
    scheduled = []
    maybe_trigger(
        session,
        "Q1",
        schedule=lambda fn, *a: scheduled.append((fn.__name__, a)),
        environment="staging",
        language="de",
    )
    assert scheduled == [("run_lazy_translation", ("Q1", "de"))]


def test_maybe_trigger_no_translate_when_language_present_or_en(session):
    o = _obj(session)
    o.content_status = "ready"
    session.commit()
    _publish(session, "Q1", "en")
    _publish(session, "Q1", "zh", body="中文。")
    scheduled = []
    sch = lambda fn, *a: scheduled.append(a)  # noqa: E731
    maybe_trigger(session, "Q1", schedule=sch, environment="staging", language="zh")
    maybe_trigger(session, "Q1", schedule=sch, environment="staging", language="en")
    assert scheduled == []  # zh 已有;en 是轴心不翻


def test_maybe_trigger_no_translate_for_empty_object(session):
    o = _obj(session)
    o.content_status = "empty"  # 无可接地材料:不生成也不翻
    session.commit()
    scheduled = []
    maybe_trigger(
        session,
        "Q1",
        schedule=lambda fn, *a: scheduled.append(a),
        environment="staging",
        language="de",
    )
    assert scheduled == []


def test_run_lazy_translation_clears_lock(session, monkeypatch):
    import app.services.enrichment.lazy as lazy

    calls = []
    monkeypatch.setattr(
        lazy, "_translate", lambda db, qid, lang: calls.append((qid, lang))
    )
    o = _obj(session)
    o.content_status = "ready"
    session.commit()
    try_acquire_lock(session, o, require_status=("ready",))
    lazy.run_lazy_translation("Q1", "de", session_factory=lambda: session, close=False)
    assert calls == [("Q1", "de")]
    assert not (_obj(session).attributes or {}).get("lazy_lock_at")


def test_lazy_run_tags_only_its_own_rows(session, monkeypatch):
    """懒任务写的段标 ai_lazy(日上限只数它);此前就有的段、别的件都不动。"""
    import app.services.enrichment.lazy as lazy

    _publish(session, "Q1", "en")  # 任务开始前已有(批量写的)
    old = session.query(ObjectContentSection).one()
    old.generated_at = datetime.now(timezone.utc) - timedelta(hours=1)
    other = MuseumObject(museum_id=_obj(session).museum_id, qid="Q2")
    session.add(other)
    session.commit()

    def fake_translate(db, qid, lang):
        for oid in (_obj(db).id, other.id):
            db.add(
                ObjectContentSection(
                    object_id=oid,
                    language=lang,
                    section_code="guide",
                    body="x",
                    generated_at=datetime.now(timezone.utc),
                )
            )
        db.commit()

    monkeypatch.setattr(lazy, "_translate", fake_translate)
    lazy.run_lazy_translation("Q1", "de", session_factory=lambda: session, close=False)
    got = {
        (r.object_id == other.id, r.language): r.source
        for r in session.query(ObjectContentSection)
    }
    assert got == {
        (False, "en"): "ai_generated",
        (False, "de"): lazy.LAZY_SOURCE,
        (True, "de"): "ai_generated",
    }


def test_run_lazy_generation_clears_lock(session, monkeypatch):
    # 完成后清锁;生成本体由 generate_object 负责置 ready/empty(此处 fake)
    import app.services.enrichment.lazy as lazy

    def fake_generate(db, qid, language=None):
        o = db.query(MuseumObject).filter_by(qid=qid).one()
        o.content_status = "ready"
        db.flush()
        return {"qid": qid}

    monkeypatch.setattr(lazy, "_generate", fake_generate)
    try_acquire_lock(session, _obj(session))
    lazy.run_lazy_generation("Q1", session_factory=lambda: session, close=False)
    o = _obj(session)
    assert o.content_status == "ready"
    assert not (o.attributes or {}).get("lazy_lock_at")  # 锁已清


def test_run_lazy_generation_clears_lock_on_failure(session, monkeypatch):
    import app.services.enrichment.lazy as lazy

    def boom(db, qid, language=None):
        raise RuntimeError("llm down")

    monkeypatch.setattr(lazy, "_generate", boom)
    try_acquire_lock(session, _obj(session))
    lazy.run_lazy_generation("Q1", session_factory=lambda: session, close=False)
    o = _obj(session)
    assert not (o.attributes or {}).get("lazy_lock_at")  # 失败也清锁,允许重试
    assert o.content_status == "stub"  # 状态不变


def test_maybe_trigger_lazy_images_when_missing(session):
    # 懒补漏:该件有"有 source_url 无 image_key"的图行 → 调度单件物化(与内容动作独立)
    from app.models.museum_object import ObjectImage

    o = _obj(session)
    o.content_status = "ready"
    session.add(
        ObjectImage(object_id=o.id, role="primary", source_url="https://x/a.jpg")
    )
    session.commit()
    _publish(session, "Q1", "en")
    _publish(session, "Q1", "zh", body="中文。")
    scheduled = []
    maybe_trigger(
        session,
        "Q1",
        schedule=lambda fn, *a: scheduled.append((fn.__name__, a)),
        environment="staging",
        language="zh",
    )
    assert scheduled == [("run_lazy_images", ("Q1",))]  # 内容齐,只补图


def test_maybe_trigger_no_lazy_images_when_materialized(session):
    from app.models.museum_object import ObjectImage

    o = _obj(session)
    o.content_status = "ready"
    session.add(
        ObjectImage(
            object_id=o.id,
            role="primary",
            source_url="https://x/a.jpg",
            image_key="images/Q1/0",
        )
    )
    session.commit()
    _publish(session, "Q1", "en")
    _publish(session, "Q1", "zh", body="中文。")
    scheduled = []
    maybe_trigger(
        session,
        "Q1",
        schedule=lambda fn, *a: scheduled.append(a),
        environment="staging",
        language="zh",
    )
    assert scheduled == []


def test_lock_active_semantics(session):
    from app.services.enrichment.lazy import lock_active

    o = _obj(session)
    assert lock_active(o) is False  # 无锁
    try_acquire_lock(session, o)
    assert lock_active(o) is True  # 活锁=生成中
    o.attributes = {
        **(o.attributes or {}),
        "lazy_lock_at": (
            datetime.now(timezone.utc) - timedelta(minutes=11)
        ).isoformat(),
    }
    session.commit()
    assert lock_active(o) is False  # 过期锁=已死,不算生成中


def test_lazy_translate_not_retriggered_when_gated(session):
    # 死循环修复:某语言已尝试翻译但全被闸挡(needs_review)→ 不再重触发(防无限"生成中")
    from app.models.content import ObjectContentSection

    o = _obj(session)
    o.content_status = "ready"
    session.commit()
    _publish(session, "Q1", "en")  # en 轴心
    # zh 已试过:有 needs_review 段(有正文但未发布)
    session.add(
        ObjectContentSection(
            object_id=o.id,
            language="zh",
            section_code="guide",
            body="翻译含缺陷 severed head",
            status="needs_review",
        )
    )
    session.commit()
    scheduled = []
    maybe_trigger(
        session,
        "Q1",
        schedule=lambda fn, *a: scheduled.append(a),
        environment="staging",
        language="zh",
    )
    assert scheduled == []  # 已尝试过,不重触发


def test_lazy_translate_still_fires_when_no_sections(session):
    # 正常场景不受影响:该语言完全无段落 → 照常触发懒翻译
    o = _obj(session)
    o.content_status = "ready"
    session.commit()
    _publish(session, "Q1", "en")
    scheduled = []
    maybe_trigger(
        session,
        "Q1",
        schedule=lambda fn, *a: scheduled.append((fn.__name__, a)),
        environment="staging",
        language="zh",
    )
    assert scheduled == [("run_lazy_translation", ("Q1", "zh"))]


def test_lazy_generation_only_request_language(session, monkeypatch):
    # 省成本核心:懒生成只产 en 轴心 + 请求语言,不产其他 9 门
    import app.services.enrichment.lazy as lazy

    captured = {}

    def fake_generate_object(db, qid, *, target_langs, lang_priority, **kw):
        captured["target_langs"] = list(target_langs)
        for lang in target_langs:
            db.add(
                ObjectContentSection(
                    object_id=db.query(lazy.MuseumObject).filter_by(qid=qid).one().id,
                    language=lang,
                    section_code="guide",
                    body="x",
                    status="published",
                )
            )
        o = db.query(lazy.MuseumObject).filter_by(qid=qid).one()
        o.content_status = "ready"
        db.commit()
        return {"qid": qid}

    monkeypatch.setattr(
        "app.services.enrichment.pipeline.generate_object", fake_generate_object
    )
    # 本测试只验生成阶段的语言;补语言见 test_lazy_fanout
    monkeypatch.setattr(lazy, "_run_fanout", lambda *a, **k: None)
    lazy.run_lazy_generation(
        qid="Q1", language="zh", session_factory=lambda: session, close=False
    )
    assert set(captured["target_langs"]) == {"en", "zh"}  # 只 en+zh,非全 10 语


def test_maybe_trigger_reports_daily_cap_and_schedules_nothing(session, monkeypatch):
    # 10-10:预算用尽原先静默跳过,App 只能显示一个永远点不好的「重试」
    monkeypatch.setattr(
        "app.services.enrichment.lazy.daily_budget_exhausted", lambda db: True
    )
    scheduled = []
    reason = maybe_trigger(
        session,
        "Q1",
        schedule=lambda fn, *a: scheduled.append(a),
        environment="staging",
    )
    assert reason == "daily_cap"
    assert scheduled == []


def test_maybe_trigger_no_reason_when_scheduled(session):
    assert (
        maybe_trigger(session, "Q1", schedule=lambda *a: None, environment="staging")
        is None
    )


import fakeredis  # noqa: E402

from app.services.enrichment.lazy import CAP_PER_USER  # noqa: E402


def _full_user(r, uid="u1"):
    from app.services.enrichment.lazy import _today

    r.set(f"lazy:u:{uid}:{_today()}", CAP_PER_USER)


def test_per_user_cap_blocks_generation_and_clears_lock(session):
    r = fakeredis.FakeRedis(decode_responses=True)
    _full_user(r)
    scheduled = []
    reason = maybe_trigger(
        session,
        "Q1",
        schedule=lambda fn, *a: scheduled.append(fn),
        environment="staging",
        user_id="u1",
        ip="1.2.3.4",
        redis=r,
    )
    assert reason == "daily_cap"
    assert scheduled == []
    assert not _obj(session).attributes.get("lazy_lock_at")  # 锁已清,不会"假生成中"


def test_generation_charges_weight_8(session):
    from app.services.enrichment.lazy import _today

    r = fakeredis.FakeRedis(decode_responses=True)
    maybe_trigger(
        session,
        "Q1",
        schedule=lambda *a: None,
        environment="staging",
        user_id="u1",
        ip="1.2.3.4",
        redis=r,
    )
    assert r.get(f"lazy:u:u1:{_today()}") == "8"


def test_translation_charges_weight_3(session):
    from app.services.enrichment.lazy import _today

    o = _obj(session)
    o.content_status = "ready"
    session.commit()
    _publish(session, "Q1", "en")  # 文件里已有的 helper
    r = fakeredis.FakeRedis(decode_responses=True)
    maybe_trigger(
        session,
        "Q1",
        schedule=lambda *a: None,
        environment="staging",
        language="fr",
        user_id="u1",
        ip="1.2.3.4",
        redis=r,
    )
    assert r.get(f"lazy:u:u1:{_today()}") == "3"


def test_no_charge_when_lock_not_acquired(session):
    r = fakeredis.FakeRedis(decode_responses=True)
    try_acquire_lock(session, _obj(session))  # 别人正在生成
    maybe_trigger(
        session,
        "Q1",
        schedule=lambda *a: None,
        environment="staging",
        user_id="u1",
        ip="1.2.3.4",
        redis=r,
    )
    assert r.keys("lazy:*") == []


def test_exempt_skips_user_and_ip_caps(session):
    r = fakeredis.FakeRedis(decode_responses=True)
    _full_user(r)
    scheduled = []
    reason = maybe_trigger(
        session,
        "Q1",
        schedule=lambda fn, *a: scheduled.append(fn),
        environment="staging",
        user_id="u1",
        ip="1.2.3.4",
        exempt=True,
        redis=r,
    )
    assert reason is None
    assert len(scheduled) == 1


def test_exempt_still_bound_by_global_cap(session, monkeypatch):
    import app.services.enrichment.lazy as lazy

    monkeypatch.setattr(lazy, "daily_budget_exhausted", lambda db, **k: True)
    reason = maybe_trigger(
        session,
        "Q1",
        schedule=lambda *a: None,
        environment="staging",
        user_id="u1",
        exempt=True,
        redis=fakeredis.FakeRedis(decode_responses=True),
    )
    assert reason == "daily_cap"


def _drop_images(s):
    s.query(ObjectImage).filter_by(object_id=_obj(s).id).delete()
    s.commit()


def test_imageless_stub_reports_no_image_and_charges_nothing(session):
    """无图 stub 不点火(方案 B):用户本就到不了,生成了会编外观,也不该占额度。"""
    _drop_images(session)
    r = fakeredis.FakeRedis(decode_responses=True)
    scheduled = []
    reason = maybe_trigger(
        session,
        "Q1",
        schedule=lambda fn, *a: scheduled.append(fn),
        environment="staging",
        user_id="u1",
        ip="1.2.3.4",
        redis=r,
    )
    assert reason == "no_image"
    assert scheduled == []
    assert r.keys("lazy:*") == []
    assert not (_obj(session).attributes or {}).get("lazy_lock_at")


def test_imageless_stub_not_blocked_by_quarantined_image_only(session):
    """只有隔离图 = 无图(与 has_image_clause 同口径)。"""
    _drop_images(session)
    session.add(
        ObjectImage(
            object_id=_obj(session).id,
            role="view_quarantine",
            sort=0,
            source_url="https://x/q.jpg",
            image_key="images/Q1/q",
        )
    )
    session.commit()
    assert (
        maybe_trigger(session, "Q1", schedule=lambda *a: None, environment="staging")
        == "no_image"
    )


def test_imageless_ready_still_lazy_translates(session):
    """懒翻译不拦:只翻已有内容、不看图,拦了会让足迹里的用户切语言撞「重试」。"""
    _drop_images(session)
    o = _obj(session)
    o.content_status = "ready"
    session.commit()
    _publish(session, "Q1", "en")
    scheduled = []
    reason = maybe_trigger(
        session,
        "Q1",
        schedule=lambda fn, *a: scheduled.append(fn.__name__),
        environment="staging",
        language="de",
    )
    assert reason is None
    assert scheduled == ["run_lazy_translation"]


# ── 补语言阶段的按语言标记(spec 2026-10-17 §4.3)──────────────────────


def test_fanout_pending_and_generating_for(session):
    from app.services.enrichment import lazy

    o = _obj(session)
    assert lazy.fanout_pending(o) == []
    lazy._set_fanout(session, o, ["de", "it"])
    o = _obj(session)
    assert lazy.fanout_pending(o) == ["de", "it"]
    assert lazy.generating_for(o, "de") is True
    assert lazy.generating_for(o, "zh") is False  # 不在 pending:已补完或不归这次补
    lazy._clear_fanout(session, o)
    assert lazy.fanout_pending(_obj(session)) == []


def test_generating_true_while_pending_even_with_guide(session):
    # Review Focus 1:de 的 guide 已落库但深度段没翻完 → 仍算生成中,
    # 否则 App 在 generating=false 时 keepAlive,用户这次会话再也看不到深度段
    from app.services.enrichment import lazy

    o = _obj(session)
    o.content_status = "ready"
    session.commit()
    _publish(session, "Q1", "de")
    lazy._set_fanout(session, _obj(session), ["de"])
    assert lazy.generating_for(_obj(session), "de") is True


def test_fanout_marker_expires_without_heartbeat(session):
    from app.services.enrichment import lazy

    o = _obj(session)
    stale = (datetime.now(timezone.utc) - timedelta(minutes=6)).isoformat()
    o.attributes = {
        **(o.attributes or {}),
        "lazy_fanout": {"at": stale, "pending": ["de"]},
    }
    session.commit()
    assert lazy.fanout_pending(_obj(session)) == []
    assert lazy.generating_for(_obj(session), "de") is False


def test_fanout_marker_bad_value_treated_as_absent(session):
    from app.services.enrichment import lazy

    o = _obj(session)
    o.attributes = {**(o.attributes or {}), "lazy_fanout": {"at": "garbage"}}
    session.commit()
    assert lazy.fanout_pending(_obj(session)) == []


def test_set_fanout_keeps_other_attribute_keys(session):
    # 音频锁也在同一个 attributes JSON 里读改写:写标记前重读,不能抹掉别的键
    from app.services.enrichment import lazy

    o = _obj(session)
    other = sessionmaker(bind=session.get_bind())()
    oo = other.query(MuseumObject).filter_by(qid="Q1").one()
    oo.attributes = {**(oo.attributes or {}), "audio_lock": {"en:guide": "x"}}
    other.commit()
    lazy._set_fanout(session, o, ["de"])
    assert _obj(session).attributes.get("audio_lock") == {"en:guide": "x"}


def _ready(s):
    o = _obj(s)
    o.content_status = "ready"
    s.commit()


def _trigger(s, language):
    scheduled = []
    maybe_trigger(
        s,
        "Q1",
        schedule=lambda fn, *a: scheduled.append((fn.__name__, a)),
        environment="staging",
        language=language,
    )
    return [x for x in scheduled if x[0] == "run_lazy_translation"]


def test_half_done_language_retriggers_translation(session):
    # Review Focus 2:de 有 guide、缺 en 已发布的 background(半途失败)→ 懒翻译能补齐
    _ready(session)
    _publish(session, "Q1", "en")
    _publish(session, "Q1", "en", code="background")
    _publish(session, "Q1", "de")
    assert _trigger(session, "de") == [("run_lazy_translation", ("Q1", "de"))]


def test_gated_only_gap_does_not_retrigger(session):
    # de 的 background 存在但翻不过闸(needs_review)→ 算"有",不反复点火烧钱
    _ready(session)
    _publish(session, "Q1", "en")
    _publish(session, "Q1", "en", code="background")
    _publish(session, "Q1", "de")
    o = _obj(session)
    session.add(
        ObjectContentSection(
            object_id=o.id,
            language="de",
            section_code="background",
            body="x",
            status="needs_review",
        )
    )
    session.commit()
    assert _trigger(session, "de") == []


def test_no_translation_while_language_pending_in_fanout(session):
    # 补语言阶段正在补 de → 不再另起一路懒翻译(防重复翻译、覆盖段、作废音频)
    from app.services.enrichment import lazy

    _ready(session)
    _publish(session, "Q1", "en")
    lazy._set_fanout(session, _obj(session), ["de"])
    assert _trigger(session, "de") == []
    assert _trigger(session, "it") == [("run_lazy_translation", ("Q1", "it"))]


def test_maybe_trigger_records_want_while_generating(session):
    # 生成中/补语言中有人打开某门语言 → 记进 Redis,补语言阶段优先补它
    import fakeredis

    from app.services.enrichment import lazy

    r = fakeredis.FakeRedis(decode_responses=True)

    def trig(lang):
        maybe_trigger(
            session,
            "Q1",
            schedule=lambda *a: None,
            environment="staging",
            language=lang,
            redis=r,
        )

    _ready(session)
    _publish(session, "Q1", "en")
    lazy._set_fanout(session, _obj(session), ["de", "it"])
    trig("de")
    trig("fr")  # 不在 pending:不记
    trig("en")
    assert r.smembers("lazy:fanout_want:Q1") == {"de"}
    assert 0 < r.ttl("lazy:fanout_want:Q1") <= 600


def test_maybe_trigger_records_want_during_first_phase(session):
    # 首轮生成(锁还在)时用户切到 zh:补语言开始时 zh 排第一批
    import fakeredis

    r = fakeredis.FakeRedis(decode_responses=True)
    assert try_acquire_lock(session, _obj(session)) is True
    maybe_trigger(
        session,
        "Q1",
        schedule=lambda *a: None,
        environment="staging",
        language="zh",
        redis=r,
    )
    assert r.smembers("lazy:fanout_want:Q1") == {"zh"}
