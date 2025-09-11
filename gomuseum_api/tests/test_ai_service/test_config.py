"""
测试AI服务配置管理
"""

import pytest
import os
from unittest.mock import patch
from pydantic import ValidationError

from app.services.ai_service.config import (
    AIServiceConfig, ModelConfig, CircuitBreakerConfig, RetryConfig, RateLimitConfig,
    ProviderType, ModelStrategy, AIServiceConfigFactory,
    get_ai_config, reload_ai_config, update_ai_config
)


class TestModelConfig:
    """测试模型配置"""
    
    def test_valid_model_config(self):
        """测试有效的模型配置"""
        config = ModelConfig(
            model_name="gpt-4o-mini",
            provider=ProviderType.OPENAI,
            api_key="sk-test-key-12345678901234567890",
            temperature=0.3,
            max_tokens=500
        )
        
        assert config.model_name == "gpt-4o-mini"
        assert config.provider == ProviderType.OPENAI
        assert config.temperature == 0.3
        assert config.supports_vision is True
        assert config.supports_chinese is True
    
    def test_invalid_api_key(self):
        """测试无效API密钥"""
        with pytest.raises(ValidationError) as exc_info:
            ModelConfig(
                model_name="gpt-4o-mini",
                provider=ProviderType.OPENAI,
                api_key="",  # 空密钥
                temperature=0.3
            )
        
        assert "at least 10 characters" in str(exc_info.value)
    
    def test_invalid_temperature(self):
        """测试无效温度值"""
        with pytest.raises(ValidationError):
            ModelConfig(
                model_name="gpt-4o-mini", 
                provider=ProviderType.OPENAI,
                api_key="sk-test-key-12345678901234567890",
                temperature=3.0  # 超出范围
            )
    
    def test_invalid_max_tokens(self):
        """测试无效token数量"""
        with pytest.raises(ValidationError):
            ModelConfig(
                model_name="gpt-4o-mini",
                provider=ProviderType.OPENAI,
                api_key="sk-test-key-12345678901234567890",
                max_tokens=0  # 无效值
            )


class TestCircuitBreakerConfig:
    """测试熔断器配置"""
    
    def test_valid_circuit_breaker_config(self):
        """测试有效熔断器配置"""
        config = CircuitBreakerConfig(
            failure_threshold=5,
            recovery_timeout=300,
            half_open_max_calls=3,
            success_threshold=2
        )
        
        assert config.failure_threshold == 5
        assert config.recovery_timeout == 300
    
    def test_invalid_recovery_timeout(self):
        """测试无效恢复超时"""
        with pytest.raises(ValidationError) as exc_info:
            CircuitBreakerConfig(
                failure_threshold=5,
                recovery_timeout=5  # 小于最小值
            )
        
        assert "greater than or equal to 10" in str(exc_info.value)
    
    def test_failure_threshold_bounds(self):
        """测试失败阈值边界"""
        with pytest.raises(ValidationError):
            CircuitBreakerConfig(failure_threshold=0)  # 小于最小值
        
        with pytest.raises(ValidationError):
            CircuitBreakerConfig(failure_threshold=101)  # 大于最大值


class TestRetryConfig:
    """测试重试配置"""
    
    def test_valid_retry_config(self):
        """测试有效重试配置"""
        config = RetryConfig(
            max_attempts=3,
            base_delay=1.0,
            max_delay=30.0,
            exponential_base=2.0,
            jitter=True
        )
        
        assert config.max_attempts == 3
        assert config.base_delay == 1.0
        assert config.max_delay == 30.0
        assert config.jitter is True
    
    def test_invalid_max_delay(self):
        """测试无效最大延迟"""
        with pytest.raises(ValidationError) as exc_info:
            RetryConfig(
                base_delay=10.0,
                max_delay=5.0  # 小于基础延迟
            )
        
        assert "最大延迟必须大于基础延迟" in str(exc_info.value)


class TestRateLimitConfig:
    """测试限流配置"""
    
    def test_valid_rate_limit_config(self):
        """测试有效限流配置"""
        config = RateLimitConfig(
            requests_per_minute=100,
            burst_allowance=10
        )
        
        assert config.requests_per_minute == 100
        assert config.burst_allowance == 10
    
    def test_invalid_burst_allowance(self):
        """测试无效突发容量"""
        with pytest.raises(ValidationError) as exc_info:
            RateLimitConfig(
                requests_per_minute=100,
                burst_allowance=60  # 超过一半
            )
        
        assert "突发容量不应超过每分钟请求数的一半" in str(exc_info.value)


class TestAIServiceConfig:
    """测试AI服务配置"""
    
    def test_empty_config(self):
        """测试空配置"""
        config = AIServiceConfig()
        
        assert len(config.models) == 0
        assert config.default_strategy == ModelStrategy.BALANCED
        assert config.cache_enabled is True
        assert config.metrics_enabled is True
    
    def test_add_remove_model(self):
        """测试添加和移除模型"""
        config = AIServiceConfig()
        
        model_config = ModelConfig(
            model_name="test-model",
            provider=ProviderType.OPENAI,
            api_key="sk-test-key-12345678901234567890"
        )
        
        # 添加模型
        config.add_model(model_config)
        assert "test-model" in config.models
        assert len(config.get_available_models()) == 1
        
        # 移除模型
        result = config.remove_model("test-model")
        assert result is True
        assert len(config.models) == 0
        
        # 移除不存在的模型
        result = config.remove_model("non-existent")
        assert result is False
    
    def test_get_models_by_provider(self):
        """测试按提供商获取模型"""
        config = AIServiceConfig()
        
        # 添加OpenAI模型
        openai_model = ModelConfig(
            model_name="gpt-4o-mini",
            provider=ProviderType.OPENAI,
            api_key="sk-test-key-12345678901234567890"
        )
        config.add_model(openai_model)
        
        # 添加Anthropic模型
        anthropic_model = ModelConfig(
            model_name="claude-3-sonnet",
            provider=ProviderType.ANTHROPIC,
            api_key="sk-ant-test-key-12345678901234567890"
        )
        config.add_model(anthropic_model)
        
        # 测试按提供商筛选
        openai_models = config.get_models_by_provider(ProviderType.OPENAI)
        assert len(openai_models) == 1
        assert openai_models[0].model_name == "gpt-4o-mini"
        
        anthropic_models = config.get_models_by_provider(ProviderType.ANTHROPIC)
        assert len(anthropic_models) == 1
        assert anthropic_models[0].model_name == "claude-3-sonnet"
    
    def test_validate_model_availability(self):
        """测试模型可用性验证"""
        config = AIServiceConfig()
        
        # 空配置应该有错误
        errors = config.validate_model_availability()
        assert len(errors) > 0
        assert "没有配置任何AI模型" in errors[0]
        
        # 添加一个有效模型但有可疑的名称格式
        valid_model = ModelConfig(
            model_name="suspicious-model-name",  # 不符合OpenAI格式
            provider=ProviderType.OPENAI,
            api_key="sk-test-key-12345678901234567890"  # 有效密钥
        )
        config.add_model(valid_model)
        
        errors = config.validate_model_availability()
        assert len(errors) > 0
        assert any("格式可能不正确" in error for error in errors)


class TestAIServiceConfigFactory:
    """测试AI服务配置工厂"""
    
    def test_create_default_config(self):
        """测试创建默认配置"""
        config = AIServiceConfigFactory.create_default_config()
        
        assert isinstance(config, AIServiceConfig)
        assert config.default_strategy == ModelStrategy.BALANCED
        assert config.circuit_breaker.failure_threshold >= 1
        assert config.retry.max_attempts >= 1
    
    @patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test-key-12345678901234567890"})
    def test_create_with_openai_key(self):
        """测试带OpenAI密钥的配置创建"""
        config = AIServiceConfigFactory.create_default_config()
        
        openai_models = config.get_models_by_provider(ProviderType.OPENAI)
        assert len(openai_models) > 0
        
        # 验证模型配置
        gpt4_mini = config.get_model_config("gpt-4o-mini")
        assert gpt4_mini is not None
        assert gpt4_mini.provider == ProviderType.OPENAI
        assert gpt4_mini.api_key == "sk-test-key-12345678901234567890"
    
    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-test-key"})
    def test_create_with_anthropic_key(self):
        """测试带Anthropic密钥的配置创建"""
        config = AIServiceConfigFactory.create_default_config()
        
        anthropic_models = config.get_models_by_provider(ProviderType.ANTHROPIC)
        assert len(anthropic_models) > 0
        
        claude_model = config.get_model_config("claude-3-sonnet-20240229")
        assert claude_model is not None
        assert claude_model.provider == ProviderType.ANTHROPIC
    
    def test_create_development_config(self):
        """测试开发环境配置"""
        config = AIServiceConfigFactory.create_development_config()
        
        # 开发环境应该有更严格的限制
        assert config.circuit_breaker.failure_threshold <= 5
        assert config.retry.max_attempts <= 3
        assert config.enable_detailed_logging is True
    
    def test_create_production_config(self):
        """测试生产环境配置"""
        config = AIServiceConfigFactory.create_production_config()
        
        # 生产环境应该有更宽松的限制
        assert config.circuit_breaker.failure_threshold >= 3
        assert config.max_concurrent_requests >= 10
        assert config.enable_detailed_logging is False
    
    @patch.dict(os.environ, {"ENVIRONMENT": "production"})
    def test_create_from_env_production(self):
        """测试从环境变量创建生产配置"""
        config = AIServiceConfigFactory.create_from_env()
        
        # 应该是生产环境配置
        assert config.enable_detailed_logging is False
        assert config.max_concurrent_requests >= 10
    
    @patch.dict(os.environ, {"ENVIRONMENT": "development"})
    def test_create_from_env_development(self):
        """测试从环境变量创建开发配置"""
        config = AIServiceConfigFactory.create_from_env()
        
        # 应该是开发环境配置
        assert config.enable_detailed_logging is True


class TestGlobalConfigManagement:
    """测试全局配置管理"""
    
    def test_get_ai_config(self):
        """测试获取AI配置"""
        config = get_ai_config()
        assert isinstance(config, AIServiceConfig)
    
    def test_reload_ai_config(self):
        """测试重新加载配置"""
        # 获取初始配置
        config1 = get_ai_config()
        
        # 重新加载
        config2 = reload_ai_config()
        
        # 应该是新的实例
        assert isinstance(config2, AIServiceConfig)
    
    def test_update_ai_config(self):
        """测试更新配置"""
        # 创建新配置
        new_config = AIServiceConfig()
        new_config.default_strategy = ModelStrategy.COST
        
        # 更新配置
        update_ai_config(new_config)
        
        # 验证更新
        current_config = get_ai_config()
        assert current_config.default_strategy == ModelStrategy.COST