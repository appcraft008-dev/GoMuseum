import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.content import ObjectContentSection
from app.models.museum import Museum
from app.models.museum_object import MuseumObject, ObjectImage
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
    o1 = upsert_object(s, m.id, {"qid": "Q1", "title_en": "A", "category": "painting"})
    o2 = upsert_object(s, m.id, {"qid": "Q2", "title_en": "B", "category": "painting"})
    upsert_object(s, m.id, {"qid": "Q3", "title_en": "C", "category": "painting"})
    s.commit()
    rows = [
        ObjectContentSection(
            object_id=o1.id,
            language="en",
            section_code="overview",
            body="x",
            status="published",
            audio_key="a.mp3",
        ),
        ObjectContentSection(
            object_id=o1.id,
            language="en",
            section_code="artist",
            body=None,
            status="needs_review",
        ),
        ObjectContentSection(
            object_id=o1.id,
            language="fr",
            section_code="overview",
            body="y",
            status="published",
        ),
        ObjectContentSection(
            object_id=o2.id,
            language="en",
            section_code="overview",
            body="z",
            status="published",
        ),
    ]
    s.add_all(rows)
    s.commit()
    yield s


def test_quality_report_counts_and_coverage(session):
    from app.services.enrichment.content_report import build_quality_report

    rep = build_quality_report(session, "orsay", ["en", "fr"])
    assert rep["objects_total"] == 3
    en = rep["languages"]["en"]
    assert en["published"] == 2 and en["needs_review"] == 1
    assert en["pct_needs_review"] == round(1 / 3, 3)
    assert en["objects_covered"] == 2
    assert en["coverage"] == round(2 / 3, 3)
    fr = rep["languages"]["fr"]
    assert fr["published"] == 1 and fr["needs_review"] == 0
    assert fr["objects_covered"] == 1
    assert rep["missing_audio"] == 2


def test_quality_report_unknown_museum(session):
    from app.services.enrichment.content_report import build_quality_report

    assert build_quality_report(session, "nope", ["en"])["error"] == "unknown museum"


def test_quality_report_markdown(session):
    from app.services.enrichment.content_report import build_quality_report

    md = build_quality_report(session, "orsay", ["en", "fr"], as_markdown=True)
    assert isinstance(md, str)
    assert "# 内容质量报告: orsay" in md
    assert "对象数: 3" in md
    assert "已发布但缺音频: 2" in md
    assert "- en:" in md and "- fr:" in md
    assert "needs_review" in md
