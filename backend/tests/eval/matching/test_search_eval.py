"""搜索回归门槛(spec §2.2/§7)。目录是 prod 抽样快照(公开目录字段),用例固定种子
(build_fixture.py)。断言两件事:每类新 ≥ 旧(只有原分档的算法);各类不低于实测门槛。"""

import collections
import json

import pytest
from rapidfuzz import fuzz

from app.services.matching.normalize import normalize
from app.services.search import inprocess
from tests.eval.matching.conftest import HERE

# 实测(2026-10-07,抽样目录 5789 件)-3pp
FLOOR_AT20 = {
    "prefix2": 0.85,
    "typo": 0.76,
    "middle_word": 0.88,
    "words_skip": 0.74,
    "artist+word": 0.97,
    "zh_part": 0.95,
}


def _hit_rates(index, rank_fn, cases):
    by = collections.defaultdict(lambda: [0, 0])
    for c in cases:
        if c["target"] is None:
            continue
        got = [e["qid"] for e, _ in rank_fn(index, c["q"], 60)[:20]]
        b = by[c["kind"]]
        b[0] += 1
        b[1] += c["target"] in got
    return {k: h / n for k, (n, h) in by.items()}


def _tier_only(index, query, limit):
    scored = inprocess._tier_scores(index, query).values()
    out = sorted(scored, key=lambda es: (-es[1], -es[0]["popularity"]))
    return out[:limit]


@pytest.fixture(scope="module")
def cases():
    return json.load(open(HERE / "search_cases.json", encoding="utf-8"))


def test_search_not_worse_than_tier_only(eval_index, cases):
    new = _hit_rates(eval_index, inprocess.rank, cases)
    old = _hit_rates(eval_index, _tier_only, cases)
    for k in old:
        assert new[k] >= old[k] - 0.01, (k, old[k], new[k])
    for k, floor in FLOOR_AT20.items():
        assert new[k] >= floor, (k, new[k], floor)


def test_hifreq_same_tier_closer_titles_first(eval_index, cases):
    # 高频词命中几百件同档作品:同档内整名与查询越像越前(spec §2.2 评审意见 5)
    for c in [c for c in cases if c["kind"] == "hifreq"]:
        qn = normalize(c["q"])
        rows = [
            (s, max(fuzz.ratio(qn, n) for n in e["names"]))
            for e, s in inprocess.rank(eval_index, c["q"], 60)
        ]
        for (s1, m1), (s2, m2) in zip(rows, rows[1:]):
            assert s1 > s2 or m1 >= m2, (c["q"], rows)
