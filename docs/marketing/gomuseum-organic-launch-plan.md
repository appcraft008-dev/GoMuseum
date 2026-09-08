# GoMuseum Play 发版 · 首批用户获取计划

背景讨论：2026-09-08。前提约束见下，方案不适用时先重新问这两个问题再套用。

## 前提

- **渠道**：纯自然渠道，不投广告（无预算）
- **首批目标人群**：英语游客（巴黎游客盘子最大，Play/Google 英语搜索量最高，且现有内容深度也最匹配——见下）
- **产品现状**：Play 商店文案（en-US/fr-FR/zh-CN）、截图、feature graphic 已定稿（`docs/play-assets/`），定位已想清楚：
  "scan / 拍照识别"是细分空位——izi.TRAVEL（300万+下载）、Bloomberg Connects、GuidiGO 这些"音频导览"红海竞品都是选景点听讲解，没人做拍照识别（见 `docs/play-assets/store-listing/en-US.md` 开头的调研记录）
- **馆藏**：卢浮宫 / 奥赛 / 橘园 / 小皇宫，均在巴黎

## 三支柱

### A. 抓"在地意图"（优先级最高）

游客真正会下载的时刻，是站在馆门口、或在 Google 搜"louvre app"/"scan painting app"的那一刻——意图最强，转化率最高。

- [ ] Google Business Profile：把 App 挂到卢浮宫附近地图搜索结果
- [ ] gomuseum.app 落地页，针对 "free louvre guide" / "louvre app instead of audio guide rental" 关键词，纯内容页不用付费
- [ ] 线下：馆外咖啡馆/青旅常驻的免费地图/导览卡片架，放二维码（跑腿成本，零现金成本）

### B. 内容 + 社区种草

覆盖"出发前做攻略"这批人，量比门口临时搜索大，但决策周期长。

- [ ] Reddit（r/ParisTravelGuide, r/travel, r/Louvre 相关帖子）、TripAdvisor 论坛、Facebook Paris 旅行群：用真人账号真实回答"卢浮宫怎么逛不用请导游"类问题，顺手带 App——**不用官方账号刷屏**，容易被封
- [ ] 联系几个做"一天逛完卢浮宫"内容的 YouTube/TikTok 博主：免费邀测换一条自然视频，不是付费投放

### C. 首发冲榜窗口

Play 排名算法对新 App 前 1-2 周的安装/评分速度敏感，"scan artwork" 这个词现在没人占，越早积累越占坑越稳。

- [ ] 正式放量那一周，把 A/B 里能提前准备好的动作（落地页、Reddit 帖子草稿、博主联系）集中在同一窗口打出去，不摊薄
- [ ] 前几十个真实用户主动要一条真实评价——**不能诱导/刷好评（违反 Play 政策）**，只能主动问朋友/早期测试用户"觉得好用能不能去 Play 打个分"

## 待办 / 下一步

三块都要做，具体执行顺序和文案未展开，下次讨论时按需要深入：
- 落地页文案怎么写
- Reddit 帖子怎么写不像广告
- C 的启动时间点怎么定（依赖 Play 发版本身的进度，见 memory `product-backlog.md`）

## 通用方法论

跨项目可复用的框架已抽出到 `docs/marketing/templates/organic-launch-playbook.md`，本文件只保留 GoMuseum 专属决策和待办。
