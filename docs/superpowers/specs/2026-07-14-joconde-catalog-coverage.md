# 覆盖率补缺:JocondeCatalog 收纸上作品(Wikidata 偏科)

> 2026-07-14。实证:用户在 prod 连拍 4 件(Fortuny 素描/美杜莎浮雕/Lévy-Dhurmer 粉彩/
> Cassatt 粉彩)全"不在库"。根因是 Wikidata 对奥赛覆盖偏科。与 [[collection-coverage-strategy]] 配套。

## 根因(已验证)

- 目录脊柱 = Wikidata SPARQL(`P195=奥赛 ∧ P31∈类目`),**类目已含纸上作品**(Q93184 素描等)。
- 但 **Wikidata 对奥赛覆盖偏科**:prod 收 painting 4437 / sculpture 210 / **works_on_paper 仅 167** / photography 15。
- 奥赛以纸上作品著称(Degas/Cassatt/Redon 粉彩上千),Wikidata 大多没标 `P195=奥赛` → 收不进。
- **Joconde 开放数据(data.culture.gouv.fr)有奥赛 4111 条,含 dessin 434 / estampe 24**;
  抽验 Cassatt《Mère et enfant sur fond vert》(ref 50350115122)在 Joconde、不在我们库。

## 方案(已实现)

**`JocondeCatalog(CatalogSource)`**(`sources/joconde_catalog.py`):Opendatasoft API 按 `nom_officiel_musee`
翻页列全馆作品 → `StubRecord`。字段映射:`numero_inventaire`→馆藏号(取首号,切 `,`/`;` 后缀)、
`titre`→标题(去" OU 别名",全大写→句首大写,存 en 列待 names 机翻补多语)、`auteur`→作者(去生卒)、
`domaine`→类目(dessin/estampe/aquarelle/pastel→works_on_paper,peinture→painting,sculpture→sculpture,
photographie→photography)、`reference`→`external_ids.P347`、`image_url=None`(© RMN 无免费图)。

**去重不覆盖既有**(`catalog_loader.filter_new_stubs`):按**归一化馆藏号 + P347** 跳过库里已有件
(多为 Wikidata 收的绘画),**只补真正缺的纸上作品**;绝不改既有 Wikidata 件的好数据。

**入口**:`onboard.py catalog --source joconde`(默认 wikidata 不变)。配置 `museums.yaml` 加
`joconde_museum: "musée d'Orsay"`,配了才跑。

## 结果与边界

- 新件进来是**文字层 stub**(© RMN 无免费图 → **可搜/可浏览,相机认不了**)。**关掉"根本不在库"**:
  Le Silence / Cassatt / Fortuny 变**搜得到**。相机识别版权纸上作品需授权图(许可问题,不在此)。
- 显示名:Joconde 只有法文题、无 qid → `names` 回填走**机翻**(从 en 列法文题译多语,同无 qid 冷门件路径)。
- 作者无 qid → 不建 Artist 实体、无多语作者名(stub 可接受;后续可按名字匹配既有 Artist 补)。

## 测试
- `tests/unit/services/enrichment/test_joconde_catalog.py`(6):字段映射/翻页/无馆名空/无号跳过/
  清洗函数/`filter_new_stubs` 去重。真实 API 冒烟通过(前 6 件正确映射)。

## 落地步骤(运维)
1. **staging 先跑**:`onboard.py orsay catalog --source joconde --target staging` → 验证新增件数/类目/去重。
2. staging 上 `names`(补多语显示名,机翻)→ 前端搜索验证纸上作品可搜。
3. **prod 跑**(⛔用户点):`catalog --source joconde --target prod` → `names` → `coverage-report`。
   预计新增数千 stub(类似 names 那种数分钟级运维事件;Joconde API 限速 0.2s/页,~41 页)。

## 契约回写(实现后)
`collection-coverage-strategy`:多源目录(Wikidata 脊柱 + Joconde 补纸上)、文字层扩展、去重原则。
