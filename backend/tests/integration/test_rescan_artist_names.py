"""存量修脚本:作者译名分叉段检测→删→带 glossary 重译(rescan_artist_names)。"""

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
from scripts.rescan_artist_names import rescan


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
        {
            "qid": "Q1",
            "title_en": "Standing Model",
            "artist_en": "Georges Seurat",
            "category": "painting",
            "attributes": {"artist_qid": "Q34013"},
        },
    )
    s.add(Artist(qid="Q34013", name_en="Georges Seurat", name_i18n={"zh": "乔治·秀拉"}))
    s.commit()
    yield s


class _Tr:
    """重译带 glossary → 译文含规范名(真实链路由 prompt 保证,这里直接体现)。"""

    def translate_object(self, en_sections, target_langs, titles=None, artists=None):
        lang = target_langs[0]
        name = (artists or {}).get(lang, "")
        return {
            lang: {
                c: SectionQuality(
                    body=f"{name}的杰作。",
                    status="published",
                    grounding_ratio=1.0,
                    conflicts=[],
                    score=1.0,
                )
                for c in en_sections
            }
        }

    def translate_section(self, text, lang, *, strong=False, title=None, artist=None):
        return f"{artist or ''}译:{text}"

    def check_faithfulness(self, en, tr, lang):
        return True, []


def _add_sec(s, o, lang, code, body):
    s.add(
        ObjectContentSection(
            object_id=o.id,
            language=lang,
            section_code=code,
            body=body,
            status="published",
        )
    )


def test_rescan_fixes_divergent_artist_rendering(session):
    o = session.query(MuseumObject).filter_by(qid="Q1").one()
    _add_sec(session, o, "en", "guide", "Seurat painted this model with dots.")
    _add_sec(session, o, "zh", "guide", "修拉用点彩画了这个模特。")  # 分叉:修拉≠秀拉
    _add_sec(session, o, "en", "facts", "Oil on canvas.")
    _add_sec(session, o, "zh", "facts", "布面油画。")  # en 未提作者 → 不动
    session.commit()

    out = rescan(session, _Tr())
    assert out["divergent_sections"] == 1 and out["fixed_langs"] == 1
    rows = {
        (r.language, r.section_code): r.body
        for r in session.query(ObjectContentSection).all()
    }
    assert "乔治·秀拉" in rows[("zh", "guide")]  # 分叉段已按规范名重译
    assert rows[("zh", "facts")] == "布面油画。"  # 无关段原样保留


def test_rescan_consistent_content_untouched(session):
    o = session.query(MuseumObject).filter_by(qid="Q1").one()
    _add_sec(session, o, "en", "guide", "Seurat painted this.")
    _add_sec(session, o, "zh", "guide", "秀拉画了这幅。")  # 已一致(含规范名姓段)
    session.commit()
    out = rescan(session, _Tr())
    assert out == {"divergent_sections": 0, "divergent_qa": 0, "fixed_langs": 0}
