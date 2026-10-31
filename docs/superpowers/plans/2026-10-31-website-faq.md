# 网站问答页(FAQ)Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 gomuseum.app 上线 `/{lang}/paris/faq/`,10 语同时上线,18 题,带核对日期/有效期/官方来源、时令题自动置顶、按馆题覆盖全部支持的馆。

**Architecture:** 内容 = 仓库里的 YAML:一份 `structure.yaml`(题目 id、分组、顺序、日期、来源、置顶区间、按馆的馆 slug——只写一次,各语言不可能不一致)+ 每语一份 `text/{lang}.yaml`(只放文字,按 id 取)。`app/services/website/faq.py` 负责加载、校验、排序;`site_pages.py` 加一个路由用现有 `render()` 出页;sitemap/hreflang/统计全部复用现有机制。纯加法。

**Tech Stack:** FastAPI + Jinja2(现有网站)、PyYAML(已在依赖)、pytest。

**Spec:** `docs/superpowers/specs/2026-10-31-website-faq-design.md`

## Global Constraints

- 10 语:`wd.LANGS`(en/fr/de/es/it/pl/ja/ko/zh/zh-hant),同时上线;英文为准,其他语言不许增删事实。
- 网址 `/{lang}/{city}/faq/`,一城一页;现只有 paris。
- 每题:完整问句标题 + 锚点(英文 slug,各语共用)+ 第一句直接答案 + 2~4 句细节 + 核对日期 + 适用期 + ≥1 个官方来源(场馆官网/通票官网/巴黎市政府,不用博客/Reddit)。
- 长期规则题 `valid_until` = 核对日 + 90 天;过期后该题自动显示「可能已过期,请以官网为准」。
- 时令题 `pin_from`/`pin_until`:今天在区间内显示在页顶「近期」区,否则回原分组。圣诞元旦题 `pin_from=2026-11-15`、`pin_until=2027-01-02`。
- 分组顺序固定:规划行程 → 门票与通票 → 各馆 → 节假日与突发。
- 按馆题(各馆闭馆日、各馆必看、各馆讲解器)必须覆盖该城市全部馆;缺馆构建失败。
- FAQPage JSON-LD + `dateModified`;进 sitemap + hreflang;首页与馆页加入口链接。
- 统计用现有 `log_page_view`,`page_type="faq"`(下载链接 utm 自动带 faq)。
- 讲解器题写成事实对比,不贬低官方讲解器,不像广告;不写「AI」卖点;不写离线可用;不暗示官方/合作。
- 改后端 → feature → staging PR;staging→main 与 prod 部署只能用户来。

## Review Focus

1. 路由顺序:`/{lang}/{city}/faq/` 必须在 `/{lang}/{city}/{museum_slug}/` 之前注册,否则被当成馆 slug 走 404 → Task 3 测试 `test_faq_page_ok` 覆盖。
2. 某语言 text 文件缺一题或多一题 → 必须构建失败而非页面少一题 → Task 1 `test_text_keys_match_structure`。
3. DB 里已上线的馆在按馆题里没有条目(上新馆漏写)→ 页面照常出其余馆,并 `logger.error`;CI 用 museums.yaml 拦 → Task 1 `test_per_museum_covers_catalog_city`、Task 3 `test_missing_museum_part_still_renders`。
4. 过期/置顶的日期边界(当天算在区间内;`today > valid_until` 才算过期)→ Task 1 `test_arrange_pin_window_inclusive`、`test_stale_after_valid_until`。
5. 答案里的 `<`、`&`、引号要被转义(Jinja autoescape),JSON-LD 里不能破出 `</script>` → Task 3 `test_jsonld_escapes_script_close`。

---

## 文件结构

- Create `backend/app/content/faq/paris/structure.yaml` — 题目骨架(唯一放日期/来源的地方)
- Create `backend/app/content/faq/paris/text/{en,fr,de,es,it,pl,ja,ko,zh,zh-hant}.yaml` — 各语文字
- Create `backend/app/services/website/faq.py` — 加载/校验/排序
- Modify `backend/app/services/website/copy.py` — 页面固定文案 6 个键 × 10 语
- Modify `backend/app/api/web/site_pages.py` — 路由 + sitemap 条目
- Create `backend/app/templates/web/faq.html`;Modify `home.html`、`museum.html` 加入口
- Test `backend/tests/unit/services/test_website_faq.py`、`backend/tests/integration/test_website_faq_page.py`

### Task 1: FAQ 内容模型、加载与校验

**Files:** Create `backend/app/services/website/faq.py`、`backend/tests/unit/services/test_website_faq.py`;测试用最小内容放 `backend/tests/fixtures/faq/demo/`(structure.yaml + text/en.yaml + text/fr.yaml)。

**Interfaces — Produces:**
```python
FAQ_ROOT: Path  # backend/app/content/faq

@dataclass(frozen=True)
class Part:            # 按馆题的一馆,或普通题本身
    museum: str | None
    checked: date
    valid_until: date
    sources: tuple[str, ...]

@dataclass(frozen=True)
class Item:
    id: str; group: str
    parts: tuple[Part, ...]          # 普通题 1 个 Part(museum=None);按馆题每馆 1 个
    pin_from: date | None; pin_until: date | None
    link: str | None                 # 目前只有 "must_see" 或 None

@dataclass(frozen=True)
class Faq:
    city: str
    groups: tuple[str, ...]          # 固定顺序的分组 id
    items: tuple[Item, ...]          # 结构文件里的顺序
    text: dict[str, dict]            # lang -> 解析后的 text yaml

def load_faq(city: str, root: Path = FAQ_ROOT) -> Faq | None   # 无该城市目录 → None;lru_cache
def faq_languages(faq: Faq) -> list[str]                       # 按 wd.LANGS 顺序
def validate(faq: Faq) -> list[str]                            # 错误清单,空 = 合格
def is_stale(part: Part, today: date) -> bool                  # today > valid_until
def arrange(faq: Faq, today: date) -> tuple[list[Item], list[tuple[str, list[Item]]]]
    # (置顶题, [(group_id, 该组未置顶的题)]);空组省略
def museums_for_city(city_en: str) -> list[str]                # museums.yaml 里 city_en 匹配且有 must_see 的 slug
```

structure.yaml 形状:
```yaml
groups: [plan, tickets, museums, holidays]
items:
  - id: closed-days
    group: plan
    per_museum:                      # 有这个键 = 按馆题
      louvre: {checked: 2026-10-31, valid_until: 2027-01-29, sources: [https://www.louvre.fr/...]}
  - id: christmas-new-year-2026
    group: holidays
    checked: 2026-10-31
    valid_until: 2027-01-02
    pin_from: 2026-11-15
    pin_until: 2027-01-02
    sources: [https://...]
```
text/{lang}.yaml 形状:
```yaml
title: ...
intro: ...
groups: {plan: ..., tickets: ..., museums: ..., holidays: ...}
items:
  closed-days: {q: ..., a: {louvre: "...", orsay: "..."}}   # 按馆题 a 是 slug→文字
  christmas-new-year-2026: {q: ..., a: "..."}               # 普通题 a 是字符串;段落用空行分隔
```

`validate` 检查(每条出一句可读错误):en 存在;每种语言的 `groups` 键 == structure.groups、`items` 键 == structure 的 id 集合;按馆题的 `a` 键 == 该题 per_museum 的馆集合,普通题 `a` 是非空字符串;每个 Part 至少 1 个 `https://` 来源、`valid_until >= checked`;`pin_from`/`pin_until` 要么都有要么都无;id 匹配 `^[a-z0-9-]+$` 且唯一;语言只能是 `wd.LANGS` 里的。

- [ ] **Step 1: 写失败测试**(用 fixtures/demo)
```python
def test_demo_loads_and_validates(): faq = load_faq("demo", FIX); assert faq and validate(faq) == []
def test_text_keys_match_structure(tmp_path):  # 复制 demo,删 fr 一题 → validate 含 "fr" 和该 id
def test_per_museum_answer_keys_must_match(tmp_path):  # fr 按馆题少一馆 → 报错含馆 slug
def test_source_required(tmp_path):  # 某 Part sources 空 → 报错
def test_stale_after_valid_until(): p=Part(None,date(2026,10,31),date(2026,12,31),("https://x",))
    assert not is_stale(p, date(2026,12,31)); assert is_stale(p, date(2027,1,1))
def test_arrange_pin_window_inclusive():  # pin 11-15..01-02:11-14 在原组;11-15、01-02 在置顶;01-03 回原组
def test_arrange_keeps_structure_order_and_drops_empty_groups()
def test_unknown_city_returns_none(): assert load_faq("nowhere", FIX) is None
```
- [ ] **Step 2:** `cd backend && pytest tests/unit/services/test_website_faq.py -v` → FAIL(模块不存在)
- [ ] **Step 3:** 实现 `faq.py`(yaml.safe_load;日期 yaml 原生解析为 `date`)。
- [ ] **Step 4:** 同命令 → PASS
- [ ] **Step 5:** commit `feat(website): FAQ 内容模型与校验`

### Task 2: 页面固定文案 10 语

**Files:** Modify `backend/app/services/website/copy.py`(每语加 6 键);现有 `test_website_copy.py` 自动覆盖「每语都有每键、占位符一致」。

键与英文:
- `faq_nav`: "Visiting FAQ"
- `faq_pinned`: "Coming up"
- `faq_checked`: "Checked {date}"
- `faq_valid`: "Applies until {date}"
- `faq_stale`: "This may be out of date — check the official website."
- `faq_sources`: "Sources"

其余 9 语按各语言自然说法写(不直译中文);日期在模板里按 `YYYY-MM-DD` 填,不做本地化日期格式。

- [ ] **Step 1:** 先只加英文 6 键 → `pytest tests/unit/services/test_website_copy.py -v` → FAIL(其他语言缺键)
- [ ] **Step 2:** 补 9 语 → 同命令 PASS
- [ ] **Step 3:** commit `feat(website): FAQ 页面文案十语`

### Task 3: 路由、模板、sitemap、入口链接

**Files:** Modify `backend/app/api/web/site_pages.py`;Create `backend/app/templates/web/faq.html`;Modify `home.html`、`museum.html`;Test `backend/tests/integration/test_website_faq_page.py`(fixture 照 `test_website_pages.py` 建 sqlite + orsay/louvre 两馆,用 monkeypatch 把 `faq.FAQ_ROOT` 指到 fixtures 里一个 `paris` 目录)。

**Interfaces — Consumes:** Task 1 全部;Task 2 文案键;现有 `render()`、`wd.find_city`、`museum_name`、`_t`。

- 路由 `@router.get("/{lang}/{city}/faq/")` **放在 `museum_page` 之前**。lang 不在 `wd.LANGS`、城市不存在、`load_faq` 为 None、lang 不在 `faq_languages` → `_not_found()`。
- 按馆题只渲染 `c.museums`(DB 已上线)里的馆,顺序同 `c.museums`,标题用 `museum_name(m, lang)`;某已上线馆在该题没有 Part → 跳过该馆并 `logger.error("faq missing museum %s/%s", item.id, slug)`。
- 每题 `<h3 id="{item.id}">`;按馆题内每馆 `<h4 id="{item.id}-{slug}">`。
- 每个 Part 下显示 `faq_checked`/`faq_valid` 和来源链接(显示域名,`rel="nofollow noopener"`);`is_stale` 时显示 `faq_stale`。
- `link == "must_see"` → 每馆加链接到该馆页的必看区(用 museum.html 里已有的必看区锚点)。
- 页顶目录:置顶区 + 各组标题(组名来自 text)。
- `render(..., page_type="faq", alternates=faq_languages(faq), path_for=lambda code: f"/{code}/{city}/faq/", title=f"{text.title} · GoMuseum", description=text.intro, jsonld=...)`。
- JSON-LD:`{"@context","@type":"FAQPage","inLanguage":lang,"dateModified":max(所有 Part.checked).isoformat(),"mainEntity":[{"@type":"Question","name":q,"acceptedAnswer":{"@type":"Answer","text":答案纯文本(按馆题拼成「馆名:答案」)}}]}`;确认 base.html 输出 jsonld 时已转义 `</`,没有就在输出处把 `</` 换成 `<\/`。
- sitemap:`_sitemap_entries` 里每个城市在城市页后加 `(f"/{{}}/{c.slug}/faq/", faq_languages(faq))`(faq 存在时)。
- 入口:home.html 每个城市块、museum.html 页面信息区各加一个 `t('faq_nav')` 链接(只在该城市有 FAQ 时出现;由路由传 `faq_href` 或 None)。

- [ ] **Step 1: 写失败测试**
```python
def test_faq_page_ok(client): r=client.get("/en/paris/faq/"); assert r.status_code==200 and 'id="closed-days"' in r.text
def test_faq_404_unknown_lang_or_city(client): 404 for "/xx/paris/faq/" and "/en/rome/faq/"
def test_faq_hreflang_lists_all_text_langs(client)
def test_pinned_section_by_date(client, monkeypatch):  # monkeypatch faq 模块的 today() → 2026-11-20:圣诞题在置顶区之前出现;→ 2027-01-10:不在置顶区
def test_stale_notice(client, monkeypatch):  # today 超过某 Part valid_until → 页面含 faq_stale 英文句
def test_missing_museum_part_still_renders(client, caplog):  # DB 有馆而 structure 缺该馆 → 200,其余馆在,caplog 有 "faq missing museum"
def test_jsonld_is_faqpage(client):  # 解析 <script type="application/ld+json"> → @type FAQPage,mainEntity 数 == 题数
def test_jsonld_escapes_script_close(client):  # fixture 答案含 "</script>" → 页面里 ld+json 块内不出现 "</script>" 原文
def test_sitemap_has_faq(client): assert "/en/paris/faq/" in client.get("/sitemap-en.xml").text
def test_home_links_faq(client): assert "/en/paris/faq/" in client.get("/en/").text
def test_faq_page_view_logged(client, db):  # AppEvent 里 page_type == "faq"
```
为了可测,`faq.py` 加 `def today() -> date`(返回 `date.today()`),路由调它。
- [ ] **Step 2:** `pytest tests/integration/test_website_faq_page.py -v` → FAIL
- [ ] **Step 3:** 实现路由、模板(继承 base.html,沿用现有 band/section 样式,不新增 CSS 文件;需要的少量样式加进 `static/web/site.css`)、sitemap、入口。
- [ ] **Step 4:** 同命令 PASS;再跑 `pytest tests/integration/test_website_*.py tests/unit/services/test_website_*.py -q` 全绿(确认没吞掉馆页路由)
- [ ] **Step 5:** commit `feat(website): FAQ 页面路由、模板、sitemap 与入口`

### Task 4: 英文内容(18 题,逐题核对官网)

**Files:** Create `backend/app/content/faq/paris/structure.yaml`、`text/en.yaml`;Test 在 `test_website_faq.py` 加:
```python
def test_paris_content_valid(): faq=load_faq("paris"); assert faq and validate(faq)==[]
def test_per_museum_covers_catalog_city():  # 每个按馆题的馆集合 ⊇ museums_for_city("Paris")
def test_paris_has_18_items(): assert len(load_faq("paris").items) == 18
```

18 题(spec 第七节,闭馆日/必看按馆合并),分组与 id:
- plan:`closed-days`(按馆)、`louvre-booking`、`louvre-night`、`louvre-time`、`louvre-orsay-one-day`、`orangerie-water-lilies`
- tickets:`museum-pass`、`museum-pass-louvre-entry`、`free-entry`、`first-sunday`、`petit-palais-ticket`
- museums:`must-see`(按馆,link=must_see)、`audio-guides`(按馆)、`photos`、`bags`
- holidays:`christmas-new-year-2026`(pin 2026-11-15..2027-01-02)、`arc-de-triomphe-holidays`(pin 同上)、`strikes-closures`

每题写作规则:第一句直接回答(含数字/日期);再 2~4 句;禁止套话开头;不写没在来源页上看到的事实;来源只用官方站。每题动笔前用 WebFetch 读来源页核对(10-29 的圣诞/凯旋门资料也重查);读不到/页面没写的事实不写,改成「请以官网为准」并给链接。`checked` 填实际核对日;长期规则 `valid_until` = checked + 90 天。

- [ ] **Step 1:** 加上述 3 个测试 → FAIL(无 paris 内容)
- [ ] **Step 2:** 逐题核对官网并写 structure.yaml + en.yaml(只建 en 文本时 validate 应通过——其它语言文件尚不存在)
- [ ] **Step 3:** 测试 PASS;本地起后端看 `/en/paris/faq/` 一眼
- [ ] **Step 4:** commit `feat(website): 巴黎 FAQ 英文内容 18 题`

### Task 5: 9 语翻译

**Files:** Create `text/{fr,de,es,it,pl,ja,ko,zh,zh-hant}.yaml`;Test 加 `def test_paris_all_ten_languages(): assert faq_languages(load_faq("paris")) == list(wd.LANGS)`。

规则:从英文译,不增删事实、数字、日期;馆名用网站现有各语译名(`museum_name`/ museums.yaml);Paris Museum Pass 等专名按当地通行叫法;zh-hant 用台湾用语;不出现「AI」。

- [ ] **Step 1:** 加测试 → FAIL
- [ ] **Step 2:** 写 9 语 → `validate` 为空、测试 PASS
- [ ] **Step 3:** 抽查:每语随机 3 题与英文逐句比对数字/日期一致(脚本:抽出所有数字串比较集合)
- [ ] **Step 4:** commit `feat(website): 巴黎 FAQ 九语翻译`

### Task 6: 收尾

- [ ] `cd backend && black --check app tests && isort --check app tests`(worktree 里钩子不跑,必须手动)
- [ ] 全量 `pytest tests/integration/test_website_*.py tests/unit/services/test_website_*.py -q`
- [ ] PR → staging,CI 绿后合并;在 staging-api.gomuseum.app 打开 10 语页面各看一眼(GET,不用 HEAD)
- [ ] backlog「网站问答页」行改为已合 staging、待用户合 main;记上线后用户要做的:合 main、注册 Bing Webmaster Tools 并提交 sitemap;每月 1 号复盘加「列出 30 天内到期的题并复核」
