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
        if '"faithful"' not in system:  # 翻译调用
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


def _seed_section(session, lang, code, body, status):
    from app.models.content import ObjectContentSection
    from app.models.museum_object import MuseumObject

    o = session.query(MuseumObject).filter_by(qid="Q1").one()
    session.add(
        ObjectContentSection(
            object_id=o.id, language=lang, section_code=code, body=body, status=status
        )
    )
    session.commit()


def _statuses(session, code):
    from app.models.content import ObjectContentSection

    return {
        r.language: r.status
        for r in session.query(ObjectContentSection).filter_by(section_code=code).all()
    }


# 契约「英语轴心」的不变量:译文的正当性来自英文源,英文源不再 published,译文必须跟着下架。
# 2026-09-03 橘园 Q64309678 实例:重生成后英文 significance 被闸清空,9 条译文原地留存,
# 正文已换塞尚、significance 还在讲梵高的医生加歇,且仍对用户下发。
def test_en_section_demoted_takes_its_translations_down(session):
    from app.services.content_repo import persist_gated_sections
    from app.services.enrichment.quality import SectionQuality

    for lang in ("fr", "zh"):
        _seed_section(session, lang, "significance", f"旧译文 {lang}", "published")
    _seed_section(session, "en", "significance", "old grounded text", "published")

    persist_gated_sections(
        session,
        "Q1",
        "en",
        {
            "significance": SectionQuality(
                body=None,
                status="needs_review",
                grounding_ratio=0.0,
                conflicts=[],
                score=0.0,
            )
        },
        model="m",
    )
    assert _statuses(session, "significance") == {
        "en": "needs_review",
        "fr": "needs_review",
        "zh": "needs_review",
    }


def test_en_section_published_leaves_translations_alone(session):
    """反向:英文段**首次**发布时不许碰译文 —— 否则这个守卫会变成随机下架机。

    注意这里没有 seed 英文段:走的是"新建"路径,没有旧 body 可比。
    英文段已存在、内容被改写的情况见下面两条。
    """
    from app.services.content_repo import persist_generated_sections

    for lang in ("fr", "zh"):
        _seed_section(session, lang, "background", f"译文 {lang}", "published")
    persist_generated_sections(
        session, "Q1", "en", {"background": "new text"}, model="m"
    )
    assert _statuses(session, "background") == {
        "en": "published",
        "fr": "published",
        "zh": "published",
    }


def test_rewriting_the_en_body_takes_its_translations_down(session):
    """英文正文**改了内容**(仍 published)→ 译文同样过期,必须下架。

    旧译文和旧音频是同一类东西:都派生自这段英文正文。清 audio_key 的那行
    早就在了,译文这半边一直漏着 —— 2026-09-14 重跑小皇宫 47 件时暴露:
    4 件的 112 段 fr/de/es/… 停在 12 天前、status 还是 published,
    英文正文已经换了一版,用户切法语看到的就是对不上的内容。
    """
    from app.services.content_repo import persist_generated_sections

    _seed_section(session, "en", "background", "old english body", "published")
    for lang in ("fr", "zh"):
        _seed_section(session, lang, "background", f"旧译文 {lang}", "published")

    persist_generated_sections(
        session, "Q1", "en", {"background": "a different english body"}, model="m"
    )
    assert _statuses(session, "background") == {
        "en": "published",
        "fr": "needs_review",
        "zh": "needs_review",
    }


def test_regenerating_identical_en_body_keeps_translations(session):
    """**对照组**:重跑生成出一字不差的正文 → 译文原样保留。

    没有这条,把判据写成"只要重写过英文段就下架译文"也能让上面那条变绿,
    而那样每次幂等重跑都会白白挂掉一批好译文、逼着重翻一遍。
    """
    from app.services.content_repo import persist_generated_sections

    _seed_section(session, "en", "background", "same english body", "published")
    for lang in ("fr", "zh"):
        _seed_section(session, lang, "background", f"译文 {lang}", "published")

    persist_generated_sections(
        session, "Q1", "en", {"background": "same english body"}, model="m"
    )
    assert _statuses(session, "background") == {
        "en": "published",
        "fr": "published",
        "zh": "published",
    }


def test_demotion_scoped_to_the_same_section(session):
    """只下架同一个 section_code 的译文,别株连隔壁段。"""
    from app.services.content_repo import persist_gated_sections
    from app.services.enrichment.quality import SectionQuality

    _seed_section(session, "fr", "significance", "译文", "published")
    _seed_section(session, "fr", "guide", "译文", "published")
    persist_gated_sections(
        session,
        "Q1",
        "en",
        {
            "significance": SectionQuality(
                body=None,
                status="needs_review",
                grounding_ratio=0.0,
                conflicts=[],
                score=0.0,
            )
        },
        model="m",
    )
    assert _statuses(session, "significance")["fr"] == "needs_review"
    assert _statuses(session, "guide")["fr"] == "published"


def test_grounding_ratio_persisted_for_en_but_not_translations(session):
    """存活率只在英语侧有意义,译文那侧 translator 填的 1.0/0.0 是 status 的复述。

    存了复述值,"平均存活率"这类查询就会被 9 种语言的假 1.0 冲淡到失真 ——
    这一列存在的全部理由就是回答"为什么挂起",掺假等于白加。
    """
    from app.models.content import ObjectContentSection
    from app.services.content_repo import persist_gated_sections
    from app.services.enrichment.quality import SectionQuality

    gated = {
        "overview": SectionQuality(
            body="Grounded.", status="published", grounding_ratio=0.75, score=0.75
        ),
        "artist": SectionQuality(
            body=None, status="needs_review", grounding_ratio=0.0, score=0.0
        ),
    }
    persist_gated_sections(session, "Q1", "en", gated, model="m")
    # 译文:translator 给的是 1.0/0.0 这种复述值
    translated = {
        "overview": SectionQuality(
            body="接地。", status="published", grounding_ratio=1.0, score=1.0
        )
    }
    persist_gated_sections(session, "Q1", "zh", translated, model="m")

    en = {
        r.section_code: r
        for r in session.query(ObjectContentSection).filter_by(language="en")
    }
    assert en["overview"].grounding_ratio == 0.75
    assert en["artist"].grounding_ratio == 0.0  # 0 ≠ NULL:整段被删是有信息的
    zh = session.query(ObjectContentSection).filter_by(language="zh").one()
    assert zh.grounding_ratio is None
