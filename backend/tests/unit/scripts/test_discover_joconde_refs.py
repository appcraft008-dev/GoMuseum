"""馆藏号反查 Joconde Reference:两条闸 + 自检。

这个脚本写的是 external_ids.P347,而 P347 一旦配错,**别人作品的资料会被灌进
这件,且没有任何地方会报错**(富化是单源容错的,错的值和对的值一样安静)。
所以这里测的重点不是"能不能找到",而是**该拒绝的有没有拒绝**。
"""

import pytest

from scripts.discover_joconde_refs import lookup_ref, museum_locations, self_test

LOC = "Petit Palais, musée des Beaux-arts de la Ville de Paris"
OTHER = "Avignon ; musée du Petit Palais"


def _getter(rows):
    """返回固定行的假 get_json;顺带记录被查的参数,用来钉死 exact 语义。"""
    seen = []

    def get_json(url, params=None):
        seen.append(params or {})
        return {"data": rows}

    get_json.seen = seen
    return get_json


def test_unique_hit_in_our_museum_is_accepted():
    g = _getter([{"Reference": "M111", "Localisation": LOC}])
    assert lookup_ref(g, "rid", "PPP377", [LOC]) == ("M111", "采纳")


def test_hit_in_another_museum_is_rejected():
    """Joconde 的 Localisation 记的是**实际存放地**,不是归属馆。同一个馆藏号
    在别的馆名下命中,通常是撞号(卢浮宫实测有 3 件写在阿维尼翁小皇宫名下)。
    采纳它等于把别人的画的材质尺寸贴到本馆这件上。
    """
    g = _getter([{"Reference": "M999", "Localisation": OTHER}])
    ref, why = lookup_ref(g, "rid", "PPP377", [LOC])
    assert ref is None and "别馆" in why


def test_two_rows_in_our_museum_is_rejected():
    """本馆内同号两条 → 无从判断是哪一件,宁缺毋滥。"""
    g = _getter(
        [
            {"Reference": "M1", "Localisation": LOC},
            {"Reference": "M2", "Localisation": LOC},
        ]
    )
    ref, why = lookup_ref(g, "rid", "3130", [LOC])
    assert ref is None and "2 条" in why


def test_other_museum_rows_do_not_make_our_single_hit_ambiguous():
    """全库三条、本馆只一条 → 仍然采纳。

    这条守的是"别把过滤和计数的顺序搞反":先数后滤会把这种情况判成多义,
    于是弱特异性的号(纯数字)几乎全被误杀 —— 而那恰恰是最常见的一类。
    """
    g = _getter(
        [
            {"Reference": "Mx", "Localisation": OTHER},
            {"Reference": "M1", "Localisation": LOC},
            {"Reference": "My", "Localisation": "Pau ; musée des beaux-arts"},
        ]
    )
    assert lookup_ref(g, "rid", "3130", [LOC]) == ("M1", "采纳")


def test_absent_upstream_is_rejected():
    assert lookup_ref(_getter([]), "rid", "PPP3130", [LOC]) == (None, "上游无此号")


def test_row_without_reference_is_rejected():
    g = _getter([{"Reference": None, "Localisation": LOC}])
    ref, why = lookup_ref(g, "rid", "PPP377", [LOC])
    assert ref is None and "Reference" in why


def test_query_uses_exact_not_contains():
    """用 contains 会让 "PPP37" 命中 "PPP377"/"PPP3766" —— 而且是**唯一命中**时
    才最危险:闸全过,值全错。所以把查询参数名本身钉死。
    """
    g = _getter([{"Reference": "M111", "Localisation": LOC}])
    lookup_ref(g, "rid", "PPP377", [LOC])
    assert "Numero_inventaire__exact" in g.seen[0]
    assert not any("contains" in k for k in g.seen[0])


class _Obj:
    def __init__(self, inv, p347=None, via=None, category="painting"):
        self.inventory_number = inv
        self.category = category
        self.attributes = {"external_ids": {"P347": p347} if p347 else {}}
        if via:
            self.attributes["joconde_ref_via"] = via


def test_self_test_ignores_refs_this_script_wrote_itself(monkeypatch):
    """金标准只认**来自 Wikidata** 的 P347,不认自己反查补的。

    否则就是拿反查的结果去验证反查,必然一致,自检形同虚设。
    2026-09-13 实跑踩到:中断后续跑时金标准从 7 件变成 1479 件
    (1441 件是自己刚写的),自检照样"通过"。

    这条用一个**只有自写件、没有权威件**的库来测:必须退出,而不是
    拿那些自写件当金标准跑得通。
    """
    objs = [_Obj("PPP1", "M1", via="inventory_number") for _ in range(50)]
    monkeypatch.setattr("scripts.discover_joconde_refs.time.sleep", lambda s: None)
    with pytest.raises(SystemExit):
        self_test(None, "rid", objs, [LOC])


def test_self_test_uses_the_authoritative_ones_when_both_kinds_exist(monkeypatch):
    """混合库:只拿权威那几件当金标准,自写的一件都不进样本。"""
    objs = [_Obj("PPP_AUTH", "M_AUTH")] + [
        _Obj(f"PPP{i}", f"M{i}", via="inventory_number") for i in range(30)
    ]
    seen = []

    def fake_lookup(g, rid, inv, locs, cat=None):
        seen.append(inv)
        return ("M_AUTH" if inv == "PPP_AUTH" else None), "采纳"

    monkeypatch.setattr("scripts.discover_joconde_refs.lookup_ref", fake_lookup)
    monkeypatch.setattr("scripts.discover_joconde_refs.time.sleep", lambda s: None)
    self_test(None, "rid", objs, [LOC])
    checked = [x for x in seen if x != "ZZ_NO_SUCH_INVENTORY_NUMBER_42"]
    assert checked == ["PPP_AUTH"], f"自检查了不该查的件: {checked}"


def test_self_test_sample_is_capped(monkeypatch):
    """金标准取样有上限 —— 卢浮宫有 7312 件权威 P347,全查要半小时且不会更准。"""
    from scripts.discover_joconde_refs import _SELF_TEST_MAX

    objs = [_Obj("PPP%03d" % i, "M%d" % i) for i in range(200)]
    seen = []

    def fake_lookup(g, rid, inv, locs, cat=None):
        seen.append(inv)
        return ({"PPP%03d" % i: "M%d" % i for i in range(200)}.get(inv), "采纳")

    monkeypatch.setattr("scripts.discover_joconde_refs.lookup_ref", fake_lookup)
    monkeypatch.setattr("scripts.discover_joconde_refs.time.sleep", lambda s: None)
    self_test(None, "rid", objs, [LOC])
    checked = [x for x in seen if x != "ZZ_NO_SUCH_INVENTORY_NUMBER_42"]
    assert len(checked) == _SELF_TEST_MAX

    # 可复现:同一批输入两次跑拿到同一批样本。
    seen.clear()
    self_test(None, "rid", objs, [LOC])
    again = [x for x in seen if x != "ZZ_NO_SUCH_INVENTORY_NUMBER_42"]
    assert again == checked, "取样要确定性,否则两次跑的自检结果不可比"

    # 但**不能靠排序**拿到确定性 —— 按馆藏号升序取前 N 是取簇:
    # 卢浮宫实测那样会选出一整批无部门前缀的纯数字号(特异性最弱的一类),
    # 20/20 全未命中,而真实命中率是 42%。可复现 ≠ 有代表性。
    assert (
        checked
        != sorted(objs_inv := [o.inventory_number for o in objs])[:_SELF_TEST_MAX]
    ), "取样退回了「按馆藏号排序取前 N」——那是取簇"
    assert set(checked) <= set(objs_inv)


def test_self_test_passes_when_lookup_agrees_with_authoritative_p347(monkeypatch):
    objs = [_Obj("PPP746", "M7353"), _Obj("PPP1006", "M7358"), _Obj("PPP999")]
    table = {"PPP746": "M7353", "PPP1006": "M7358"}
    monkeypatch.setattr(
        "scripts.discover_joconde_refs.lookup_ref",
        lambda g, rid, inv, locs, cat=None: (
            table.get(inv),
            "采纳" if inv in table else "无",
        ),
    )
    monkeypatch.setattr("scripts.discover_joconde_refs.time.sleep", lambda s: None)
    self_test(None, "rid", objs, [LOC])  # 不抛 = 通过


def test_self_test_fails_on_a_conflict_with_a_live_authoritative_ref(monkeypatch):
    """与**仍然有效**的权威值冲突 → 中止。"43/60 命中"这个数字在
    "43 次张冠李戴"的世界里长得**一模一样** —— 分开这两个世界的只有金标准。
    """
    objs = [_Obj("PPP746", "M7353"), _Obj("PPP1006", "M7358")]
    monkeypatch.setattr(
        "scripts.discover_joconde_refs.lookup_ref",
        lambda g, rid, inv, locs, cat=None: ("M_WRONG", "采纳"),
    )
    monkeypatch.setattr(
        "scripts.discover_joconde_refs.ref_exists", lambda g, rid, ref: True
    )
    monkeypatch.setattr("scripts.discover_joconde_refs.time.sleep", lambda s: None)
    with pytest.raises(SystemExit):
        self_test(None, "rid", objs, [LOC])


def test_self_test_tolerates_a_dead_authoritative_ref(monkeypatch):
    """权威 ref 自己在上游已经没了 → 反查那个才是活的,不该算自检失败。

    实测小皇宫 PDUT933:Wikidata 的 P347 是完整值被截断的前 11 位。
    按"不一致就失败"判,自检**永远过不了**,脚本一行都跑不起来。
    """
    objs = [_Obj("PDUT933", "M1111160004")]
    monkeypatch.setattr(
        "scripts.discover_joconde_refs.lookup_ref",
        lambda g, rid, inv, locs, cat=None: (
            ("M1111160004529", "采纳") if inv == "PDUT933" else (None, "无")
        ),
    )
    monkeypatch.setattr(
        "scripts.discover_joconde_refs.ref_exists", lambda g, rid, ref: False
    )
    monkeypatch.setattr("scripts.discover_joconde_refs.time.sleep", lambda s: None)
    self_test(None, "rid", objs, [LOC])  # 不抛 = 通过


def test_self_test_tolerates_a_lookup_miss(monkeypatch):
    """反查找不到 ≠ 配错。借展品的馆藏号(如 'Inlån JSS 416:01')上游记的是
    别的号,查不到是正常的;它本来就不会被写入,不构成误配。
    """
    objs = [_Obj("Inlån JSS 416:01", "M7655"), _Obj("PPP746", "M7353")]
    table = {"PPP746": "M7353"}
    monkeypatch.setattr(
        "scripts.discover_joconde_refs.lookup_ref",
        lambda g, rid, inv, locs, cat=None: (
            table.get(inv),
            "采纳" if inv in table else "无",
        ),
    )
    monkeypatch.setattr("scripts.discover_joconde_refs.time.sleep", lambda s: None)
    self_test(None, "rid", objs, [LOC])  # 不抛 = 通过


def test_self_test_fails_when_impossible_inventory_number_matches(monkeypatch):
    """负样本:编造的号若也能"命中",说明匹配太松,整批结果不可信。
    金标准只能证明"对的能对上",证不了"错的会被拒"。
    """
    objs = [_Obj("PPP746", "M7353")]
    monkeypatch.setattr(
        "scripts.discover_joconde_refs.lookup_ref",
        lambda g, rid, inv, locs, cat=None: (
            "M7353" if inv == "PPP746" else "M_ANY",
            "采纳",
        ),
    )
    monkeypatch.setattr("scripts.discover_joconde_refs.time.sleep", lambda s: None)
    with pytest.raises(SystemExit):
        self_test(None, "rid", objs, [LOC])


def test_self_test_refuses_to_run_without_any_gold_sample(monkeypatch):
    """没有金标准时**退出**,而不是"跳过自检继续跑" —— 后者会产出一批
    无人校准过的 P347,而它们看起来和校准过的完全一样。
    """
    monkeypatch.setattr("scripts.discover_joconde_refs.time.sleep", lambda s: None)
    with pytest.raises(SystemExit):
        self_test(None, "rid", [_Obj("PPP999")], [LOC])


def test_missing_joconde_locations_exits_instead_of_finding_nothing(tmp_path):
    """没配 Localisation 就退出。若改成"空列表照跑",输出会是
    "找到 0 / 2986 件" —— 和"这个馆上游真没数据"一字不差。
    """
    p = tmp_path / "museums.yaml"
    p.write_text("museums:\n  petit_palais:\n    name_en: Petit Palais\n")
    with pytest.raises(SystemExit):
        museum_locations("petit_palais", str(p))


def test_locations_are_read_from_config(tmp_path):
    p = tmp_path / "museums.yaml"
    p.write_text(
        "museums:\n  petit_palais:\n    joconde_locations: ['%s', '%s']\n"
        % (LOC, OTHER)
    )
    assert museum_locations("petit_palais", str(p)) == [LOC, OTHER]


# ── 纸上作品的 recto/verso 后缀 ────────────────────────────────────────────
# 上游把素描/版画**按面分行**:我们的 `INV 8195` 那边是 `INV 8195, recto`。
# 不试后缀的话卢浮宫素描件 __exact 全部零行 —— 实测 80 件分层抽样
# 命中率 1% → 42%,救回的 33/34 全靠这个后缀。


def _by_inv(table):
    """按被查的馆藏号返回不同结果的假 get_json（真上游就是这样)。"""
    seen = []

    def get_json(url, params=None):
        params = params or {}
        seen.append(params)
        return {"data": table.get(params.get("Numero_inventaire__exact"), [])}

    get_json.seen = seen
    return get_json


def test_recto_suffix_is_found():
    g = _by_inv(
        {
            "INV 8195, recto": [
                {"Reference": "M8195", "Localisation": LOC, "Domaine": "dessin"}
            ]
        }
    )
    assert lookup_ref(g, "rid", "INV 8195", [LOC], "works_on_paper") == (
        "M8195",
        "采纳",
    )


def test_verso_suffix_is_found():
    g = _by_inv(
        {
            "RF 20815, verso": [
                {"Reference": "M2081", "Localisation": LOC, "Domaine": "estampe"}
            ]
        }
    )
    assert lookup_ref(g, "rid", "RF 20815", [LOC], "works_on_paper") == (
        "M2081",
        "采纳",
    )


def test_plain_value_still_wins_without_extra_requests():
    """原值命中就停,不再多打两次上游(逐条查 1 万件,每件省两次往返)。"""
    g = _by_inv({"PPP377": [{"Reference": "M111", "Localisation": LOC}]})
    assert lookup_ref(g, "rid", "PPP377", [LOC]) == ("M111", "采纳")
    assert len(g.seen) == 1


def test_suffix_variants_do_not_loosen_the_museum_gate():
    """后缀变体只是换写法,不放宽判据② —— 命中在别馆照样拒绝。"""
    g = _by_inv(
        {
            "INV 8195, recto": [
                {"Reference": "M8195", "Localisation": OTHER, "Domaine": "dessin"}
            ]
        }
    )
    assert lookup_ref(g, "rid", "INV 8195", [LOC], "works_on_paper") == (
        None,
        "命中但在别馆(寄存?)",
    )


def test_suffix_variants_do_not_loosen_the_uniqueness_gate():
    """判据①也不放宽:同一变体下本馆两条同号,仍然拒绝。"""
    g = _by_inv(
        {
            "INV 8195, recto": [
                {"Reference": "A", "Localisation": LOC, "Domaine": "dessin"},
                {"Reference": "B", "Localisation": LOC, "Domaine": "dessin"},
            ]
        }
    )
    assert lookup_ref(g, "rid", "INV 8195", [LOC], "works_on_paper")[0] is None


def test_no_general_normalisation():
    """**只**加这两个确定的后缀,不剥空格/连字符。剥完 `E 367.1` → `E3671`
    会在全库 80 万行里撞上别的件,而错配的 P347 无处报错。
    """
    g = _by_inv({"INV8195": [{"Reference": "M8195", "Localisation": LOC}]})
    assert lookup_ref(g, "rid", "INV 8195", [LOC]) == (None, "上游无此号")


def test_self_test_fails_when_every_gold_sample_misses(monkeypatch):
    """金标准**全员**未命中 = 反查本身坏了,不是"本馆没数据"。

    只看"有没有冲突"的话,一个什么都查不到的反查永远零冲突、自检照样打勾。
    2026-09-21 卢浮宫实测踩到:20/20 全未命中而自检报 ✓。
    """
    objs = [_Obj("INV 8195", "M1"), _Obj("INV 483", "M2")]
    monkeypatch.setattr(
        "scripts.discover_joconde_refs.lookup_ref",
        lambda g, rid, inv, locs, cat=None: (None, "上游无此号"),
    )
    monkeypatch.setattr("scripts.discover_joconde_refs.time.sleep", lambda s: None)
    with pytest.raises(SystemExit, match="全部"):
        self_test(None, "rid", objs, [LOC])


def test_suffix_variant_rejected_when_kind_differs():
    """卢浮宫 `INV 5145` 的真实场景:同号在两个部门各有一件毫不相干的作品。

    我们库里是 Gudin 的**油画**(寄存凡尔赛),而 `INV 5145, recto` 是
    Muziano 之后的一张**素描**。两条在上游是不同的 Numero_inventaire 字符串,
    所以判据①的唯一性检查各自都只看到一行、挡不住。实测 80 件金标准里
    7 件(9%)是这样配错的,全是"我们记 painting,配到 dessin"。
    """
    g = _by_inv(
        {
            "INV 5145, recto": [
                {
                    "Reference": "50350007462",
                    "Localisation": LOC,
                    "Domaine": "dessin",
                }
            ]
        }
    )
    assert lookup_ref(g, "rid", "INV 5145", [LOC], "painting")[0] is None


def test_original_value_hit_is_not_subject_to_kind_check():
    """原值精确命中不存在这种歧义,不该被品类闸误杀(品类数据本身会缺)。"""
    g = _by_inv({"PPP377": [{"Reference": "M111", "Localisation": LOC}]})
    assert lookup_ref(g, "rid", "PPP377", [LOC], None) == ("M111", "采纳")


def test_suffix_variant_rejected_when_our_kind_is_unknown():
    """品类未知就判否 —— 猜错的代价是把别人作品的资料灌进这件(宁缺毋滥)。"""
    g = _by_inv(
        {
            "INV 8195, recto": [
                {"Reference": "M8195", "Localisation": LOC, "Domaine": "dessin"}
            ]
        }
    )
    assert lookup_ref(g, "rid", "INV 8195", [LOC], "unknown")[0] is None
    assert lookup_ref(g, "rid", "INV 8195", [LOC], None)[0] is None
