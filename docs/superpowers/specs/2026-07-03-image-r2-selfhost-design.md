# 图像 R2 自存（路线图阶段4）设计

> 2026-07-03 与用户 brainstorm 定稿。修列表图加载慢/Wikimedia UA 拦截；兼作识别参照图库地基。

## 目标与非目标

**目标**：全馆图片自存 R2、预生成两档尺寸；端点字段名不变、前端零改；多角度图入库（识别地基）；合规署名。
**非目标**：Commons 分类挖掘（多角度图扩采，留给识别机制 brainstorm——噪声过滤策略取决于识别方案）；Cloudflare 在线缩放（平台耦合）；存原图（可从 source_url 重下，YAGNI）。

## 核心决策（用户拍板）

1. **两档、不存原图**：thumb 480px（列表/馆包）+ large 1600px（详情/识别参照），JPEG q82。
2. **抓版权信息**：物化时调 Commons API 补 `ObjectImage.license/credit`（雕塑照片有摄影师版权，CC-BY 必须署名）。
3. **批量预物化为主 + 懒补漏为辅**：
   - 列表一屏要几十张缩略图（多数永不被点开）+ 识别参照库必须先于识别存在 → **图=目录门面，必须预物化**；成本≈0（下载免费/R2 几分钱/出口免费），与讲解（必须懒，$/件）成本结构相反——此分界写入契约。
   - **自愈钩子**：懒生成/识别触发时顺手检查该件图未物化（新进目录/上次失败）→ 后台补单件（复用物化器，幂等）。

## 架构：采集与物化解耦

**采集层**（图从哪来）：
- catalog 收 **P18 全部值**（现只留第一张）：`StubRecord.image_url` 保持（首张=primary），新增 `image_urls` 列表；loader 落多行 `ObjectImage`（首张 `role=primary`，其余 `role=view`）。
- 未来 Commons 挖掘器 = 新采集来源，产出同样的行，物化层零改。
- 数据现实（奥赛雕塑 169 件）：P18 多图仅 15 件；P373 Commons 分类 117 件（金矿但噪声大，识别轮再定）。

**物化层**（图怎么存）：
- 新 onboard 子命令 `images --target <env> [--limit N]`：扫"有 `source_url`、无 `image_key`"的 ObjectImage 行 →
  下载（PoliteSession 合规 UA、1req/s）→ Pillow 两档 → R2 put → Commons imageinfo 补 license/credit → 填 `image_key`。
- 逐行 try/except：失败留空、记日志、重跑重试（幂等）。SVG/超 60MB 跳过记日志。
- 单件物化函数独立（`materialize_object_images(db, obj)`）供懒补漏钩子复用。

## key 约定与端点接线

- `image_key` 存**基础键**：`images/{qid}/{n}`；实际文件 `{base}_thumb.jpg`、`{base}_large.jpg`。
  （库中现无存量 image_key，约定自由定；与 audio_key 存全键的先例不同，注释说明。）
- 端点取图助手按档位出 URL：`thumbnail`（端点3）/`image`（端点2）→ thumb 档；`images[].url`（端点4）→ large 档。字段名不变。
- 无 image_key 行为不变（回退 source_url）。

## 依赖与体量

- 新增 **Pillow**（poetry lock，项目规矩）。
- prod 全量 ~2000 张：下载 5-10GB、1.5-3h（限速主导）、R2 存 ~1.5GB（月费分级）。

## 验证

- TDD：物化器（下载/出档/落 key/license 注入 fake 全离线）；采集层多 P18 → 多行 role；端点档位 URL。
- staging `--limit 30` 真图样本：缩略图/大图直链 200、雕塑多图、credit 有值。
- prod 全量跑 = 用户指示后执行。

## 契约回写

图片字段节：R2 直链兑现 + 档位语义 + role 多角度 + "图=预物化 vs 内容=懒生成"成本分界 + Commons 挖掘留待识别 brainstorm。
