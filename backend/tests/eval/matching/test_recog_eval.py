"""识别文字链回归门槛(spec §2.1/§7)。门槛 0.75/0.9 只在偶数下标(调参半边)上定过;
这里用奇数下标(留出半边)报数和断言,外加 Cross 墙签双标题回归用例(不论奇偶)。"""

import collections
import json

from app.services.matching.normalize import normalize
from app.services.recognition.matcher import match
from tests.eval.matching.conftest import HERE

# 实测(2026-10-07,抽样目录 5789 件,留出半边)-3pp
FLOOR_TOP3 = {"exact": 0.97, "partial": 0.93, "typo": 0.97, "alias_missing": 0.26}
MAX_SHOWN = {"neg_junk": 0.0, "neg_famous": 0.34}


def test_recognition_holdout(eval_index):
    all_cases = json.load(open(HERE / "recog_cases.json", encoding="utf-8"))
    cases = all_cases[1::2] + [c for c in all_cases if c["kind"] == "label_bilingual"]
    pos = {e["qid"]: i for i, e in enumerate(eval_index)}
    for c in all_cases:  # 别名缺失:把目标件的英文名从索引里删掉(与构造时一致)
        if c.get("drop"):
            e = eval_index[pos[c["target"]]]
            e["names"] = e["names"] - {normalize(x) for x in c["drop"]}
    by = collections.defaultdict(lambda: [0, 0, 0])  # n, 进前3, 出候选
    for c in cases:
        r = match(eval_index, c["queries"], [], c["hints"])[:3]
        b = by[c["kind"]]
        b[0] += 1
        b[1] += any(q == c["target"] for q, _ in r)
        b[2] += bool(r)
    rate = {k: (t / n, s / n) for k, (n, t, s) in by.items()}
    for k, floor in FLOOR_TOP3.items():
        assert rate[k][0] >= floor, (k, rate[k])
    for k, cap in MAX_SHOWN.items():
        assert rate[k][1] <= cap, (k, rate[k])
    assert rate["label_bilingual"][0] == 1.0
