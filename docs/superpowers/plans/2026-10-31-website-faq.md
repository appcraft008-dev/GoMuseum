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
- 每个 Part 有内部 `review_by`(不上页面):长期规则 = 核对日 + 90 天;过了显示「可能已过期,请以官网为准」且不进 JSON-LD。时令题(`kind: dated`)有公开的 `applies_to` 文字,过了 `review_by` 从页面和 JSON-LD 整条隐藏。
- 时间一律 24 小时制(18:00);馆名在文本里写占位符 `{louvre}`,渲染时换成 `museum_name(m, lang)`。
- 时令题 `pin_from`/`pin_until`:今天(巴黎时区)在区间内显示在页顶「近期」区,否则回原分组。圣诞元旦题 `pin_from=2026-11-15`、`pin_until=2027-01-02`。
- 分组顺序固定:规划行程 → 门票与通票 → 各馆 → 节假日与突发。
- 7 道按馆题(闭馆日、必看、讲解器、免费人群、第一个周日、拍照、背包)必须覆盖 museums.yaml 里该城市全部馆;缺馆构建失败。页面只显示该语言有内容的已上线馆(`_museum_vms`)。
- 通票题写明:GoMuseum 巴黎通票只解锁讲解,不含场馆门票;不写 App 价格。免责加「不隶属巴黎博物馆通票机构」。
- FAQPage JSON-LD + `dateModified`;进 sitemap + hreflang;首页与馆页加入口链接。
- 统计用现有 `log_page_view`,`page_type="faq"`(下载链接 utm 自动带 faq)。
- 讲解器题写成事实对比,不贬低官方讲解器,不像广告;不写「AI」卖点;不写离线可用;不暗示官方/合作。
- 改后端 → feature → staging PR;staging→main 与 prod 部署只能用户来。

## Review Focus

1. 路由顺序:`/{lang}/{city}/faq/` 必须在 `/{lang}/{city}/{museum_slug}/` 之前注册 → Task 3 `test_faq_page_ok`。
2. 测试隔离:`load_faq` 有 lru_cache,默认根目录必须在调用时取模块属性 → Task 3 fixture 里 monkeypatch 后 `cache_clear()`,`test_faq_page_ok` 只在 fixture 内容下才通过(Task 3 时真实内容还不存在)。
3. 已上线但该语言无内容的馆不能出现在按馆题里(会链到 404 馆页)→ Task 3 `test_per_museum_skips_museum_without_lang_content`。
4. 过期 Part 进 JSON-LD 会被 AI 原样引用 → Task 3 `test_stale_part_not_in_jsonld`、`test_dated_item_hidden_after_review_by`。
5. 译文数字/时间和英文不一致 → Task 5 `test_numbers_match_english`(全量,不抽查)。

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
    review_by: date                  # 内部复核日,不上页面
    sources: tuple[str, ...]
    evidence: str                    # 来源原文短摘录,不上页面

@dataclass(frozen=True)
class Item:
    id: str; group: str
    kind: str                        # "rule" | "dated"
    parts: tuple[Part, ...]          # 普通题 1 个 Part(museum=None);按馆题每馆 1 个
    pin_from: date | None; pin_until: date | None
    link: str | None                 # "must_see" | "museum" | None

@dataclass(frozen=True)
class Faq:
    city: str                        # 城市 slug
    groups: tuple[str, ...]
    items: tuple[Item, ...]
    text: dict[str, dict]            # lang -> 解析后的 text yaml

def today() -> date                                            # datetime.now(ZoneInfo("Europe/Paris")).date()
def load_faq(city: str, root: Path | None = None) -> Faq | None  # root = root or FAQ_ROOT(调用时取);lru_cache;无目录 → None
def faq_languages(faq: Faq) -> list[str]                       # 按 wd.LANGS 顺序
def validate(faq: Faq) -> list[str]                            # 错误清单,空 = 合格
def is_stale(part: Part, today: date) -> bool                  # today > review_by
def visible(item: Item, today: date) -> bool                   # dated 且所有 Part 都过了 review_by → False
def arrange(faq: Faq, today: date) -> tuple[list[Item], list[tuple[str, list[Item]]]]
    # 只含 visible 的题;(置顶题, [(group_id, 该组未置顶的题)]);空组省略
def museums_for_city(city_slug: str) -> list[str]              # museums.yaml 里 wd.city_slug(cfg.city_en)==city_slug 的全部 slug(不按 must_see 过滤)
def expiring(faq: Faq, today: date, days: int) -> list[tuple[str, str | None, date, tuple[str, ...]]]
    # (题 id, 馆, review_by, sources),review_by <= today+days,按日期排序
# __main__: python -m app.services.website.faq --expiring 30 [--city paris] 打印上面列表
```

structure.yaml 形状:
```yaml
groups: [plan, tickets, museums, holidays]
items:
  - id: closed-days
    group: plan
    per_museum:                      # 有这个键 = 按馆题
      louvre: {checked: 2026-10-31, review_by: 2027-01-29, sources: [https://www.louvre.fr/...], evidence: "..."}
  - id: christmas-new-year
    group: holidays
    kind: dated
    checked: 2026-10-31
    review_by: 2027-01-02
    pin_from: 2026-11-15
    pin_until: 2027-01-02
    sources: [https://...]
    evidence: "..."
```
text/{lang}.yaml 形状:
```yaml
title: ...
intro: ...
groups: {plan: ..., tickets: ..., museums: ..., holidays: ...}
items:
  closed-days: {q: ..., a: {louvre: "...", orsay: "..."}}       # 按馆题 a 是 slug→文字
  christmas-new-year: {q: ..., applies_to: "...", a: "..."}     # dated 题必须有 applies_to(公开)
```
文本里馆名写占位符 `{louvre}`/`{orsay}`…,渲染时替换。

`validate` 检查(每条一句可读错误):en 存在;每种语言 `groups` 键 == structure.groups、`items` 键 == structure 的 id 集合;按馆题 `a` 键 == per_museum 馆集合,普通题 `a` 非空字符串;dated 题有 `applies_to`、rule 题没有;每个 Part ≥1 个 `https://` 来源、`evidence` 非空、`review_by >= checked`;`pin_from`/`pin_until` 成对;id 与按馆锚点用的馆 slug 都转成 `-` 形式后匹配 `^[a-z0-9-]+$` 且唯一;每段文字里的 `{占位符}` 集合与英文同题一致且都是已知馆 slug;语言只能是 `wd.LANGS`。

- [ ] **Step 1: 写失败测试**(用 fixtures/demo,调用都显式传 `root=FIX`)
```python
def test_demo_loads_and_validates(): faq = load_faq("demo", FIX); assert faq and validate(faq) == []
def test_text_keys_match_structure(tmp_path):  # 复制 demo,删 fr 一题 → validate 含 "fr" 和该 id
def test_per_museum_answer_keys_must_match(tmp_path):  # fr 按馆题少一馆 → 报错含馆 slug
def test_source_and_evidence_required(tmp_path):  # sources 空 / evidence 空 → 各报错
def test_placeholder_mismatch(tmp_path):  # fr 少写一个 {louvre} → 报错
def test_stale_after_review_by(): p=Part(None,date(2026,10,31),date(2026,12,31),("https://x",),"e")
    assert not is_stale(p, date(2026,12,31)); assert is_stale(p, date(2027,1,1))
def test_dated_item_invisible_after_review_by()  # dated 题 01-02 可见,01-03 不可见;rule 题过期仍可见
def test_arrange_pin_window_inclusive():  # pin 11-15..01-02:11-14 在原组;11-15、01-02 在置顶;01-03 回原组(rule 题)
def test_arrange_keeps_structure_order_and_drops_empty_groups()
def test_expiring_lists_within_days()  # review_by 在 30 天内的进,之外的不进,按日期排
def test_unknown_city_returns_none(): assert load_faq("nowhere", FIX) is None
```
- [ ] **Step 2:** `cd backend && pytest tests/unit/services/test_website_faq.py -v` → FAIL(模块不存在)
- [ ] **Step 3:** 实现 `faq.py`(yaml.safe_load;日期 yaml 原生解析为 `date`)。
- [ ] **Step 4:** 同命令 → PASS
- [ ] **Step 5:** commit `feat(website): FAQ 内容模型与校验`

### Task 2: 页面固定文案 10 语

**Files:** Modify `backend/app/services/website/copy.py`(每语加 7 键);现有 `test_website_copy.py` 自动覆盖「每语都有每键、占位符一致」。

键与英文:
- `faq_nav`: "Visiting FAQ"
- `faq_pinned`: "Coming up"
- `faq_checked`: "Checked {date}"
- `faq_applies`: "Applies to: {period}"
- `faq_stale`: "This may be out of date — check the official website."
- `faq_sources`: "Sources"
- `faq_disclaimer`: "GoMuseum is independent and not affiliated with any museum or with the Paris Museum Pass."
- `faq_pass_note` 不加:通票与讲解的区分写在通票题答案里。

其余 9 语按各语言自然说法写(不直译中文);日期在模板里按 `YYYY-MM-DD` 填,不做本地化日期格式。

- [ ] **Step 1:** 先只加英文 7 键 → `pytest tests/unit/services/test_website_copy.py -v` → FAIL(其他语言缺键)
- [ ] **Step 2:** 补 9 语 → 同命令 PASS
- [ ] **Step 3:** commit `feat(website): FAQ 页面文案十语`

### Task 3: 路由、模板、sitemap、入口链接

**Files:** Modify `backend/app/api/web/site_pages.py`;Create `backend/app/templates/web/faq.html`;Modify `home.html`、`museum.html`;Test `backend/tests/integration/test_website_faq_page.py`(fixture 照 `test_website_pages.py` 建 sqlite + orsay/louvre 两馆,用 monkeypatch 把 `faq.FAQ_ROOT` 指到 fixtures 里一个 `paris` 目录)。

**Interfaces — Consumes:** Task 1 全部;Task 2 文案键;现有 `render()`、`wd.find_city`、`museum_name`、`_t`。

- 路由 `@router.get("/{lang}/{city}/faq/")` **放在 `museum_page` 之前**。lang 不在 `wd.LANGS`、城市不存在、`load_faq` 为 None、lang 不在 `faq_languages` → `_not_found()`。日期用 `faq.today()`(模块属性调用,便于 monkeypatch)。
- 按馆题只渲染 `_museum_vms(db, c.museums, lang)` 里的馆(已上线且该语言有内容),顺序同它;标题与文本占位符用 `museum_name(m, lang)`。某可见馆在该题没有 Part → 跳过并 `logger.warning`(每进程每题每馆只记一次)。
- `link == "must_see"` → 仅当 `_must_see_cards(db, m, lang)` 非空时链到 `/{lang}/{city}/{slug}/#must-see`,否则链馆页;`link == "museum"` → 链馆页。
- 锚点:题 `<h3 id="{item.id}">`;按馆小节 `<h4 id="{item.id}-{slug 中 _ 换 -}">`(如 `closed-days-petit-palais`)。
- 每个 Part 下显示 `faq_checked`;dated 题显示 `faq_applies`;`is_stale` 显示 `faq_stale`;来源链接显示域名,`rel="nofollow noopener"`。`evidence` 不上页面。
- 页头:标题、intro、`faq_checked`(取可见 Part 的最大 checked)、`faq_disclaimer`;页顶目录 = 置顶区 + 各组标题。
- `render(..., page_type="faq", alternates=faq_languages(faq), path_for=lambda code: f"/{code}/{city}/faq/", title=f"{text.title} · GoMuseum", description=text.intro, jsonld=...)`。
- JSON-LD:FAQPage,`inLanguage`,`dateModified` = 非过期可见 Part 的最大 checked;`mainEntity` 只含可见题、只含**未过期**的 Part(按馆题拼成「馆名:答案」;一题的 Part 全过期则该题不进)。base.html 已用 `|tojson` 输出,不要再手工替换 `</`。
- sitemap:`_sitemap_entries` 每个城市在城市页后加 `(f"/{{}}/{c.slug}/faq/", faq_languages(faq))`;只给这一条输出 `<lastmod>`(= dateModified)。
- 入口:home.html 每个城市块、city.html、museum.html 各加一个 `t('faq_nav')` 链接(只在该城市有 FAQ 时出现,路由传 `faq_href` 或 None)。

- [ ] **Step 1: 写失败测试**
```python
def test_faq_page_ok(client): r=client.get("/en/paris/faq/"); assert r.status_code==200 and 'id="closed-days"' in r.text
def test_faq_404_unknown_lang_or_city(client): 404 for "/xx/paris/faq/" and "/en/rome/faq/"
def test_faq_hreflang_lists_all_text_langs(client)
def test_pinned_section_by_date(client, monkeypatch):  # monkeypatch faq 模块的 today() → 2026-11-20:圣诞题在置顶区之前出现;→ 2027-01-10:不在置顶区
def test_stale_notice(client, monkeypatch):  # today 超过某 Part valid_until → 页面含 faq_stale 英文句
def test_missing_museum_part_still_renders(client, caplog):  # DB 有馆而 structure 缺该馆 → 200,其余馆在,caplog 有 warning
def test_per_museum_skips_museum_without_lang_content(client):  # 该馆只有 en 讲解 → /fr/paris/faq/ 不出该馆小节
def test_must_see_link_only_when_cards(client)  # 无必看卡片的馆不带 #must-see
def test_stale_part_not_in_jsonld(client, monkeypatch)  # today 超过某 Part review_by → 页面有横幅,JSON-LD 不含该答案
def test_dated_item_hidden_after_review_by(client, monkeypatch)  # 2027-01-03 圣诞题页面和 JSON-LD 都没有
def test_jsonld_is_faqpage(client):  # 解析 <script type="application/ld+json"> → @type FAQPage,mainEntity 数 == 可见题数
def test_jsonld_escapes_script_close(client):  # fixture 答案含 "</script>" → 页面里 ld+json 块内不出现 "</script>" 原文
def test_sitemap_has_faq(client): assert "/en/paris/faq/" in client.get("/sitemap-en.xml").text
def test_home_links_faq(client): assert "/en/paris/faq/" in client.get("/en/").text
def test_faq_page_view_logged(client, db):  # AppEvent 里 page_type == "faq"
```
fixture:`monkeypatch.setattr(faq, "FAQ_ROOT", FIX_PARIS); faq.load_faq.cache_clear()`,teardown 再 `cache_clear()`;改日期用 `monkeypatch.setattr(faq, "today", lambda: date(...))`。
- [ ] **Step 2:** `pytest tests/integration/test_website_faq_page.py -v` → FAIL
- [ ] **Step 3:** 实现路由、模板(继承 base.html,沿用现有 band/section 样式,不新增 CSS 文件;需要的少量样式加进 `static/web/site.css`)、sitemap、入口。
- [ ] **Step 4:** 同命令 PASS;再跑 `pytest tests/integration/test_website_*.py tests/unit/services/test_website_*.py -q` 全绿(确认没吞掉馆页路由)
- [ ] **Step 5:** commit `feat(website): FAQ 页面路由、模板、sitemap 与入口`

### Task 4: 英文内容(18 题,逐题核对官网)

**Files:** Create `backend/app/content/faq/paris/structure.yaml`、`text/en.yaml`;Test 在 `test_website_faq.py` 加:
```python
def test_paris_content_valid(): faq=load_faq("paris"); assert faq and validate(faq)==[]
def test_per_museum_covers_catalog_city():  # 每个按馆题的馆集合 ⊇ museums_for_city("paris")
def test_paris_has_18_items(): assert len(load_faq("paris").items) == 18
```

18 题(spec 第七节,闭馆日/必看按馆合并),分组与 id:
- plan:`closed-days`(按馆)、`louvre-booking`、`louvre-night`、`louvre-time`、`louvre-orsay-one-day`、`orangerie-water-lilies`
- tickets:`museum-pass`、`museum-pass-louvre-entry`、`free-entry`(按馆)、`first-sunday`(按馆)、`petit-palais-ticket`
- museums:`must-see`(按馆,link=must_see)、`audio-guides`(按馆,link=museum)、`photos`(按馆)、`bags`(按馆)
- holidays:`christmas-new-year`(dated,applies_to 写 2026-12/2027-01,pin 2026-11-15..2027-01-02,review_by 2027-01-02)、`arc-de-triomphe-holidays`(dated,同上)、`strikes-closures`

`museum-pass` 答案必须含一句:GoMuseum 的巴黎通票只解锁讲解,不含任何场馆门票。`audio-guides` 不写 App 价格。

每题写作规则:每段答案能单独成立(写全馆名、城市、年份,不用「它/这里/今年」);问句用游客真实搜法;第一句直接回答(含数字/日期);再 2~4 句;禁止套话开头;时间 24 小时制;馆名用占位符;不写没在来源页上看到的事实;来源只用官方站(同一官方域名的 PDF/新闻稿可以)。每题动笔前用 WebFetch 读来源页核对(10-29 的圣诞/凯旋门资料也重查),把支撑句的原文短摘录(≤25 词)写进 `evidence`;读不到或页面没写 → 删掉该题/该馆条目,不上空答案,并在 PR 描述里列出删了什么。`checked` 填实际核对日;长期规则 `review_by` = checked + 90 天。

- [ ] **Step 1:** 加上述 3 个测试 → FAIL(无 paris 内容)
- [ ] **Step 2:** 逐题核对官网并写 structure.yaml + en.yaml(只建 en 文本时 validate 应通过——其它语言文件尚不存在)
- [ ] **Step 3:** 测试 PASS;本地起后端看 `/en/paris/faq/` 一眼
- [ ] **Step 4:** commit `feat(website): 巴黎 FAQ 英文内容 18 题`

### Task 5: 9 语翻译

**Files:** Create `text/{fr,de,es,it,pl,ja,ko,zh,zh-hant}.yaml`;Test 加 `def test_paris_all_ten_languages(): assert faq_languages(load_faq("paris")) == list(wd.LANGS)` 和 `def test_numbers_match_english()`:每种语言每段答案抽出的数字串集合(全角数字先归一化)== 英文同段。

规则:从英文译,不增删事实、数字、日期;时间照写 24 小时制;馆名保留占位符;Paris Museum Pass 等专名按当地通行叫法;zh-hant 用台湾用语;不出现「AI」。

- [ ] **Step 1:** 加测试 → FAIL
- [ ] **Step 2:** 写 9 语 → `validate` 为空、测试 PASS
- [ ] **Step 3:** commit `feat(website): 巴黎 FAQ 九语翻译`

### Task 6: 收尾

- [ ] `cd backend && black --check app tests && isort --check app tests`(worktree 里钩子不跑,必须手动)
- [ ] 全量 `pytest tests/integration/test_website_*.py tests/unit/services/test_website_*.py -q`
- [ ] PR → staging,CI 绿后合并;在 staging-api.gomuseum.app 打开 10 语页面各看一眼(GET,不用 HEAD)
- [ ] text/{lang}.yaml 的 `title`/`intro` 含城市名和主要题材关键词(如「Paris museums FAQ: closing days, tickets, Museum Pass」);在网站根目录加 IndexNow 密钥文件(`deployment/website/` 下,随 scp 上线);上线后提交 FAQ 网址前先问用户
- [ ] backlog「网站问答页」行改为已合 staging、待用户合 main;记上线后用户要做的:合 main、注册 Bing Webmaster Tools 并提交 sitemap;每月 1 号复盘加「跑 `python -m app.services.website.faq --expiring 30` 并复核」
