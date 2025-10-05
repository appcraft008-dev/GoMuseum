# 修复识别缓存问题 - 用户操作指南

## 问题现象

如果你遇到以下情况：
- ✅ 后端日志显示识别成功（confidence 0.95）
- ❌ 前端仍然显示"Unknown Artwork"或旧的失败结果
- ❌ 热重载、完全重启、flutter clean都无法解决

**原因**：本地Drift数据库中缓存了旧的失败记录。

---

## 解决方案（已自动执行）

### ✅ 缓存已清理

我已经帮你清理了本地缓存中的3条失败记录：

```
❌ Failed recognition records (已删除):
----------------------------
hash                 artwork_name     confidence  time
-------------------  ---------------  ----------  -------------------
2f3ae5d4ba4ceb00...  Unknown Artwork  0.0         2025-10-03 13:15:56
dfc34e5ec9900158...  Unknown Artwork  0.0         2025-10-03 13:11:19
8992d75e2b2ea0eb...  Unknown Artwork  0.0         2025-10-03 10:23:35

✅ Current database (剩余):
----------------------------
hash                 artwork_name    artist              confidence  time
-------------------  --------------  ------------------  ----------  -------------------
b34138931901a12f...  Self-Portrait   Vincent van Gogh    0.95        2025-10-03 13:37:01
d1b96134cb5dffcb...  The Bedroom     Vincent van Gogh    0.95        2025-10-03 13:26:27
e84155455e545f32...  Self-portrait   Vincent van Gogh    0.95        2025-10-03 13:25:50
26ebd0f724181098...  The Bedroom     Vincent van Gogh    0.95        2025-10-03 13:25:09
```

---

## 下一步操作

### 步骤1：重启Flutter应用

```bash
# 如果应用正在运行，先停止它（按 q 键或 Ctrl+C）

# 然后重新启动
cd /Users/hongyang/Projects/GoMuseum/frontend/gomuseum_app
flutter run -d macos
```

### 步骤2：重新识别那三张图片

1. 打开应用
2. 点击"Choose from Gallery"
3. 选择之前失败的图片
4. 现在应该会看到正确的识别结果！

**期望结果**：
- "The Bedroom" by Vincent van Gogh (confidence: 0.95)
- "Self-Portrait" by Vincent van Gogh (confidence: 0.95)
- 第三张图片的正确识别结果

---

## 如果问题再次出现

### 方法1：手动运行清理脚本

```bash
cd /Users/hongyang/Projects/GoMuseum/frontend/gomuseum_app
./scripts/clear_drift_cache.sh
```

脚本会显示交互式菜单：

```
Select an option:
  1) Clear ALL cache (all X records)
  2) Clear only failed records (X records)  # ← 推荐选这个
  3) Cancel

Enter your choice (1-3): 2
```

### 方法2：手动删除数据库文件

```bash
rm ~/Library/Containers/com.example.gomuseumApp/Data/Documents/gomuseum.db
```

**注意**：这会删除所有缓存记录（包括成功的记录）。

### 方法3：使用SQL命令

```bash
sqlite3 ~/Library/Containers/com.example.gomuseumApp/Data/Documents/gomuseum.db \
  "DELETE FROM recognition_results WHERE artwork_name='Unknown Artwork';"
```

---

## 预防措施

### 未来改进

我已经在代码中添加了以下功能（需要后续实现UI）：

1. **强制刷新识别** (`recognizeArtworkForceFresh`)
   - 绕过缓存，直接调用API
   - 用新结果覆盖旧缓存

2. **缓存管理工具** (`CacheManager`)
   - 清除所有缓存
   - 清除失败记录
   - 查看缓存统计

3. **建议的UI改进**：
   - 在识别结果页面添加"重新识别"按钮
   - 在设置页面添加"缓存管理"选项
   - 低置信度结果显示警告提示

### 技术层面改进建议

1. **添加缓存过期机制 (TTL)**
   - 缓存时间：24小时
   - 过期后自动重新识别

2. **低置信度结果不缓存**
   - confidence < 0.5 的结果不存入缓存
   - 每次都调用API获取最新结果

3. **用户可见的缓存管理**
   - 在设置页面显示缓存统计
   - 提供"清理缓存"按钮

---

## 技术说明

### 为什么热重载、重启、flutter clean都无效？

| 操作           | 清理范围                  | 是否清理Drift数据库 |
| -------------- | ------------------------- | ------------------- |
| 热重载 (r)     | 重新加载代码              | ❌                  |
| 完全重启 (R)   | 重启Dart VM               | ❌                  |
| flutter clean  | 删除build/产物            | ❌                  |
| 卸载应用       | 删除所有应用数据          | ✅                  |

**原因**：Drift数据库文件存储在应用的Documents目录：
```
~/Library/Containers/com.example.gomuseumApp/Data/Documents/gomuseum.db
```

这是受系统保护的用户数据目录，只有：
- 卸载应用
- 手动删除文件
- SQL DELETE命令
- 代码层的清理方法

才能清除数据。

### 缓存优先策略

```dart
// RecognitionRepositoryImpl.recognizeArtwork()
1. 计算图片的SHA256哈希值
2. 查询本地数据库：SELECT * FROM recognition_results WHERE image_hash = ?
3. if (找到记录) {
     return 缓存结果;  // ← 直接返回，不调用API
   } else {
     调用后端API;
     存入缓存;
     return API结果;
   }
```

**问题**：如果缓存中存在旧的失败记录，会直接返回，永远不会调用API更新。

---

## 验证修复成功

### 检查数据库状态

```bash
sqlite3 ~/Library/Containers/com.example.gomuseumApp/Data/Documents/gomuseum.db \
  "SELECT COUNT(*) FROM recognition_results WHERE artwork_name='Unknown Artwork';"
```

**期望输出**: `0`（没有失败记录）

### 检查应用日志

重新识别时，应该在控制台看到：

```
[network] Making API request: POST /api/v1/recognition/recognize
[dio] Response 200 OK
[cache] Storing result for hash: 8992d75e2b2ea0eb...
```

---

## 需要帮助？

如果以上方法都无法解决问题，请提供：

1. **数据库查询结果**：
   ```bash
   sqlite3 ~/Library/Containers/com.example.gomuseumApp/Data/Documents/gomuseum.db \
     "SELECT * FROM recognition_results ORDER BY timestamp DESC LIMIT 5;"
   ```

2. **应用日志**：运行`flutter run -v`的完整输出

3. **后端日志**：`docker logs gomuseum-backend`的相关部分

---

**最后更新**: 2025-10-03
**状态**: 已修复 ✅
