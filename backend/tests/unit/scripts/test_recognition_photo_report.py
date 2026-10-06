"""分诊口径:用当前引擎重跑这张照片,结果已经指向答案 → fixed_now;
答案作品库里没图(=没向量,拍照不可能认出)→ no_reference;其余 → real_failure。
not_found(没有答案)只能是 real_failure。"""

import io

import numpy as np
from PIL import Image

from scripts.recognition_photo_report import classify, clues


def test_fixed_now_when_match_is_answer():
    out = {"outcome": "match", "match": {"qid": "Q1"}, "candidates": []}
    assert classify("Q1", out, answer_has_image=True) == "fixed_now"


def test_fixed_now_when_answer_is_top_candidate():
    out = {"outcome": "candidates", "match": None, "candidates": [{"qid": "Q1"}]}
    assert classify("Q1", out, answer_has_image=True) == "fixed_now"


def test_answer_lower_candidate_is_still_failure():
    out = {
        "outcome": "candidates",
        "match": None,
        "candidates": [{"qid": "Q2"}, {"qid": "Q1"}],
    }
    assert classify("Q1", out, answer_has_image=True) == "real_failure"


def test_no_reference_when_answer_has_no_image():
    out = {"outcome": "unrecognized", "match": None, "candidates": []}
    assert classify("Q1", out, answer_has_image=False) == "no_reference"


def test_not_found_is_real_failure():
    out = {"outcome": "unrecognized", "match": None, "candidates": []}
    assert classify(None, out, answer_has_image=False) == "real_failure"


def _jpeg(arr):
    buf = io.BytesIO()
    Image.fromarray(arr.astype("uint8")).save(buf, format="JPEG")
    return buf.getvalue()


def test_clues_flag_blur_and_overexposure():
    flat_white = _jpeg(np.full((64, 64, 3), 255))
    noisy = _jpeg(np.random.default_rng(0).integers(0, 255, (64, 64, 3)))
    c_white, c_noisy = clues(flat_white), clues(noisy)
    assert c_white["overexposed"] > 0.9
    assert c_white["blur"] < c_noisy["blur"]  # 纯色=最「糊」(拉普拉斯方差≈0)
