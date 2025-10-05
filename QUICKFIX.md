# 时间戳问题快速修复指南

## 问题症状

图片识别功能返回500错误：

```
psycopg2.errors.CheckViolation: new row for relation "recognition_results"
violates check constraint "check_timestamp_not_future"
```

## 根本原因

**macOS系统时间被设置为2025年（未来时间）**

## 快速修复步骤（5分钟）

### 步骤1：修正系统时间

**方法A - 图形界面**（推荐）：

1. 打开"系统偏好设置" → "日期与时间"
2. 点击左下角锁图标🔒，输入密码
3. 取消勾选"自动设置日期和时间"
4. 手动修改年份为 **2024**
5. 重新勾选"自动设置日期和时间"

**方法B - 命令行**：

```bash
# 禁用自动时间
sudo systemsetup -setusingnetworktime off

# 设置日期（格式：月:日:年）
sudo systemsetup -setdate "10:03:2024"

# 重新启用自动时间（推荐）
sudo systemsetup -setusingnetworktime on
```

### 步骤2：重启Docker容器

```bash
cd /Users/hongyang/Projects/GoMuseum

# 停止容器
docker-compose down

# 启动容器
docker-compose up -d

# 等待容器启动
sleep 10
```

### 步骤3：验证修复

```bash
# 运行验证脚本
./scripts/verify-time.sh

# 或手动检查
date  # 应该显示2024年
docker exec gomuseum-backend date  # 应该显示2024年
docker exec gomuseum-db date  # 应该显示2024年
```

### 步骤4：测试功能

重新测试图片识别功能，应该正常工作。

---

## 长期优化（可选，10分钟）

为防止未来类似问题，建议执行代码优化：

### 1. 应用代码优化

代码已修改为使用数据库服务器端时间：

- 文件：`/Users/hongyang/Projects/GoMuseum/backend/app/models/recognition_result.py`
- 修改：`timestamp = Column(DateTime, server_default=func.now())`

### 2. 运行数据库迁移

```bash
# 进入backend容器
docker exec -it gomuseum-backend bash

# 运行迁移
alembic upgrade head

# 验证迁移
alembic current
# 应该显示：004 (head)

# 退出容器
exit
```

### 3. 验证迁移效果

```bash
# 检查timestamp列配置
docker exec gomuseum-db psql -U postgres -d gomuseum -c "
  SELECT column_default
  FROM information_schema.columns
  WHERE table_name = 'recognition_results'
  AND column_name = 'timestamp';
"
# 应该显示：now()
```

---

## 验证清单

完成后检查：

- [ ] 系统时间显示2024年
- [ ] 所有Docker容器时间显示2024年
- [ ] 图片识别功能正常
- [ ] 数据库迁移完成（可选）

---

## 详细文档

完整解决方案和技术细节请查看：

- `/Users/hongyang/Projects/GoMuseum/docs/TIMESTAMP_ISSUE_RESOLUTION.md`

紧急问题请参考：

- `/Users/hongyang/Projects/GoMuseum/docs/URGENT_FIX_SYSTEM_TIME.md`
