"""存量划线快照(spec §6):sha 必须与 DB 正文逐字节对应,以后才能判「正文没变」。"""

import gzip
import hashlib
import json
from datetime import datetime

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
from app.models.museum_object import MuseumObject
from scripts import snapshot_grounding_baseline as snap


@pytest.fixture()
def db():
    e = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(
        bind=e,
        tables=[
            Museum.__table__,
            MuseumObject.__table__,
            SectionType.__table__,
            CategorySection.__table__,
            ObjectContentSection.__table__,
            ObjectSuggestedQuestion.__table__,
        ],
    )
    s = sessionmaker(bind=e)()
    yield s
    s.close()


def test_sha_is_exact_bytes_no_strip():
    assert snap.sha(" a\n") == hashlib.sha256(" a\n".encode("utf-8")).hexdigest()
    assert snap.sha(None) is None


def test_snapshot_only_published_en_sections_and_published_questions(db):
    m = Museum(
        slug="m", name_en="M", description_i18n={"en": "Intro.", "fr": "Intro FR."}
    )
    db.add(m)
    db.commit()
    o = MuseumObject(museum_id=m.id, qid="Q1")
    db.add(o)
    db.commit()
    db.add_all(
        [
            ObjectContentSection(
                object_id=o.id,
                language="en",
                section_code="guide",
                body="G.",
                status="published",
                generated_at=datetime(2026, 10, 1),
            ),
            ObjectContentSection(
                object_id=o.id,
                language="en",
                section_code="facts",
                body="F.",
                status="needs_review",
            ),
            ObjectContentSection(
                object_id=o.id,
                language="fr",
                section_code="guide",
                body="G fr.",
                status="published",
            ),
            ObjectSuggestedQuestion(
                object_id=o.id,
                language="en",
                sort=1,
                question="q",
                answer="A.",
                status="published",
            ),
            ObjectSuggestedQuestion(
                object_id=o.id,
                language="en",
                sort=2,
                question="q2",
                answer="B.",
                status="needs_review",
            ),
        ]
    )
    db.commit()
    s = snap.build_snapshot(db)
    assert [(r["qid"], r["section"]) for r in s["sections"]] == [("Q1", "guide")]
    assert s["sections"][0]["sha"] == snap.sha("G.")
    assert s["sections"][0]["generated_at"] == "2026-10-01T00:00:00"
    assert [(r["qid"], r["language"], r["sort"]) for r in s["questions"]] == [
        ("Q1", "en", 1)
    ]
    assert s["questions"][0]["sha"] == snap.sha("q\nA.")
    assert s["museums"] == [
        {"slug": "m", "sha": {"en": snap.sha("Intro."), "fr": snap.sha("Intro FR.")}}
    ]


def test_cli_writes_gzip_json(db, tmp_path, monkeypatch):
    monkeypatch.setattr(snap, "_session", lambda: db)
    out = tmp_path / "s.json.gz"
    assert snap.main(["--out", str(out)]) == 0
    doc = json.loads(gzip.decompress(out.read_bytes()))
    assert set(doc) >= {"at", "sections", "questions", "museums"}
