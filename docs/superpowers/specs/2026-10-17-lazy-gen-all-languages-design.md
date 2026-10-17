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
remaining = resolve_languages(museum.languages)   # 该馆配置的语言集
            − {"en"}
            − 该件已有任一段落的语言              # 幂等,跑两次不重复花钱
```

请求语言正常情况下已有段落,自然被排除;如果它在生成阶段一行都没落成,补语言阶段顺手补上
(实施计划 Task 4 的 Ruling)。

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
| **B(推荐)** | `generate_object` 原样不动(仍是 en + 请求语言);生成结束后释放 `_SEM`,再在后台**按语言并行**调已有的 `translate_object_language` 补齐其余语言 | 要给"补语言"阶段单独做一个按语言的进行中标记(见第四节) |
| C | 维持现状,靠用户请求时触发懒翻译 | 就是现在要解决的问题 |

推荐 B 的理由:

1. 首屏和请求者自己的语言走的代码**一行不改**,时延不会变差。
2. `translate_object_language` 是懒翻译和 `onboard translate` 共用的函数,prod 已用它补齐了
   1027 件 ready 作品的 10 门语言。它只翻缺失段,幂等,对共享实体只补缺。
3. 标题的多语言在铺目录时已经由 `backfill_display_names` 填好(prod 实测:stub 平均
   9.99 门 `title_i18n`)。作者名、国籍、代表作的多语言**没有**核实:新作者在生成时只填了
   en 和请求语言,所以补出来的其余语言译文没有规范作者名可锁。这和现在的懒翻译一样,
   不是本特性带来的新问题,本 spec 不处理。

## 四、设计(方案 B)

### 4.1 流程

```
用户点开 stub
 └ maybe_trigger:上 lazy_lock_at、扣额度(不变)
    └ run_lazy_generation(后台)
       ├ 持有 _SEM(2):generate_object(en + 请求语言)        ← 不变
       │   首屏 guide → en 深度段 → 请求语言深度段 → 问答
       ├ 打 ai_lazy 标签、清 lazy_lock_at、释放 _SEM           ← 不变
       └ 新增:补语言阶段(仍在同一个后台线程里)
           ├ 前置条件不满足 → 结束(见下)
           ├ 写 lazy_fanout = {"at": now, "pending": remaining}
           ├ 主线程先串行补 remaining 里缺的作者 bio(只补缺)
           ├ 线程池按语言并行:translate_object_language(include_bio=False)
           │   每个线程自带 session,线程尾部 commit
           ├ 主线程按 as_completed:每完成一门,从 pending 移除并刷新 at(心跳)
           ├ 把本阶段写的段打 ai_lazy_fanout 标签
           └ finally:清 lazy_fanout
```

进入补语言阶段的前置条件(任一不满足就直接结束,其余语言回到按请求懒翻译):

1. 这件 `content_status == "ready"`,并且 en 有已发布段。生成结果是 `empty` 时不开线程。
2. `remaining` 非空。
3. 今天 `ai_lazy_fanout` 段数没到补语言日上限(4.4 节)。
4. 非阻塞拿到 `_FANOUT_SEM`。

只在 `run_lazy_generation` 后面接补语言阶段。`run_lazy_translation` 不接:prod 的 ready 件
绝大多数已有全部语言,没有必要。

### 4.2 并发与锁

- `_FANOUT_SEM = threading.Semaphore(2)`,非阻塞获取,满了就跳过、不排队。代价只是这件的
  其余语言回到按请求懒翻译。它和现有的 `_SEM` 一样是**进程级**的:prod 是 uvicorn
  `--workers 2`,所以实际最多 2 进程 × 2 件 × 4 线程 = 16 路 mini 调用。
- 补语言阶段跑在 FastAPI BackgroundTasks 的线程里,会多占这条线程几分钟。线程池默认
  40 个名额,和所有同步接口共用;因为 `_FANOUT_SEM` 最多 2 个,影响很小。
- 每件按语言开 `ThreadPoolExecutor(max_workers=4)`。
- 每个线程用 `guarded_sessionmaker(bind=db.get_bind())` 建自己的 session,和
  `backfill_languages` 一样。`translate_object_language` 自己不做最后的 commit,所以线程尾部
  要 `s.commit()`。线程之间写的行不重叠:段和问答都按 `(object_id, language)` 分开。
  `persist_gated_sections` 对非 en 语言不改 `museum_objects`(已对照
  `content_repo.py` 核实)。
- **作者 bio 是共享行(纪律 37),不能多线程写。** 多个线程同时 `art.bio = {**bio, lang: x}`
  会互相覆盖。所以:
  - 给 `translate_object_language` 加关键字参数 `include_bio=True`,默认值保持现有行为,
    补语言的线程传 `False`;
  - 开线程前由主线程把 `remaining` 里缺的 bio 串行补完。每门语言写之前先
    `db.refresh(art)`,写完马上 commit,把同作者另一件的生成同时改这一行时丢更新的窗口
    压到最小。
- 标记 `lazy_fanout` 存在 `attributes` 里,由主线程读写。每次写之前先 `db.refresh(o)`,
  因为音频锁也在同一个 JSON 里做读改写(`lazy_audio.py`)。
- 标记的 TTL 是 **5 分钟,按心跳算**:`at` 在开始时写一次,之后每完成一门语言刷新一次。
  所以慢任务只要还在推进就不会过期;进程被部署杀掉后,最多空等 5 分钟就自动失效。
- 清标记放在 `finally` 里,`BaseException`(例如进程关闭时的 `SystemExit`)也要能清掉。
  注意 web 进程启动时 `set_record_only()`,音频损失闸只记账不抛 `AudioLossBlocked`;
  只有脚本直接调用 `run_lazy_generation` 时才可能遇到它。
  线程里的普通异常在 `future.result()` 处兜住,只记日志。`BaseException` 冒出来时,先取消
  排队的语言、等在跑的结束,**之后**才清标记、还名额;否则孤儿线程会在标记清掉后继续写
  (计划审查时用真实线程池复现过)。
- 每完成一门语言就打一次 `ai_lazy_fanout` 标签,进程被杀时已落库的段也已计入补语言日上限。

### 4.3 `generating` 与重复触发

补语言阶段**不持有** `lazy_lock_at`,改用按语言的 `pending` 列表:

```
generating(请求语言 L) = lock_active(obj)
                         or (fanout_active(obj) and L in obj.attributes["lazy_fanout"]["pending"])
```

`maybe_trigger` 用同一个判据:`L in pending` 时不点火,防止和补语言阶段重复翻译。

这样 `generating` 对每门语言的含义都和现在的懒翻译一样:**这门语言整门翻完之前一直是
true**。这一点很重要,因为前端在 `generating=false` 时会把结果一直缓存下来
(`catalog_providers.dart` 的 `if (!content.generating) ref.keepAlive()`)。如果只有 guide
落库就返回 false,用户这次会话里就再也看不到后面的深度段。

| 场景 | 请求语言 L 的 `generating` | `maybe_trigger` |
|---|---|---|
| `lazy_lock_at` 有效 | true(不变) | 不点火(不变) |
| 补语言进行中,L 还在 `pending` 里 | true:前端继续轮询 | 不点火 |
| 补语言进行中,L 已翻完或不在 `remaining` 里 | false | 不变 |
| 都没有 | false(不变) | 不变 |

### 4.4 额度与花费

补语言阶段写的段打 `ai_lazy_fanout` 标签,**不计入**现有日上限(`daily_budget_exhausted`
只数 `ai_lazy`)。如果计入,每件写的段从约 8 段涨到约 32 段,现有 1000 段的日上限会从约
120 件/天掉到约 31 件/天。

但补语言要有**自己的日上限**,而不是靠"它只跟在一次生成后面"来推理封顶。原因是英语用户
触发时:每件在现有日上限里只算约 5 段,能放过的件更多,每件又要补 9 门而不是 8 门。

- 新增 `_FANOUT_DAILY_SECTION_CAP = 3000`:今天 `source == 'ai_lazy_fanout'` 的段数到了就
  不再补语言。和 `daily_budget_exhausted` 用同一条 count 查询,只是来源不同。
- 超了没有用户可见的坏结果,其余语言回到按请求懒翻译。

`_LAZY_DAILY_SECTION_CAP`、`WEIGHT_GENERATION`、`CAP_PER_USER`、`CAP_PER_IP` 都不变。

**成本估算**(公式和每个变量的来源都列出来,便于重算):

```
每补一门语言 ≈ en 已发布段数 × 每段调用 + 问答条数 × 每条调用 + bio(仅缺时)
             ≈ 3 × 2 + 2.26 × 4 + 1 = 16 次 gpt-4o-mini
每次 mini ≈ 570 in × $0.15/M + 75 out × $0.60/M ≈ $0.00013
强模型重译 ≈ 每门约 0.48 次 gpt-4o × $0.0029 ≈ $0.0014
每门 ≈ 16 × 0.00013 + 0.0014 ≈ $0.0035

每件:非 en 用户触发 → 补 8 门 ≈ $0.028;en 用户触发 → 补 9 门 ≈ $0.031
最坏一天 = 补语言日上限 3000 段 ÷ 每门 3 段 = 1000 门次 × $0.0035 ≈ $3.5
```

变量来源:

| 变量 | 值 | 来源 |
|---|---|---|
| en 已发布段数/件 | 均值 2.97,中位 3 | prod 近 30 天懒生成件(10-17 查) |
| 每段调用 | 2 次 mini | `translate_object`:一次 `translate_section`,加一次 `check_faithfulness`(判定用 mini,`factory.py`) |
| 每条问答调用 | 4 次 mini | `translate_qa_items`:问句和答案各翻一次、各校一次;问答没有强模型重译 |
| 每件每语言问答 | 2.26 条 | prod 近 30 天 `object_suggested_questions` |
| mini 每次 tokens | 570 in / 75 out | prod `llm_usage` 近 30 天,channel=translate |
| 强模型 | 2201 次 ÷ 69465 次 ≈ 3.2%;464 in / 170 out | 同上。只有段落有重译,所以折成每段约 16%,每门 3 段约 0.48 次 |
| 不调 LLM 的 | 语言检测 | `lang_detect` 用本地 lingua |

这个估算已由另一个模型独立重算过。它指出的英语用户触发补 9 门、bio 漏算这两点已经并入;
它对段数的疑问(4.9 vs 3)经 prod 复查,已发布 en 段确实是 2.97。

### 4.5 时延

- 首屏、请求者的深度段和问答:代码路径不变,验收时对比改前改后。
- 补语言阶段,每门语言串行约 16 次调用:3 段 × 约 12 秒(含校验,数据来自
  `backfill_languages` 的 docstring 记录的 prod 实测),加问答 9 次 × 约 6 秒,约 90–100 秒。
  中日韩语言每次翻译还要多查一次名字表(Wikidata),会更慢一点。
  - 补 8 门,4 线程,2 轮 ≈ 3–3.5 分钟;
  - 补 9 门(en 用户触发),3 轮 ≈ 5 分钟。
- 补语言不占 `lazy_lock_at`,和 10 分钟锁 TTL 无关;自己的标记靠心跳续期(4.2 节)。
- 其余语言的用户如果在这几分钟里打开,要等自己的语言轮到,最多约 5 分钟。这比现在
  "每门语言各自等一次懒翻译"差不多或更快,而且只在这件刚生成的几分钟内。

## 五、契约与兼容

- 纯后端改动,属于升级场景 3 的变体:契约形状不变,`generating` 仍是 bool。
- 每门语言的 `generating` 和现在的懒翻译一样,都是"这门语言整门翻完前为 true"
  (4.3 节),所以老 App 的轮询和缓存逻辑看到的状态和现在一样。
- 不改前端,不需要发版。

## 六、prod 写入面(纪律 37)

补语言阶段会写:

| 表 | 行 | 还被谁引用 | 覆盖已有内容? |
|---|---|---|---|
| `object_content_sections` | 这一件 × `remaining` 语言 × 缺失段 | 只属于这件 | 否。`remaining` 只含该件一行都没有的语言,所以不会碰到已有的 needs_review 段 |
| `object_suggested_questions` | 这一件 × `remaining` 语言 | 只属于这件 | 否。同上 |
| `artists.bio` | 这件的作者 × `remaining` 里缺 bio 的语言 | **跨件跨馆共享** | 否。只补缺失语言的键,写前 refresh |
| `museum_objects.attributes` | 这一件的 `lazy_fanout` 键 | — | 只增删这一个键,写前 refresh |

作废的已有音频:**0**。写的都是原来没有正文的段,以及作者 bio 原来没有的语言。

懒翻译的触发判据也要改(见第七节),它会让少量已 ready、但某门语言半缺的件在用户请求时
补齐。写入面和现在的懒翻译完全相同(都是 `translate_object_language`)。

本特性不跑存量回填。存量 ready 件里还有 16 件不满 10 门(prod 10-17:0 门 1 件、1 门 1 件、
2 门 7 件、9 门 7 件),要补就用现有的 `onboard translate`,另走一次带写入面清单的确认流程。

## 七、失败处理

| 失败 | 结果 |
|---|---|
| 某门语言翻译抛异常 | 只记日志,其余语言照跑,这门语言从 `pending` 移除 |
| 某门语言**半途**失败(guide 已落库,深度段没翻) | 用户下次请求时由懒翻译补齐,前提是改了下面这条判据 |
| `_FANOUT_SEM` 满,或补语言日上限已到 | 不补语言,其余语言回到按请求懒翻译 |
| 进程在补语言中途被杀(部署重启很常见) | 标记最多 5 分钟后失效;已落库的段保留,缺的段由懒翻译补齐 |
| `generate_object` 失败或结果为 `empty` | 不进入补语言阶段 |

**懒翻译判据要改。** 现在 `maybe_trigger` 用 `_has_any_section(lang)`:只要该语言有任何一段,
就不再触发。半途失败的语言(已有 guide、缺深度段)因此永远补不齐。补语言会把半途失败的
机会放大几倍,所以改成:

```
wants_translation = ready 且 L != "en"
                    且 en 已发布的 section_code 里,有该语言一行都没有的(任何状态都算有)
                    且 L 不在 pending 里
```

needs_review 的行也算"有",所以不会对翻不过闸的段反复点火、反复花钱。

## 八、测试

单元/集成测试(沿用 `tests/integration/test_lazy_generation.py` 的写法)。现有 fixture 是
单连接的 sqlite(StaticPool),多线程测不准,所以单元测试把线程池换成串行执行器,真并发
留给 staging 验收。

1. 语言集不写死:馆配置 `["en","fr","de"]`、请求 `fr` → 只补 `de`;配置 4 门 → 补 2 门。
2. 请求语言是 en:除 en 外全部补上。
3. 已有任何一段的语言不进 `remaining`(幂等);needs_review 的段不会被重翻。
4. 某门语言抛异常 → 其余语言照样落库,这门语言从 `pending` 移除,标记最后被清。
5. 抛 `BaseException` 时标记也被清掉。
6. `_FANOUT_SEM` 占满、补语言日上限已到、生成结果是 `empty` → 都不补语言,不报错。
7. 补语言写的段打 `ai_lazy_fanout`;`daily_budget_exhausted` 不计入;补语言日上限计入。
8. `generating`:L 在 `pending` 里时为 true,**即使 L 已有已发布 guide**;L 移出 `pending`
   后为 false;标记心跳超时后为 false。
9. `maybe_trigger`:L 在 `pending` 里时不点火。
10. 懒翻译新判据:L 有 guide、缺某个 en 已发布的深度段 → 点火;只缺"en 已发布但 L 是
    needs_review"的段 → 不点火。
11. 作者 bio:主线程补齐多门语言、互不丢失;预置 `fr` bio 不被覆盖;线程里
    `include_bio=False` 不碰 `artists`;默认值行为不变(现有测试全过)。

staging 验收(Google TTS key 只认 VPS IP,所以在 staging 上做):

1. 选 3 件 stub,用请求语言 zh 触发,记录首屏(zh guide 的 `generated_at` 减去触发时刻),
   和改前 staging 同口径的基线对比:**不得变慢**。
2. 约 5 分钟内,这 3 件在该馆配置的每一门语言都有已发布 guide 和深度段。
3. 补语言进行中,用另一门语言打开:`generating=true`,直到这门语言整门翻完才变 false;
   用 App 真机看一次深度段完整出现。
4. 从 `llm_usage` 取当天 `translate@app` 调用的增量,除以件数,和 4.4 节对比
   (约 16 × 8 ≈ 128 次/件)。偏差超过 2 倍就停下来查。
5. 补语言进行中重启一次 staging 后端容器:5 分钟后标记失效;再用缺内容的语言打开,
   能由懒翻译补齐。

## 九、不做

- 存量回填:另走流程(见第六节)。
- 音频预生成:音频照旧按段点播。
- 懒翻译(ready 件缺一门语言)之后也补全部语言:没有需要。
- 配置开关:回滚就 revert PR,后端部署几分钟就能完成。

## 十、审查记录

2026-10-17 由另一个模型(Sonnet 5.5)对照代码独立审查,并独立重算了成本。已采纳:

- **`generating` 提前变 false 会让 App 永久缓存半成品**(`keepAlive`):改为按语言的
  `pending` 列表(4.3 节)。
- 半途失败的语言永远补不齐:懒翻译判据改成"按 en 段逐个查缺"(第七节)。
- 补语言加自己的日上限(4.4 节),不再只靠推理封顶。
- 英语用户触发补 9 门、bio 调用漏算:并入成本估算。
- 时延低估:问答每次调用从 2 秒改按 6 秒算,标记 TTL 改为心跳续期的 5 分钟。
- bio 和标记写前 refresh;清标记放 `finally`;结果为 `empty` 不开线程。

实施计划审查(2026-10-17,Sonnet 5.5 与 Fable 各一份,都在副本里实跑了计划代码)带回 spec 的改动:
`remaining` 不再单独排除请求语言;`BaseException` 时先停线程再清标记;每完成一门打标签;
并发数按进程级如实写明。
- 单元测试用串行执行器,真并发留给 staging 验收。

未采纳:审查者怀疑段数应按 4.9 段算。prod 复查已发布的 en 段均值是 2.97,维持 3 段。
