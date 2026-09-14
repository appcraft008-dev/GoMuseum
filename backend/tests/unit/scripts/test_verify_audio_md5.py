"""verify_audio_md5.db_key —— 三类段落各去各的表取 audio_key。

为什么三类都要有用例:被取代的那版脚本只查 ObjectContentSection,对 qa 和
artist_bio 完全失明,**而且报告照样全绿**(2026-09-14 卢浮宫七语那批,285 条里
111 条属于这两类)。只测 section 这一侧,等于把原来的 bug 一起测成"通过"。
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.artist import Artist
from app.models.content import ObjectContentSection, ObjectSuggestedQuestion
from app.models.museum import Museum
from app.models.museum_object import MuseumObject
from scripts.verify_audio_md5 import db_key, kind_of


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
            ObjectContentSection.__table__,
            ObjectSuggestedQuestion.__table__,
            Artist.__table__,
        ],
    )
    s = sessionmaker(bind=engine)()
    m = Museum(slug="louvre", name_en="Louvre")
    s.add(m)
    s.flush()
    o = MuseumObject(museum_id=m.id, qid="Q1", title_en="One")
    s.add(o)
    s.flush()
    s.add_all(
        [
            ObjectContentSection(
                object_id=o.id,
                language="de",
                section_code="guide",
                body="x",
                audio_key="k/section",
            ),
            ObjectSuggestedQuestion(
                object_id=o.id,
                language="de",
                sort=1,
                question="q",
                answer="a",
                audio_key="k/qa",
            ),
            # 作者音频按作者共享,挂在 Artist.bio_audio 的语言字典上
            Artist(qid="Q9", bio={"de": "b"}, bio_audio={"de": "k/bio"}),
        ]
    )
    s.commit()
    yield s
    s.close()


def test_三类分派():
    assert kind_of("guide") == "section"
    assert kind_of("significance") == "section"
    assert kind_of("qa_0") == "qa"
    assert kind_of("artist_bio") == "artist_bio"


def test_正文段取到key(session):
    assert db_key(session, "Q1", "de", "guide") == "k/section"


def test_问答取到key(session):
    """sort 从 section 名里解析,qa_1 必须命中 sort=1 那一行。"""
    assert db_key(session, "Q1", "de", "qa_1") == "k/qa"


def test_作者介绍按作者qid取(session):
    """artist_bio 的 qid 是作者 qid,不是作品 qid —— 传作品 qid 必须取不到。"""
    assert db_key(session, "Q9", "de", "artist_bio") == "k/bio"
    assert db_key(session, "Q1", "de", "artist_bio") is None


def test_缺失一律返回None(session):
    assert db_key(session, "Q1", "fr", "guide") is None  # 该语言没有这一段
    assert db_key(session, "Q1", "de", "qa_7") is None  # 没有这个 sort
    assert db_key(session, "Q404", "de", "guide") is None  # 作品不存在
