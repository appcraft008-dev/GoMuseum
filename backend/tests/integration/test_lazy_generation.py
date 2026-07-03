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
