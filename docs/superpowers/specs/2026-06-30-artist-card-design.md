# 作者卡(结构化必选)— 设计

> **状态**:设计定稿(2026-06-30 brainstorm)。下一步 writing-plans。
> **主文档**:`docs/architecture/museum-api-contract.md`(端点4 + 内容体系)。完成回写。
> **背景**:用户反馈"深度内容缺作者介绍,应必选,含生卒/国籍/代表作/简短经历"。作者是一等实体,值得一张结构化的"作者卡"。

## 1. 背景与目标

现状:作者信息只是 `tabs` 里的 `artist` 段(一段生成叙事),会被动态隐藏(料薄→空→隐),且**无结构化硬信息**(生卒/国籍/代表作)。

**目标**:`get_object_content` 增一个**必选常驻**的 `artist` 卡片对象:
- **结构化硬事实**(从作者 Wikidata 实体,接地、对知名作者总是有):生卒年(P569/P570)、国籍(P27)、代表作(P800)。
- **简短经历**:复用现有 `artist` 段生成的叙事。
- 因有结构化兜底 → 作者卡**永不为空**(知名作者),不再随动态隐藏。

## 2. 取数:fetch_artist_facts(独立 SPARQL)

`material.fetch_artist_facts(qid, *, run_query=None) -> dict`(注入式,镜像 `fetch_artist_material` 模式):
```sparql
SELECT ?birth ?death ?natLabel ?workLabel WHERE {
  wd:{qid} wdt:P170 ?artist .
  OPTIONAL { ?artist wdt:P569 ?birth. }
  OPTIONAL { ?artist wdt:P570 ?death. }
  OPTIONAL { ?artist wdt:P27 ?nat. }
  OPTIONAL { ?artist wdt:P800 ?work. }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
}
```
解析:birth/death 取年(日期前 4 位)、nationality 取首个 natLabel、notable_works 收集 workLabel 去重限 5。返回:
```python
{"artist_birth": "1832", "artist_death": "1883",
 "artist_nationality": "France", "artist_notable_works": ["Olympia", "The Fifer", ...]}
```
无作者/网络失败 → `{}`(健壮降级)。

> ponytail: nationality/notable_works 用 **en 标签**(canonical,存一次)。zh 视图下暂显 en(如 "France"/"Olympia")——已知 v1 限制;生卒年与作者名(已本地化)不受影响。需要本地化 nationality/works 再做 round2(按语言重取标签)。

## 3. 落库:pipeline

`generate_object` 现有作者材料抓取块(registry 门控,`fetch_artist_material`→artist_extract_*)旁,加一行调 `fetch_artist_facts(o.qid, run_query=...)`,结果并入 `o.attributes`(artist_birth/death/nationality/notable_works)。同样 try/except 不拖垮。registry 门控 → 测试离线。

## 4. 契约:get_object_content 增 artist 卡

`get_object_content` 返回增 `artist` 对象(**必选常驻**):
```json
"artist": {
  "name": "爱德华·马奈",
  "birth": "1832", "death": "1883",
  "nationality": "France",
  "notable_works": ["Olympia", "The Fifer"],
  "bio": "<artist 段已发布叙事(按 language)>"
}
```
- `name`:`_pick(language, artist_zh, artist_en, attrs.artist_fr)`。
- 结构化字段:读 `attrs.artist_birth/death/nationality/notable_works`(缺则 null/[])。
- `bio`:该语种 `section_code='artist'` 已发布正文(缺则 null)。
- **`artist` 段移出 `tabs`**(它成了卡片,不再是深度模块 tab;避免重复)——镜像 `default_guide`/`guide` 的处理(`museum_repo` 读 artist 段单独入卡、不进 tabs)。

## 5. 前端(交接,本 session 只后端)

前端在导览页固定展示作者卡(姓名/生卒/国籍/代表作/经历),常驻不隐。写一段交接给前端 session。

## 6. 非目标(本期)

nationality/notable_works 多语本地化(round2)、作者头像、作者其它作品跳转、artist 段之外的额外作者生成。

## 7. 契约 / 迁移

- `get_object_content` 加 `artist` 对象(加法);`artist` 段从 tabs 移出(数据呈现变化,前端改为读卡)。
- **无迁移**(用 attributes + 现有 artist 段)。前向兼容:老前端不读 `artist` 卡无害;artist 不在 tabs → 老前端少一个 tab(可接受,内容进卡)。

## 8. 测试

- `fetch_artist_facts`:fake run_query 返 birth/death/nat/work 行 → 解析出年份/国籍/代表作(去重限 5);空行→{}。
- `get_object_content`:有 attrs 作者facts + artist 段 → `artist` 卡含 name/birth/death/nationality/notable_works/bio;**artist 不在 tabs**;缺结构化时卡仍返(name+bio)。
- 全量回归无破。

## 9. 改动文件

- `backend/app/services/enrichment/material.py`(`fetch_artist_facts` + 查询)
- `backend/app/services/enrichment/pipeline.py`(generate_object 调 fetch_artist_facts 并入 attributes)
- `backend/app/services/museum_repo.py`(get_object_content 增 artist 卡;artist 段移出 tabs)
- 测试:`test_material.py`(或 `test_artist_material.py`)、`test_pack_and_content_facts.py`
- 完成回写主文档 + 前端交接
