"""音频队列只排已发布内容 —— 未发布的段/问答不该进队列。

2026-08 橘园试点实测:30 个 guide 任务里 2 个是 needs_review,前端不返回其正文,
生成侧取不回文本 → 白跑一趟,灌入时质量闸还判失败。占比 6.7%,量大时是实打实的浪费。
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.artist import Artist
from app.models.content import ObjectContentSection, ObjectSuggestedQuestion
from app.models.museum import Museum
from app.models.museum_object import MuseumObject, ObjectImage
from app.services.enrichment.audio_queue import build_queue
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
    m = upsert_museum(s, {"slug": "orangerie", "name_en": "Orangerie"})
    upsert_object(s, m.id, {"qid": "Q1", "title_en": "A"})
    upsert_object(s, m.id, {"qid": "Q2", "title_en": "B"})
    s.commit()
    yield s
    s.close()


def _obj_id(s, qid):
    return s.query(MuseumObject).filter_by(qid=qid).one().id


def test_needs_review_section_not_queued(session):
    """已发布的进队列,needs_review 的不进。"""
    session.add_all(
        [
            ObjectContentSection(
                object_id=_obj_id(session, "Q1"),
                language="de",
                section_code="guide",
                body="veroeffentlicht",
                status="published",
            ),
            ObjectContentSection(
                object_id=_obj_id(session, "Q2"),
                language="de",
                section_code="guide",
                body="noch nicht geprueft",
                status="needs_review",
            ),
        ]
    )
    session.commit()

    jobs = build_queue(session, languages=["de"], target_engine="voxcpm2")
    qids = {j.qid for j in jobs}
    assert "Q1" in qids, "已发布的段必须进队列"
    assert "Q2" not in qids, "needs_review 的段不该进队列(取不回正文,白跑)"


def test_needs_review_qa_not_queued(session):
    """问答同理:未发布的不进队列。"""
    session.add_all(
        [
            ObjectContentSection(
                object_id=_obj_id(session, "Q1"),
                language="zh",
                section_code="guide",
                body="正文",
                status="published",
            ),
            ObjectSuggestedQuestion(
                object_id=_obj_id(session, "Q1"),
                language="zh",
                sort=0,
                question="问一",
                answer="答一",
                status="published",
            ),
            ObjectSuggestedQuestion(
                object_id=_obj_id(session, "Q1"),
                language="zh",
                sort=1,
                question="问二",
                answer="答二",
                status="needs_review",
            ),
        ]
    )
    session.commit()

    jobs = build_queue(session, languages=["zh"], target_engine="voxcpm2")
    qa_sections = {j.section for j in jobs if j.kind == "qa"}
    assert "qa_0" in qa_sections, "已发布问答必须进队列"
    assert "qa_1" not in qa_sections, "needs_review 问答不该进队列"
