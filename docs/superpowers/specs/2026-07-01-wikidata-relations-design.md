# 配源 round2a:Wikidata 关系属性 — 设计

> **状态**:定稿(2026-07-01)。小改,spec+实现一并。
> **背景**:significance 常空(艺术史影响/遗产,目录源给不了)。Wikidata 关系属性(衍生/影响/基于/系列)是**接地的影响钩子**,零依赖。

## 1. 目标

给 `evidence.py` 的 `fetch_rich_facts` 补 4 个关系属性,喂 significance/background,给它们具体可展开的接地事实。

| 属性 | 含义 | topic | claim |
|---|---|---|---|
| P4969 | has derivative work(衍生作品/被模仿) | significance | 影响了 |
| P144 | based on(基于) | background | 基于 |
| P941 | inspired by(受启发) | background | 受启发于 |
| P361 | part of(所属系列/组画) | background | 所属系列 |

## 2. 机制

- `_RICH_PROPS` 加这 4 条(PID→(claim,topic))。
- `_RICH_QUERY` 的 `VALUES ?prop` 加 `wdt:P4969 wdt:P144 wdt:P941 wdt:P361`。
- 现有解析逻辑不变(取值+en 标签→fact 原子)。多值天然多行;**每属性限 5 条**(防名作衍生作品爆表)——在 `fetch_rich_facts` 组装时按 pid 计数截断。
- 证据包/生成自动用上(build_material 渲染 wikidata 富属性)。

## 3. 诚实预期

关系**主要名作有**;极冷门件一条没有(任何源都填不了)。故主加强**名作 significance**。冷门件事实覆盖等 Europeana(需 key)。

## 4. 非目标

Europeana(待 key)、P737 influenced-by(多在人物实体上,本期不取)、关系的深度叙事(生成侧负责)。

## 5. 契约 / 迁移

无。纯生成材料增强。重生成后名作 significance 有关系钩子。

## 6. 测试

- fake run_query 返 P4969/P144 行 → facts 含"影响了"(significance)、"基于"(background)。
- 每属性 >5 值 → 截到 5。
- 全量回归无破。

## 7. 改动文件

- `backend/app/services/enrichment/evidence.py`(_RICH_PROPS + _RICH_QUERY + 每属性限 5)
- 测试:`test_evidence.py`
- 回写主文档(证据包富属性含关系类)
