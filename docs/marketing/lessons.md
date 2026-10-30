# GoMuseum 营销经验与教训

只收**真实踩过的坑**或**真实数据验证过的做法**，推测不收。每条写三样：规则、证据、日期。
能跨项目复用的，同时提炼进 `templates/organic-launch-playbook.md`。

分工：待办 → `docs/ops/backlog.md`；计划与决策 → `gomuseum-organic-launch-plan.md`；本文件只记"做了之后学到的"。

## Reddit

**R1. r/ParisTravelGuide 禁止任何 AI 参与写作，版主主动删。**
只能自己写英文，或自己写中文后用 Google 翻译 / DeepL；AI 起草、润色、翻译都不行，被删后不许重发。少用长破折号（—），这是最常被当成 AI 的特征。
证据：2026-10-25 版主删帖说明里写明规则；10-26 帖子 1xfjbgv 楼里一条评论被以 "appears to have been written using AI" 删除。

**R2. 挑发帖几小时内的新帖回，回得晚等于白写。**
证据（2026-10-26 早上读数）：发帖约 4 小时内回复的那条，9 小时后有 188 浏览、6 赞；在发帖已两天的旧帖下回复的那条，16 小时后只有 50 浏览、2 赞。

**R3. 回之前先读完整楼，查临时情况（罢工、闭馆）。**
证据：2026-10-25 第一条卢浮宫回答，写完才发现楼里有人提到周一罢工闭馆，只好编辑补救。
给场馆、市集等地点的事实前，还要先搜最近一个月的新闻（火灾、施工、罢工、闭馆）。证据：2026-10 整理 Reddit 要点时推荐了 Marché des Enfants Rouges，被楼里网友指出它 10-11 至 12 日夜里刚失火，只好回复致谢更正。

**R4. 补楼里别人没说的具体信息，这是最有效的切入点。**
例：一楼都在争"要不要做计划"，没人列出各馆闭馆日（卢浮宫、橘园周二，奥赛周一）。补上这一条后就是 R2 里那条 188 浏览、6 赞的回复。

**R5. 判断版块活跃度看发帖频率，别看搜索框里的"每周访客"。**
大版块在搜索下拉里显示简介而不是访客数，容易误以为小版块更大。证据（2026-10-25）：r/Louvre 最新 25 帖跨约 6 个半月，r/ParisTravelGuide 最新 25 帖跨约 2 天。
NSFW 版块（如 r/museum，因裸体艺术被设成 18+）的帖子不进搜索和推荐，没登录的人看要先过年龄验证，基本没有长尾流量，只能当加分项。

**R6. r/ParisTravelGuide 不只禁 AI 措辞，连"用 AI 查资料再转述"也不行：事实和观点都必须是你自己的。**
证据：2026-10-29 首个 Tips & Advice 帖（1xiyo2w，圣诞元旦博物馆闭馆速查）被版块 AI 检测器拦下；版主翻账号历史说"有片段像 AI"。实情是：事实由 Claude 查、中文要点由 Claude 列，英文由 ChatGPT 润色（之前的评论也是）。用户如实坦白后，版主 10-30 答复：拿用户的问题问 AI 再发回去没有意义，"even if you start writing future posts in your own words, it's not enough. The ideas and facts have to be your own as well."
做法：在 PTG 只凭自己的真实经历和知识发言，AI 不参与找贴、查资料、核对；对版主一律如实说。查好的事实改放到自己的网站上（见 backlog「网站问答页」）。

## Play / ASO

**A1. 小语种关键词用真实 Play 数据研究，不从英语、法语类推。**
证据：2026-10-20 意大利语 v1 按法语结论类推；补了真实 Play 搜索数据后，Title 改成 `GoMuseum: Guida del Louvre`。工具用 google-play-scraper；`search()` 在 `country='it'` 下取不到数据，要改用 `country='us', lang='it'`。

**A2. 文案里的免费额度、付费权益，上架前要跟后端配置逐字核对。**
证据：2026-10-25 线上十语审计，发现 ja、pl 两语的免费额度写法和后端不一致（`FREE_RECOGNITION_QUOTA`、`FREE_AUDIO_WINDOW`），已改并过审。

**A3. 评价：不能用自己或亲友的第二个账号给自己打分；请人评价，要让对方从正式商店页安装。**
内测通道里留的评价只进 Console 私下反馈，不会公开。新评价从进 Console 到公开显示要审核，2026-10-25 那条 5★ 当天前台仍是 0 条。

## SEO / Search Console

**S1. 域名资源提交 sitemap 要填完整 URL（`https://gomuseum.app/sitemap.xml`），只填路径会报"站点地图地址无效"。**
刚提交时显示"无法抓取"属于正常，过一阵会自己变成成功。证据：2026-10-25。

**S2. Search Console 用 Cloudflare 上的 DNS TXT 记录做所有权验证，这条记录不能删，删了就掉验证。** 2026-10-25。

## GEO（让 AI 回答里提到我们）

**G1. 基线（2026-10-26）：问"用什么 App 替代卢浮宫讲解器，最好能扫画"，ChatGPT、Perplexity、Google 都没提 GoMuseum。**
- ChatGPT：推荐 Smartify、TourLens、ArtGuide、Chiaro；引用来源以 Play 商店页和各家官网为主，没有 Reddit。直接问它 GoMuseum，它能说出功能，但称"在应用商店索引里找不到"，所以把 Smartify 排在前面。
- Perplexity：推荐 Smartify、CulturAll、TourLens、卢浮宫官方 App；引用的是博客和官网。
- Google 搜 "best app for louvre audio guide"：前排是各家商店页，加 3 个 r/ParisTravelGuide 帖子。其中 1w3b9zd（2026-08-31）还能评论，2027-02 底归档前要去回；另外两个是 2023 年的，已经归档。
- 推论（待验证）：AI 引用商店页，商店页本身就是 GEO 主战场，要靠安装量、评价和时间被收录。下次复测时对比。

**G2. 仓库是公开的，AI 会读里面的文档。**
ChatGPT 答出了"奥赛约 6,789 件"，官网上没有这个数，出处是公开仓库里的 `aso/google-play-round1/app-marketing-context.md`。写进仓库的营销文档要当成会被公开看到来写（2026-10-26）。

## 竞品观察

- **ArtGuide**（art-guide.app）：网页版拍画听讲解，免装 App，50 次免费扫描，之后 €4.90 起。用户亲测：以德语为主，收费项太多，体验差。2026-10-26
- **CulturAll**：卢浮宫拍作品或拍标签生成语音讲解，免费每天 5 件，通票 €1.99 起。Perplexity 推荐。2026-10-26
- **TourLens: Louvre Guide**：拍了就能听，宣称完全免费。ChatGPT 和 Perplexity 都推荐。2026-10-26
