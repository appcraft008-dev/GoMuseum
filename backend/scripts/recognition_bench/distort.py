"""合成畸变:官方图 → 伪游客照。纯 PIL+numpy,禁 import torch/onnxruntime。
非名作在 Commons 无他人照片,合成畸变是其测试照的主要来源(spec ③)。"""

from __future__ import annotations

import random

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter


def _perspective_coeffs(src_pts, dst_pts):
    # PIL PERSPECTIVE 需要 8 系数:解 8 元线性方程(标准做法)
    a = []
    for (x, y), (u, v) in zip(dst_pts, src_pts):
        a.append([x, y, 1, 0, 0, 0, -u * x, -u * y])
        a.append([0, 0, 0, x, y, 1, -v * x, -v * y])
    b = np.array(src_pts, dtype=np.float64).reshape(8)
    return np.linalg.solve(np.array(a, dtype=np.float64), b).tolist()


def _perspective(img: Image.Image, rng: random.Random) -> Image.Image:
    w, h = img.size
    j = lambda lim: rng.uniform(0.02, 0.10) * lim  # 角点抖动 2-10%
    dst = [(j(w), j(h)), (w - j(w), j(h)), (w - j(w), h - j(h)), (j(w), h - j(h))]
    src = [(0, 0), (w, 0), (w, h), (0, h)]
    coeffs = _perspective_coeffs(src, dst)
    return img.transform((w, h), Image.PERSPECTIVE, coeffs, Image.BICUBIC)


def _glare(img: Image.Image, rng: random.Random) -> Image.Image:
    w, h = img.size
    cx, cy = rng.uniform(0.2, 0.8) * w, rng.uniform(0.1, 0.5) * h
    r = rng.uniform(0.15, 0.3) * max(w, h)
    overlay = Image.new("L", (w, h), 0)
    draw = ImageDraw.Draw(overlay)
    for i in range(int(r), 0, -2):  # 同心圆近似径向渐变
        draw.ellipse([cx - i, cy - i, cx + i, cy + i], fill=int(200 * (1 - i / r)))
    white = Image.new("RGB", (w, h), (255, 255, 240))
    return Image.composite(white, img, overlay)


def _crop(img: Image.Image, rng: random.Random) -> Image.Image:
    w, h = img.size
    f = rng.uniform(0.75, 0.85)
    cw, ch = int(w * f), int(h * f)
    x, y = rng.randint(0, w - cw), rng.randint(0, h - ch)
    return img.crop((x, y, x + cw, y + ch)).resize((w, h), Image.BICUBIC)


def distort_all(img: Image.Image, seed: int) -> dict[str, Image.Image]:
    img = img.convert("RGB")
    rng = random.Random(seed)
    return {
        "perspective": _perspective(img, rng),
        "glare": _glare(img, rng),
        "crop": _crop(img, rng),
        "blur": img.filter(ImageFilter.GaussianBlur(2.5)),
        "dark": ImageEnhance.Brightness(img).enhance(0.45),
    }
