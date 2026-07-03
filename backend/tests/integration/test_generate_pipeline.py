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
    def translate_section(self, t, lang):
        return t + "_" + lang

    def translate_object(self, en_sections, target_langs):
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
        def translate_object(self, en_sections, target_langs):
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
    def suggest(self, material, facts, category, target_langs, covered=None):
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
        def translate_object(self, en_sections, target_langs):
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
        def suggest(self, material, facts, category, target_langs, covered=None):
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
