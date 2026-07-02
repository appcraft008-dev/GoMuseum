"""源注册表 + 外部 ID 路由：读对象 Wikidata 外部 ID → 自动选适用连接器(零管理员配置)。"""

from __future__ import annotations


class SourceRegistry:
    def __init__(self, sources: list):
        self._sources = list(sources)

    def route(self, external_ids: dict) -> list:
        """返回 probe(external_ids) 为真的源(按注册顺序)。"""
        return [s for s in self._sources if s.probe(external_ids)]

    def get(self, name: str):
        for s in self._sources:
            if getattr(s, "name", None) == name:
                return s
        return None


def build_registry(names: list[str], *, session) -> SourceRegistry:
    """按 museums.yaml 的 sources 名单实例化连接器。未知名 → KeyError(配置错误早炸)。"""
    from app.services.enrichment.sources.joconde import JocondeSource
    from app.services.enrichment.sources.wikipedia import WikipediaSource

    builders = {
        "joconde": lambda: JocondeSource(session=session),
        "wikipedia": lambda: WikipediaSource(session=session),
    }
    return SourceRegistry([builders[n]() for n in names])
