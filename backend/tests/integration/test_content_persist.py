# tests/integration/test_content_persist.py
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.content import ObjectContentSection
from app.models.museum import Museum
from app.models.museum_object import MuseumObject, ObjectImage
from app.services.content_repo import persist_explanation
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
    upsert_object(
        s,
        m.id,
        {"qid": "Q1", "title_en": "A", "image": "http://x/a.jpg", "attributes": {}},
    )
    s.commit()
    yield s


def test_persist_explanation(session):
    payload = {
        "summary": "s",
        "historical_context": "h",
        "artistic_analysis": "a",
        "cultural_significance": "c",
        "interesting_facts": ["f1", "f2"],
    }
    assert (
        persist_explanation(session, "Q1", "en", payload, model="gpt-4o-mini") is True
    )
    rows = session.query(ObjectContentSection).all()
    codes = {r.section_code for r in rows}
    assert codes == {"overview", "background", "analysis", "significance", "facts"}
    assert persist_explanation(session, "Q404", "en", payload) is False  # 无此展品


def test_persist_explanation_clears_audio_on_body_change(session):
    payload = {"summary": "s1", "interesting_facts": []}
    persist_explanation(session, "Q1", "en", payload)
    row = (
        session.query(ObjectContentSection)
        .filter_by(language="en", section_code="overview")
        .one()
    )
    row.audio_key = "object-audio/Q1/en/overview.mp3"
    session.commit()

    persist_explanation(session, "Q1", "en", {"summary": "s2", "interesting_facts": []})
    session.refresh(row)
    assert row.body == "s2"
    assert row.audio_key is None


def test_persist_explanation_keeps_audio_on_same_body(session):
    payload = {"summary": "same", "interesting_facts": []}
    persist_explanation(session, "Q1", "en", payload)
    row = (
        session.query(ObjectContentSection)
        .filter_by(language="en", section_code="overview")
        .one()
    )
    row.audio_key = "object-audio/Q1/en/overview.mp3"
    session.commit()

    persist_explanation(session, "Q1", "en", payload)
    session.refresh(row)
    assert row.audio_key == "object-audio/Q1/en/overview.mp3"


def test_persist_generated_sections_upsert(session):
    from app.services.content_repo import persist_generated_sections

    n = persist_generated_sections(
        session,
        "Q1",
        "en",
        {"overview": "An overview.", "artist": None},  # artist None → 不建行
        model="gpt-4o-mini",
    )
    assert n == 1  # 只发布有内容的 overview
    rows = {
        r.section_code: r
        for r in session.query(ObjectContentSection).filter_by(language="en").all()
    }
    assert rows["overview"].body == "An overview."
    assert rows["overview"].status == "published"
    assert rows["overview"].model == "gpt-4o-mini"
    assert rows["overview"].source == "ai_generated"
    assert "artist" not in rows  # 空段不建行


def test_persist_generated_unknown_qid_returns_zero(session):
    from app.services.content_repo import persist_generated_sections

    assert (
        persist_generated_sections(session, "Q404", "en", {"overview": "x"}, model="m")
        == 0
    )


def test_persist_gated_sections_writes_published_and_needs_review(session):
    from app.models.content import ObjectContentSection
    from app.services.content_repo import persist_gated_sections
    from app.services.enrichment.quality import SectionQuality

    results = {
        "overview": SectionQuality(
            body="Good grounded text.",
            status="published",
            grounding_ratio=1.0,
            conflicts=[],
            score=1.0,
        ),
        "artist": SectionQuality(
            body=None,
            status="needs_review",
            grounding_ratio=0.0,
            conflicts=[],
            score=0.0,
        ),
    }
    pub, nr = persist_gated_sections(session, "Q1", "en", results, model="gpt-4o-mini")
    assert (pub, nr) == (1, 1)
    rows = {
        r.section_code: r
        for r in session.query(ObjectContentSection).filter_by(language="en").all()
    }
    assert rows["overview"].status == "published"
    assert rows["overview"].body == "Good grounded text."
    assert rows["overview"].source == "ai_generated"
    assert rows["artist"].status == "needs_review"
    assert rows["artist"].body is None


def test_persist_gated_unknown_qid_returns_zeros(session):
    from app.services.content_repo import persist_gated_sections
    from app.services.enrichment.quality import SectionQuality

    r = {
        "overview": SectionQuality(
            body="x", status="published", grounding_ratio=1.0, conflicts=[], score=1.0
        )
    }
    assert persist_gated_sections(session, "Q404", "en", r, model="m") == (0, 0)


def test_persist_generated_sections_still_works(session):
    # 回归：抽 _upsert_section 后旧函数行为不变
    from app.services.content_repo import persist_generated_sections

    n = persist_generated_sections(
        session, "Q1", "en", {"overview": "Body.", "artist": None}, model="m"
    )
    assert n == 1


def test_translate_object_output_persists_per_language(session):
    import json as _json

    from app.services.content_repo import persist_gated_sections
    from app.services.enrichment.translator import ContentTranslator

    def router(system, user):
        if "quality judge" not in system.lower():  # 翻译调用
            return "Texte traduit."
        return _json.dumps({"faithful": True, "issues": []})

    by_lang = ContentTranslator(router).translate_object(
        {"overview": "English overview."}, ["en", "fr"]
    )
    # 按语言落库
    for lang, results in by_lang.items():
        persist_gated_sections(session, "Q1", lang, results, model="gpt-4o-mini")

    rows = {
        (r.language, r.section_code): r
        for r in session.query(ObjectContentSection).all()
    }
    assert ("fr", "overview") in rows
    assert rows[("fr", "overview")].body == "Texte traduit."
    assert rows[("fr", "overview")].status == "published"
    assert ("en", "overview") not in rows


def test_upsert_section_clears_audio_key_on_body_change(session):
    # Important 修复:persist_gated_sections 改 body → 旧 audio_key 失效(防播放旧音频)
    from app.services.content_repo import persist_gated_sections, persist_section_audio
    from app.services.enrichment.quality import SectionQuality

    class _FakeStore:
        def put(self, k, d, c):
            pass

        def public_url(self, k):
            return f"u/{k}"

    def _sec(body):
        return {
            "guide": SectionQuality(
                body=body,
                status="published",
                grounding_ratio=1.0,
                conflicts=[],
                score=1.0,
            )
        }

    persist_gated_sections(session, "Q1", "zh", _sec("原讲解"), "m")
    persist_section_audio(session, "Q1", "zh", "guide", b"AUDIO", _FakeStore())
    o = session.query(MuseumObject).filter_by(qid="Q1").one()
    row = (
        session.query(ObjectContentSection)
        .filter_by(object_id=o.id, language="zh", section_code="guide")
        .one()
    )
    assert row.audio_key is not None  # 有音频

    persist_gated_sections(session, "Q1", "zh", _sec("改后的讲解"), "m")  # body 变
    session.refresh(row)
    assert row.audio_key is None  # 旧音频失效

    # 相同 body 重跑 → 不误清(此处已 None,验幂等不报错即可)
    persist_section_audio(session, "Q1", "zh", "guide", b"AUDIO2", _FakeStore())
    persist_gated_sections(session, "Q1", "zh", _sec("改后的讲解"), "m")  # body 同
    session.refresh(row)
    assert row.audio_key is not None  # body 未变 → 音频保留
