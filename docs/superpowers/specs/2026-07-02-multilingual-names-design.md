# 多语显示名(语言无关)— 设计

> **状态**:定稿(2026-07-02)。规则已入主契约(§内容体系 多语显示名规则)。
> **背景**:切到 fr 时藏品标题显英文(星夜 fr="Starry Night…" 应 "La Nuit étoilée")、冷门件 zh 未译。根因:目录只抓 en+zh 标签、翻译兜底只对重生成件生效。需**语言无关**的规则化解法(加语言=加配置)。

## 1. 规则(契约已定)

显示名(title / artist.name)按请求语言解析,回退链:**① Wikidata 该语言权威标签 → ② 从 en 机器翻译 → ③ en 原名(永不空)**。语言无关:抓全目标语言 labels + 缺则翻译。QID 是匹配键,名字仅显示。

## 2. 存储:per-language 名字字典

- **藏品标题**:`MuseumObject.attributes["title_i18n"] = {lang: title}`(不动现有 `title_en`/`title_zh` 列,兼容;`title_i18n` 是权威真相,列由它回填)。
- **作者名**:`Artist.name_i18n = {lang: name}`(JSON,类似 `bio`;不动 `name_en`/`name_zh` 列)。

## 3. 抓多语标签:fetch_labels

`material.fetch_wikidata_labels(qid, langs, *, run_query=None) -> dict[lang,str]`(注入式):
一次查 Wikidata 实体在 `langs` 的 labels(`rdfs:label` + `FILTER(lang(?l) IN (...))`,或 entity REST `labels`)。返回 `{lang: label}`(只含有的语言)。

## 4. 生成时填充(pipeline)

对 work QID + artist QID,拿到 `DEFAULT_LANGUAGES`(或 target_langs)的目标集:
1. `labels = fetch_wikidata_labels(qid, langs)` → 填 `title_i18n`(权威)。
2. 对目标集里**缺**的语言:`translate_section(en_title, lang)` 兜底填(需 en 原名作源)。
3. 作者名同理填 `Artist.name_i18n`。
4. registry 门控(测试离线)、try/except(不拖垮)。

## 5. 端点解析(museum_repo)

- 加 helper `resolve_name(i18n: dict, language, fallback_en) -> str`:`i18n.get(language) or fallback_en`。
- 端点2/3/4 的 `title`、作者卡 `name` 都经它:
  - title:`resolve_name(attrs.get("title_i18n") or {}, language, o.title_en or o.title_zh or o.qid)`。
  - artist name:`resolve_name(art.name_i18n or {}, language, art.name_en or o.artist_en)`。
- 避开脏格式:不再回退到 `attributes.artist_fr`(Joconde "Lastname First (dates)")。

## 6. 语言集来源

`DEFAULT_LANGUAGES`(现 zh/en/fr;de/es/it 已列但未生成)。**加语言只改这里** → fetch_labels 抓它、缺则翻译。零 per-language 代码。

## 7. 非目标

改 title_en/title_zh 列结构(保留兼容)、per-language period、TTS、Europeana。

## 8. 契约 / 迁移

- `Artist.name_i18n` JSONB 列(迁移,加法)。`title_i18n` 用 attributes(无迁移)。
- 端点 `title`/`name` 值可能变(更准的语言)——形状不变,前向兼容。

## 9. 测试

- `fetch_wikidata_labels`:fake run_query 返多语 labels → dict。
- `resolve_name`:命中语言→该语言;缺→en 兜底。
- pipeline:填 title_i18n / name_i18n(权威 + 翻译兜底);registry 门控离线。
- 端点:fr 有权威标签→显法语;无→翻译;绝不显脏 Joconde 格式。
- 全量回归无破。

## 10. 改动文件

- `backend/app/models/artist.py`(name_i18n 列)+ 迁移
- `backend/app/services/enrichment/material.py`(fetch_wikidata_labels)
- `backend/app/services/enrichment/pipeline.py`(填 title_i18n / name_i18n)
- `backend/app/services/museum_repo.py`(resolve_name;端点 title/name 用之)
- 测试 + 回写主文档(已加规则,补 name_i18n 字段说明)
