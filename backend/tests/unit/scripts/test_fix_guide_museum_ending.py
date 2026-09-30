"""存量修复脚本:dry-run 不写;apply 只删英文 guide 最后一句,并让同段译文降级待重翻。"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.content import ObjectContentSection
from app.models.museum import Museum
from app.models.museum_object import MuseumObject
from app.services.object_importer import upsert_museum, upsert_object
from scripts.fix_guide_museum_ending import apply, plan

HOUSED = "One. Two. Three. It is now housed in the Musée d'Orsay."
CLEAN = "One. Two. Three. Four."


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(
        bind=engine,
        tables=[
            Museum.__table__,
            MuseumObject.__table__,
            ObjectContentSection.__table__,
        ],
    )
    s = sessionmaker(bind=engine)()
    m = upsert_museum(s, {"slug": "orsay", "name_en": "Orsay"})
    for qid, body in (("Q1", HOUSED), ("Q2", CLEAN)):
        o = upsert_object(s, m.id, {"qid": qid, "title_en": qid, "attributes": {}})
        s.flush()
        for lang, b in (("en", body), ("fr", "Un. Deux.")):
            s.add(
                ObjectContentSection(
                    object_id=o.id,
                    language=lang,
                    section_code="guide",
                    body=b,
                    status="published",
                )
            )
    s.commit()
    yield s


def _row(db, qid, lang):
    return (
        db.query(ObjectContentSection)
        .join(MuseumObject)
        .filter(MuseumObject.qid == qid, ObjectContentSection.language == lang)
        .one()
    )


def test_dry_run_plans_only_the_housed_ending_and_writes_nothing(db):
    items = plan(db, "orsay")
    assert [(o.qid, new) for o, _, new, _ in items] == [("Q1", "One. Two. Three.")]
    assert _row(db, "Q1", "en").body == HOUSED


def test_apply_drops_sentence_and_demotes_translation_for_retranslation(db):
    apply(db, plan(db, "orsay"))
    assert _row(db, "Q1", "en").body == "One. Two. Three."
    assert _row(db, "Q1", "fr").status == "needs_review"  # translate 会把它当缺失重翻
    assert (
        _row(db, "Q2", "en").body == CLEAN
        and _row(db, "Q2", "fr").status == "published"
    )
    assert plan(db, "orsay") == []  # 幂等
