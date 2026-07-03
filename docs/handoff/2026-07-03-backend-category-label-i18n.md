# 交接（后端）：馆藏分类 label 按 language 本地化

> 前端已开放 6 语（PR #138–#140）并补齐全部 UI 文案。真机测 de/es/it 时发现：
> **藏品列表顶部的分类标签栏（全部 / Painting / Sculpture / Works on paper）不跟随语言切换**——
> 因为这些 label 由后端返回、且未本地化。前端无法翻译后端返回的自由文本，需后端修。

## 现象

意/德/西语界面下，分类标签栏仍显示中英混杂：

- `全部`（中文，硬编码）
- `Painting` / `Sculpture` / `Works on paper`（英文）

而藏品**标题**已正确本地化（后端按 `language` 返回 `title`），说明本地化通路是通的——只有**分类 label 这一处**漏了。

## 契约现状（问题定位）

**端点**：`GET /api/v1/museums/{slug}?language={lang}`
**返回**：`categories: [{ code, label, count }]`

- 端点**已经收 `language` 参数**（前端 zh/en/fr/de/es/it 都会传）。
- 但返回的 `category.label` **不随 `language` 变**：
  - `code=all` → `label="全部"`（写死中文）
  - `code=painting` / `sculpture` / `works_on_paper` … → `label` 是英文
- 前端把 `code` 与 `label` 分开：`code` 用于筛选（`?category=painting`，稳定不译），`label` 用于显示（应本地化）。

前端模型（只读 `label` 显示）：
```dart
class MuseumCategory { final String code; final String label; final int count; }
// 渲染：Text(cat.label)   // museum_page.dart
```

## 要做（后端）

**让 `category.label` 按请求的 `language` 返回本地化文本。** `code` 保持不变（前端筛选靠它）。

分类是**有限固定集**（painting/sculpture/works_on_paper/… 十来个），不是每件藏品的自由文本——所以只需一张 `code × language → label` 的翻译表，一次配齐 6 语即可，无需 AI 生成。

示例（`language=it`）：
```json
{
  "categories": [
    { "code": "painting",       "label": "Dipinti",            "count": 245 },
    { "code": "sculpture",      "label": "Sculture",           "count": 11 },
    { "code": "works_on_paper", "label": "Opere su carta",     "count": 5 }
  ]
}
```

## 契约约束（遵循项目硬规则）

- **加法/前向兼容**：`label` 字段本就存在，只是改其**取值**为按语言本地化——对老前端无破坏（老前端照显、只是显对应语言）。**不新增/删字段、不改 `code` 语义**。
- **缺翻译回退**：某语言缺某 `code` 的译名 → 回退英文（勿返回 null，前端虽有回退但契约侧也应给 fallback，见记忆 `enrichment-data-frontend-contract`）。
- **`all` 类目可不管**：前端已用 `l10n.all` 覆盖 `code=all` 的 label（PR #139），后端返啥前端都显本地化"全部"。后端把精力放在真实分类上即可。

## 验收

- `GET /api/v1/museums/orsay?language=it` → `categories[].label` 为意大利语；`?language=de` → 德语；等。
- `code` 值不变（前端 `?category=painting` 筛选照常работает）。
- 缺译名回退英文，不返 null。
- 前端零改动即生效（server-driven，免发版）。

## 相关

- 前端改动：PR #138（选择器 6 语）/ #139（UI 文案全量 + 前端覆盖 all tab）/ #140（序号折行）
- 契约主文档：`docs/architecture/museum-api-contract.md`
- 端点/模型：`catalog_remote_datasource.dart` / `museum_detail_model.dart`
