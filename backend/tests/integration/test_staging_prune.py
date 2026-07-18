"""金样本裁剪:规则保留(热度top/樱桃/文字层样本/多视角/多音译作者/裸stub/empty),其余连子行删。"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.artist import Artist
from app.models.content import ObjectContentSection, ObjectSuggestedQuestion
from app.models.museum import Museum
from app.models.museum_object import MuseumObject, ObjectImage
from app.models.object_embedding import ObjectEmbedding
from app.services.object_importer import upsert_museum, upsert_object
from scripts.staging_prune import golden_ids, prune


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
            ObjectEmbedding.__table__,
            ObjectContentSection.__table__,
            ObjectSuggestedQuestion.__table__,
            Artist.__table__,
        ],
    )
    s = sessionmaker(bind=engine)()
    m = upsert_museum(s, {"slug": "orsay", "name_en": "Orsay"})

    def obj(qid, **kw):
        return upsert_object(
            s,
            m.id,
            {
                "qid": qid,
                "title_en": kw.pop("title", qid),
                "category": kw.pop("category", "painting"),
                "attributes": {},
                **kw,
            },
        )

    hot = obj("Q1")
    hot.popularity = 99
    obj("Q2").popularity = 50
    cherry = obj("joconde-C1")  # 合成 qid 带图(樱桃)
    s.add(ObjectImage(object_id=cherry.id, role="primary", source_url="u"))
    obj("joconde-T1")  # 合成 qid 文字层
    sculpt = obj("Q3", category="sculpture")
    s.add(ObjectImage(object_id=sculpt.id, role="view", source_url="v"))
    seurat = obj("Q4")
    seurat.artist_en = "Georges Seurat"
    bare = obj("Q5")
    bare.title_en = None
    empty = obj("Q6")
    empty.content_status = "empty"
    # 该死的:热度垫底且带全套子行
    doomed = obj("Q99", category="works_on_paper")
    doomed.popularity = -1
    img = ObjectImage(object_id=doomed.id, role="primary", source_url="x")
    s.add(img)
    s.flush()
    s.add(ObjectEmbedding(object_id=doomed.id, image_id=img.id, model="m", vec=b"\x00"))
    s.add(
        ObjectContentSection(
            object_id=doomed.id,
            language="en",
            section_code="guide",
            body="b",
            status="published",
        )
    )
    s.add(
        ObjectSuggestedQuestion(
            object_id=doomed.id,
            language="en",
            sort=0,
            question="q?",
            answer="a",
            status="published",
        )
    )
    s.commit()
    yield s


def test_golden_rules_keep_edge_faces(session):
    keep = golden_ids(session)
    qids = {
        o.qid for o in session.query(MuseumObject).filter(MuseumObject.id.in_(keep))
    }
    assert {"Q1", "joconde-C1", "joconde-T1", "Q3", "Q4", "Q5", "Q6"} <= qids


def test_prune_deletes_doomed_with_children(session):
    # 让 doomed 落网:works_on_paper 类只此一件会被 top30 保住 → 再造 30 件同类挤掉它
    m = session.query(Museum).one()
    for i in range(30):
        o = upsert_object(
            session,
            m.id,
            {
                "qid": f"Qf{i}",
                "title_en": f"f{i}",
                "category": "works_on_paper",
                "attributes": {},
            },
        )
        o.popularity = 10 + i
    session.commit()
    out = prune(session)
    assert out["deleted"] >= 1
    assert session.query(MuseumObject).filter_by(qid="Q99").count() == 0
    # 子行无孤儿
    kept_obj_ids = {oid for (oid,) in session.query(MuseumObject.id)}
    for model, col in (
        (ObjectImage, ObjectImage.object_id),
        (ObjectContentSection, ObjectContentSection.object_id),
        (ObjectSuggestedQuestion, ObjectSuggestedQuestion.object_id),
        (ObjectEmbedding, ObjectEmbedding.object_id),
    ):
        for (oid,) in session.query(col):
            assert oid in kept_obj_ids, f"{model.__name__} 留下孤儿行"
    assert session.query(MuseumObject).filter_by(qid="Q1").count() == 1  # 金样本健在
    assert out["after"] == out["before"] - out["deleted"]
