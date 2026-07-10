# tests/integration/test_audio_endpoint.py
"""guide 音频懒生成端点(点播放触发):无 key→生成+落库+返 URL;有 key→秒返不重生成。"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.main import app
from app.models.artist import Artist
from app.models.content import (
    CategorySection,
    ObjectContentSection,
    ObjectSuggestedQuestion,
    SectionType,
)
from app.models.museum import Museum
from app.models.museum_object import MuseumObject, ObjectImage
from app.services.object_importer import upsert_museum, upsert_object


class FakeStorage:
    def __init__(self):
        self.objects = {}

    def put(self, key, data, content_type):
        self.objects[key] = data

    def exists(self, key):
        return key in self.objects

    def public_url(self, key):
        return f"https://cdn.test/{key}"


@pytest.fixture()
def client(monkeypatch):
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
            Artist.__table__,
        ],
    )
    s = sessionmaker(bind=engine)()
    m = upsert_museum(s, {"slug": "orsay", "name_en": "Orsay"})
    obj = upsert_object(
        s,
        m.id,
        {
            "qid": "Q1",
            "title_en": "A",
            "category": "painting",
            "image": "http://x/a.jpg",
            "attributes": {},
        },
    )
    s.add(
        ObjectContentSection(
            object_id=obj.id,
            language="zh",
            section_code="guide",
            body="讲解正文",
            status="published",
        )
    )
    s.add(
        ObjectContentSection(
            object_id=obj.id,
            language="zh",
            section_code="background",
            body="背景段正文",
            status="published",
        )
    )
    s.add(
        ObjectSuggestedQuestion(
            object_id=obj.id,
            language="zh",
            sort=1,
            question="为什么这幅画有名？",
            answer="因为它的光线效果开创了先河。",
            status="published",
        )
    )
    s.add(Artist(qid="Q296", name_en="Manet", bio={"zh": "马奈是法国画家，生于巴黎。"}))
    obj.attributes = {"artist_qid": "Q296"}
    s.commit()

    import app.services.enrichment.lazy_audio as la

    monkeypatch.setattr(la, "get_object_storage", lambda: FakeStorage())

    app.dependency_overrides[get_db] = lambda: (yield s)
    yield TestClient(app)
    app.dependency_overrides.pop(get_db, None)
    s.close()


def test_audio_endpoint_generates_then_caches(client, monkeypatch):
    import app.services.enrichment.lazy_audio as la

    calls = {"tts": 0}

    def fake_tts(text, language):
        calls["tts"] += 1
        return b"MP3BYTES"

    monkeypatch.setattr(la, "_synth", fake_tts)

    r1 = client.get("/api/v1/museums/orsay/objects/Q1/audio?language=zh&section=guide")
    assert r1.status_code == 200 and r1.json()["audio_url"]
    assert calls["tts"] == 1

    r2 = client.get("/api/v1/museums/orsay/objects/Q1/audio?language=zh&section=guide")
    assert r2.status_code == 200
    assert calls["tts"] == 1  # 第二次走缓存,不重生成


def test_audio_endpoint_404_when_no_guide_text(client):
    r = client.get("/api/v1/museums/orsay/objects/Q1/audio?language=de&section=guide")
    assert r.status_code == 404


def test_audio_endpoint_503_on_tts_failure(client, monkeypatch):
    import app.services.enrichment.lazy_audio as la
    from app.services.content_repo import get_section_audio_key

    def boom(text, language):
        raise RuntimeError("tts down")

    monkeypatch.setattr(la, "_synth", boom)

    r = client.get("/api/v1/museums/orsay/objects/Q1/audio?language=zh&section=guide")
    assert r.status_code == 503

    from app.core.database import get_db as _get_db

    db = next(iter(app.dependency_overrides[_get_db]()))
    assert get_section_audio_key(db, "Q1", "zh", "guide") is None


def test_audio_busy_when_section_locked(monkeypatch):
    # 段级锁:同段同语言已在生成(锁活)→ 返 busy,不重复调 TTS
    from datetime import datetime, timezone

    import app.services.enrichment.lazy_audio as la

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
            Artist.__table__,
        ],
    )
    s = sessionmaker(bind=engine)()
    m = upsert_museum(s, {"slug": "orsay", "name_en": "Orsay"})
    obj = upsert_object(s, m.id, {"qid": "Q1", "title_en": "A", "category": "painting"})
    s.add(
        ObjectContentSection(
            object_id=obj.id,
            language="zh",
            section_code="guide",
            body="讲解",
            status="published",
        )
    )
    obj.attributes = {
        "audio_locks": {"zh:guide": datetime.now(timezone.utc).isoformat()}
    }
    s.commit()

    monkeypatch.setattr(la, "get_object_storage", lambda: FakeStorage())
    calls = {"tts": 0}
    monkeypatch.setattr(
        la, "_synth", lambda t, l: calls.__setitem__("tts", calls["tts"] + 1) or b"X"
    )

    url, status = la.get_or_make_audio_url(s, "orsay", "Q1", "zh", "guide")
    assert status == "busy"
    assert calls["tts"] == 0  # 锁活 → 不生成
    s.close()


def test_audio_endpoint_deep_section(client, monkeypatch):
    # Phase2:深度模块段(background 等)也能点播放懒生成音频
    import app.services.enrichment.lazy_audio as la

    monkeypatch.setattr(la, "_synth", lambda t, l: b"MP3")
    r = client.get(
        "/api/v1/museums/orsay/objects/Q1/audio?language=zh&section=background"
    )
    assert r.status_code == 200 and r.json()["audio_url"]


def test_audio_endpoint_deep_section_404_when_missing(client):
    r = client.get(
        "/api/v1/museums/orsay/objects/Q1/audio?language=zh&section=analysis"
    )
    assert r.status_code == 404  # analysis 段无已发布正文


def test_audio_endpoint_qa(client, monkeypatch):
    # QA 音频:问+答连念,懒生成,audio_key 落行
    import app.services.enrichment.lazy_audio as la

    seen = {}

    def fake(t, l):
        seen["text"] = t
        return b"MP3"

    monkeypatch.setattr(la, "_synth", fake)
    r = client.get(
        "/api/v1/museums/orsay/objects/Q1/audio?language=zh&section=qa&qa_sort=1"
    )
    assert r.status_code == 200 and r.json()["audio_url"]
    assert "为什么" in seen["text"] and "因为" in seen["text"]  # 问+答连念
    r2 = client.get(
        "/api/v1/museums/orsay/objects/Q1/audio?language=zh&section=qa&qa_sort=1"
    )
    assert r2.status_code == 200  # 秒回缓存


def test_audio_endpoint_artist_bio_shared(client, monkeypatch):
    # 作者介绍音频:按作者共享(key 按 artist qid,非藏品 qid)
    import app.services.enrichment.lazy_audio as la

    monkeypatch.setattr(la, "_synth", lambda t, l: b"MP3")
    r = client.get(
        "/api/v1/museums/orsay/objects/Q1/audio?language=zh&section=artist_bio"
    )
    assert r.status_code == 200
    assert "/artist/Q296/" in r.json()["audio_url"]  # 作者维度 key,同作者共享


def test_bio_audio_regenerated_after_bio_change(client, monkeypatch):
    # bio 音频失效链:改 bio 后再点播放应重新生成(不是旧音频)
    import app.services.enrichment.lazy_audio as la

    calls = {"n": 0}
    monkeypatch.setattr(
        la, "_synth", lambda t, l: calls.__setitem__("n", calls["n"] + 1) or b"M"
    )
    client.get("/api/v1/museums/orsay/objects/Q1/audio?language=zh&section=artist_bio")
    assert calls["n"] == 1
    client.get("/api/v1/museums/orsay/objects/Q1/audio?language=zh&section=artist_bio")
    assert calls["n"] == 1  # 缓存
