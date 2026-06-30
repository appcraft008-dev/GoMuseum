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
