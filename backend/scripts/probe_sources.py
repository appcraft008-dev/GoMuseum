"""外部富化源探活:每天问一次"这几个源还活着吗",死了就非零退出让人看见。

为什么需要:material.py 的单源容错(纪律①)会把任何一个源的异常降级成一条 warning
然后继续 —— 这是对的,少一个源远好过整馆停摆。但代价是**源死掉不是一次故障,
而是内容悄悄变薄**。2026 年 Joconde 就是这么死的:老 API 7-22 断供,日志里只多了
些 warning,没有任何东西变红,**整整两个月没人发现**,期间生成的内容全少一路材料。
推送式的报错不会来,所以只能主动去问。

⚠️ 探针**走真正的 source.enrich()**,不自己拼 HTTP 请求。
自己拼的探针会和生产代码漂移:上游改列名时探针照样 200 绿着,而 enrich 拿到一堆
None。走真链路 + 断言关键字段非空,才能同时探到"域名死了"和"字段名改了"两种死法
—— 后者正是 tabular API 的现实风险(官方标 beta,且与源 CSV 强耦合,
见 datagouv issue #1861)。

金标样本挑的是各馆镇馆之宝(蒙娜丽莎),下架风险最低;它要是真没了,
那确实该有人来看一眼。

⚠️ **同一个上游可能有多个接入点,探针要逐个覆盖**。Joconde 就有两个:
`JocondeSource`(富化,按件查)和 `JocondeCatalog`(目录,按馆拉全量)。
2026-09 修富化源时只看了富化那侧,目录源在同一次断供里也坏着 —— 探针没覆盖它,
所以"修好了"的结论少了一半。目录源现在失败会抛 RuntimeError 而不是静默,
但那只在上新馆时才触发,平时照样没人看见。

    python scripts/probe_sources.py              # 探活
    python scripts/probe_sources.py --self-test  # 自检:喂坏输入,断言探针会喊 FAIL

退出码:0 = 全活   1 = 有源探不通   2 = 自检没通过(探针自己坏了,探活结果不可信)
"""

import argparse
import sys

sys.path.insert(0, "/app")

UA = "GoMuseumBot/0.1 (https://gomuseum.app; contact appcraft008@gmail.com)"

# 蒙娜丽莎:qid / Joconde Reference / 维基标题
GOLDEN_QID = "Q12418"
GOLDEN_P347 = "000PE025604"
GOLDEN_TITLES = {"en": "Mona Lisa", "fr": "Joconde"}

# 目录源金标:橘园。四馆里配了 joconde_museum 的最小的一个(2026-09-20 实测 133 条,
# 奥赛 4111 条要 21 秒)。探活是定时跑的,挑小的那个。
GOLDEN_CATALOG_SLUG = "orangerie"
GOLDEN_CATALOG_MIN = 120  # 实测 133;留出上游正常增删的余量,但认得出"掉成个位数"


def _session():
    from app.services.enrichment.http_client import PoliteSession

    return PoliteSession(user_agent=UA, min_interval=1.0)


def probe_joconde(p347: str = GOLDEN_P347) -> str:
    """→ 说明串;任何问题抛异常。"""
    from app.services.enrichment.sources.joconde import JocondeSource

    c = JocondeSource(session=_session()).enrich(GOLDEN_QID, {"P347": p347}, {})
    if c is None:
        raise RuntimeError(f"ref {p347} 查无此件(上游数据集可能换了主键或掉了行)")
    # 这两个字段撑着展签面板;它们空掉 = 列名变了,比整个源死掉更难发现
    for key in ("title_fr", "medium_fr"):
        if not c.fields.get(key):
            raise RuntimeError(f"字段 {key} 为空(上游列名可能已改)")
    return f"{c.fields['title_fr']} / {c.fields['medium_fr'][:40]}"


def probe_joconde_catalog(
    slug: str = GOLDEN_CATALOG_SLUG, museum: str | None = None
) -> str:
    """目录源:按馆拉全量 stub。与 probe_joconde 同一个上游、**不同接入点**。

    cfg 走真正的 museums.yaml(不自己拼一个),于是这条探针连带覆盖
    "museums.yaml 里的 joconde_museum 馆名被上游改了" —— 馆名对不上时
    `__exact` 筛出 0 行,看起来和"这个馆就是没藏品"一模一样。

    `museum` 只给自检用:换个不存在的馆名,让探针在**真实上游**上拿到空结果,
    验它认不认得出来(不联网的自检等于没验)。
    """
    from dataclasses import replace

    from app.services.enrichment.catalog import MuseumCatalog
    from app.services.enrichment.factory import CATALOG_PATH
    from app.services.enrichment.sources.joconde_catalog import JocondeCatalog

    cfg = MuseumCatalog.from_file(CATALOG_PATH).get(slug)
    if museum:
        cfg = replace(cfg, joconde_museum=museum)
    stubs = list(JocondeCatalog().list(cfg))
    if len(stubs) < GOLDEN_CATALOG_MIN:
        raise RuntimeError(
            f"{slug} 只拉到 {len(stubs)} 条(期望 ≥{GOLDEN_CATALOG_MIN})"
            f" —— 馆名 {cfg.joconde_museum!r} 对不上,或上游掉了行"
        )
    # 下面两条断的是"列名变了/类型变了"这种**拿得到行、但内容是空的**死法。
    # 只数行数探不到它:_to_stub 照样产出 stub,只是 title/category 全空。
    titled = sum(1 for s in stubs if s.title)
    if titled < len(stubs) // 2:
        raise RuntimeError(f"{titled}/{len(stubs)} 条有标题 —— Titre 列可能已改名")
    # Domaine 从 list 变 str 那次,逐字符遍历让类目**全部**落 unknown 且不报错
    cats = {s.category for s in stubs} - {"unknown"}
    if not cats:
        raise RuntimeError("类目全是 unknown —— Domaine 列的名字或格式变了")
    return f"{slug} {len(stubs)} 条 / 标题 {titled} / 类目 {sorted(cats)}"


def probe_wikipedia(titles: dict | None = None) -> str:
    from app.services.enrichment.sources.wikipedia import WikipediaSource

    c = WikipediaSource(session=_session()).enrich(
        GOLDEN_QID, {}, {"wiki_titles": titles or GOLDEN_TITLES}
    )
    if c is None or not c.fields.get("extract_en"):
        raise RuntimeError("拿不到英文全文")
    return f"extract_en {len(c.fields['extract_en'])} 字"


def probe_wikidata(qid: str = GOLDEN_QID) -> str:
    from app.services.enrichment.sources.wikidata import run_sparql

    rows = run_sparql(f"SELECT ?artist WHERE {{ wd:{qid} wdt:P170 ?artist . }} LIMIT 1")
    if not rows:
        raise RuntimeError(f"{qid} 查不到 P170(SPARQL 端点或数据有变)")
    return f"P170 → {rows[0]}"


PROBES = {
    "joconde": probe_joconde,
    "joconde_catalog": probe_joconde_catalog,
    "wikipedia": probe_wikipedia,
    "wikidata": probe_wikidata,
}

# 自检用的坏输入:每个都该让对应探针抛异常。
# 没有这组,一个恒返回 OK 的坏探针会安安静静地"每天都说一切正常"。
BROKEN = {
    "joconde": {"p347": "00000000000"},  # 格式合法但不存在的 ref
    # 格式合法但不存在的馆名:上游会正常 200 返回空结果集 ——
    # 探针必须把"0 条"读成故障,不是"这馆没藏品"
    "joconde_catalog": {"museum": "musée qui n'existe pas"},
    "wikipedia": {"titles": {"en": "Xyzzy_no_such_article_42"}},
    "wikidata": {"qid": "Q999999999999"},
}


def run(names: list[str]) -> int:
    bad = []
    for name in names:
        try:
            print(f"[OK]   {name}: {PROBES[name]()}", flush=True)
        except Exception as e:
            print(f"[FAIL] {name}: {type(e).__name__}: {e}", flush=True)
            bad.append(name)
    if bad:
        print(f"\n⚠️ 探不通的源: {', '.join(bad)} —— 内容会静默变薄,去查上游。")
        return 1
    print(f"\n全部 {len(names)} 个源正常。")
    return 0


def self_test(names: list[str]) -> int:
    """喂已知坏输入,断言探针确实会喊 FAIL。"""
    silent = []
    for name in names:
        try:
            out = PROBES[name](**BROKEN[name])
            print(f"[BAD]  {name}: 坏输入却返回成功 → {out}", flush=True)
            silent.append(name)
        except Exception as e:
            print(f"[OK]   {name}: 坏输入如期报错 ({type(e).__name__})", flush=True)
    if silent:
        print(f"\n⚠️ 这些探针没有判断力: {', '.join(silent)} —— 它们的'正常'不可信。")
        return 2
    print(f"\n自检通过:{len(names)} 个探针都能认出坏输入。")
    return 0


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--self-test", action="store_true")
    p.add_argument("--only", help="只探某个源", choices=sorted(PROBES))
    a = p.parse_args()
    names = [a.only] if a.only else sorted(PROBES)
    sys.exit(self_test(names) if a.self_test else run(names))
