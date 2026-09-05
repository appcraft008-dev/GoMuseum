"""make_record 的不变量:顶层分数必须与磁盘上那个文件同源。

这条不变量坏过一次,而且坏得无声 —— 分数照常写进 _state.json,只是拼错了来源。
下游没有任何东西会报错,只有人在排查失败原因时被带偏。
"""

from batch_record import make_record

FAIL1 = {"try": 1, "ok": False, "sharp": 136.1, "consist": 0.06, "lenratio": 1.46, "atempo": 0.784}
FAIL2 = {"try": 2, "ok": False, "sharp": 144.2, "consist": 0.72, "lenratio": 0.94, "atempo": 0.804}
FAIL3 = {"try": 3, "ok": False, "sharp": 135.6, "consist": 0.87, "lenratio": 1.01, "atempo": 0.971}
PASS3 = {"try": 3, "ok": True, "sharp": 143.1, "consist": 0.90, "lenratio": 1.02, "atempo": 0.965}


def test_全失败时顶层取最后一次而不是最优的一次():
    # 真实回归:旧版这里会记 sharp=136.1/consist=0.06(第一次,锐度"最优"),
    # 而 _rejected/ 里的文件是第三次的产物 —— 拿 0.06 去诊断必然跑偏。
    rec = make_record([FAIL1, FAIL2, FAIL3], "SEED_en", None)
    assert rec["consist"] == 0.87
    assert rec["sharp"] == 135.6
    assert rec["ok"] is False


def test_成功时顶层就是成功那次():
    rec = make_record([FAIL1, FAIL2, PASS3], "SEED_en", "abc")
    assert rec["ok"] is True
    assert rec["consist"] == 0.90
    assert rec["md5"] == "abc"


def test_四个分数同源不混搭():
    # 错位是逐字段发生的,所以逐字段核对:四个分数必须全部来自同一次尝试。
    rec = make_record([FAIL1, FAIL2, FAIL3], "SEED_en", None)
    for k in ("sharp", "consist", "lenratio", "atempo"):
        assert rec[k] == FAIL3[k], f"{k} 不是最后一次的值"


def test_每次尝试的原始分数都留着():
    rec = make_record([FAIL1, FAIL2, FAIL3], "SEED_en", None)
    assert [t["consist"] for t in rec["tries"]] == [0.06, 0.72, 0.87]


def test_单次成功也记进_tries():
    rec = make_record([PASS3], "SEED_zh", "d41d8")
    assert len(rec["tries"]) == 1
    assert rec["seed"] == "SEED_zh"
