"""标题存量修复:剥「Name:」标签 + 维基消歧后缀;正式副标题/引号不动;有音频的正文不改。"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.artist import Artist
from app.models.content import ObjectContentSection, ObjectSuggestedQuestion
from app.models.museum import Museum
from app.models.museum_object import MuseumObject
from app.services.object_importer import upsert_museum, upsert_object
from scripts.fix_title_i18n import apply, clean_title, plan

MONET = {"Claude Monet", "モネ", "莫奈"}


@pytest.mark.parametrize(
    "title,en,want",
    [
        ("Nome:\nPiatto con pesci dorati", "Plate", "Piatto con pesci dorati"),
        ("昼食 (モネ)", "The Luncheon", "昼食"),
        ("阿尔弗雷德·勒罗伊 (画作)", "Alfred Leroy", "阿尔弗雷德·勒罗伊"),
        (
            "ヴィシー（木立）",
            "Vichy (Grove of Trees)",
            "ヴィシー（木立）",
        ),  # 英文也带括号
        ("磨坊（马蒂格周边）", "The Mill", "磨坊（马蒂格周边）"),  # 不是作者/泛称
        (
            'La Vierge, dite "Vierge d\'humilité"',
            "Virgin",
            'La Vierge, dite "Vierge d\'humilité"',
        ),
        ("Sketch: The Flowers", "Sketch", "Sketch: The Flowers"),
    ],
)
def test_clean_title(title, en, want):
    assert clean_title(title, en, MONET) == want


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
            ObjectSuggestedQuestion.__table__,
            Artist.__table__,
        ],
    )
    s = sessionmaker(bind=engine)()
    s.add(
        Artist(
            qid="Q296",
            name_en="Claude Monet",
            name_i18n={"ja": "モネ", "it": "Nome:\nClaude Monet"},
        )
    )
    m = upsert_museum(s, {"slug": "orsay", "name_en": "Orsay"})
    o = upsert_object(
        s,
        m.id,
        {
            "qid": "Q1",
            "title_en": "The Luncheon",
            "attributes": {
                "artist_qid": "Q296",
                "title_i18n": {
                    "en": "The Luncheon",
                    "ja": "昼食 (モネ)",
                    "it": "Nome:\nLa colazione",
                },
            },
        },
    )
    s.flush()
    s.add_all(
        [
            ObjectContentSection(
                object_id=o.id,
                language="ja",
                section_code="guide",
                status="published",
                body="《昼食 (モネ)》は…",
            ),
            ObjectContentSection(
                object_id=o.id,
                language="ja",
                section_code="facts",
                status="published",
                body="昼食 (モネ)。",
                audio_key="k.mp3",
            ),
        ]
    )
    s.commit()
    yield s


def test_apply_fixes_titles_texts_without_audio_and_artist_label(db, tmp_path):
    apply(db, plan(db), str(tmp_path / "b.json"))
    o = db.query(MuseumObject).one()
    assert o.attributes["title_i18n"] == {
        "en": "The Luncheon",
        "ja": "昼食",
        "it": "La colazione",
    }
    guide, facts = (
        db.query(ObjectContentSection).filter_by(section_code=c).one()
        for c in ("guide", "facts")
    )
    assert guide.body == "《昼食》は…"
    assert facts.body == "昼食 (モネ)。" and facts.audio_key == "k.mp3"  # 有音频不动
    assert db.query(Artist).one().name_i18n == {"ja": "モネ", "it": "Claude Monet"}
    assert (tmp_path / "b.json").exists()
    p = plan(db)
    assert (
        p["objects"] == [] and p["artists"] == []
    )  # 幂等(有音频那行仍在 texts,但跳过)
