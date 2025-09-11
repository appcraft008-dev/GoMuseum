"""
AI Service Module for GoMuseum

This module provides AI-powered artwork recognition capabilities using
multiple model providers with a unified adapter interface.

Features:
- Multi-provider support (OpenAI, Anthropic, etc.)
- Smart model selection based on cost, accuracy, and speed
- Fallback mechanisms for reliability
- Cost tracking and budget management
"""

from .base_adapter import VisionModelAdapter
from .exceptions import (
    AIServiceError,
    ModelNotAvailableError,
    InsufficientQuotaError,
    ImageProcessingError
)

__all__ = [
    'VisionModelAdapter',
    'AIServiceError',
    'ModelNotAvailableError', 
    'InsufficientQuotaError',
    'ImageProcessingError'
]

__version__ = "0.1.0"