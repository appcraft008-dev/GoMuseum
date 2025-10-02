# GoMuseum API Keys 配置指南

## 📋 需要的API Keys

为了运行GoMuseum的AI识别功能,你需要配置以下API keys:

---

## 1. OpenAI API Key (必需)

### 获取步骤:

1. **访问OpenAI平台**: https://platform.openai.com/
2. **登录或注册**账号
3. **进入API Keys页面**: https://platform.openai.com/api-keys
4. **点击"Create new secret key"**
5. **复制生成的key**(格式: `sk-proj-...` 或 `sk-...`)
6. **充值账户**: https://platform.openai.com/account/billing/overview
   - 最低充值: $5 USD
   - 建议充值: $10-20 USD (测试和开发够用)

### 预估成本:

| 使用场景 | Token消耗 | 预估成本 |
|---------|----------|---------|
| 单次识别 | ~500 tokens | $0.01-0.02 |
| 100次测试 | ~50K tokens | $1-2 |
| 1000次识别 | ~500K tokens | $10-20 |

**模型**: gpt-4o (Vision)
- Input: $5.00 / 1M tokens
- Output: $15.00 / 1M tokens

---

## 2. Anthropic Claude API Key (可选,推荐)

这是fallback服务,当OpenAI失败时自动使用。

### 获取步骤:

1. **访问Anthropic Console**: https://console.anthropic.com/
2. **登录或注册**账号
3. **进入API Keys页面**: https://console.anthropic.com/settings/keys
4. **点击"Create Key"**
5. **复制生成的key**(格式: `sk-ant-...`)
6. **充值账户**: https://console.anthropic.com/settings/plans
   - 最低充值: $5 USD

### 预估成本:

| 使用场景 | Token消耗 | 预估成本 |
|---------|----------|---------|
| 单次识别 | ~400 tokens | $0.008-0.015 |
| 100次测试 | ~40K tokens | $0.8-1.5 |

**模型**: claude-3-5-sonnet-20241022
- Input: $3.00 / 1M tokens
- Output: $15.00 / 1M tokens

---

## 🔧 配置步骤

### 步骤1: 复制环境变量文件

```bash
cd /Users/hongyang/Projects/GoMuseum/backend
cp .env.example .env
```

### 步骤2: 编辑 `.env` 文件

用你喜欢的编辑器打开 `backend/.env`:

```bash
# 使用VSCode
code backend/.env

# 或使用vim
vim backend/.env

# 或使用nano
nano backend/.env
```

### 步骤3: 填写API Keys

找到以下行,填入你的真实API keys:

```bash
# OpenAI API (必填)
OPENAI_API_KEY=sk-proj-your-actual-key-here

# Anthropic Claude API (可选,但推荐)
ANTHROPIC_API_KEY=sk-ant-your-actual-key-here
```

**示例** (不要使用这个,这只是格式示例):
```bash
OPENAI_API_KEY=sk-proj-AbC123...xyz789
ANTHROPIC_API_KEY=sk-ant-api03-XyZ456...abc123
```

### 步骤4: 保存文件

- **VSCode**: `Cmd+S` (Mac) 或 `Ctrl+S` (Windows)
- **vim**: 按 `Esc`, 输入 `:wq`, 回车
- **nano**: 按 `Ctrl+O`, 回车保存, `Ctrl+X` 退出

---

## ✅ 验证配置

运行验证脚本检查API keys是否正确:

```bash
cd /Users/hongyang/Projects/GoMuseum/backend
python -c "
from app.core.config import settings
print(f'OpenAI API Key配置: {\"✅ 已配置\" if settings.OPENAI_API_KEY else \"❌ 未配置\"}')
print(f'Claude API Key配置: {\"✅ 已配置\" if settings.ANTHROPIC_API_KEY else \"⚠️  未配置(可选)\"}')
"
```

预期输出:
```
OpenAI API Key配置: ✅ 已配置
Claude API Key配置: ✅ 已配置
```

---

## 🧪 测试API连接

### 测试OpenAI连接:

```bash
cd backend
python -c "
import asyncio
from app.services.ai_service import AIService

async def test():
    service = AIService()
    # 使用测试图片(Base64)
    test_image = 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=='
    result = await service.recognize(test_image)
    print(f'AI识别测试: {result[\"source\"]} - {result[\"artwork_name\"]}')

asyncio.run(test())
"
```

成功输出示例:
```
AI识别测试: openai - [识别到的作品名称]
```

---

## 🚨 安全提醒

### ⚠️ 重要:

1. **永远不要提交 `.env` 文件到Git**
   - `.env` 已在 `.gitignore` 中
   - 检查: `git status` 不应该显示 `.env`

2. **不要分享你的API keys**
   - 一旦泄露,立即删除并重新生成

3. **定期检查使用量**
   - OpenAI: https://platform.openai.com/usage
   - Anthropic: https://console.anthropic.com/settings/usage

4. **设置消费限制**
   - OpenAI: 在Billing设置中设置月度限额
   - Anthropic: 在Plans设置中设置预算告警

---

## 🔄 Fallback策略说明

GoMuseum使用3级fallback确保服务可用性:

```
1. OpenAI GPT-4V (3秒超时)
   ↓ 失败
2. Anthropic Claude Vision (2秒超时)
   ↓ 失败
3. Manual Fallback (返回"未识别")
```

**建议配置**:
- ✅ **同时配置OpenAI和Claude** - 最佳可用性(99.9%+)
- ⚠️ **只配置OpenAI** - 可用性依赖单一服务(~99%)
- ❌ **都不配置** - 所有识别都返回"未识别"(仅用于测试架构)

---

## 💰 成本优化建议

### 开发和测试阶段:

1. **使用缓存**
   - 相同图片第二次识别不消耗API调用
   - 缓存命中率目标: 60%+

2. **限制测试次数**
   - 使用固定的测试图片集
   - 不要频繁上传新图片

3. **监控使用量**
   - 每日检查API使用统计
   - 设置消费告警($5, $10, $20)

### 生产环境:

1. **启用Redis缓存** (已实现)
2. **PostgreSQL去重** (已实现)
3. **优先使用OpenAI** (成本更低)
4. **监控AI调用日志** (`ai_service_logs`表)

---

## 📞 获取帮助

如果遇到问题:

1. **API Key无效**:
   - 检查key格式是否正确(sk-proj-... 或 sk-ant-...)
   - 确认账户已充值
   - 在平台上重新生成key

2. **API调用失败**:
   - 检查网络连接
   - 查看后端日志: `uvicorn app.main:app --reload`
   - 检查API使用限额是否达到上限

3. **其他问题**:
   - 查看详细日志: `backend/logs/`
   - 检查 `ai_service_logs` 表的错误记录

---

**准备好API keys后,告诉我,我会帮你完成最后的验收测试!** ✅
