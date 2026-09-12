"""JocondeSource:P347 → data.gouv.fr 表格 API 逐件查。fake session 注入,不打真网。

canned 形状摘自真实 tabular-api.data.gouv.fr 响应(2026-09 迁移后)。
"""

import pytest

from app.services.enrichment.sources import joconde as mod
from app.services.enrichment.sources.joconde import JocondeSource

# 真实 dataset 元数据形状:靠 format=="csv" 认资源,不认顺序
CANNED_DATASET = {
    "resources": [
        {"id": "ods-nomenclature", "format": "ods", "title": "liste_champs.ods"},
        {"id": "csv-rid", "format": "csv", "title": "base-joconde-extrait.csv"},
    ]
}

CANNED_ROW = {
    "Reference": "000PE004070",
    "Titre": "Etude : torse",
    "Auteur": "RENOIR Pierre Auguste",
    "Materiaux_techniques": "peinture à l'huile;toile",
    "Mesures": "81 H ; 64.8 L",
    "Numero_inventaire": "RF 2740",
    "Sujet_Represente": "torse,nu,figure",
    "Periode_de_creation": "4e quart 19e siècle",
    "Domaine": "peinture",
    "Denomination": "tableau",
    "Ecole_pays": "France",
    "Localisation": "Paris ; musée d'Orsay",
}


@pytest.fixture(autouse=True)
def _reset_rid_cache():
    """模块级 rid 缓存跨测试会串味(某测试的假 rid 泄进下一个)。每例清一次。"""
    mod._rid_cache = None
    yield
    mod._rid_cache = None


_UNSET = object()  # rows=None 要能表达"上游零命中",不能被默认值吃掉


class FakeSession:
    """按 URL 分派:dataset 元数据 vs 表格数据。记录每次调用供断言。"""

    def __init__(self, rows=_UNSET, dataset=None):
        self._rows = CANNED_ROW if rows is _UNSET else rows
        self._dataset = dataset if dataset is not None else CANNED_DATASET
        self.calls = []

    def get_json(self, url, params=None, _transport=None):
        self.calls.append((url, params))
        if url.startswith(mod.DATASET_API):
            return self._dataset
        return {"data": [self._rows] if self._rows else []}


def test_probe_requires_p347():
    s = JocondeSource(session=None)
    assert s.probe({"P347": "000PE004070"}) is True
    assert s.probe({}) is False


def test_enrich_maps_french_fields():
    sess = FakeSession()
    c = JocondeSource(session=sess).enrich("Q1", {"P347": "000PE004070"}, {})

    assert c is not None
    assert c.source == "official"
    assert c.qid == "Q1"
    assert c.fields["title_fr"] == "Etude : torse"
    assert c.fields["artist_fr"] == "RENOIR Pierre Auguste"
    assert c.fields["medium_fr"] == "peinture à l'huile;toile"
    assert c.fields["dimensions"] == "81 H ; 64.8 L"
    assert c.fields["inventory_number"] == "RF 2740"
    assert c.fields["subjects_fr"] == "torse,nu,figure"
    assert c.fields["period_fr"] == "4e quart 19e siècle"
    assert c.fields["domaine_fr"] == "peinture"
    assert c.fields["denomination_fr"] == "tableau"
    assert c.fields["school_fr"] == "France"
    assert c.fields["location_fr"] == "Paris ; musée d'Orsay"
    # 按 ref 精确过滤,且打在解析出来的那个 rid 上
    data_url, data_params = sess.calls[-1]
    assert data_params == {"Reference__exact": "000PE004070"}
    assert "csv-rid" in data_url


def test_missing_column_falls_back_to_none():
    """上游列缺失/改名 → 该字段 None,不抛 KeyError 拖垮整件富化。"""
    sess = FakeSession(rows={"Reference": "X", "Titre": "T"})
    c = JocondeSource(session=sess).enrich("Q1", {"P347": "X"}, {})
    assert c.fields["title_fr"] == "T"
    assert c.fields["medium_fr"] is None
    assert c.fields["dimensions"] is None


def test_resource_id_resolved_once_and_cached():
    """逐件富化不该每件都解析一遍 rid —— 上万件就是上万次多余请求。"""
    sess = FakeSession()
    src = JocondeSource(session=sess)
    src.enrich("Q1", {"P347": "A"}, {})
    src.enrich("Q2", {"P347": "B"}, {})

    dataset_calls = [u for u, _ in sess.calls if u.startswith(mod.DATASET_API)]
    assert len(dataset_calls) == 1
    assert len(sess.calls) == 3  # 1 次 rid 解析 + 2 次数据


def test_resource_id_picks_csv_not_first_resource():
    """资源顺序不保证:必须按 format 认,不能取 resources[0]。"""
    sess = FakeSession()
    JocondeSource(session=sess).enrich("Q1", {"P347": "A"}, {})
    assert "csv-rid" in sess.calls[-1][0]
    assert "ods-nomenclature" not in sess.calls[-1][0]


def test_enrich_returns_none_without_p347():
    assert JocondeSource(session=None).enrich("Q1", {}, {}) is None


def test_enrich_returns_none_when_no_rows():
    assert (
        JocondeSource(session=FakeSession(rows=None)).enrich("Q1", {"P347": "X"}, {})
        is None
    )
