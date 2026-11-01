"""图像物化器:扫"有 source_url 无 image_key"的 ObjectImage 行 →
下载(合规 UA 限速)→ Pillow 两档(thumb480/large1600,JPEG q82,不放大)→ R2 →
Commons 署名(license/credit)→ 填 image_key(基础键 images/{qid}/{sort})。
逐行 try/except 幂等:失败留空重跑重试;打不开的(SVG等)记 skipped。
批量预物化为主(列表门面+识别参照);懒补漏钩子复用单件入口。
spec docs/superpowers/specs/2026-07-03-image-r2-selfhost-design.md。"""

from __future__ import annotations

import html
import io
import logging
import re
from urllib.parse import unquote

from app.models.museum import Museum
from app.models.museum_object import MuseumObject, ObjectImage

logger = logging.getLogger(__name__)

_THUMB_PX = 480
_LARGE_PX = 1600
_JPEG_QUALITY = 82
_MAX_BYTES = 60 * 1024 * 1024  # 超大原图跳过(记 skipped)

_UA = "GoMuseumBot/0.1 (https://gomuseum.app; contact appcraft008@gmail.com)"


def image_base_key(qid: str, sort: int) -> str:
    """image_key 存基础键;实际文件 {base}_thumb.jpg / {base}_large.jpg。
    (与 audio_key 存全键的先例不同:一行图对应两个档位文件。)"""
    return f"images/{qid}/{sort}"


def _default_fetch_bytes(url: str) -> bytes:
    import requests

    # Special:FilePath 加 ?width:用 Wikimedia 服务端缩放,带宽降一个量级,
    # 根除名作原图 70MB+ 触发超大跳过(库尔贝《画家的工作室》教训)
    if "Special:FilePath" in url and "?" not in url:
        url = f"{url}?width={_LARGE_PX}"
    r = requests.get(url, headers={"User-Agent": _UA}, timeout=60)
    r.raise_for_status()
    return r.content


def _strip_html(s: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", s or "")).strip()


def _clip(s: str, limit: int) -> str | None:
    """截断到 DB 列宽;空串 → None。"""
    if not s:
        return None
    return s[:limit]


# Credit 字段常写的是图片来源而不是人;这些情况认不准,不猜
_NOT_A_PERSON = re.compile(
    r"https?:|www\.|gallery|mus[eé]|œuvre|\.jpe?g|\.png|image:|wikipedia|collection",
    re.IGNORECASE,
)
_BOT = re.compile(r"\bbot\b|^(rotatebot|cropbot|fbot|sfbot)$", re.IGNORECASE)


def photo_author(attribution: str, credit: str, uploader: str | None) -> str | None:
    """这张照片该署谁(CC BY 要署的人)。`Artist` 常是画家,所以另外找;认不准 → None。"""
    if attribution:
        return attribution
    if "own work" in credit.lower():
        return uploader if uploader and not _BOT.search(uploader) else None
    if credit and len(credit) <= 80 and not _NOT_A_PERSON.search(credit):
        return credit
    return None


def is_cc_by(license_: str | None) -> bool:
    return (license_ or "").upper().startswith("CC BY")


def extmeta_fields(info: dict) -> dict:
    """imageinfo 一项 → {license, credit, photo_author}。截断到列宽。"""
    meta = info.get("extmetadata") or {}
    text = lambda k: _strip_html((meta.get(k) or {}).get("value", ""))
    # 截断到列宽:部分 Commons 署名是多段落说明(英法双语+联系方式),
    # 超 varchar(255) 会 StringDataRightTruncation 崩掉整轮物化
    # (2026-07-25 卢浮宫实测:1369/10159 处崩)。署名截断不影响合规归属。
    return {
        "license": _clip(text("LicenseShortName"), 128),
        "credit": _clip(text("Artist"), 255),
        "photo_author": _clip(
            photo_author(text("Attribution"), text("Credit"), info.get("user")) or "",
            255,
        ),
    }


def _default_fetch_meta(source_url: str) -> dict:
    """Commons imageinfo → {license, credit, photo_author}。失败返回 {}(署名可后补)。"""
    import requests

    filename = unquote(source_url.rsplit("/", 1)[-1])
    try:
        r = requests.get(
            "https://commons.wikimedia.org/w/api.php",
            params={
                "action": "query",
                "titles": f"File:{filename}",
                "prop": "imageinfo",
                "iiprop": "extmetadata|user",
                "format": "json",
            },
            headers={"User-Agent": _UA},
            timeout=30,
        )
        r.raise_for_status()
        pages = r.json()["query"]["pages"]
        return extmeta_fields(next(iter(pages.values()))["imageinfo"][0])
    except Exception:
        return {}


class _Unreadable(Exception):
    """SVG/损坏/超大等不可处理图:永久跳过(区别于网络失败可重试)。"""


def _two_tiers(data: bytes) -> tuple[bytes, bytes]:
    from PIL import Image, UnidentifiedImageError

    if len(data) > _MAX_BYTES:
        raise _Unreadable(f"too large: {len(data)} bytes")
    try:
        img = Image.open(io.BytesIO(data))
        img = img.convert("RGB")
    except (UnidentifiedImageError, OSError, ValueError) as e:
        raise _Unreadable(str(e)) from e

    def _tier(max_px: int) -> bytes:
        t = img.copy()
        t.thumbnail((max_px, max_px))  # 不放大
        buf = io.BytesIO()
        t.save(buf, format="JPEG", quality=_JPEG_QUALITY)
        return buf.getvalue()

    return _tier(_THUMB_PX), _tier(_LARGE_PX)


def materialize_row(
    db, row: ObjectImage, qid: str, *, fetch_bytes, storage, fetch_meta=None
) -> str:
    """单行物化。返回 'done' | 'failed' | 'skipped'。失败/跳过均留 image_key 为空。"""
    base = image_base_key(qid, row.sort or 0)
    # 共桶复用:两档文件已在 R2(如 staging 先物化过)→ 免下载/缩放/上传,只填 DB
    try:
        already = storage.exists(f"{base}_thumb.jpg") and storage.exists(
            f"{base}_large.jpg"
        )
    except Exception:
        already = False  # 探测失败不阻断,走正常下载
    if not already:
        try:
            data = fetch_bytes(row.source_url)
            thumb, large = _two_tiers(data)
        except _Unreadable as e:
            logger.warning("image unreadable, skip: %s (%s)", row.source_url, e)
            return "skipped"
        except Exception:
            logger.exception("image fetch failed: %s", row.source_url)
            return "failed"
        try:
            storage.put(f"{base}_thumb.jpg", thumb, "image/jpeg")
            storage.put(f"{base}_large.jpg", large, "image/jpeg")
        except Exception:
            logger.exception("image upload failed: %s", base)
            return "failed"
    if fetch_meta is not None:
        meta = fetch_meta(row.source_url) or {}
        row.license = meta.get("license") or row.license
        row.credit = meta.get("credit") or row.credit
        if meta.get("photo_author") and is_cc_by(row.license) and row.credit:
            # Artist 填的是画家时,展示层会隐藏它,CC BY 要署的摄影师就没了
            from app.services.matching.people import is_artist_credit
            from app.services.museum_repo import artist_aliases_of

            obj = db.get(MuseumObject, row.object_id)
            if is_artist_credit(row.credit, artist_aliases_of(db, obj)):
                row.credit = meta["photo_author"]
    try:  # 入库即嵌入(R2 已有文件时从 storage 取 large;失败不阻断物化)
        from app.services.recognition.embeddings import embed_image_row

        large_bytes = large if not already else storage.get(f"{base}_large.jpg")
        if large_bytes:
            embed_image_row(db, row, large_bytes)
    except Exception:
        logger.exception("embed hook failed: %s", base)
    row.image_key = base
    db.flush()
    return "done"


def materialize_object_images(
    db, obj: MuseumObject, *, fetch_bytes=None, storage=None, fetch_meta=None
) -> dict:
    """单件入口(懒补漏钩子复用):物化该件全部缺 key 的图行。"""
    fetch_bytes = fetch_bytes or _default_fetch_bytes
    fetch_meta = _default_fetch_meta if fetch_meta is None else fetch_meta
    if storage is None:
        from app.services.storage import get_object_storage

        storage = get_object_storage()
    counts = {"done": 0, "failed": 0, "skipped": 0}
    rows = (
        db.query(ObjectImage)
        .filter(
            ObjectImage.object_id == obj.id,
            ObjectImage.image_key.is_(None),
            ObjectImage.source_url.isnot(None),
        )
        .order_by(ObjectImage.sort)
        .all()
    )
    for row in rows:
        counts[
            materialize_row(
                db,
                row,
                obj.qid,
                fetch_bytes=fetch_bytes,
                storage=storage,
                fetch_meta=fetch_meta,
            )
        ] += 1
    return counts


def materialize_images(
    db, slug: str, *, limit=None, fetch_bytes=None, storage=None, fetch_meta=None
) -> dict:
    """全馆批量(onboard images 命令):按热度逐件物化缺图。幂等可重跑。"""
    m = db.query(Museum).filter_by(slug=slug).one_or_none()
    if not m:
        return {"error": "unknown museum"}
    q = (
        db.query(MuseumObject)
        .filter_by(museum_id=m.id)
        .order_by(MuseumObject.popularity.desc())
    )
    if limit:
        q = q.limit(limit)
    counts = {"done": 0, "failed": 0, "skipped": 0}
    for i, o in enumerate(q.all()):
        c = materialize_object_images(
            db, o, fetch_bytes=fetch_bytes, storage=storage, fetch_meta=fetch_meta
        )
        for k in counts:
            counts[k] += c[k]
        if (i + 1) % 25 == 0:
            db.commit()  # 分批落盘:中途崩溃/重部署不丢已完成进度
    db.commit()
    return counts
