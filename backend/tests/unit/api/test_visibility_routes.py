"""可见性闸的**登记簿**:凡是能按 slug/qid/museum 定位馆或藏品的路由,都必须在这里
表态 —— 要么接了闸,要么写明为什么不需要。

为什么要有它(spec 2026-09-20 §九②):闸的暴露面清单是 9-20 手工枚举的,到实现时
已经过期 —— `/audio`、`/audio/stream` 两个端点不在当初的十一项里。手工清单必然会
漏,所以改成遍历 `app.routes`:新加一个带 slug/qid 的端点而没来这里登记,这条就红。

登记"接了闸"只是声明;行为由 `tests/integration/test_visibility_gate.py` 的 2×2 验证。
"""

import inspect
import re
import typing

from fastapi.routing import APIRoute

from app.main import app

_KEYS = {"slug", "qid", "museum", "museum_slug"}

GATED = "gated"

REGISTRY = {
    ("GET", "/api/v1/museums/{slug}"): GATED,
    ("GET", "/api/v1/museums/{slug}/objects"): GATED,
    ("GET", "/api/v1/museums/{slug}/objects/{qid}/content"): GATED,
    ("GET", "/api/v1/museums/{slug}/objects/{qid}/audio"): GATED,
    ("GET", "/api/v1/museums/{slug}/objects/{qid}/audio/stream"): GATED,
    ("GET", "/api/v1/museums/{slug}/search"): GATED,
    ("POST", "/api/v1/museums/{slug}/recognize"): GATED,
    ("POST", "/api/v1/recognize"): GATED,
    ("POST", "/api/v1/recognize/confirm"): GATED,
    ("POST", "/api/v1/entitlements/audio/unlock"): GATED,
    ("POST", "/api/v1/feedback"): "只写不读:收下反馈不回显任何馆/藏品内容",
    ("POST", "/api/v1/content/explanation"): "已退役,恒 410",
    (
        "POST",
        "/api/v1/content/tts/generate",
    ): "qid 分支已退役恒 410;ad-hoc 分支不按 qid 取任何内容",
    ("POST", "/api/v1/content/tts/info"): "只算文本哈希与时长,不读库",
}


def _locating_params(route: APIRoute) -> set[str]:
    """读端点函数签名,不读 `route.dependant`:后者是 FastAPI 内部结构,CI 与本地
    版本不同(0.141 vs 0.115)时整个探测器静默失明 —— 实测过一次,靠下面的自检才发现。"""
    names = set(re.findall(r"\{(\w+)\}", route.path))
    try:
        hints = typing.get_type_hints(route.endpoint)
    except Exception:
        hints = {}
    for name, param in inspect.signature(route.endpoint).parameters.items():
        names.add(name)
        ann = hints.get(name, param.annotation)
        names |= set(getattr(ann, "model_fields", None) or {})
    return names & _KEYS


def _locating_routes() -> set[tuple[str, str]]:
    out = set()
    for r in app.routes:
        if isinstance(r, APIRoute) and _locating_params(r):
            for m in r.methods:
                out.add((m, r.path))
    return out


def test_every_locating_route_is_registered():
    missing = _locating_routes() - set(REGISTRY)
    assert not missing, (
        f"新端点能按 slug/qid 定位馆或藏品,但没在可见性闸登记簿里表态: {sorted(missing)}。"
        "接上 app.services.visibility 的闸并登记 GATED,或写明为什么不需要。"
    )


def test_registry_has_no_stale_entries():
    """路由删了/改名了,登记簿也要跟着删 —— 否则它会慢慢变成又一份过期清单。"""
    stale = set(REGISTRY) - _locating_routes()
    assert not stale, f"登记簿里的路由已不存在: {sorted(stale)}"


def test_detector_sees_path_query_and_body_params():
    """登记簿的判断力自检:三种定位方式各有一个已知样本必须被认出来。
    否则 detector 坏了,上面两条会因为"什么都没扫到"而一起绿。"""
    found = _locating_routes()
    assert ("GET", "/api/v1/museums/{slug}") in found  # path
    assert ("POST", "/api/v1/entitlements/audio/unlock") in found  # query
    assert ("POST", "/api/v1/recognize/confirm") in found  # body
