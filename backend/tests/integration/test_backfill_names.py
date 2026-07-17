"""显示名回填（铺目录时机）：stub 即有完整 title_i18n / artist_qid / Artist.name_i18n。
契约:多语显示名解析时机=目录铺出时,不等内容生成。fetch/translator 注入,离线可测。"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.artist import Artist
from app.models.museum import Museum
from app.models.museum_object import MuseumObject, ObjectImage
from app.services.enrichment.backfill import backfill_display_names
from app.services.object_importer import upsert_museum, upsert_object


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
    m = upsert_museum(s, {"slug": "orsay", "name_en": "Orsay"})
    # stub:无 title_i18n 无 artist_qid(截图问题场景)
    upsert_object(
        s,
        m.id,
        {
            "qid": "Q1",
            "title_en": "The Wounded Man",
            "artist_en": "Gustave Courbet",
            "category": "painting",
        },
    )
    # 已有完整 i18n 的对象(幂等:不应再抓/翻)
    upsert_object(
        s,
        m.id,
        {
            "qid": "Q2",
            "title_en": "Olympia",
            "artist_en": "Manet",
            "category": "painting",
            "attributes": {
                "title_i18n": {"en": "Olympia", "fr": "Olympia", "zh": "奥林匹亚"},
                "artist_qid": "Q296",
            },
        },
    )
    s.commit()
    yield s


class _Translator:
    def __init__(self):
        self.calls = []

    def translate_section(self, text, lang, *, strong=False, title=None, artist=None):
        self.calls.append((text, lang))
        return f"{text}_{lang}"


def _labels(mapping):
    def fetch(qid, langs, **kw):
        return mapping.get(qid, {})

    return fetch


def test_backfill_fills_title_i18n_authoritative_then_translate(session):
    tr = _Translator()
    out = backfill_display_names(
        session,
        "orsay",
        translator=tr,
        langs=["en", "fr", "zh"],
        fetch_labels=_labels({"Q1": {"fr": "L'Homme blessé", "zh": "受伤的男人"}}),
        fetch_creators=lambda qids: {},
    )
    o = session.query(MuseumObject).filter_by(qid="Q1").one()
    ti = o.attributes["title_i18n"]
    assert ti["fr"] == "L'Homme blessé"  # 权威
    assert ti["zh"] == "受伤的男人"  # 权威
    assert ti["en"] == "The Wounded Man"  # en 轴心兜底
    assert o.title_zh == "受伤的男人"  # 列同步填(zh 视图旧回退链也受益)
    assert out["titles"] == 1


def test_backfill_translates_when_no_authoritative_label(session):
    tr = _Translator()
    backfill_display_names(
        session,
        "orsay",
        translator=tr,
        langs=["en", "zh"],
        fetch_labels=_labels({}),
        fetch_creators=lambda qids: {},
    )
    o = session.query(MuseumObject).filter_by(qid="Q1").one()
    assert o.attributes["title_i18n"]["zh"] == "The Wounded Man_zh"  # 翻译兜底


def test_backfill_prefers_authoritative_en_label(session):
    # 目录把法语标签存进 title_en 的场景(Régates à Argenteuil):en 权威标签应纠正它
    o = session.query(MuseumObject).filter_by(qid="Q1").one()
    o.title_en = "Régates à Argenteuil"
    session.commit()
    backfill_display_names(
        session,
        "orsay",
        translator=_Translator(),
        langs=["en", "zh"],
        fetch_labels=_labels(
            {"Q1": {"en": "Regattas at Argenteuil", "zh": "阿让特伊的帆船赛"}}
        ),
        fetch_creators=lambda qids: {},
    )
    o = session.query(MuseumObject).filter_by(qid="Q1").one()
    assert o.attributes["title_i18n"]["en"] == "Regattas at Argenteuil"


def test_backfill_idempotent_skips_complete_objects(session):
    tr = _Translator()
    out = backfill_display_names(
        session,
        "orsay",
        translator=tr,
        langs=["en", "fr", "zh"],
        fetch_labels=_labels({}),
        fetch_creators=lambda qids: {},
    )
    # Q2 已完整 → 不翻;Q1 缺 → 翻 fr/zh
    assert out["titles"] == 1
    assert all("Olympia" not in t for t, _ in tr.calls)


def test_backfill_fills_artist_qid_and_artist_names(session):
    tr = _Translator()
    out = backfill_display_names(
        session,
        "orsay",
        translator=tr,
        langs=["en", "zh"],
        fetch_labels=_labels({"Q34618": {"zh": "居斯塔夫·库尔贝"}}),
        fetch_creators=lambda qids: {"Q1": "Q34618"},
    )
    o = session.query(MuseumObject).filter_by(qid="Q1").one()
    assert o.attributes["artist_qid"] == "Q34618"
    art = session.query(Artist).filter_by(qid="Q34618").one()
    assert art.name_en == "Gustave Courbet"
    assert art.name_i18n["zh"] == "居斯塔夫·库尔贝"  # 权威
    assert art.name_zh == "居斯塔夫·库尔贝"
    # Q2 已带 artist_qid(Q296)但无 Artist 行 → 也补名字行(共 2)
    assert out["artists"] == 2
    assert session.query(Artist).filter_by(qid="Q296").one().name_en == "Manet"


def test_backfill_merges_existing_artist_langs(session):
    # 已有 Artist 行:补缺失语种,不覆盖已有
    session.add(Artist(qid="Q296", name_en="Manet", name_i18n={"zh": "马奈"}))
    session.commit()
    backfill_display_names(
        session,
        "orsay",
        translator=_Translator(),
        langs=["en", "zh", "fr"],
        fetch_labels=_labels({"Q296": {"zh": "爱德华·马奈", "fr": "Édouard Manet"}}),
        fetch_creators=lambda qids: {},
    )
    art = session.query(Artist).filter_by(qid="Q296").one()
    assert art.name_i18n["zh"] == "马奈"  # 已有不覆盖
    assert art.name_i18n["fr"] == "Édouard Manet"  # 缺失补权威


def test_backfill_pivots_on_any_label_when_no_en(session):
    # 冷门件无 en/zh 标签只有 fr(Q17492795 Le Chat blanc 场景):
    # 以 fr 权威标签为轴翻出缺失语言,并回填 title_en 列 → 任何视图都不再显 QID
    o = session.query(MuseumObject).filter_by(qid="Q1").one()
    o.title_en = None
    o.title_zh = None
    session.commit()
    backfill_display_names(
        session,
        "orsay",
        translator=_Translator(),
        langs=["en", "fr", "zh"],
        fetch_labels=_labels({"Q1": {"fr": "Le Chat blanc"}}),
        fetch_creators=lambda qids: {},
    )
    o = session.query(MuseumObject).filter_by(qid="Q1").one()
    ti = o.attributes["title_i18n"]
    assert ti["fr"] == "Le Chat blanc"  # 权威
    assert ti["en"] == "Le Chat blanc_en"  # fr 轴翻 en
    assert ti["zh"] == "Le Chat blanc_zh"  # fr 轴翻 zh
    assert o.title_en == "Le Chat blanc_en"  # en 列回填(轴心补齐)


def test_backfill_retranslates_junk_zh_value(session):
    # 《Vue de toits》类:zh 位存了无汉字的值(翻译失败残留)→ 视为缺失重解析
    o = session.query(MuseumObject).filter_by(qid="Q1").one()
    o.attributes = {"title_i18n": {"en": "View of Roofs", "zh": "《Vue de toits》"}}
    session.commit()
    backfill_display_names(
        session,
        "orsay",
        translator=_Translator(),
        langs=["en", "zh"],
        fetch_labels=_labels({}),
        fetch_creators=lambda qids: {},
    )
    o = session.query(MuseumObject).filter_by(qid="Q1").one()
    assert o.attributes["title_i18n"]["zh"] == "View of Roofs_zh"  # 重翻覆盖坏值


def test_fill_i18n_prefers_translate_name(session):
    # 显示名翻译走 translate_name(标题专用 prompt),而非正文 translate_section
    from app.services.enrichment.pipeline import _fill_i18n

    calls = []

    class _T:
        def translate_name(self, text, lang):
            calls.append(("name", text, lang))
            return f"{text}~{lang}"

        def translate_section(
            self, text, lang, *, strong=False, title=None, artist=None
        ):
            calls.append(("section", text, lang))
            return f"{text}_{lang}"

    out = _fill_i18n({}, "The Cat", {}, ["en", "zh"], _T())
    assert out["zh"] == "The Cat~zh"
    assert all(kind == "name" for kind, *_ in calls)


def test_translate_name_strips_brackets_and_quotes():
    from app.services.enrichment.translator import ContentTranslator

    tr = ContentTranslator(lambda system, user: "《屋顶景色》")
    assert tr.translate_name("Vue de toits", "zh") == "屋顶景色"
    tr2 = ContentTranslator(lambda system, user: '"White Cat"')
    assert tr2.translate_name("Le Chat blanc", "en") == "White Cat"


def test_backfill_strips_surrounding_brackets_from_existing_values(session):
    # 旧翻译残留《中文题》→ 剥外层书名号并落库(与权威标签风格一致);内容不重翻
    o = session.query(MuseumObject).filter_by(qid="Q1").one()
    o.attributes = {"title_i18n": {"en": "Poplars", "zh": "《白杨树》"}}
    session.commit()
    tr = _Translator()
    backfill_display_names(
        session,
        "orsay",
        translator=tr,
        langs=["en", "zh"],
        fetch_labels=_labels({}),
        fetch_creators=lambda qids: {},
    )
    o = session.query(MuseumObject).filter_by(qid="Q1").one()
    assert o.attributes["title_i18n"]["zh"] == "白杨树"  # 剥号,不重翻
    assert all(t != "Poplars" for t, _ in tr.calls)  # 标题未触发重翻(作者名翻译不算)


def test_fetch_creators_batches_large_qid_sets():
    # prod 教训:1300+ QID 单条 VALUES 查询 URL 超长(HTTP 414)→ 必须分批
    from app.services.enrichment.backfill import _fetch_creators

    calls = []

    def fake_run(sparql):
        calls.append(sparql)
        return [
            {
                "item": {"value": "http://www.wikidata.org/entity/Q1"},
                "creator": {"value": "http://www.wikidata.org/entity/Q9"},
            }
        ]

    qids = [f"Q{i}" for i in range(450)]
    out = _fetch_creators(qids, run_query=fake_run)
    assert len(calls) == 3  # 450 / 200 每批 → 3 次
    assert all(sparql.count("wd:Q") <= 200 for sparql in calls)
    assert out["Q1"] == "Q9"


def test_backfill_unknown_museum(session):
    out = backfill_display_names(
        session,
        "nope",
        translator=_Translator(),
        langs=["en"],
        fetch_labels=_labels({}),
        fetch_creators=lambda qids: {},
    )
    assert out.get("error") == "unknown museum"


def test_backfill_survives_per_object_fetch_failure(session):
    # prod 教训:单件 Wikidata 超时炸死整个回填(253/1942 即止,进度全丢)
    # → 单件失败跳过继续 + 分批 commit
    def flaky(qid, langs, **kw):
        if qid == "Q1":
            raise TimeoutError("wikidata read timeout")
        return {}

    tr = _Translator()
    out = backfill_display_names(
        session,
        "orsay",
        translator=tr,
        langs=["en", "zh"],
        fetch_labels=flaky,
        fetch_creators=lambda qids: {},
    )
    # Q1 失败被跳过,Q2 及作者流程正常走完,整体不抛
    assert out.get("errors", 0) >= 1
    assert "titles" in out


def test_fetch_creators_survives_batch_failure():
    # prod 教训2:Wikidata 502 炸在 creators 批量查询(循环之前),整个回填没起步就死
    # → 单批失败重试一次,仍失败跳过该批继续(幂等重跑再补)
    from app.services.enrichment.backfill import _fetch_creators

    calls = {"n": 0}

    def flaky(sparql):
        calls["n"] += 1
        if "Q0 " in sparql or sparql.rstrip().endswith(
            "Q0 } ?item wdt:P170 ?creator }"
        ):
            pass
        if calls["n"] <= 2 and "wd:Q0" in sparql:  # 第一批(含重试)都失败
            raise RuntimeError("502 Bad Gateway")
        return [
            {
                "item": {"value": "http://www.wikidata.org/entity/Q300"},
                "creator": {"value": "http://www.wikidata.org/entity/Q9"},
            }
        ]

    qids = [f"Q{i}" for i in range(450)]  # 3 批
    out = _fetch_creators(qids, run_query=flaky, retry_wait=0)
    assert out.get("Q300") == "Q9"  # 后续批正常
    assert calls["n"] >= 4  # 第一批试了2次(原+重试),另两批各1次


def test_backfill_fills_artist_facts_i18n(session):
    # 交接③:names 回填顺带补 国籍/代表作 多语(权威→翻译兜底→en;幂等)
    from app.models.artist import Artist

    Artist.__table__.create(bind=session.get_bind(), checkfirst=True)
    o = session.query(MuseumObject).filter_by(qid="Q1").one()
    o.attributes = {"artist_qid": "Q296"}
    session.add(
        Artist(
            qid="Q296",
            name_en="Manet",
            name_i18n={"en": "Manet", "zh": "马奈"},
            nationality="France",
            notable_works=["Olympia"],
        )
    )
    session.commit()
    tr = _Translator()
    backfill_display_names(
        session,
        "orsay",
        translator=tr,
        langs=["en", "zh", "de"],
        fetch_labels=_labels({}),
        fetch_creators=lambda qids: {},
        fetch_artist_facts_i18n=lambda qid, langs: {
            "nationality_i18n": {"zh": "法国"},  # zh 权威;de 缺 → 翻译兜底
            "notable_works_i18n": {},  # 全缺 → 从 en 列翻译兜底
        },
    )
    art = session.query(Artist).filter_by(qid="Q296").one()
    assert art.nationality_i18n["zh"] == "法国"  # 权威
    assert art.nationality_i18n["de"] == "France_de"  # 翻译兜底(_Tr 回显)
    assert art.nationality_i18n["en"] == "France"  # en 列作轴
    assert art.notable_works_i18n["zh"] == ["Olympia_zh"]
    assert art.notable_works_i18n["en"] == ["Olympia"]


def test_backfill_refresh_langs_replaces_with_authoritative(session):
    # 繁简修复:refresh 模式下,该语言有权威标签则覆盖存量(繁→简);无标签保留(翻译值不动)
    o = session.query(MuseumObject).filter_by(qid="Q1").one()
    o.attributes = {
        "title_i18n": {"en": "The Wounded Man", "zh": "受傷的男人"}  # 繁体存量
    }
    session.commit()
    o2 = session.query(MuseumObject).filter_by(qid="Q2").one()
    # Q2 zh 是翻译兜底产物,Wikidata 无 zh 标签 → refresh 不应动它
    backfill_display_names(
        session,
        "orsay",
        translator=_Translator(),
        langs=["en", "zh"],
        fetch_labels=_labels({"Q1": {"zh": "受伤的男人"}}),
        fetch_creators=lambda qids: {},
        refresh_langs=["zh"],
    )
    o = session.query(MuseumObject).filter_by(qid="Q1").one()
    assert o.attributes["title_i18n"]["zh"] == "受伤的男人"  # 权威简体覆盖繁体
    o2 = session.query(MuseumObject).filter_by(qid="Q2").one()
    assert o2.attributes["title_i18n"]["zh"] == "奥林匹亚"  # 无标签→保留原值


def test_retranslate_langs_regenerates_machine_translated(session):
    # A修复:retranslate-langs 对无权威标签的机翻显示名强制重译(修卧 nude/奥林比亚);
    # 有权威标签仍用权威
    o = session.query(MuseumObject).filter_by(qid="Q1").one()
    o.title_en = "Reclining Nude"
    o.attributes = {"title_i18n": {"en": "Reclining Nude", "zh": "卧 nude 女人"}}
    session.commit()
    backfill_display_names(
        session,
        "orsay",
        translator=_Translator(),
        langs=["en", "zh"],
        fetch_labels=_labels({}),  # 无权威标签
        fetch_creators=lambda qids: {},
        retranslate_langs=["zh"],
    )
    o = session.query(MuseumObject).filter_by(qid="Q1").one()
    zh = o.attributes["title_i18n"]["zh"]
    assert "nude" not in zh  # 坏译名被重译(不再含英文残片)
    assert zh != "卧 nude 女人"


def test_bio_en_usable_rejects_french():
    # 问题3:en bio 含法语(né/est un peintre français)=坏值,不可作轴心,需重生
    from app.services.enrichment.backfill import bio_en_usable

    assert bio_en_usable({"en": "Monet was a French painter born in 1840."}) is True
    assert (
        bio_en_usable(
            {"en": "Claude Monet, né en 1840 à Paris, est un peintre français."}
        )
        is False
    )  # 法语
    assert bio_en_usable({"en": "Courbet était un peintre réaliste."}) is False


def test_bio_en_usable_uses_detector_any_language():
    # Task5:bio_en_usable 用检测器,不再打地鼠(德语等也被拦)
    from app.services.enrichment.backfill import bio_en_usable

    assert (
        bio_en_usable(
            {
                "en": "Monet was a French Impressionist painter and a leader of the movement."
            }
        )
        is True
    )
    assert (
        bio_en_usable(
            {
                "en": "Claude Monet, né en 1840 à Paris, est un peintre français reconnu partout."
            }
        )
        is False
    )
    assert (
        bio_en_usable(
            {
                "en": "Claude Monet war ein französischer Maler und Mitbegründer des Impressionismus."
            }
        )
        is False
    )  # 德语:打地鼠时代漏网,检测器拦
