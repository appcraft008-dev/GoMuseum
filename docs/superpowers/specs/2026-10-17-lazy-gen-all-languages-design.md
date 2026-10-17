# 懒生成一次出齐全部语言文本 · 设计

日期:2026-10-17 · 状态:待用户审 · 范围:纯后端(契约形状不变)

## 一、要解决什么

现状:用户点开一件 stub,懒生成只出 **英语轴心 + 请求语言**(`lazy._generate` 里
`target_langs=["en"] + _req`)。别的语言的用户第一次点开同一件时,要再等一次懒翻译
(`run_lazy_translation`),而且是在**作品页上看着转圈等**。

目标:第一个用户触发生成后,后台把**该馆配置的全部语言**的文本(讲解段 + 深度段 + 问答)
都补齐。之后任何语言的用户点开都直接可读,不再等翻译。

不变的东西:

- 第一个用户自己的体验:首屏(请求语言 guide)和自己语言的深度段/问答,**时延不得变差**。
- 契约:`/content` 响应字段不增不删。`generating` 的含义变成"**对你请求的这门语言**还在生成",
  老 App 照常工作(见第五节)。
- 音频不在本 spec 里:音频照旧按段点播懒生成(Google Chirp 3 HD),落库后定期由 Mac 上的
  VoxCPM2 批量替换(记忆 `audio-voice-strategy-1017`)。

## 二、语言集不写死

**不新增任何语言列表。** 要补的语言 = 该馆配置的语言集 − 这件已有内容的语言:

```
remaining = resolve_languages(museum.languages)   # factory 已算好:c["target_langs"]
            − {"en", 请求语言}
            − 该件已有任一段落的语言              # 幂等,跑两次不重复花钱
```

`resolve_languages` 读 `museums.yaml` 的馆级覆盖,没有就用 `lang_config.DEFAULT_LANGUAGES`
(现为 10 门)。以后加一门语言,照契约里的"加语言 checklist"把它加进 `DEFAULT_LANGUAGES` /
`LANG_NAMES` 等处即可,本特性零改动:

- 加语言之后**新**触发的懒生成,自动带上新语言;
- 加语言之前就已 ready 的件,由已有的懒翻译(用户请求时)兜底,或者运营者跑一次
  `onboard translate`(`backfill_languages`)批量补。

代码里不出现 `10`、语言个数或任何语言代码常量。测试用 3 门、4 门这样的非 10 语言集来验证。

## 三、方案比较

| | 做法 | 主要问题 |
|---|---|---|
| A | `_generate` 直接传全部语言,在 `generate_object` 里按语言并行翻译 | 要动首屏关键路径。作者块(`_enrich_artist_and_titles`)对每门语言串行翻 bio/名字,新作者要多 20–30 秒才轮到请求者的深度段;占着 `_SEM` 的时间变长,别的新件更容易撞满被丢 |
| **B(推荐)** | `generate_object` 原样不动(仍是 en + 请求语言);生成结束后释放 `_SEM`,再在后台**按语言并行**调已有的 `translate_object_language` 补齐其余语言 | 要给"补语言"阶段单独做一个锁标记(见第四节) |
| C | 维持现状,靠用户请求时触发懒翻译 | 就是现在要解决的问题 |

推荐 B 的理由:

1. 首屏和请求者自己的语言走的代码**一行不改**,时延不会变差。
2. `translate_object_language` 是懒翻译和 `onboard translate` 共用的函数,prod 已用它补齐了
   1027 件 ready 作品的 10 门语言。它只翻缺失段,幂等,对共享实体只补缺。
3. 标题和作者名的多语言在铺目录时已经由 `backfill_display_names` 填好
   (prod 实测:stub 平均 9.99 门 `title_i18n`),所以 B 不需要在补语言阶段重做作者块。

## 四、设计(方案 B)

### 4.1 流程

```
用户点开 stub
 └ maybe_trigger:上 lazy_lock_at、扣额度(不变)
    └ run_lazy_generation(后台)
       ├ 持有 _SEM(2):generate_object(en + 请求语言)       ← 不变
       │   首屏 guide → en 深度段 → 请求语言深度段 → 问答
       ├ 打 ai_lazy 标签、清 lazy_lock_at、释放 _SEM          ← 不变
       └ 新增:补语言阶段
           ├ 拿不到 _FANOUT_SEM(非阻塞)→ 直接结束,其余语言留给懒翻译兜底
           ├ 写 lazy_fanout_at 标记
           ├ 线程池按语言并行:translate_object_language(include_bio=False)
           │   每个线程自带 session(同 backfill_languages)
           ├ 主线程串行:补这些语言的作者 bio(只补缺)
           ├ 把本阶段写的段打 ai_lazy_fanout 标签
           └ 清 lazy_fanout_at
```

只在 `run_lazy_generation` 结束后接补语言阶段。`run_lazy_translation` 不接:prod 里 ready
的件绝大多数已有全部语言,没有必要。

### 4.2 并发与锁

- `_FANOUT_SEM = threading.Semaphore(2)`,非阻塞获取。满了就跳过、不排队。代价是这件的
  其余语言回到现状(按请求懒翻译),没有坏结果。
- 每件按语言开 `ThreadPoolExecutor(max_workers=4)`。最坏同时 2 件 × 4 线程 = 8 路
  gpt-4o-mini 调用,远低于账户的限速。
- 每个线程用 `guarded_sessionmaker(bind=...)` 建自己的 session,同 `backfill_languages`。
  线程之间写的行不重叠(段和问答都按 `(object_id, language)` 分开)。
- **作者 bio 是共享行(纪律 37),不能多线程写。** 多个线程同时 `art.bio = {**bio, lang: x}`
  会互相覆盖,丢掉别的语言。所以线程里跳过 bio,等全部线程结束后由主线程一次补齐。
  这需要给 `translate_object_language` 加一个关键字参数 `include_bio=True`(默认值保持
  现有行为不变)。
- `lazy_fanout_at` 存在 `attributes` 里,TTL 与 `_LOCK_TTL` 一样是 10 分钟:进程崩溃后超时
  自动失效。写和清都在主线程。

### 4.3 `generating` 与重复触发

补语言阶段**不持有** `lazy_lock_at`。否则请求者自己的语言早就齐了,`generating` 还是
`true`,前端会继续每 4 秒轮询、一直转"深度内容生成中"。新规则:

| 场景 | `generating` | `maybe_trigger` |
|---|---|---|
| `lazy_lock_at` 有效 | true(不变) | 不点火(不变) |
| 补语言进行中,且请求语言**还没有**已发布 guide | true:前端继续轮询,等这门语言出来 | **不点火**:防止和补语言阶段重复翻译 |
| 补语言进行中,且请求语言已有已发布 guide | false | 不点火(该语言已有段,本来就不会触发) |
| 都没有 | false(不变) | 不变 |

已知的小代价:补语言进行中打开某门语言的用户,在这门语言 guide 落库后 `generating` 就变成
false,这时深度段可能还没翻完,要下次打开才能看到。窗口约 1–2 分钟,只在"刚好有人在这件
补语言时打开"才会碰上。

### 4.4 额度与花费

**日上限的单位不变,数值也不变。** 补语言阶段写的段打 `ai_lazy_fanout` 标签,
`daily_budget_exhausted` 只数 `ai_lazy`,所以不计入日上限。理由:

- 补语言只会跟在一次懒生成后面(1:1),不是新的触发入口,次数已被现有的日上限、每账号
  上限和每 IP 上限间接封住;
- 如果把它计入 `ai_lazy`,每件写的段从约 8 段涨到约 32 段,现有 1000 段的日上限会从约 120 件/天
  掉到约 31 件/天。

`WEIGHT_GENERATION`、`CAP_PER_USER`、`CAP_PER_IP` 都不变。

**成本估算**(公式和每个变量的来源都列在下面,便于独立重算):

```
每门补的语言 ≈ 段数 × 每段调用 + 问答条数 × 每条调用 (+ bio 1 次,仅缺时)
             ≈ 3 × 2 + 2.26 × 4 = 15 次 gpt-4o-mini
每次 mini ≈ 570 in × $0.15/M + 75 out × $0.60/M ≈ $0.00013
强模型重译 ≈ 3.2% 的翻译调用 × (464 in × $2.5/M + 170 out × $10/M ≈ $0.0029/次)
每门 ≈ 15 × 0.00013 + 15 × 0.032 × 0.0029 ≈ $0.0020 + $0.0014 ≈ $0.0034
每件(N=10 → 补 8 门)≈ 8 × 0.0034 ≈ $0.027
最坏一天(日上限 ≈ 120 件)≈ +$3.3
```

变量来源:

| 变量 | 值 | 来源 |
|---|---|---|
| 非 en 每语言段数 | 2.93–3.00 | prod 近 30 天 `source='ai_lazy'` 的段,按 (件, 语言) 计数 |
| 每段调用数 | 2 | `translate_object`:一次 `translate_section` + 一次 `check_faithfulness` |
| 每件每语言问答条数 | 2.26 | prod 近 30 天 `object_suggested_questions` |
| 每条问答调用数 | 4 | `translate_qa_items`:问句和答案各翻 1 次、各校 1 次 |
| mini 每次 tokens | 570 in / 75 out | prod `llm_usage` 近 30 天,channel=translate,gpt-4o-mini |
| 强模型占比 | 2201 / 69465 ≈ 3.2% | 同上,gpt-4o 调用 ÷ gpt-4o-mini 调用 |
| 强模型每次 tokens | 464 in / 170 out | 同上 |
| 日上限对应件数 | ≈ 120 | `_LAZY_DAILY_SECTION_CAP=1000` ÷ prod 实测 7.9 段/件 |

假设:强模型重译时调用的是 `translate_section` 和 `check_faithfulness` 各一次;这里粗算成
"每次调用有 3.2% 的概率再加一次 gpt-4o 调用",会稍微高估。

### 4.5 时延

- 首屏、请求者的深度段和问答:代码路径不变。验收时对比改前改后。
- 补语言阶段:每门语言串行约 15 次调用。`backfill_languages` 的 docstring 记录 prod 约
  12 秒/段(含校验),所以每门约 3 × 12 + 9 × 2 ≈ 55 秒。8 门、4 线程 ≈ 2 轮 ≈ 2 分钟。
  不占 `lazy_lock_at`,所以和 10 分钟锁 TTL 无关;`lazy_fanout_at` 也是 10 分钟,留有余量。

## 五、契约与兼容

- 纯后端改动,属于升级场景 3 的变体:契约形状不变。`generating` 仍是 bool,只是在补语言
  阶段对已出齐的语言提前返回 false。
- 老 App(V63 及以前):`generating=false` 时停止轮询,显示已有内容。行为与"懒翻译刚做完"
  一样,不会出现新状态。
- 不改前端,不需要发版。

## 六、prod 写入面(纪律 37)

补语言阶段会写:

| 表 | 行 | 还被谁引用 | 覆盖已有内容? |
|---|---|---|---|
| `object_content_sections` | 这一件 × `remaining` 语言 × 缺失段 | 只属于这件 | 否:只写该语言还没有已发布正文的段 |
| `object_suggested_questions` | 这一件 × `remaining` 语言 | 只属于这件 | 否:该语言已有已发布问答就跳过 |
| `artists.bio` | 这件的作者 × `remaining` 里缺 bio 的语言 | **跨件跨馆共享** | 否:只补缺失语言的键 |
| `museum_objects.attributes` | 这一件的 `lazy_fanout_at` 键 | — | 只加删这一个键 |

作废的已有音频:**0**。写的都是原来没有正文的段,或作者 bio 原来没有的语言。

本特性不跑存量回填。存量 ready 件里还有 16 件不满 10 门(prod 10-17:0 门 1 件、1 门 1 件、
2 门 7 件、9 门 7 件),要补就用现有的 `onboard translate`,另走一次带写入面清单的确认流程。

## 七、失败处理

| 失败 | 结果 |
|---|---|
| 某门语言翻译抛异常 | 只记日志,其余语言照跑;这门语言回到按请求懒翻译 |
| `_FANOUT_SEM` 满 | 不补语言;其余语言回到按请求懒翻译 |
| 进程在补语言中途崩溃 | `lazy_fanout_at` 10 分钟后失效;已落库的段保留,缺的回到按请求懒翻译 |
| `generate_object` 本身失败 | 不进入补语言阶段(没有 en 轴心,`translate_object_language` 本来就会全零返回) |

## 八、测试

单元/集成测试(沿用 `tests/integration/test_lazy_generation.py` 的写法):

1. 语言集不写死:馆配置 `["en","fr","de"]`、请求 `fr` → 只补 `de`;配置 4 门 → 补 2 门。
2. 已有段的语言不补(幂等):预置 `de` 段 → 不调翻译。
3. 某门语言抛异常 → 其余语言照样落库,`lazy_fanout_at` 最后被清掉。
4. `_FANOUT_SEM` 被占满 → 不补语言,不报错。
5. 补语言阶段写的段打 `ai_lazy_fanout`,`daily_budget_exhausted` 不把它们计入。
6. `generating`:补语言进行中,请求语言有已发布 guide → false;没有 → true。
7. `maybe_trigger`:补语言进行中,对缺内容的语言不点火。
8. 作者 bio 只在主线程补,且只补缺:预置 `fr` bio → 不被覆盖;多门语言都补上、互不丢失。
9. `translate_object_language(include_bio=False)` 不碰 `artists`;默认值行为不变(现有测试全过)。

staging 验收(Google TTS key 只认 VPS IP,所以在 staging 上做):

1. 选 3 件 stub,用请求语言 zh 触发,记录首屏(zh guide 的 `generated_at` − 触发时刻),
   与改前 staging 同口径基线对比:**不得变慢**。
2. 2–3 分钟内,这 3 件在该馆配置的每一门语言都有已发布 guide。
3. 补语言进行中用另一门语言打开:`generating=true`;guide 出来后变成 false。
4. 从 `llm_usage` 取当天 `translate@app` 调用增量 ÷ 件数,对比 4.4 节的估算(约 15 × 8 = 120
   次/件);偏差超过 2 倍就停下来查。

## 九、不做

- 存量回填:另走流程(见第六节)。
- 音频预生成:音频照旧按段点播。
- 懒翻译(ready 件缺一门语言)之后也补全部语言:没有需要。
- 配置开关:回滚就 revert PR,后端部署几分钟就能完成。
