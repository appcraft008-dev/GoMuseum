"""找画布:合成「墙+画框+画、再斜拍」场景,候选里必须有一块与原画对得上。"""

import numpy as np
from PIL import Image

from app.services.recognition.canvas import canvas_quads


def _painting(w=300, h=400, seed=0):
    rng = np.random.default_rng(seed)
    small = rng.integers(0, 255, (8, 6, 3), dtype=np.uint8)  # 平滑色块,像画不像噪声
    return Image.fromarray(small).resize((w, h), Image.BICUBIC)


def _scene(painting, frame=40, yaw_shrink=0.12):
    """灰墙上挂金框画,再做一次透视(右边缩短)模拟斜拍。"""
    pw, ph = painting.size
    framed = Image.new("RGB", (pw + 2 * frame, ph + 2 * frame), (190, 150, 60))
    framed.paste(painting, (frame, frame))
    wall = Image.new("RGB", (900, 900), (120, 120, 125))
    fx, fy = (900 - framed.width) // 2, (900 - framed.height) // 2
    wall.paste(framed, (fx, fy))
    d = yaw_shrink * 900
    # PIL PERSPECTIVE:输出点 → 输入点;右缘上下各收 d
    src = [(0, 0), (900, 0), (900, 900), (0, 900)]
    dst = [(0, 0), (900, d), (900, 900 - d), (0, 900)]
    a, b = [], []
    for (x, y), (u, v) in zip(dst, src):
        a += [[x, y, 1, 0, 0, 0, -u * x, -u * y], [0, 0, 0, x, y, 1, -v * x, -v * y]]
        b += [u, v]
    coeffs = np.linalg.solve(np.array(a, float), np.array(b, float))
    return wall.transform((900, 900), Image.PERSPECTIVE, coeffs.tolist(), Image.BICUBIC)


def _mae(x, y):
    f = lambda im: np.asarray(im.convert("RGB").resize((48, 64)), dtype=float)
    return float(np.abs(f(x) - f(y)).mean())


def test_finds_canvas_in_framed_oblique_scene():
    p = _painting()
    scene = _scene(p)
    quads = canvas_quads(scene)
    assert quads, "应至少找到一个框"
    best = min(_mae(q, p) for q in quads)
    assert best < 12  # 拉正后的画布与原画接近
    assert _mae(scene, p) > 3 * best  # 对照:整张图(带框+墙)明显更远


def test_plain_image_has_no_quads():
    assert canvas_quads(Image.new("RGB", (400, 300), (10, 20, 30))) == []
