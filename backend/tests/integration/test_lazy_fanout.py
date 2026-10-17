"""补语言阶段(spec 2026-10-17):懒生成完成后,按语言补齐该馆其余语言。
单元测试用串行执行器 + 共享 sqlite 会话(StaticPool 单连接测不了真并发,真并发留给 staging)。"""

from concurrent.futures import Future

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.artist import Artist
from app.models.content import (
    CategorySection,
    ObjectContentSection,
    ObjectSuggestedQuestion,
    SectionType,
)
from app.models.museum import Museum
from app.models.museum_object import MuseumObject, ObjectImage
from app.services.enrichment import lazy
from app.services.enrichment.lang_config import DEFAULT_LANGUAGES
from app.services.object_importer import upsert_museum, upsert_object

BIO_EN = "Claude Monet was a French painter and a founder of Impressionism."


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
            Artist.__table__,
        ],
    )
    s = sessionmaker(bind=engine)()
    m = upsert_museum(s, {"slug": "orsay", "name_en": "Orsay"})
    upsert_object(s, m.id, {"qid": "Q1", "title_en": "A", "category": "painting"})
    o = s.query(MuseumObject).filter_by(qid="Q1").one()
    o.content_status = "ready"
    o.attributes = {**(o.attributes or {}), "artist_qid": "Q296"}
    s.add(Artist(qid="Q296", name_en="Claude Monet", bio={"en": BIO_EN}))
    for lang, code in (("en", "guide"), ("en", "background"), ("fr", "guide")):
        s.add(
            ObjectContentSection(
                object_id=o.id,
                language=lang,
                section_code=code,
                body=f"{lang} {code}.",
                status="published",
            )
        )
    s.commit()
    yield s


class _Abort(BaseException):
    pass


class _Tr:
    def __init__(self, fail_langs=(), base_fail_langs=(), bio_fail_once=(), delay=0):
        self.delay = delay  # 每段翻译的耗时(秒),真线程池测试用来制造"还在排队"
        self.fail_langs = set(fail_langs)
        self.base_fail_langs = set(base_fail_langs)
        self.bio_fail_once = set(bio_fail_once)
        self.langs = []

    def translate_object(self, en_sections, target_langs, **_kw):
        from app.services.enrichment.quality import SectionQuality

        lang = target_langs[0]
        if lang in self.base_fail_langs:
            raise _Abort  # BaseException 的代表(AudioLossBlocked 同类)
        if lang in self.fail_langs:
            raise RuntimeError("llm down")
        if self.delay:
            import time

            time.sleep(self.delay)
        self.langs.append(lang)
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

    def translate_section(self, text, lang, **_kw):
        if text == BIO_EN and lang in self.bio_fail_once:
            self.bio_fail_once.discard(lang)
            raise RuntimeError("bio llm blip")
        return f"{lang}:{text}"

    def check_faithfulness(self, en, translated, lang, **_kw):
        return True, []


class _Serial:
    """串行执行器:submit 立刻跑完,接口够 as_completed 用。"""

    def submit(self, fn, *a):
        f = Future()
        try:
            f.set_result(fn(*a))
        except (
            BaseException
        ) as e:  # 同真实 ThreadPoolExecutor:异常进 future,在 result() 处抛
            f.set_exception(e)
        return f

    def shutdown(self, wait=True, cancel_futures=False):
        pass


def _obj(s):
    return s.query(MuseumObject).filter_by(qid="Q1").one()


def _langs_with_guide(s):
    o = _obj(s)
    return {
        r.language
        for r in s.query(ObjectContentSection).filter_by(
            object_id=o.id, section_code="guide", status="published"
        )
    }


def _run(s, langs, tr=None):
    return lazy._fanout(
        s,
        "Q1",
        langs=langs,
        translator=tr or _Tr(),
        session_factory=lambda: s,
        close=False,
        executor=_Serial(),
    )


def test_fanout_fills_only_languages_without_rows(session):
    # 语言集不写死:配置 3 门、fr 已有 → 只补 de
    out = _run(session, ["en", "fr", "de"])
    assert set(out) == {"de"}
    assert _langs_with_guide(session) == {"en", "fr", "de"}


def test_fanout_language_set_is_configurable(session):
    out = _run(session, ["en", "fr", "de", "it"])
    assert set(out) == {"de", "it"}


def test_fanout_after_en_request_fills_all_other_languages(session):
    # Review Focus 5:请求语言是 en 时没有"请求语言"可排除,其余全补
    o = _obj(session)
    session.query(ObjectContentSection).filter_by(
        object_id=o.id, language="fr"
    ).delete()
    session.commit()
    out = _run(session, ["en", "fr", "de", "it"])
    assert set(out) == {"fr", "de", "it"}


def test_fanout_is_idempotent(session):
    _run(session, ["en", "fr", "de"])
    tr = _Tr()
    assert _run(session, ["en", "fr", "de"], tr) == {}
    assert tr.langs == []


def test_fanout_skips_language_with_needs_review_rows(session):
    o = _obj(session)
    session.add(
        ObjectContentSection(
            object_id=o.id,
            language="de",
            section_code="guide",
            body="x",
            status="needs_review",
        )
    )
    session.commit()
    tr = _Tr()
    assert _run(session, ["en", "fr", "de"], tr) == {}
    assert tr.langs == []


def test_fanout_one_language_failure_isolated(session):
    out = _run(session, ["en", "fr", "de", "it"], _Tr(fail_langs={"de"}))
    assert set(out) == {"it"}
    assert "it" in _langs_with_guide(session)
    assert (_obj(session).attributes or {}).get("lazy_fanout") is None


def test_fanout_clears_marker_and_releases_sem_on_base_exception(session):
    # Review Focus 3
    with pytest.raises(_Abort):
        _run(session, ["en", "fr", "de"], _Tr(base_fail_langs={"de"}))
    assert (_obj(session).attributes or {}).get("lazy_fanout") is None
    assert lazy._FANOUT_SEM.acquire(blocking=False)  # 名额已还
    lazy._FANOUT_SEM.release()


def test_fanout_marker_shrinks_as_languages_finish(session, monkeypatch):
    seen = []
    real = lazy._set_fanout

    def spy(db, obj, pending):
        seen.append(list(pending))
        real(db, obj, pending)

    monkeypatch.setattr(lazy, "_set_fanout", spy)
    _run(session, ["en", "fr", "de", "it"])
    assert seen[0] == ["de", "it"]
    assert seen[-1] == []
    assert (_obj(session).attributes or {}).get("lazy_fanout") is None


def test_fanout_fills_bios_in_main_thread_without_overwrite(session):
    # Review Focus 4:预置 de bio 不被覆盖;it 补上;两者互不丢失
    art = session.query(Artist).filter_by(qid="Q296").one()
    art.bio = {**art.bio, "de": "Bio DE."}
    session.commit()
    _run(session, ["en", "fr", "de", "it"])
    bio = session.query(Artist).filter_by(qid="Q296").one().bio
    assert bio["de"] == "Bio DE."
    assert bio["it"] == f"it:{BIO_EN}"


def test_fanout_threads_never_write_artist(session):
    # include_bio=False 接线:主线程补 it 的 bio 时失败一次 → 线程里不得再补
    # (线程写共享作者行会互相覆盖)。若线程传了 include_bio=True,it 会被补上。
    _run(session, ["en", "fr", "de", "it"], _Tr(bio_fail_once={"it"}))
    bio = session.query(Artist).filter_by(qid="Q296").one().bio
    assert "it" not in bio
    assert bio["de"] == f"de:{BIO_EN}"


def test_fanout_bio_refresh_keeps_concurrent_write(session, monkeypatch):
    # 补语言主线程写 bio 前必须重读:同作者另一件的生成刚补了 es。
    # 并发写要放在 _set_fanout **之后**:它的 commit 会让会话里的对象全部过期,
    # 之前写的话不 refresh 也能读到新值(复审实测的假测试)。
    real = lazy._set_fanout
    done = []

    def set_then_race(db, obj, pending):
        real(db, obj, pending)
        if done:
            return
        done.append(1)
        held = db.query(Artist).filter_by(qid="Q296").one()
        assert "es" not in held.bio  # 本会话载入旧值并持有
        other = sessionmaker(bind=db.get_bind())()
        art = other.query(Artist).filter_by(qid="Q296").one()
        art.bio = {**art.bio, "es": "Bio ES."}
        other.commit()
        set_then_race.held = held  # 持有引用,防 identity map 弱引用回收

    monkeypatch.setattr(lazy, "_set_fanout", set_then_race)
    _run(session, ["en", "fr", "de"])
    bio = session.query(Artist).filter_by(qid="Q296").one().bio
    assert bio["es"] == "Bio ES."
    assert bio["de"] == f"de:{BIO_EN}"


def test_fanout_base_exception_stops_other_languages_before_cleanup(session):
    # 真实线程池(1 个 worker):第一门抛 BaseException 后,排队的语言必须被取消,
    # 函数返回后不能再有段落库(否则标记已清、名额已还,孤儿线程还在写)
    import time
    from concurrent.futures import ThreadPoolExecutor

    with pytest.raises(_Abort):
        lazy._fanout(
            session,
            "Q1",
            langs=["en", "fr", "de", "it", "es", "pl"],
            translator=_Tr(base_fail_langs={"de"}, delay=0.2),
            session_factory=lambda: session,
            close=False,
            executor=ThreadPoolExecutor(max_workers=1),
        )
    after = _langs_with_guide(session)
    # remaining 顺序 de,it,es,pl:de 抛错时 worker 可能已开始 it(会被等完),
    # es/pl 还在排队 → 必须被取消
    assert not ({"es", "pl"} & after)
    time.sleep(1.0)
    assert _langs_with_guide(session) == after  # 返回后再无落库
    assert (_obj(session).attributes or {}).get("lazy_fanout") is None


def test_fanout_tags_rows_with_own_source(session):
    _run(session, ["en", "fr", "de"])
    o = _obj(session)
    src = {
        r.source
        for r in session.query(ObjectContentSection).filter_by(
            object_id=o.id, language="de"
        )
    }
    assert src == {lazy.FANOUT_SOURCE}
    assert lazy.daily_budget_exhausted(session, cap=1) is False  # 不计入懒生成日上限
    assert lazy.daily_budget_exhausted(session, cap=1, source=lazy.FANOUT_SOURCE)


def test_fanout_skipped_when_own_daily_cap_hit(session, monkeypatch):
    monkeypatch.setattr(lazy, "_FANOUT_DAILY_SECTION_CAP", 0)
    tr = _Tr()
    assert _run(session, ["en", "fr", "de"], tr) == {}
    assert tr.langs == []


def test_fanout_skipped_when_sem_full(session):
    assert lazy._FANOUT_SEM.acquire(blocking=False)
    assert lazy._FANOUT_SEM.acquire(blocking=False)
    try:
        tr = _Tr()
        assert _run(session, ["en", "fr", "de"], tr) == {}
        assert tr.langs == []
    finally:
        lazy._FANOUT_SEM.release()
        lazy._FANOUT_SEM.release()


@pytest.mark.parametrize("status", ["empty", "stub"])
def test_fanout_skipped_unless_ready(session, status):
    o = _obj(session)
    o.content_status = status
    session.commit()
    tr = _Tr()
    assert _run(session, ["en", "fr", "de"], tr) == {}
    assert tr.langs == []


def test_museum_languages_reads_catalog(session):
    # 走馆目录配置(有覆盖用覆盖,否则全局默认);不对 orsay 是否有覆盖做假设
    from app.services.enrichment.catalog import MuseumCatalog
    from app.services.enrichment.factory import CATALOG_PATH
    from app.services.enrichment.lang_config import resolve_languages

    cfg = MuseumCatalog.from_file(CATALOG_PATH).get("orsay")
    got = lazy._museum_languages(session, _obj(session))
    assert got == resolve_languages(cfg.languages)
    assert got  # 非空;无覆盖时即 DEFAULT_LANGUAGES


def test_run_lazy_generation_runs_fanout_after_lock_cleared(session, monkeypatch):
    calls = []

    def fake_generate(db, qid, language=None):
        o = db.query(MuseumObject).filter_by(qid=qid).one()
        o.content_status = "ready"
        db.flush()
        return {"qid": qid}

    def fake_fanout(db, qid, **_kw):
        o = db.query(MuseumObject).filter_by(qid=qid).one()
        calls.append(bool((o.attributes or {}).get("lazy_lock_at")))
        return {}

    monkeypatch.setattr(lazy, "_generate", fake_generate)
    monkeypatch.setattr(lazy, "_fanout", fake_fanout)
    lazy.try_acquire_lock(session, _obj(session), require_status=("ready",))
    lazy.run_lazy_generation("Q1", "zh", session_factory=lambda: session, close=False)
    assert calls == [False]  # 跑了一次,且 lazy_lock_at 已清
