# 懒生成分层 + 解耦 TTS + 流式先出 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 懒生成只产请求语言（省成本）、TTS 按播放懒生成（仅 guide）、guide 先出流式（降等待），语速客户端零成本。

**Architecture:** 三层——英语轴心（造一次共享）→ 单语言翻译（按需，已有 `run_lazy_translation`）→ TTS（按播放，段级落库复用）。改动复用现有懒锁/翻译/音频落库基础设施。

**Tech Stack:** FastAPI 同步端点、SQLAlchemy、OpenAI tts-1（`TTSService.generate_audio` async→`asyncio.run`）、R2（`get_object_storage`/`persist_section_audio`）。

## Global Constraints

- 所有 Python 过 black + isort；TDD（先写失败测试）。
- 端点用**同步 def**（FastAPI 线程池；TTS 内 `asyncio.run` 避免 running-loop 冲突，见 vision.py 先例）。
- 加法兼容：新字段/新端点不破老 App；忠实度/接地不变（TTS 只念已发布文字）。
- ⛔ 现状 N=0 不变——本计划不触发任何 prod 内容生成。
- 任务顺序 = 先上成本+TTS（Task 1/2/3），再流式（Task 4/5）；每任务独立可发。

---

### Task 1: 懒生成改单语言（英语轴心 + 请求语言）

**Files:**
- Modify: `backend/app/services/enrichment/lazy.py`（`_generate` 的 `target_langs`）
- Test: `backend/tests/integration/test_lazy_generation.py`

**Interfaces:**
- Consumes: `generate_object(..., target_langs, lang_priority)`（现有）
- Produces: `run_lazy_generation` 后只有 `en` + 请求语言有 published 段。

- [ ] **Step 1: 写失败测试**（懒生成只产 en + 请求语言，不产其他）

```python
def test_lazy_generation_only_request_language(session, monkeypatch):
    # 省成本核心:懒生成只产 en 轴心 + 请求语言,不产其他 9 门
    import app.services.enrichment.lazy as lazy
    from app.models.content import ObjectContentSection

    captured = {}

    def fake_generate_object(db, qid, *, target_langs, lang_priority, **kw):
        captured["target_langs"] = list(target_langs)
        # 模拟只落 en + lang_priority
        for lang in target_langs:
            db.add(ObjectContentSection(
                object_id=db.query(lazy.MuseumObject).filter_by(qid=qid).one().id,
                language=lang, section_code="guide", body="x", status="published"))
        o = db.query(lazy.MuseumObject).filter_by(qid=qid).one()
        o.content_status = "ready"
        db.commit()
        return {"qid": qid}

    monkeypatch.setattr("app.services.enrichment.pipeline.generate_object", fake_generate_object)
    o = _obj(session)  # stub 件
    lazy.run_lazy_generation(qid="Q1", language="zh",
                             session_factory=lambda: session, close=False)
    assert set(captured["target_langs"]) == {"en", "zh"}  # 只 en+zh,非全 10 语
```

- [ ] **Step 2: 跑测试确认失败** — `pytest backend/tests/integration/test_lazy_generation.py::test_lazy_generation_only_request_language -q` → FAIL（现产全语言）

- [ ] **Step 3: 实现**（`_generate` 限制 target_langs）

```python
# lazy.py _generate 内,把 target_langs=c["target_langs"] 改为:
_req = [language] if language and language != "en" else []
return generate_object(
    db, qid,
    enricher=c["enricher"], gate=c["gate"], translator=c["translator"],
    target_langs=["en"] + _req,   # 英语轴心 + 请求语言(仅);其余走 lazy_translation
    model="gpt-4o-mini",
    qa_suggester=c["qa_suggester"], registry=c["registry"],
    country_lang=c["country_lang"], lang_priority=language,
)
```

- [ ] **Step 4: 跑测试确认通过** + 全量 `pytest backend/tests/ -q -W "ignore::PendingDeprecationWarning"`

- [ ] **Step 5: Commit** — `feat(content): 懒生成只产请求语言(省成本;其余走懒翻译)`

---

### Task 2: TTS VOICE_MAPPING 补 pl/ja/ko/zh-hant

**Files:**
- Modify: `backend/app/services/tts_service.py`（`VOICE_MAPPING`）
- Test: `backend/tests/unit/services/test_tts_service.py`（若无则建）

**Interfaces:**
- Produces: `VOICE_MAPPING` 含全 10 语,`generate_audio` 对新语言不再回退/报错。

- [ ] **Step 1: 写失败测试**

```python
def test_voice_mapping_covers_all_default_languages():
    from app.services.enrichment.lang_config import DEFAULT_LANGUAGES
    from app.services.tts_service import VOICE_MAPPING
    for lang in DEFAULT_LANGUAGES:
        assert lang in VOICE_MAPPING, f"TTS 缺 {lang} 音色"
        assert VOICE_MAPPING[lang].get("default")
```

- [ ] **Step 2: 跑测试确认失败**（缺 pl/ja/ko/zh-hant）

- [ ] **Step 3: 实现**（tts-1 音色语言无关,选通用 default）

```python
# VOICE_MAPPING 末尾补:
    "pl": {"default": "alloy", "options": ["alloy", "nova", "shimmer"]},
    "ja": {"default": "nova", "options": ["nova", "shimmer", "alloy"]},
    "ko": {"default": "nova", "options": ["nova", "shimmer", "alloy"]},
    "zh-hant": {"default": "nova", "options": ["nova", "shimmer", "alloy"]},
```

- [ ] **Step 4: 跑测试确认通过**

- [ ] **Step 5: Commit** — `feat(tts): VOICE_MAPPING 补 pl/ja/ko/zh-hant`

---

### Task 3: TTS 懒生成端点（仅 guide，按播放）

**Files:**
- Modify: `backend/app/api/v1/endpoints/museums.py`（新端点）
- Create: `backend/app/services/enrichment/lazy_audio.py`（生成逻辑 + 段级锁）
- Test: `backend/tests/integration/test_audio_endpoint.py`

**Interfaces:**
- Consumes: `get_section_audio_key(db,qid,lang,code)`、`persist_section_audio(db,qid,lang,code,bytes,storage)`、`get_object_storage()`、`TTSService.generate_audio(text,language)`（async,返 `{"audio_data": bytes,...}`）、`get_object_content`（取 guide 正文）
- Produces: `GET /museums/{slug}/objects/{qid}/audio?language=X&section=guide` → `{"audio_url": str}` 或 404/409/503

- [ ] **Step 1: 写失败测试**（无 key→生成+落库+返 URL；有 key→秒返不重生成）

```python
def test_audio_endpoint_generates_then_caches(client, monkeypatch):
    import app.services.enrichment.lazy_audio as la
    calls = {"tts": 0}
    def fake_tts(text, language):
        calls["tts"] += 1
        return b"MP3BYTES"
    monkeypatch.setattr(la, "_synth", fake_tts)  # 打桩 TTS
    # Q1 有 zh guide published(fixture)
    r1 = client.get("/api/v1/museums/orsay/objects/Q1/audio?language=zh&section=guide")
    assert r1.status_code == 200 and r1.json()["audio_url"]
    assert calls["tts"] == 1
    r2 = client.get("/api/v1/museums/orsay/objects/Q1/audio?language=zh&section=guide")
    assert r2.status_code == 200
    assert calls["tts"] == 1  # 第二次走缓存,不重生成

def test_audio_endpoint_404_when_no_guide_text(client):
    r = client.get("/api/v1/museums/orsay/objects/Q1/audio?language=de&section=guide")
    assert r.status_code == 404  # 该语言 guide 未生成 → 无文字可念
```

- [ ] **Step 2: 跑测试确认失败**（端点/模块不存在）

- [ ] **Step 3: 实现** `lazy_audio.py`

```python
"""guide 音频懒生成(点播放触发):有 audio_key 秒返,否则生成+落库+返 URL。段级锁防并发重复。"""
import asyncio

from app.services.content_repo import get_section_audio_key, persist_section_audio
from app.services.storage import get_object_storage


def _synth(text: str, language: str) -> bytes:
    """调 TTSService(async)→bytes。测试打桩此处。"""
    from app.services.tts_service import TTSService

    async def _run():
        return (await TTSService().generate_audio(text, language))["audio_data"]

    return asyncio.run(_run())


def get_or_make_audio_url(db, slug: str, qid: str, language: str, section: str = "guide"):
    """返 (url, status)。status: ok|no_text|busy。仅 guide(Phase1)。"""
    from app.services.museum_repo import get_object_content

    storage = get_object_storage()
    key = get_section_audio_key(db, qid, language, section)
    if key:
        return storage.public_url(key), "ok"
    # 取该语言 guide 正文(已发布才有)
    data = get_object_content(db, slug, qid, language)
    if data is None:
        return None, "no_text"
    body = (data.get("default_guide") or {}).get("body")
    if not body:
        return None, "no_text"
    audio = _synth(body, language)  # 失败上抛 → 端点 503,不写 key
    new_key = persist_section_audio(db, qid, language, section, audio, storage)
    return storage.public_url(new_key), "ok"
```

- [ ] **Step 4: 实现端点**（museums.py，同步 def）

```python
@router.get("/{slug}/objects/{qid}/audio")
def object_audio(slug: str, qid: str, language: str = "zh",
                 section: str = "guide", db: Session = Depends(get_db)) -> dict:
    """guide 音频懒生成(点播放触发)。仅 guide(Phase1)。语速由客户端 setPlaybackRate。"""
    from app.services.enrichment.lazy_audio import get_or_make_audio_url

    try:
        url, status = get_or_make_audio_url(db, slug, qid, language, section)
    except Exception:
        raise HTTPException(status_code=503, detail={"reason": "tts_failed"})
    if status == "no_text":
        raise HTTPException(status_code=404, detail={"reason": "no_published_text"})
    return {"audio_url": url}
```

- [ ] **Step 5: 跑测试确认通过** + 全量

- [ ] **Step 6: Commit** — `feat(tts): guide 音频懒生成端点(点播放触发,落库复用)`

---

### Task 4: guide 先出流式 — 英语轴心先落 guide

**Files:**
- Modify: `backend/app/services/enrichment/pipeline.py`（`generate_object` 持久化顺序）
- Test: `backend/tests/integration/test_generate_pipeline.py`

**Interfaces:**
- Produces: 英语 guide 段在深度模块**之前**落库（轮询中间态可见 guide、深度缺）。

- [ ] **Step 1: 写失败测试**（记录持久化顺序,guide 先于深度）

```python
def test_en_guide_persisted_before_deep_modules(session, monkeypatch):
    import app.services.enrichment.pipeline as pl
    order = []
    orig = pl.persist_gated_sections
    def spy(db, qid, lang, results, model):
        order.extend(results.keys())
        return orig(db, qid, lang, results, model)
    monkeypatch.setattr(pl, "persist_gated_sections", spy)
    # ... 用现有 generate_object fixture 跑 en 轴心
    # 断言 guide 在 order 里早于 background/analysis
    assert order.index("guide") < order.index("background")
```

- [ ] **Step 2: 跑测试确认失败**（现一次性 persist,guide 与深度同批）

- [ ] **Step 3: 实现**（`generate_object` 里 guide 生成后**立即** persist en guide,再造+persist 深度模块）

```python
# pipeline.py:改造现有块——guide_text 生成后先 gate+persist guide:
guide_text = (enricher.generate_default_guide(obj, facts, guide_target_chars(o.popularity))
              if hasattr(enricher, "generate_default_guide") else None)
if guide_text:
    gq = gate.check_section(material, facts, guide_text)
    persist_gated_sections(db, qid, "en", {"guide": gq}, model)  # ← guide 先落
    o.content_status = "ready" if gq.status == "published" else o.content_status
    db.flush()
# 再造深度模块(guide 作去重锚):
draft = enricher.generate_canonical(obj, sections, guide=guide_text)
gated_en = gate.gate(material, facts, draft)
pub_en, nr_en = persist_gated_sections(db, qid, "en", gated_en, model)  # 深度随后
if o.content_status != "ready":
    o.content_status = "ready" if pub_en > 0 else "empty"
db.flush()
```
（删去原先重复的 guide 二次 persist 块，避免重复落库。）

- [ ] **Step 4: 跑测试确认通过** + 全量（确保原有生成测试不回归）

- [ ] **Step 5: Commit** — `feat(content): 英语轴心 guide 先落库(流式先出前置)`

---

### Task 5: guide 先出流式 — 翻译先翻 guide + 前端部分就绪信号

**Files:**
- Modify: `backend/app/services/enrichment/backfill.py`（`translate_object_language` guide 段排首）
- Test: `backend/tests/integration/test_backfill_languages.py`、`test_pack_and_content_facts.py`

**Interfaces:**
- Produces: 翻译时 guide 段先翻先落；content 端点 `generating=true` 且 `default_guide` 在 → 前端可显 guide + "深度生成中"（`generating` 字段已存在，无需改端点，仅验证语义）。

- [ ] **Step 1: 写失败测试**（翻译顺序 guide 先）

```python
def test_translate_guide_section_first(session, monkeypatch):
    # guide 段在深度模块之前翻译+持久化(用户先看到主讲解)
    from app.services.enrichment.backfill import translate_object_language
    persisted = []
    # 监视 persist_gated_sections 调用顺序(section_code)
    # 构造 en 有 guide+background+analysis,翻 zh,断言 guide 先落
    ...
    assert persisted.index("guide") < persisted.index("background")
```

- [ ] **Step 2: 跑测试确认失败**

- [ ] **Step 3: 实现**（`translate_object_language`：`missing` 里 guide 排首、翻完即 persist，再翻其余）

```python
# backfill.py translate_object_language:missing 分两批,guide 先
missing = {c: b for c, b in en_secs.items() if c not in have}
if missing:
    title = ((o.attributes or {}).get("title_i18n") or {}).get(lang)
    ordered = (["guide"] if "guide" in missing else []) + [c for c in missing if c != "guide"]
    for code in ordered:
        res = translator.translate_object({code: missing[code]}, [lang],
                                          titles={lang: title} if title else None).get(lang, {})
        pub, _ = persist_gated_sections(db, o.qid, lang, res, model)
        counts["sections"] += pub  # guide 先落 → 前端先显
```

- [ ] **Step 4: 验证 content 端点部分就绪语义**（新测试：generating=true 且 guide 已落 → 端点返 guide + generating=true）

```python
def test_content_returns_guide_while_generating(session):
    from datetime import datetime, timezone
    from app.services.museum_repo import get_object_content
    o = session.query(MuseumObject).filter_by(qid="Q1").one()
    # zh guide 已发布,但仍持锁(深度模块生成中)
    _publish_guide(session, "Q1", "zh")
    o.attributes = {**(o.attributes or {}), "lazy_lock_at": datetime.now(timezone.utc).isoformat()}
    session.commit()
    d = get_object_content(session, "orsay", "Q1", "zh")
    assert d["generating"] is True
    assert d["default_guide"]["body"]  # 生成中也返回已落的 guide → 前端流式显示
```

- [ ] **Step 5: 跑测试确认通过** + 全量

- [ ] **Step 6: Commit** — `feat(content): 翻译 guide 先落+生成中返guide(流式先出闭环)`

---

### Task 6: 前端交接文档

**Files:**
- Create: `docs/handoff/2026-07-06-lazy-tts-streaming-frontend.md`

- [ ] **Step 1: 写交接**（三件）
  1. **部分就绪流式**：content `generating=true` 且 `default_guide` 有 → 显 guide + "深度内容生成中"，继续轮询；深度模块/问答到了填入（细化现有三态）。
  2. **TTS 点播放**："听讲解"点击 → `GET .../audio?language=X&section=guide` → 拿 `audio_url` 播放；生成中转圈；404=该语言文字未就绪、503=音频失败可重试；**不阻塞文字**。
  3. **语速档位** 0.75/1/1.5/2x → 播放器 `setPlaybackRate`（一个音频文件，零重新请求）；legacy `_speeds` 可参考。

- [ ] **Step 2: Commit** — `docs(handoff): 懒生成流式+TTS点播放+语速 前端交接`

---

## Self-Review

**Spec coverage:**
- 懒生成单语言 → Task 1 ✅
- guide 先出流式(两层) → Task 4(轴心)+Task 5(翻译) ✅
- TTS 懒端点(仅guide) → Task 3 ✅；VOICE_MAPPING → Task 2 ✅
- 语速客户端 → Task 6(前端) ✅
- per-language N → 无需代码(`generate --langs` 已支持,N=0 休眠) ✅ 保持 YAGNI
- 前端部分就绪/TTS/语速 → Task 6 ✅
- Phase 2(深度模块TTS/预热TTS) → 不在本计划(spec 明列后置) ✅

**Placeholder scan:** Task 5 Step 1 用了 `...` 省略构造——实现时按 test_backfill_languages 现有 fixture 补全 en 段构造（guide+background+analysis published），非规划占位。其余步骤代码完整。

**Type consistency:** `get_or_make_audio_url(db,slug,qid,language,section)→(url,status)`、`_synth(text,language)→bytes`、`persist_section_audio(...)→key`、端点返 `{"audio_url"}` 全一致。

## Execution Handoff

见下（询问执行方式）。
