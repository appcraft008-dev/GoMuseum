"""逐件材料富化：给一件（qid + 外部ID + wiki 标题）按需路由富化源、抓材料、merge。

= 把 Fetcher 一锅式抓取的「逐件富化」半边抽出，供生成时按需调用（spec §6 列目录/抓材料解耦）。
"""

from __future__ import annotations

import logging

from app.services.enrichment.fetcher import _CORE
from app.services.enrichment.merge import merge_contributions
from app.services.enrichment.sources import wikidata as _wd

logger = logging.getLogger(__name__)


def fetch_object_material(
    qid: str, external_ids: dict, wiki_titles: dict, registry
) -> dict:
    """路由富化源→enrich→merge，返回材料 attributes（剥身份/留痕键）。无贡献→{}。"""
    context = {"wiki_titles": wiki_titles or {}}
    contribs = []
    for src in registry.route(external_ids or {}):
        # 单源失败跳过继续(纪律①)。此前任一源抛异常会一路冒到顶、**炸掉整个
        # generate 运行**——2026-07-27 实测:Joconde 返回非 JSON(200 + 空/HTML body)
        # 使 orsay/orangerie 预热两次全崩,而只用 wikipedia 的 louvre 完好。
        # 少一个源的材料 = 内容薄一点(接地闸自会把关),远好过整馆停摆。
        try:
            c = src.enrich(qid, external_ids or {}, context)
        except Exception:
            logger.warning(
                "source %s failed for %s, skipping this source",
                getattr(src, "name", src),
                qid,
                exc_info=True,
            )
            continue
        if c is not None:
            contribs.append(c)
    if not contribs:
        return {}
    merged = merge_contributions(contribs)
    merged.pop("image_url", None)
    return {k: v for k, v in merged.items() if k not in _CORE}


# 一件作品可以有多条 P170(合作、翻铸、"归于"/"可能出自")。此前三条独立路径
# 各自「取第一个」:fetch_artist_material 取到 A、fetch_artist_facts 取到 B、
# backfill._fetch_creators 取到 C —— 谁都没错,但拼出来的是同一件作品三个作者。
# ⚠️ 更隐蔽的是 fetch_artist_facts 会**逐行合并**:artist_qid 取第一行,生卒/国籍/
# 代表作各取"第一个非空",于是能拼出 A 的 qid + B 的生年。
# 2026-09-03 实例:橘园 Q64309678《静物,梨和青苹果》—— Wikidata 同时挂着
# 塞尚(限定 presumably,引用=橘园官网)与加歇医生(限定 possibly,零引用);
# 管线把加歇的维基传记灌进 artist_extract_*,10 语 78 条正文全在讲"梵高的医生
# 画了这幅静物",而结构化字段是塞尚的生卒年和代表作。
# → 解析一次、传下去。排序键用 Wikidata 自己的不确定性标记,不是随机取首个。
_CREATOR_QUERY = """
SELECT ?artist ?rank ?cert (COUNT(?ref) AS ?refs) WHERE {{
  wd:{qid} p:P170 ?st .
  ?st ps:P170 ?artist ; wikibase:rank ?rank .
  OPTIONAL {{ ?st pq:P1480 ?cert . }}
  OPTIONAL {{ ?st prov:wasDerivedFrom ?ref . }}
}} GROUP BY ?artist ?rank ?cert
"""

_RANK_ORDER = {"PreferredRank": 0, "NormalRank": 1}
# P1480 "sourcing circumstances":无限定=直接断言最强,其次 presumably,再次 possibly。
# 未知限定词按最弱处理(宁可信有标记的那条更不确定)。
_CERT_ORDER = {None: 0, "Q18122778": 1, "Q30230067": 3}
_CERT_UNKNOWN = 2


def creator_candidate(row, *, var="artist"):
    """P170 语句行 → (排序键, 作者QID);blank node / deprecated rank → None。

    单件版(resolve_creator_qid)与批量版(backfill._fetch_creators)共用同一把尺子 ——
    两处各写一份排序规则,就是本 bug 的翻版。
    """
    from app.services.enrichment.identity import is_wikidata_qid

    aq = (row.get(var) or {}).get("value", "").rsplit("/", 1)[-1]
    if not is_wikidata_qid(aq):
        # P170="未知值" 时 Wikidata 返回 blank node(.well-known/genid/<hex>),
        # rsplit 会把哈希当作者 QID → 建出一堆假作者(卢浮宫 4642 件实测崩过)。
        return None
    rank = (row.get("rank") or {}).get("value", "").rsplit("#", 1)[-1]
    if rank == "DeprecatedRank":
        return None
    cert = (row.get("cert") or {}).get("value", "").rsplit("/", 1)[-1] or None
    try:
        refs = int((row.get("refs") or {}).get("value") or 0)
    except ValueError:
        refs = 0
    key = (
        _RANK_ORDER.get(rank, 2),
        _CERT_ORDER.get(cert, _CERT_UNKNOWN),
        -refs,
        int(aq[1:]),  # 全部打平时按 QID 定序,保证跨次运行可复现
    )
    return key, aq


def resolve_creator_qid(qid, *, run_query=None) -> str | None:
    """作品 QID → **唯一**作者 QID。多值时按 (rank, 不确定性限定词, 引用数) 择优。

    全流程只应调这一次,结果传给 fetch_artist_facts / fetch_artist_material。
    无作者、或 P170 是"未知值"(blank node)→ None(宁缺毋滥,不猜)。
    """
    run_query = run_query or _default_artist_query
    cands = [
        c
        for c in (
            creator_candidate(r)
            for r in run_query(_CREATOR_QUERY.format(qid=qid)) or []
        )
        if c
    ]
    return min(cands)[1] if cands else None


_ARTIST_QUERY = """
SELECT ?al_en ?al_cl WHERE {{
  wd:{qid} wdt:P170 ?artist .
  OPTIONAL {{ ?a_en schema:about ?artist ; schema:isPartOf <https://en.wikipedia.org/> ; schema:name ?al_en . }}
  OPTIONAL {{ ?a_cl schema:about ?artist ; schema:isPartOf <https://{cl}.wikipedia.org/> ; schema:name ?al_cl . }}
}} LIMIT 1
"""

# artist_qid 已由 resolve_creator_qid 定好时走这条:直接问作者实体,不再跳 P170。
_ARTIST_TITLES_QUERY = """
SELECT ?al_en ?al_cl WHERE {{
  OPTIONAL {{ ?a_en schema:about wd:{aqid} ; schema:isPartOf <https://en.wikipedia.org/> ; schema:name ?al_en . }}
  OPTIONAL {{ ?a_cl schema:about wd:{aqid} ; schema:isPartOf <https://{cl}.wikipedia.org/> ; schema:name ?al_cl . }}
}} LIMIT 1
"""


def _default_artist_query(sparql):
    import requests

    r = requests.get(
        _wd.SPARQL_ENDPOINT,
        params={"query": sparql, "format": "json"},
        headers={
            "User-Agent": _wd.USER_AGENT,
            "Accept": "application/sparql-results+json",
        },
        timeout=60,
    )
    r.raise_for_status()
    return r.json()["results"]["bindings"]


def _is_raw_qid(v: str) -> bool:
    """wikibase:label 对无本地化标签的实体退回原始 QID/PID(如 'Q17490760')。"""
    return bool(v) and v[0] in "QP" and v[1:].isdigit()


# 同上:作者已定则直接问作者实体。走 P170 版本时多作者会**逐行串味**
# (artist_qid 来自 A、生年来自 B),这正是 Q64309678 的病灶之一。
_ARTIST_FACTS_BY_ARTIST_QUERY = """
SELECT ?birth ?death ?natLabel ?workLabel WHERE {{
  OPTIONAL {{ wd:{aqid} wdt:P569 ?birth. }}
  OPTIONAL {{ wd:{aqid} wdt:P570 ?death. }}
  OPTIONAL {{ wd:{aqid} wdt:P27 ?nat. }}
  OPTIONAL {{ wd:{aqid} wdt:P800 ?work. }}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
}}
"""

_ARTIST_FACTS_QUERY = """
SELECT ?artist ?birth ?death ?natLabel ?workLabel WHERE {{
  wd:{qid} wdt:P170 ?artist .
  OPTIONAL {{ ?artist wdt:P569 ?birth. }}
  OPTIONAL {{ ?artist wdt:P570 ?death. }}
  OPTIONAL {{ ?artist wdt:P27 ?nat. }}
  OPTIONAL {{ ?artist wdt:P800 ?work. }}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
}}
"""


def fetch_artist_facts(qid, *, run_query=None, artist_qid=None) -> dict:
    """作者 Wikidata 实体结构化属性 → {artist_birth/death/nationality/notable_works}。无→{}。

    artist_qid 已由 resolve_creator_qid 定好时直接问该实体 —— 多作者作品必须走这条,
    否则字段会跨作者串味。不传则退回 P170 遍历(兼容老调用点)。
    """
    run_query = run_query or _default_artist_query
    if artist_qid:
        rows = run_query(_ARTIST_FACTS_BY_ARTIST_QUERY.format(aqid=artist_qid))
    else:
        rows = run_query(_ARTIST_FACTS_QUERY.format(qid=qid))
    if not rows:
        return {"artist_qid": artist_qid} if artist_qid else {}
    out = {"artist_qid": artist_qid} if artist_qid else {}
    works = []
    for row in rows:
        b = (row.get("birth") or {}).get("value")
        d = (row.get("death") or {}).get("value")
        nat = (row.get("natLabel") or {}).get("value")
        w = (row.get("workLabel") or {}).get("value")
        # 标签服务对无本地化标签的实体退回原始 QID → 无意义,跳过
        if nat and _is_raw_qid(nat):
            nat = None
        if w and _is_raw_qid(w):
            w = None
        if "artist_qid" not in out:
            au = (row.get("artist") or {}).get("value", "")
            if au:
                out["artist_qid"] = au.rsplit("/", 1)[-1]
        if b and "artist_birth" not in out:
            out["artist_birth"] = b[:4]
        if d and "artist_death" not in out:
            out["artist_death"] = d[:4]
        if nat and "artist_nationality" not in out:
            out["artist_nationality"] = nat
        if w and w not in works:
            works.append(w)
    if works:
        out["artist_notable_works"] = works[:5]
    return out


_LABELS_QUERY = """
SELECT ?l WHERE {{ wd:{qid} rdfs:label ?l . FILTER(lang(?l) IN ({langs})) }}
"""

# 批量版:一次查一批实体的标签。上大馆的硬前提——单件版是 N+1,卢浮宫 17283 件
# = 17283 次串行 SPARQL(实测 ~5h,CPU 只占 12%,全在等网络)。
_LABELS_BATCH_QUERY = """
SELECT ?item ?l WHERE {{ VALUES ?item {{ {values} }} ?item rdfs:label ?l .
  FILTER(lang(?l) IN ({langs})) }}
"""
_LABELS_BATCH = 200  # 与 _CREATORS_BATCH 同量级(URL 长度与 WDQS 超时的折中)


# 字形变体语言:同一语言不同字形,可逐字确定性 OpenCC 转换(区别于独立语言 ca/pt——
# 那些要真翻译)。lang → (Wikidata 标签变体优先序, OpenCC 方向)。
# 加变体语言=加一行;非变体语言不在表里、走默认路径不受影响。
_SCRIPT_VARIANTS = {
    "zh": (("zh-hans", "zh-cn", "zh"), "t2s"),  # 收敛简体
    # ⚠️ zh-hk 排在 zh 之后是**故意的**:港式音译是粤语拼读的另一套传统
    # (Cézanne→施傘 / Giorgione→佐助彌 / Christoffer→基斯杜化),把它排在 zh 前面
    # 等于"宁可要另一个传统的音译,也不要本传统的简体转繁"。实测 Q35548 无
    # zh-hant/zh-tw 标签 → 旧序取 zh-hk 得「保羅·施傘」,新序取 zh 转繁得「保羅·塞尚」。
    # 仍留在链尾:当它是唯一的中文标签时,人工标签好过机翻兜底。
    "zh-hant": (
        ("zh-hant", "zh-tw", "zh", "zh-hans", "zh-cn", "zh-hk"),
        "s2t",
    ),  # 繁体优先,简体兜底再转,港式垫底
}

_opencc: dict = {}


def _variant_convert(lang: str, s: str) -> str:
    """字形变体语言按其方向 OpenCC 转换;非变体语言原样返回。确定性,不用 LLM。"""
    conf = _SCRIPT_VARIANTS.get(lang)
    if not conf or not s:
        return s
    direction = conf[1]
    if direction not in _opencc:
        from opencc import OpenCC

        _opencc[direction] = OpenCC(direction)
    return _opencc[direction].convert(s)


def to_simplified(s: str) -> str:
    """繁→简薄包装(向后兼容;一次性脚本仍在用)。"""
    return _variant_convert("zh", s)


def fetch_wikidata_labels(qid: str, langs: list, *, run_query=None) -> dict:
    """Wikidata 实体在 langs 的官方标签 → {lang: label}(只含有的)。
    zh 按 zh-hans > zh-cn > zh 取(修繁简混杂:愛德華·馬奈类)。
    非 Wikidata 对外把手(joconde-<ref> 等)→ 直接 {}(无真 QID,names 回退机翻 title_en)。"""
    from app.services.enrichment.identity import is_wikidata_qid

    if not is_wikidata_qid(qid):
        return {}
    run_query = (
        run_query or _default_artist_query
    )  # ponytail: same generic SPARQL caller
    langlist = ", ".join('"%s"' % x for x in _query_langs(langs))
    rows = run_query(_LABELS_QUERY.format(qid=qid, langs=langlist))
    raw: dict = {}
    for row in rows:
        lv = row.get("l") or {}
        lang = lv.get("xml:lang") or lv.get("lang")
        val = lv.get("value")
        if lang and val and lang not in raw:
            raw[lang] = val
    return _collapse_variants(raw, langs)


def _query_langs(langs: list) -> list:
    """目标语言 + 各自的字形变体(zh 要连 zh-hans/zh-cn 一起查)。"""
    out = list(langs)
    for lang in langs:
        if lang in _SCRIPT_VARIANTS:
            out += [v for v in _SCRIPT_VARIANTS[lang][0] if v not in out]
    return out


def _collapse_variants(raw: dict, langs: list) -> dict:
    """原始 {语言变体: 标签} → {目标语言: 标签}。单件版与批量版共用同一语义。"""
    out = {}
    for lang in langs:
        if lang in _SCRIPT_VARIANTS:
            for v in _SCRIPT_VARIANTS[lang][0]:
                if raw.get(v):
                    # 变体标签逐字转到目标字形(hans→hant 或反;同字形转换是无害幂等)
                    out[lang] = _variant_convert(lang, raw[v])
                    break
        elif raw.get(lang):
            out[lang] = raw[lang]
    return out


def fetch_wikidata_labels_batch(qids, langs: list, *, run_query=None) -> dict:
    """批量版:{qid: {lang: label}}(只含查到的)。语义与单件版逐字一致,只是把
    N 次网络往返压成 N/200 次——上万件大馆的硬前提(卢浮宫单件版跑了 ~5h)。
    非 Wikidata 把手直接跳过;单批失败重试一次仍败则跳过该批(幂等重跑再补)。"""
    import logging
    import time

    from app.services.enrichment.identity import is_wikidata_qid

    real = [q for q in dict.fromkeys(qids) if is_wikidata_qid(q)]
    if not real:
        return {}
    run_query = run_query or _default_artist_query
    langlist = ", ".join('"%s"' % x for x in _query_langs(langs))
    raw_by_qid: dict = {}
    for i in range(0, len(real), _LABELS_BATCH):
        batch = real[i : i + _LABELS_BATCH]
        sparql = _LABELS_BATCH_QUERY.format(
            values=" ".join(f"wd:{q}" for q in batch), langs=langlist
        )
        rows = None
        for attempt in (1, 2):
            try:
                rows = run_query(sparql)
                break
            except Exception:
                if attempt == 1:
                    time.sleep(5)
                else:
                    logging.getLogger(__name__).exception(
                        "labels batch failed, skip %d qids", len(batch)
                    )
        for row in rows or []:
            q = (row.get("item") or {}).get("value", "").rsplit("/", 1)[-1]
            lv = row.get("l") or {}
            lang, val = (lv.get("xml:lang") or lv.get("lang")), lv.get("value")
            if q and lang and val:
                raw_by_qid.setdefault(q, {}).setdefault(lang, val)
    return {q: _collapse_variants(raw, langs) for q, raw in raw_by_qid.items()}


def fetch_artist_material(
    qid, registry, *, run_query=None, country_lang="fr", artist_qid=None
) -> dict:
    """抓作者实体 Wikipedia(作者→维基标题→extract)。无作者/无维基→{}。

    artist_qid 已定则直接问该实体;不传则退回作品→P170 遍历(兼容老调用点)。
    """
    run_query = run_query or _default_artist_query
    cl = country_lang or "fr"
    if artist_qid:
        rows = run_query(_ARTIST_TITLES_QUERY.format(aqid=artist_qid, cl=cl))
    else:
        rows = run_query(_ARTIST_QUERY.format(qid=qid, cl=cl))
    if not rows:
        return {}
    row = rows[0]
    titles = {}
    se = (row.get("al_en") or {}).get("value")
    if se:
        titles["en"] = se.rsplit("/", 1)[-1]
    scl = (row.get("al_cl") or {}).get("value")
    if scl:
        titles[country_lang or "fr"] = scl.rsplit("/", 1)[-1]
    if not titles:
        return {}
    wiki = registry.get("wikipedia")
    if wiki is None:
        return {}
    contrib = wiki.enrich(qid, {}, {"wiki_titles": titles})
    if contrib is None:
        return {}
    return {
        f"artist_{k}": v
        for k, v in contrib.fields.items()
        if k.startswith("extract_") and v
    }


_ARTIST_I18N_FACTS_QUERY = """
SELECT ?natLabel ?work ?workLabel WHERE {{
  OPTIONAL {{ wd:{qid} wdt:P27 ?nat . ?nat rdfs:label ?natLabel .
             FILTER(lang(?natLabel) IN ({langs})) }}
  OPTIONAL {{ wd:{qid} wdt:P800 ?work . ?work rdfs:label ?workLabel .
             FILTER(lang(?workLabel) IN ({langs})) }}
}}
"""


def authoritative_work_label(labels: dict, lang: str) -> str | None:
    """一件作品在某语言下的**权威**显示名:本语言标签 → 字形变体链(繁体取简体转)。
    都没有 → None,由调用方决定是翻译还是回退原文(见 fill_artist_i18n_facts)。"""
    if labels.get(lang):
        return labels[lang]
    for src in (_SCRIPT_VARIANTS.get(lang) or ((), None))[0]:
        if labels.get(src):
            return _variant_convert(lang, labels[src])
    return None


def _pick_work_label(labels: dict, lang: str) -> str | None:
    """权威名,没有就回退英文/原名。**纯数据层的兜底** —— 拿不到翻译器的调用方
    (pipeline 直接用 fetch 结果)至少能拿到同一批作品,而不是整件缺席。"""
    return (
        authoritative_work_label(labels, lang)
        or labels.get("en")
        or next(iter(labels.values()), None)
    )


def fetch_artist_i18n_facts(artist_qid, langs, *, run_query=None) -> dict:
    """作者国籍(P27)/代表作(P800)的多语权威标签(交接③:作者卡本地化)。
    单查询 rdfs:label 语言过滤(同 _LABELS_QUERY 款,一作者一查)。
    返回 {"nationality_i18n": {lang: label}, "notable_works_i18n": {lang: [labels]}}。
    代表作**先选作品集合再逐语言取标签**,所以各语言列的是同一批作品、长度一致;
    国籍无标签的语言仍缺席(由调用方翻译兜底)。"""
    run_query = run_query or _default_artist_query
    # 变体语言要连它的兜底源一起取:zh-hant 的链里有 zh,若只按 langs 过滤,
    # 请求 zh-hant 而没请求 zh 时链就断了、只能掉到英文。
    wanted = list(
        dict.fromkeys(
            [*langs, *(v for x in langs for v in (_SCRIPT_VARIANTS.get(x) or ((),))[0])]
        )
    )
    langlist = ", ".join('"%s"' % x for x in wanted)
    rows = run_query(_ARTIST_I18N_FACTS_QUERY.format(qid=artist_qid, langs=langlist))
    nat_i18n: dict = {}
    works: dict = {}  # 作品 qid -> {lang: label}
    for row in rows:
        nl = row.get("natLabel") or {}
        wl = row.get("workLabel") or {}
        nlang, nv = nl.get("xml:lang") or nl.get("lang"), nl.get("value")
        wlang, wv = wl.get("xml:lang") or wl.get("lang"), wl.get("value")
        if nv and nlang in langs and not _is_raw_qid(nv) and nlang not in nat_i18n:
            nat_i18n[nlang] = _variant_convert(nlang, nv)
        wq = ((row.get("work") or {}).get("value") or "").rsplit("/", 1)[-1]
        if wq and wv and wlang in wanted and not _is_raw_qid(wv):
            works.setdefault(wq, {}).setdefault(wlang, _variant_convert(wlang, wv))
    # ⚠️ 先选作品(语言无关)、再逐语言取标签。此前是每个语言各自 append 再各自 [:5] ——
    # 于是**不同语言展示的是不同的画**,不是同一批的不同译名。实测莫迪利亚尼:
    # P800 十语共 10 件,西语那 4 幅和英语那 5 幅没有交集,用户换个 App 语言
    # 作者卡就换了一批作品。排序判据:被这些语言标注得最全的排前(近似"最知名"),
    # 同分按 qid 稳定排 —— 必须与语言无关,否则又回到各挑各的。
    top = sorted(works.items(), key=lambda kv: (-len(kv[1]), kv[0]))[:5]
    works_i18n: dict = {}
    for lang in langs:
        vals = [v for v in (_pick_work_label(ls, lang) for _, ls in top) if v]
        if vals:
            works_i18n[lang] = vals
    return {
        "nationality_i18n": nat_i18n,
        "notable_works_i18n": works_i18n,
        # 逐件的原始标签(有序,与上面各语言列表一一对应)。调用方靠它分辨
        # "这一件本来就有权威译名"和"这一件是回退的英文名,该翻" —— 只比对
        # 字符串猜不出来(法语的 Olympia 就等于英语的 Olympia)。
        "notable_works_labels": [ls for _, ls in top],
    }


def fetch_museum_intro_material(qid: str, *, get_json=None) -> dict:
    """馆级接地材料(spec 2026-07-18):qid → enwiki sitelink → en 全文 extract。
    馆没有对象级 wiki_titles 管道,故独立小抓取。get_json 注入可测;失败返 extract_en=None
    (调用方宁缺毋滥 skip)。"""
    if get_json is None:
        import requests

        def get_json(url, params):
            r = requests.get(
                url,
                params=params,
                headers={
                    "User-Agent": "GoMuseumBot/0.1 (contact appcraft008@gmail.com)"
                },
                timeout=30,
            )
            r.raise_for_status()
            return r.json()

    try:
        ent = get_json(
            "https://www.wikidata.org/w/api.php",
            {
                "action": "wbgetentities",
                "ids": qid,
                "props": "sitelinks",
                "format": "json",
            },
        )
        title = (
            ent.get("entities", {}).get(qid, {}).get("sitelinks", {}).get("enwiki", {})
        ).get("title")
        if not title:
            return {"extract_en": None}
        data = get_json(
            "https://en.wikipedia.org/w/api.php",
            {
                "action": "query",
                "prop": "extracts",
                "explaintext": 1,
                "format": "json",
                "titles": title,
            },
        )
        pages = data.get("query", {}).get("pages", {})
        extract = next(iter(pages.values()), {}).get("extract") or None
        return {"extract_en": extract[:8000] if extract else None}
    except Exception:
        return {"extract_en": None}


_BUILDING_PHOTO_QUERY = "SELECT ?img WHERE {{ wd:{qid} wdt:P18 ?img . }} LIMIT 1"


def fetch_museum_building_photo(qid: str, *, run_query=None) -> str | None:
    """馆自身(非藏品)P18 建筑外观照(spec 2026-07-20 museum-cover-intro-quality)。
    SPARQL wdt:P18 绑定即完整 Commons Special:FilePath URL,可直接下载。无→None。"""
    from app.services.enrichment.identity import is_wikidata_qid

    if not is_wikidata_qid(qid):
        return None
    run_query = run_query or _default_artist_query
    rows = run_query(_BUILDING_PHOTO_QUERY.format(qid=qid))
    for row in rows:
        v = (row.get("img") or {}).get("value")
        if v:
            return v
    return None
