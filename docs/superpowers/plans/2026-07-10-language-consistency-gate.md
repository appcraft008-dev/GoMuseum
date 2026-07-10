# 语言一致性闸 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 所有用户可见的生成/翻译文本在语言 X 下真的是语言 X，零混杂；语言无关派生自 DEFAULT_LANGUAGES，未来加语言自动覆盖。

**Architecture:** 一个离线检测器 `lang_detect.text_in_language(text, lang)`（非拉丁按字形、拉丁用 lingua），接入现有"faithfulness→gpt-4o 重试→needs_review"机制（翻译路径/QA/en轴心/bio），失败重译仍失败则 needs_review 不发布。

**Tech Stack:** lingua-language-detector（离线语言识别）、正则字形检测、现有 translator/QualityGate。

## Global Constraints

- TDD：先写失败测试→看失败→最小实现→全量绿。测试从 `backend/` 跑：`cd backend && pytest tests/ -q -W "ignore::PendingDeprecationWarning"`。
- black + isort 过所有改动文件。
- 语言无关：候选集派生自 `DEFAULT_LANGUAGES`，绝不硬编语言名单（非拉丁集是配置）。
- fail-open：检测器异常/不确定/短文本 → 返 True（放行，防误杀名字短标题）。
- 加法/不破：现有测试全绿；⛔ 不触发 prod 内容生成。
- 阈值起始值：拉丁 lingua 主导语言≠目标 且置信≥0.7 判 False；非拉丁 拉丁字母占字母总数 >40% 判 False；文本 <15 字符或 <3 词 → True。
- commit trailer：`Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>` + `Claude-Session: https://claude.ai/code/session_01Mc1cEJZSHncQ239qYY8afF`；不 push、不建分支。

---

### Task 1: 检测器 `lang_detect.text_in_language`

**Files:**
- Create: `backend/app/services/enrichment/lang_detect.py`
- Test: `backend/tests/unit/services/enrichment/test_lang_detect.py`
- Modify: `backend/pyproject.toml`（加 lingua 依赖）

**Interfaces:**
- Produces: `text_in_language(text: str, lang: str) -> bool`（散文语言校验；短/专名/异常→True）

- [ ] **Step 1: 加依赖** `cd backend && poetry add lingua-language-detector`（生成 poetry.lock；本地 `~/.pyenv/versions/3.11.7/bin/pip install lingua-language-detector` 供测试）

- [ ] **Step 2: 写失败测试**

```python
import pytest
from app.services.enrichment.lang_detect import text_in_language


@pytest.mark.parametrize("text,lang,expected", [
    ("这是一段完整的中文讲解，介绍这幅画的历史与技法。", "zh", True),
    ("This is a complete English paragraph about the painting.", "en", True),
    ("Claude Monet, né en 1840 à Paris, est un peintre français.", "en", False),  # 法语混入 en
    ("约翰·施洗者的 severed head 悬浮在空中，这是一段中文。", "zh", True),  # 少量专名残片,占比低→放行
    ("What did Van Gogh's letters reveal about this piece?", "zh", False),  # 整句英文在 zh→拦
    ("Monet", "en", True),   # 短文本→放行
    ("1855", "zh", True),    # 数字/短→放行
])
def test_text_in_language(text, lang, expected):
    assert text_in_language(text, lang) is expected


def test_language_agnostic_all_default_languages():
    # 语言无关:对 DEFAULT_LANGUAGES 每一门都不崩,正常本语文本判 True
    from app.services.enrichment.lang_config import DEFAULT_LANGUAGES
    samples = {"en": "A long English sentence here about art history and technique.",
               "fr": "Une longue phrase française sur l'histoire de l'art et la technique.",
               "de": "Ein langer deutscher Satz über Kunstgeschichte und Technik hier.",
               "es": "Una larga frase en español sobre la historia del arte y la técnica.",
               "it": "Una lunga frase italiana sulla storia dell'arte e la tecnica qui.",
               "pl": "Długie polskie zdanie o historii sztuki i technice tutaj przedstawione.",
               "zh": "这是一段较长的中文文本，讲述艺术史与绘画技法的内容。",
               "zh-hant": "這是一段較長的中文文本，講述藝術史與繪畫技法的內容。",
               "ja": "これは美術史と絵画技法について述べる、やや長めの日本語の文章です。",
               "ko": "이것은 미술사와 회화 기법에 대해 설명하는 다소 긴 한국어 문장입니다。"}
    for lang in DEFAULT_LANGUAGES:
        assert text_in_language(samples[lang], lang) is True, lang
```

- [ ] **Step 3: 跑测试确认失败** `cd backend && pytest tests/unit/services/enrichment/test_lang_detect.py -q -W "ignore::PendingDeprecationWarning"` → FAIL（模块不存在）

- [ ] **Step 4: 实现**

```python
"""语言一致性检测器:text 是否真的是 lang(散文校验)。离线、确定性。
非拉丁按字形(拉丁残片占比)、拉丁用 lingua。派生自 DEFAULT_LANGUAGES,语言无关。
fail-open:短文本/专名/不确定/异常 → True(放行,宁漏不误杀名字短标题)。"""
import re

# 非拉丁字形语言 → 该字形的 Unicode 判定(加新非拉丁语言加一行)。
_NONLATIN_SCRIPT = {
    "zh": r"[一-鿿]",
    "zh-hant": r"[一-鿿]",
    "ja": r"[一-鿿぀-ヿ]",
    "ko": r"[가-힣]",
}
# 拉丁语言 code → lingua Language(候选集派生自 DEFAULT_LANGUAGES 与此交集)。
_LINGUA_CODE = {
    "en": "ENGLISH", "fr": "FRENCH", "de": "GERMAN",
    "es": "SPANISH", "it": "ITALIAN", "pl": "POLISH",
}
_LATIN = re.compile(r"[a-zA-Z]")
_detector = None


def _get_detector():
    global _detector
    if _detector is None:
        from lingua import Language, LanguageDetectorBuilder
        from app.services.enrichment.lang_config import DEFAULT_LANGUAGES

        langs = [
            getattr(Language, _LINGUA_CODE[c])
            for c in DEFAULT_LANGUAGES
            if c in _LINGUA_CODE
        ]
        _detector = LanguageDetectorBuilder.from_languages(*langs).build()
    return _detector


def text_in_language(text: str, lang: str) -> bool:
    t = (text or "").strip()
    if len(t) < 15 or len(t.split()) < 3:
        return True  # 短文本/名字→放行
    try:
        if lang in _NONLATIN_SCRIPT:
            alpha = re.findall(r"[^\W\d_]", t, re.UNICODE)  # 字母类字符
            if not alpha:
                return True
            latin = sum(1 for c in alpha if _LATIN.match(c))
            return (latin / len(alpha)) <= 0.4  # 拉丁占比>40%=英文污染
        if lang in _LINGUA_CODE:
            from lingua import Language

            det = _get_detector()
            conf = det.compute_language_confidence_values(t)
            if not conf:
                return True
            top = conf[0]
            want = getattr(Language, _LINGUA_CODE[lang])
            return not (top.language != want and top.value >= 0.7)
        return True  # 未知/lingua 外语言→放行(兜底不崩)
    except Exception:
        return True  # fail-open
```

- [ ] **Step 5: 跑测试确认通过 + 全量** `cd backend && pytest tests/ -q -W "ignore::PendingDeprecationWarning"`

- [ ] **Step 6: Commit** `feat(i18n): 语言一致性检测器 lang_detect(非拉丁字形+拉丁lingua,语言无关)`

---

### Task 2: 翻译路径接入（translator）

**Files:**
- Modify: `backend/app/services/enrichment/translator.py`（`translate_object` 重试块）
- Test: `backend/tests/integration/test_generate_pipeline.py`

**Interfaces:**
- Consumes: `text_in_language(text, lang)`（Task 1）
- Produces: 译文语言不符 → gpt-4o 重译；仍不符 → SectionQuality.status="needs_review"

- [ ] **Step 1: 写失败测试**

```python
def test_translate_object_gates_wrong_language(session):
    # 语言闸:译文语言不符→gpt-4o重译;仍不符→needs_review
    from app.services.enrichment.translator import ContentTranslator

    calls = {"mini": 0, "strong": 0}

    def mini(system, user):
        if "quality judge" in system.lower():
            return '{"faithful": true, "issues": []}'
        calls["mini"] += 1
        return "Claude Monet est un peintre français né en 1840 à Paris ville."  # 法语(污染)

    def strong(system, user):
        if "quality judge" in system.lower():
            return '{"faithful": true, "issues": []}'
        calls["strong"] += 1
        return "Claude Monet was a French painter born in Paris in the year 1840."  # 英文(干净)

    tr = ContentTranslator(mini, complete_strong=strong)
    out = tr.translate_object({"guide": "Monet was a French painter."}, ["en"])
    # en 目标:mini 出法语→闸拦→gpt-4o重译出英文→published
    # (用 en 做目标便于 lingua 判定;translate_object 跳过 en,故用 fr 目标验证)
```

（注：`translate_object` 跳过 `en`；测试用非 en 目标。改测试为目标 `fr`，mini 出英文=污染，strong 出法语=干净：）

```python
def test_translate_object_gates_wrong_language(session):
    from app.services.enrichment.translator import ContentTranslator

    calls = {"strong": 0}

    def mini(system, user):
        if "quality judge" in system.lower():
            return '{"faithful": true, "issues": []}'
        return "This is an English sentence that leaked into a French translation."  # 目标fr但出英文

    def strong(system, user):
        if "quality judge" in system.lower():
            return '{"faithful": true, "issues": []}'
        calls["strong"] += 1
        return "Ceci est une phrase française correcte sur le tableau et son histoire."

    tr = ContentTranslator(mini, complete_strong=strong)
    out = tr.translate_object({"guide": "A sentence about the painting here."}, ["fr"])
    assert calls["strong"] == 1  # 语言不符触发了强模型重译
    assert out["fr"]["guide"].status == "published"  # 重译后语言正确
```

- [ ] **Step 2: 跑测试确认失败**（当前只看 faithfulness,不查语言→strong 未触发）

- [ ] **Step 3: 实现**（`translate_object` 重试条件并入语言闸）

```python
# translator.py translate_object 循环内,替换 check_faithfulness 后的判定块:
                translated = self.translate_section(en_body, lang, title=title)
                ok, issues = self.check_faithfulness(en_body, translated, lang)
                lang_ok = _lang_ok(translated, lang)
                if (not ok or not lang_ok) and self._complete_strong:
                    # 不忠实 或 语言不符 → 强模型重译并采用
                    translated = self.translate_section(
                        en_body, lang, strong=True, title=title
                    )
                    ok, issues = self.check_faithfulness(en_body, translated, lang)
                    lang_ok = _lang_ok(translated, lang)
                published = ok and lang_ok  # 忠实且语言正确才发布
                lang_result[code] = SectionQuality(
                    body=translated,
                    status="published" if published else "needs_review",
                    grounding_ratio=1.0 if published else 0.0,
                    conflicts=issues if ok else (issues + ["language_mismatch"]),
                    score=1.0 if published else 0.0,
                )
```

加模块级 helper（translator.py 顶部）：
```python
def _lang_ok(text, lang):
    from app.services.enrichment.lang_detect import text_in_language

    return text_in_language(text, lang)
```

- [ ] **Step 4: 跑测试确认通过 + 全量**

- [ ] **Step 5: Commit** `feat(i18n): 翻译路径接语言闸(语言不符→gpt-4o重译→仍不符needs_review)`

---

### Task 3: 问答路径接入（translate_qa_items）

**Files:**
- Modify: `backend/app/services/enrichment/qa_suggester.py`（`translate_qa_items`）
- Test: `backend/tests/unit/services/enrichment/test_qa_suggester.py`

**Interfaces:**
- Consumes: `text_in_language`（Task 1）
- Produces: 问句或答案语言不符 → 该 QA `status="needs_review"`

- [ ] **Step 1: 写失败测试**

```python
def test_qa_gates_wrong_language():
    from app.services.enrichment.qa_suggester import translate_qa_items

    class _Tr:
        def translate_section(self, text, lang, *, strong=False, title=None):
            return "This whole answer leaked into English instead of Chinese language."

        def check_faithfulness(self, en, tr, lang):
            return True, []

    out = translate_qa_items(
        _Tr(), [{"question": "Why?", "answer": "Because of the light effects here."}], "zh"
    )
    assert out[0]["status"] == "needs_review"  # 答案是英文→语言不符→不发布
```

- [ ] **Step 2: 跑测试确认失败**

- [ ] **Step 3: 实现**（translate_qa_items 内,答案发布前加语言检测）

```python
# qa_suggester.py translate_qa_items:计算 ok 时并入语言闸
        ok, _ = translator.check_faithfulness(it["answer"], ta, lang)
        from app.services.enrichment.lang_detect import text_in_language

        lang_ok = text_in_language(ta, lang) and text_in_language(tq, lang)
        out.append(
            {
                "question": tq,
                "answer": ta,
                "status": "published" if (ok and lang_ok) else "needs_review",
            }
        )
```

- [ ] **Step 4: 跑测试确认通过 + 全量**

- [ ] **Step 5: Commit** `feat(i18n): 问答接语言闸(问/答语言不符→needs_review)`

---

### Task 4: en 轴心接入（QualityGate）

**Files:**
- Modify: `backend/app/services/enrichment/quality.py`（`check_section` 末尾加英文校验）
- Test: `backend/tests/unit/services/enrichment/test_quality.py`（若无则建）

**Interfaces:**
- Consumes: `text_in_language`（Task 1）
- Produces: en 段非英文 → needs_review

- [ ] **Step 1: 写失败测试**

```python
def test_en_axis_rejects_non_english():
    from app.services.enrichment.quality import QualityGate

    def fake(system, user):
        return '{"verdicts": [true]}'  # 接地全过

    gate = QualityGate(fake)
    # body 是法语(en 轴心应英文)→ 即使接地过,语言不符→needs_review
    q = gate.check_section("material", "facts",
                           "Ceci est une phrase française qui a fui dans l'axe anglais.")
    assert q.status == "needs_review"
```

- [ ] **Step 2: 跑测试确认失败**

- [ ] **Step 3: 实现**（check_section 计算出 published body 后,加英文校验）

在 `check_section` return published 结果前插入：
```python
        from app.services.enrichment.lang_detect import text_in_language

        # en 轴心须英文:接地过但语言不是英文(镜像了法语源)→needs_review
        if result_body and not text_in_language(result_body, "en"):
            return SectionQuality(
                body=result_body, status="needs_review", grounding_ratio=0.0
            )
```
（`result_body` 用实现里最终发布 body 的变量名；实现者按 check_section 现有变量对齐。）

- [ ] **Step 4: 跑测试确认通过 + 全量**

- [ ] **Step 5: Commit** `feat(i18n): en 轴心接语言闸(非英文→needs_review)`

---

### Task 5: 作者 bio 改用检测器（删打地鼠）

**Files:**
- Modify: `backend/app/services/enrichment/backfill.py`（`bio_en_usable`）
- Test: `backend/tests/integration/test_backfill_names.py`

**Interfaces:**
- Consumes: `text_in_language`（Task 1）
- Produces: `bio_en_usable` 用检测器判 en bio 是否英文（取代 `_CJK`/`_FRENCH_SIG`）

- [ ] **Step 1: 写失败测试**（补德语等也被拦,证明不再打地鼠）

```python
def test_bio_en_usable_uses_detector_any_language():
    from app.services.enrichment.backfill import bio_en_usable

    assert bio_en_usable({"en": "Monet was a French Impressionist painter and leader."}) is True
    assert bio_en_usable({"en": "Claude Monet, né en 1840, est un peintre français."}) is False  # fr
    assert bio_en_usable(
        {"en": "Claude Monet war ein französischer Maler und Mitbegründer."}
    ) is False  # de(打地鼠时代漏网,现在被检测器拦)
```

- [ ] **Step 2: 跑测试确认失败**（`_FRENCH_SIG` 抓不到德语）

- [ ] **Step 3: 实现**（bio_en_usable 用 text_in_language，删 _FRENCH_SIG）

```python
def bio_en_usable(bio) -> bool:
    """en bio 有且真的是英文→可作轴心/无需重生。契约"完整性判断按语言维度":坏值=缺失。
    用语言一致性检测器(取代原 _CJK/_FRENCH_SIG 打地鼠)。"""
    from app.services.enrichment.lang_detect import text_in_language

    en = (bio or {}).get("en")
    return bool(en) and text_in_language(en, "en")
```
删除 `_FRENCH_SIG` 定义与 `_CJK` 若仅此处用（`_CJK` 别处若还用则保留）。

- [ ] **Step 4: 跑测试确认通过 + 全量**

- [ ] **Step 5: Commit** `fix(i18n): bio_en_usable 改用语言检测器(取代查中/法语打地鼠)`

---

### Task 6: 存量全库重扫脚本（P2）

**Files:**
- Create: `backend/scripts/rescan_language.py`
- Test: `backend/tests/integration/test_rescan_language.py`

**Interfaces:**
- Consumes: `text_in_language`（Task 1）、`translate_object_language`、enricher（bio）
- Produces: `rescan(db, slug) -> dict`（扫全库已发布段+bio，污染的重译/重生成，返回计数）

- [ ] **Step 1: 写失败测试**

```python
def test_rescan_finds_and_fixes_contaminated(session):
    # 构造:zh guide 混英文→重扫应标记并重译
    from app.scripts_rescan import rescan  # 见实现路径
    ...
    r = rescan(session, "orsay", translator=_CleanTr(), enricher=None)
    assert r["contaminated"] >= 1
```

- [ ] **Step 2: 跑测试确认失败**

- [ ] **Step 3: 实现** `rescan_language.py`

```python
"""存量全库重扫:所有语言所有已发布段+bio 过语言检测器,污染的重译/重生成。幂等。"""
import sys
sys.path.insert(0, ".")


def rescan(db, slug, translator, enricher):
    from app.models.museum_object import MuseumObject
    from app.models.content import ObjectContentSection
    from app.services.enrichment.lang_detect import text_in_language
    from app.services.enrichment.backfill import translate_object_language

    m_objs = (
        db.query(MuseumObject)
        .join(ObjectContentSection, ObjectContentSection.object_id == MuseumObject.id)
        .distinct()
        .all()
    )
    contaminated = 0
    fixed = 0
    for o in m_objs:
        bad_langs = set()
        for sec in (
            db.query(ObjectContentSection)
            .filter_by(object_id=o.id, status="published")
            .all()
        ):
            if sec.language != "en" and not text_in_language(sec.body or "", sec.language):
                bad_langs.add(sec.language)
        for lang in bad_langs:
            contaminated += 1
            db.query(ObjectContentSection).filter_by(
                object_id=o.id, language=lang
            ).delete()
            db.commit()
            translate_object_language(db, o, lang, translator)
            db.commit()
            fixed += 1
    return {"contaminated": contaminated, "fixed": fixed}


if __name__ == "__main__":
    import argparse
    from app.core.database import SessionLocal
    from app.services.enrichment.factory import build_generation_components

    ap = argparse.ArgumentParser()
    ap.add_argument("slug")
    ap.add_argument("--target", choices=["staging", "prod"], required=True)
    ns = ap.parse_args()
    db = SessionLocal()
    c = build_generation_components(ns.slug)
    print(rescan(db, ns.slug, c["translator"], c["enricher"]))
```

- [ ] **Step 4: 跑测试确认通过 + 全量**

- [ ] **Step 5: Commit** `feat(i18n): 存量语言一致性重扫脚本(污染段重译,幂等)`

---

### Task 7: 契约原则 + checklist⑦（P3）

**Files:**
- Modify: `docs/architecture/museum-api-contract.md`
- Modify: `docs/i18n-translation-quality-checklist.md`

- [ ] **Step 1: 契约加原则**

在多语显示名/翻译质量原则群加：
> **语言一致性(2026-07-10 定,核心差异点)**:所有用户可见文本(讲解/深度/问答/bio/简介)在语言 X 下必须真的是语言 X,零混杂。经语言一致性闸(`lang_detect`,非拉丁字形+拉丁 lingua)校验,不符→gpt-4o 重译→仍不符 needs_review 不发布。**语言无关**:检测候选集派生自 DEFAULT_LANGUAGES,加语言自动覆盖。取代此前查中/法语的打地鼠补丁。

- [ ] **Step 2: checklist⑦ 纳入**

在 `docs/i18n-translation-quality-checklist.md` 检查点①区补：语言一致性闸对新语言生效（候选集含之）；加语言验收含"整段外语污染"检测。

- [ ] **Step 3: Commit** `docs(api): 定语言一致性原则+checklist纳入(核心差异点)`

---

## Self-Review

**Spec coverage:**
- 检测器（非拉丁字形+拉丁 lingua+派生 DEFAULT_LANGUAGES+fail-open）→ Task 1 ✅
- 翻译路径接入 → Task 2 ✅；问答 → Task 3 ✅；en 轴心 → Task 4 ✅；bio 删打地鼠 → Task 5 ✅
- 存量重扫 → Task 6 ✅；契约+checklist → Task 7 ✅
- 前端无需改动（needs_review 已过滤）→ spec P3 已注，无任务 ✅
- 依赖 lingua → Task 1 Step 1 ✅

**Placeholder scan:** Task 4 `result_body` 变量名待实现者对齐 check_section 现有变量（已注明，非占位）；Task 6 测试 `_CleanTr`/构造由实现者按现有 fake 补全（已注明）。其余步骤代码完整。

**Type consistency:** `text_in_language(text, lang)->bool` 全任务一致；`SectionQuality(body,status,grounding_ratio,conflicts,score)` 与现有一致；`translate_object_language(db,o,lang,translator)` 与现有一致。

## Execution Handoff

见下（询问执行方式）。
