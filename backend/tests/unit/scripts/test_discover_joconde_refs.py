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
    def __init__(self, inv, p347=None):
        self.inventory_number = inv
        self.attributes = {"external_ids": {"P347": p347} if p347 else {}}


def test_self_test_passes_when_lookup_agrees_with_authoritative_p347(monkeypatch):
    objs = [_Obj("PPP746", "M7353"), _Obj("PPP1006", "M7358"), _Obj("PPP999")]
    table = {"PPP746": "M7353", "PPP1006": "M7358"}
    monkeypatch.setattr(
        "scripts.discover_joconde_refs.lookup_ref",
        lambda g, rid, inv, locs: (table.get(inv), "采纳" if inv in table else "无"),
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
        lambda g, rid, inv, locs: ("M_WRONG", "采纳"),
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
        lambda g, rid, inv, locs: (
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
        lambda g, rid, inv, locs: (table.get(inv), "采纳" if inv in table else "无"),
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
        lambda g, rid, inv, locs: ("M7353" if inv == "PPP746" else "M_ANY", "采纳"),
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
