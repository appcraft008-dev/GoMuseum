# tests/unit/models/test_step1_models.py
import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.content import CategorySection, ObjectContentSection, SectionType
from app.models.museum import Museum
from app.models.museum_object import MuseumObject, ObjectImage


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
        ],
    )
    Session = sessionmaker(bind=engine)
    s = Session()
    yield s
    s.close()


def test_object_with_attributes_and_image(session):
    m = Museum(slug="orsay", name_en="Musée d'Orsay")
    session.add(m)
    session.flush()
    obj = MuseumObject(
        museum_id=m.id,
        qid="Q12418",
        category="painting",
        title_en="Mona Lisa",
        attributes={"material": "oil on panel"},
    )
    session.add(obj)
    session.flush()
    session.add(
        ObjectImage(object_id=obj.id, role="primary", source_url="http://x/a.jpg")
    )
    session.commit()
    got = session.query(MuseumObject).filter_by(qid="Q12418").one()
    assert got.attributes["material"] == "oil on panel"


def test_qid_unique(session):
    m = Museum(slug="orsay")
    session.add(m)
    session.flush()
    session.add(MuseumObject(museum_id=m.id, qid="Q1"))
    session.commit()
    session.add(MuseumObject(museum_id=m.id, qid="Q1"))
    with pytest.raises(IntegrityError):
        session.commit()


def test_content_section_unique_per_obj_lang_section(session):
    m = Museum(slug="orsay")
    session.add(m)
    session.flush()
    obj = MuseumObject(museum_id=m.id, qid="Q2")
    session.add(obj)
    session.flush()
    session.add(SectionType(code="overview", label_en="Overview"))
    session.flush()
    session.add(
        ObjectContentSection(
            object_id=obj.id, language="en", section_code="overview", body="a"
        )
    )
    session.commit()
    session.add(
        ObjectContentSection(
            object_id=obj.id, language="en", section_code="overview", body="b"
        )
    )
    with pytest.raises(IntegrityError):
        session.commit()
