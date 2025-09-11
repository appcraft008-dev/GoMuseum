"""
OpenAI Vision Model Adapter

基于OpenAI GPT-4V的艺术品识别适配器实现
"""

import base64
import json
import time
import asyncio
from typing import Dict, Any, List, Optional
import logging

import openai
from openai import AsyncOpenAI

from .base_adapter import VisionModelAdapter
from .exceptions import (
    AIServiceError,
    APIError,
    TokenLimitExceededError,
    ImageProcessingError
)

logger = logging.getLogger(__name__)


class OpenAIVisionAdapter(VisionModelAdapter):
    """OpenAI GPT-4V 视觉模型适配器"""
    
    provider_name = "openai"
    max_image_size = 20 * 1024 * 1024  # 20MB for OpenAI
    supported_formats = ["jpeg", "jpg", "png", "gif", "webp"]
    
    def __init__(
        self,
        api_key: str,
        model_name: str = "gpt-4-vision-preview",
        temperature: float = 0.3,
        max_tokens: int = 500,
        timeout: float = 30.0,
        **kwargs
    ):
        """
        初始化OpenAI适配器
        
        Args:
            api_key: OpenAI API密钥
            model_name: 模型名称
            temperature: 生成温度
            max_tokens: 最大token数
            timeout: 请求超时时间
        """
        if not api_key or api_key.strip() == "":
            raise ValueError("API key is required")
        
        super().__init__(**kwargs)
        
        self.api_key = api_key
        self.model_name = model_name
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout
        
        # 初始化OpenAI客户端
        self.client = AsyncOpenAI(api_key=api_key)
        
        # 模型特定配置
        self._model_costs = {
            "gpt-5-vision": 0.05,
            "gpt-4-vision-preview": 0.03,
            "gpt-4-turbo-vision": 0.02,
            "gpt-4o": 0.025,
            "gpt-4o-mini": 0.01
        }
        
        self._model_accuracy = {
            "gpt-5-vision": 0.95,
            "gpt-4-vision-preview": 0.90,
            "gpt-4-turbo-vision": 0.85,
            "gpt-4o": 0.88,
            "gpt-4o-mini": 0.80
        }
    
    async def recognize_artwork(
        self, 
        image_bytes: bytes, 
        language: str = "zh", 
        **kwargs
    ) -> Dict[str, Any]:
        """
        使用OpenAI GPT-4V识别艺术品
        
        Args:
            image_bytes: 图像二进制数据
            language: 语言代码 (zh, en, fr, de, es, it)
            **kwargs: 其他参数
            
        Returns:
            Dict: 识别结果
        """
        start_time = time.time()
        
        try:
            # 验证图像
            self._validate_image(image_bytes)
            
            # 编码图像为Base64
            image_base64 = self._encode_image_to_base64(image_bytes)
            
            # 生成提示词
            prompt = self._generate_recognition_prompt(language)
            
            # 调用OpenAI API
            response = await self._call_openai_api(image_base64, prompt)
            
            # 解析响应
            result = self._parse_recognition_response(response, language)
            
            # 计算处理时间和成本
            processing_time = time.time() - start_time
            cost = self.estimate_cost(image_bytes)
            
            # 更新统计信息
            self._update_stats(True, cost, processing_time)
            
            # 完善结果
            result.update({
                "success": True,
                "processing_time": processing_time,
                "model_used": self.model_name,
                "timestamp": time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime()),
                "cost_usd": cost
            })
            
            logger.info(f"OpenAI recognition successful: {processing_time:.2f}s, cost: ${cost:.4f}")
            return result
            
        except Exception as e:
            processing_time = time.time() - start_time
            self._update_stats(False, 0.0, processing_time)
            
            logger.error(f"OpenAI recognition failed: {e}", exc_info=True)
            
            return {
                "success": False,
                "candidates": [],
                "processing_time": processing_time,
                "model_used": self.model_name,
                "timestamp": time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime()),
                "error": str(e),
                "error_type": type(e).__name__
            }
    
    async def health_check(self) -> bool:
        """
        检查OpenAI API健康状态
        
        Returns:
            bool: True if healthy
        """
        try:
            # 发送简单的测试请求
            response = await asyncio.wait_for(
                self.client.chat.completions.create(
                    model="gpt-3.5-turbo",  # 使用更便宜的模型进行健康检查
                    messages=[
                        {"role": "user", "content": "Health check. Reply with 'OK'."}
                    ],
                    max_tokens=5,
                    timeout=10.0
                ),
                timeout=15.0
            )
            
            return response.choices[0].message.content.strip().upper() == "OK"
            
        except Exception as e:
            logger.warning(f"OpenAI health check failed: {e}")
            return False
    
    def get_model_info(self) -> Dict[str, Any]:
        """
        获取OpenAI模型信息
        
        Returns:
            Dict: 模型信息
        """
        return {
            "model_name": self.model_name,
            "provider": self.provider_name,
            "version": "1.0.0",
            "capabilities": [
                "artwork_recognition",
                "visual_analysis", 
                "multilingual_output",
                "confidence_scoring"
            ],
            "pricing": {
                "cost_per_call": self._model_costs.get(self.model_name, 0.03),
                "currency": "USD"
            },
            "limits": {
                "max_image_size": self.max_image_size,
                "max_tokens": self.max_tokens,
                "supported_formats": self.supported_formats
            }
        }
    
    def estimate_cost(self, image_bytes: bytes) -> float:
        """
        估算API调用成本
        
        Args:
            image_bytes: 图像数据
            
        Returns:
            float: 预估成本（美元）
        """
        base_cost = self._model_costs.get(self.model_name, 0.03)
        
        # 根据图像大小调整成本
        image_size_mb = len(image_bytes) / (1024 * 1024)
        size_multiplier = 1.0 + (image_size_mb - 1) * 0.1  # 每MB额外增加10%成本
        
        return base_cost * max(1.0, size_multiplier)
    
    def get_accuracy_score(self) -> float:
        """
        获取模型准确率评分
        
        Returns:
            float: 0.0-1.0之间的准确率评分
        """
        return self._model_accuracy.get(self.model_name, 0.85)
    
    def _encode_image_to_base64(self, image_bytes: bytes) -> str:
        """
        将图像编码为Base64字符串
        
        Args:
            image_bytes: 图像二进制数据
            
        Returns:
            str: Base64编码字符串
        """
        return base64.b64encode(image_bytes).decode('utf-8')
    
    def _generate_recognition_prompt(self, language: str) -> str:
        """
        生成艺术品识别提示词
        
        Args:
            language: 语言代码
            
        Returns:
            str: 提示词
        """
        if language == "zh":
            return """
你是一位专业的艺术史学家。请分析这幅博物馆艺术品图像。

请以JSON格式输出结果：
{
  "artwork_name": "作品确切名称",
  "artist": "艺术家姓名",
  "confidence": 0.0-1.0,
  "visual_features": ["关键视觉特征"],
  "period": "艺术时期/年代",
  "museum_section": "所属展厅"
}

如果图像中有文字标签，请优先参考。要简洁准确。
"""
        else:
            return """
You are an expert art historian. Analyze this museum artwork image.

Output JSON format:
{
  "artwork_name": "exact name",
  "artist": "artist name", 
  "confidence": 0.0-1.0,
  "visual_features": ["key features"],
  "period": "art period/year",
  "museum_section": "location"
}

Prioritize text/labels if visible in image.
Be concise and accurate.
"""
    
    async def _call_openai_api(self, image_base64: str, prompt: str) -> Dict[str, Any]:
        """
        调用OpenAI API
        
        Args:
            image_base64: Base64编码的图像
            prompt: 提示词
            
        Returns:
            Dict: API响应
            
        Raises:
            APIError: API调用失败
            TokenLimitExceededError: Token限制超出
        """
        try:
            # 构建消息
            messages = [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": prompt
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{image_base64}",
                                "detail": "high"
                            }
                        }
                    ]
                }
            ]
            
            # 调用API
            response = await asyncio.wait_for(
                self.client.chat.completions.create(
                    model=self.model_name,
                    messages=messages,
                    max_tokens=self.max_tokens,
                    temperature=self.temperature
                ),
                timeout=self.timeout
            )
            
            return response
            
        except openai.RateLimitError as e:
            raise APIError("openai", f"Rate limit exceeded: {e}", 429)
        except openai.AuthenticationError as e:
            raise APIError("openai", f"Authentication failed: {e}", 401)
        except openai.BadRequestError as e:
            if "token" in str(e).lower():
                raise TokenLimitExceededError(
                    self.max_tokens, 
                    self.max_tokens,
                    self.model_name
                )
            raise APIError("openai", f"Bad request: {e}", 400)
        except asyncio.TimeoutError:
            raise APIError("openai", f"Request timeout after {self.timeout}s", 408)
        except Exception as e:
            raise APIError("openai", f"Unexpected error: {e}")
    
    def _parse_recognition_response(
        self, 
        response: Any, 
        language: str
    ) -> Dict[str, Any]:
        """
        解析OpenAI API响应
        
        Args:
            response: OpenAI API响应
            language: 语言代码
            
        Returns:
            Dict: 解析后的结果
            
        Raises:
            ImageProcessingError: 解析失败
        """
        try:
            # 获取响应内容
            content = response.choices[0].message.content.strip()
            
            # 尝试解析JSON
            try:
                result_data = json.loads(content)
            except json.JSONDecodeError:
                # 如果不是纯JSON，尝试提取JSON部分
                import re
                json_match = re.search(r'\{.*\}', content, re.DOTALL)
                if json_match:
                    result_data = json.loads(json_match.group())
                else:
                    raise ImageProcessingError(f"Could not parse JSON from response: {content}")
            
            # 标准化结果格式
            candidates = []
            
            if result_data:
                candidate = {
                    "artwork_id": f"openai-{hash(result_data.get('artwork_name', 'unknown'))}",
                    "name": result_data.get("artwork_name", "Unknown"),
                    "artist": result_data.get("artist", "Unknown"),
                    "confidence": float(result_data.get("confidence", 0.5)),
                    "period": result_data.get("period", "Unknown"),
                    "museum_section": result_data.get("museum_section", "Unknown"),
                    "visual_features": result_data.get("visual_features", [])
                }
                candidates.append(candidate)
            
            return {"candidates": candidates}
            
        except Exception as e:
            logger.error(f"Failed to parse OpenAI response: {e}")
            raise ImageProcessingError(f"Response parsing failed: {e}")
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """清理资源"""
        if hasattr(self, 'client') and self.client:
            await self.client.close()
    
    def __repr__(self) -> str:
        return f"OpenAIVisionAdapter(model={self.model_name})"