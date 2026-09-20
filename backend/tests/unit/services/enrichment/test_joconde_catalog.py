"""JocondeCatalog:从 Joconde 开放数据列纸上作品 → StubRecord;去重只补 Wikidata 缺的件。
注入式 http_get,离线。"""

from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.artist import Artist
from app.models.museum import Museum
from app.models.museum_object import MuseumObject, ObjectImage
from app.services.enrichment.catalog_loader import filter_new_stubs
from app.services.enrichment.catalog_source import StubRecord
from app.services.enrichment.sources.joconde_catalog import (
    _MUSEUM_COL,
    JocondeCatalog,
    _category,
    _clean_artist,
    _clean_inv,
    _clean_title,
    _clean_year,
)
from app.services.object_importer import upsert_museum, upsert_object

_RID = "7e3307c2-f2ff-455c-bbca-bb6f11aec7bb"
_DATASET = {"resources": [{"id": _RID, "format": "csv"}]}


def _fake_get_json(rows, page_size=200, errors_on_page=None):
    """表格 API 的最小替身：dataset 解析 + 按馆名筛 + 分页。"""

    def get_json(url, params=None):
        if params is None:  # resolve_resource_id 那一跳
            return _DATASET
        want = params[f"{_MUSEUM_COL}__exact"]
        page = params["page"]
        if errors_on_page == page:
            return {"errors": [{"title": "Invalid query string"}]}
        hit = [r for r in rows if r.get(_MUSEUM_COL) == want]
        lo = (page - 1) * page_size
        return {
            "data": hit[lo : lo + page_size],
            "meta": {"page": page, "page_size": page_size, "total": len(hit)},
        }

    return get_json


_ORSAY = SimpleNamespace(slug="orsay", joconde_museum="musée d'Orsay")


@pytest.fixture(autouse=True)
def _clear_rid_cache():
    """resolve_resource_id 有进程内缓存 —— 不清会让用例互相串味。"""
    import app.services.enrichment.sources.joconde as _j

    _j._rid_cache = None
    yield
    _j._rid_cache = None


def test_list_maps_record_fields():
    rec = {
        "Reference": "50350115122",
        "Numero_inventaire": "RF 2051, recto",
        "Titre": "MERE ET ENFANT SUR FOND VERT OU MATERNITE",
        "Auteur": "Cassatt Mary (1844-1926)",
        "Domaine": "beaux-arts;dessin",
        "Millesime_de_creation": "1897",
        "Nom_officiel_musee": "musée d'Orsay",
    }
    out = list(JocondeCatalog(get_json=_fake_get_json([rec])).list(_ORSAY))
    assert len(out) == 1
    s = out[0]
    assert s.inventory_number == "RF 2051"
    assert s.title == "Mere et enfant sur fond vert"
    assert s.artist == "Cassatt Mary"
    assert s.year == "1897"
    assert s.category == "works_on_paper"
    assert s.external_ids["P347"] == "50350115122"
    # 合成对外把手:命名空间 + 非 Q 格式(防撞车、不误入 Wikidata SPARQL)
    assert s.qid == "joconde-50350115122"
    assert s.image_url is None and s.source == "joconde"


def test_filters_by_museum_name():
    """整包是**全法国**的馆,没有服务端筛选了 —— 过滤错了会把别馆的件灌进来。"""
    rows = [
        {
            "Reference": str(i),
            "Numero_inventaire": f"RF {i}",
            "Titre": f"T{i}",
            "Domaine": "peinture",
            "Nom_officiel_musee": name,
        }
        for i, name in enumerate(
            ["musée d'Orsay", "musée du Louvre", "musée d'Orsay", "musée de Cluny"]
        )
    ]
    out = list(JocondeCatalog(get_json=_fake_get_json(rows)).list(_ORSAY))
    assert [o.inventory_number for o in out] == ["RF 0", "RF 2"]


def test_museum_name_passed_through_verbatim():
    """馆名**原样**发给服务端的 `__exact`,我们不改写它。

    筛选在服务端做,大小写/空格由它说了算 —— 所以配置里必须填 POP 精确官方名
    (契约里那条"先 search(nom_officiel_musee) 探查"就是为这个)。
    实测全量 CSV 里这两个馆各只有一种写法,不存在变体。
    """
    seen = {}

    def spy(url, params=None):
        if params is None:
            return _DATASET
        seen.update(params)
        return {"data": [], "meta": {"total": 0}}

    list(JocondeCatalog(get_json=spy).list(_ORSAY))
    assert seen[f"{_MUSEUM_COL}__exact"] == "musée d'Orsay"
    assert seen["page_size"] == 200  # 表格 API 的上限,超过直接 400


def test_page_size_clamped_by_server_still_paginates():
    """服务端把 page_size 钳小时**不能**当成末页。

    用 `len(rows) < 我们请求的 page_size` 判终止,会在第一页就停 ——
    静默少一批件。所以终止以 meta.total 为准。
    """
    rows = [
        {
            "Reference": str(i),
            "Numero_inventaire": f"RF {i}",
            "Titre": "T",
            "Domaine": "peinture",
            _MUSEUM_COL: "musée d'Orsay",
        }
        for i in range(7)
    ]
    # fake 只给 3 条一页,而代码请求的是 200
    out = list(JocondeCatalog(get_json=_fake_get_json(rows, page_size=3)).list(_ORSAY))
    assert len(out) == 7


def test_domaine_is_semicolon_string_not_list():
    """⚠️ 换通道最容易静默踩的一脚。

    旧 API 的 `domaine` 是 list,CSV 的 `Domaine` 是 `;` 分隔**字符串**。
    直接丢进原来那个 `for d in domaine` 会**逐字符**遍历 —— 一个字符都匹配不上
    `_DOMAINE_CAT`,于是全部落到 "unknown",**而且不报任何错**。
    """
    rows = [
        {
            "Reference": "r1",
            "Numero_inventaire": "RF 1",
            "Titre": "T",
            "Domaine": "beaux-arts;sculpture",
            "Nom_officiel_musee": "musée d'Orsay",
        }
    ]
    out = list(JocondeCatalog(get_json=_fake_get_json(rows)).list(_ORSAY))
    assert out[0].category == "sculpture"  # 不是 "unknown"


def test_year_is_normalized_at_import():
    """脏年代串不许进库 —— 它会被 pipeline 当 "Creation year" 喂给 LLM。"""
    rows = [
        {
            "Reference": f"r{i}",
            "Numero_inventaire": f"RF {i}",
            "Titre": "T",
            "Domaine": "peinture",
            "Millesime_de_creation": raw,
            "Nom_officiel_musee": "musée d'Orsay",
        }
        for i, raw in enumerate(
            [
                "1853 vers",
                "1865 entre,1908 et",
                "1860 vers,1928 tirage",
                "1854-1856",
                "1897",
                "1867 vers,1868 ou",  # 语义模糊 → 原样,不许猜
            ]
        )
    ]
    out = list(JocondeCatalog(get_json=_fake_get_json(rows)).list(_ORSAY))
    assert [o.year for o in out] == [
        "c. 1853",
        "1865–1908",
        "c. 1860",
        "1854–1856",
        "1897",
        "1867 vers,1868 ou",
    ]


def test_no_joconde_museum_yields_nothing():
    cfg = SimpleNamespace(slug="x", joconde_museum=None)
    assert list(JocondeCatalog(get_json=_fake_get_json([])).list(cfg)) == []


def test_skip_record_without_inventory_or_reference():
    no_inv = {
        "Reference": "r",
        "Numero_inventaire": "",
        "Titre": "T",
        "Domaine": "dessin",
        "Nom_officiel_musee": "musée d'Orsay",
    }
    no_ref = {
        "Reference": "",
        "Numero_inventaire": "RF 1",
        "Titre": "T",
        "Domaine": "dessin",
        "Nom_officiel_musee": "musée d'Orsay",
    }
    got = list(JocondeCatalog(get_json=_fake_get_json([no_inv, no_ref])).list(_ORSAY))
    assert got == []  # 无号或无 ref(合成不出把手)都跳过


def test_is_wikidata_qid_and_labels_guard():
    from app.services.enrichment.identity import is_wikidata_qid
    from app.services.enrichment.material import fetch_wikidata_labels

    assert is_wikidata_qid("Q334138") is True
    assert is_wikidata_qid("joconde-50350115122") is False
    assert is_wikidata_qid(None) is False
    # 合成 qid → 直接 {},绝不调 SPARQL(省成本 + 避免 wd:<合成号> 垃圾查询)
    called = {"n": 0}

    def _boom(q):
        called["n"] += 1
        raise AssertionError("run_query 不该被调用")

    assert fetch_wikidata_labels("joconde-50350115122", ["zh"], run_query=_boom) == {}
    assert called["n"] == 0


def test_cleaners():
    assert _clean_inv("RF 2051, recto") == "RF 2051"
    assert _clean_inv("RF 1977 444 ; LUX 1051 P ; J DE P 25 P") == "RF 1977 444"
    assert _clean_inv(None) is None
    assert _clean_artist("Cassatt Mary (1844-1926)") == "Cassatt Mary"
    assert _clean_title("MERE ET ENFANT SUR FOND VERT OU MATERNITE") == (
        "Mere et enfant sur fond vert"
    )
    assert _category(["beaux-arts", "dessin"]) == "works_on_paper"
    assert _category(["peinture"]) == "painting"
    assert _category(["sculpture"]) == "sculpture"
    assert _category(["beaux-arts"]) == "unknown"
    # CSV 形态:`;` 分隔字符串(不拆的话会逐字符遍历 → 全 unknown)
    assert _category("beaux-arts;dessin") == "works_on_paper"
    assert _category("peinture") == "painting"
    assert _category("") == "unknown"


# --- filter_new_stubs 去重 ---


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(
        bind=engine,
        tables=[
            Museum.__table__,
            MuseumObject.__table__,
            ObjectImage.__table__,
            Artist.__table__,
        ],
    )
    s = sessionmaker(bind=engine)()
    yield s
    s.close()


def _stub(inv, p347=None):
    return StubRecord(
        inventory_number=inv,
        qid=None,
        title="T",
        artist="A",
        year=None,
        category="works_on_paper",
        image_url=None,
        popularity=0,
        owning_museum="orsay",
        source="joconde",
        external_ids={"P347": p347} if p347 else {},
    )


def test_filter_new_stubs_skips_existing_inv_and_p347(db):
    m = upsert_museum(db, {"slug": "orsay", "name_en": "Orsay"})
    upsert_object(db, m.id, {"inventory_number": "RF 100", "title_en": "Existing"})
    upsert_object(
        db,
        m.id,
        {
            "qid": "Q1",
            "inventory_number": "RF 200",
            "attributes": {"external_ids": {"P347": "joc-9"}},
        },
    )
    db.commit()
    stubs = [
        _stub("RF100"),  # 归一化撞既有 RF 100 → 跳
        _stub("RF 999", p347="joc-9"),  # P347 撞既有 → 跳
        _stub("RF 300", p347="joc-new"),  # 真新 → 留
    ]
    out = filter_new_stubs(db, m.id, stubs)
    assert [s.inventory_number for s in out] == ["RF 300"]


def test_api_error_raises_instead_of_yielding_nothing():
    """表格 API 出错时返回的是 {"errors": [...]},**没有 data 键**。

    不认它的话 `data.get("data") or []` 会把报错读成"这个馆没有藏品" ——
    静默少一批件,看起来跟真的没藏品一模一样,是这条链路最难查的失败(纪律 31)。
    """
    rows = [
        {
            "Reference": str(i),
            "Numero_inventaire": f"RF {i}",
            "Titre": "T",
            "Domaine": "peinture",
            _MUSEUM_COL: "musée d'Orsay",
        }
        for i in range(3)
    ]
    bad = _fake_get_json(rows, errors_on_page=1)
    with pytest.raises(RuntimeError) as e:
        list(JocondeCatalog(get_json=bad).list(_ORSAY))
    assert "Invalid query string" in str(e.value)


def test_pagination_mismatch_raises():
    """拉到的行数与 meta.total 对不上必须喊出来(漏页/源在翻页中途变了)。"""

    def liar(url, params=None):
        if params is None:
            return _DATASET
        return (
            {"data": [], "meta": {"total": 5}}
            if params["page"] > 1
            else {
                "data": [
                    {
                        "Reference": "r1",
                        "Numero_inventaire": "RF 1",
                        "Titre": "T",
                        "Domaine": "peinture",
                        _MUSEUM_COL: "musée d'Orsay",
                    }
                ],
                "meta": {"total": 5},  # ← 说有 5 条,只给了 1 条
            }
        )

    with pytest.raises(RuntimeError) as e:
        list(JocondeCatalog(get_json=liar).list(_ORSAY))
    assert "分页对不上" in str(e.value)


def test_clean_year_table_and_passthrough():
    assert _clean_year("1853 vers") == "c. 1853"
    assert _clean_year("1865 entre,1908 et") == "1865–1908"
    assert _clean_year("1865 entre,1881 et,1931 tirage") == "1865–1881"
    assert _clean_year("1854-1856") == "1854–1856"
    assert _clean_year("1897") == "1897"
    assert _clean_year(None) is None
    # 语义模糊的原样:「约1867**或**1868」压成区间是改写原意
    assert _clean_year("1867 vers,1868 ou") == "1867 vers,1868 ou"
    assert _clean_year("1859 avant") == "1859 avant"  # 留给前端做 l10n
