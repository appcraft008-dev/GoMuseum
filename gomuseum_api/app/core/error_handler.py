"""
安全的错误处理和日志脱敏工具
"""

import logging
import re
import uuid
from typing import Any, Dict, Optional
from fastapi import HTTPException


class SecureErrorHandler:
    """安全的错误处理器"""
    
    def __init__(self, logger_name: str = __name__):
        self.logger = logging.getLogger(logger_name)
        
        # 敏感信息模式（需要脱敏的内容）
        self.sensitive_patterns = [
            (r'sk-[a-zA-Z0-9]{32,}', '[API_KEY_REDACTED]'),
            (r'claude-[a-zA-Z0-9]{32,}', '[API_KEY_REDACTED]'),
            (r'Bearer [a-zA-Z0-9+/=]{20,}', '[TOKEN_REDACTED]'),
            (r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '[EMAIL_REDACTED]'),
            (r'\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b', '[CARD_REDACTED]'),
            (r'"password"\s*:\s*"[^"]*"', '"password": "[REDACTED]"'),
            (r'"api_key"\s*:\s*"[^"]*"', '"api_key": "[REDACTED]"'),
        ]
    
    def sanitize_message(self, message: str) -> str:
        """脱敏敏感信息"""
        sanitized = message
        for pattern, replacement in self.sensitive_patterns:
            sanitized = re.sub(pattern, replacement, sanitized, flags=re.IGNORECASE)
        return sanitized
    
    def generate_error_id(self) -> str:
        """生成错误追踪ID"""
        return str(uuid.uuid4())[:8]
    
    def log_error_securely(
        self, 
        error: Exception, 
        context: Optional[Dict[str, Any]] = None,
        user_id: Optional[str] = None,
        request_id: Optional[str] = None
    ) -> str:
        """安全地记录错误信息"""
        error_id = self.generate_error_id()
        
        # 构建日志上下文
        log_context = {
            "error_id": error_id,
            "error_type": type(error).__name__,
            "user_id": user_id,
            "request_id": request_id,
        }
        
        if context:
            # 脱敏上下文信息
            sanitized_context = {}
            for key, value in context.items():
                if isinstance(value, str):
                    sanitized_context[key] = self.sanitize_message(value)
                else:
                    sanitized_context[key] = value
            log_context["context"] = sanitized_context
        
        # 脱敏错误消息
        sanitized_error_msg = self.sanitize_message(str(error))
        
        # 记录完整错误（用于内部调试）
        self.logger.error(
            f"Error {error_id}: {sanitized_error_msg}",
            extra=log_context,
            exc_info=True
        )
        
        return error_id
    
    def create_user_safe_error(
        self, 
        error: Exception,
        default_message: str = "系统暂时不可用，请稍后重试",
        status_code: int = 500,
        context: Optional[Dict[str, Any]] = None,
        user_id: Optional[str] = None,
        request_id: Optional[str] = None
    ) -> HTTPException:
        """创建用户安全的错误响应"""
        
        error_id = self.log_error_securely(
            error=error,
            context=context,
            user_id=user_id,
            request_id=request_id
        )
        
        # 根据错误类型决定是否暴露详细信息
        if isinstance(error, (ValueError, TypeError)) and status_code < 500:
            # 客户端错误，可以暴露脱敏后的消息
            user_message = self.sanitize_message(str(error))
        else:
            # 服务器错误，使用通用消息
            user_message = default_message
        
        return HTTPException(
            status_code=status_code,
            detail={
                "error": user_message,
                "error_id": error_id,
                "timestamp": None  # 将由中间件添加
            }
        )


# 创建全局实例
secure_error_handler = SecureErrorHandler("app.error_handler")


def handle_api_error(
    error: Exception,
    default_message: str = "系统暂时不可用，请稍后重试",
    status_code: int = 500,
    context: Optional[Dict[str, Any]] = None,
    user_id: Optional[str] = None,
    request_id: Optional[str] = None
) -> HTTPException:
    """便捷的API错误处理函数"""
    return secure_error_handler.create_user_safe_error(
        error=error,
        default_message=default_message,
        status_code=status_code,
        context=context,
        user_id=user_id,
        request_id=request_id
    )