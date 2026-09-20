"""JocondeCatalog：从 Joconde 开放数据整包 CSV 里筛出该馆全部作品 → StubRecord。
补 Wikidata 对纸上作品(粉彩/素描)的覆盖偏科(实证:Wikidata 收奥赛纸上仅 167,
Joconde 有 434 素描)。多为 © RMN 版权图、无免费图 → 落文字层 stub(可搜、不可拍)。
去重靠 Joconde reference(P347)+ 馆藏号,不覆盖既有 Wikidata 件(见 catalog_loader.filter_new_stubs)。"""

from __future__ import annotations

import csv
import re
import time
from typing import Iterable

from app.services.enrichment.catalog_source import CatalogSource, StubRecord

# 整包 CSV(约 1.2GB,`|` 分隔,68 字段,多值用 `;`)。
#
# ⚠️ 2026-09-20 起这是唯一通道。原先的 opendatasoft 查询 API
# (data.culture.gouv.fr)已**整站 301** 到 culture.data.gouv.fr,而且重定向
# **把路径也丢了** —— 任何 API 路径都落到首页、返回 HTML 且 status **200**,
# 于是 `status_code != 200` 那道判断形同虚设,一路崩在 resp.json() 上。
#
# 换通道顺带解掉一个老限制:opendatasoft 的 limit+offset ≤ 10000 让大馆
# 最多只能拿 9900 条(原 `_MAX_OFFSET`),整包 CSV 没有这个天花板。
_CSV_URL = "https://ministere-culture.s3.sbg.io.cloud.ovh.net/POP/joconde.csv"
_UA = "GoMuseumEnrichment/1.0 (appcraft008@gmail.com)"
_MUSEUM_COL = "Nom_officiel_musee"

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


def _norm_museum(raw: str | None) -> str:
    """馆名比对用的归一化:折叠空白 + casefold。

    整包 CSV 是全法国的馆,没有服务端筛选了,**过滤漏一点就少一批件**,
    而且少得很安静(看起来像"这馆藏品就这么多")。编目里同一个馆出现
    大小写/多空格变体是常事,所以不做字面相等。

    仍是**精确相等**不是子串匹配 —— 子串会把"musée d'Orsay - annexe"
    这类另一个馆误收进来。
    """
    return " ".join((raw or "").split()).casefold()


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
    """CSV 的 `Domaine` 是 `;` 分隔的**字符串**(旧 API 给的是 list)。

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


def _default_http_get(url, headers=None, timeout=None):
    import requests

    time.sleep(0.2)  # 礼貌限速(公共开放数据)
    # stream=True:1.2GB 整包,必须边下边过滤,不能 .content 进内存。
    return requests.get(url, headers=headers, timeout=timeout, stream=True)


class JocondeCatalog(CatalogSource):
    name = "joconde"

    def __init__(self, http_get=None):
        self._http_get = http_get or _default_http_get

    def list(self, cfg) -> Iterable[StubRecord]:
        museum = getattr(cfg, "joconde_museum", None)
        if not museum:
            return
        resp = self._http_get(
            _CSV_URL,
            headers={"User-Agent": _UA, "Accept": "text/csv"},
            timeout=60,
        )
        status = getattr(resp, "status_code", 200)
        if status != 200:
            raise RuntimeError(f"Joconde CSV 不可用(HTTP {status}):{_CSV_URL}")

        rows = csv.DictReader(resp.iter_lines(decode_unicode=True), delimiter="|")
        if _MUSEUM_COL not in (rows.fieldnames or ()):
            # 拿到的不是那份 CSV(重定向到门户首页、被改版、被换 schema)。
            # 不报出来的话下面那个循环会安静地一条不匹配,看起来像"这馆没有藏品"。
            raise RuntimeError(
                f"Joconde CSV 缺列 {_MUSEUM_COL},拿到的不是预期的那份数据"
                f"(表头:{(rows.fieldnames or ['<空>'])[:3]}…)。源可能又搬家了:"
                f"去 data.gouv.fr 的 collections-des-musees-de-france-base-joconde "
                f"查当前资源地址。"
            )

        want = _norm_museum(museum)
        for rec in rows:
            # 按馆名过滤:整包是全法国的馆,没有服务端筛选了。
            if _norm_museum(rec.get(_MUSEUM_COL)) != want:
                continue
            s = _to_stub(rec, cfg.slug)
            if s:
                yield s
