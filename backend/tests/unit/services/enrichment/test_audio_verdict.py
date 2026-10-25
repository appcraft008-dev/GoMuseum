"""灌入端核验生成侧判定的护栏(契约「音频批量生产与灌入」⑫)。

⚠️ **反样本不能省。** 只测"合格的能通过"的话,把 verdict_problem 写成
`return None` 也能过测 —— 而那正好等于没装护栏。
"""

import hashlib

import pytest

from app.services.enrichment.audio_verdict import load_verdicts, verdict_problem

DATA = b"pretend-this-is-an-mp3" * 100
MD5 = hashlib.md5(DATA).hexdigest()


GOOD = {"ok": True, "md5": MD5, "pipeline": "ea1c0bc3"}


def test_good_clip_passes():
    """正样本:判定合格、md5 相符、带管线版本 → 放行。"""
    assert verdict_problem({"a.mp3": GOOD}, "a.mp3", DATA) is None


def test_gate_failed_clip_is_refused():
    """反样本①:生成侧判定 ok=false —— 漏进 prod 那条正是这个形态。"""
    v = {"a.mp3": {"ok": False, "sharp": 231.0, "consist": 0.99, "md5": MD5}}
    assert "gate_failed" in (verdict_problem(v, "a.mp3", DATA) or "")


def test_unknown_clip_is_refused():
    """反样本②:文件在目录里但判定记录没有 —— 拷错目录 / 别批残留。"""
    assert "no_verdict" in (verdict_problem({}, "a.mp3", DATA) or "")


def test_content_mismatch_is_refused():
    """反样本③:内容与判定时的 md5 不符 —— 传输损坏或文件被换过。"""
    v = {"a.mp3": {**GOOD, "md5": hashlib.md5(b"other").hexdigest()}}
    assert "md5_mismatch" in (verdict_problem(v, "a.mp3", DATA) or "")


def test_old_copy_record_is_refused():
    """反样本④:生成机旧副本产的记录长这样(ok 但无 md5/pipeline)——
    2026-10-19 起 535 条就是这个形态灌进去的,线上响度极差 12.1dB。"""
    v = {"a.mp3": {"ok": True, "sharp": 120.0, "atempo": 0.9}}
    assert "unverified_pipeline" in (verdict_problem(v, "a.mp3", DATA) or "")


def test_md5_without_pipeline_is_refused():
    """反样本⑤:有 md5 没管线版本 —— 不是 start_run.sh 起的(直接调了 run_chunked)。"""
    v = {"a.mp3": {"ok": True, "md5": MD5}}
    assert "unverified_pipeline" in (verdict_problem(v, "a.mp3", DATA) or "")


def test_legacy_escape_hatch_must_be_explicit():
    """重灌老批次:显式 allow_legacy 才放行,且 md5 不符仍然拦。"""
    assert (
        verdict_problem({"a.mp3": {"ok": True}}, "a.mp3", DATA, allow_legacy=True)
        is None
    )
    bad = {"a.mp3": {"ok": True, "md5": hashlib.md5(b"other").hexdigest()}}
    assert "md5_mismatch" in (
        verdict_problem(bad, "a.mp3", DATA, allow_legacy=True) or ""
    )


def test_apply_without_state_file_is_refused(tmp_path):
    """--apply 且没有 _state.json → 报错退出,不许悄悄降级成不校验。"""
    with pytest.raises(SystemExit):
        load_verdicts(tmp_path, apply=True, allow_unverified=False)


def test_dry_run_without_state_file_is_tolerated(tmp_path):
    """dry-run 不写库,允许没有判定文件(否则连看一眼都做不到)。"""
    assert load_verdicts(tmp_path, apply=False, allow_unverified=False) is None


def test_escape_hatch_must_be_explicit(tmp_path):
    """外部引擎产出确实没有该文件时,必须显式开逃生口才放行。"""
    assert load_verdicts(tmp_path, apply=True, allow_unverified=True) is None


def test_state_file_is_read_when_present(tmp_path):
    (tmp_path / "_state.json").write_text('{"a.mp3": {"ok": true}}')
    assert load_verdicts(tmp_path, apply=True, allow_unverified=False) == {
        "a.mp3": {"ok": True}
    }
