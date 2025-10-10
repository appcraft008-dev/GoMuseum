# Content Module

GoMuseum应用的Content模块，负责艺术品讲解生成和TTS音频生成功能。

## 架构设计

本模块遵循Clean Architecture模式，分为三层：

### Domain Layer (业务逻辑层)

**核心业务实体和规则，不依赖任何框架或外部库**

- **Entities**: 纯业务对象
  - `Explanation` - 艺术品讲解实体

- **Repositories**: 接口定义
  - `ContentRepository` - 定义数据操作接口

- **UseCases**: 业务用例
  - `GenerateExplanation` - 生成艺术品讲解
  - `GenerateTtsAudio` - 生成TTS音频

### Data Layer (数据层)

**处理数据获取和存储，实现Domain层定义的接口**

- **Models**: 数据模型（支持JSON序列化）
  - `ExplanationModel` - 讲解数据模型

- **DataSources**: 数据源
  - `ContentRemoteDataSource` - 远程API数据源

- **Repositories**: Repository实现
  - `ContentRepositoryImpl` - 实现ContentRepository接口

### Presentation Layer (表现层)

**UI组件和状态管理**

- **Providers**: Riverpod状态管理
  - `content_providers.dart` - 依赖注入配置
  - `content_providers.g.dart` - 自动生成的Provider代码

- **Widgets**: UI组件
  - `ExplanationCard` - 讲解内容展示卡片
  - `AudioPlayerWidget` - 音频播放器控件

## 技术栈

- **状态管理**: Riverpod 2.4.0 + riverpod_annotation
- **网络请求**: Dio 5.4.0
- **函数式编程**: dartz (Either类型)
- **音频播放**: just_audio 0.9.36
- **代码生成**: build_runner + riverpod_generator

## 依赖关系

```
Presentation Layer (providers, widgets)
    ↓
Domain Layer (entities, repositories, usecases)
    ↓
Data Layer (models, datasources, repository implementations)
```

- Domain层不依赖任何其他层
- Data层依赖Domain层
- Presentation层依赖Domain层

## API集成

### Backend Endpoints

1. **生成讲解**: `POST /api/v1/content/explanation`
2. **生成TTS音频**: `POST /api/v1/content/tts/generate`

详细API文档参见 [USAGE_EXAMPLE.md](./USAGE_EXAMPLE.md)

## 使用方法

### 1. 生成讲解

```dart
final useCase = ref.read(generateExplanationUseCaseProvider);
final params = GenerateExplanationParams(
  artworkName: "Mona Lisa",
  artist: "Leonardo da Vinci",
  period: "Renaissance",
  language: "en",
);

final result = await useCase(params);
result.fold(
  (failure) => print('Error: ${failure.message}'),
  (explanation) => print('Success: ${explanation.title}'),
);
```

### 2. 生成TTS音频

```dart
final useCase = ref.read(generateTtsAudioUseCaseProvider);
final params = GenerateTtsAudioParams(
  text: "Your text here",
  language: "en",
  speed: 1.0,
);

final result = await useCase(params);
result.fold(
  (failure) => print('Error: ${failure.message}'),
  (audioUrl) => audioPlayer.setUrl(audioUrl),
);
```

更多示例参见 [USAGE_EXAMPLE.md](./USAGE_EXAMPLE.md)

## 错误处理

所有业务操作返回 `Either<Failure, T>` 类型：

- `ServerFailure` - 服务器错误
- `NetworkFailure` - 网络连接失败
- `TimeoutFailure` - 请求超时
- `ValidationFailure` - 参数验证失败

## 测试

### 运行测试

```bash
flutter test test/features/content/
```

### 测试覆盖

- [ ] Domain层单元测试
- [ ] Data层单元测试
- [ ] Repository实现测试
- [ ] Widget测试

## 代码生成

当修改Riverpod providers时，需要重新生成代码：

```bash
flutter pub run build_runner build --delete-conflicting-outputs
```

## 代码格式化

```bash
dart format lib/features/content/
```

## 代码分析

```bash
flutter analyze lib/features/content/
```

## Future Improvements

1. **缓存机制**: 添加本地缓存以减少API调用
2. **离线支持**: 实现讲解内容的本地存储
3. **多语言**: 完善多语言支持
4. **音频优化**: 优化音频文件的存储和管理
5. **测试覆盖**: 添加完整的单元测试和Widget测试

## 相关模块

- **Recognition模块**: 艺术品识别功能
- **TtsService**: 核心TTS服务 (`lib/core/services/tts_service.dart`)
- **ExplanationPage**: 讲解展示页面 (`lib/ui/pages/explanation_page.dart`)

## 维护者

GoMuseum开发团队

## License

MIT
