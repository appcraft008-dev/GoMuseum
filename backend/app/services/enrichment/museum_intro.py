"""博物馆介绍 + 封面(spec 2026-07-18)。
介绍:qid→en extract→接地生成(gate 不过不落)→按语言补缺(完整性按语言维度)。
封面:top-N 有图件逐件 LLM 得体性判定(古典/宗教裸体可,写实露骨否决;判定失败保守跳过)。
门面类预生成内容(成本分界原则),每馆一次性几分钱。"""

from __future__ import annotations

import logging

from app.models.museum import Museum
from app.models.museum_object import MuseumObject, ObjectImage
from app.services.enrichment.content_enricher import _parse_json
from app.services.enrichment.material import (
    fetch_museum_building_photo,
    fetch_museum_intro_material,
)
from app.services.enrichment.prompts import (
    build_cover_safety_prompt,
    build_museum_intro_prompt,
)

logger = logging.getLogger(__name__)


def generate_museum_intro(
    db,
    slug: str,
    *,
    complete,
    gate,
    translator,
    langs: list,
    force: bool = False,
    fetch_material=None,
) -> dict:
    m = db.query(Museum).filter_by(slug=slug).one_or_none()
    if not m:
        return {"error": "unknown museum"}
    di = {} if force else dict(m.description_i18n or {})
    out = {"generated": False, "translated": [], "skipped": None}

    if not di.get("en"):
        mat = (fetch_material or fetch_museum_intro_material)(m.qid)
        extract = mat.get("extract_en")
        if not extract:
            out["skipped"] = "no_material"  # 宁缺毋滥:源薄不硬写
            return out
        system, user = build_museum_intro_prompt(m.name_en or slug, extract)
        # 分段走固定三具名字段的JSON对象,后端拼接——staging实测:变长数组
        # {"paragraphs":[...]} 对 gpt-4o-mini 约束力不够,3/3次真实调用模型都合并成
        # 单元素数组(未违反格式,但违反意图);具名必填字段是更强的结构化约束
        # (模型难以"偷懒"合并——省略必填key比塞满弱格式约束更显眼,遵从率更高)。
        try:
            data = _parse_json(complete(system, user) or "")
            paragraphs = [data.get(k) for k in ("history", "highlights", "invitation")]
            text = "\n\n".join(p.strip() for p in paragraphs if p and p.strip())
        except Exception:
            text = ""
        if not text:
            return out  # JSON解析失败/空段落=当生成失败,不落半成品(宁缺毋滥,重跑再试)
        q = gate.check_section(extract, f"- Museum: {m.name_en}", text)
        if q.status != "published" or not q.body:
            return out  # gate 不过=不落库,重跑再试(无 needs_review 状态机)
        di["en"] = q.body
        out["generated"] = True

    for lang in langs:  # 按语言补缺:已有语种不动,缺的从 en 轴心纯翻译
        if lang == "en" or di.get(lang):
            continue
        try:
            di[lang] = translator.translate_section(di["en"], lang)
            out["translated"].append(lang)
        except Exception:
            logger.exception("museum intro translate %s failed: %s", lang, slug)
    m.description_i18n = di
    db.flush()
    return out


def _materialize_museum_photo(url, qid, storage, fetch_bytes) -> str | None:
    """馆建筑照精简物化:下载→两档→R2。不嵌入(建筑照绝不能进识别向量库,
    会污染藏品识别),不建 ObjectImage 行(Museum 无此关联,直接落 cover_image_key)。
    失败返回 None(调用方回落藏品逻辑)。"""
    from app.services.enrichment.materializer import (
        _two_tiers,
        _Unreadable,
        image_base_key,
    )

    base = image_base_key(qid, 0)
    try:
        if storage.exists(f"{base}_thumb.jpg") and storage.exists(f"{base}_large.jpg"):
            return base  # 共桶复用(同 materialize_row 惯例)
    except Exception:
        pass
    try:
        thumb, large = _two_tiers(fetch_bytes(url))
    except _Unreadable:
        return None
    except Exception:
        logger.warning("museum building photo fetch failed: %s", url, exc_info=True)
        return None
    try:
        storage.put(f"{base}_thumb.jpg", thumb, "image/jpeg")
        storage.put(f"{base}_large.jpg", large, "image/jpeg")
    except Exception:
        logger.warning("museum building photo upload failed: %s", base, exc_info=True)
        return None
    return base


def select_cover(
    db,
    slug: str,
    *,
    complete,
    force: bool = False,
    limit: int = 10,
    fetch_building_photo=None,
    storage=None,
    fetch_bytes=None,
):
    """封面优先取馆自身建筑外观照(P18,不过安全闸——架构零裸体风险,且无
    title/artist/category 可喂闸);无建筑照/下载失败 → 回落藏品图逐件得体性判定
    (原逻辑不变)。全不过→None(前端隐藏)。"""
    m = db.query(Museum).filter_by(slug=slug).one_or_none()
    if not m:
        return None
    if m.cover_image_key and not force:
        return m.cover_image_key

    if m.qid:
        fetch_photo = fetch_building_photo or fetch_museum_building_photo
        photo_url = fetch_photo(m.qid)
        if photo_url:
            from app.services.enrichment.materializer import _default_fetch_bytes
            from app.services.storage import get_object_storage

            key = _materialize_museum_photo(
                photo_url,
                m.qid,
                storage or get_object_storage(),
                fetch_bytes or _default_fetch_bytes,
            )
            if key:
                m.cover_image_key = key
                db.flush()
                return key

    rows = (
        db.query(MuseumObject, ObjectImage)
        .join(ObjectImage, ObjectImage.object_id == MuseumObject.id)
        .filter(
            MuseumObject.museum_id == m.id,
            ObjectImage.role == "primary",
            ObjectImage.image_key.isnot(None),
        )
        .order_by(MuseumObject.popularity.desc().nullslast())
        .limit(limit)
        .all()
    )
    for o, img in rows:
        system, user = build_cover_safety_prompt(
            o.title_en or o.qid, o.artist_en, o.category
        )
        try:
            ok = bool(_parse_json(complete(system, user)).get("appropriate"))
        except Exception:  # 判定失败=保守跳过该件(封面宁缺毋错)
            logger.warning("cover judge failed for %s, skip", o.qid)
            continue
        if ok:
            m.cover_image_key = img.image_key
            db.flush()
            return img.image_key
    return None
