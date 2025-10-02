# GoMuseum Step 1 手工验收指南

**验收版本**: v0.1.0 (MVP Step 1)
**验收日期**: 2025年10月2日
**验收人**: [你的名字]

---

## 📋 验收清单总览

- [ ] 1. 打开相机拍照功能正常
- [ ] 2. 识别请求在5秒内返回结果
- [ ] 3. 识别结果准确率达到预期
- [ ] 4. 缓存机制工作正常,二次识别更快
- [ ] 5. 网络异常时有适当的错误提示
- [ ] 6. 识别历史记录正确保存
- [ ] 7. 测试覆盖率达到目标要求

---

## 🚀 第一步: 启动系统

### 1.1 启动后端服务 (Terminal 1)

```bash
# 进入项目目录
cd /Users/hongyang/Projects/GoMuseum

# 启动Docker服务 (PostgreSQL + Redis)
docker-compose up -d

# 等待服务启动 (约10秒)
sleep 10

# 验证Docker服务
docker ps

# 应该看到2个容器:
# - gomuseum-postgres (端口5432)
# - gomuseum-redis (端口6379)
```

```bash
# 进入后端目录
cd backend

# 确认Python环境
python3 --version  # 应该是 3.11.7

# 运行数据库迁移
alembic upgrade head

# 启动FastAPI服务
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 看到以下输出表示成功:
# INFO:     Uvicorn running on http://0.0.0.0:8000
# INFO:     Application startup complete.
```

**验证后端**:
- 浏览器打开: http://localhost:8000/docs
- 应该看到Swagger API文档界面
- 点击 `GET /api/health/` → Try it out → Execute
- 应该返回: `{"status": "ok"}`

---

### 1.2 启动Flutter应用 (Terminal 2)

```bash
# 新开一个Terminal窗口
cd /Users/hongyang/Projects/GoMuseum/frontend/gomuseum_app

# 确认Flutter环境
flutter --version  # 应该是 3.35.5

# 安装依赖 (如果还没有)
flutter pub get

# 生成代码
flutter pub run build_runner build --delete-conflicting-outputs

# 运行应用 (选择一个选项)

# 选项1: iOS模拟器
flutter run -d "iPhone 15 Pro"

# 选项2: Android模拟器
flutter run -d emulator-5554

# 选项3: Chrome浏览器 (推荐用于快速测试)
flutter run -d chrome

# 选项4: macOS桌面应用
flutter run -d macos
```

**验证Flutter**:
- 应该看到GoMuseum应用启动
- 首页加载正常
- 无崩溃和错误

---

## ✅ 验收项目详细步骤

### 验收项 #1: 打开相机拍照功能正常

**测试步骤**:

1. **在Flutter应用中找到拍照按钮**
   - 应该看到 "Take Photo" 按钮

2. **点击"Take Photo"**
   - 如果是真机: 应该打开系统相机
   - 如果是模拟器: 会提示无相机权限 (预期行为)
   - 如果是Chrome: 会请求相机权限

3. **测试相册选择**
   - 点击 "Choose from Gallery" 按钮
   - 应该打开系统相册选择器

**验收标准**:
- [ ] 相机权限请求正常显示
- [ ] 相册选择器正常打开
- [ ] 选择图片后能成功加载

**替代方案** (如果模拟器无相机):
```bash
# 使用预先准备的测试图片
# 1. 下载一张艺术品图片到手机/电脑
# 2. 使用"Choose from Gallery"功能选择图片
```

---

### 验收项 #2: 识别请求在5秒内返回结果

**测试步骤**:

1. **准备测试图片**
   - 从网上下载一张知名艺术品图片
   - 推荐: 蒙娜丽莎 / 星空 / 向日葵
   - 格式: JPEG或PNG
   - 大小: <10MB

2. **使用秒表计时**
   - 打开手机秒表或使用在线秒表
   - 点击"Choose from Gallery"选择图片
   - 同时启动秒表

3. **观察识别过程**
   - 应该立即显示"Loading"状态
   - 界面显示加载动画
   - 记录识别完成的时间

**验收标准**:
- [ ] 识别在**5秒内**返回结果
- [ ] Loading状态正确显示
- [ ] 进度提示清晰

**测试记录**:
```
测试图片1: [图片名称]
识别时间: [X.X秒]
结果: [ ] <5秒 (通过) / [ ] ≥5秒 (失败)

测试图片2: [图片名称]
识别时间: [X.X秒]
结果: [ ] <5秒 (通过) / [ ] ≥5秒 (失败)

测试图片3: [图片名称]
识别时间: [X.X秒]
结果: [ ] <5秒 (通过) / [ ] ≥5秒 (失败)
```

**调试技巧**:
如果超过5秒,检查:
```bash
# 查看后端日志
# Terminal 1 应该显示:
# INFO: POST /api/v1/recognition/recognize
# [识别耗时日志]

# 如果超时,可能是网络问题或OpenAI API慢
# 可以调整超时时间进行测试
```

---

### 验收项 #3: 识别结果准确率达到预期

**测试步骤**:

1. **准备5张知名艺术品图片**
   - 蒙娜丽莎 (Leonardo da Vinci)
   - 星空 (Vincent van Gogh)
   - 向日葵 (Vincent van Gogh)
   - 戴珍珠耳环的少女 (Johannes Vermeer)
   - 创世纪 (Michelangelo)

2. **逐一识别并记录结果**

**验收标准**:
- [ ] 作品名称准确率 ≥ 80% (5张中至少4张正确)
- [ ] 艺术家名称准确率 ≥ 90% (5张中至少4张正确)
- [ ] 时期判断准确率 ≥ 70% (5张中至少3张正确)
- [ ] 置信度分数 ≥ 0.7

**测试记录表**:

| 图片 | 预期结果 | 实际结果 | 作品名 | 艺术家 | 时期 | 置信度 | 通过 |
|-----|---------|---------|-------|-------|------|--------|------|
| 蒙娜丽莎 | Mona Lisa / Leonardo da Vinci / Renaissance | [填写] | ☐ | ☐ | ☐ | [X.XX] | ☐ |
| 星空 | Starry Night / van Gogh / Post-Impressionism | [填写] | ☐ | ☐ | ☐ | [X.XX] | ☐ |
| 向日葵 | Sunflowers / van Gogh / Post-Impressionism | [填写] | ☐ | ☐ | ☐ | [X.XX] | ☐ |
| 戴珍珠耳环的少女 | Girl with a Pearl Earring / Vermeer / Baroque | [填写] | ☐ | ☐ | ☐ | [X.XX] | ☐ |
| 创世纪 | Creation of Adam / Michelangelo / Renaissance | [填写] | ☐ | ☐ | ☐ | [X.XX] | ☐ |

**评分计算**:
```
作品名称准确率 = [正确数] / 5 = [X]%
艺术家准确率 = [正确数] / 5 = [X]%
时期准确率 = [正确数] / 5 = [X]%
平均置信度 = [总和] / 5 = [X.XX]
```

---

### 验收项 #4: 缓存机制工作正常,二次识别更快

**测试步骤**:

1. **第一次识别**
   - 选择一张图片进行识别
   - 记录识别时间 (应该2-4秒)
   - 记录结果

2. **立即第二次识别同一张图片**
   - 重新选择**完全相同**的图片
   - 记录识别时间 (应该<1秒)
   - 确认结果与第一次一致

3. **检查缓存来源**
   - 查看后端日志
   - 应该显示 "Cache hit" 或 "Database hit"

**验收标准**:
- [ ] 第二次识别时间 < 1秒
- [ ] 第二次结果与第一次完全一致
- [ ] 后端日志显示缓存命中

**测试记录**:
```
测试图片: [图片名称]

第一次识别:
- 时间: [X.X秒]
- 结果: [作品名/艺术家]
- 来源: AI识别 (OpenAI)

第二次识别 (同一图片):
- 时间: [X.X秒]
- 结果: [作品名/艺术家]
- 来源: [应显示缓存命中]
- 结果一致: [ ] 是 / [ ] 否

性能提升: [(第一次时间 - 第二次时间) / 第一次时间 * 100]%
```

**验证缓存层级**:
```bash
# 在Terminal 1 (后端日志)中查看:

# 第一次识别应该显示:
# INFO: Cache miss for image_hash=abc123...
# INFO: Calling OpenAI GPT-4V...
# INFO: Storing result to database and cache

# 第二次识别应该显示:
# INFO: Cache hit for image_hash=abc123...
# INFO: Returning cached result
```

---

### 验收项 #5: 网络异常时有适当的错误提示

**测试步骤**:

**场景1: 后端服务停止**

1. **停止后端服务**
   ```bash
   # 在Terminal 1中按 Ctrl+C 停止FastAPI服务
   ```

2. **尝试识别图片**
   - 选择任意图片
   - 点击识别

3. **观察错误提示**
   - 应该显示网络错误提示
   - 错误消息应该用户友好

**场景2: 网络超时**

1. **模拟慢速网络** (可选)
   ```bash
   # macOS网络限制工具
   # 系统偏好设置 → Network Link Conditioner
   # 或在backend/.env中设置极短的超时:
   # AI_TOTAL_TIMEOUT=0.1
   ```

2. **尝试识别**
   - 应该在超时后显示错误
   - 提示"识别超时,请重试"

**验收标准**:
- [ ] 后端停止时显示网络错误提示
- [ ] 错误消息清晰易懂 (不是技术错误码)
- [ ] 提供重试选项
- [ ] 界面不崩溃,可以继续使用

**测试记录**:
```
场景1: 后端服务停止
- 错误提示: [记录实际提示文本]
- 用户友好度: [ ] 好 / [ ] 中 / [ ] 差
- 界面状态: [ ] 正常 / [ ] 崩溃

场景2: 网络超时
- 错误提示: [记录实际提示文本]
- 超时时间: [X秒]
- 可以重试: [ ] 是 / [ ] 否
```

**恢复测试环境**:
```bash
# 重新启动后端服务
cd backend
uvicorn app.main:app --reload
```

---

### 验收项 #6: 识别历史记录正确保存

**测试步骤**:

1. **识别3张不同的图片**
   - 图片1: [名称]
   - 图片2: [名称]
   - 图片3: [名称]

2. **查询数据库验证保存**
   ```bash
   # 打开PostgreSQL
   docker exec -it gomuseum-postgres psql -U gomuseum -d gomuseum_db

   # 查询识别记录
   SELECT
     artwork_name,
     artist,
     confidence,
     timestamp
   FROM recognition_results
   ORDER BY timestamp DESC
   LIMIT 10;

   # 退出
   \q
   ```

3. **验证Redis缓存**
   ```bash
   # 打开Redis CLI
   docker exec -it gomuseum-redis redis-cli

   # 查看所有识别缓存
   KEYS recognition:*

   # 查看某个缓存内容
   GET recognition:[某个key]

   # 退出
   exit
   ```

**验收标准**:
- [ ] PostgreSQL中有3条识别记录
- [ ] 记录包含完整信息(作品名/艺术家/时期/描述/置信度/时间)
- [ ] Redis中有对应的缓存key
- [ ] 缓存数据与数据库一致

**测试记录**:
```
PostgreSQL记录:
- 记录数: [X条]
- 字段完整: [ ] 是 / [ ] 否
- 时间戳正确: [ ] 是 / [ ] 否

Redis缓存:
- 缓存key数: [X个]
- 数据一致性: [ ] 一致 / [ ] 不一致
- TTL设置: [ ] 24小时 / [ ] 其他
```

---

### 验收项 #7: 测试覆盖率达到目标要求

**测试步骤**:

1. **运行Flutter测试覆盖率**
   ```bash
   cd frontend/gomuseum_app

   # 运行测试生成覆盖率
   flutter test --coverage

   # 查看覆盖率报告
   genhtml coverage/lcov.info -o coverage/html
   open coverage/html/index.html
   ```

2. **运行Python测试覆盖率**
   ```bash
   cd backend

   # 运行测试生成覆盖率
   pytest --cov=app --cov-report=html

   # 查看覆盖率报告
   open htmlcov/index.html
   ```

3. **检查覆盖率数值**
   - Flutter覆盖率目标: ≥80%
   - Python覆盖率目标: ≥85%

**验收标准**:
- [ ] Flutter测试覆盖率 ≥ 80%
- [ ] Python测试覆盖率 ≥ 85%
- [ ] 所有测试全部通过
- [ ] 无跳过的测试

**测试记录**:
```
Flutter测试:
- 测试数量: [X个]
- 通过数量: [X个]
- 覆盖率: [X%]
- 达标: [ ] 是 (≥80%) / [ ] 否

Python测试:
- 测试数量: [X个]
- 通过数量: [X个]
- 覆盖率: [X%]
- 达标: [ ] 是 (≥85%) / [ ] 否
```

---

## 📊 综合验收结果

### 验收评分表

| 验收项 | 权重 | 得分 | 加权得分 | 备注 |
|-------|------|------|---------|------|
| 1. 相机拍照功能 | 10% | [0-10] | [X.X] | |
| 2. 5秒内返回结果 | 20% | [0-10] | [X.X] | |
| 3. 识别准确率 | 25% | [0-10] | [X.X] | |
| 4. 缓存机制 | 15% | [0-10] | [X.X] | |
| 5. 错误提示 | 10% | [0-10] | [X.X] | |
| 6. 历史记录 | 10% | [0-10] | [X.X] | |
| 7. 测试覆盖率 | 10% | [0-10] | [X.X] | |
| **总分** | **100%** | - | **[X.X]** | |

**评分标准**:
- 10分: 完全符合要求,超出预期
- 8-9分: 符合要求,表现良好
- 6-7分: 基本符合,有小问题
- 4-5分: 部分符合,有明显问题
- 0-3分: 不符合要求

**验收结论**:
- [ ] **通过** (总分 ≥ 80分)
- [ ] **条件通过** (总分 60-79分,需优化)
- [ ] **不通过** (总分 < 60分,需返工)

---

## 🐛 问题记录

如果发现问题,请记录在此:

### 问题1: [问题标题]
- **严重程度**: [ ] 严重 / [ ] 中等 / [ ] 轻微
- **复现步骤**:
  1.
  2.
  3.
- **预期行为**:
- **实际行为**:
- **截图/日志**:
- **建议解决方案**:

### 问题2: [问题标题]
...

---

## 📸 验收截图

请在验收过程中截图保存以下界面:

- [ ] Flutter应用首页
- [ ] 相机/相册选择界面
- [ ] Loading加载界面
- [ ] 识别成功结果展示
- [ ] 错误提示界面
- [ ] 数据库记录查询结果
- [ ] 测试覆盖率报告

**保存位置**: `/Users/hongyang/Projects/GoMuseum/docs/acceptance_screenshots/`

---

## ✅ 验收签字

**验收人**: ___________________
**验收日期**: 2025年10月2日
**验收结果**: [ ] 通过 / [ ] 条件通过 / [ ] 不通过

**备注**:



---

**提示**:
- 如果遇到问题,请先查看后端日志 (Terminal 1)
- Docker服务问题: `docker-compose logs -f`
- Flutter问题: 查看Flutter控制台输出
- 需要帮助时,提供完整的错误日志
