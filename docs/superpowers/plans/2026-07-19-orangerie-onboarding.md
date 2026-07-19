# 橘园上馆 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 纯配置上第二家馆(橘园 ~150 件)——"零代码上新馆"契约主张的第一次实证裁决。

**Architecture:** 唯一代码改动 = museums.yaml 一个条目;其余为契约配方运维序列(staging 小样本→发布→prod 全链→验收+回写)。若中途被迫改核心代码 → 记为配方缺口修复(#286 模式)。

**Tech Stack:** museums.yaml / onboard CLI / VPS docker exec。

## Global Constraints

- spec: `docs/superpowers/specs/2026-07-19-orangerie-onboarding-design.md`
- 橘园 QID=**Q726781**;Joconde 官方名精确=**"musée de l'Orangerie des Tuileries"**
- names 保持 gpt-4o(用户确认不降档;#201 教训);Batch/换模型留成本工程②③
- 长命令 detached+日志(纪律⑥,跑前确认无部署在途);staging 护栏自动生效
- **配置必须先发到 prod 容器**(museums.yaml 随 CD 部署)才能跑 prod 配方 → 依赖 staging→main 发布(用户点)

---

### Task 1: museums.yaml 橘园条目 + 配置测试

**Files:**
- Modify: `backend/museums.yaml`(orsay 条目之后追加)
- Test: `backend/tests/unit/services/enrichment/test_catalog.py`(追加)

- [ ] **Step 1: 失败测试**(追加到 test_catalog.py)

```python
def test_orangerie_config_loads():
    # 第二家馆(spec 2026-07-19):纯配置上馆的唯一"代码"
    cat = MuseumCatalog.from_file("museums.yaml")
    cfg = cat.get("orangerie")
    assert cfg.wikidata_qid == "Q726781"
    assert cfg.joconde_museum == "musée de l'Orangerie des Tuileries"
    assert cfg.country_lang == "fr" and "joconde" in cfg.sources
```

- [ ] **Step 2: 跑确认失败** `cd backend && python -m pytest tests/unit/services/enrichment/test_catalog.py -q --no-cov -p no:cacheprovider`(KeyError/None)

- [ ] **Step 3: museums.yaml 追加**(orsay 条目同缩进层级)

```yaml
  orangerie:
    name_zh: 橘园美术馆
    name_en: Musée de l'Orangerie
    city_zh: 巴黎
    city_en: Paris
    country: FR
    wikidata_qid: Q726781
    category_filter: Q3305213
    categories: [Q3305213, Q219423,
                 Q860861, Q179700, Q241045, Q1066288,
                 Q93184, Q18761202, Q12043905, Q15123870, Q2647254, Q5078274,
                 Q125191]
    country_lang: fr
    sources: [joconde, wikipedia]
    joconde_museum: "musée de l'Orangerie des Tuileries"
    fetch_limit: 500
    sample_size: 10
    sample_qids: []
```

- [ ] **Step 4: 跑通过** + **Step 5: Commit + PR→staging 合并**

```bash
git add backend/museums.yaml backend/tests/unit/services/enrichment/test_catalog.py
git commit -m "feat(museum): 橘园美术馆配置(第二家馆,纯配置上馆)"
git push -u origin feature/orangerie
gh pr create --base staging --head feature/orangerie --title "feat(museum): 橘园配置(第二家馆,零代码上馆实证)" --body "spec: docs/superpowers/specs/2026-07-19-orangerie-onboarding-design.md"
# CI 绿 → squash 合并 --delete-branch → 等 staging 部署 success
```

### Task 2: staging 小样本验证(分钱级)

**Files:** 无(运维;staging 容器内)

- [ ] **Step 1: 目录小样本**(两源)

```bash
docker exec -w /app gomuseum_staging_backend python scripts/onboard.py orangerie catalog --target staging --limit 30
# 预期: loaded ~19(wikidata 就 19 件)
docker exec -w /app gomuseum_staging_backend python scripts/onboard.py orangerie catalog --target staging --source joconde
# 预期: "Joconde 列 133 件,去重后新增 ~130+"
```

- [ ] **Step 2: names(护栏自动 limit=50)+ intro**

```bash
docker exec -w /app gomuseum_staging_backend python scripts/onboard.py orangerie names --target staging
# 预期: 护栏提示 limit→50;titles ~50
docker exec -w /app gomuseum_staging_backend python scripts/onboard.py orangerie intro --target staging
# 预期: generated=True translated=9语 cover=<某key或None(staging未物化图则None,正常)>
```

- [ ] **Step 3: API 验证**

```bash
curl -s "http://localhost:8101/api/v1/museums" | python3 -c "import sys,json; print([m['slug'] for m in json.load(sys.stdin)['museums']])"
# 预期: ['orsay','orangerie'] —— 探索页自动出现
curl -s "http://localhost:8101/api/v1/museums/orangerie?language=zh" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['name_zh'], d['archive_count'], (d['description'] or '')[:40])"
# 预期: 橘园美术馆 ~150 中文介绍非空
```

(⚠️ /museums 返回形状若非 {'museums':[...]} 按实际调整解析——运维步骤,现场看响应。)

### Task 3: 发布(用户点)

- [ ] staging→main 发布 PR(可与攒着的 #294/#295 成本记账同批)→ **用户合并** → prod 部署 success(museums.yaml 到位)

### Task 4: prod 配方全链

**Files:** 无(运维;prod 容器内,跑前确认无部署在途)

- [ ] **Step 1: 目录**

```bash
docker exec -w /app gomuseum_prod_backend python scripts/onboard.py orangerie catalog --target prod
docker exec -w /app gomuseum_prod_backend python scripts/onboard.py orangerie catalog --target prod --source joconde
# 预期合计 ~150 件;errors 若>0 看日志判性质(重复条目跳过=正常)
```

- [ ] **Step 2: names(全量 ~150×10语,分钟级)**

```bash
docker exec -d gomuseum_prod_backend sh -c "cd /app && setsid python scripts/onboard.py orangerie names --target prod > /tmp/orangerie_names.log 2>&1"
# 完成判据: log 出现 "✓ names 回填完成";预期 titles ~150 artists ~30-50
```

- [ ] **Step 3: 图+向量+介绍**

```bash
docker exec -w /app gomuseum_prod_backend python scripts/onboard.py orangerie images --target prod
# 预期 done ~16
docker exec -w /app gomuseum_prod_backend sh -c "PYTHONPATH=/app python scripts/backfill_embeddings.py"
docker exec -w /app gomuseum_prod_backend python scripts/onboard.py orangerie intro --target prod
# 预期 generated=True + cover=16张里得体性筛选出一张(睡莲类,无裸体争议,应首件即中)
```

- [ ] **Step 4: 收官报告**

```bash
docker exec -w /app gomuseum_prod_backend python scripts/onboard.py orangerie coverage-report --museum orangerie 2>/dev/null || docker exec -w /app gomuseum_prod_backend python scripts/onboard.py coverage-report --museum orangerie
# (coverage-report 用 --museum,slug 位可省;按实际 CLI 形态跑)
docker exec -w /app gomuseum_prod_backend python scripts/llm_cost_report.py --days 1
```

### Task 5: 验收(零代码裁决)+ 回写

- [ ] **Step 1: 验收四条**(对照 spec §4):探索页两馆;馆包介绍+封面;搜索命中橘园件+懒讲解生成一件;双数字 ~16/~150
- [ ] **Step 2: 裁决**:未改核心代码 → 契约变更记录写"零代码上新馆实证成立 + 本次上馆成本基准(llm_cost_report 数字)";改了 → 各缺口按 #286 模式成文
- [ ] **Step 3: 契约变更记录 + memory 更新(product-backlog/staging-pending)** → docs PR → staging 合并

---

## Self-Review

1. **Spec coverage**:§1→T1;§2→T2;§3→T4;§4→T5;发布依赖→T3 ✓
2. **Placeholder**:命令全给出+预期输出;两处"按实际调整"是运维现场判断非代码占位 ✓
3. **一致性**:QID/Joconde 名与 spec 一致;fetch_limit 500 一致 ✓
