"""进程内搜索引擎:子串/前缀/编号/作者匹配 + 排序 + 全局/馆域过滤 + 无图 stub 可搜。
契约由端点锁定;本层测匹配行为。离线 sqlite,fixture 抄 test_matcher。"""

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.artist import Artist
from app.models.museum import Museum
from app.models.museum_object import MuseumObject, ObjectImage
from app.services.object_importer import upsert_museum, upsert_object
from app.services.search import inprocess
from app.services.search.inprocess import build_search_index, rank, search


@pytest.fixture()
def session():
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
    m = upsert_museum(
        s,
        {
            "slug": "orsay",
            "name_zh": "奥赛博物馆",
            "name_en": "Orsay Museum",
            "city_zh": "巴黎",
            "city_en": "Paris",
        },
    )
    s.add(
        Artist(qid="Q5582", name_en="Vincent van Gogh", name_i18n={"zh": "文森特·梵高"})
    )
    # 有图件:星夜(高人气)
    upsert_object(
        s,
        m.id,
        {
            "qid": "Q45585",
            "title_en": "The Starry Night",
            "artist_en": "Vincent van Gogh",
            "category": "painting",
            "year": "1889",
            "popularity": 100,
            "image": "https://example.com/starry.jpg",
            "attributes": {
                "title_i18n": {"en": "The Starry Night", "zh": "星夜"},
                "artist_qid": "Q5582",
            },
        },
    )
    # 无图 stub:同作者另一件(低人气,文字可识别层)
    upsert_object(
        s,
        m.id,
        {
            "qid": "Q_STUB",
            "title_en": "Starry Night Over the Rhone",
            "artist_en": "Vincent van Gogh",
            "category": "painting",
            "year": "1888",
            "popularity": 10,
            "inventory_number": "RF 1993-15",
            "attributes": {"artist_qid": "Q5582"},
        },
    )
    s.commit()
    inprocess._index_cache.clear()
    yield s
    inprocess._index_cache.clear()


def _mid(s):
    return s.query(Museum).filter_by(slug="orsay").one().id


class _FakeStorage:
    def public_url(self, key):  # 无 image_key 时不会被调用
        return f"https://cdn/{key}"


# --- 匹配逻辑(build_index + rank) ---


def test_title_substring_hit(session):
    idx = build_search_index(session, _mid(session))
    out = rank(idx, "星夜")  # 仅 Q45585 有中文标题"星夜"
    assert [e["qid"] for e, _ in out] == ["Q45585"]


def test_mid_word_query_is_substring_not_prefix(session):
    idx = build_search_index(session, _mid(session))
    out = dict((e["qid"], s) for e, s in rank(idx, "Starry"))
    # "The Starry Night" 归一化 "the starry night" 不以 "starry" 开头 → 子串 0.6
    assert out["Q45585"] == 0.6


def test_title_prefix_scores_high(session):
    idx = build_search_index(session, _mid(session))
    out = dict((e["qid"], s) for e, s in rank(idx, "The Starry"))
    assert out["Q45585"] == 0.8  # 前缀命中


def test_artist_substring_cross_language(session):
    # 中文界面/中文数据下打英文作者名也命中(全语种归一化作者集)
    idx = build_search_index(session, _mid(session))
    out = rank(idx, "van gogh")
    qids = {e["qid"] for e, _ in out}
    assert {"Q45585", "Q_STUB"} <= qids
    assert all(s == 0.4 for _, s in out)  # 作者子串档


def test_artist_zh_hits(session):
    idx = build_search_index(session, _mid(session))
    out = rank(idx, "梵高")
    assert {e["qid"] for e, _ in out} == {"Q45585", "Q_STUB"}


def test_inventory_exact_scores_full(session):
    idx = build_search_index(session, _mid(session))
    out = rank(idx, "RF1993-15")
    assert out[0][0]["qid"] == "Q_STUB" and out[0][1] == 1.0


def test_short_query_no_inv(session):
    idx = build_search_index(session, _mid(session))
    out = rank(idx, "RF")  # <3 归一化位 → 不触发编号满分
    assert not any(s == 1.0 for _, s in out)


def test_tie_break_by_popularity(session):
    # 两件标题都含"night"子串(同 0.6)→ 高人气(Q45585,100)排前
    idx = build_search_index(session, _mid(session))
    out = rank(idx, "night")
    assert [e["qid"] for e, _ in out][:2] == ["Q45585", "Q_STUB"]
    assert out[0][1] == out[1][1] == 0.6  # 同分


def test_empty_query_returns_empty(session):
    idx = build_search_index(session, _mid(session))
    assert rank(idx, "") == []
    assert rank(idx, "   ") == []


def test_no_results(session):
    idx = build_search_index(session, _mid(session))
    assert rank(idx, "Mona Lisa xyz") == []


def test_limit_respected(session):
    idx = build_search_index(session, _mid(session))
    assert len(rank(idx, "van gogh", limit=1)) == 1


def test_index_cached(session):
    calls = {"n": 0}
    orig = session.query

    def counting(*a, **kw):
        calls["n"] += 1
        return orig(*a, **kw)

    session.query = counting
    mid = _mid(session)
    calls["n"] = 0
    build_search_index(session, mid)
    first = calls["n"]
    build_search_index(session, mid)
    assert calls["n"] == first  # 二次走缓存


# --- search() 契约输出 ---


def test_global_search_returns_museums_and_objects(session):
    museums, objects = search(
        session, _FakeStorage(), "梵高", museum_id=None, language="zh"
    )
    assert [o["qid"] for o in objects][0] == "Q45585"
    assert objects[0]["title"] == "星夜" and objects[0]["artist"] == "文森特·梵高"
    assert objects[0]["year"] == "1889"
    # 博物馆段仅全局:查"梵高"不含馆名 → 空
    assert museums == []


def test_museum_search_by_name(session):
    museums, objects = search(
        session, _FakeStorage(), "奥赛", museum_id=None, language="zh"
    )
    assert any(m["slug"] == "orsay" and m["city"] == "巴黎" for m in museums)


def test_scoped_search_has_no_museum_segment(session):
    museums, objects = search(
        session, _FakeStorage(), "奥赛", museum_id=_mid(session), language="zh"
    )
    assert museums == []  # 馆域端点不搜博物馆


def test_no_image_stub_in_results_with_flag(session):
    # "starry" 命中两件(Q45585 有图,Q_STUB 无图 stub)
    _, objects = search(
        session, _FakeStorage(), "starry", museum_id=None, language="zh"
    )
    by_qid = {o["qid"]: o for o in objects}
    assert by_qid["Q45585"]["has_image"] is True and by_qid["Q45585"]["thumbnail"]
    assert by_qid["Q_STUB"]["has_image"] is False
    assert by_qid["Q_STUB"]["thumbnail"] is None  # 无图件诚实 null


def test_museum_slug_on_object(session):
    _, objects = search(session, _FakeStorage(), "星夜", museum_id=None, language="zh")
    assert all(o["museum"] == "orsay" for o in objects)


def test_english_language_resolves_names(session):
    _, objects = search(
        session, _FakeStorage(), "starry", museum_id=None, language="en"
    )
    top = next(o for o in objects if o["qid"] == "Q45585")
    assert top["title"] == "The Starry Night" and top["artist"] == "Vincent van Gogh"


def test_empty_query_search_returns_empty(session):
    assert search(session, _FakeStorage(), "", museum_id=None) == ([], [])


# --- 性能形状(修"转圈圈"):索引自带展示字段,search 零回表;建索引不拖重 JSONB 列 ---


def _capture_sql(session):
    stmts = []
    event.listen(
        session.get_bind(),
        "before_cursor_execute",
        lambda conn, cur, stmt, params, ctx, many: stmts.append(stmt),
    )
    return stmts


def test_build_index_skips_heavy_columns(session):
    # 冷建索引不得加载 sources/evidence_pack(原始包/证据包,冷建慢的主因)
    stmts = _capture_sql(session)
    build_search_index(session)
    joined = " ".join(stmts).lower()
    assert "evidence_pack" not in joined
    assert "museum_objects.sources" not in joined


def test_warm_search_no_object_table_roundtrips(session):
    # 热索引下 search() 的 objects 段全部来自索引,不再逐条回查(原 N+1:每条 4 查询)
    build_search_index(session)
    stmts = _capture_sql(session)
    _, objects = search(
        session, _FakeStorage(), "starry", museum_id=None, language="zh"
    )
    assert len(objects) == 2
    joined = " ".join(stmts).lower()
    assert "museum_objects" not in joined
    assert "artists" not in joined and "object_images" not in joined


def test_scoped_search_reuses_global_index(session):
    # 馆域搜索复用全局索引过滤,热态零 SQL(原先每馆独立冷建)
    mid = _mid(session)
    build_search_index(session)
    stmts = _capture_sql(session)
    _, objects = search(session, _FakeStorage(), "starry", museum_id=mid, language="zh")
    assert len(objects) == 2
    assert stmts == []
