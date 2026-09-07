"""pilot_snapshot 的纯函数部分。

DB 部分靠 staging 实证（破坏→回滚→verify 归零，跑了两轮 + 一次幂等重跑），
这里只锁住两个**真的出过 bug** 的转换函数：
  - _pg 漏掉某个 JSONB 列 → `can't adapt type 'dict'`，只在真回滚那一刻炸
  - _j  datetime 不转 → json.dump 直接失败
"""

import importlib.util
from datetime import datetime
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "pilot_snapshot",
    Path(__file__).resolve().parents[3] / "scripts" / "pilot_snapshot.py",
)
ps = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ps)


def test_pg_serializes_any_dict_or_list():
    # 按值类型判，不按列名清单 —— 列名清单会漏（bio_audio 就漏过）
    assert ps._pg({"zh": "a"}) == '{"zh": "a"}'
    assert ps._pg(["a", "b"]) == '["a", "b"]'
    assert ps._pg({}) == "{}"
    assert ps._pg([]) == "[]"


def test_pg_passes_through_scalars():
    for v in ("text", 1, 1.5, None, True):
        assert ps._pg(v) is v


def test_pg_keeps_non_ascii_readable():
    assert "库尔贝" in ps._pg({"zh": "库尔贝"})


def test_j_converts_datetime():
    assert ps._j(datetime(2026, 9, 7, 12, 0)) == "2026-09-07T12:00:00"
    assert ps._j("已经是字符串") == "已经是字符串"
    assert ps._j(None) is None


def test_column_lists_cover_audio_fields():
    # audio_key 不备份 = 回滚回不来音频（R2 文件还在，只差这个指针）
    assert "audio_key" in ps.SEC_COLS and "audio_engine" in ps.SEC_COLS
    assert "audio_key" in ps.QA_COLS
    assert "bio_audio" in ps.ART_COLS
