"""JocondeCatalog：按馆名分页查 Joconde 开放数据 → 该馆全部作品 StubRecord。
补 Wikidata 对纸上作品(粉彩/素描)的覆盖偏科(实证:Wikidata 收奥赛纸上仅 167,
Joconde 有 434 素描)。多为 © RMN 版权图、无免费图 → 落文字层 stub(可搜、不可拍)。
去重靠 Joconde reference(P347)+ 馆藏号,不覆盖既有 Wikidata 件(见 catalog_loader.filter_new_stubs)。

⚠️ 2026-09 换过接入方式,与 `JocondeSource`(富化源)**同一条通道、同一份资源** ——
见那边的模块 docstring(断供时间线、公告日≠断供日)。这里只补目录侧的:
旧 opendatasoft 的 `limit+offset ≤ 10000` 天花板(原 `_MAX_OFFSET=9900`)没有了,
Tabular API 深翻页正常(奥赛 4111 条实测翻到第 42 页)。
"""

from __future__ import annotations

import re
import time
from typing import Iterable

from app.services.enrichment.catalog_source import CatalogSource, StubRecord
from app.services.enrichment.sources.joconde import TABULAR_URL, resolve_resource_id

_UA = "GoMuseumEnrichment/1.0 (appcraft008@gmail.com)"
_MUSEUM_COL = "Nom_officiel_musee"
_PAGE = 200  # Tabular API 的 page_size 上限(超过直接 400)

# `Millesime_de_creation` 归一化。Joconde 把创作年和法语精度词**反序**拼在
# 一起:`1853 vers`(约1853)、`1865 entre,1908 et`、`1911 vers,1912 ou,1914 et`。
# 源数据本身就长这样(已核对官方 CSV 与库里三条记录一致),不是中间平台加工的
# —— 所以清洗必须在入库这一步做,否则脏值会进 LLM 材料
# (`pipeline.py` 把 year 当 "Creation year" 喂给模型)。
#
# 这里只做**语言中立**的形态;`avant`/`après` 要按界面语言渲染,
# 后端没有语言维度,留给前端 `year_format.dart`(规则与这里成对,改一边要改另一边)。
# 尾部 `N tirage` 是**印制年**不是创作年,丢掉是归位不是丢信息。
_MILL_RULES = (
    (re.compile(r"^(\d+) vers$"), lambda m: f"c. {m[1]}"),
    (re.compile(r"^(\d+) vers,\d+ tirage$"), lambda m: f"c. {m[1]}"),
    (re.compile(r"^(\d+) entre,(\d+) et$"), lambda m: f"{m[1]}–{m[2]}"),
    (re.compile(r"^(\d+) entre,(\d+) et,\d+ tirage$"), lambda m: f"{m[1]}–{m[2]}"),
    (re.compile(r"^(\d+)-(\d+)$"), lambda m: f"{m[1]}–{m[2]}"),
)

_DATES = re.compile(r"\s*\([^)]*\)\s*$")  # 作者尾部"(1844-1926)"
_DOMAINE_CAT = {
    "peinture": "painting",
    "sculpture": "sculpture",
    "dessin": "works_on_paper",
    "estampe": "works_on_paper",
    "aquarelle": "works_on_paper",
    "pastel": "works_on_paper",
    "photographie": "photography",
}


def _clean_inv(raw: str | None) -> str | None:
    """取首个馆藏号:'RF 2051, recto'→'RF 2051';'RF 1977 444 ; LUX 1051 P'→'RF 1977 444'
    (多号/recto-verso 后缀切掉,取第一个;否则整串归一化后与 Wikidata 号对不上、去重失效)。"""
    if not raw:
        return None
    return re.split(r"[;,]", raw)[0].strip() or None


def _clean_artist(raw: str | None) -> str | None:
    """'Cassatt Mary (1844-1926)' → 'Cassatt Mary'(去生卒;姓名序保留源样,不冒险重排)。"""
    if not raw:
        return None
    return _DATES.sub("", raw).strip() or None


def _clean_title(raw: str | None) -> str | None:
    """取首个题名(去' OU 别名'/'; dit aussi');Joconde 全大写 → 句首大写。
    en 列存法文题,names 回填时机翻补多语显示名(同无 qid 冷门件路径)。"""
    if not raw:
        return None
    t = re.split(r"\s+OU\s+", raw, maxsplit=1)[0]
    t = t.split(" ; ")[0].strip()
    if t.isupper():
        t = t.capitalize()
    return t or None


def _clean_year(raw: str | None) -> str | None:
    """`Millesime_de_creation` → 语言中立年代。表外形态原样返回。

    见 `_MILL_RULES`。猜出来的年代比读着别扭的年代糟糕得多,所以只收
    能确定语义的形态 —— `1867 vers,1868 ou`(约1867**或**1868)压成区间
    是改写原意,不做。
    """
    if not raw:
        return None
    t = raw.strip()
    for pat, render in _MILL_RULES:
        m = pat.match(t)
        if m:
            return render(m)
    return t or None


def _category(domaine) -> str:
    """`Domaine` 现在是 `;` 分隔的**字符串**(旧 opendatasoft API 给的是 list)。

    ⚠️ 传字符串给下面这个循环会**逐字符**遍历、全部落到 "unknown" 且不报错
    —— 换通道时最容易静默踩的一脚,所以在这里统一拆。
    """
    if isinstance(domaine, str):
        domaine = domaine.split(";")
    for d in domaine or []:
        c = _DOMAINE_CAT.get(str(d).strip().lower())
        if c:
            return c
    return "unknown"


def _to_stub(rec: dict, slug: str) -> StubRecord | None:
    """一条 Joconde 记录 → StubRecord。无馆藏号或无 reference(无法幂等去重/合成把手)→ None。
    非 Wikidata 作品:对外把手 qid 合成为 `joconde-<ref>`(命名空间防撞车、非 Q 格式,让它
    可搜/可导航/可懒生成而不误入 Wikidata SPARQL);真实身份仍是对象 UUID。"""
    inv = _clean_inv(rec.get("Numero_inventaire"))
    ref = rec.get("Reference")
    if not inv or not ref:
        return None
    return StubRecord(
        inventory_number=inv,
        qid=f"joconde-{ref}",
        title=_clean_title(rec.get("Titre")),
        artist=_clean_artist(rec.get("Auteur")),
        year=_clean_year(rec.get("Millesime_de_creation")),
        category=_category(rec.get("Domaine")),
        image_url=None,  # © RMN 版权图,无免费图 → 文字层
        popularity=0,
        owning_museum=slug,
        source="joconde",
        raw={"reference": ref},
        external_ids={"P347": ref} if ref else {},
    )


def _default_get_json(url, params=None):
    import requests

    time.sleep(0.2)  # 礼貌限速(公共开放数据)
    r = requests.get(
        url,
        params=params,
        headers={"User-Agent": _UA, "Accept": "application/json"},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


class JocondeCatalog(CatalogSource):
    name = "joconde"

    def __init__(self, get_json=None):
        self._get_json = get_json or _default_get_json

    def list(self, cfg) -> Iterable[StubRecord]:
        museum = getattr(cfg, "joconde_museum", None)
        if not museum:
            return
        # 资源 id 按 dataset slug 解析(文件重传时 id 会变,slug 不会),
        # 与 JocondeSource 共用那份进程内缓存。
        rid = resolve_resource_id(self._get_json)
        url = TABULAR_URL.format(rid=rid)

        page, seen = 1, 0
        while True:
            data = self._get_json(
                url,
                {
                    f"{_MUSEUM_COL}__exact": museum,
                    "page": page,
                    "page_size": _PAGE,
                },
            )
            # ⚠️ 出错时这个 API 返回的是 {"errors": [...]},**没有 data 键**。
            # 不认它的话下面 `or []` 会把报错读成"这个馆没有藏品"——
            # 静默少一批件是这条链路最难查的失败(同纪律 31)。
            if "data" not in data:
                raise RuntimeError(
                    f"Joconde 表格 API 返回错误(page={page}, museum={museum!r}):"
                    f"{data.get('errors') or data}"
                )
            rows = data["data"] or []
            total = (data.get("meta") or {}).get("total")
            for rec in rows:
                stub = _to_stub(rec, cfg.slug)
                if stub:
                    yield stub
            seen += len(rows)

            # 终止**以 meta.total 为准**,不看 `len(rows) < _PAGE`:
            # 服务端若把 page_size 钳到比我们请求的更小(它有权这么做),
            # 那个判断会在第一页就误判成末页 —— 静默少一批件。
            if total is None:
                if len(rows) < _PAGE:
                    break
            elif seen >= total:
                break
            elif not rows:
                # total 说还有,却给了空页 —— 漏页/源在翻页中途变了。
                # 不喊出来就是安静地少一批件(同纪律 31)。
                raise RuntimeError(
                    f"Joconde 分页对不上:拉到 {seen} 行,meta.total={total}"
                    f"(museum={museum!r})"
                )
            page += 1
