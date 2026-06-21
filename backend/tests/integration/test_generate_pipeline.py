import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.content import ObjectContentSection
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
    def generate_canonical(self, obj, sections):
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
