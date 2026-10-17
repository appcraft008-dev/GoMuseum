# 懒生成补齐全部语言 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 懒生成完成后,后台按语言并行把该馆配置的其余语言(段 + 问答 + 作者 bio)补齐,首个用户的体验不变。

**Architecture:** `generate_object` 一行不改。`run_lazy_generation` 在释放 `_SEM` 和 `lazy_lock_at` 之后新增"补语言阶段" `_fanout`:主线程串行补作者 bio,线程池按语言调 `translate_object_language(include_bio=False)`,用 `attributes["lazy_fanout"] = {"at", "pending"}` 做按语言的进行中标记(心跳 TTL 5 分钟)。`generating` 和 `maybe_trigger` 都改为认这个 `pending` 列表;懒翻译判据改为"按 en 段逐个查缺"。

**Tech Stack:** FastAPI / SQLAlchemy / pytest(sqlite StaticPool)/ poetry。

**Spec:** `docs/superpowers/specs/2026-10-17-lazy-gen-all-languages-design.md`

## Global Constraints

- 语言集只从 `resolve_languages(MuseumCatalog.get(slug).languages)` 来;代码里不出现语言个数或新的语言代码常量(en 轴心除外,既有约定)。
- `generate_object` 与首屏路径不改。
- 契约形状不变:`/content` 不增删字段,`generating` 仍是 bool。
- 纪律 37:共享实体(`artists`)只补缺;本特性写入面 = spec 第六节表格,作废已有音频数必须为 0。
- 新常量:`_FANOUT_SEM = threading.Semaphore(2)`、`_FANOUT_WORKERS = 4`、`_FANOUT_TTL = timedelta(minutes=5)`、`_FANOUT_DAILY_SECTION_CAP = 3000`、`FANOUT_SOURCE = "ai_lazy_fanout"`。
- 不改的常量:`_LAZY_DAILY_SECTION_CAP=1000`、`WEIGHT_GENERATION=8`、`WEIGHT_TRANSLATION=3`、`CAP_PER_USER=160`、`CAP_PER_IP=300`、`_LOCK_TTL=10 分钟`。
- 后端测试命令:在 `backend/` 下 `poetry run pytest <path> -q --no-cov`(不带 `--no-cov` 会因覆盖率门槛报 FAIL)。
- worktree 里 husky 钩子不跑:每次提交前手动 `poetry run black <改过的 .py> && poetry run isort <改过的 .py>`。
- 提交信息遵循 Conventional Commits,结尾带:
  ```
  Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_01EQgJmCjbBm5Z2hmZMXmurZ
  ```
- staging→main 合并只能用户来;prod 只做只读查询。

## Review Focus

1. 补语言进行中 App 打开某门还在 `pending` 的语言、且该语言 guide 已落库 → `generating` 必须仍为 true(否则 App `keepAlive` 永久缓存半成品)。Task 2 测试 `test_generating_true_while_pending_even_with_guide`。
2. 半途失败的语言(有 guide、缺深度段)→ 下次请求必须能被懒翻译补齐;只缺"翻不过闸(needs_review)"的段时不能反复点火。Task 3 两个测试。
3. 线程里抛 `BaseException`(如 `AudioLossBlocked`)→ 排队的语言被取消、在跑的等完,**之后**才清标记、还名额;函数返回后不再有段落库。Task 4 `test_fanout_clears_marker_and_releases_sem_on_base_exception` + `test_fanout_base_exception_stops_other_languages_before_cleanup`(真实线程池)。
4. 预置作者某语言 bio → 补语言阶段不覆盖它;另一会话同时补的语言不被整 JSON 覆盖丢掉;线程里不写作者行。Task 1 + Task 4(`test_fanout_bio_refresh_keeps_concurrent_write`、`test_fanout_threads_never_write_artist`)。
5. 请求语言是 en → 其余语言全部补上(不少补一门)。Task 4 `test_fanout_after_en_request_fills_all_other_languages`。

---

### Task 1: 作者 bio 补缺抽成函数 + `include_bio` 开关

**Files:**
- Modify: `backend/app/services/enrichment/backfill.py`(`translate_object_language` 签名约 146 行;bio 块约 221–234 行)
- Test: `backend/tests/integration/test_fill_artist_bio.py`(新建)

**Interfaces:**
- Produces:
  - `fill_artist_bio(db, o, lang, translator, *, refresh=False) -> int`:返回补上的条数(0 或 1),不 commit。
  - `translate_object_language(db, o, lang, translator, model="gpt-4o-mini", *, include_bio=True) -> dict`:`include_bio=False` 时不碰 `artists`。

- [ ] **Step 1: 写失败测试**

新建 `backend/tests/integration/test_fill_artist_bio.py`:

```python
"""作者 bio 补缺(纪律 37:共享实体只补缺)。补语言阶段要在主线程单独调它,
线程里的 translate_object_language 传 include_bio=False 不碰 artists(spec 2026-10-17 §4.2)。"""

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
from app.services.enrichment.backfill import (
    fill_artist_bio,
    translate_object_language,
)
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
    o.attributes = {**(o.attributes or {}), "artist_qid": "Q296"}
    s.add(Artist(qid="Q296", name_en="Claude Monet", bio={"en": BIO_EN, "fr": "Bio FR."}))
    s.add(
        ObjectContentSection(
            object_id=o.id,
            language="en",
            section_code="guide",
            body="EN guide.",
            status="published",
        )
    )
    s.commit()
    yield s


class _Tr:
    def __init__(self):
        self.calls = []

    def translate_object(self, en_sections, target_langs, **_kw):
        from app.services.enrichment.quality import SectionQuality

        lang = target_langs[0]
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
        self.calls.append((lang, text))
        return f"{lang}:{text}"

    def check_faithfulness(self, en, translated, lang, **_kw):
        return True, []


def _obj(s):
    return s.query(MuseumObject).filter_by(qid="Q1").one()


def _bio(s):
    return s.query(Artist).filter_by(qid="Q296").one().bio


def test_fill_artist_bio_adds_missing_language(session):
    tr = _Tr()
    assert fill_artist_bio(session, _obj(session), "de", tr) == 1
    assert _bio(session)["de"] == f"de:{BIO_EN}"


def test_fill_artist_bio_never_overwrites_existing(session):
    tr = _Tr()
    assert fill_artist_bio(session, _obj(session), "fr", tr) == 0
    assert _bio(session)["fr"] == "Bio FR."
    assert tr.calls == []


def test_fill_artist_bio_refresh_keeps_concurrent_write(session):
    # 另一条会话(同作者另一件的生成)先补了 it;refresh=True 写 de 时不能把 it 覆盖掉
    # 持有引用:作者行留在本会话 identity map 里(否则弱引用被回收、query 本来就重读库,
    # 去掉 refresh 也能过 —— 独立审查实测抓到的假测试)
    held = session.query(Artist).filter_by(qid="Q296").one()
    assert "it" not in held.bio
    other = sessionmaker(bind=session.get_bind())()
    art = other.query(Artist).filter_by(qid="Q296").one()
    art.bio = {**art.bio, "it": "Bio IT."}
    other.commit()
    fill_artist_bio(session, _obj(session), "de", _Tr(), refresh=True)
    session.commit()
    assert set(_bio(session)) == {"en", "fr", "it", "de"}


def test_translate_object_language_include_bio_false_leaves_artist(session):
    out = translate_object_language(
        session, _obj(session), "de", _Tr(), include_bio=False
    )
    assert out["bios"] == 0
    assert "de" not in _bio(session)
    assert out["sections"] == 1  # 段照常翻


def test_translate_object_language_default_still_fills_bio(session):
    out = translate_object_language(session, _obj(session), "de", _Tr())
    assert out["bios"] == 1
    assert _bio(session)["de"] == f"de:{BIO_EN}"
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && poetry run pytest tests/integration/test_fill_artist_bio.py -q --no-cov`
Expected: collection 报错 `ImportError: cannot import name 'fill_artist_bio'`

- [ ] **Step 3: 实现**

在 `backfill.py` 里 `translate_object_language` 定义之前加:

```python
def fill_artist_bio(db, o, lang, translator, *, refresh=False) -> int:
    """该件作者缺 lang 的 bio → 从有效 en 纯翻译补上。**只补缺**(纪律 37:作者跨馆共享)。
    返回补了几条(0/1),不 commit。
    refresh=True:写前重读作者行。bio 是整 JSON 覆盖写,补语言阶段与同作者另一件的生成
    可能同时改这一行,重读把丢更新的窗口压到最小(spec 2026-10-17 §4.2)。"""
    aqid = (o.attributes or {}).get("artist_qid")
    if not aqid:
        return 0
    art = db.query(Artist).filter_by(qid=aqid).first()
    if art is None:
        return 0
    if refresh:
        db.refresh(art)
    # 坏 en(含汉字)不作轴心,防垃圾扩散;重生交给 generate 路径
    bio_en = (art.bio or {}).get("en") if bio_en_usable(art.bio) else None
    if not bio_en or (art.bio or {}).get(lang):
        return 0
    try:
        art.bio = {**(art.bio or {}), lang: translator.translate_section(bio_en, lang)}
    except Exception:
        return 0
    return 1
```

`translate_object_language` 签名改为:

```python
def translate_object_language(
    db, o, lang, translator, model="gpt-4o-mini", *, include_bio=True
) -> dict:
```

docstring 末尾加一行:`include_bio=False:不碰作者行(补语言阶段多线程调用时由主线程统一补 bio)。`

把函数末尾整段 bio 块(从 `aqid = (o.attributes or {}).get("artist_qid")` 到 `except Exception: pass`)替换为:

```python
    if include_bio:
        counts["bios"] += fill_artist_bio(db, o, lang, translator)
```

- [ ] **Step 4: 跑测试确认通过,并跑现有补语种测试**

Run: `cd backend && poetry run pytest tests/integration/test_fill_artist_bio.py tests/integration/test_backfill_languages.py -q --no-cov`
Expected: 全部 PASS

- [ ] **Step 5: 格式化并提交**

```bash
cd backend && poetry run black app/services/enrichment/backfill.py tests/integration/test_fill_artist_bio.py && poetry run isort app/services/enrichment/backfill.py tests/integration/test_fill_artist_bio.py
cd .. && git add backend/app/services/enrichment/backfill.py backend/tests/integration/test_fill_artist_bio.py
git commit -m "refactor(backfill): 作者 bio 补缺抽成 fill_artist_bio,translate_object_language 加 include_bio"
```

---

### Task 2: 按语言的补语言标记 + `generating` 接线

**Files:**
- Modify: `backend/app/services/enrichment/lazy.py`(常量区、`lock_active` 附近)
- Modify: `backend/app/services/museum_repo.py`(约 908 行 import、约 924 行 `generating`)
- Test: `backend/tests/integration/test_lazy_generation.py`(末尾追加)、`backend/tests/integration/test_pack_and_content_facts.py`(末尾追加)

**Interfaces:**
- Produces(都在 `lazy.py`):
  - 常量 `_FANOUT_TTL = timedelta(minutes=5)`
  - `fanout_pending(obj) -> list[str]`:标记有效时返回还没补完的语言,否则 `[]`
  - `generating_for(obj, language) -> bool`
  - `_set_fanout(db, obj, pending: list[str]) -> None`:写前 `db.refresh(obj)`,写 `{"at": now, "pending": pending}`,commit
  - `_clear_fanout(db, obj) -> None`:写前 `db.refresh(obj)`,删 `lazy_fanout` 键,commit

- [ ] **Step 1: 写失败测试**

在 `tests/integration/test_lazy_generation.py` 末尾追加:

```python
# ── 补语言阶段的按语言标记(spec 2026-10-17 §4.3)──────────────────────


def test_fanout_pending_and_generating_for(session):
    from app.services.enrichment import lazy

    o = _obj(session)
    assert lazy.fanout_pending(o) == []
    lazy._set_fanout(session, o, ["de", "it"])
    o = _obj(session)
    assert lazy.fanout_pending(o) == ["de", "it"]
    assert lazy.generating_for(o, "de") is True
    assert lazy.generating_for(o, "zh") is False  # 不在 pending:已补完或不归这次补
    lazy._clear_fanout(session, o)
    assert lazy.fanout_pending(_obj(session)) == []


def test_generating_true_while_pending_even_with_guide(session):
    # Review Focus 1:de 的 guide 已落库但深度段没翻完 → 仍算生成中,
    # 否则 App 在 generating=false 时 keepAlive,用户这次会话再也看不到深度段
    from app.services.enrichment import lazy

    o = _obj(session)
    o.content_status = "ready"
    session.commit()
    _publish(session, "Q1", "de")
    lazy._set_fanout(session, _obj(session), ["de"])
    assert lazy.generating_for(_obj(session), "de") is True


def test_fanout_marker_expires_without_heartbeat(session):
    from app.services.enrichment import lazy

    o = _obj(session)
    stale = (datetime.now(timezone.utc) - timedelta(minutes=6)).isoformat()
    o.attributes = {
        **(o.attributes or {}),
        "lazy_fanout": {"at": stale, "pending": ["de"]},
    }
    session.commit()
    assert lazy.fanout_pending(_obj(session)) == []
    assert lazy.generating_for(_obj(session), "de") is False


def test_fanout_marker_bad_value_treated_as_absent(session):
    from app.services.enrichment import lazy

    o = _obj(session)
    o.attributes = {**(o.attributes or {}), "lazy_fanout": {"at": "garbage"}}
    session.commit()
    assert lazy.fanout_pending(_obj(session)) == []


def test_set_fanout_keeps_other_attribute_keys(session):
    # 音频锁也在同一个 attributes JSON 里读改写:写标记前重读,不能抹掉别的键
    from app.services.enrichment import lazy

    o = _obj(session)
    other = sessionmaker(bind=session.get_bind())()
    oo = other.query(MuseumObject).filter_by(qid="Q1").one()
    oo.attributes = {**(oo.attributes or {}), "audio_lock": {"en:guide": "x"}}
    other.commit()
    lazy._set_fanout(session, o, ["de"])
    assert _obj(session).attributes.get("audio_lock") == {"en:guide": "x"}
```

在 `tests/integration/test_pack_and_content_facts.py` 末尾追加:

```python
def test_content_generating_follows_fanout_pending(session):
    # 补语言阶段(spec 2026-10-17 §4.3):只对还在 pending 的语言报 generating=true
    from app.services.enrichment.lazy import _set_fanout
    from app.services.museum_repo import get_object_content

    o = session.query(MuseumObject).filter_by(qid="Q1").one()
    _set_fanout(session, o, ["de"])
    assert get_object_content(session, "orsay", "Q1", "de")["generating"] is True
    assert get_object_content(session, "orsay", "Q1", "zh")["generating"] is False
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && poetry run pytest tests/integration/test_lazy_generation.py tests/integration/test_pack_and_content_facts.py -q --no-cov -k "fanout or generating"`
Expected: FAIL,`AttributeError: module 'app.services.enrichment.lazy' has no attribute '_set_fanout'`(以及 content 测试的 ImportError)

- [ ] **Step 3: 实现**

`lazy.py` 常量区 `_LOCK_TTL` 下面加:

```python
# 补语言阶段(spec 2026-10-17):懒生成完成后按语言并行补齐该馆其余语言。
# 标记 attributes.lazy_fanout = {"at": 心跳时刻, "pending": [还没补完的语言]}。
# 心跳 = 每补完一门刷新 at:慢任务不会过期;进程被部署杀掉后最多空等 5 分钟。
_FANOUT_TTL = timedelta(minutes=5)
```

`lock_active` 函数后面加:

```python
def fanout_pending(obj: MuseumObject) -> list[str]:
    """补语言进行中、还没补完的语言;无标记/心跳超时/坏值 → []。"""
    f = (obj.attributes or {}).get("lazy_fanout") or {}
    try:
        if datetime.now(timezone.utc) - datetime.fromisoformat(f["at"]) >= _FANOUT_TTL:
            return []
    except (KeyError, TypeError, ValueError):
        return []
    return list(f.get("pending") or [])


def generating_for(obj: MuseumObject, language) -> bool:
    """端点 generating 字段:整件在懒生成/懒翻译,或这门语言还在补语言阶段的 pending 里。
    ⚠️ 必须是"这门语言整门翻完前一直 true":App 在 false 时 keepAlive 缓存结果
    (catalog_providers.dart),只有 guide 就报 false 会让深度段永远看不到。"""
    return lock_active(obj) or language in fanout_pending(obj)


def _set_fanout(db, obj: MuseumObject, pending) -> None:
    # 写前重读:音频锁也在同一个 attributes JSON 里读改写(lazy_audio),压小覆盖窗口
    db.refresh(obj)
    obj.attributes = {
        **(obj.attributes or {}),
        "lazy_fanout": {
            "at": datetime.now(timezone.utc).isoformat(),
            "pending": list(pending),
        },
    }
    db.commit()


def _clear_fanout(db, obj: MuseumObject) -> None:
    db.refresh(obj)
    attrs = dict(obj.attributes or {})
    attrs.pop("lazy_fanout", None)
    obj.attributes = attrs
    db.commit()
```

`museum_repo.py`:把 `from app.services.enrichment.lazy import lock_active` 改为
`from app.services.enrichment.lazy import generating_for`,把
`"generating": lock_active(obj),` 改为 `"generating": generating_for(obj, language),`,
并把上方注释改为 `# 加法字段(2026-07-04):前端三态精确信号——true=懒生成/懒翻译/该语言补语言进行中`。
先 `grep -n "lock_active" app/services/museum_repo.py` 确认没有别处还在用它。

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && poetry run pytest tests/integration/test_lazy_generation.py tests/integration/test_pack_and_content_facts.py tests/integration/test_object_content_endpoint.py -q --no-cov`
Expected: 全部 PASS

- [ ] **Step 5: 格式化并提交**

```bash
cd backend && poetry run black app/services/enrichment/lazy.py app/services/museum_repo.py tests/integration/test_lazy_generation.py tests/integration/test_pack_and_content_facts.py && poetry run isort app/services/enrichment/lazy.py app/services/museum_repo.py
cd .. && git add -u backend
git commit -m "feat(lazy): 补语言按语言进行中标记,generating 按请求语言判断"
```

---

### Task 3: 懒翻译判据改为按 en 段逐个查缺 + 补语言中不点火

**Files:**
- Modify: `backend/app/services/enrichment/lazy.py`(`_has_any_section` 约 254 行;`maybe_trigger` 的 `wants_translation` 约 415 行)
- Test: `backend/tests/integration/test_lazy_generation.py`(末尾追加)

**Interfaces:**
- Consumes: Task 2 的 `fanout_pending(obj)`
- Produces: `_has_missing_section(db, object_id, lang) -> bool`;删除 `_has_any_section`

- [ ] **Step 1: 写失败测试**

在 `tests/integration/test_lazy_generation.py` 末尾追加:

```python
def _ready(s):
    o = _obj(s)
    o.content_status = "ready"
    s.commit()


def _trigger(s, language):
    scheduled = []
    maybe_trigger(
        s,
        "Q1",
        schedule=lambda fn, *a: scheduled.append((fn.__name__, a)),
        environment="staging",
        language=language,
    )
    return [x for x in scheduled if x[0] == "run_lazy_translation"]


def test_half_done_language_retriggers_translation(session):
    # Review Focus 2:de 有 guide、缺 en 已发布的 background(半途失败)→ 懒翻译能补齐
    _ready(session)
    _publish(session, "Q1", "en")
    _publish(session, "Q1", "en", code="background")
    _publish(session, "Q1", "de")
    assert _trigger(session, "de") == [("run_lazy_translation", ("Q1", "de"))]


def test_gated_only_gap_does_not_retrigger(session):
    # de 的 background 存在但翻不过闸(needs_review)→ 算"有",不反复点火烧钱
    _ready(session)
    _publish(session, "Q1", "en")
    _publish(session, "Q1", "en", code="background")
    _publish(session, "Q1", "de")
    o = _obj(session)
    session.add(
        ObjectContentSection(
            object_id=o.id,
            language="de",
            section_code="background",
            body="x",
            status="needs_review",
        )
    )
    session.commit()
    assert _trigger(session, "de") == []


def test_no_translation_while_language_pending_in_fanout(session):
    # 补语言阶段正在补 de → 不再另起一路懒翻译(防重复翻译、覆盖段、作废音频)
    from app.services.enrichment import lazy

    _ready(session)
    _publish(session, "Q1", "en")
    lazy._set_fanout(session, _obj(session), ["de"])
    assert _trigger(session, "de") == []
    assert _trigger(session, "it") == [("run_lazy_translation", ("Q1", "it"))]
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && poetry run pytest tests/integration/test_lazy_generation.py -q --no-cov -k "half_done or gated_only or pending_in_fanout"`
Expected: `test_half_done_language_retriggers_translation` 和 `test_no_translation_while_language_pending_in_fanout` FAIL(前者得到 `[]`,后者 de 被调度);`test_gated_only_gap_does_not_retrigger` 可能已 PASS(现有判据下也不触发)——这是预期,它守的是新判据不回归。

- [ ] **Step 3: 实现**

把 `_has_any_section` 整个函数替换为:

```python
def _has_missing_section(db, object_id, lang) -> bool:
    """en 已发布的段里,有该语言**一行都没有**的(任何状态都算有)。
    取代原「该语言有任一段就不再触发」:那个判据下,半途失败(有 guide、缺深度段)的语言
    永远补不齐,补语言阶段会把这种半成品放大(spec 2026-10-17 §七)。
    needs_review 也算有 → 翻不过闸的段不会被反复点火烧钱。"""
    from app.models.content import ObjectContentSection as S

    en = {
        c
        for (c,) in db.query(S.section_code).filter(
            S.object_id == object_id,
            S.language == "en",
            S.status == "published",
            S.body.isnot(None),
        )
    }
    have = {
        c
        for (c,) in db.query(S.section_code).filter(
            S.object_id == object_id, S.language == lang
        )
    }
    return bool(en - have)
```

`maybe_trigger` 里的 `wants_translation` 改为:

```python
    wants_translation = (
        o.content_status == "ready"
        and language
        and language != "en"
        and language not in fanout_pending(o)
        and _has_missing_section(db, o.id, language)
        and _has_published(db, o.id, "en")
    )
```

然后 `grep -rn "_has_any_section" app tests` 确认没有残留引用。

- [ ] **Step 4: 跑测试确认通过(含现有懒生成/端点测试)**

Run: `cd backend && poetry run pytest tests/integration/test_lazy_generation.py tests/integration/test_object_content_endpoint.py -q --no-cov`
Expected: 全部 PASS(现有 `test_lazy_translate_not_retriggered_when_gated`、`test_lazy_translate_still_fires_when_no_sections` 也要过)

- [ ] **Step 5: 格式化并提交**

```bash
cd backend && poetry run black app/services/enrichment/lazy.py tests/integration/test_lazy_generation.py
cd .. && git add -u backend
git commit -m "fix(lazy): 懒翻译按 en 段逐个查缺,半途失败的语言能自愈;补语言中不点火"
```

---

### Task 4: 补语言阶段 `_fanout` + 接到 `run_lazy_generation`

**Files:**
- Modify: `backend/app/services/enrichment/lazy.py`
- Modify: `backend/tests/integration/test_lazy_generation.py`(`test_lazy_generation_only_request_language` 加一行 monkeypatch)
- Test: `backend/tests/integration/test_lazy_fanout.py`(新建)

**Interfaces:**
- Consumes: Task 1 `fill_artist_bio(db, o, lang, translator, *, refresh=False) -> int`、`translate_object_language(..., include_bio=False)`;Task 2 `_set_fanout`、`_clear_fanout`、`fanout_pending`
- Produces:
  - 常量 `_FANOUT_SEM`、`_FANOUT_WORKERS = 4`、`_FANOUT_DAILY_SECTION_CAP = 3000`、`FANOUT_SOURCE = "ai_lazy_fanout"`
  - `daily_budget_exhausted(db, cap=_LAZY_DAILY_SECTION_CAP, source=LAZY_SOURCE) -> bool`(加 `source` 参数,默认值行为不变)
  - `_tag_lazy_rows(db, obj, since, source=LAZY_SOURCE) -> None`(加 `source` 参数)
  - `_museum_languages(db, obj) -> list[str]`
  - `_fanout_langs(db, obj, langs) -> list[str]`
  - `_fanout(db, qid, *, langs=None, translator=None, session_factory=None, close=True, executor=None) -> dict`:返回 `{lang: translate_object_language 的计数}`;前置条件不满足返回 `{}`
  - `_run_fanout(qid, *, session_factory=None, close=True) -> None`

**Ruling(写计划时已定,spec 第二节/4.1 已同步):**
- `_fanout_langs` 只排除 en 和"这件已有任一行"的语言,不单独排除请求语言。请求语言正常已有行,自然被排除;它在生成阶段一行都没落成时,补上它是对的。
- 首轮生成清 `lazy_lock_at` 到 `_set_fanout` 之间仍有几条查询长的窗口(`_has_published`、`_fanout_langs`、读馆目录、预算 count)。窗口内另一门语言的用户打开会另起一路懒翻译,和补语言重复翻同一门。代价是多花一次翻译费;覆盖段会清掉该段音频,但新段几秒前才写、来不及有人点播生成音频。不为此把补语言的准备挪进 `_run_locked`(那会占着 `_SEM`)。

- [ ] **Step 1: 写失败测试**

新建 `backend/tests/integration/test_lazy_fanout.py`:

```python
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
        except BaseException as e:  # 同真实 ThreadPoolExecutor:异常进 future,在 result() 处抛
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
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && poetry run pytest tests/integration/test_lazy_fanout.py -q --no-cov`
Expected: FAIL,`AttributeError: module 'app.services.enrichment.lazy' has no attribute '_fanout'` 等

- [ ] **Step 3: 实现**

`lazy.py` 顶部 import 加 `from concurrent.futures import ThreadPoolExecutor, as_completed`。

常量区 `_FANOUT_TTL` 下面加:

```python
# ponytail: 进程级同时最多 2 件补语言,满了跳过不排队(其余语言回到按请求懒翻译)
_FANOUT_SEM = threading.Semaphore(2)
_FANOUT_WORKERS = 4  # 每件按语言并行;2 件 × 4 = 最多 8 路 mini 调用
# 补语言写的段打自己的来源,不挤占懒生成日上限(计入的话 1000 段只够约 31 件/天);
# 但要有自己的上限,不靠"只跟在生成后面"推理封顶:en 用户触发时每件要补的语言更多。
# 3000 段 ÷ 每门约 3 段 ≈ 1000 门次 × $0.0035 ≈ 最坏 $3.5/天(spec §4.4)。
FANOUT_SOURCE = "ai_lazy_fanout"
_FANOUT_DAILY_SECTION_CAP = 3000
```

`_tag_lazy_rows` 签名改为 `def _tag_lazy_rows(db, obj: MuseumObject, since, source=LAZY_SOURCE) -> None:`,函数体里 `.update({"source": LAZY_SOURCE}, ...)` 改为 `.update({"source": source}, ...)`。

`daily_budget_exhausted` 签名改为 `def daily_budget_exhausted(db, cap: int = _LAZY_DAILY_SECTION_CAP, source: str = LAZY_SOURCE) -> bool:`,过滤条件 `ObjectContentSection.source == LAZY_SOURCE` 改为 `ObjectContentSection.source == source`。docstring 末尾加一句:`source=FANOUT_SOURCE 时管补语言自己的日上限(spec 2026-10-17 §4.4)。`

`run_lazy_translation` 之前加:

```python
def _museum_languages(db, obj: MuseumObject) -> list[str]:
    """该馆配置的语言集(museums.yaml 馆级覆盖,否则全局默认)——不写死语言个数。"""
    from app.models.museum import Museum
    from app.services.enrichment.catalog import MuseumCatalog
    from app.services.enrichment.factory import CATALOG_PATH
    from app.services.enrichment.lang_config import resolve_languages

    slug = db.query(Museum.slug).filter_by(id=obj.museum_id).scalar()
    return resolve_languages(MuseumCatalog.from_file(CATALOG_PATH).get(slug).languages)


def _fanout_langs(db, obj: MuseumObject, langs) -> list[str]:
    """要补的语言 = 配置语言集里这件**一行都还没有**的(en 轴心除外)。幂等,跑两次不重复花钱;
    有 needs_review 行的语言也不补(不碰已有段)。"""
    from app.models.content import ObjectContentSection

    have = {
        lang
        for (lang,) in db.query(ObjectContentSection.language)
        .filter(ObjectContentSection.object_id == obj.id)
        .distinct()
    }
    return [lang for lang in langs if lang != "en" and lang not in have]


def _fanout(
    db,
    qid: str,
    *,
    langs=None,
    translator=None,
    session_factory=None,
    close=True,
    executor=None,
) -> dict:
    """补语言阶段(spec 2026-10-17):懒生成完成后,把该馆其余语言的段/问答/作者 bio 补齐。
    不占 _SEM 和 lazy_lock_at;按语言的进行中标记见 fanout_pending。
    前置条件不满足(未 ready / 无 en / 无可补语言 / 自己的日上限 / 名额满)→ 返回 {},
    其余语言回到按请求懒翻译。测试注入 langs/translator/session_factory/executor。"""
    o = db.query(MuseumObject).filter_by(qid=qid).one_or_none()
    if o is None or o.content_status != "ready" or not _has_published(db, o.id, "en"):
        return {}
    remaining = _fanout_langs(
        db, o, langs if langs is not None else _museum_languages(db, o)
    )
    if not remaining:
        return {}
    if daily_budget_exhausted(db, _FANOUT_DAILY_SECTION_CAP, FANOUT_SOURCE):
        logger.warning("lazy fanout: 当日补语言预算用尽,跳过 qid=%s", qid)
        return {}
    if not _FANOUT_SEM.acquire(blocking=False):
        return {}
    # acquire 后紧跟 try:之后任何一步抛异常都要还名额、清标记
    t0 = datetime.now(timezone.utc)
    out: dict = {}
    try:
        pending = list(remaining)
        # 先写标记再做其它初始化:首轮生成已清 lazy_lock_at,这之间别的语言用户打开会
        # 另起一路懒翻译。标记越早写,这个窗口越小(剩几条查询的时长,见 Ruling)。
        _set_fanout(db, o, pending)
        from app.services.enrichment.backfill import (
            fill_artist_bio,
            translate_object_language,
        )

        if translator is None:
            from app.services.enrichment.factory import build_translator

            translator = build_translator("translate")
        if session_factory is None:
            from app.core.database import guarded_sessionmaker

            # 带音频损失闸(纪律 37);绑同一个 engine,同 backfill_languages
            session_factory = guarded_sessionmaker(bind=db.get_bind())
        # 作者 bio 是跨馆共享行、整 JSON 覆盖写:线程里写会互相覆盖。主线程先逐语言补,
        # 写前重读、写完即提交(纪律 37 只补缺)。
        for lang in remaining:
            if fill_artist_bio(db, o, lang, translator, refresh=True):
                db.commit()
        oid = o.id

        def _one(lang):
            s = session_factory()  # 线程内独立 session:session 非线程安全
            try:
                c = translate_object_language(
                    s, s.get(MuseumObject, oid), lang, translator, include_bio=False
                )
                s.commit()  # 保险:persist_* 已逐段提交,这里通常是空操作
                return c
            finally:
                if close:
                    s.close()

        pool = executor or ThreadPoolExecutor(max_workers=_FANOUT_WORKERS)
        try:
            futs = {pool.submit(_one, lang): lang for lang in remaining}
            for f in as_completed(futs):
                lang = futs[f]
                try:
                    out[lang] = f.result()
                except Exception:
                    logger.exception("lazy fanout failed: %s/%s", qid, lang)
                pending.remove(lang)
                # 每完成一门:打来源标签(进程被杀也已计入补语言日上限)+ 心跳,
                # 这门语言的 generating 随之转 false
                _tag_lazy_rows(db, o, t0, FANOUT_SOURCE)
                _set_fanout(db, o, pending)
        finally:
            # BaseException(如 AudioLossBlocked)从 result() 冒出来时,别的语言还在跑或排队:
            # 取消排队的、等在跑的结束,**之后**才清标记还名额 —— 否则孤儿线程在标记清掉后
            # 继续写,generating 提前转 false、懒翻译重复点火(独立审查实测)
            pool.shutdown(wait=True, cancel_futures=True)
    finally:
        try:
            db.rollback()  # 之前的写都已提交;BaseException 后会话可能处于失败态
            _tag_lazy_rows(db, o, t0, FANOUT_SOURCE)
            _clear_fanout(db, o)
        finally:
            _FANOUT_SEM.release()
    return out


def _run_fanout(qid: str, *, session_factory=None, close=True) -> None:
    """补语言后台骨架:自带会话,失败只记日志(其余语言回到按请求懒翻译)。"""
    if session_factory is None:
        from app.core.database import SessionLocal

        session_factory = SessionLocal
    db = session_factory()
    try:
        out = _fanout(db, qid)
        if out:
            logger.info("lazy fanout done: %s -> %s", qid, out)
    except Exception:
        db.rollback()
        logger.exception("lazy fanout failed: %s", qid)
    finally:
        if close:
            db.close()
```

`run_lazy_generation` 改为:

```python
def run_lazy_generation(
    qid: str, language: str | None = None, *, session_factory=None, close=True
) -> None:
    """stub 首访 → 生成英语轴心 + 请求语言;完成后补语言阶段补齐该馆其余语言
    (此时 _SEM 与 lazy_lock_at 都已释放,首屏和请求者自己的语言不受影响)。"""
    _run_locked(
        qid,
        lambda db: _generate(db, qid, language),
        "lazy generation",
        session_factory=session_factory,
        close=close,
    )
    _run_fanout(qid, session_factory=session_factory, close=close)
```

修改现有测试 `test_lazy_generation_only_request_language`(`tests/integration/test_lazy_generation.py` 约 396 行):在 `monkeypatch.setattr("app.services.enrichment.pipeline.generate_object", ...)` 后面加一行
`monkeypatch.setattr(lazy, "_run_fanout", lambda *a, **k: None)  # 本测试只验生成阶段的语言;补语言见 test_lazy_fanout`。
否则它会走真实翻译器打网络。

实现时逐行核对两处"签名 + 函数体"成对的改动(`_tag_lazy_rows` 和 `daily_budget_exhausted` 都是签名加参数、函数体里把 `LAZY_SOURCE` 换成参数),只改签名不改函数体时测试报的是断言失败而不是 ImportError,不好定位。

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && poetry run pytest tests/integration/test_lazy_fanout.py tests/integration/test_lazy_generation.py tests/integration/test_fill_artist_bio.py tests/integration/test_backfill_languages.py tests/integration/test_object_content_endpoint.py -q --no-cov`
Expected: 全部 PASS

- [ ] **Step 5: 格式化并提交**

```bash
cd backend && poetry run black app/services/enrichment/lazy.py tests/integration/test_lazy_fanout.py tests/integration/test_lazy_generation.py && poetry run isort app/services/enrichment/lazy.py tests/integration/test_lazy_fanout.py
cd .. && git add backend/app/services/enrichment/lazy.py backend/tests/integration/test_lazy_fanout.py backend/tests/integration/test_lazy_generation.py
git commit -m "feat(lazy): 懒生成后补语言阶段,按语言并行补齐该馆其余语言"
```

---

### Task 5: 全量测试、staging 基线、PR 到 staging

**Files:**
- Create(不提交): `<scratchpad>/measure_lazy.py`

- [ ] **Step 1: 全量后端测试**

Run: `cd backend && poetry run pytest -q --no-cov -x > <scratchpad>/full.txt 2>&1; tail -5 <scratchpad>/full.txt`
Expected: 全部 PASS。有失败就读完整 `full.txt`,按 systematic-debugging 查,不截断诊断输出。

- [ ] **Step 2: 写测量脚本**

`<scratchpad>/measure_lazy.py`(在 staging 容器里跑,直接调后台入口,绕开端点额度):

```python
"""staging 懒生成测量:选 N 件有图 stub,用 LANG 触发,打印首屏/全部完成时长、各语言 guide、
翻译调用增量(只数脚本进程的 channel='translate',不混 App 的 translate@app)。
用法:先 docker cp 到容器 /tmp/measure_lazy.py,再
docker exec -w /app -e PYTHONPATH=/app gomuseum_staging_backend python /tmp/measure_lazy.py N LANG"""
import sys
from datetime import datetime, timezone

from sqlalchemy import text

from app.core.database import SessionLocal
from app.models.content import ObjectContentSection as S
from app.models.museum_object import MuseumObject
from app.services.enrichment import lazy
from app.services.must_see import has_image_clause

N, LANG = int(sys.argv[1]), sys.argv[2]
db = SessionLocal()
# generated_at 是无时区 DateTime(存的是 UTC):t0 也用裸 UTC,否则相减抛 TypeError


def calls():
    return db.execute(
        text("select coalesce(sum(calls),0) from llm_usage where day=current_date and channel='translate'")
    ).scalar()


objs = (
    db.query(MuseumObject)
    .filter(MuseumObject.content_status == "stub", has_image_clause())
    .order_by(MuseumObject.popularity.desc(), MuseumObject.id)
    .limit(N)
    .all()
)
c0 = calls()
for o in objs:
    assert lazy.try_acquire_lock(db, o)
    t0 = datetime.now(timezone.utc).replace(tzinfo=None)
    lazy.run_lazy_generation(o.qid, LANG)
    db.expire_all()
    rows = db.query(S).filter(S.object_id == o.id).all()
    first = [r.generated_at for r in rows if r.language == LANG and r.section_code == "guide"]
    pub = [r for r in rows if r.status == "published"]
    print(
        o.qid,
        "ttfc_s", round((min(first) - t0).total_seconds(), 1) if first else None,
        "total_s", round((max(r.generated_at for r in rows) - t0).total_seconds(), 1) if rows else None,
        "guide_langs", sorted({r.language for r in pub if r.section_code == "guide"}),
        "sections_by_lang", {l: sum(1 for r in pub if r.language == l) for l in sorted({r.language for r in pub})},
        flush=True,
    )
print("translate_calls_delta", calls() - c0, "objects", len(objs))
```

- [ ] **Step 3: 改前基线(staging 还是旧代码时跑)**

先 `ssh -i ~/.ssh/deepmeeting_deploy root@38.242.207.219 'cd /opt/gomuseum/staging && git log --oneline -1'`(或查容器镜像)确认 staging 还没有本分支代码,然后:

```bash
scp -i ~/.ssh/deepmeeting_deploy <scratchpad>/measure_lazy.py root@38.242.207.219:/tmp/measure_lazy.py
ssh -i ~/.ssh/deepmeeting_deploy root@38.242.207.219 'docker cp /tmp/measure_lazy.py gomuseum_staging_backend:/tmp/measure_lazy.py && docker exec -w /app -e PYTHONPATH=/app gomuseum_staging_backend python /tmp/measure_lazy.py 3 zh' | tee <scratchpad>/baseline.txt
```

Expected: 3 行,每行 `guide_langs` 只有 `['en','zh']`,记下 `ttfc_s`。

- [ ] **Step 4: 推分支、提 PR 到 staging**

```bash
git push -u origin feature/lazy-gen-all-languages
gh pr create --base staging --title "feat(lazy): 懒生成后补齐该馆全部语言文本" --body "<摘要 + spec/plan 路径 + 测试结果 + 基线数字,结尾带 🤖 Generated with [Claude Code](https://claude.com/claude-code) 和 session 链接>"
```

等 CI 全绿后 `gh pr merge --squash --delete-branch`(feature→staging 可自行合并)。合并后等 staging 自动部署完成(`gh run list --workflow deploy.yml -L 1`)。

---

### Task 6: staging 验收 + prod 只读影响面

- [ ] **Step 1: 改后测量**

```bash
scp -i ~/.ssh/deepmeeting_deploy <scratchpad>/measure_lazy.py root@38.242.207.219:/tmp/measure_lazy.py
ssh -i ~/.ssh/deepmeeting_deploy root@38.242.207.219 'docker cp /tmp/measure_lazy.py gomuseum_staging_backend:/tmp/measure_lazy.py && docker exec -w /app -e PYTHONPATH=/app gomuseum_staging_backend python /tmp/measure_lazy.py 3 zh' | tee <scratchpad>/after.txt
```

Expected:
- `ttfc_s` 和 baseline 同量级,中位数不比基线慢 20% 以上(否则停下来查);
- 每件 `guide_langs` = 该馆配置的全部语言,`total_s` ≤ 约 330 秒;
- 从后端日志 `lazy fanout done` 前后的时间,记下最长的单门语言耗时(心跳 TTL 5 分钟只在单门超过 5 分钟时才会提前过期);
- `translate_calls_delta / objects` 和 spec 4.4 对比:每件约 128 次补语言调用 + 生成阶段原有调用(以 baseline 的每件增量为参照);补语言部分偏差超过 2 倍就停下来查。

- [ ] **Step 2: generating 按语言转换**

再选 1 件 stub,后台跑 `measure_lazy.py 1 zh`;在它补语言期间,每 5 秒用另一门语言(如 de)请求 staging 的 `/content`(或容器里直接调 `get_object_content(db, slug, qid, "de")["generating"]`),记录序列。
Expected:de 在整门翻完前一直 true(即使 de guide 已出现),之后变 false;zh 在补语言期间为 false。

- [ ] **Step 3: 崩溃自愈**

再选 1 件 stub,后台跑 `measure_lazy.py 1 zh`,看到 zh guide 落库后约 30 秒,`ssh ... 'docker exec gomuseum_staging_backend pkill -f measure_lazy.py'`。⚠️ 不要用 `pkill -f "python -"`:uvicorn `--workers 2` 的 worker 命令行是 `python -c ...`,会被一起杀掉。
Expected:
- 5 分钟内 `fanout_pending` 变 `[]`;
- 对还缺段的语言调 `maybe_trigger(db, qid, schedule=..., environment="staging", language=<该语言>, exempt=True)`,能调度 `run_lazy_translation`。

- [ ] **Step 4: 真机看一次**

请用户在 App(staging 包)里打开一件刚触发的 stub,切到非请求语言,确认深度段完整出现、不会一直转圈。这一步需要人看,其它都已自动验证。

- [ ] **Step 5: prod 只读影响面**

新的懒翻译判据会让 prod 上"某门语言半缺"的件在用户请求时补齐。上 prod 前只读统计一次:

```sql
with en as (select object_id, section_code from object_content_sections where language='en' and status='published' and body is not null),
langs as (select distinct object_id, language from object_content_sections where language<>'en')
select l.language, count(distinct l.object_id) objs
from langs l join en e on e.object_id=l.object_id
where not exists (select 1 from object_content_sections s where s.object_id=l.object_id and s.language=l.language and s.section_code=e.section_code)
group by 1 order by 2 desc;
```

Expected:给出每门语言会被新判据重新点火的件数;作废音频为 0(只写缺失段)。把数字连同 staging 验收结果写进 PR 描述 / 报告给用户。

- [ ] **Step 6: 台账**

在新 worktree 里给 `docs/ops/backlog.md` 的"最近关闭"记一条(日期、PR 号、staging 验收数字、prod 待用户合 main),提 docs PR 到 staging。

- [ ] **Step 7: 交给用户**

报告:staging 验收数字(基线 vs 改后)、prod 影响面统计、真机结果。staging→main 由用户决定;提醒合 main 前确认 prod 没有长任务在跑。
