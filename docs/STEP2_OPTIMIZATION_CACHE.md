# Step 2 优化：智能缓存机制

## 问题描述

### 当前缓存机制局限性

**实现方式：** 基于图片文件内容的 SHA256 哈希

- 前端：`recognize_artwork.dart:87` - `sha256.convert(bytes)`
- 后端：`image_service.py:90` - `hashlib.sha256(image_data).hexdigest()`

**问题场景：**

同一件艺术品的不同照片被视为完全不同的缓存键：

```
用户A拍摄梵高《星夜》：
- 设备：iPhone 14 Pro
- 分辨率：1080p
- 光线：白天自然光
- 角度：正面
→ SHA256: abc123...def456
→ 首次识别：20-30秒
→ 结果缓存

用户B拍摄梵高《星夜》：
- 设备：Samsung Galaxy
- 分辨率：4K
- 光线：博物馆灯光
- 角度：略微侧面
→ SHA256: xyz789...uvw012  （完全不同！）
→ 不命中缓存
→ 又需识别：20-30秒 ❌
```

### 影响评估

**用户体验：**
- 每个用户对同一艺术品首次识别都需要 20-30 秒
- 无法利用其他用户的识别结果
- 高峰期可能导致 API 成本激增

**成本影响：**
- OpenAI API 调用成本：$0.00015/图片（GPT-4V）
- 如果同一艺术品被拍摄 1000 次 → $0.15（当前方案）
- 理想缓存方案 → $0.00015（节省 99.9%）

## 优化方案

### 方案1：感知哈希（pHash）⭐ 推荐

**原理：** 基于图像视觉特征的哈希，相似图片产生相似哈希值

**实现：**

```python
# backend/requirements.txt
ImageHash==4.3.1

# backend/app/services/image_service.py
from PIL import Image
import imagehash
from io import BytesIO

@staticmethod
def generate_perceptual_hash(image_data: bytes) -> str:
    """
    生成感知哈希，相似图片产生相似哈希

    Args:
        image_data: 图片字节数据

    Returns:
        感知哈希字符串
    """
    image = Image.open(BytesIO(image_data))

    # 使用 pHash 算法
    phash = imagehash.phash(image, hash_size=8)

    return str(phash)

@staticmethod
def hash_similarity(hash1: str, hash2: str) -> float:
    """
    计算两个哈希的相似度

    Returns:
        相似度 0.0-1.0，1.0 表示完全相同
    """
    h1 = imagehash.hex_to_hash(hash1)
    h2 = imagehash.hex_to_hash(hash2)

    # 汉明距离越小，图片越相似
    hamming_distance = h1 - h2
    max_distance = 64  # 8x8 hash

    return 1.0 - (hamming_distance / max_distance)
```

**缓存策略：**

```python
# 1. 生成感知哈希
phash = ImageService.generate_perceptual_hash(image_data)

# 2. 在 Redis 中查找相似哈希
pattern = f"phash:*"
for key in redis.scan_iter(match=pattern):
    cached_hash = key.split(":")[1]
    similarity = ImageService.hash_similarity(phash, cached_hash)

    if similarity >= 0.90:  # 90% 相似度阈值
        # 命中缓存
        return redis.get(key)

# 3. 未命中，调用 AI 识别
result = await ai_service.recognize(image_data)

# 4. 缓存结果
redis.setex(f"phash:{phash}", 3600*24*7, result)
```

**优点：**
- 抗旋转、缩放、轻微色差
- 实现简单，性能好
- 预计命中率提升至 60-80%

**缺点：**
- 角度差异大（>45°）时可能失效
- 需要遍历缓存键（可优化为向量索引）

### 方案2：二级缓存（识别结果关联）

**原理：** 识别成功后，使用艺术品名称作为二级缓存键

**实现：**

```python
# 第一层：文件哈希缓存（当前实现）
file_hash = hashlib.sha256(image_data).hexdigest()
cached = redis.get(f"file:{file_hash}")

if cached:
    return cached

# 第二层：艺术品名称缓存
result = await ai_service.recognize(image_data)

if result.artwork_name != "Unknown Art" and result.confidence >= 0.7:
    # 缓存到艺术品名称键
    artwork_key = f"artwork:{result.artwork_name.lower().replace(' ', '_')}"
    redis.setex(artwork_key, 3600*24*30, result)  # 30天

    # 同时缓存文件哈希
    redis.setex(f"file:{file_hash}", 3600*24*7, result)  # 7天

return result
```

**优点：**
- 无需额外依赖
- 识别成功后，后续可直接通过作品名搜索
- 适合已知艺术品的场景

**缺点：**
- 首次识别仍然慢
- 需要精确的作品名称

### 方案3：图像向量检索（长期规划）

**原理：** 使用深度学习模型提取图像特征向量，在向量数据库中检索

**技术栈：**
```
- 特征提取：CLIP / ResNet50
- 向量数据库：Pinecone / Milvus / Qdrant
- 相似度算法：余弦相似度
```

**实现架构：**

```python
# 1. 提取图像特征向量
import torch
from transformers import CLIPProcessor, CLIPModel

model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32")
processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")

image = Image.open(BytesIO(image_data))
inputs = processor(images=image, return_tensors="pt")
features = model.get_image_features(**inputs)
vector = features.detach().numpy()[0]  # 512维向量

# 2. 在向量数据库中检索
from pinecone import Pinecone

pc = Pinecone(api_key="...")
index = pc.Index("artworks")

results = index.query(
    vector=vector.tolist(),
    top_k=1,
    include_metadata=True
)

if results.matches and results.matches[0].score > 0.95:
    # 命中缓存
    return results.matches[0].metadata['recognition_result']

# 3. 识别并存储向量
result = await ai_service.recognize(image_data)

index.upsert(
    vectors=[{
        'id': str(uuid.uuid4()),
        'values': vector.tolist(),
        'metadata': {'recognition_result': result}
    }]
)
```

**优点：**
- 最强大的语义相似性
- 可处理各种角度、光线、遮挡
- 预计命中率 80-95%

**缺点：**
- 成本较高（Pinecone: $70/月起）
- 复杂度高，维护成本大
- 需要额外的模型部署

## 实施建议

### Step 2 优先级

1. **Phase 1：感知哈希（pHash）** ⭐
   - 工作量：2-3天
   - 成本：几乎为零
   - 预期效果：命中率提升至 60-80%

2. **Phase 2：二级缓存（可选）**
   - 工作量：1天
   - 成本：零
   - 预期效果：对已知艺术品效果显著

3. **Phase 3：向量检索（长期）**
   - 工作量：1-2周
   - 成本：$70-200/月
   - 预期效果：最佳用户体验

### 性能指标

**当前（Step 1 MVP）：**
- 缓存命中率：~5%（仅完全相同文件）
- 平均识别时间：25秒
- API 调用成本：$0.00015 × 请求数

**目标（Step 2 优化后）：**
- 缓存命中率：60-80%（pHash）
- 平均识别时间：~8秒（混合）
- API 成本节省：60-80%

## 数据统计建议

为了验证优化效果，建议在 Step 2 添加以下监控指标：

```python
# app/models/recognition_stats.py
class RecognitionStats(Base):
    __tablename__ = "recognition_stats"

    id = Column(Integer, primary_key=True)
    image_hash = Column(String, index=True)
    perceptual_hash = Column(String, index=True)  # 新增
    cache_hit = Column(Boolean, default=False)
    cache_type = Column(String)  # "file", "phash", "artwork"
    response_time_ms = Column(Integer)
    artwork_identified = Column(Boolean)
    created_at = Column(DateTime)
```

## 相关资源

- [ImageHash Documentation](https://github.com/JohannesBuchner/imagehash)
- [CLIP Model (OpenAI)](https://github.com/openai/CLIP)
- [Pinecone Vector Database](https://www.pinecone.io/)
- [pHash Algorithm Paper](http://www.phash.org/)

## 记录信息

- 创建日期：2025-10-05
- 创建原因：Step 1 MVP 验收测试发现缓存局限性
- 优先级：Medium（Step 2 实施）
- 预期收益：API 成本节省 60-80%，用户体验显著提升
