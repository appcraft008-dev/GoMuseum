"""每日音频盘点(契约纪律 37 第③层)的判定逻辑。

09-14 那次损失 12 天没人发现;这里钉住:掉了就报、换 key 不报、
绕过台账的损失被单独标成「来源不明」(最高级别)。
"""

from scripts.audio_inventory import diff, render


def _slot(key, engine="voxcpm2", museum="orsay", label="x"):
    return dict(key=key, engine=engine, museum=museum, label=label)


PREV = {
    "artist|Q34618|zh": _slot("a/zh.mp3", museum="(跨馆作者)"),
    "section|o1|fr|guide": _slot("s/fr.mp3"),
    "section|o1|en|guide": _slot("s/en-tts.mp3", engine="tts-1"),
}


def test_replaced_key_is_not_a_loss():
    now = dict(PREV)
    now["section|o1|en|guide"] = _slot("s/en-vox.mp3")  # tts-1 → VoxCPM2 重录
    d = diff(PREV, now, set())
    assert d == {"explained": [], "unexplained": []}


def test_dropped_slot_without_ledger_is_unexplained():
    now = {k: v for k, v in PREV.items() if k != "artist|Q34618|zh"}  # 09-14 那种
    d = diff(PREV, now, set())
    assert [s for s, _ in d["unexplained"]] == ["artist|Q34618|zh"]
    assert d["explained"] == []


def test_dropped_slot_with_ledger_is_explained_but_still_reported():
    now = {k: v for k, v in PREV.items() if k != "section|o1|fr|guide"}
    d = diff(PREV, now, {"s/fr.mp3"})
    assert [s for s, _ in d["explained"]] == ["section|o1|fr|guide"]
    subject, body = render(PREV, now, d, "2026-09-26T04:20:00+00:00")
    assert subject.startswith("⚠️") and "orsay / section: 1" in body


def test_unexplained_loss_gets_the_highest_severity_subject():
    now = {}
    d = diff(PREV, now, {"s/fr.mp3"})
    subject, body = render(PREV, now, d, "2026-09-26T04:20:00+00:00")
    assert subject.startswith("⛔") and "来源不明" in subject
    assert "(跨馆作者) / artist: 1" in body
