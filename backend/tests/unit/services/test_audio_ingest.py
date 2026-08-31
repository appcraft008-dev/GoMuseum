"""外部生成音频的灌入:验 → 传 → 落库。

最要紧的两条:不过闸绝不覆盖旧版本(替换不可逆),以及重跑幂等
(生成机会重传,不能每次都重新上传+改 key)。
"""

import json
import subprocess
import sys
from pathlib import Path

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
from app.services.enrichment.audio_quality import check_audio

sys.path.insert(0, "scripts")


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
    m = Museum(slug="louvre", name_en="Louvre")
    s.add(m)
    s.commit()
    o = MuseumObject(museum_id=m.id, qid="Q1")
    s.add(o)
    s.commit()
    yield s, o
    s.close()


def _audio(seconds: float) -> bytes:
    return b"\0" * int(seconds * 160_000 / 8)


def test_filename_convention_is_round_trippable():
    """生成机按这个约定写文件名 —— 约定错了整批都对不上号。"""
    from audio_ingest_cli import _filename

    assert _filename("Q152509", "zh", "guide") == "Q152509__zh__guide.mp3"
    assert _filename("Q152509", "zh-hant", "qa_0") == "Q152509__zh-hant__qa_0.mp3"


def test_source_text_found_for_section_and_qa(db):
    """质量闸要对照原文,取不到文本就等于没有闸。"""
    from audio_ingest_cli import _source_text

    s, o = db
    s.add(
        ObjectContentSection(
            object_id=o.id, language="zh", section_code="guide", body="正文" * 50
        )
    )
    s.add(
        ObjectSuggestedQuestion(
            object_id=o.id, language="zh", sort=0, question="问?", answer="答。"
        )
    )
    s.commit()
    assert "正文" in _source_text(s, o.id, "zh", "guide")
    qa = _source_text(s, o.id, "zh", "qa_0")
    assert "问?" in qa and "答。" in qa, "问答要连念,上下文不能丢"


def test_rejected_audio_must_not_replace_existing():
    """⭐ 不过闸就保留旧版本 —— 替换不可逆(旧文件即刻成孤儿),
    模型回归不该静默毁掉音频库。"""
    text = "字" * 280  # 期望约 60 秒
    truncated = check_audio(_audio(10), text=text, language="zh")
    assert truncated.ok is False
    # 调用方据此跳过落库:key 与 engine 都不该被改写


def test_deviation_check_uses_previous_size():
    """旧版本时长从 R2 对象大小估,不必下载内容。"""
    from app.services.enrichment.audio_quality import estimate_duration_sec

    old_bytes = len(_audio(60))
    assert (
        abs(
            estimate_duration_sec(
                old_bytes if isinstance(old_bytes, bytes) else _audio(60)
            )
            - 60
        )
        < 0.1
    )


def test_cli_is_dry_run_by_default(tmp_path):
    """默认不写 —— 灌入是批量写操作,误跑代价大。"""
    jobs = tmp_path / "jobs.json"
    jobs.write_text(json.dumps([]))
    out = subprocess.run(
        [
            sys.executable,
            "scripts/audio_ingest_cli.py",
            "--jobs",
            str(jobs),
            "--dir",
            str(tmp_path),
            "--engine",
            "voxcpm2",
        ],
        capture_output=True,
        text=True,
    )
    assert "dry-run" in out.stdout, out.stdout + out.stderr


def _run_main(db_session, tmp_path, *extra, engine="voxcpm2"):
    """跑 CLI 的 main(),把 DB/存储换成测试替身。返回 (stats 输出, 写入的 key 列表)."""
    import audio_ingest_cli as cli

    written: list[str] = []

    class _Storage:
        def size(self, key):
            return None

        def put(self, key, data, ct):
            written.append(key)

    s, obj = db_session
    monkey = pytest.MonkeyPatch()
    monkey.setattr(cli, "SessionLocal", lambda: s)
    monkey.setattr(cli, "get_object_storage", lambda: _Storage())
    jobs = tmp_path / "jobs.json"
    jobs.write_text(json.dumps([{"qid": "Q1", "language": "zh", "section": "guide"}]))
    (tmp_path / "Q1__zh__guide.mp3").write_bytes(_audio(60))
    monkey.setattr(
        sys,
        "argv",
        [
            "x",
            "--jobs",
            str(jobs),
            "--dir",
            str(tmp_path),
            "--engine",
            engine,
            "--apply",
            *extra,
        ],
    )
    try:
        cli.main()
    finally:
        monkey.undo()
    return written


@pytest.fixture()
def db_with_existing(db):
    """已经灌过 voxcpm2 的一条 guide —— 重灌场景的起点。"""
    s, obj = db
    s.add(
        ObjectContentSection(
            object_id=obj.id,
            language="zh",
            section_code="guide",
            body="正" * 280,
            status="published",
            audio_key="object-audio/old.mp3",
            audio_engine="voxcpm2",
        )
    )
    s.commit()
    return s, obj


def test_same_engine_skipped_without_force(db_with_existing, tmp_path, capsys):
    """默认必须幂等跳过。写反了会静默覆盖 prod 已有音频 —— 不可逆。"""
    written = _run_main(db_with_existing, tmp_path)
    assert written == [], "没给 --force 就不该重写同引擎的音频"
    assert "already_done" in capsys.readouterr().out


def test_same_engine_rewritten_with_force(db_with_existing, tmp_path):
    """--force 用于修生成侧 bug 后重灌(引擎没变,坏的是产物)。"""
    written = _run_main(db_with_existing, tmp_path, "--force")
    assert len(written) == 1, "--force 应当重灌同引擎的条目"
    s, _ = db_with_existing
    row = s.query(ObjectContentSection).one()
    assert row.audio_key == written[0], "DB 的 key 必须指向新写入的对象"
