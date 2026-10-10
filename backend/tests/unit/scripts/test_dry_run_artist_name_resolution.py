"""dry-run 脚本的 _scan:批量跑一整个馆时,单件解析异常不该中断整个扫描。"""

from scripts.dry_run_artist_name_resolution import _scan


class _FakeObj:
    def __init__(self, qid, artist_en, attributes=None):
        self.qid = qid
        self.artist_en = artist_en
        self.attributes = attributes or {}


def test_one_resolve_error_does_not_stop_the_rest_of_the_scan():
    objs = [
        _FakeObj("joconde-1", "RENOIR Pierre Auguste"),
        _FakeObj("joconde-2", "SOUTINE Chaïm"),  # 这件解析会抛异常
        _FakeObj("joconde-3", "UTRILLO Maurice"),
    ]

    def resolve(name):
        if name == "SOUTINE Chaïm":
            raise ConnectionError("Wikidata 超时")
        return "Q39931" if "RENOIR" in name else "Q108301"

    counts = _scan(objs, resolve=resolve)

    assert counts == {
        "resolved": 2,
        "abstained": 0,
        "errored": 1,
        "skipped_has_aqid": 0,
        "skipped_qid_format": 0,
    }


def test_skips_objects_with_existing_artist_qid_or_wikidata_qid():
    objs = [
        _FakeObj("joconde-1", "RENOIR Pierre Auguste", {"artist_qid": "Q39931"}),
        _FakeObj("Q999", "Some Name"),
    ]

    def resolve_should_not_be_called(name):
        raise AssertionError("已有 artist_qid 或 Wikidata qid 的件不该走解析")

    counts = _scan(objs, resolve=resolve_should_not_be_called)

    assert counts["skipped_has_aqid"] == 1
    assert counts["skipped_qid_format"] == 1
    assert counts["resolved"] == 0
    assert counts["abstained"] == 0


def test_sleep_is_called_even_when_resolve_raises():
    """限速不能因为异常被跳过——异常多的时候更不该打更快。"""
    sleeps = []
    objs = [_FakeObj("joconde-1", "SOUTINE Chaïm")]

    def resolve(name):
        raise ConnectionError("boom")

    _scan(objs, resolve=resolve, sleep=sleeps.append)

    assert len(sleeps) == 1
