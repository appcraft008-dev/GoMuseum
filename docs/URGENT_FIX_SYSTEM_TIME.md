# 紧急修复：系统时间错误

## 问题诊断
您的macOS系统时间被设置为 **2025年10月3日**，导致数据库约束检查失败。

## 修复步骤

### 1. 修正macOS系统时间

在macOS中修改系统时间：

```bash
# 方法1：使用系统偏好设置（推荐）
# 打开 系统偏好设置 > 日期与时间
# 取消勾选"自动设置日期和时间"
# 手动设置为正确的日期：2024年10月3日

# 方法2：使用命令行（需要管理员权限）
sudo systemsetup -setdate "10:03:2024"
sudo systemsetup -settime "12:00:00"

# 方法3：重新启用自动时间同步
sudo systemsetup -setusingnetworktime on
```

### 2. 重启Docker容器同步时间

系统时间修改后，必须重启Docker容器：

```bash
cd /Users/hongyang/Projects/GoMuseum
docker-compose down
docker-compose up -d
```

### 3. 验证时间已修正

```bash
# 检查宿主机时间
date

# 检查Docker容器时间
docker exec gomuseum-backend date
docker exec gomuseum-db date

# 检查数据库时间
docker exec gomuseum-db psql -U postgres -d gomuseum -c "SELECT now();"

# 检查Python应用时间
docker exec gomuseum-backend python -c "from datetime import datetime; print(datetime.utcnow())"
```

所有时间应该显示 **2024年10月3日**。

### 4. 测试识别功能

时间修正后，重新测试图片识别功能，应该可以正常工作。

## 注意事项

- 修改系统时间可能影响其他应用（如邮件、日历等）
- 建议启用"自动设置日期和时间"避免未来问题
- 如果使用Time Machine备份，可能需要重新设置备份计划
