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

    def translate_section(self, text, lang):
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

        def translate_section(self, text, lang):
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
