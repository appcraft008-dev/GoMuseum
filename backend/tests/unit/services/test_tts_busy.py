"""TTS 同时合成数(spec §7 T2):本进程同时合成达到 4 路记一条 tts_busy,每分钟最多一条。"""

import asyncio
import threading
import time

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.app_event import AppEvent
from app.services import tts_service as tts


@pytest.fixture(autouse=True)
def _reset(monkeypatch):
    monkeypatch.setattr(tts, "_busy_logged", float("-inf"))
    monkeypatch.setattr(tts, "_active", 0)


def test_note_busy_threshold_and_once_a_minute(monkeypatch):
    seen = []
    done = threading.Event()

    def log(n):
        seen.append(n)
        if len(seen) == 2:
            done.set()

    monkeypatch.setattr(tts, "_log_busy", log)
    assert tts._note_busy(3, now=100.0) is False
    assert tts._note_busy(4, now=100.0) is True
    assert tts._note_busy(6, now=159.9) is False
    assert tts._note_busy(5, now=160.0) is True
    assert done.wait(2) and sorted(seen) == [4, 5]


def test_note_busy_does_not_wait_for_the_db_write(monkeypatch):
    gate = threading.Event()
    # 模拟连接池耗尽时写库卡住
    monkeypatch.setattr(tts, "_log_busy", lambda n: gate.wait(5))
    t = time.monotonic()
    assert tts._note_busy(4, now=1000.0) is True
    assert time.monotonic() - t < 0.5
    gate.set()


def test_log_busy_writes_event():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(bind=engine, tables=[AppEvent.__table__])
    S = sessionmaker(bind=engine)
    tts._log_busy(4, session_factory=S)
    assert [e.props for e in S().query(AppEvent).filter_by(name="tts_busy")] == [
        {"active": 4}
    ]


def test_drain_counts_active_and_releases_on_error():
    seen = []

    def it():
        seen.append(tts._active)
        yield b"x"
        raise RuntimeError("boom")

    loop = asyncio.new_event_loop()
    try:
        tts._drain(loop, asyncio.Queue(), it, object())
    finally:
        loop.close()
    assert seen == [1] and tts._active == 0
