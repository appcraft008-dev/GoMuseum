"""
AI Service Exceptions

定义AI服务相关的异常类，提供统一的错误处理机制
"""


class AIServiceError(Exception):
    """AI服务基础异常类"""
    
    def __init__(self, message: str, error_code: str = None, details: dict = None):
        super().__init__(message)
        self.message = message
        self.error_code = error_code or "AI_SERVICE_ERROR"
        self.details = details or {}
    
    def to_dict(self) -> dict:
        """转换为字典格式，用于API响应"""
        return {
            "error": self.error_code,
            "message": self.message,
            "details": self.details
        }


class ModelNotAvailableError(AIServiceError):
    """模型不可用错误"""
    
    def __init__(self, model_name: str, reason: str = None):
        message = f"Model '{model_name}' is not available"
        if reason:
            message += f": {reason}"
        
        super().__init__(
            message=message,
            error_code="MODEL_NOT_AVAILABLE",
            details={"model_name": model_name, "reason": reason}
        )
        self.model_name = model_name
        self.reason = reason


class InsufficientQuotaError(AIServiceError):
    """配额不足错误"""
    
    def __init__(self, quota_type: str = "api_calls", current: int = 0, limit: int = 0):
        message = f"Insufficient quota for {quota_type}: {current}/{limit}"
        
        super().__init__(
            message=message,
            error_code="INSUFFICIENT_QUOTA",
            details={
                "quota_type": quota_type,
                "current": current,
                "limit": limit
            }
        )
        self.quota_type = quota_type
        self.current = current
        self.limit = limit


class ImageProcessingError(AIServiceError):
    """图像处理错误"""
    
    def __init__(self, message: str, image_info: dict = None):
        super().__init__(
            message=message,
            error_code="IMAGE_PROCESSING_ERROR",
            details={"image_info": image_info or {}}
        )
        self.image_info = image_info


class APIError(AIServiceError):
    """外部API调用错误"""
    
    def __init__(self, provider: str, message: str, status_code: int = None):
        full_message = f"{provider} API error: {message}"
        
        super().__init__(
            message=full_message,
            error_code="API_ERROR",
            details={
                "provider": provider,
                "status_code": status_code,
                "original_message": message
            }
        )
        self.provider = provider
        self.status_code = status_code


class TokenLimitExceededError(AIServiceError):
    """Token限制超出错误"""
    
    def __init__(self, requested: int, limit: int, model_name: str = None):
        message = f"Token limit exceeded: requested {requested}, limit {limit}"
        if model_name:
            message += f" for model {model_name}"
        
        super().__init__(
            message=message,
            error_code="TOKEN_LIMIT_EXCEEDED",
            details={
                "requested": requested,
                "limit": limit,
                "model_name": model_name
            }
        )
        self.requested = requested
        self.limit = limit
        self.model_name = model_name


class InvalidImageFormatError(ImageProcessingError):
    """无效图像格式错误"""
    
    def __init__(self, format_detected: str = None, supported_formats: list = None):
        message = f"Invalid image format"
        if format_detected:
            message += f": detected {format_detected}"
        if supported_formats:
            message += f", supported formats: {', '.join(supported_formats)}"
        
        super().__init__(
            message=message,
            image_info={
                "format_detected": format_detected,
                "supported_formats": supported_formats or []
            }
        )
        self.format_detected = format_detected
        self.supported_formats = supported_formats


class ImageTooLargeError(ImageProcessingError):
    """图像过大错误"""
    
    def __init__(self, size_bytes: int, max_size_bytes: int):
        size_mb = size_bytes / (1024 * 1024)
        max_size_mb = max_size_bytes / (1024 * 1024)
        
        message = f"Image too large: {size_mb:.1f}MB (max: {max_size_mb:.1f}MB)"
        
        super().__init__(
            message=message,
            image_info={
                "size_bytes": size_bytes,
                "max_size_bytes": max_size_bytes,
                "size_mb": size_mb,
                "max_size_mb": max_size_mb
            }
        )
        self.size_bytes = size_bytes
        self.max_size_bytes = max_size_bytes