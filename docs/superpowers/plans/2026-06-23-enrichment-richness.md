# 富化提厚（Wikipedia 全文 + Joconde 叙事字段）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把生成材料从「Wikipedia lead 摘要」提厚到「Wikipedia 全文（有界 5000 字符）+ Joconde 叙事字段」，提升接地句子量、降低 43% needs_review。

**Architecture:** 改两个既有富化连接器（WikipediaSource / JocondeSource）取更厚素材，并把新 Joconde 字段接进 `build_material` 白名单。纯加法，不改契约、无迁移、核心管线不变。

**Tech Stack:** FastAPI + pytest，注入式 PoliteSession，离线 mock 可测。

**Design notes（已对真实数据核验，2026-06-23）：**
- **Wikipedia**：现用 REST `/page/summary/` 仅取 lead（实测 L'Origine du monde en≈200 字符）。改用 **Action API `prop=extracts&explaintext=1`** 取全文（实测 en=14,389 / fr=22,669 字符），**在代码里截到 5000 字符**。⚠️ `exchars` 参数在非 exintro 全文模式下不可靠（实测 exchars=5000 只回 ~1200），故**不用 exchars，取全文后 Python 切片**（确定、可测）。
- **Joconde**：spec 原设想的 `description`/`precisions_sur_l_auteur` **经真实记验作废**——`description` 实为材质（"huile sur toile"，与 materiaux_techniques 冗余）；`precisions_sur_l_auteur` 在 `base-joconde-extrait` 子集**不存在**。真正有用的叙事字段是 **`sujet_represente`**（被表现主题，如"couché sur le dos,figure,nu…"）+ **`periode_de_creation`**（创作时期"3e quart 19e siècle"，异于纯年份）。
- **build_material**：`_ATTR_FACT_KEYS` 是白名单（用 key 名作标签）；`extract_*` 已自动全收（Wikipedia 提厚自动生效），但新 Joconde 键须加进白名单才进材料。
- **版权**：全文/主题只作**接地素材**，生成是 grounded 原创改写、只取事实（同 Wikipedia CC-BY-SA 现状），不照搬。

---

## File Structure

- **Modify** `backend/app/services/enrichment/sources/wikipedia.py` — REST summary → Action API 全文 + 5000 截断。
- **Modify** `backend/app/services/enrichment/sources/joconde.py` — 加 `subjects_fr`(sujet_represente) + `period_fr`(periode_de_creation)。
- **Modify** `backend/app/services/enrichment/content_enricher.py` — `_ATTR_FACT_KEYS` 加 `subjects_fr`/`period_fr`。

测试：
- **Modify** `backend/tests/unit/services/enrichment/test_wikipedia_source.py`
- **Modify** `backend/tests/unit/services/enrichment/test_joconde_source.py`
- **Modify** `backend/tests/unit/services/enrichment/test_content_enricher.py`

---

### Task 1: WikipediaSource 取全文（有界 5000）

**Files:**
- Modify: `backend/app/services/enrichment/sources/wikipedia.py`
- Test: `backend/tests/unit/services/enrichment/test_wikipedia_source.py`

- [ ] **Step 1: 改写测试**

把 `test_wikipedia_source.py` 整体替换为（Action API 响应形状 + 截断断言）：

```python
from app.services.enrichment.sources.wikipedia import MAX_EXTRACT_CHARS, WikipediaSource


def _page(extract):
    return {"query": {"pages": {"123": {"extract": extract}}}}


def test_enrich_pulls_full_extracts_for_en_and_country_lang():
    calls = []

    class FakeSession:
        def get_json(self, url, params=None, _transport=None):
            calls.append((url, params))
            lang = "fr" if "fr.wikipedia" in url else "en"
            return _page(f"full-{lang}")

    s = WikipediaSource(session=FakeSession())
    c = s.enrich(
        "Q1",
        {},
        {"wiki_titles": {"en": "Bedroom_in_Arles", "fr": "La_Chambre_à_Arles"}},
    )
    assert c is not None and c.source == "wikipedia"
    assert c.fields["extract_en"] == "full-en"
    assert c.fields["extract_fr"] == "full-fr"
    # 用 Action API：prop=extracts + explaintext，标题经 params 传
    url0, params0 = calls[0]
    assert "/w/api.php" in url0
    assert params0["prop"] == "extracts" and params0["explaintext"] == 1
    assert params0["titles"] in ("Bedroom_in_Arles", "La_Chambre_à_Arles")


def test_enrich_truncates_to_max_chars():
    long = "x" * (MAX_EXTRACT_CHARS + 500)

    class FakeSession:
        def get_json(self, url, params=None, _transport=None):
            return {"query": {"pages": {"1": {"extract": long}}}}

    c = WikipediaSource(session=FakeSession()).enrich(
        "Q1", {}, {"wiki_titles": {"en": "A"}}
    )
    assert len(c.fields["extract_en"]) == MAX_EXTRACT_CHARS


def test_enrich_none_when_no_titles():
    assert WikipediaSource(session=None).enrich("Q1", {}, {}) is None


def test_enrich_skips_lang_without_extract():
    class FakeSession:
        def get_json(self, url, params=None, _transport=None):
            # fr 页缺失（missing page 无 extract）
            if "fr.wikipedia" in url:
                return {"query": {"pages": {"-1": {}}}}
            return {"query": {"pages": {"5": {"extract": "ok"}}}}

    c = WikipediaSource(session=FakeSession()).enrich(
        "Q1", {}, {"wiki_titles": {"en": "A", "fr": "B"}}
    )
    assert c.fields == {"extract_en": "ok"}
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/unit/services/enrichment/test_wikipedia_source.py -q`
Expected: FAIL（`MAX_EXTRACT_CHARS` 未定义 / 响应形状解析不对）

- [ ] **Step 3: 改实现**

把 `wikipedia.py` 整体替换为：

```python
"""WikipediaSource：按对象各语言 Wikipedia 标题拉**全文** plaintext（叙事接地素材，有界）。
多源语言（en + 馆所在国语言）；用注入的 PoliteSession（限速/缓存/UA）。"""

from __future__ import annotations

from app.services.enrichment.sources.base import ObjectContribution, Source

API = "https://{lang}.wikipedia.org/w/api.php"
MAX_EXTRACT_CHARS = 5000  # 全文截断上限：控 grounding prompt 成本/噪声；正文实质内容前置


class WikipediaSource(Source):
    name = "wikipedia"

    def __init__(self, session):
        self._session = session

    def enrich(self, qid: str, external_ids: dict, context: dict):
        titles = (context or {}).get("wiki_titles") or {}
        if not titles:
            return None
        fields = {}
        for lang, title in titles.items():
            data = self._session.get_json(
                API.format(lang=lang),
                params={
                    "action": "query",
                    "format": "json",
                    "prop": "extracts",
                    "explaintext": 1,
                    "exsectionformat": "plain",
                    "redirects": 1,
                    "titles": title,
                },
            )
            pages = ((data or {}).get("query") or {}).get("pages") or {}
            extract = ""
            for pg in pages.values():
                extract = pg.get("extract") or ""
                break
            if extract:
                fields[f"extract_{lang}"] = extract[:MAX_EXTRACT_CHARS]
        if not fields:
            return None
        return ObjectContribution(
            source="wikipedia", qid=qid, fields=fields, raw={"titles": titles}
        )

    def fetch(self, cfg):
        return []
```

- [ ] **Step 4: 运行确认通过**

Run: `cd backend && python -m pytest tests/unit/services/enrichment/test_wikipedia_source.py -q`
Expected: PASS（4 用例）

- [ ] **Step 5: 提交**

```bash
cd backend && git add app/services/enrichment/sources/wikipedia.py tests/unit/services/enrichment/test_wikipedia_source.py
git commit -m "feat(enrichment): Wikipedia 取全文(有界 5000)替代 lead 摘要"
```

---

### Task 2: JocondeSource 加叙事字段

**Files:**
- Modify: `backend/app/services/enrichment/sources/joconde.py`
- Test: `backend/tests/unit/services/enrichment/test_joconde_source.py`

- [ ] **Step 1: 加失败测试**

在 `test_joconde_source.py` 的 `test_enrich_maps_french_fields` 里，给 FakeSession 返回的 `fields` 补 `sujet_represente`/`periode_de_creation`，并加断言。把该用例的 `return {...}` 中 fields 字典扩为：

```python
                        "fields": {
                            "titre": "Etude : torse",
                            "auteur": "RENOIR Pierre Auguste",
                            "materiaux_techniques": "peinture à l'huile;toile",
                            "mesures": "81 H ; 64.8 L",
                            "numero_inventaire": "RF 2740",
                            "sujet_represente": "torse,nu,figure",
                            "periode_de_creation": "4e quart 19e siècle",
                        }
```

并在该用例末尾追加断言：

```python
    assert c.fields["subjects_fr"] == "torse,nu,figure"
    assert c.fields["period_fr"] == "4e quart 19e siècle"
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/unit/services/enrichment/test_joconde_source.py -q`
Expected: FAIL（`subjects_fr`/`period_fr` 不在 c.fields）

- [ ] **Step 3: 改实现**

在 `joconde.py` 的 `enrich` 里，`fields` 字典中 `"bibliography_fr": f.get("exposition")` 那块之后（即字典内）补两行：

```python
        fields = {
            "title_fr": f.get("titre"),
            "artist_fr": f.get("auteur"),
            "medium_fr": f.get("materiaux_techniques"),
            "dimensions": f.get("mesures"),
            "inventory_number": f.get("numero_inventaire"),
            "provenance_fr": f.get("ancienne_appartenance"),
            "exhibitions_fr": f.get("exposition"),
            "bibliography_fr": f.get("bibliographie"),
            "subjects_fr": f.get("sujet_represente"),
            "period_fr": f.get("periode_de_creation"),
        }
```

（即在原 8 字段后加 `subjects_fr`/`period_fr` 两行；其余不动。）

- [ ] **Step 4: 运行确认通过**

Run: `cd backend && python -m pytest tests/unit/services/enrichment/test_joconde_source.py -q`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
cd backend && git add app/services/enrichment/sources/joconde.py tests/unit/services/enrichment/test_joconde_source.py
git commit -m "feat(enrichment): Joconde 加 sujet_represente/periode_de_creation 叙事字段"
```

---

### Task 3: build_material 接入新 Joconde 字段

**Files:**
- Modify: `backend/app/services/enrichment/content_enricher.py`
- Test: `backend/tests/unit/services/enrichment/test_content_enricher.py`

- [ ] **Step 1: 加失败测试**

在 `test_content_enricher.py` 末尾追加：

```python
def test_build_material_includes_new_joconde_fields():
    obj = {
        "qid": "Q1",
        "title_en": "X",
        "category": "painting",
        "attributes": {
            "subjects_fr": "torse,nu,figure",
            "period_fr": "4e quart 19e siècle",
        },
    }
    mat = build_material(obj)
    assert "torse,nu,figure" in mat
    assert "4e quart 19e siècle" in mat
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/unit/services/enrichment/test_content_enricher.py -q`
Expected: FAIL（两值不在 material）

- [ ] **Step 3: 改实现**

在 `content_enricher.py` 的 `_ATTR_FACT_KEYS` 列表末尾加两项：

```python
_ATTR_FACT_KEYS = [
    "medium_fr",
    "dimensions",
    "inventory_number",
    "provenance_fr",
    "exhibitions_fr",
    "bibliography_fr",
    "title_fr",
    "artist_fr",
    "subjects_fr",
    "period_fr",
]
```

- [ ] **Step 4: 运行确认通过**

Run: `cd backend && python -m pytest tests/unit/services/enrichment/test_content_enricher.py -q`
Expected: PASS

- [ ] **Step 5: 全量 enrichment 测试 + 提交**

Run: `cd backend && python -m pytest tests/unit/services/enrichment/ -q`
Expected: PASS（全绿）

```bash
cd backend && git add app/services/enrichment/content_enricher.py tests/unit/services/enrichment/test_content_enricher.py
git commit -m "feat(enrichment): build_material 接入 subjects_fr/period_fr"
```

---

## Self-Review

- **覆盖设计**：Wikipedia 全文+截断（Task 1）✓；Joconde 叙事字段（Task 2，按真实字段名 sujet_represente/periode_de_creation）✓；build_material 接入（Task 3）✓。
- **真实数据校验**：字段名/响应形状/截断行为均已对 prod 真实记录核验（非占位猜测）。
- **前向兼容**：纯加法，无契约/端点/迁移改动；`extract_*` 自动流转；老对象不受影响。
- **类型一致**：`subjects_fr`/`period_fr` 在 Task 2 产出、Task 3 消费，键名一致；`MAX_EXTRACT_CHARS` 在 Task 1 定义并被测试 import。
- **YAGNI**：丢弃 spec 原设想但真实无用的 description/precisions，只加真有信号的 2 个 Joconde 字段。

## 验证富化效果（合 staging 后人工跑，回答「效果 vs 成本」）

提厚是否划算靠实测，不靠估算。合入 staging 后在 staging 容器内：

1. **重生成对照**：`onboard orsay generate --qid Q334138 --target staging --langs en,fr --force`
   （Q334138 提厚前为 en 4 published/1 needs_review）。
2. **看发布率变化**：查 `object_content_sections` 里该件 published vs needs_review 段数，对比提厚前。
3. **抽查内容**：肉眼看 overview/significance 段是否更实、更接地（而非泛泛）。
4. **实测成本**：若要精确成本，临时在 `default_complete` 旁打 token 日志（或用 OpenAI 用量面板看本次 generate 的 token），换算单件成本，校准之前 ~$0.008/件 的估算。
5. 据 2–4 判断：提厚收益（发布率↑、内容质感↑）是否值这 ~2–3× 成本；不值则回调 `MAX_EXTRACT_CHARS`（更小=更省）。

（满意后再决定是否 prod 全量重生成既有 14 件 + 后续 TOP-N。）
