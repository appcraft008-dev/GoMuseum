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
    JocondeCatalog,
    _category,
    _clean_artist,
    _clean_inv,
    _clean_title,
)
from app.services.object_importer import upsert_museum, upsert_object


class _Resp:
    status_code = 200

    def __init__(self, results):
        self._r = {"results": results}

    def json(self):
        return self._r


def _fake_http(pages):
    """按 offset//limit 分页发 canned 结果。"""

    def get(url, params=None, headers=None, timeout=None):
        i = params["offset"] // params["limit"]
        return _Resp(pages[i] if i < len(pages) else [])

    return get


_ORSAY = SimpleNamespace(slug="orsay", joconde_museum="musée d'Orsay")


def test_list_maps_record_fields():
    rec = {
        "reference": "50350115122",
        "numero_inventaire": "RF 2051, recto",
        "titre": "MERE ET ENFANT SUR FOND VERT OU MATERNITE",
        "auteur": "Cassatt Mary (1844-1926)",
        "domaine": ["beaux-arts", "dessin"],
        "millesime_de_creation": "1897",
    }
    out = list(JocondeCatalog(http_get=_fake_http([[rec], []])).list(_ORSAY))
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


def test_list_paginates_until_short_page():
    full = [
        {
            "reference": str(i),
            "numero_inventaire": f"RF {i}",
            "titre": f"T{i}",
            "domaine": ["peinture"],
        }
        for i in range(100)
    ]
    tail = [
        {
            "reference": "x",
            "numero_inventaire": "RF X",
            "titre": "TX",
            "domaine": ["sculpture"],
        }
    ]
    out = list(JocondeCatalog(http_get=_fake_http([full, tail, []])).list(_ORSAY))
    assert len(out) == 101


def test_no_joconde_museum_yields_nothing():
    cfg = SimpleNamespace(slug="x", joconde_museum=None)
    assert list(JocondeCatalog(http_get=_fake_http([])).list(cfg)) == []


def test_skip_record_without_inventory_or_reference():
    no_inv = {
        "reference": "r",
        "numero_inventaire": None,
        "titre": "T",
        "domaine": ["dessin"],
    }
    no_ref = {
        "reference": None,
        "numero_inventaire": "RF 1",
        "titre": "T",
        "domaine": ["dessin"],
    }
    got = list(JocondeCatalog(http_get=_fake_http([[no_inv, no_ref], []])).list(_ORSAY))
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
