"""按**馆藏号**反查 Joconde 的 Reference,补进 attributes.external_ids.P347。

为什么需要:JocondeSource 的发现只认 Wikidata P347,而 P347 在 Wikidata 上
覆盖极不均匀 —— 小皇宫 3009 件里只有 7 件有(0.2%),卢浮宫 9971 件没有。
上游数据本身是在的(巴黎小皇宫在 Joconde 里有 29502 件),缺的只是"配对的钥匙"。
把钥匙补上,既有的 JocondeSource / backfill_joconde_attrs 一行不改就能吃到。

把发现(discovery)和富化(enrichment)分开是有意的:一件作品在 Joconde 里的编号
是**结构性事实**,查一次落库即可,不该每次 generate 都重新问上游一遍。

判据(两条**都**满足才写):
  ① 该馆藏号在 Joconde 全库**唯一命中**;
  ② 命中行的 Localisation 在本馆配置的 joconde_locations 里。
①防一号多件,②防跨馆误配(inv 号如 "3130"、"18.17.2-29" 特异性很弱,
全库 80 万行里撞号很正常)。②的代价是漏掉**寄存(dépôt)在外馆**的件 ——
Joconde 的 Localisation 记的是实际存放地,不是归属馆:卢浮宫 786 件实测有
~30% 写在凡尔赛/波城/里尔等名下,甚至 3 件写在"Avignon ; musée du Petit Palais"。
漏掉 ≠ 配错,宁缺毋滥;漏掉的件会单独计数报出来。

⚠️ 为什么逐条查而不批量:上游 `Numero_inventaire__in` 有**静默**解析 bug ——
批次里只要出现一个含括号的号(如 "PPS3351(1)"),它**后面的值全被丢弃**,
HTTP 200、不报错、只少返回行。实测 60 件样本批量查漏 3 件。宁可慢。

用法:
    python scripts/discover_joconde_refs.py --museum petit_palais            # dry-run
    python scripts/discover_joconde_refs.py --museum petit_palais --apply
    python scripts/discover_joconde_refs.py --museum petit_palais --limit 50
幂等:已有 P347 的件直接跳过(绝不覆盖权威值)。中断后重跑即续。

跑完接 `backfill_joconde_attrs.py --museum <slug> --apply` 把法语字段灌进
attributes —— 那一步才让展签面板(尺寸/材质)出数,且不碰正文、不动音频。
"""

import argparse
import sys
import time

sys.path.insert(0, "/app")

import requests  # noqa: E402
import yaml  # noqa: E402

from app.core.database import SessionLocal  # noqa: E402
from app.models.museum import Museum  # noqa: E402
from app.models.museum_object import MuseumObject  # noqa: E402
from app.services.enrichment.sources.joconde import (  # noqa: E402
    TABULAR_URL,
    resolve_resource_id,
)

_UA = "GoMuseumEnrichment/1.0 (appcraft008@gmail.com)"
_PAUSE = 0.25  # 礼貌限速。逐条查 ~3000 件约 13 分钟
_PAGE = 200  # 上游硬上限(超过直接 400 "Page size exceeds allowed maximum: 200")
# 自检负样本:这个馆藏号在 Joconde 里不可能存在。反查返回非 None 就说明
# 匹配逻辑太松(例如不小心用了 contains 而不是 exact),结果整体不可信。
_IMPOSSIBLE_INV = "ZZ_NO_SUCH_INVENTORY_NUMBER_42"
# 金标准取样上限。多查不会更准 —— 能检出系统性错配的样本量很小,
# 而每件都要一次上游往返(卢浮宫有 7312 件权威 P347,全查要半小时,纯浪费)。
# 按馆藏号排序取前 N 而不是随机:同一个库两次跑的自检样本一致,结果可复现。
_SELF_TEST_MAX = 20


def _get_json(url, params=None):
    r = requests.get(
        url,
        params=params,
        headers={"User-Agent": _UA, "Accept": "application/json"},
        timeout=60,
    )
    r.raise_for_status()
    return r.json() or {}


def museum_locations(slug: str, path: str = "museums.yaml") -> list[str]:
    """本馆在 Joconde 里的 Localisation 值(配置)。没配 → SystemExit。

    没配就退出而不是"当作空列表跑完报 0 命中" —— 后者看起来像
    "这个馆上游没有数据",是最难发现的一类假结论。
    """
    with open(path) as f:
        cfg = (yaml.safe_load(f) or {}).get("museums", {}).get(slug)
    if cfg is None:
        raise SystemExit(f"museums.yaml 里没有 {slug}")
    locs = cfg.get("joconde_locations") or []
    if not locs:
        raise SystemExit(
            f"{slug} 未配 joconde_locations —— 先去 museums.yaml 配上\n"
            f"  (取值方式:拿本馆已有 P347 的件查上游,看 Localisation 列的实际写法;\n"
            f"   别照国立馆的「城市 ; 馆名」格式猜,巴黎小皇宫写的是\n"
            f"   'Petit Palais, musée des Beaux-arts de la Ville de Paris')"
        )
    return list(locs)


def _inv_variants(inv: str) -> list[str]:
    """馆藏号在上游的可能写法。

    ⚠️ 纸上作品(素描/版画)在 Joconde 里**按面分行**:我们的 `INV 8195`
    那边存成 `INV 8195, recto`(还有 `, verso`)。不试这两个后缀,
    卢浮宫素描件 `__exact` 全部零行 —— 实测 80 件分层抽样命中率
    1% → 42%,救回的 33/34 全靠这个后缀。

    只加这两个确定的后缀,**不做通用归一化**(剥空格/连字符)。剥完
    `E 367.1` → `E3671` 会在全库 80 万行里撞上别的件,而错配的 P347
    会把别人的作品资料灌进这件且无处报错(见模块头判据①)。
    """
    return [inv, f"{inv}, recto", f"{inv}, verso"]


def lookup_ref(get_json, rid: str, inv: str, locations: list[str]) -> tuple:
    """馆藏号 → (ref, 原因)。ref 为 None 时原因说明为什么没采纳。

    一次请求拿回该号在**全库**的所有行,本地按 locations 过滤 —— 不把
    Localisation 塞进查询条件,是为了能分清"上游根本没这个号"和
    "有,但记在别的馆名下(寄存)",后者是要单独报数的。

    逐个试 `_inv_variants`,第一个**在本馆唯一命中**的就采纳;
    后缀变体不改变判据①②,只是把同一件的另一种写法也找出来。
    """
    rows = []
    for cand in _inv_variants(inv):
        data = get_json(
            TABULAR_URL.format(rid=rid),
            {"Numero_inventaire__exact": cand, "page_size": _PAGE},
        )
        got = data.get("data") or []
        rows += got
        if [r for r in got if r.get("Localisation") in locations]:
            break
    if not rows:
        return None, "上游无此号"
    mine = [r for r in rows if r.get("Localisation") in locations]
    if not mine:
        return None, "命中但在别馆(寄存?)"
    if len(mine) > 1:
        return None, f"本馆内 {len(mine)} 条同号"
    ref = mine[0].get("Reference")
    return (ref, "采纳") if ref else (None, "命中行无 Reference")


def ref_exists(get_json, rid: str, ref: str) -> bool:
    """这个 Reference 在上游存在吗(判断 Wikidata 的 P347 是否已失效)。"""
    data = get_json(
        TABULAR_URL.format(rid=rid), {"Reference__exact": ref, "page_size": 1}
    )
    return bool(data.get("data"))


def classify(get_json, rid: str, want: str, got: str | None) -> str:
    """反查结果 vs 权威 P347 的关系。只有 "冲突" 才说明反查逻辑有问题。

    ⚠️ "反查 ≠ 权威" **不等于** "反查错了" —— Wikidata 上的 P347 本身会坏。
    实测小皇宫 PDUT933:权威写的 `M1111160004` 在上游 0 行,而反查出的
    `M1111160004529` 是它**被截断前的完整值**(标题 L'abreuvoir、作者
    Velde Adriaen van de、馆藏号 PDUT933 三项全对)。把这种算"自检失败",
    自检就永远过不了;而把所有不一致都算"通过",自检就等于没有。
    分水岭是:权威那个 ref 自己还活着吗?
    """
    if got == want:
        return "一致"
    if got is None:
        return "反查未命中"  # 不会写入,不构成误配
    return "冲突" if ref_exists(get_json, rid, want) else "权威失效(反查救回)"


def self_test(get_json, rid: str, objs: list, locations: list[str]) -> None:
    """拿**已有权威 P347** 的件当金标准校准自己,外加一个不可能的号当负样本。

    没有这一步,"命中 43/60" 只是个数字 —— 它同样可能是 43 次张冠李戴。
    有一条真冲突就退出:错配的 P347 会把别人的作品资料灌进这件,
    而且灌进去之后没有任何地方会报错。
    """
    gold = sorted(
        (
            (
                o.inventory_number,
                (o.attributes or {}).get("external_ids", {}).get("P347"),
            )
            for o in objs
            if o.inventory_number
            and (o.attributes or {}).get("external_ids", {}).get("P347")
            # ⚠️ **排除本脚本自己写过的件**。金标准必须来自 Wikidata(P347 的权威源),
            # 不能是上一轮反查的产物 —— 否则就是拿反查的结果去验证反查,必然一致,
            # 自检形同虚设。2026-09-13 实跑踩到:中断后续跑时,金标准从 7 件
            # 变成 1479 件(1441 件是自己刚写的),自检还"通过"了。
            # `joconde_ref_via` 这个留痕字段本来是为"将来能整批撤回"留的,
            # 这里发现它的第二个用途:把自己写的和权威的分开。
            and not (o.attributes or {}).get("joconde_ref_via")
        )
    )[:_SELF_TEST_MAX]
    if not gold:
        raise SystemExit(
            "自检无法进行:本馆没有任何「既有馆藏号 + **来自 Wikidata 的** P347」的件\n"
            "(本脚本自己反查补的不算,它们不能给自己当金标准)。\n"
            "无从校准反查是否配对正确。要强行跑请显式加 --no-self-test。"
        )
    print(f"自检:{len(gold)} 件金标准(权威源) + 1 个负样本", flush=True)
    tally: dict = {}
    conflicts = []
    for inv, want in gold:
        got, _ = lookup_ref(get_json, rid, inv, locations)
        verdict = classify(get_json, rid, want, got)
        tally[verdict] = tally.get(verdict, 0) + 1
        if verdict == "冲突":
            conflicts.append((inv, want, got))
        elif verdict == "权威失效(反查救回)":
            print(f"  ⓘ {inv}: Wikidata 的 {want} 已失效,反查得 {got}", flush=True)
        time.sleep(_PAUSE)
    neg, _ = lookup_ref(get_json, rid, _IMPOSSIBLE_INV, locations)
    if neg is not None:
        conflicts.append((_IMPOSSIBLE_INV, "(不应命中)", neg))
    if conflicts:
        for inv, want, got in conflicts:
            print(f"  🔴 {inv}: 权威={want} 反查={got}")
        raise SystemExit("自检未通过:反查与**仍然有效**的权威值冲突,已中止。")
    # ⚠️ 金标准**全员未命中**也要拦。只看"有没有冲突"的话,一个什么都查不到的
    # 反查永远零冲突 —— 自检照样打勾,然后整馆跑出 1% 命中率,看起来像
    # "这个馆上游就是没数据"。2026-09-21 卢浮宫实测踩到:20/20 全是
    # "反查未命中",自检却报 ✓(真因是上游按 recto/verso 分行,见 _inv_variants)。
    # 金标准是**已知在上游存在**的件,查不到它们就是反查本身坏了。
    if tally.get("反查未命中", 0) == len(gold):
        raise SystemExit(
            f"自检未通过:{len(gold)} 件金标准**全部**反查未命中。\n"
            "它们是已知在上游存在的件(权威 P347 来自 Wikidata),全查不到\n"
            "说明匹配方式对本馆不成立(如上游馆藏号写法不同),不是'本馆没数据'。"
        )
    print(
        "  ✓ 无冲突,负样本正确拒绝 —— "
        + "、".join(f"{k} {v}" for k, v in sorted(tally.items())),
        flush=True,
    )


def main(
    slug: str,
    apply: bool,
    limit: int | None,
    do_self_test: bool,
    config: str = "museums.yaml",
) -> None:
    locations = museum_locations(slug, config)
    db = SessionLocal()
    m = db.query(Museum).filter_by(slug=slug).one_or_none()
    if m is None:
        raise SystemExit(f"museum not found: {slug}")  # typo 别静默 0/0
    objs = db.query(MuseumObject).filter_by(museum_id=m.id).all()
    print(f"{slug}: {len(objs)} 件,Localisation 配置 {locations}", flush=True)

    rid = resolve_resource_id(_get_json)
    print(f"CSV 资源 id = {rid}", flush=True)
    if do_self_test:
        self_test(_get_json, rid, objs, locations)

    todo = [
        o
        for o in objs
        if o.inventory_number
        and not (o.attributes or {}).get("external_ids", {}).get("P347")
    ]
    if limit:
        todo = todo[:limit]
    print(f"待反查 {len(todo)} 件(已有 P347 的跳过)", flush=True)

    found = 0
    reasons: dict = {}
    for i, o in enumerate(todo):
        try:
            ref, why = lookup_ref(_get_json, rid, o.inventory_number, locations)
        except Exception as e:  # 单件网络失败跳过,幂等重跑再补(纪律①)
            ref, why = None, f"请求失败({type(e).__name__})"
        reasons[why] = reasons.get(why, 0) + 1
        if ref:
            found += 1
            if apply:
                attrs = dict(o.attributes or {})
                ext = dict(attrs.get("external_ids") or {})
                ext["P347"] = ref
                attrs["external_ids"] = ext
                # 留痕:这条 P347 是反查出来的,不是 Wikidata 给的。将来若发现
                # 判据有问题,靠它能把这批**整体**找出来撤掉(只看 P347 分不出来源)。
                attrs["joconde_ref_via"] = "inventory_number"
                o.attributes = attrs
        if (i + 1) % 50 == 0:
            if apply:
                db.commit()  # 分批落盘(纪律②),中断不丢进度
            print(f"  [{i + 1}/{len(todo)}] 已找到 {found}", flush=True)
        time.sleep(_PAUSE)
    if apply:
        db.commit()

    mode = "已写入" if apply else "dry-run(加 --apply 生效)"
    print(
        f"\n{mode}: 找到 {found} / {len(todo)} 件 ({found * 100 // max(len(todo), 1)}%)"
    )
    for why, n in sorted(reasons.items(), key=lambda kv: -kv[1]):
        print(f"  {n:6d}  {why}")
    print("\n下一步: backfill_joconde_attrs.py --museum %s --apply" % slug)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--museum", required=True, help="馆 slug")
    p.add_argument("--apply", action="store_true")
    p.add_argument("--limit", type=int, help="只处理前 N 件(试跑)")
    p.add_argument(
        "--no-self-test",
        action="store_true",
        help="跳过金标准自检(仅当本馆一件权威 P347 都没有时)",
    )
    # 合并部署前想在真库上跑 dry-run 时用:把脚本和配置 docker cp 到容器 /tmp,
    # 指到 /tmp/museums.yaml,不必覆盖 /app 里正在服务的那份。
    p.add_argument("--config", default="museums.yaml", help="museums.yaml 路径")
    a = p.parse_args()
    main(a.museum, a.apply, a.limit, not a.no_self_test, a.config)
