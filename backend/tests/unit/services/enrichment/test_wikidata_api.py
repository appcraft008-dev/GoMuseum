import threading
import time

import pytest

from app.services.enrichment import wikidata_api as wa


class _Resp:
    def __init__(self, status=200, body=None, headers=None):
        self.status_code = status
        self._body = body if body is not None else {}
        self.headers = headers or {}

    def json(self):
        return self._body

    def raise_for_status(self):
        if self.status_code >= 400:
            raise wa.requests.HTTPError(str(self.status_code))


def _seq(*resps):
    calls = []
    it = iter(resps)

    def get(url, params=None, headers=None, timeout=None):
        calls.append(params)
        return next(it)

    return get, calls


def _ok(ents):
    return _Resp(body={"entities": ents})


def test_sends_props_languages_maxlag_and_user_agent():
    seen = {}

    def get(url, params=None, headers=None, timeout=None):
        seen.update(url=url, params=params, headers=headers, timeout=timeout)
        return _ok({"Q1": {"id": "Q1"}})

    wa.get_entities(["Q1"], props="labels", languages=["en", "zh"], http_get=get)
    p = seen["params"]
    assert seen["url"] == "https://www.wikidata.org/w/api.php"
    assert p["action"] == "wbgetentities" and p["format"] == "json"
    assert p["ids"] == "Q1" and p["props"] == "labels" and p["languages"] == "en|zh"
    # 不带 maxlag:它跟的是 WDQS 复制延迟(10-10 实测 7.9s/23.9s),设 5 会让只读请求
    # 恰在 WDQS 慢时被全部拒掉 —— 正是本次要绕开的场景。maxlag 是给批量写入的机器人用的。
    assert "maxlag" not in p and seen["timeout"] == 10
    assert seen["headers"]["User-Agent"] == wa._wd.USER_AGENT


def test_batches_ids_by_50_and_drops_missing():
    sizes = []

    def get(url, params=None, headers=None, timeout=None):
        ids = params["ids"].split("|")
        sizes.append(len(ids))
        ents = {q: {"id": q} for q in ids}
        ents[ids[0]] = {"id": ids[0], "missing": ""}
        return _ok(ents)

    out = wa.get_entities(
        [f"Q{i}" for i in range(1, 121)], props="labels", http_get=get
    )
    assert sizes == [50, 50, 20]
    assert "Q1" not in out and "Q51" not in out and "Q101" not in out
    assert len(out) == 117


def test_429_retry_after_then_success():
    waits = []
    get, calls = _seq(_Resp(429, headers={"Retry-After": "3"}), _ok({"Q1": {}}))
    assert wa.get_entities(
        ["Q1"], props="claims", http_get=get, sleep=waits.append
    ) == {"Q1": {}}
    assert waits == [3.0] and len(calls) == 2


def test_maxlag_is_http_200_error_body_and_retried():
    waits = []
    get, calls = _seq(
        _Resp(body={"error": {"code": "maxlag", "info": "lagged"}}), _ok({"Q1": {}})
    )
    assert wa.get_entities(
        ["Q1"], props="claims", http_get=get, sleep=waits.append
    ) == {"Q1": {}}
    assert waits == [1.0] and len(calls) == 2


def test_other_error_body_raises_without_retry():
    get, calls = _seq(_Resp(body={"error": {"code": "toomanyvalues", "info": "x"}}))
    with pytest.raises(wa.WikidataApiError):
        wa.get_entities(["Q1"], props="claims", http_get=get, sleep=lambda s: None)
    assert len(calls) == 1


def test_other_4xx_raises_wikidata_error_without_retry():
    get, calls = _seq(_Resp(400))
    with pytest.raises(wa.WikidataApiError):
        wa.get_entities(["Q1"], props="claims", http_get=get, sleep=lambda s: None)
    assert len(calls) == 1


def test_200_without_entities_raises():
    get, _ = _seq(_Resp(body={"success": 1}))
    with pytest.raises(wa.WikidataApiError):
        wa.get_entities(["Q1"], props="claims", http_get=get, sleep=lambda s: None)


def test_gives_up_after_three_tries_with_backoff():
    waits = []
    get, calls = _seq(_Resp(503), _Resp(503), _Resp(503))
    with pytest.raises(wa.WikidataApiError):
        wa.get_entities(["Q1"], props="claims", http_get=get, sleep=waits.append)
    assert len(calls) == 3 and waits == [1.0, 2.0]


def test_timeout_is_retried():
    n = [0]

    def get(url, params=None, headers=None, timeout=None):
        n[0] += 1
        if n[0] == 1:
            raise wa.requests.Timeout()
        return _ok({})

    assert (
        wa.get_entities(["Q1"], props="claims", http_get=get, sleep=lambda s: None)
        == {}
    )
    assert n[0] == 2


def test_at_most_two_requests_in_flight():
    lock = threading.Lock()
    cur, peak = [0], [0]

    def get(url, params=None, headers=None, timeout=None):
        with lock:
            cur[0] += 1
            peak[0] = max(peak[0], cur[0])
        time.sleep(0.05)
        with lock:
            cur[0] -= 1
        return _ok({})

    ts = [
        threading.Thread(
            target=wa.get_entities,
            args=(["Q1"],),
            kwargs={"props": "claims", "http_get": get},
        )
        for _ in range(6)
    ]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    assert peak[0] == 2


def _st(value, rank="normal", snaktype="value", dtype="wikibase-entityid"):
    snak = {"snaktype": snaktype, "property": "P1"}
    if snaktype == "value":
        if dtype == "time":
            snak["datavalue"] = {"value": {"time": value}, "type": "time"}
        else:
            snak["datavalue"] = {
                "value": {"entity-type": "item", "id": value},
                "type": "wikibase-entityid",
            }
    return {"mainsnak": snak, "rank": rank}


def test_best_statements_preferred_only_if_any():
    e = {
        "claims": {
            "P1": [_st("Q1"), _st("Q2", rank="preferred"), _st("Q3", rank="deprecated")]
        }
    }
    assert [wa.entity_id(s) for s in wa.best_statements(e, "P1")] == ["Q2"]


def test_best_statements_normal_when_no_preferred_and_excludes_deprecated():
    e = {"claims": {"P1": [_st("Q1"), _st("Q3", rank="deprecated"), _st("Q4")]}}
    assert [wa.entity_id(s) for s in wa.best_statements(e, "P1")] == ["Q1", "Q4"]


def test_best_statements_drops_unknown_and_no_value():
    e = {
        "claims": {
            "P1": [
                _st(None, snaktype="somevalue"),
                _st(None, snaktype="novalue"),
                _st("Q5"),
            ]
        }
    }
    assert [wa.entity_id(s) for s in wa.best_statements(e, "P1")] == ["Q5"]
    assert wa.best_statements({}, "P1") == []


def test_time_value_and_entity_id_by_type():
    assert (
        wa.time_value(_st("+1483-04-06T00:00:00Z", dtype="time"))
        == "+1483-04-06T00:00:00Z"
    )
    assert wa.entity_id(_st("+1483-04-06T00:00:00Z", dtype="time")) is None
    assert wa.time_value(_st("Q1")) is None


def test_labels_of_maps_and_skips_empty():
    def fetch(ids, *, props, languages=None):
        assert props == "labels" and languages == ["en"]
        return {
            "Q1": {"labels": {"en": {"language": "en", "value": "France"}}},
            "Q2": {},
        }

    assert wa.labels_of(["Q1", "Q2"], ["en"], fetch) == {
        "Q1": {"en": "France"},
        "Q2": {},
    }
    assert wa.labels_of([], ["en"], fetch) == {}


def test_retry_after_capped_so_first_screen_never_stalls():
    """终审 #2:服务器给的 Retry-After 不设上限会把用户首屏一起卡住。"""
    waits = []
    get, _ = _seq(_Resp(429, headers={"Retry-After": "600"}), _ok({"Q1": {}}))
    wa.get_entities(["Q1"], props="claims", http_get=get, sleep=waits.append)
    assert waits == [5.0]


def test_non_json_200_is_retried():
    """终审 #3:代理/错误页返回 200 + HTML 是瞬时故障,要重试而不是直接丢资料。"""

    class _Html(_Resp):
        def json(self):
            raise ValueError("Expecting value")

    waits = []
    get, calls = _seq(_Html(), _ok({"Q1": {}}))
    assert wa.get_entities(
        ["Q1"], props="claims", http_get=get, sleep=waits.append
    ) == {"Q1": {}}
    assert len(calls) == 2


def _page(revs):
    return _Resp(body={"query": {"pages": {"1": {"title": "Q1", "revisions": revs}}}})


def test_recent_revisions_newest_first_with_user_flags():
    """真实形状(Q18572451 10-19):临时账号带 temp 键、名字以 ~ 开头。"""
    revs = [
        {"revid": 3, "user": "~2026-50953-52", "temp": ""},
        {"revid": 2, "user": "Bot"},
    ]
    get, calls = _seq(_page(revs))
    assert wa.recent_revisions("Q1", http_get=get) == revs
    assert calls[0]["titles"] == "Q1" and calls[0]["rvprop"] == "ids|user|flags"


def test_entity_at_parses_main_slot_json():
    content = '{"id": "Q1", "claims": {"P170": []}}'
    get, calls = _seq(_page([{"slots": {"main": {"*": content}}}]))
    assert wa.entity_at(7, http_get=get) == {"id": "Q1", "claims": {"P170": []}}
    assert calls[0]["revids"] == 7


def test_entity_at_hidden_content_is_none():
    get, _ = _seq(_page([{"slots": {"main": {"texthidden": ""}}}]))
    assert wa.entity_at(7, http_get=get) is None


def test_untrusted_editor_temp_ip_or_hidden():
    assert wa.untrusted_editor({"user": "~2026-1-1", "temp": ""})
    assert wa.untrusted_editor({"user": "1.2.3.4", "anon": ""})
    assert wa.untrusted_editor({"userhidden": ""})
    assert not wa.untrusted_editor({"user": "Shonagon"})
