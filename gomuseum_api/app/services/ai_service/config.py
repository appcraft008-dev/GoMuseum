"""
AI服务统一配置管理

提供类型安全、环境相关的配置管理机制
"""

from pydantic import BaseModel, Field, field_validator
from typing import Dict, Any, Optional, List
from enum import Enum
import os


class ProviderType(str, Enum):
    """AI提供商类型"""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"
    AZURE = "azure"
    LOCAL = "local"


class ModelStrategy(str, Enum):
    """模型选择策略"""
    COST = "cost"
    ACCURACY = "accuracy"  
    SPEED = "speed"
    BALANCED = "balanced"


class CircuitBreakerConfig(BaseModel):
    """熔断器配置"""
    failure_threshold: int = Field(default=5, ge=1, le=100)
    recovery_timeout: int = Field(default=300, ge=10, le=3600)  # 5分钟
    half_open_max_calls: int = Field(default=3, ge=1, le=10)
    success_threshold: int = Field(default=2, ge=1, le=10)
    
    @field_validator('recovery_timeout')
    @classmethod
    def validate_recovery_timeout(cls, v, info):
        """验证恢复超时时间合理性"""
        if v < 10:
            raise ValueError("恢复超时时间不能少于10秒")
        return v


class RetryConfig(BaseModel):
    """重试配置"""
    max_attempts: int = Field(default=3, ge=1, le=10)
    base_delay: float = Field(default=1.0, ge=0.1, le=10.0)
    max_delay: float = Field(default=30.0, ge=1.0, le=300.0)
    exponential_base: float = Field(default=2.0, ge=1.1, le=5.0)
    jitter: bool = Field(default=True)
    
    @field_validator('max_delay')
    @classmethod
    def validate_max_delay(cls, v, info):
        """确保最大延迟大于基础延迟"""
        base_delay = info.data.get('base_delay', 1.0)
        if v <= base_delay:
            raise ValueError("最大延迟必须大于基础延迟")
        return v


class RateLimitConfig(BaseModel):
    """限流配置"""
    requests_per_minute: int = Field(default=100, ge=1, le=10000)
    burst_allowance: int = Field(default=10, ge=1, le=100)
    
    @field_validator('burst_allowance')
    @classmethod
    def validate_burst_allowance(cls, v, info):
        """确保突发容量合理"""
        rpm = info.data.get('requests_per_minute', 100)
        if v > rpm / 2:
            raise ValueError("突发容量不应超过每分钟请求数的一半")
        return v


class ModelConfig(BaseModel):
    """单个模型配置"""
    model_name: str = Field(..., min_length=1)
    provider: ProviderType
    api_key: str = Field(..., min_length=10)
    base_url: Optional[str] = None
    temperature: float = Field(default=0.3, ge=0.0, le=2.0)
    max_tokens: int = Field(default=500, ge=1, le=4096)
    timeout: int = Field(default=30, ge=5, le=300)
    
    # 成本和性能元数据
    cost_per_1k_tokens: float = Field(default=0.01, ge=0.0)
    accuracy_score: float = Field(default=0.8, ge=0.0, le=1.0)
    avg_response_time: float = Field(default=2.0, ge=0.1, le=60.0)
    
    # 模型能力标记
    supports_vision: bool = Field(default=True)
    supports_chinese: bool = Field(default=True)
    max_image_size: int = Field(default=10*1024*1024)  # 10MB
    
    @field_validator('api_key')
    @classmethod
    def validate_api_key(cls, v):
        """验证API密钥格式和安全性"""
        if not v or v == "":
            raise ValueError("API密钥不能为空")
        
        # 检查最小长度
        if len(v) < 32:
            raise ValueError("API密钥长度不足，最少需要32个字符")
        
        # 检查格式（基于主要AI提供商的密钥格式）
        valid_prefixes = ['sk-', 'claude-', 'gcp-', 'azure-']
        if not any(v.startswith(prefix) for prefix in valid_prefixes):
            # 允许无前缀但长度足够的密钥（某些提供商）
            if len(v) < 40:
                raise ValueError("API密钥格式不正确或长度不足")
        
        # 检查是否包含明显的测试/示例密钥
        test_indicators = ['test', 'demo', 'example', 'sample', '123456', 'abcdef']
        v_lower = v.lower()
        if any(indicator in v_lower for indicator in test_indicators):
            raise ValueError("检测到测试密钥，请使用真实的API密钥")
        
        # 检查密钥复杂度（避免过于简单的密钥）
        if len(set(v)) < 16:  # 至少16个不同字符
            raise ValueError("API密钥复杂度不足")
        
        return v


class AIServiceConfig(BaseModel):
    """AI服务完整配置"""
    
    # 模型配置
    models: Dict[str, ModelConfig] = Field(default_factory=dict)
    default_strategy: ModelStrategy = Field(default=ModelStrategy.BALANCED)
    
    # 可靠性配置
    circuit_breaker: CircuitBreakerConfig = Field(default_factory=CircuitBreakerConfig)
    retry: RetryConfig = Field(default_factory=RetryConfig)
    rate_limit: RateLimitConfig = Field(default_factory=RateLimitConfig)
    
    # 健康检查配置
    health_check_interval: int = Field(default=60, ge=10, le=3600)  # 秒
    health_check_timeout: int = Field(default=10, ge=1, le=60)     # 秒
    
    # 缓存配置
    cache_enabled: bool = Field(default=True)
    cache_ttl: int = Field(default=3600, ge=60, le=86400)  # 1小时
    
    # 监控配置
    metrics_enabled: bool = Field(default=True)
    logging_level: str = Field(default="INFO")
    enable_detailed_logging: bool = Field(default=False)
    
    # 业务约束
    max_concurrent_requests: int = Field(default=10, ge=1, le=100)
    request_timeout: int = Field(default=30, ge=5, le=300)
    max_image_size: int = Field(default=10*1024*1024, ge=1024*1024)  # 最小1MB
    
    def get_model_config(self, model_name: str) -> Optional[ModelConfig]:
        """获取指定模型的配置"""
        return self.models.get(model_name)
    
    def get_models_by_provider(self, provider: ProviderType) -> List[ModelConfig]:
        """获取指定提供商的所有模型"""
        return [config for config in self.models.values() 
                if config.provider == provider]
    
    def get_available_models(self) -> List[str]:
        """获取所有可用模型名称"""
        return list(self.models.keys())
    
    def add_model(self, model_config: ModelConfig):
        """添加模型配置"""
        self.models[model_config.model_name] = model_config
    
    def remove_model(self, model_name: str) -> bool:
        """移除模型配置"""
        if model_name in self.models:
            del self.models[model_name]
            return True
        return False
    
    def validate_model_availability(self) -> List[str]:
        """验证模型可用性，返回错误信息列表"""
        errors = []
        
        if not self.models:
            errors.append("没有配置任何AI模型")
            return errors
        
        for model_name, config in self.models.items():
            # 检查API密钥
            if not config.api_key or config.api_key == "":
                errors.append(f"模型 {model_name} 缺少API密钥")
            
            # 检查提供商特定配置
            if config.provider == ProviderType.OPENAI:
                if not config.model_name.startswith(("gpt-", "davinci-")):
                    errors.append(f"OpenAI模型名称 {config.model_name} 格式可能不正确")
            
            elif config.provider == ProviderType.ANTHROPIC:
                if not config.model_name.startswith("claude-"):
                    errors.append(f"Anthropic模型名称 {config.model_name} 格式可能不正确")
        
        return errors


class AIServiceConfigFactory:
    """AI服务配置工厂"""
    
    @staticmethod
    def create_default_config() -> AIServiceConfig:
        """创建默认配置"""
        config = AIServiceConfig()
        
        # 添加OpenAI模型
        if os.getenv("OPENAI_API_KEY"):
            config.add_model(ModelConfig(
                model_name="gpt-4o-mini",
                provider=ProviderType.OPENAI,
                api_key=os.getenv("OPENAI_API_KEY", ""),
                temperature=0.3,
                max_tokens=500,
                cost_per_1k_tokens=0.0015,
                accuracy_score=0.85,
                avg_response_time=2.0
            ))
            
            config.add_model(ModelConfig(
                model_name="gpt-4-vision-preview",
                provider=ProviderType.OPENAI,
                api_key=os.getenv("OPENAI_API_KEY", ""),
                temperature=0.3,
                max_tokens=500,
                cost_per_1k_tokens=0.01,
                accuracy_score=0.95,
                avg_response_time=3.5
            ))
        
        # 添加Anthropic模型  
        if os.getenv("ANTHROPIC_API_KEY"):
            config.add_model(ModelConfig(
                model_name="claude-3-sonnet-20240229",
                provider=ProviderType.ANTHROPIC,
                api_key=os.getenv("ANTHROPIC_API_KEY", ""),
                temperature=0.3,
                max_tokens=500,
                cost_per_1k_tokens=0.003,
                accuracy_score=0.90,
                avg_response_time=2.5
            ))
        
        return config
    
    @staticmethod
    def create_development_config() -> AIServiceConfig:
        """创建开发环境配置"""
        config = AIServiceConfigFactory.create_default_config()
        
        # 开发环境特定设置
        config.circuit_breaker.failure_threshold = 2
        config.circuit_breaker.recovery_timeout = 30
        config.retry.max_attempts = 2
        config.rate_limit.requests_per_minute = 30
        config.enable_detailed_logging = True
        
        return config
    
    @staticmethod
    def create_production_config() -> AIServiceConfig:
        """创建生产环境配置"""
        config = AIServiceConfigFactory.create_default_config()
        
        # 生产环境特定设置
        config.circuit_breaker.failure_threshold = 5
        config.circuit_breaker.recovery_timeout = 300
        config.retry.max_attempts = 3
        config.rate_limit.requests_per_minute = 100
        config.max_concurrent_requests = 20
        config.enable_detailed_logging = False
        
        return config
    
    @staticmethod
    def create_from_env() -> AIServiceConfig:
        """从环境变量创建配置"""
        env = os.getenv("ENVIRONMENT", "development").lower()
        
        if env == "production":
            return AIServiceConfigFactory.create_production_config()
        else:
            return AIServiceConfigFactory.create_development_config()


# 全局配置实例
_ai_config: Optional[AIServiceConfig] = None


def get_ai_config() -> AIServiceConfig:
    """获取AI服务配置实例"""
    global _ai_config
    if _ai_config is None:
        _ai_config = AIServiceConfigFactory.create_from_env()
    return _ai_config


def reload_ai_config():
    """重新加载AI配置"""
    global _ai_config
    _ai_config = None
    return get_ai_config()


def update_ai_config(new_config: AIServiceConfig):
    """更新AI配置"""
    global _ai_config
    _ai_config = new_config