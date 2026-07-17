import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.artist import Artist
from app.models.content import ObjectContentSection, ObjectSuggestedQuestion
from app.models.museum import Museum
from app.models.museum_object import MuseumObject, ObjectImage
from app.services.enrichment.quality import SectionQuality
from app.services.object_importer import upsert_museum, upsert_object


@pytest.fixture(autouse=True)
def _offline_artist_i18n(monkeypatch):
    # 新增的国籍/代表作多语抓取默认打桩(防既有测试触网);需要时单测覆盖
    import app.services.enrichment.pipeline as pl

    monkeypatch.setattr(
        pl,
        "_artist_i18n_facts",
        lambda qid, langs: {"nationality_i18n": {}, "notable_works_i18n": {}},
    )


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
            ObjectSuggestedQuestion.__table__,
            Artist.__table__,
        ],
    )
    s = sessionmaker(bind=engine)()
    m = upsert_museum(s, {"slug": "orsay", "name_en": "Orsay"})
    upsert_object(
        s,
        m.id,
        {"qid": "Q1", "title_en": "A", "category": "painting", "attributes": {}},
    )
    s.commit()
    yield s


class _FakeEnricher:
    def generate_canonical(self, obj, sections, guide=None):
        return {"overview": "EN overview."}


class _FakeGate:
    def gate(self, material, facts, draft):
        return {
            "overview": SectionQuality(
                body="EN overview.",
                status="published",
                grounding_ratio=1.0,
                conflicts=[],
                score=1.0,
            )
        }


class _FakeTranslator:
    def translate_section(self, t, lang, *, strong=False, title=None, artist=None):
        return t + "_" + lang

    def translate_object(self, en_sections, target_langs, titles=None, artists=None):
        return {
            "fr": {
                "overview": SectionQuality(
                    body="FR aperçu.",
                    status="published",
                    grounding_ratio=1.0,
                    conflicts=[],
                    score=1.0,
                )
            }
        }


def _run(session, qid, **kw):
    from app.services.enrichment.pipeline import generate_object

    return generate_object(
        session,
        qid,
        enricher=_FakeEnricher(),
        gate=_FakeGate(),
        translator=_FakeTranslator(),
        target_langs=["en", "fr"],
        model="gpt-4o-mini",
        **kw,
    )


def test_generate_object_persists_en_and_translation(session):
    out = _run(session, "Q1")
    assert out["counts"]["en"] == (1, 0)
    assert out["counts"]["fr"] == (1, 0)
    rows = {
        (r.language, r.section_code): r
        for r in session.query(ObjectContentSection).all()
    }
    assert rows[("en", "overview")].body == "EN overview."
    assert rows[("fr", "overview")].body == "FR aperçu."


def test_generate_object_skips_when_already_published(session):
    _run(session, "Q1")
    out2 = _run(session, "Q1")
    assert out2["skipped"] == "exists"


def test_generate_object_force_regenerates(session):
    _run(session, "Q1")
    out2 = _run(session, "Q1", force=True)
    assert "counts" in out2 and "skipped" not in out2


def test_generate_object_absent_qid(session):
    assert _run(session, "Q404")["skipped"] == "absent"


def test_generate_museum_runs_over_objects(session):
    from app.services.enrichment.pipeline import generate_museum

    out = generate_museum(
        session,
        "orsay",
        enricher=_FakeEnricher(),
        gate=_FakeGate(),
        translator=_FakeTranslator(),
        target_langs=["en", "fr"],
        model="gpt-4o-mini",
    )
    assert out["objects"] == 1
    assert out["results"][0]["qid"] == "Q1"
    assert session.query(ObjectContentSection).filter_by(language="en").count() == 1


def test_generate_museum_unknown_slug(session):
    from app.services.enrichment.pipeline import generate_museum

    out = generate_museum(
        session,
        "nope",
        enricher=_FakeEnricher(),
        gate=_FakeGate(),
        translator=_FakeTranslator(),
        target_langs=["en"],
        model="m",
    )
    assert out["error"] == "unknown museum"


def test_generate_object_translates_per_language_with_priority(session):
    # 懒生成体验:请求语言排队首、逐语言翻完即落库;单语言失败不拖垮其他
    from app.services.enrichment.pipeline import generate_object
    from app.services.enrichment.quality import SectionQuality

    order = []

    class _Tr(_FakeTranslator):
        def translate_object(
            self, en_sections, target_langs, titles=None, artists=None
        ):
            assert len(target_langs) == 1  # 逐语言调用(翻完即存)
            lang = target_langs[0]
            order.append(lang)
            if lang == "de":
                raise RuntimeError("de provider down")
            return {
                lang: {
                    c: SectionQuality(
                        body=f"{lang} {b}",
                        status="published",
                        grounding_ratio=1.0,
                        conflicts=[],
                        score=1.0,
                    )
                    for c, b in en_sections.items()
                }
            }

    out = generate_object(
        session,
        "Q1",
        enricher=_FakeEnricher(),
        gate=_FakeGate(),
        translator=_Tr(),
        target_langs=["en", "de", "fr", "it"],
        model="m",
        lang_priority="it",
    )
    assert order[0] == "it"  # 请求语言优先
    assert set(order) == {"it", "de", "fr"}
    assert out["counts"]["it"] == (1, 0)
    assert out["counts"]["fr"] == (1, 0)  # de 失败不拖垮 fr
    assert "de" not in out["counts"] or out["counts"]["de"] == (0, 0)


class _FakeQA:
    def suggest(
        self,
        material,
        facts,
        category,
        target_langs,
        covered=None,
        titles=None,
        artists=None,
    ):
        return {
            "en": [{"question": "Q?", "answer": "A.", "status": "published"}],
            "fr": [{"question": "Q-fr?", "answer": "A-fr.", "status": "published"}],
        }


def test_generate_object_persists_suggested_questions(session):
    from app.models.content import ObjectSuggestedQuestion
    from app.services.enrichment.pipeline import generate_object

    out = generate_object(
        session,
        "Q1",
        enricher=_FakeEnricher(),
        gate=_FakeGate(),
        translator=_FakeTranslator(),
        target_langs=["en", "fr"],
        model="gpt-4o-mini",
        qa_suggester=_FakeQA(),
    )
    assert out["qa"] == {"en": 1, "fr": 1}
    rows = session.query(ObjectSuggestedQuestion).all()
    assert {r.language for r in rows} == {"en", "fr"}
    en = next(r for r in rows if r.language == "en")
    assert en.question == "Q?" and en.answer == "A." and en.status == "published"


def test_generate_object_without_qa_suggester_unchanged(session):
    from app.models.content import ObjectSuggestedQuestion
    from app.services.enrichment.pipeline import generate_object

    out = generate_object(
        session,
        "Q1",
        enricher=_FakeEnricher(),
        gate=_FakeGate(),
        translator=_FakeTranslator(),
        target_langs=["en", "fr"],
        model="m",
    )
    assert "qa" not in out
    assert session.query(ObjectSuggestedQuestion).count() == 0


def test_generate_object_produces_guide_section(session):
    from app.models.content import ObjectContentSection
    from app.services.enrichment.pipeline import generate_object
    from app.services.enrichment.quality import SectionQuality

    class _GuideEnricher(_FakeEnricher):
        def generate_default_guide(self, obj, facts, target_chars):
            return "Guide hook. Notice the eyes."

    class _GuideGate(_FakeGate):
        def check_section(self, material, facts, body):
            return SectionQuality(
                body=body,
                status="published",
                grounding_ratio=1.0,
                conflicts=[],
                score=1.0,
            )

    class _GuideTranslator(_FakeTranslator):
        def translate_object(
            self, en_sections, target_langs, titles=None, artists=None
        ):
            return {
                "fr": {
                    c: SectionQuality(
                        body="FR " + b,
                        status="published",
                        grounding_ratio=1.0,
                        conflicts=[],
                        score=1.0,
                    )
                    for c, b in en_sections.items()
                }
            }

    out = generate_object(
        session,
        "Q1",
        enricher=_GuideEnricher(),
        gate=_GuideGate(),
        translator=_GuideTranslator(),
        target_langs=["en", "fr"],
        model="m",
    )
    rows = {
        (r.language, r.section_code): r
        for r in session.query(ObjectContentSection).all()
    }
    assert rows[("en", "guide")].body == "Guide hook. Notice the eyes."
    assert rows[("fr", "guide")].body.startswith("FR ")


def test_generate_object_passes_guide_into_canonical(session):
    from app.services.enrichment.pipeline import generate_object
    from app.services.enrichment.quality import SectionQuality

    seen = {}

    class _Enr(_FakeEnricher):
        def generate_default_guide(self, obj, facts, target_chars):
            return "HEADLINE."

        def generate_canonical(self, obj, sections, guide=None):
            seen["guide"] = guide
            return {"artist": "A."}

    class _G(_FakeGate):
        def check_section(self, m, f, b):
            return SectionQuality(
                body=b, status="published", grounding_ratio=1.0, conflicts=[], score=1.0
            )

    generate_object(
        session,
        "Q1",
        enricher=_Enr(),
        gate=_G(),
        translator=_FakeTranslator(),
        target_langs=["en"],
        model="m",
    )
    assert seen["guide"] == "HEADLINE."  # 模块拿到了先生成的头条


def test_en_guide_persisted_before_deep_modules(session, monkeypatch):
    # 流式先出:guide 落库这一批 persist 调用必须先于深度模块那一批,轮询才能中途看到 guide。
    import app.services.enrichment.pipeline as pl
    from app.services.enrichment.quality import SectionQuality

    order = []
    orig = pl.persist_gated_sections

    def spy(db, qid, lang, results, model):
        order.extend(results.keys())
        return orig(db, qid, lang, results, model)

    monkeypatch.setattr(pl, "persist_gated_sections", spy)

    class _GuideEnricher(_FakeEnricher):
        def generate_default_guide(self, obj, facts, target_chars):
            return "Guide hook."

        def generate_canonical(self, obj, sections, guide=None):
            return {"background": "Deep background."}

    class _GuideGate(_FakeGate):
        def check_section(self, material, facts, body):
            return SectionQuality(
                body=body,
                status="published",
                grounding_ratio=1.0,
                conflicts=[],
                score=1.0,
            )

        def gate(self, material, facts, draft):
            return {
                code: SectionQuality(
                    body=b,
                    status="published",
                    grounding_ratio=1.0,
                    conflicts=[],
                    score=1.0,
                )
                for code, b in draft.items()
            }

    from app.services.enrichment.pipeline import generate_object

    generate_object(
        session,
        "Q1",
        enricher=_GuideEnricher(),
        gate=_GuideGate(),
        translator=_FakeTranslator(),
        target_langs=["en"],
        model="m",
    )
    assert order.index("guide") < order.index("background")


def test_priority_lang_guide_persisted_before_canonical(session, monkeypatch):
    # TTFC:请求语言的 guide 必须先于 canonical 深度段落库——用户 ~15s 就看到自己
    # 语言的主讲解,而非等全件(canonical/artist/qa)生成完。质量/counts 不变。
    import app.services.enrichment.pipeline as pl
    from app.services.enrichment.pipeline import generate_object
    from app.services.enrichment.quality import SectionQuality

    order = []
    orig = pl.persist_gated_sections

    def spy(db, qid, lang, results, model):
        order.extend((lang, code) for code in results)
        return orig(db, qid, lang, results, model)

    monkeypatch.setattr(pl, "persist_gated_sections", spy)

    def _ok(body):
        return SectionQuality(
            body=body, status="published", grounding_ratio=1.0, conflicts=[], score=1.0
        )

    class _Enr(_FakeEnricher):
        def generate_default_guide(self, obj, facts, target_chars):
            return "Guide hook."

        def generate_canonical(self, obj, sections, guide=None):
            return {"background": "Deep."}

    class _Gate(_FakeGate):
        def check_section(self, m, f, b):
            return _ok(b)

        def gate(self, m, f, draft):
            return {c: _ok(b) for c, b in draft.items()}

    class _Tr(_FakeTranslator):
        def translate_object(
            self, en_sections, target_langs, titles=None, artists=None
        ):
            lang = target_langs[0]
            return {lang: {c: _ok(f"{lang} {b}") for c, b in en_sections.items()}}

    out = generate_object(
        session,
        "Q1",
        enricher=_Enr(),
        gate=_Gate(),
        translator=_Tr(),
        target_langs=["en", "ja"],
        model="m",
        lang_priority="ja",
    )
    # ja guide 抢在 canonical 深度段(en background)之前落库
    assert order.index(("ja", "guide")) < order.index(("en", "background"))
    assert order.count(("ja", "guide")) == 1  # 不重复翻译
    assert out["counts"]["ja"] == (2, 0)  # 内容完整:guide + background 都发布
    assert out["counts"]["en"] == (1, 0)


class _FakeRegistry:
    def __init__(self):
        self.calls = []

    def route(self, external_ids):
        from app.services.enrichment.sources.base import ObjectContribution, Source

        outer = self

        class _Src(Source):
            name = "wikipedia"

            def fetch(self, cfg):
                return []

            def enrich(self, qid, ext, ctx):
                outer.calls.append(qid)
                return ObjectContribution(
                    source="wikipedia",
                    qid=qid,
                    fields={"extract_en": "fetched"},
                    raw={},
                )

        return [_Src()]


def test_generate_object_fetches_material_for_stub_and_marks_ready(session):
    from app.models.museum_object import MuseumObject
    from app.services.enrichment.pipeline import generate_object

    o = session.query(MuseumObject).filter_by(qid="Q1").one()
    o.content_status = "stub"
    o.attributes = {"external_ids": {}, "wiki_titles": {"en": "X"}}
    session.commit()

    reg = _FakeRegistry()
    out = generate_object(
        session,
        "Q1",
        enricher=_FakeEnricher(),
        gate=_FakeGate(),
        translator=_FakeTranslator(),
        target_langs=["en", "fr"],
        model="gpt-4o-mini",
        registry=reg,
    )
    assert "counts" in out and reg.calls == ["Q1"]
    o2 = session.query(MuseumObject).filter_by(qid="Q1").one()
    assert o2.content_status == "ready"
    assert o2.attributes["extract_en"] == "fetched"


def test_generate_object_marks_empty_when_nothing_published(session):
    from app.models.museum_object import MuseumObject
    from app.services.enrichment.pipeline import generate_object
    from app.services.enrichment.quality import SectionQuality

    class _RejectGate:
        def gate(self, material, facts, draft):
            return {
                "overview": SectionQuality(
                    body=None, status="needs_review", grounding_ratio=0.0
                )
            }

    out = generate_object(
        session,
        "Q1",
        enricher=_FakeEnricher(),
        gate=_RejectGate(),
        translator=_FakeTranslator(),
        target_langs=["en"],
        model="m",
    )
    assert out["counts"]["en"] == (0, 1)
    o = session.query(MuseumObject).filter_by(qid="Q1").one()
    assert o.content_status == "empty"


def test_generate_object_builds_evidence_pack(session):
    from app.models.museum_object import MuseumObject
    from app.services.enrichment.pipeline import generate_object

    o = session.query(MuseumObject).filter_by(qid="Q1").one()
    o.attributes = {"extract_en": "work text"}
    session.commit()
    generate_object(
        session,
        "Q1",
        enricher=_FakeEnricher(),
        gate=_FakeGate(),
        translator=_FakeTranslator(),
        target_langs=["en"],
        model="m",
    )
    o2 = session.query(MuseumObject).filter_by(qid="Q1").one()
    assert o2.evidence_pack is not None
    assert any(n["source"] == "wikipedia:work" for n in o2.evidence_pack["narrative"])


def test_generate_object_stores_artist_facts(session, monkeypatch):
    import app.services.enrichment.pipeline as pl
    from app.models.museum_object import MuseumObject
    from app.services.enrichment.pipeline import generate_object

    monkeypatch.setattr(
        pl,
        "_artist_facts",
        lambda qid: {"artist_birth": "1832", "artist_nationality": "France"},
    )
    generate_object(
        session,
        "Q1",
        enricher=_FakeEnricher(),
        gate=_FakeGate(),
        translator=_FakeTranslator(),
        target_langs=["en"],
        model="m",
        registry=_FakeRegistry(),
    )
    o = session.query(MuseumObject).filter_by(qid="Q1").one()
    assert o.attributes.get("artist_birth") == "1832"
    assert o.attributes.get("artist_nationality") == "France"


def test_generate_object_no_registry_skips_material_fetch(session):
    from app.models.museum_object import MuseumObject
    from app.services.enrichment.pipeline import generate_object

    o = session.query(MuseumObject).filter_by(qid="Q1").one()
    o.content_status = "stub"
    session.commit()
    out = generate_object(
        session,
        "Q1",
        enricher=_FakeEnricher(),
        gate=_FakeGate(),
        translator=_FakeTranslator(),
        target_langs=["en"],
        model="m",
    )
    assert "counts" in out
    assert (
        session.query(MuseumObject).filter_by(qid="Q1").one().content_status == "ready"
    )


def test_generate_object_passes_covered_to_qa(session):
    from app.services.enrichment.pipeline import generate_object
    from app.services.enrichment.quality import SectionQuality

    seen = {}

    class _QA:
        def suggest(
            self,
            material,
            facts,
            category,
            target_langs,
            covered=None,
            titles=None,
            artists=None,
        ):
            seen["covered"] = covered
            return {"en": []}

    class _Enr(_FakeEnricher):
        def generate_canonical(self, obj, sections, guide=None):
            return {"background": "深度背景正文。"}

    class _G(_FakeGate):
        def gate(self, material, facts, draft):
            return {
                code: SectionQuality(
                    body=b,
                    status="published",
                    grounding_ratio=1.0,
                    conflicts=[],
                    score=1.0,
                )
                for code, b in draft.items()
            }

    generate_object(
        session,
        "Q1",
        enricher=_Enr(),
        gate=_G(),
        translator=_FakeTranslator(),
        target_langs=["en"],
        model="m",
        qa_suggester=_QA(),
    )
    assert seen["covered"] and "深度背景正文" in seen["covered"]


def test_generate_object_creates_and_reuses_artist(session, monkeypatch):
    import app.services.enrichment.pipeline as pl
    from app.models.artist import Artist
    from app.models.museum_object import MuseumObject
    from app.services.enrichment.pipeline import generate_object

    monkeypatch.setattr(
        pl,
        "_artist_facts",
        lambda qid: {"artist_qid": "Q296", "artist_birth": "1853"},
    )
    calls = {"n": 0}

    class _Enr(_FakeEnricher):
        def generate_artist_bio(self, artist_obj):
            calls["n"] += 1
            return "梵高生平。"

    o = session.query(MuseumObject).filter_by(qid="Q1").one()
    o.attributes = {"artist_extract_en": "Van Gogh..."}
    session.commit()
    common = dict(
        enricher=_Enr(),
        gate=_FakeGate(),
        translator=_FakeTranslator(),
        target_langs=["en"],
        model="m",
        registry=_FakeRegistry(),
    )
    generate_object(session, "Q1", **common)
    art = session.query(Artist).filter_by(qid="Q296").one()
    assert art.bio and art.birth == "1853"
    assert (
        session.query(MuseumObject)
        .filter_by(qid="Q1")
        .one()
        .attributes.get("artist_qid")
        == "Q296"
    )
    # 再跑一次(同作者已存在)→ 不再调 generate_artist_bio
    generate_object(session, "Q1", **common)
    assert calls["n"] == 1


def test_generate_object_translates_missing_artist_name_zh(session, monkeypatch):
    import app.services.enrichment.pipeline as pl
    from app.models.artist import Artist
    from app.models.museum_object import MuseumObject
    from app.services.enrichment.pipeline import generate_object

    monkeypatch.setattr(pl, "_artist_facts", lambda qid: {"artist_qid": "Q7"})

    class _Enr(_FakeEnricher):
        def generate_artist_bio(self, artist_obj):
            return "bio。"

    o = session.query(MuseumObject).filter_by(qid="Q1").one()
    o.artist_zh = None
    o.artist_en = "Alfred Sisley"
    o.attributes = {"artist_extract_en": "x"}
    session.commit()
    generate_object(
        session,
        "Q1",
        enricher=_Enr(),
        gate=_FakeGate(),
        translator=_FakeTranslator(),
        target_langs=["en"],
        model="m",
        registry=_FakeRegistry(),
    )
    art = session.query(Artist).filter_by(qid="Q7").one()
    assert (
        art.name_zh and "Alfred Sisley" in art.name_zh
    )  # _FakeTranslator 回显 → 证明翻译被调


def test_generate_fills_title_and_artist_name_i18n(session, monkeypatch):
    import app.services.enrichment.pipeline as pl
    from app.models.artist import Artist
    from app.models.museum_object import MuseumObject
    from app.services.enrichment.pipeline import generate_object

    monkeypatch.setattr(pl, "_artist_facts", lambda qid: {"artist_qid": "Q7"})
    # work Q1: fr 权威有、de 无(翻译兜底);artist Q7: 无权威(翻译兜底)
    monkeypatch.setattr(
        pl,
        "_wikidata_labels",
        lambda qid, langs: {"fr": "La Nuit"} if qid != "Q7" else {},
    )

    class _Enr(_FakeEnricher):
        def generate_artist_bio(self, o):
            return "bio。"

    o = session.query(MuseumObject).filter_by(qid="Q1").one()
    o.title_en = "Starry Night"
    o.artist_en = "Van Gogh"
    o.attributes = {"artist_extract_en": "x"}
    session.commit()
    generate_object(
        session,
        "Q1",
        enricher=_Enr(),
        gate=_FakeGate(),
        translator=_FakeTranslator(),
        target_langs=["en", "fr", "de"],
        model="m",
        registry=_FakeRegistry(),
        force=True,
    )
    o2 = session.query(MuseumObject).filter_by(qid="Q1").one()
    ti = o2.attributes.get("title_i18n") or {}
    assert ti["fr"] == "La Nuit"  # 权威优先
    assert "Starry Night" in ti["de"]  # de 无权威→翻译兜底(_FakeTranslator 回显含原文)
    ni = session.query(Artist).filter_by(qid="Q7").one().name_i18n or {}
    assert "Van Gogh" in ni["fr"]  # 作者无权威→翻译兜底


def test_generate_fills_bio_when_artist_exists_without_bio(session, monkeypatch):
    # 显示名回填会先建名字-only 的 Artist 行;generate 遇 bio 空必须补,不能因行存在跳过
    import app.services.enrichment.pipeline as pl
    from app.models.artist import Artist
    from app.models.museum_object import MuseumObject
    from app.services.enrichment.pipeline import generate_object

    monkeypatch.setattr(pl, "_artist_facts", lambda qid: {"artist_qid": "Q34618"})
    monkeypatch.setattr(pl, "_wikidata_labels", lambda qid, langs: {})
    session.add(Artist(qid="Q34618", name_en="Courbet", name_i18n={"en": "Courbet"}))
    o = session.query(MuseumObject).filter_by(qid="Q1").one()
    o.attributes = {"artist_extract_en": "material"}
    session.commit()

    class _Enr(_FakeEnricher):
        def generate_artist_bio(self, artist_obj):
            return "Courbet bio."

    generate_object(
        session,
        "Q1",
        enricher=_Enr(),
        gate=_FakeGate(),
        translator=_FakeTranslator(),
        target_langs=["en"],
        model="m",
        registry=_FakeRegistry(),
    )
    art = session.query(Artist).filter_by(qid="Q34618").one()
    assert art.bio and art.bio["en"] == "Courbet bio."


def test_generate_tops_up_missing_bio_languages_for_existing_artist(
    session, monkeypatch
):
    # 作者实体已存在(bio 有 en/zh)时,生成新作品应为 bio 补齐目标语言缺口(es/it),
    # 且不重新生成 bio(用户反馈:es/it 作者简介不全)
    import app.services.enrichment.pipeline as pl
    from app.models.artist import Artist
    from app.models.museum_object import MuseumObject
    from app.services.enrichment.pipeline import generate_object

    monkeypatch.setattr(pl, "_artist_facts", lambda qid: {"artist_qid": "Q40599"})
    monkeypatch.setattr(pl, "_wikidata_labels", lambda qid, langs: {})
    session.add(
        Artist(qid="Q40599", name_en="Manet", bio={"en": "EN bio.", "zh": "中文生平。"})
    )
    o = session.query(MuseumObject).filter_by(qid="Q1").one()
    o.attributes = {"artist_extract_en": "material"}
    session.commit()
    called = {"n": 0}

    class _Enr(_FakeEnricher):
        def generate_artist_bio(self, artist_obj):
            called["n"] += 1
            return "regenerated"

    generate_object(
        session,
        "Q1",
        enricher=_Enr(),
        gate=_FakeGate(),
        translator=_FakeTranslator(),
        target_langs=["en", "es", "it", "zh"],
        model="m",
        registry=_FakeRegistry(),
    )
    art = session.query(Artist).filter_by(qid="Q40599").one()
    assert called["n"] == 0  # bio 已有 → 不重生成
    assert art.bio["es"] == "EN bio._es"  # 缺口从 en 翻译补
    assert art.bio["it"] == "EN bio._it"
    assert art.bio["zh"] == "中文生平。"  # 已有不动


def test_generate_regenerates_bio_when_en_is_junk(session, monkeypatch):
    # 存量坏数据(老bug#117遗留):bio.en 位是中文 → 视为无效,重生成英文 bio
    # (契约"完整性判断按语言维度":坏值=缺失;用户反馈 en 视图作者简介显中文)
    import app.services.enrichment.pipeline as pl
    from app.models.artist import Artist
    from app.models.museum_object import MuseumObject
    from app.services.enrichment.pipeline import generate_object

    monkeypatch.setattr(pl, "_artist_facts", lambda qid: {"artist_qid": "Q39931"})
    monkeypatch.setattr(pl, "_wikidata_labels", lambda qid, langs: {})
    session.add(
        Artist(
            qid="Q39931",
            name_en="Renoir",
            bio={"en": "雷诺阿是法国印象派画家。", "zh": "中文生平。"},
        )
    )
    o = session.query(MuseumObject).filter_by(qid="Q1").one()
    o.attributes = {"artist_extract_en": "material"}
    session.commit()

    class _Enr(_FakeEnricher):
        def generate_artist_bio(self, artist_obj):
            return "Proper English bio."

    generate_object(
        session,
        "Q1",
        enricher=_Enr(),
        gate=_FakeGate(),
        translator=_FakeTranslator(),
        target_langs=["en", "it"],
        model="m",
        registry=_FakeRegistry(),
    )
    art = session.query(Artist).filter_by(qid="Q39931").one()
    assert art.bio["en"] == "Proper English bio."  # 坏 en 被重生成替换
    assert art.bio["it"] == "Proper English bio._it"  # it 从新 en 翻
    assert art.bio["zh"] == "中文生平。"  # 已有合法语种保留


def test_generate_object_passes_country_lang_to_artist_material(session, monkeypatch):
    # 契约"零核心改动上新馆":country_lang 来自 museums.yaml,不得硬编 fr
    import app.services.enrichment.material as mat
    import app.services.enrichment.pipeline as pl
    from app.models.museum_object import MuseumObject
    from app.services.enrichment.pipeline import generate_object

    monkeypatch.setattr(pl, "_artist_facts", lambda qid: {})
    monkeypatch.setattr(pl, "_wikidata_labels", lambda qid, langs: {})
    seen = {}

    def fake_artist_material(qid, registry, *, run_query=None, country_lang="fr"):
        seen["country_lang"] = country_lang
        return {}

    monkeypatch.setattr(mat, "fetch_artist_material", fake_artist_material)
    o = session.query(MuseumObject).filter_by(qid="Q1").one()
    o.evidence_pack = {"facts": [], "narrative": [], "flagged": []}  # 免触网重建
    session.commit()
    generate_object(
        session,
        "Q1",
        enricher=_FakeEnricher(),
        gate=_FakeGate(),
        translator=_FakeTranslator(),
        target_langs=["en"],
        model="m",
        registry=_FakeRegistry(),
        country_lang="nl",
    )
    assert seen["country_lang"] == "nl"


def test_generate_object_force_refreshes_artist_bio(session, monkeypatch):
    import app.services.enrichment.pipeline as pl
    from app.models.artist import Artist
    from app.models.museum_object import MuseumObject
    from app.services.enrichment.pipeline import generate_object

    monkeypatch.setattr(pl, "_artist_facts", lambda qid: {"artist_qid": "Q9"})
    calls = {"n": 0}

    class _Enr(_FakeEnricher):
        def generate_artist_bio(self, artist_obj):
            calls["n"] += 1
            return "bio v%d。" % calls["n"]

    # 预置一条旧 Artist(bio 含旧 en + fr)
    session.add(Artist(qid="Q9", name_en="X", bio={"en": "old wrong", "fr": "fr bio"}))
    o = session.query(MuseumObject).filter_by(qid="Q1").one()
    o.artist_en = "X"
    o.attributes = {"artist_extract_en": "material"}
    session.commit()
    generate_object(
        session,
        "Q1",
        enricher=_Enr(),
        gate=_FakeGate(),
        translator=_FakeTranslator(),
        target_langs=["en"],
        model="m",
        registry=_FakeRegistry(),
        force=True,
    )
    art = session.query(Artist).filter_by(qid="Q9").one()
    assert calls["n"] == 1  # force 刷新了 bio
    assert art.bio["en"] == "bio v1。"  # en 更新
    assert art.bio["fr"] == "fr bio"  # 其它语种保留(合并)


def test_generate_fills_artist_facts_i18n(session, monkeypatch):
    # 交接③:生成时为作者补 国籍/代表作 多语(权威→翻译兜底)
    import app.services.enrichment.pipeline as pl
    from app.models.artist import Artist
    from app.models.museum_object import MuseumObject
    from app.services.enrichment.pipeline import generate_object

    monkeypatch.setattr(
        pl,
        "_artist_facts",
        lambda qid: {"artist_qid": "Q296", "artist_nationality": "France"},
    )
    monkeypatch.setattr(pl, "_wikidata_labels", lambda qid, langs: {})
    monkeypatch.setattr(
        pl,
        "_artist_i18n_facts",
        lambda qid, langs: {
            "nationality_i18n": {"zh": "法国"},
            "notable_works_i18n": {},
        },
    )

    class _Enr(_FakeEnricher):
        def generate_artist_bio(self, o):
            return "bio."

    o = session.query(MuseumObject).filter_by(qid="Q1").one()
    o.attributes = {"artist_extract_en": "x"}
    session.commit()
    generate_object(
        session,
        "Q1",
        enricher=_Enr(),
        gate=_FakeGate(),
        translator=_FakeTranslator(),
        target_langs=["en", "zh", "it"],
        model="m",
        registry=_FakeRegistry(),
    )
    art = session.query(Artist).filter_by(qid="Q296").one()
    assert art.nationality_i18n["zh"] == "法国"  # 权威
    assert art.nationality_i18n["it"] == "France_it"  # en 轴翻译兜底


def test_translate_retries_with_strong_model_on_faithfulness_fail(session):
    # Layer2:闸失败→用强模型(gpt-4o)重译(语言无关,靠闸信号触发,不硬编语言)
    from app.services.enrichment.translator import ContentTranslator

    calls = {"mini": 0, "strong": 0, "faith": 0}

    def mini(system, user):
        if "quality judge" in system:  # faithfulness
            calls["faith"] += 1
            # mini 译文含残片 → 第一次判不忠实,重译后忠实
            return (
                '{"faithful": false, "issues": ["fragment"]}'
                if calls["strong"] == 0
                else '{"faithful": true, "issues": []}'
            )
        calls["mini"] += 1
        return "含残片 severed head 的译文"

    def strong(system, user):
        calls["strong"] += 1
        return "干净的中文译文"

    tr = ContentTranslator(mini, complete_strong=strong)
    out = tr.translate_object({"guide": "The severed head."}, ["zh"])
    assert calls["strong"] == 1  # 触发了强模型重译
    assert out["zh"]["guide"].status == "published"
    assert out["zh"]["guide"].body == "干净的中文译文"


def test_translate_no_strong_retry_when_faithful(session):
    from app.services.enrichment.translator import ContentTranslator

    strong_calls = {"n": 0}

    def mini(system, user):
        if "quality judge" in system:
            return '{"faithful": true, "issues": []}'
        return "忠实译文"

    def strong(system, user):
        strong_calls["n"] += 1
        return "x"

    tr = ContentTranslator(mini, complete_strong=strong)
    out = tr.translate_object({"guide": "Body."}, ["zh"])
    assert strong_calls["n"] == 0  # 忠实则不动强模型
    assert out["zh"]["guide"].status == "published"


def test_translate_object_threads_canonical_title(session):
    from app.services.enrichment.translator import ContentTranslator

    seen = {}

    def fake(system, user):
        if "quality judge" in system.lower():
            return '{"faithful": true, "issues": []}'
        seen["system"] = system
        return "译文"

    tr = ContentTranslator(fake)
    tr.translate_object({"guide": "The Apparition."}, ["zh"], titles={"zh": "幻影"})
    assert "幻影" in seen["system"]  # 标题被穿进翻译 prompt


def test_translate_qa_items_threads_title(session):
    from app.services.enrichment.qa_suggester import translate_qa_items

    seen = []

    class _Tr:
        def translate_section(
            self, text, lang, *, strong=False, title=None, artist=None
        ):
            seen.append(title)
            return "译:" + text

        def check_faithfulness(self, en, tr, lang):
            return True, []

    translate_qa_items(
        _Tr(), [{"question": "What?", "answer": "A."}], "zh", title="显现"
    )
    assert "显现" in seen  # 问答翻译也收到规范标题


def test_translate_object_gates_wrong_language(session):
    # 语言闸:译文语言不符→gpt-4o重译;重译后语言正确→published
    from app.services.enrichment.translator import ContentTranslator

    calls = {"strong": 0}

    def mini(system, user):
        if "quality judge" in system.lower():
            return '{"faithful": true, "issues": []}'
        return (
            "This is an English sentence that leaked into a French translation badly."
        )

    def strong(system, user):
        if "quality judge" in system.lower():
            return '{"faithful": true, "issues": []}'
        calls["strong"] += 1
        return "Ceci est une phrase française correcte au sujet du tableau et de son histoire."

    tr = ContentTranslator(mini, complete_strong=strong)
    out = tr.translate_object(
        {"guide": "A sentence about the painting here now."}, ["fr"]
    )
    assert calls["strong"] == 1  # 语言不符触发强模型重译
    assert out["fr"]["guide"].status == "published"  # 重译后语言正确


def test_translate_object_threads_artist_name(session):
    # 作者译名一致性:作者规范名穿进翻译 prompt(与标题同机制)
    from app.services.enrichment.translator import ContentTranslator

    seen = {}

    def fake(system, user):
        if "quality judge" in system.lower():
            return '{"faithful": true, "issues": []}'
        seen["system"] = system
        return "译文"

    tr = ContentTranslator(fake)
    tr.translate_object(
        {"guide": "Seurat painted this."}, ["zh"], artists={"zh": "秀拉"}
    )
    assert "秀拉" in seen["system"]


def test_translate_qa_items_threads_artist(session):
    from app.services.enrichment.qa_suggester import translate_qa_items

    seen = []

    class _Tr:
        def translate_section(
            self, text, lang, *, strong=False, title=None, artist=None
        ):
            seen.append(artist)
            return "译:" + text

        def check_faithfulness(self, en, tr, lang):
            return True, []

    translate_qa_items(
        _Tr(), [{"question": "Who?", "answer": "Seurat."}], "zh", artist="秀拉"
    )
    assert "秀拉" in seen


def test_generate_passes_artist_glossary_to_translations(session, monkeypatch):
    # 端到端:作者卡规范名(name_i18n)锁进 正文翻译 + QA 的 glossary
    import app.services.enrichment.pipeline as pl
    from app.models.artist import Artist
    from app.models.museum_object import MuseumObject
    from app.services.enrichment.pipeline import generate_object
    from app.services.enrichment.quality import SectionQuality

    monkeypatch.setattr(pl, "_artist_facts", lambda qid: {"artist_qid": "Q296"})
    monkeypatch.setattr(pl, "_wikidata_labels", lambda qid, langs: {})
    session.add(
        Artist(qid="Q296", name_en="Georges Seurat", name_i18n={"zh": "乔治·秀拉"})
    )
    o = session.query(MuseumObject).filter_by(qid="Q1").one()
    o.artist_en = "Georges Seurat"
    o.attributes = {"artist_extract_en": "x"}
    session.commit()

    seen = {"translate": [], "qa": None}

    class _Tr(_FakeTranslator):
        def translate_object(
            self, en_sections, target_langs, titles=None, artists=None
        ):
            seen["translate"].append(artists)
            lang = target_langs[0]
            return {
                lang: {
                    c: SectionQuality(
                        body=f"{lang} {b}",
                        status="published",
                        grounding_ratio=1.0,
                        conflicts=[],
                        score=1.0,
                    )
                    for c, b in en_sections.items()
                }
            }

    class _QA:
        def suggest(
            self,
            material,
            facts,
            category,
            target_langs,
            covered=None,
            titles=None,
            artists=None,
        ):
            seen["qa"] = artists
            return {"en": []}

    generate_object(
        session,
        "Q1",
        enricher=_FakeEnricher(),
        gate=_FakeGate(),
        translator=_Tr(),
        target_langs=["en", "zh"],
        model="m",
        registry=_FakeRegistry(),
        qa_suggester=_QA(),
    )
    assert {"zh": "乔治·秀拉"} in seen["translate"]  # 正文翻译带作者 glossary
    assert seen["qa"] and seen["qa"].get("zh") == "乔治·秀拉"  # QA 同


def test_qa_runs_parallel_with_translations(session):
    # qa ‖ 翻译并行:qa 必须在翻译循环开始前已提交启动(串行实现会让本测试超时失败)
    import threading

    from app.services.enrichment.pipeline import generate_object
    from app.services.enrichment.quality import SectionQuality

    qa_started = threading.Event()

    class _Tr(_FakeTranslator):
        def translate_object(
            self, en_sections, target_langs, titles=None, artists=None
        ):
            assert qa_started.wait(timeout=5), "qa 未先于翻译启动(退化回串行?)"
            lang = target_langs[0]
            return {
                lang: {
                    c: SectionQuality(
                        body=f"{lang} {b}",
                        status="published",
                        grounding_ratio=1.0,
                        conflicts=[],
                        score=1.0,
                    )
                    for c, b in en_sections.items()
                }
            }

    class _QA:
        def suggest(
            self,
            material,
            facts,
            category,
            target_langs,
            covered=None,
            titles=None,
            artists=None,
        ):
            qa_started.set()
            return {"en": [{"question": "Q?", "answer": "A.", "status": "published"}]}

    out = generate_object(
        session,
        "Q1",
        enricher=_FakeEnricher(),
        gate=_FakeGate(),
        translator=_Tr(),
        target_langs=["en", "fr"],
        model="m",
        qa_suggester=_QA(),
    )
    assert out["counts"]["fr"] == (1, 0)  # 翻译照常落库
    assert out["qa"] == {"en": 1}  # qa 照常落库
