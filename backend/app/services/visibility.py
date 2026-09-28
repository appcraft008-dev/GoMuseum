"""上新馆可见性闸的单一真相源(spec 2026-09-20-museum-visibility-gate §2.1)。

所有解析馆/藏品的端点一律走这里,**端点里不写 `published_at` 谓词** —— 十一处各写
一遍,下一个新端点必然会忘。`tests/unit/api/test_visibility_routes.py` 遍历全部路由,
新加带 slug/qid 的端点没登记就会红。

语义:
- `published_at IS NULL` = 准备中,只有 `can_preview` 账号看得见。
- 看不见一律按"不存在"处理(调用方返回与未知 slug 完全相同的 404,不是 403)——
  403 等于确认"这个馆存在但你不能看",对未官宣的馆本身就是泄漏。
- 索引(搜索/识别)里不携带可见性,查询时用本模块给的一份新鲜集合过滤:
  放出是一条直连 Postgres 的 SQL,碰不到任何 worker 的进程内缓存。
"""

from app.models.museum import Museum
from app.models.museum_object import MuseumObject


def can_preview(db, credentials) -> bool:
    """令牌 → 是否预览者。无令牌/坏令牌/过期一律 False,**绝不 401**
    (老 App 拿过期令牌打探索页,401 整页就崩)。"""
    if not credentials:
        return False
    try:
        from app.services.auth_service import AuthService

        user = AuthService.get_current_user(db, credentials.credentials)
    except Exception:
        return False
    return bool(getattr(user, "can_preview", False))


def visible_museum_ids(db, preview: bool) -> set | None:
    """可见馆 id 集合;None = 全可见(预览者)。每次现查:馆总共个位数行。"""
    if preview:
        return None
    rows = db.query(Museum.id).filter(Museum.published_at.isnot(None)).all()
    return {r[0] for r in rows}


def museum_visible(db, slug: str, preview: bool) -> bool:
    """未知 slug 也返回 False —— 调用方对两者给同一个 404。"""
    m = db.query(Museum.published_at).filter(Museum.slug == slug).first()
    return m is not None and (preview or m[0] is not None)


def qid_visible(db, qid: str, preview: bool) -> bool:
    """藏品所属馆是否可见。**未知 qid 返回 True**:交给下游走它自己的 not-found,
    这样隐身馆的藏品与不存在的藏品得到同一个响应。"""
    if preview:
        return True
    row = (
        db.query(Museum.published_at)
        .join(MuseumObject, MuseumObject.museum_id == Museum.id)
        .filter(MuseumObject.qid == qid)
        .first()
    )
    return row is None or row[0] is not None
