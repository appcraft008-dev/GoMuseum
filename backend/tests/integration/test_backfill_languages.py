"""补语种(契约"加语言"checklist⑤):存量对象把缺失语言从已存 en 段纯翻译落库。
不重生成、不重接地(忠实度校验继承);含 guide 段与建议问答;幂等。"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.content import (
    CategorySection,
    ObjectContentSection,
    ObjectSuggestedQuestion,
    SectionType,
)
from app.models.museum import Museum
from app.models.museum_object import MuseumObject, ObjectImage
from app.services.enrichment.backfill import backfill_languages
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
            SectionType.__table__,
            CategorySection.__table__,
            ObjectContentSection.__table__,
            ObjectSuggestedQuestion.__table__,
        ],
    )
    s = sessionmaker(bind=engine)()
    m = upsert_museum(s, {"slug": "orsay", "name_en": "Orsay"})
    upsert_object(s, m.id, {"qid": "Q1", "title_en": "A", "category": "painting"})
    upsert_object(s, m.id, {"qid": "Q2", "title_en": "B", "category": "painting"})
    o1 = s.query(MuseumObject).filter_by(qid="Q1").one()
    # Q1:en 已生成(guide+background 发布,zh 已有);Q2:纯 stub 无内容
    for code, body in (("guide", "EN guide."), ("background", "EN background.")):
        s.add(
            ObjectContentSection(
                object_id=o1.id,
                language="en",
                section_code=code,
                body=body,
                status="published",
            )
        )
    s.add(
        ObjectContentSection(
            object_id=o1.id,
            language="zh",
            section_code="guide",
            body="中文讲解。",
            status="published",
        )
    )
    s.add(
        ObjectSuggestedQuestion(
            object_id=o1.id,
            language="en",
            question="Why famous?",
            answer="Because X.",
            status="published",
            sort=1,
        )
    )
    s.commit()
    yield s


class _Tr:
    def __init__(self):
        self.calls = []

    def translate_object(
        self, en_sections, target_langs, titles=None, artists=None, **_kw
    ):
        from app.services.enrichment.quality import SectionQuality

        lang = target_langs[0]
        self.calls.append(("obj", lang, sorted(en_sections)))
        return {
            lang: {
                c: SectionQuality(
                    body=f"{lang} {b}",
                    status="published",
                    grounding_ratio=1.0,
                    conflicts=[],
                    score=1.0,
                )
                for c, b in en_sections.items()
            }
        }

    def translate_section(
        self, text, lang, *, strong=False, title=None, artist=None, **_kw
    ):
        self.calls.append(("sec", lang, text))
        return f"{text}?" if "?" in text else f"{text}_{lang}"

    def check_faithfulness(self, en, translated, lang, title=None, artist=None, **_kw):
        return True, []


def _rows(s, qid, lang):
    o = s.query(MuseumObject).filter_by(qid=qid).one()
    return {
        r.section_code: r
        for r in s.query(ObjectContentSection)
        .filter_by(object_id=o.id, language=lang, status="published")
        .all()
    }


def test_backfill_translates_missing_language_sections(session):
    tr = _Tr()
    out = backfill_languages(session, "orsay", langs=["de"], translator=tr)
    de = _rows(session, "Q1", "de")
    assert set(de) == {"guide", "background"}
    assert de["guide"].body == "de EN guide."
    assert out["objects"] == 1  # Q2 无 en 内容 → 跳过


def test_backfill_only_translates_missing_sections(session):
    # zh 已有 guide → 只补 zh 缺的 background,不重翻已有
    tr = _Tr()
    backfill_languages(session, "orsay", langs=["zh"], translator=tr)
    assert ("obj", "zh", ["background"]) in tr.calls
    zh = _rows(session, "Q1", "zh")
    assert zh["guide"].body == "中文讲解。"  # 原样保留
    assert zh["background"].body == "zh EN background."


def test_backfill_idempotent(session):
    backfill_languages(session, "orsay", langs=["de"], translator=_Tr())
    tr2 = _Tr()
    out2 = backfill_languages(session, "orsay", langs=["de"], translator=tr2)
    assert tr2.calls == []  # 第二遍零翻译
    assert out2["objects"] == 0


def test_backfill_translates_suggested_questions(session):
    backfill_languages(session, "orsay", langs=["de"], translator=_Tr())
    o = session.query(MuseumObject).filter_by(qid="Q1").one()
    qa = (
        session.query(ObjectSuggestedQuestion)
        .filter_by(object_id=o.id, language="de", status="published")
        .all()
    )
    assert len(qa) == 1
    assert qa[0].question.endswith("?")
    assert "Because X." in qa[0].answer


def test_backfill_translates_artist_bio(session):
    # 作者 bio 也是内容:en 有、目标语言缺 → 翻译补(修 de 作者介绍不完整)
    from app.models.artist import Artist

    Artist.__table__.create(bind=session.get_bind(), checkfirst=True)
    o = session.query(MuseumObject).filter_by(qid="Q1").one()
    o.attributes = {"artist_qid": "Q34618"}
    session.add(
        Artist(
            qid="Q34618", name_en="Courbet", bio={"en": "EN bio.", "zh": "中文生平。"}
        )
    )
    session.commit()
    tr = _Tr()
    backfill_languages(session, "orsay", langs=["de", "zh"], translator=tr)
    art = session.query(Artist).filter_by(qid="Q34618").one()
    assert art.bio["de"] == "EN bio._de"  # de 缺 → 翻译补
    assert art.bio["zh"] == "中文生平。"  # 已有不动
    # 幂等:重跑不再翻 bio
    tr2 = _Tr()
    backfill_languages(session, "orsay", langs=["de"], translator=tr2)
    assert all(t != "EN bio." for _, _, t in tr2.calls)


def test_backfill_skips_junk_en_bio_pivot(session):
    # bio.en 是中文(坏值)→ 不作翻译轴心(防垃圾扩散);重生交给 generate 路径
    from app.models.artist import Artist

    Artist.__table__.create(bind=session.get_bind(), checkfirst=True)
    o = session.query(MuseumObject).filter_by(qid="Q1").one()
    o.attributes = {"artist_qid": "Q39931"}
    session.add(Artist(qid="Q39931", name_en="Renoir", bio={"en": "雷诺阿中文简介。"}))
    session.commit()
    tr = _Tr()
    backfill_languages(session, "orsay", langs=["it"], translator=tr)
    art = session.query(Artist).filter_by(qid="Q39931").one()
    assert "it" not in (art.bio or {})  # 坏轴心不翻
    assert all("雷诺阿中文简介" not in t for _, _, t in tr.calls if isinstance(t, str))


def test_backfill_unknown_museum(session):
    out = backfill_languages(session, "nope", langs=["de"], translator=_Tr())
    assert out.get("error") == "unknown museum"


def test_translate_guide_section_first(session, monkeypatch):
    # 流式先出:guide 段必须先于深度模块 persist(前端轮询先看到主讲解)
    import app.services.content_repo as cr

    order = []
    orig = cr.persist_gated_sections

    def spy(db, qid, lang, results, model):
        order.extend(results.keys())
        return orig(db, qid, lang, results, model)

    monkeypatch.setattr(cr, "persist_gated_sections", spy)
    backfill_languages(session, "orsay", langs=["de"], translator=_Tr())
    # Q1 en 有 guide+background,de 缺两者 → guide 先落
    assert order.index("guide") < order.index("background")


# —— 并发与选件(2026-07-29:prod 实测串行补两个大馆要 48 小时) ——


def test_only_objects_with_en_axis_enter_the_queue(session, monkeypatch):
    """查询层就滤掉无 en 轴心的件。prod: louvre 17283 件里只有 303 件有内容,
    不过滤 = 98% 的件白跑一次 translate_object_language 才返回全零。"""
    import app.services.enrichment.backfill as bf

    seen = []
    orig = bf.translate_object_language

    def spy(db, o, lang, translator, model="gpt-4o-mini", **kw):
        seen.append(o.qid)
        return orig(db, o, lang, translator, model, **kw)

    monkeypatch.setattr(bf, "translate_object_language", spy)
    backfill_languages(session, "orsay", langs=["de"], translator=_Tr())
    # Q2 是纯 stub(无 en 段)→ 压根不该被取出来
    assert set(seen) == {"Q1"}


def test_single_object_failure_is_skipped_and_counted(session, monkeypatch):
    """单件失败跳过继续 + 计 errors(批处理纪律①),不炸掉整轮。"""
    import app.services.enrichment.backfill as bf

    def boom(db, o, lang, translator, model="gpt-4o-mini", **kw):
        raise RuntimeError("translator exploded")

    monkeypatch.setattr(bf, "translate_object_language", boom)
    out = backfill_languages(session, "orsay", langs=["de"], translator=_Tr())
    assert out["errors"] == 1
    assert out["objects"] == 0


def test_parallel_workers_produce_same_result_as_serial(session):
    """并发只是提速,产出必须与串行逐字一致(同输入同调用集)。"""
    backfill_languages(session, "orsay", langs=["de"], translator=_Tr(), workers=4)
    de = _rows(session, "Q1", "de")
    assert set(de) == {"guide", "background"}
    assert de["guide"].body == "de EN guide."


def test_translate_passes_artist_english_name_and_museum_name(session):
    """补语种路径必须把作者英文原名 + 馆规范名传到正文与问答两侧
    (半个单一真相源的坑:只接一条路径,另一条永远不会红)。"""
    from app.services.enrichment.backfill import translate_object_language

    m = session.query(Museum).filter_by(slug="orsay").one()
    m.name_zh = "奥赛博物馆"
    o = session.query(MuseumObject).filter_by(qid="Q1").one()
    o.artist_en = "Henri de Toulouse-Lautrec"
    session.commit()
    seen = []

    class _Rec(_Tr):
        def translate_object(self, en_sections, target_langs, **kw):
            seen.append(("section", kw.get("artist_en"), kw.get("museums")))
            return super().translate_object(en_sections, target_langs, **kw)

        def translate_section(self, text, lang, **kw):
            seen.append(("qa", kw.get("artist_en"), kw.get("museum")))
            return super().translate_section(text, lang, **kw)

    translate_object_language(session, o, "zh", _Rec())
    sec = [x for x in seen if x[0] == "section"]
    qa = [x for x in seen if x[0] == "qa"]
    assert sec and all(
        x[1] == "Henri de Toulouse-Lautrec" and x[2] == {"zh": "奥赛博物馆"}
        for x in sec
    )
    assert qa and all(
        x[1] == "Henri de Toulouse-Lautrec" and x[2] == "奥赛博物馆" for x in qa
    )


def _two_objects_same_artist(s):
    # Q1、Q3 同一作者,都有 en 内容
    from app.models.artist import Artist

    Artist.__table__.create(bind=s.get_bind(), checkfirst=True)
    m = s.query(Museum).filter_by(slug="orsay").one()
    upsert_object(s, m.id, {"qid": "Q3", "title_en": "C", "category": "painting"})
    for qid in ("Q1", "Q3"):
        o = s.query(MuseumObject).filter_by(qid=qid).one()
        o.attributes = {"artist_qid": "Q34618"}
        if qid == "Q3":
            s.add(
                ObjectContentSection(
                    object_id=o.id,
                    language="en",
                    section_code="guide",
                    body="EN guide 3.",
                    status="published",
                )
            )
    s.add(Artist(qid="Q34618", name_en="Courbet", bio={"en": "EN bio."}))
    s.commit()


def test_backfill_bio_translated_once_per_artist(session):
    # 同一作者的两件:bio 每门只翻一次(原先每件各翻一次,且并发整 JSON 覆盖写)
    from app.models.artist import Artist

    _two_objects_same_artist(session)
    tr = _Tr()
    out = backfill_languages(
        session, "orsay", langs=["de", "it"], translator=tr, workers=1
    )
    bio_calls = sorted(lang for k, lang, t in tr.calls if t == "EN bio.")
    assert bio_calls == ["de", "it"]
    art = session.query(Artist).filter_by(qid="Q34618").one()
    assert art.bio == {"en": "EN bio.", "de": "EN bio._de", "it": "EN bio._it"}
    assert out["bios"] == 2


def test_backfill_artist_written_only_from_main_thread(session, monkeypatch):
    # 共享作者行只许主线程写(线程里写会互相覆盖,纪律 37)
    import threading

    from app.services.enrichment import backfill

    _two_objects_same_artist(session)
    writers = []
    real = backfill.fill_artist_bio

    def spy(*a, **kw):
        writers.append(threading.current_thread() is threading.main_thread())
        return real(*a, **kw)

    monkeypatch.setattr(backfill, "fill_artist_bio", spy)
    backfill_languages(session, "orsay", langs=["de"], translator=_Tr(), workers=1)
    assert writers and all(writers)


def test_backfill_bio_failure_keeps_other_languages(session):
    from app.models.artist import Artist

    _two_objects_same_artist(session)

    class _TrFail(_Tr):
        def translate_section(self, text, lang, **kw):
            if text == "EN bio." and lang == "de":
                raise RuntimeError("llm down")
            return super().translate_section(text, lang, **kw)

    backfill_languages(
        session, "orsay", langs=["de", "it"], translator=_TrFail(), workers=1
    )
    art = session.query(Artist).filter_by(qid="Q34618").one()
    assert art.bio == {"en": "EN bio.", "it": "EN bio._it"}
