"""存量语言一致性重扫:污染段找出并重译。"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.content import (
    CategorySection,
    ObjectContentSection,
    ObjectSuggestedQuestion,
    SectionType,
)
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
            SectionType.__table__,
            CategorySection.__table__,
            ObjectContentSection.__table__,
            ObjectSuggestedQuestion.__table__,
        ],
    )
    s = sessionmaker(bind=engine)()
    m = upsert_museum(s, {"slug": "orsay", "name_en": "Orsay"})
    o = upsert_object(s, m.id, {"qid": "Q1", "title_en": "A", "category": "painting"})
    # en guide(轴心) + zh guide 污染(整段英文)
    s.add(
        ObjectContentSection(
            object_id=o.id,
            language="en",
            section_code="guide",
            body="A full English guide about the painting here now.",
            status="published",
        )
    )
    s.add(
        ObjectContentSection(
            object_id=o.id,
            language="zh",
            section_code="guide",
            body="This zh guide is entirely English which is contamination.",
            status="published",
        )
    )
    s.commit()
    yield s


class _CleanTr:
    def translate_object(self, en_sections, target_langs, titles=None):
        from app.services.enrichment.quality import SectionQuality

        lang = target_langs[0]
        return {
            lang: {
                c: SectionQuality(
                    body="这是干净的中文重译内容，讲述绘画。",
                    status="published",
                    grounding_ratio=1.0,
                    conflicts=[],
                    score=1.0,
                )
                for c in en_sections
            }
        }

    def translate_section(self, text, lang, *, strong=False, title=None):
        return "这是干净的中文重译内容，讲述绘画。"

    def check_faithfulness(self, en, tr, lang):
        return True, []


def test_rescan_finds_and_fixes_contaminated(session):
    from scripts.rescan_language import rescan

    r = rescan(session, "orsay", _CleanTr())
    assert r["contaminated_sections"] >= 1  # zh guide 是英文=污染
    assert r["fixed_langs"] >= 1
    # 重译后 zh guide 是中文
    o = session.query(MuseumObject).filter_by(qid="Q1").one()
    zh = (
        session.query(ObjectContentSection)
        .filter_by(object_id=o.id, language="zh", section_code="guide")
        .first()
    )
    assert zh and "中文" in zh.body
