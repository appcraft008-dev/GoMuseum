"""找画布:游客照 → 若干「画框/画布」四边形候选,透视拉正后送嵌入(与全帧按 qid 取 MAX)。

为什么需要:参考图只有画布,游客照常带一大圈雕花画框+墙(实测蒙娜丽莎正面照被挤到第46名,
裁到画布后第1名)。斜拍的梯形也在这里一并拉正。
不挑「哪个才是画布」——外框/内框/画布都作候选交给向量打分,挑错的代价只是多算几次嵌入。
2026-10-01 验证:9 张小红书游客照 5/6 幅画升到第1;留出集(bench 真实照+库外)9 改善 0 退化,
直接认错/库外直判均为 0。"""

from __future__ import annotations

import cv2
import numpy as np
from PIL import Image

_MAX_SIDE = 640  # 找框在缩略图上做,拉正用原图
# 多组边缘参数各找一遍:单组参数常把雕花框/墙的边连成一片,找出歪框(大宫女实测)
_CANNY = ((0.66, 1.33, True), (0.33, 0.66, True), (0.66, 1.33, False), (1.0, 2.0, True))
# 外框拉正后若找不出闭合内框(雕花内缘与画布边连成一片),按框宽常见比例内缩
_INSETS = (0.10, 0.17, 0.24)


def _order(pts: np.ndarray) -> np.ndarray:
    """四点 → 左上/右上/右下/左下。"""
    s, d = pts.sum(1), np.diff(pts, axis=1).ravel()
    return np.array(
        [pts[s.argmin()], pts[d.argmin()], pts[s.argmax()], pts[d.argmax()]],
        np.float32,
    )


def _quads(
    img: Image.Image, max_n: int, min_frac: float, max_frac: float
) -> list[Image.Image]:
    rgb = np.asarray(img.convert("RGB"))
    H, W = rgb.shape[:2]
    k = _MAX_SIDE / max(H, W)
    small = cv2.resize(rgb, (round(W * k), round(H * k)), interpolation=cv2.INTER_AREA)
    gray = cv2.GaussianBlur(cv2.cvtColor(small, cv2.COLOR_RGB2GRAY), (5, 5), 0)
    med = float(np.median(gray))
    area_img = small.shape[0] * small.shape[1]
    found: list[tuple[float, np.ndarray]] = []
    for lo, hi, dilate in _CANNY:
        edges = cv2.Canny(gray, int(max(0, lo * med)), int(min(255, hi * med)))
        if dilate:
            edges = cv2.dilate(edges, np.ones((3, 3), np.uint8))
        cnts, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
        for c in cnts:
            hull = cv2.convexHull(c)
            a = cv2.contourArea(hull)
            if not (min_frac * area_img <= a <= max_frac * area_img):
                continue
            approx = cv2.approxPolyDP(hull, 0.03 * cv2.arcLength(hull, True), True)
            if len(approx) != 4:
                continue
            q = _order(approx.reshape(4, 2).astype(np.float32))
            # 去重:四角都接近视为同一框
            if all(np.abs(q - b).max() > 0.03 * max(small.shape) for _, b in found):
                found.append((a, q))
    found.sort(key=lambda t: -t[0])
    out = []
    for _, q in found[:max_n]:
        q = q / k
        w = int(max(np.linalg.norm(q[1] - q[0]), np.linalg.norm(q[2] - q[3])))
        h = int(max(np.linalg.norm(q[3] - q[0]), np.linalg.norm(q[2] - q[1])))
        if w < 32 or h < 32:
            continue
        M = cv2.getPerspectiveTransform(q, np.float32([[0, 0], [w, 0], [w, h], [0, h]]))
        out.append(Image.fromarray(cv2.warpPerspective(rgb, M, (w, h))))
    return out


def canvas_quads(img: Image.Image, max_n: int = 4) -> list[Image.Image]:
    """外层找框 → 每个框内再找一层;找不出内框则按比例内缩。无框 → []。"""
    out: list[Image.Image] = []
    for q in _quads(img, max_n, 0.08, 0.92):
        out.append(q)
        inner = _quads(q, 1, 0.35, 0.92)
        out += inner
        if not inner:
            w, h = q.size
            for f in _INSETS:
                d = round(f * min(w, h))
                out.append(q.crop((d, d, w - d, h - d)))
    return out
