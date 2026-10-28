"""各馆「必看」作品清单 —— 预生成与馆藏列表的排序头部。

替代 popularity 当排序主键:popularity = Wikidata 跨语言条目数,prod 77% 为 0
(Joconde 源的件写死 0),同分大面积平局 → 前 N 件由 id 决定,等于随机。

来源(2026-09-30 摸底,qid 逐件在 prod 核过馆/作者/年代):
- louvre:官方参观线路 12 件
- orsay:官网无逐件清单,取主流导览共识
- petit_palais:官网 chefs-d'œuvre 页 11 件里能唯一对上的 7 件
  (乌戈林像库里 4 个同名版本分不清,其余库里没有 —— 不猜)
- orangerie:睡莲库里有的 7 块(缺《Matin aux saules》)+ 保罗·纪尧姆像;
  另 3 件是无图件(9-05 定不做)

清单本身在 museums.yaml 各馆的 `must_see:`。改清单只需部署后端,不用发 App 包。顺序即排序。
"""

from sqlalchemy import and_, case, exists, or_

from app.models.museum_object import MuseumObject, ObjectImage


def _configs():
    from app.services.enrichment.catalog import MuseumCatalog
    from app.services.enrichment.factory import CATALOG_PATH

    return [
        (slug, cfg)
        for slug, cfg in MuseumCatalog.from_file(CATALOG_PATH).items()
        if cfg.must_see
    ]


_CONFIGS = _configs()

# 真相源是 museums.yaml 的 `must_see:`(2026-10-22 从代码搬过去:上新馆=加 yaml,不改代码)
MUST_SEE: dict[str, list[str]] = {slug: list(cfg.must_see) for slug, cfg in _CONFIGS}

# 必看件的馆内位置 slug → qid → {wing, level, room}(官网取得到才有,spec 2026-10-27 §五.5)
MUST_SEE_LOCATION: dict[str, dict[str, dict]] = {
    slug: dict(cfg.must_see_locations) for slug, cfg in _CONFIGS
}

ALL_MUST_SEE: frozenset[str] = frozenset(q for qs in MUST_SEE.values() for q in qs)


def must_see_order(slug: str | None) -> list:
    """ORDER BY 头部键,用法 `order_by(*must_see_order(slug), 其余键...)`。

    必看件按清单顺序 0..n-1,其余 n;没清单的馆 → 空列表(排序照旧)。"""
    qs = MUST_SEE.get(slug or "", [])
    if not qs:
        return []
    return [
        case({q: i for i, q in enumerate(qs)}, value=MuseumObject.qid, else_=len(qs))
    ]


def has_image_clause():
    """有图过滤:对象至少有一张可展示图(image_key 或 source_url 非空,且非隔离图)。

    与 must_see_order 同属"馆 TOP-N 是谁"这一个问题:App 藏品列表(浏览面)
    只给有图件排名,生成/报告用的 top_objects 曾经不过滤,导致两边候选池不同、
    排出来的第 N 位不是同一件(2026-10-07 橘园 TOP50 实例)。统一到这一个函数,
    谁用 top_objects / must_see_order 就自动跟 App 列表口径一致。
    qid 直达与搜索不受影响,只影响"前 N 件是谁"这个排名问题。
    """
    return exists().where(
        and_(
            ObjectImage.object_id == MuseumObject.id,
            or_(
                ObjectImage.image_key.isnot(None),
                ObjectImage.source_url.isnot(None),
            ),
            ObjectImage.role != "view_quarantine",
        )
    )
