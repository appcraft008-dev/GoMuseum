"""宽幅作品切块参考图(role="tile"):让「只拍了一段」的照片也有参照可比。

识别预处理把整图直接压成 224×224:橘园《睡莲》这种 3:1~9:1 的长卷被压扁后,
用户拍的局部(手机取景 4:3)跟它几乎不像,而 8 幅睡莲彼此又像 → 掉兜底或认成邻幅。
修法在索引侧:沿长边切成手机取景比例(满高 4:3,步长半块)的块,每块一个向量、
都指向原件。查询侧不动。

实测(2026-10-04,Commons 54 张橘园实拍,SIFT 独立标注):top1 对 27→51,
直判 12→38,错认 8→1;橘园其余 110 件对照 0 件被抢。加半高块(×7 向量)只多对 1 张,不做。
tile 不是展示图:图集/分享排除它(见 HIDDEN_ROLES)。
"""

from __future__ import annotations

import io

from PIL import Image

from app.models.museum_object import ObjectImage

TILE_ROLE = "tile"
# 不进图集/分享的 role
HIDDEN_ROLES = ("view_quarantine", TILE_ROLE)
TILE_MIN_RATIO = 2.0  # 长短边比 ≥ 此值才切
_SORT_BASE = 1000  # 排在所有展示图之后(按 sort 取首图的地方不会取到 tile)
_JPEG_QUALITY = 82


def tile_boxes(w: int, h: int) -> list[tuple[int, int, int, int]]:
    """沿长边切满短边、4:3 取景的窗口,步长半窗,首尾都贴边。不够宽 → []。"""
    if max(w, h) < TILE_MIN_RATIO * min(w, h):
        return []
    horizontal = w >= h
    long_, short = (w, h) if horizontal else (h, w)
    win = round(short * 4 / 3)
    starts = list(range(0, long_ - win + 1, max(1, win // 2)))
    if starts[-1] != long_ - win:
        starts.append(long_ - win)
    if horizontal:
        return [(s, 0, s + win, h) for s in starts]
    return [(0, s, w, s + win) for s in starts]


def tile_key(qid: str, i: int) -> str:
    """基础键(与 materializer 同约定:文件为 {base}_large.jpg,backfill 换模型时按它重嵌)。"""
    return f"images/{qid}/tile-{i}"


def add_tiles(db, storage, obj, image: Image.Image, primary: ObjectImage, embed) -> int:
    """给一件作品写切块行 + R2 文件 + 向量。已有 tile 或不够宽 → 0。不 commit。
    embed(db, row, jpeg_bytes) 即 embed_image_row(tile 不是 view,不过入库闸)。"""
    if db.query(ObjectImage).filter_by(object_id=obj.id, role=TILE_ROLE).first():
        return 0
    image = image.convert("RGB")
    n = 0
    for i, box in enumerate(tile_boxes(*image.size)):
        buf = io.BytesIO()
        tile = image.crop(box)
        tile.thumbnail((1600, 1600))
        tile.save(buf, format="JPEG", quality=_JPEG_QUALITY)
        base = tile_key(obj.qid, i)
        storage.put(f"{base}_large.jpg", buf.getvalue(), "image/jpeg")
        row = ObjectImage(
            object_id=obj.id,
            role=TILE_ROLE,
            image_key=base,
            license=primary.license,
            credit=primary.credit,
            sort=_SORT_BASE + i,
        )
        db.add(row)
        db.flush()
        embed(db, row, buf.getvalue())
        n += 1
    return n
