"""外部生成音频的灌入:验 → 传 → 落库。

最要紧的两条:不过闸绝不覆盖旧版本(替换不可逆),以及重跑幂等
(生成机会重传,不能每次都重新上传+改 key)。
"""

import hashlib
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
    """旧版本时长从 R2 对象大小估,不必下载内容。

    ⚠️ 这个测试原来写成 `estimate_duration_sec(n if isinstance(n, bytes) else _audio(60))`
    —— isinstance 恒为假,于是**永远在测 bytes 路径**,恰好绕开了它声称要测的
    `storage.size()` 返回 int 这条路。结果替换路径首次真跑就炸(TypeError: object of
    type 'int' has no len())。**测试里的条件分支若绕开被测路径,测试就是假的。**
    """
    from app.services.enrichment.audio_quality import estimate_duration_sec

    n_bytes = len(_audio(60))
    assert isinstance(n_bytes, int)
    assert abs(estimate_duration_sec(n_bytes) - 60) < 0.1, "字节数(int)必须能直接估时长"
    assert abs(estimate_duration_sec(_audio(60)) - 60) < 0.1, "音频字节同样要支持"


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


def _run_main(db_session, tmp_path, *extra, engine="voxcpm2", verdict=True):
    """跑 CLI 的 main(),把 DB/存储换成测试替身。返回 (stats 输出, 写入的 key 列表)."""
    import audio_ingest_cli as cli

    written: list[str] = []

    class _Storage:
        """size() 返回 int —— 和真实 R2 一致(HEAD 拿 ContentLength)。

        ⚠️ 起初这里写的是 `return None`,于是替换路径的偏差检查整段被跳过,
        我新加的两个测试同样没能挡住那个 int/bytes bug。**替身的返回类型
        必须跟真实实现一致**,否则测的是一条现实中不存在的路径。
        """

        def size(self, key):
            return len(_audio(60)) if key else None

        def put(self, key, data, ct):
            written.append(key)

    s, obj = db_session
    monkey = pytest.MonkeyPatch()
    monkey.setattr(cli, "SessionLocal", lambda: s)
    monkey.setattr(cli, "get_object_storage", lambda: _Storage())
    jobs = tmp_path / "jobs.json"
    jobs.write_text(json.dumps([{"qid": "Q1", "language": "zh", "section": "guide"}]))
    data = _audio(60)
    (tmp_path / "Q1__zh__guide.mp3").write_bytes(data)
    # 生成侧的合格判定必须随文件一起交付(契约 音频节⑫);缺它 --apply 会被拒。
    # 真实目录里本来就有这个文件,测试替身也得有,否则测的是现实中不存在的路径。
    if verdict is not None:
        (tmp_path / "_state.json").write_text(
            json.dumps(
                {
                    "Q1__zh__guide.mp3": {
                        "ok": verdict,
                        "md5": hashlib.md5(data).hexdigest(),
                        "sharp": 120.0,
                        "consist": 0.99,
                    }
                }
            )
        )
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


def test_gate_failed_clip_is_not_written(db_with_existing, tmp_path, capsys):
    """契约 音频节⑫:生成侧判定不合格的产物,即使躺在灌入目录里也不许落库。

    这条是 CLI 全链路的,不是纯函数级 —— 2026-09-04 的实测教训:
    我先只测了 `verdict_problem` 这个纯函数,接线对不对完全没测到,
    是 CI 里两个既有测试撞上 SystemExit 才证明守卫真的接上了。
    """
    written = _run_main(db_with_existing, tmp_path, "--force", verdict=False)
    assert written == [], "未过闸的产物不该被写入"
    out = capsys.readouterr().out
    assert "unverified" in out, "拒绝原因要单独计数,不能混进质量闸的 rejected"


def test_apply_without_state_file_is_refused(db_with_existing, tmp_path):
    """没有 _state.json 就 --apply → 报错退出,不许悄悄降级成不校验。"""
    with pytest.raises(SystemExit):
        _run_main(db_with_existing, tmp_path, verdict=None)
