"""Wikidata Action API(wbgetentities)单实体读取 —— 生成流程专用。

spec 2026-10-10-wikidata-action-api:生成流程里「查一个实体的几项属性」原先走 WDQS SPARQL,
负载高时卡满 60s 超时并静默丢资料(10-10 抽样:多语标题 5/28 超时)。wbgetentities 走缓存,
同批 28 件 p50 0.49s、最慢 0.67s、0 失败。批量/目录类查询仍走 SPARQL,不在此处。
"""

from __future__ import annotations

import logging
import threading
import time

import requests

from app.services.enrichment.sources import wikidata as _wd

logger = logging.getLogger(__name__)

API = "https://www.wikidata.org/w/api.php"
_BATCH = 50  # wbgetentities 匿名调用上限(超了返回 200 + error toomanyvalues)
_TIMEOUT = 10
_TRIES = 3
# ponytail: 进程级同时在途 ≤2(Wikimedia API 礼仪);prod 2 worker → ≤4。量大再上跨进程令牌。
_GATE = threading.BoundedSemaphore(2)


class WikidataApiError(RuntimeError):
    pass


def _retry_after(resp) -> float | None:
    try:
        v = resp.headers.get("Retry-After")
        return float(v) if v else None
    except (AttributeError, ValueError):
        return None


def _get(params: dict, http_get, sleep) -> dict:
    """一次 wbgetentities(带重试)。返回 entities 字典。

    ⚠️ 失败看两层:HTTP 状态,以及**响应体 error.code** —— maxlag/toomanyvalues 等是
    HTTP 200 + {"error": …}、没有 entities 键,只看状态码会当成「实体不存在」静默丢资料。
    """
    last: Exception | None = None
    for attempt in range(_TRIES):
        wait = float(2**attempt)  # 1s, 2s
        try:
            with _GATE:
                r = http_get(
                    API,
                    params=params,
                    headers={"User-Agent": _wd.USER_AGENT},
                    timeout=_TIMEOUT,
                )
            if r.status_code == 429 or r.status_code >= 500:
                last = WikidataApiError(f"HTTP {r.status_code}")
                wait = _retry_after(r) or wait
            else:
                try:
                    r.raise_for_status()
                except (
                    requests.HTTPError
                ) as e:  # 其它 4xx:不重试,统一成 WikidataApiError
                    raise WikidataApiError(f"HTTP {r.status_code}") from e
                body = r.json()
                err = body.get("error")
                if err:
                    if err.get("code") != "maxlag":
                        raise WikidataApiError(f"{err.get('code')}: {err.get('info')}")
                    last = WikidataApiError("maxlag")
                    wait = _retry_after(r) or wait
                elif "entities" not in body:
                    raise WikidataApiError("response has no entities")
                else:
                    return body["entities"]
        except (requests.Timeout, requests.ConnectionError) as e:
            last = e
        if attempt < _TRIES - 1:
            sleep(wait)
    raise last if isinstance(last, WikidataApiError) else WikidataApiError(str(last))


def get_entities(
    ids, *, props: str, languages=None, http_get=requests.get, sleep=time.sleep
) -> dict[str, dict]:
    """wbgetentities。ids 按 50 个一批;返回 {qid: entity},缺失实体不出现。"""
    ids = list(dict.fromkeys(ids))
    out: dict[str, dict] = {}
    for i in range(0, len(ids), _BATCH):
        params = {
            "action": "wbgetentities",
            "format": "json",
            "maxlag": 5,
            "ids": "|".join(ids[i : i + _BATCH]),
            "props": props,
        }
        if languages:
            params["languages"] = "|".join(languages)
        for q, e in _get(params, http_get, sleep).items():
            if "missing" not in e:
                out[q] = e
    return out


def best_statements(entity: dict, pid: str) -> list[dict]:
    """spec §3.2 主值:排除 deprecated;有 preferred 只取 preferred,否则 normal(= SPARQL wdt:),
    另外只取 snaktype=value —— wdt: 会把「未知值」当 blank node 返回,这里故意收紧(修 §4.2)。"""
    sts = [
        s
        for s in ((entity or {}).get("claims") or {}).get(pid, [])
        if s.get("rank") != "deprecated"
    ]
    pref = [s for s in sts if s.get("rank") == "preferred"]
    return [
        s for s in (pref or sts) if (s.get("mainsnak") or {}).get("snaktype") == "value"
    ]


def _datavalue(statement: dict) -> dict:
    snak = statement.get("mainsnak") or {}
    return (snak.get("datavalue") or {}) if snak.get("snaktype") == "value" else {}


def entity_id(statement: dict) -> str | None:
    dv = _datavalue(statement)
    return (
        (dv.get("value") or {}).get("id")
        if dv.get("type") == "wikibase-entityid"
        else None
    )


def time_value(statement: dict) -> str | None:
    dv = _datavalue(statement)
    return (dv.get("value") or {}).get("time") if dv.get("type") == "time" else None


def labels_of(ids, languages, fetch) -> dict[str, dict[str, str]]:
    """{qid: {lang: label}}(只含有的)。fetch = get_entities 或测试注入。"""
    ids = list(ids)
    if not ids:
        return {}
    ents = fetch(ids, props="labels", languages=list(languages))
    return {
        q: {lang: v["value"] for lang, v in (e.get("labels") or {}).items()}
        for q, e in ents.items()
    }
