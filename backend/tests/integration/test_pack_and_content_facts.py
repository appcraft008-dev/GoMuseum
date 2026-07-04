import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.artist import Artist
from app.models.content import (  # noqa: F401  (建表用)
    CategorySection,
    ObjectContentSection,
    ObjectSuggestedQuestion,
    SectionType,
)
from app.models.museum import Museum
from app.models.museum_object import MuseumObject, ObjectImage
from app.services.museum_repo import get_museum_pack, get_object_content
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
            CategorySection.__table__,
            ObjectContentSection.__table__,
            ObjectSuggestedQuestion.__table__,
            SectionType.__table__,
            Artist.__table__,
        ],
    )
    s = sessionmaker(bind=engine)()
    m = upsert_museum(s, {"slug": "orsay", "name_zh": "奥赛博物馆", "name_en": "Orsay"})
    upsert_object(
        s,
        m.id,
        {
            "qid": "Q1",
            "title_zh": "世界的起源",
            "title_en": "Origin",
            "artist_zh": "库尔贝",
            "artist_en": "Courbet",
            "year": "1866",
            "category": "painting",
            "inventory_number": "RF 1995 10",
            "image": "http://img/x.jpg",
            "attributes": {
                "medium_fr": "huile sur toile",
                "dimensions": "46 x 55 cm",
                "exhibitions_fr": "1988, New York#1996, Paris",
                # 多语显示名走 title_i18n(权威→翻译→en);列 title_zh 仅回退兜底
                "title_i18n": {"zh": "世界的起源", "en": "Origin"},
            },
        },
    )
    upsert_object(s, m.id, {"qid": "Q2", "title_en": "S", "category": "sculpture"})
    s.query(MuseumObject).filter_by(qid="Q1").one().content_status = "ready"
    s.commit()
    yield s


def test_pack_includes_category_facet(session):
    cats = {c["code"]: c for c in get_museum_pack(session, "orsay", "zh")["categories"]}
    assert cats["all"]["count"] == 2
    assert cats["painting"] == {"code": "painting", "label": "绘画", "count": 1}
    assert cats["sculpture"]["label"] == "雕塑"


def test_content_includes_facts_title_images_status(session):
    o = session.query(MuseumObject).filter_by(qid="Q1").one()
    session.add(
        ObjectContentSection(
            object_id=o.id,
            language="zh",
            section_code="guide",
            body="讲解正文。",
            status="published",
        )
    )
    session.commit()
    d = get_object_content(session, "orsay", "Q1", "zh")
    assert d["title"] == "世界的起源" and d["status"] == "ready"
    assert d["images"][0]["url"] == "https://img/x.jpg"  # upsert_object 把 http→https
    f = d["facts"]
    assert f["artist"] == "库尔贝" and f["date"] == "1866"
    assert f["medium"] == "油画" and f["dimensions"] == "46 × 55 cm"  # 已人性化
    assert f["inventory"] == "RF 1995 10" and f["location"] == "奥赛博物馆"
    # exhibitions 已移出面板(进证据包材料级)
    assert f["exhibitions"] == []


def test_content_en_localizes(session):
    d = get_object_content(session, "orsay", "Q1", "en")
    assert d["title"] == "Origin" and d["facts"]["artist"] == "Courbet"


def test_content_returns_default_guide(session):
    from app.models.content import ObjectContentSection
    from app.models.museum_object import MuseumObject
    from app.services.museum_repo import get_object_content

    o = session.query(MuseumObject).filter_by(qid="Q1").one()
    session.add(
        ObjectContentSection(
            object_id=o.id,
            language="zh",
            section_code="guide",
            body="单主线默认讲解。",
            status="published",
        )
    )
    session.commit()
    d = get_object_content(session, "orsay", "Q1", "zh")
    assert d["default_guide"]["body"] == "单主线默认讲解。"
    assert "audio_url" in d["default_guide"]
    assert all(t["section_code"] != "guide" for t in d["tabs"])


def test_content_default_guide_null_when_absent(session):
    from app.services.museum_repo import get_object_content

    d = get_object_content(session, "orsay", "Q1", "en")
    assert d["default_guide"] is None


def test_content_facts_curated_and_humanized(session):
    from app.models.museum_object import MuseumObject
    from app.services.museum_repo import get_object_content

    o = session.query(MuseumObject).filter_by(qid="Q1").one()
    o.attributes = {
        "medium_fr": "huile sur toile",
        "dimensions": "en mètres : L. 0,55 ; H. 0,46",
        "provenance_fr": "coll X",
        "exhibitions_fr": "1988#1996",
        "bibliography_fr": "Tabarant 66",
    }
    o.evidence_pack = {
        "facts": [
            {
                "claim": "材质",
                "value": "Oil on canvas",
                "source": "wikidata:P186",
                "topic": "analysis",
                "tier": "wall_label",
            },
        ],
        "narrative": [],
        "flagged": [],
    }
    session.commit()
    f = get_object_content(session, "orsay", "Q1", "zh")["facts"]
    # academic 项移出面板(返空/None)
    assert not f.get("bibliography")
    assert not f.get("provenance")
    assert not f.get("exhibitions")
    # medium 人性化(zh huile→油画);基础项保留
    assert f["medium"] == "油画"
    assert "artist" in f and "date" in f


def test_content_facts_medium_prefers_evidence_pack_p186(session):
    # 契约§4:medium 优先证据包干净源(Wikidata P186);存量 pack 为 tier=material、多值
    from app.models.museum_object import MuseumObject
    from app.services.museum_repo import get_object_content

    o = session.query(MuseumObject).filter_by(qid="Q1").one()
    o.attributes = {"medium_fr": "technique mixte"}
    o.evidence_pack = {
        "facts": [
            {
                "claim": "材质",
                "value": "oil paint",
                "source": "wikidata:P186",
                "topic": "analysis",
                "tier": "material",
            },
            {
                "claim": "材质",
                "value": "canvas",
                "source": "wikidata:P186",
                "topic": "analysis",
                "tier": "material",
            },
        ],
        "narrative": [],
        "flagged": [],
    }
    session.commit()
    assert get_object_content(session, "orsay", "Q1", "zh")["facts"]["medium"] == "油画"
    assert (
        get_object_content(session, "orsay", "Q1", "en")["facts"]["medium"]
        == "Oil on canvas"
    )


def test_content_facts_medium_humanized_from_attributes(session):
    from app.models.museum_object import MuseumObject
    from app.services.museum_repo import get_object_content

    o = session.query(MuseumObject).filter_by(qid="Q1").one()
    o.attributes = {"medium_fr": "huile sur toile"}
    o.evidence_pack = None
    session.commit()
    f = get_object_content(session, "orsay", "Q1", "zh")["facts"]
    assert f["medium"] == "油画"  # 人性化,非原始法语


def test_humanize_medium_and_dimensions():
    from app.services.museum_repo import _humanize_dimensions, _humanize_medium

    assert _humanize_medium("peinture à l'huile (toile)", "zh") == "油画"
    assert _humanize_medium("huile sur toile", "en") == "Oil on canvas"
    assert _humanize_medium("bronze", "zh") == "青铜"
    assert (
        _humanize_medium("technique inconnue", "zh") == "technique inconnue"
    )  # 未知原样
    assert _humanize_medium(None, "zh") is None
    assert _humanize_dimensions("en mètres : L. 0,55 ; H. 0,46") == "55 × 46 cm"
    assert _humanize_dimensions("H. 208, l. 264.5") == "208 × 264.5 cm"
    assert _humanize_dimensions(None) is None


def test_tabs_exclude_overview(session):
    from app.services.museum_repo import get_object_content

    d = get_object_content(session, "orsay", "Q1", "zh")
    assert all(t["section_code"] != "overview" for t in d["tabs"])


def test_content_artist_card(session):
    from app.models.artist import Artist
    from app.models.museum_object import MuseumObject
    from app.services.museum_repo import get_object_content

    o = session.query(MuseumObject).filter_by(qid="Q1").one()
    o.attributes = {"artist_qid": "Q40599"}
    session.add(
        Artist(
            qid="Q40599",
            name_zh="马奈",
            name_en="Manet",
            name_i18n={"zh": "马奈", "en": "Manet"},
            birth="1832",
            death="1883",
            nationality="France",
            notable_works=["Olympia"],
            bio={"zh": "马奈生平叙事。"},
        )
    )
    session.commit()
    d = get_object_content(session, "orsay", "Q1", "zh")
    a = d["artist"]
    assert a["name"] == "马奈" and a["birth"] == "1832" and a["death"] == "1883"
    assert a["nationality"] == "France" and a["notable_works"] == ["Olympia"]
    assert a["bio"] == "马奈生平叙事。"
    assert all(t["section_code"] != "artist" for t in d["tabs"])  # artist 段不在 tabs


def test_content_artist_card_present_when_thin(session):
    from app.models.museum_object import MuseumObject
    from app.services.museum_repo import get_object_content

    o = session.query(MuseumObject).filter_by(qid="Q1").one()
    o.attributes = {}
    session.commit()
    d = get_object_content(session, "orsay", "Q1", "zh")
    assert "artist" in d and "name" in d["artist"]  # 缺结构化+缺bio,卡仍返(name兜底)


def test_tabs_hide_empty_and_unpublished(session):
    from app.models.content import CategorySection, ObjectContentSection, SectionType
    from app.models.museum_object import MuseumObject
    from app.services.museum_repo import get_object_content

    o = session.query(MuseumObject).filter_by(qid="Q1").one()
    session.add(SectionType(code="significance", icon="i"))
    session.add(SectionType(code="background", icon="i"))
    session.add(
        CategorySection(category="painting", section_code="significance", sort_order=1)
    )
    session.add(
        CategorySection(category="painting", section_code="background", sort_order=2)
    )
    # significance: needs_review(应隐);background: published 有正文(应显)
    session.add(
        ObjectContentSection(
            object_id=o.id,
            language="zh",
            section_code="significance",
            body="",
            status="needs_review",
        )
    )
    session.add(
        ObjectContentSection(
            object_id=o.id,
            language="zh",
            section_code="background",
            body="背景正文。",
            status="published",
        )
    )
    session.commit()
    codes = [
        t["section_code"]
        for t in get_object_content(session, "orsay", "Q1", "zh")["tabs"]
    ]
    assert "significance" not in codes  # 空/未发布 → 隐
    assert "background" in codes  # 有发布正文 → 显


def test_artist_card_from_artists_table(session):
    from app.models.artist import Artist
    from app.models.museum_object import MuseumObject
    from app.services.museum_repo import get_object_content

    o = session.query(MuseumObject).filter_by(qid="Q1").one()
    o.attributes = {"artist_qid": "Q296"}
    session.add(
        Artist(
            qid="Q296",
            name_zh="梵高",
            name_en="Van Gogh",
            name_i18n={"zh": "梵高", "en": "Van Gogh"},
            birth="1853",
            nationality="Netherlands",
            notable_works=["Starry Night"],
            bio={"zh": "梵高生平。"},
        )
    )
    session.commit()
    a = get_object_content(session, "orsay", "Q1", "zh")["artist"]
    assert a["name"] == "梵高" and a["birth"] == "1853" and a["bio"] == "梵高生平。"
    assert a["notable_works"] == ["Starry Night"]


def test_content_title_and_artist_resolve_by_language(session):
    from app.models.artist import Artist
    from app.models.museum_object import MuseumObject
    from app.services.museum_repo import get_object_content

    o = session.query(MuseumObject).filter_by(qid="Q1").one()
    o.title_en = "Starry Night"
    o.attributes = {
        "artist_qid": "Q7",
        "title_i18n": {"en": "Starry Night", "fr": "La Nuit étoilée"},
    }
    session.add(
        Artist(
            qid="Q7",
            name_en="Van Gogh",
            name_i18n={"en": "Van Gogh", "fr": "Van Gogh"},
        )
    )
    session.commit()
    assert (
        get_object_content(session, "orsay", "Q1", "fr")["title"] == "La Nuit étoilée"
    )
    assert get_object_content(session, "orsay", "Q1", "en")["title"] == "Starry Night"
    assert (
        get_object_content(session, "orsay", "Q1", "fr")["artist"]["name"] == "Van Gogh"
    )


def test_status_empty_when_language_has_no_content(session):
    from app.services.museum_repo import get_object_content

    d = get_object_content(session, "orsay", "Q1", "fr")  # fr 无 guide 无 tab
    assert d["status"] == "empty"


def test_title_falls_back_to_zh_column_when_no_i18n(session):
    # 未富化 stub:有 title_zh 无 title_i18n → zh 视图仍显中文名(不退成英文)
    from app.models.museum_object import MuseumObject
    from app.services.museum_repo import get_object_content

    o = session.query(MuseumObject).filter_by(qid="Q1").one()
    o.title_zh = "中文名"
    o.title_en = "English Name"
    o.attributes = {}  # 无 title_i18n
    session.commit()
    assert get_object_content(session, "orsay", "Q1", "zh")["title"] == "中文名"
    assert get_object_content(session, "orsay", "Q1", "en")["title"] == "English Name"


def test_pack_category_labels_localized_all_six_languages(session):
    # 前端交接 2026-07-03:de/es/it 界面分类标签不本地化(只配了 zh/en/fr,回退英文)
    from app.services.museum_repo import get_museum_pack

    expect = {
        "de": {"painting": "Malerei", "sculpture": "Skulpturen"},
        "es": {"painting": "Pintura", "sculpture": "Escultura"},
        "it": {"painting": "Dipinti", "sculpture": "Sculture"},
        "fr": {"painting": "Peinture", "sculpture": "Sculpture"},
    }
    for lang, m in expect.items():
        cats = {
            c["code"]: c["label"]
            for c in get_museum_pack(session, "orsay", lang)["categories"]
        }
        assert cats["painting"] == m["painting"], (lang, cats)
        assert cats["sculpture"] == m["sculpture"], (lang, cats)


def test_category_label_unknown_language_falls_back_to_english():
    from app.services.museum_repo import _category_label

    assert _category_label("painting", "xx") == "Painting"  # 缺译回退 en,不返 null
    assert _category_label("works_on_paper", "it") == "Opere su carta"


def test_content_images_use_large_tier_and_pack_uses_thumb(session):
    from app.models.museum_object import ObjectImage
    from app.services.museum_repo import get_museum_pack, get_object_content

    o = session.query(MuseumObject).filter_by(qid="Q1").one()
    img = session.query(ObjectImage).filter_by(object_id=o.id).first()
    img.image_key = "images/Q1/0"
    session.commit()
    d = get_object_content(session, "orsay", "Q1", "zh")
    assert d["images"][0]["url"].endswith("images/Q1/0_large.jpg")  # 详情=large
    pack = get_museum_pack(session, "orsay", "zh")
    art = next(a for a in pack["artworks"] if a["qid"] == "Q1")
    assert art["image"].endswith("images/Q1/0_thumb.jpg")  # 馆包=thumb


def test_artist_card_nationality_and_works_localized(session):
    # 交接③:国籍/代表作按 language 本地化(i18n 优先,缺退 en 列,不返 null)
    from app.models.artist import Artist
    from app.models.museum_object import MuseumObject
    from app.services.museum_repo import get_object_content

    o = session.query(MuseumObject).filter_by(qid="Q1").one()
    o.attributes = {"artist_qid": "Q296"}
    session.add(
        Artist(
            qid="Q296",
            name_en="Manet",
            nationality="France",
            notable_works=["Olympia", "The Balcony"],
            nationality_i18n={"zh": "法国", "de": "Frankreich"},
            notable_works_i18n={"zh": ["奥林匹亚", "阳台"]},
        )
    )
    session.commit()
    zh = get_object_content(session, "orsay", "Q1", "zh")["artist"]
    assert zh["nationality"] == "法国"
    assert zh["notable_works"] == ["奥林匹亚", "阳台"]
    de = get_object_content(session, "orsay", "Q1", "de")["artist"]
    assert de["nationality"] == "Frankreich"
    assert de["notable_works"] == ["Olympia", "The Balcony"]  # 缺 de 列表 → en 兜底
    it = get_object_content(session, "orsay", "Q1", "it")["artist"]
    assert it["nationality"] == "France"  # 缺 it → en 列兜底


def test_content_exposes_generating_flag(session):
    # 加法字段:前端三态判断(生成中/资料不足/待完善可重试)的精确信号
    from datetime import datetime, timezone

    from app.services.museum_repo import get_object_content

    o = session.query(MuseumObject).filter_by(qid="Q1").one()
    d = get_object_content(session, "orsay", "Q1", "zh")
    assert d["generating"] is False
    o.attributes = {
        **(o.attributes or {}),
        "lazy_lock_at": datetime.now(timezone.utc).isoformat(),
    }
    session.commit()
    d = get_object_content(session, "orsay", "Q1", "zh")
    assert d["generating"] is True


def test_content_exposes_generating_flag(session):
    # 加法字段:前端三态判断(生成中/资料不足/待完善可重试)的精确信号
    from datetime import datetime, timezone

    from app.services.museum_repo import get_object_content

    o = session.query(MuseumObject).filter_by(qid="Q1").one()
    d = get_object_content(session, "orsay", "Q1", "zh")
    assert d["generating"] is False
    o.attributes = {
        **(o.attributes or {}),
        "lazy_lock_at": datetime.now(timezone.utc).isoformat(),
    }
    session.commit()
    d = get_object_content(session, "orsay", "Q1", "zh")
    assert d["generating"] is True
