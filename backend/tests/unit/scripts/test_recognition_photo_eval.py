from scripts.recognition_photo_eval import replay, verdict

TH = dict(low=0.72, high=0.85, margin=0.04)


def test_replay_crops_gate_liberty_case():
    """《自由引导人民》10-12 真机:画框给错的 0.723,只有裁块能把答案抬到 0.912。"""
    full = [("WRONG", 0.60)]
    canvas = [[("WRONG", 0.723)]]
    crops = [[("LIB", 0.912)], [("WRONG", 0.70)]]
    now = replay(full, canvas, crops, crops_below=0.72, high=0.85)
    assert now[0] == ("WRONG", 0.723)  # ≥LOW → 裁块被跳过
    new = replay(full, canvas, crops, crops_below=0.85, high=0.85)
    assert new[0] == ("LIB", 0.912)


def test_replay_full_frame_direct_skips_everything():
    full = [("A", 0.9)]
    assert replay(full, [[("B", 0.95)]], [[("C", 0.99)]], 0.85, 0.85) == full


def test_replay_none_stage_is_skipped():
    assert replay([("A", 0.5)], None, None, 0.85, 0.85) == [("A", 0.5)]


def test_verdict_positive():
    assert verdict([("A", 0.9), ("B", 0.5)], {"A"}, **TH) == "直判对"
    assert verdict([("B", 0.9), ("A", 0.5)], {"A"}, **TH) == "直判错"
    # 第二名紧咬 → 不直判,落候选
    assert verdict([("B", 0.9), ("A", 0.88)], {"A"}, **TH) == "候选含答案(第2)"
    assert verdict([("B", 0.8), ("C", 0.75)], {"A"}, **TH) == "候选全错"
    assert verdict([("A", 0.7)], {"A"}, **TH) == "交AI"


def test_verdict_absent():
    assert verdict([("B", 0.9)], set(), **TH) == "直判错"
    assert verdict([("B", 0.8)], set(), **TH) == "候选噪音"
    assert verdict([("B", 0.6)], set(), **TH) == "交AI(对)"
    assert verdict([], set(), **TH) == "交AI(对)"
