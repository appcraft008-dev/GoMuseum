# 懒生成防刷 + 外观段等图再写 设计

日期:2026-10-11 · 分支 `feature/lazy-gen-abuse-and-deferred-analysis` · 状态:待用户确认

## 一、要解决的两件事

1. **防恶意刷懒生成。** 现在只有一道全站日上限(`lazy.py` `_LAZY_DAILY_SECTION_CAP=1000` 段)。
   它是钱包止损,不分是谁:一个脚本就能在一天里把它吃满 → ①多花钱(最坏约 $4–10/天)
   ②多写约 120 件冷门件进库(永久)③当天所有真实用户都显示「明天再来」。
2. **没照片的件不写外观段,照片到了自动补写。** 接地闸对外观描写失明(记忆
   `grounding-gate-visual-description-blindspot`):材料里没有视觉信息时,「色调沉静/背景暗淡」
   这类编出来的句子会被判成 IMPRESSION 放行。照片会陆续补进来(S7、懒补图),所以是「等图」,不是「永远不写」。

## 二、现状(按代码核实,2026-10-11 origin/staging)

| 项 | 现状 | 位置 |
|---|---|---|
| 点火身份闸 | 无令牌/坏令牌不点火;**游客令牌可以点火** | `museums.py:139` `_caller_id` |
| 游客账号 | 同 device_id 复用;换 device_id 就是新账号;创建限流 5 次/小时/IP | `auth.py:189`、`auth_service.py:481` |
| 限流取的 IP | 真实客户端 IP(prod 日志核过:90.160.x / 84.123.x 等,不是统一网关地址) | `core/rate_limit.py` |
| 全站日上限 | 只数 `source=ai_lazy` 的段,1000 | `lazy.py:258` |
| 并发 | 每进程 2 个(×2 worker) | `lazy.py:18` |
| 外观描述 | 生成前有图就看图(gpt-4o high),写进 `attributes.visual_description_en`;没图就没有,照常生成全部段 | `vision.py`、`pipeline.py:160` |
| 外观类段 | painting / works_on_paper 的 `analysis`;sculpture / decorative_arts 的 `material-technique` | `category_config.py:65` |
| 已生成件补段 | **没有这条路**:懒生成只认 stub;懒翻译只在该语言一段都没有时触发 | `lazy.py:maybe_trigger` |
| 补译 | `translate_object_language` 只翻该语言缺的段,可直接复用 | `backfill.py:130` |

**单 IP 攻击账**:5 个游客/小时 × 24 = 每天 120 个新游客账号。所以只加"每账号上限"挡不住单 IP 换号,
还要一道"每 IP 上限"。

## 三、方案 A:防刷(三层)

点火前按顺序检查,任一层满了就不点火,返回 `unavailable_reason="daily_cap"`(已有加法字段,App 已会显示「明天再来」,
**不改契约、不用发包**)。

| 层 | 新/旧 | 默认值 | 挡什么 |
|---|---|---|---|
| ① 每账号每日点火次数 | 新 | 正式账号 40 次、游客 15 次;`can_preview` 运营账号不限 | 单个脚本账号 |
| ② 每 IP 每日点火次数 | 新 | 100 次 | 单 IP 换 device_id 批量开游客号 |
| ③ 全站每日段数 | 旧 | 1000 段 | 多 IP 分布式攻击的最后止损 |

- **计数单位 = 点火次数**(一次懒生成 / 一次懒翻译 / 一次外观段补写 各算 1),不是段数。
  拿到锁真正调度了才计,没拿到锁(别人正在生成)不计。
- **存哪**:Redis `INCR lazy:u:{user_id}:{UTC日期}` / `lazy:ip:{ip}:{UTC日期}`,首次设 2 天过期。
  不建表、不加字段。prod 已有 `gomuseum_prod_redis`。
- **Redis 挂了 → 放行(fail open)+ ERROR 日志。** 理由:③ 全站上限在 DB 里照样兜底;
  反过来 fail closed 会让 Redis 一抖全站懒生成停摆。
- **默认值依据**:10-07/10-08 运营者一个人逛馆一天约 36–38 件触发(301/315 段 ÷ ~8 段/件),
  真实游客一天打开的新冷门件远少于此。运营者账号有 `can_preview` 豁免,不受影响。
  IP 100 次:博物馆共享 WiFi 下,同馆几十人同一天各开几件**还没生成过**的件,到不了 100。
  数值放常量,观察 error/warning 日志后再调。
- **被拦时记 WARNING**(账号、IP、哪一层),为以后看有没有人在刷留证据。

## 四、方案 B:外观段等图再写

### B1. 生成时(新件)
`generate_object` 里,看图那步结束后判断:这件**没有** `visual_description_en`
(无图,或看图失败)→ 本次 `sections` 去掉外观类段(`analysis` / `material-technique`),
并写 `attributes.visual_sections_pending = ["analysis"]`(记具体段名,不同类别不同)。

- 看图失败也走这条(现在是失败照写全部段;改成先不写外观段,等下次补)。
- 批量生成命令走的也是 `generate_object`,同样生效 —— 规则只有一处。
- `--force` 重生成同理:那时有图就写,没图就挂 pending。

### B2. 补写(照片到了)
`maybe_trigger` 加第三种情形:件是 ready、有 `visual_sections_pending`、**现在有本地图**
(`vision.primary_image_url` 非空)→ 上锁、计数(方案 A 三层都检查)、后台跑 `run_lazy_visual_sections`:

1. `ensure_description` 看图;失败 → 清锁、保留 pending,下次再试。
2. 用现有 `enricher.generate_canonical(obj, pending段, guide=已发布的en guide)` 只生成这几段,
   过同一道闸,`persist_gated_sections` 落 en。
3. 触发者的请求语言(非 en)当场用 `translate_object_language` 补译(它只翻缺的段);
   其余语言以后有人用该语言打开时补。
4. 清掉 `visual_sections_pending`(闸挂起了也清 —— 「宁缺」,不反复重试烧钱)。

**写入面**:只**新增**该件的外观段(en + 请求语言)和更新本件 `attributes`。
不改已有段、不碰作者等共享实体、**不作废任何已有音频**(纪律 37:写入面清单为空集之外只有新增行)。

### B3. 懒翻译补漏
现在懒翻译只在「该语言一段都没有」时触发,补写后的新段在其他已有语言里永远不会被翻。
改为:该语言**缺任一已发布 en 段**就触发(仍用 `_has_any_section` 那类防循环判据:
该段该语言已有任何行(含 needs_review)就不再触发,避免过不了闸的段每次打开都重翻)。

## 五、不做 / 不在范围

- **存量**:已生成、没图、已写了外观段的件不回刷(会作废音频;同 152 件证据包的决定)。
- **主讲解(guide)里的外观描写**:guide 也会描述画面,没图时同样可能编。修法是在 guide prompt
  「描写画面」那一拍上加「材料里没有 [VISIBLE IN THE ARTWORK] 时不描写外观」,
  但按以往教训(禁令要长在那一拍上、要 A/B 才知道有没有效)需要单独做 A/B,**另开一项,写进 backlog**。
- 不做 Play Integrity 设备证明(要 Play Console 配置,等有真实滥用证据)。
- 不改全站 1000 段上限。

## 六、测试

- 方案 A:三层各自到线被拦、`can_preview` 豁免、没拿到锁不计数、Redis 抛异常时放行且第 ③ 层仍生效;
  跨 UTC 零点换 key。
- 方案 B(按「跨配置维度测试」:有图/无图两侧都比):
  - 无图生成 → 无外观段、有 pending;有图生成 → 有外观段、无 pending;看图失败 → 同无图。
  - 补写:只新增外观段,其余段 `updated_at`/body 不变、音频 key 不变;请求语言当场补译;pending 清除。
  - 补写时仍无图 → 不触发;看图失败 → pending 保留。
  - 懒翻译补漏:已有其他段的语言缺新段 → 触发;该段已有 needs_review → 不再触发。
- staging 冒烟:挑一件无图 stub 懒生成 → 确认无 analysis;手工给它挂一张图 → 再打开 → 补出 analysis。

## 七、等你定的

1. 默认值:正式 40 / 游客 15 / IP 100 / 运营账号豁免 —— 可以吗?
2. guide 外观描写那条是另开一项(建议),还是并进这次?
