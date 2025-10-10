# Content Module Architecture

## Module Structure

```
lib/features/content/
│
├── domain/                          # Domain Layer (业务逻辑层)
│   ├── entities/
│   │   └── explanation.dart         # 讲解实体 (纯业务对象)
│   │
│   ├── repositories/
│   │   └── content_repository.dart  # Repository接口定义
│   │
│   └── usecases/
│       ├── generate_explanation.dart    # UseCase: 生成讲解
│       └── generate_tts_audio.dart      # UseCase: 生成TTS音频
│
├── data/                            # Data Layer (数据层)
│   ├── models/
│   │   └── explanation_model.dart   # 数据模型 (JSON序列化)
│   │
│   ├── datasources/
│   │   └── content_remote_datasource.dart  # 远程API数据源
│   │
│   └── repositories/
│       └── content_repository_impl.dart    # Repository实现
│
└── presentation/                    # Presentation Layer (表现层)
    ├── providers/
    │   ├── content_providers.dart       # Riverpod Providers
    │   └── content_providers.g.dart     # 生成的Provider代码
    │
    └── widgets/
        ├── explanation_card.dart        # 讲解卡片组件
        └── audio_player_widget.dart     # 音频播放器组件
```

## Layer Dependencies

```
┌─────────────────────────────────────────────────────────┐
│                  Presentation Layer                      │
│  ┌──────────────┐  ┌────────────────────────────────┐  │
│  │   Providers  │  │          Widgets               │  │
│  │              │  │  - ExplanationCard             │  │
│  │  - DataSources│  │  - AudioPlayerWidget          │  │
│  │  - Repository │  │                                │  │
│  │  - UseCases  │  │                                │  │
│  └──────────────┘  └────────────────────────────────┘  │
└────────────────────────┬─────────────────────────────────┘
                         │ depends on
                         ▼
┌─────────────────────────────────────────────────────────┐
│                    Domain Layer                          │
│  ┌──────────┐  ┌──────────────┐  ┌─────────────────┐  │
│  │ Entities │  │ Repositories │  │    UseCases     │  │
│  │          │  │ (Interfaces) │  │                 │  │
│  │- Explain-│  │              │  │- GenerateExplan-│  │
│  │  ation   │  │- ContentRepo │  │  ation          │  │
│  │          │  │              │  │- GenerateTts    │  │
│  └──────────┘  └──────────────┘  │  Audio          │  │
│                                   └─────────────────┘  │
└────────────────────────┬─────────────────────────────────┘
                         │ implemented by
                         ▼
┌─────────────────────────────────────────────────────────┐
│                     Data Layer                           │
│  ┌──────────┐  ┌──────────────┐  ┌─────────────────┐  │
│  │  Models  │  │ DataSources  │  │  Repositories   │  │
│  │          │  │              │  │ (Implementations)│  │
│  │- Explain-│  │- ContentRem- │  │                 │  │
│  │  ation   │  │  oteDatasrc  │  │- ContentRepoImp │  │
│  │  Model   │  │              │  │                 │  │
│  └──────────┘  └──────────────┘  └─────────────────┘  │
└────────────────────────┬─────────────────────────────────┘
                         │ calls
                         ▼
┌─────────────────────────────────────────────────────────┐
│                    External APIs                         │
│  - POST /api/v1/content/explanation                     │
│  - POST /api/v1/content/tts/generate                    │
└─────────────────────────────────────────────────────────┘
```

## Data Flow

### Generate Explanation Flow

```
UI (Widget)
    │
    │ 1. User Action
    ▼
Provider (Riverpod)
    │
    │ 2. Get UseCase
    ▼
GenerateExplanation (UseCase)
    │
    │ 3. Validate params
    │ 4. Call repository
    ▼
ContentRepository (Interface)
    │
    │ 5. Implementation
    ▼
ContentRepositoryImpl
    │
    │ 6. Call datasource
    ▼
ContentRemoteDataSource
    │
    │ 7. HTTP POST
    ▼
Backend API (/api/v1/content/explanation)
    │
    │ 8. JSON Response
    ▼
ExplanationModel.fromJson()
    │
    │ 9. Convert to Entity
    ▼
Either<Failure, Explanation>
    │
    │ 10. Return result
    ▼
UI (Widget) - Display or Show Error
```

### Generate TTS Audio Flow

```
UI (Widget)
    │
    │ 1. User Action
    ▼
Provider (Riverpod)
    │
    │ 2. Get UseCase
    ▼
GenerateTtsAudio (UseCase)
    │
    │ 3. Validate params
    │ 4. Call repository
    ▼
ContentRepository (Interface)
    │
    │ 5. Implementation
    ▼
ContentRepositoryImpl
    │
    │ 6. Call datasource
    ▼
ContentRemoteDataSource
    │
    │ 7. HTTP POST
    ▼
Backend API (/api/v1/content/tts/generate)
    │
    │ 8. Binary Response (MP3)
    ▼
Base64 Encode / File Path
    │
    │ 9. Return audio URL
    ▼
Either<Failure, String>
    │
    │ 10. Return result
    ▼
AudioPlayer (just_audio) - Play Audio
```

## Error Handling Flow

```
Any Layer
    │
    │ Exception Occurs
    ▼
Data Layer
    │
    │ Catch Exception
    │ Convert to Failure
    ▼
Either<Failure, T>
    │
    │ Return Left(Failure)
    ▼
Presentation Layer
    │
    │ Handle with fold()
    ▼
UI - Display Error Message
```

### Exception → Failure Mapping

| Exception Type      | Failure Type      |
| ------------------- | ----------------- |
| ServerException     | ServerFailure     |
| NetworkException    | NetworkFailure    |
| TimeoutException    | TimeoutFailure    |
| ValidationException | ValidationFailure |

## Dependency Injection (Riverpod)

```
┌────────────────────────────────────────────┐
│       content_providers.dart               │
├────────────────────────────────────────────┤
│                                            │
│  dioProvider (from recognition module)    │
│         │                                  │
│         ▼                                  │
│  contentRemoteDataSourceProvider          │
│         │                                  │
│         ▼                                  │
│  contentRepositoryProvider                │
│         │                                  │
│         ├─────────────────┐               │
│         ▼                 ▼               │
│  generateExplanation  generateTtsAudio   │
│  UseCaseProvider      UseCaseProvider    │
│                                            │
└────────────────────────────────────────────┘
```

## Testing Strategy

### Unit Tests

1. **Domain Layer**
   - UseCases: 测试业务逻辑和参数验证
   - Entities: 测试相等性和不变性

2. **Data Layer**
   - Models: 测试JSON序列化/反序列化
   - DataSources: 测试API调用和错误处理
   - Repositories: 测试异常转换和数据流

### Widget Tests

1. **ExplanationCard**: 测试内容显示
2. **AudioPlayerWidget**: 测试播放控制

### Integration Tests

1. 端到端测试：从UI到API的完整流程
2. Mock后端响应进行测试

## Performance Considerations

### Optimization Points

1. **Caching**:
   - 缓存已生成的讲解内容
   - 缓存TTS音频文件

2. **Lazy Loading**:
   - 按需加载讲解的不同部分
   - 延迟加载音频数据

3. **Memory Management**:
   - 及时释放AudioPlayer资源
   - 管理大型音频文件的内存占用

4. **Network**:
   - 超时设置合理（30-60秒）
   - 重试机制
   - 请求取消支持

## Security Considerations

1. **API Authentication**: 确保API请求包含认证信息
2. **Input Validation**: 在UseCase层验证所有输入
3. **Error Messages**: 不暴露敏感的技术细节
4. **Audio Data**: 安全处理二进制音频数据

## Scalability

### Future Enhancements

1. **Multi-language Support**: 扩展更多语言支持
2. **Offline Mode**: 本地存储讲解和音频
3. **Personalization**: 根据用户偏好定制讲解
4. **Analytics**: 追踪讲解生成和播放统计
5. **Batch Operations**: 支持批量生成讲解

## Clean Architecture Benefits

1. **Testability**: 每层都可以独立测试
2. **Maintainability**: 清晰的职责分离
3. **Flexibility**: 易于替换实现（如更换数据源）
4. **Independence**: Domain层不依赖任何框架
5. **Reusability**: 业务逻辑可在不同平台复用
