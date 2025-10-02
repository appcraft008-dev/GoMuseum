# GoMuseum Step 1 快速启动指南

## 🚀 一键启动验收环境

```bash
cd /Users/hongyang/Projects/GoMuseum
bash scripts/start-manual-acceptance.sh
```

---

## 📋 手工验收快速指南

### 步骤1: 启动后端 (Terminal 1)

```bash
cd /Users/hongyang/Projects/GoMuseum/backend
uvicorn app.main:app --reload
```

**验证**: 浏览器打开 http://localhost:8000/docs 看到API文档

---

### 步骤2: 启动Flutter (Terminal 2)

```bash
cd /Users/hongyang/Projects/GoMuseum/frontend/gomuseum_app
flutter run -d chrome
```

**或选择其他设备**:
- iOS模拟器: `flutter run -d "iPhone 15 Pro"`
- Android: `flutter run -d emulator-5554`
- macOS桌面: `flutter run -d macos`

---

### 步骤3: 开始验收测试

按照 **MANUAL_ACCEPTANCE_GUIDE.md** 进行7项验收:

1. ✅ 相机拍照功能
2. ✅ 5秒内返回结果
3. ✅ 识别准确率
4. ✅ 缓存机制
5. ✅ 错误提示
6. ✅ 历史记录保存
7. ✅ 测试覆盖率

---

## 🧪 快速测试API

### 测试1: 健康检查

```bash
curl http://localhost:8000/api/health/
# 应返回: {"status":"ok"}
```

### 测试2: API连接测试

```bash
cd backend
python3 test_api_connection.py
```

预期输出:
```
✅ OpenAI API 连接成功!
识别结果:
  作品名称: [AI识别结果]
  艺术家: [艺术家名称]
  置信度: 95.00%
```

---

## 📊 测试覆盖率快速检查

### Flutter覆盖率

```bash
cd frontend/gomuseum_app
flutter test --coverage
genhtml coverage/lcov.info -o coverage/html
open coverage/html/index.html
```

### Python覆盖率

```bash
cd backend
pytest --cov=app --cov-report=html
open htmlcov/index.html
```

---

## 🗄️ 数据库快速查询

### 查看识别记录

```bash
# PostgreSQL
docker exec -it gomuseum-postgres psql -U gomuseum -d gomuseum_db -c "SELECT artwork_name, artist, confidence, timestamp FROM recognition_results ORDER BY timestamp DESC LIMIT 5;"
```

### 查看缓存

```bash
# Redis
docker exec -it gomuseum-redis redis-cli KEYS "recognition:*"
```

---

## 🐛 常见问题

### Q: 后端启动失败
```bash
# 检查Docker服务
docker ps

# 查看日志
docker-compose logs -f
```

### Q: Flutter编译错误
```bash
# 清理并重新生成
flutter clean
flutter pub get
flutter pub run build_runner build --delete-conflicting-outputs
```

### Q: API调用失败
```bash
# 检查.env配置
cat backend/.env | grep OPENAI_API_KEY

# 测试API连接
python3 backend/test_api_connection.py
```

---

## 📁 关键文档

| 文档 | 用途 |
|------|------|
| **MANUAL_ACCEPTANCE_GUIDE.md** | 完整手工验收指南 |
| **STEP1_FINAL_ACCEPTANCE.md** | 最终验收报告 |
| **API_KEYS_SETUP_GUIDE.md** | API配置指南 |
| **STEP1_COMPLETION_REPORT.md** | 技术完成报告 |

---

## ✅ 验收通过标准

- [ ] 7项验收全部通过
- [ ] 总分 ≥ 80分
- [ ] 无阻断性bug

---

## 🎯 下一步

验收通过后可以:
1. 开始Step 2开发 (AI Explanation)
2. 优化用户体验
3. 准备生产环境部署

---

**快速帮助**: 遇到问题查看后端日志 `docker-compose logs -f`
