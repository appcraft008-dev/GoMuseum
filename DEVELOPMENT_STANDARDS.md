# GoMuseum 开发规范

## 项目概述

GoMuseum是一个基于AI的智能博物馆导览应用，采用Flutter + Python FastAPI的技术架构。

### 技术架构
- **前端**: Flutter 3.x + Dart
- **后端**: Python FastAPI + PostgreSQL + Redis
- **AI服务**: OpenAI GPT-4V, Claude, Pinecone
- **部署**: Docker + Kubernetes

## 代码规范

### 1. 命名规范

#### Dart/Flutter
- **文件命名**: snake_case，如 `user_profile_screen.dart`
- **类命名**: PascalCase，如 `UserProfileScreen`
- **变量命名**: camelCase，如 `userName`
- **常量命名**: lowerCamelCase，如 `apiBaseUrl`
- **私有成员**: 下划线前缀，如 `_privateMethod`

#### Python
- **文件命名**: snake_case，如 `user_service.py`
- **类命名**: PascalCase，如 `UserService`
- **变量命名**: snake_case，如 `user_name`
- **常量命名**: SCREAMING_SNAKE_CASE，如 `API_BASE_URL`
- **私有成员**: 下划线前缀，如 `_private_method`

### 2. 目录结构

#### Flutter 项目结构
```
lib/
├── core/               # 核心功能
│   ├── constants/     # 常量定义
│   ├── errors/        # 错误处理
│   ├── network/       # 网络配置
│   └── utils/         # 工具函数
├── features/          # 功能模块
│   ├── recognition/   # 识别功能
│   ├── explanation/   # 讲解功能
│   ├── user/         # 用户功能
│   └── payment/      # 支付功能
├── shared/           # 共享组件
│   ├── widgets/      # 通用UI组件
│   ├── models/       # 数据模型
│   └── services/     # 共享服务
└── main.dart         # 应用入口
```

#### Python 项目结构
```
backend/
├── app/
│   ├── api/          # API路由
│   ├── core/         # 核心配置
│   ├── models/       # 数据模型
│   ├── services/     # 业务逻辑
│   ├── schemas/      # Pydantic模式
│   └── dependencies/ # 依赖注入
├── tests/            # 测试文件
├── migrations/       # 数据库迁移
├── scripts/          # 脚本文件
└── requirements/     # 依赖文件
```

### 3. 代码质量

#### 代码格式化
- **Flutter**: 使用 `dart format`，行长度80字符
- **Python**: 使用 `black`，行长度88字符

#### 静态分析
- **Flutter**: 使用 `flutter analyze` 和 `analysis_options.yaml`
- **Python**: 使用 `flake8`, `mypy`, `isort`

#### 测试要求
- 单元测试覆盖率 ≥ 80%
- 集成测试覆盖率 ≥ 70%
- 关键业务逻辑 100% 覆盖率

## Git 工作流

### 分支策略
```
main                    # 生产分支
├── staging            # 预发布分支
└── feature/           # 功能分支
    ├── feature/auth   # 认证功能
    ├── feature/recognition # 识别功能
    └── feature/payment # 支付功能
```

### 提交规范 (Conventional Commits)
```
<type>[scope]: <description>

[body]

[footer]
```

**类型定义:**
- `feat`: 新功能
- `fix`: Bug修复
- `docs`: 文档更新
- `style`: 代码格式
- `refactor`: 重构
- `test`: 测试
- `chore`: 工具/构建

**示例:**
```
feat(recognition): add image recognition API

Implement AI-powered artwork recognition using GPT-4V
- Add image upload endpoint
- Integrate OpenAI Vision API
- Add caching for recognition results

Closes #123
```

## 开发环境

### 必需工具版本
- Flutter: 3.24.0+
- Dart: 3.5.0+
- Python: 3.11+
- Node.js: 20.x (工具链)
- Docker: 24.0+
- PostgreSQL: 16.x
- Redis: 8.x

### IDE 配置
推荐使用 VS Code 并安装以下扩展:
- Dart Code
- Flutter
- Python
- Black Formatter
- GitLens
- Docker

### 环境变量
```bash
# 开发环境 (.env.local)
DATABASE_URL=postgresql://user:pass@localhost:5432/gomuseum_dev
REDIS_URL=redis://localhost:6379/0
OPENAI_API_KEY=your_openai_key
CLAUDE_API_KEY=your_claude_key
PINECONE_API_KEY=your_pinecone_key
```

## 测试策略

### Flutter 测试
```dart
// 单元测试示例
testWidgets('Recognition button triggers recognition', (tester) async {
  await tester.pumpWidget(RecognitionScreen());
  await tester.tap(find.byType(ElevatedButton));
  await tester.pump();

  expect(find.text('正在识别...'), findsOneWidget);
});
```

### Python 测试
```python
# API测试示例
@pytest.mark.asyncio
async def test_recognize_artwork(client: AsyncClient):
    response = await client.post(
        "/api/v1/recognize",
        files={"image": ("test.jpg", test_image_data, "image/jpeg")}
    )
    assert response.status_code == 200
    assert "artwork_id" in response.json()
```

## 性能要求

### 响应时间目标
- 识别响应: ≤ 5秒 (P95)
- 讲解生成: ≤ 3秒 (P95)
- 页面加载: ≤ 2秒 (P95)

### 缓存策略
- L1 本地缓存: SQLite, 200MB
- L2 Redis缓存: 10GB TTL 1小时
- L3 CDN缓存: 无限容量

## 部署规范

### 环境划分
1. **Development**: 本地开发
2. **Staging**: 预发布测试
3. **Production**: 生产环境

### CI/CD 流程
1. 代码提交 → 自动测试
2. 合并到 staging → 部署到测试环境
3. 合并到 main → 部署到生产环境

### Docker 化
```dockerfile
# Python 后端
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

## 监控和告警

### 关键指标
- 识别成功率: ≥ 95%
- API可用性: ≥ 99.9%
- 响应时间: P95 ≤ 5s
- 错误率: ≤ 1%

### 日志级别
- ERROR: 系统错误，需要立即处理
- WARN: 警告信息，需要关注
- INFO: 一般信息，正常业务流程
- DEBUG: 调试信息，仅开发环境

## 安全规范

### API 安全
- JWT Token 认证
- Rate Limiting: 每用户100次/小时
- Input Validation: 严格验证所有输入
- HTTPS Only: 生产环境强制HTTPS

### 数据保护
- 密码加密: bcrypt + salt
- 敏感数据加密: AES-256
- API Key 轮换: 每90天轮换
- 最小权限原则

## 文档规范

### 代码文档
- 所有公开API必须有文档注释
- 复杂业务逻辑需要详细注释
- README文件必须包含快速开始指南

### API 文档
- 使用 OpenAPI/Swagger 自动生成
- 包含请求/响应示例
- 错误代码说明

## 发布管理

### 版本号规范
采用语义化版本号: `MAJOR.MINOR.PATCH`
- MAJOR: 不兼容的API变更
- MINOR: 向下兼容的功能性新增
- PATCH: 向下兼容的问题修正

### 发布流程
1. 功能开发完成 → 合并到 staging
2. 测试通过 → 创建 Release PR
3. Code Review → 合并到 main
4. 自动部署 → 监控系统状态

## 团队协作

### Code Review 要求
- 所有代码必须经过 Code Review
- 关注代码质量、性能、安全
- 提供建设性反馈

### 沟通规范
- 技术讨论使用英文
- 用户界面使用中文
- 错误信息提供中英文对照

---

**本文档将随项目发展持续更新。所有开发人员都有义务遵循这些规范，并在发现问题时及时反馈和改进。**