# 前端交接:作者卡(必选常驻)

## 变化
`GET /museums/{slug}/objects/{qid}/content` 新增 **`artist` 对象**,且 **artist 段从 `tabs` 移出**。

```json
"artist": {
  "name": "爱德华·马奈",
  "birth": "1832", "death": "1883",
  "nationality": "France",
  "notable_works": ["Olympia", "The Fifer"],
  "bio": "<作者经历叙事，按 language>"
}
```

## 前端要做
1. 导览页**固定展示作者卡**(姓名 / 生卒年 / 国籍 / 代表作 / 经历 bio)——**常驻,不随空隐**(它是必选项,区别于 tabs 的动态隐藏)。
2. tabs 里**不再有 artist**(内容已进卡)——原先若把 artist 当 tab 渲染,改为渲染作者卡。
3. 容错:`birth/death/nationality/bio` 可能 null、`notable_works` 可能 []——缺啥不显啥;`name` 一定有。

## 已知限制(v1)
- `nationality`/`notable_works` 当前是 **en 标签**(如 "France"/"Olympia"),zh 视图也显 en。`name`(已本地化)和生卒年不受影响。多语本地化留 round2。

## 契约
主文档 `docs/architecture/museum-api-contract.md` 端点4 已回写。纯加法(老前端不读 artist 卡无害;artist 不在 tabs = 少个 tab,内容进卡)。

---

## 追加(2026-06-30):作者卡改放到"深度内容"抽屉首位

用户本意:作者卡应是 **"深度内容"(底部抽屉)的第一张卡**,**不要**留在讲解主页面。

**3 处改动**(均前端):
1. `lib/features/guide/presentation/pages/guide_page.dart` 约 line 1129-1131:**删掉**主页面那段
   ```dart
   // 作者卡（必选常驻；name 一定有时才渲染）
   if (content.artist != null && content.artist!.name.isNotEmpty)
     GuideArtistCard(artist: content.artist!),
   ```
2. 同文件 line 1160:把 artist 传进抽屉
   ```dart
   onTap: () => showGuideDeepSheet(context, layer.deepTabs, artist: content.artist),
   ```
3. `lib/features/guide/presentation/widgets/guide_deep_sheet.dart`:
   - `showGuideDeepSheet(BuildContext, List<ObjectTab> tabs, {Artist? artist})` 加可选 `artist` 参数,透传给 `GuideDeepSheetContent(tabs: tabs, artist: artist)`。
   - `GuideDeepSheetContent` 加 `final Artist? artist;`。
   - 在抽屉内容列表**最前面**(tabs 之前)渲染:
     ```dart
     if (artist != null && artist.name.isNotEmpty)
       GuideArtistCard(artist: artist),
     ```
   - import `guide_artist_card.dart` 与 `Artist` 模型。

**测试**:`guide_artist_card_test.dart` 不变;`guide_layering_test`/`guide_redesign_widget_test` 若断言主页面有卡,改为断言抽屉里有、主页面没有。

> 注意"深度内容"抽屉的露出条件是 `layer.hasDeep`(deepTabs 非空)。若希望**即便没有深度 tabs 也能看到作者卡**(作者卡必选常驻),需把抽屉入口/露出条件改为"有作者卡 或 hasDeep";否则料薄无 tab 的件,抽屉不出现 → 作者卡也看不到。请前端按"作者卡必选常驻"的本意决定:建议入口条件改为 `layer.hasDeep || content.artist != null`。
