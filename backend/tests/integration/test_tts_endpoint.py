"""`POST /api/v1/content/tts/generate` 的 ad-hoc 模式。

⚠️ **section 模式已于 2026-09-20 安全审计退役**，原先这里的三条用例
（`generates_and_persists` / `reuses_without_tts` / `unknown_qid_returns_404`）
随之移除。

值得记一笔的是那三条**当时在断言的正是那个漏洞的行为** ——
`test_section_mode_generates_and_persists` 提交 `{"text": "hello", "qid": "Q1"}`
然后断言 `"hello"` 被合成并落库成 Q1 的官方音频。测试是绿的、写得也认真，
但它把"调用方提交的自由文本可以成为藏品的官方音频"当成了**期望行为**。
🔑 测试只能钉住你已经想到的错法；它钉不住"这个行为本身就不该存在"。

section 模式现在返 410 的断言在 `tests/unit/api/test_retired_cost_holes.py`，
与其余退役端点放在一起。本文件只剩 ad-hoc 模式 —— 它是**要保留**的那一半，
也是"退役没有误伤"的那一格。
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.api.v1.endpoints.content as content_ep
from app.core.database import Base
from app.main import app
from app.models.content import ObjectContentSection
from app.models.museum import Museum
from app.models.museum_object import MuseumObject, ObjectImage
from app.services.tts_service import get_tts_service


class FakeTTS:
    def __init__(self):
        self.calls = 0

    async def generate_audio(self, text, language="en", voice=None, speed=1.0):
        self.calls += 1
        return {
            "audio_data": b"MP3BYTES",
            "content_type": "audio/mpeg",
            "duration_estimate": 1.0,
            "voice": "x",
            "language": language,
            "text_hash": "h",
            "size_bytes": 8,
        }


@pytest.fixture()
def ctx(monkeypatch):
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
        ],
    )
    Session = sessionmaker(bind=engine)

    fake_tts = FakeTTS()
    # 端点用 SessionLocal()（非 Depends(get_db)），故替身工厂。
    # 这条用例考的是**出不出声**;付费墙另有 test_audio_paywall.py 专测,
    # 闸门在此 no-op,否则要建用户+令牌,把测试意图淹没。
    monkeypatch.setattr(content_ep, "_require_tts_access", lambda *a, **k: "test-user")
    monkeypatch.setattr(content_ep, "SessionLocal", Session)
    app.dependency_overrides[get_tts_service] = lambda: fake_tts
    client = TestClient(app)
    yield client, fake_tts
    app.dependency_overrides.clear()


def test_ad_hoc_mode_streams_audio(ctx):
    client, fake_tts = ctx
    r = client.post(
        "/api/v1/content/tts/generate", json={"text": "hi", "language": "en"}
    )
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("audio/")
    assert r.content == b"MP3BYTES"
    assert fake_tts.calls == 1


def test_section_mode_is_retired_without_touching_tts(ctx):
    """与上一条配对：退役只砍 section 模式，ad-hoc 一分不少地留着。

    同时确认 410 发生在 TTS **之前** —— `fake_tts.calls` 必须是 0。
    """
    client, fake_tts = ctx
    r = client.post(
        "/api/v1/content/tts/generate",
        json={
            "text": "hello",
            "language": "en",
            "qid": "Q1",
            "section_code": "overview",
        },
    )
    assert r.status_code == 410
    assert fake_tts.calls == 0
