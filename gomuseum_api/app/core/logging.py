import logging
import logging.config
import json
from datetime import datetime
from typing import Any, Dict
from .config import settings


class JSONFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging"""
    
    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        # Add extra fields
        if hasattr(record, "user_id"):
            log_data["user_id"] = record.user_id
        if hasattr(record, "request_id"):
            log_data["request_id"] = record.request_id
        if hasattr(record, "duration"):
            log_data["duration"] = record.duration
            
        return json.dumps(log_data, ensure_ascii=False)


def setup_logging():
    """Setup application logging configuration"""
    import os
    
    # Create logs directory if it doesn't exist
    log_dir = "./logs"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir, exist_ok=True)
    
    handlers = {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "json" if settings.environment == "production" else "standard",
            "stream": "ext://sys.stdout",
        }
    }
    
    # Add file handler only if logs directory exists
    if os.path.exists(log_dir):
        handlers["file"] = {
            "class": "logging.handlers.RotatingFileHandler",
            "formatter": "json",
            "filename": f"{log_dir}/gomuseum.log",
            "maxBytes": 10485760,  # 10MB
            "backupCount": 5,
        }
        app_handlers = ["console", "file"]
    else:
        app_handlers = ["console"]
    
    config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "json": {
                "()": JSONFormatter,
            },
            "standard": {
                "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
            },
        },
        "handlers": handlers,
        "loggers": {
            "app": {
                "handlers": app_handlers,
                "level": "INFO" if settings.environment == "production" else "DEBUG",
                "propagate": False,
            },
            "uvicorn": {
                "handlers": ["console"],
                "level": "INFO",
                "propagate": False,
            },
        },
        "root": {
            "handlers": ["console"],
            "level": "WARNING",
        },
    }
    
    logging.config.dictConfig(config)


def get_logger(name: str) -> logging.Logger:
    """Get logger instance with proper configuration"""
    return logging.getLogger(f"app.{name}")


# Logging utilities
def log_api_call(logger: logging.Logger, method: str, endpoint: str, user_id: str = None, duration: float = None):
    """Log API call with structured data"""
    extra = {"user_id": user_id, "duration": duration} if user_id or duration else {}
    logger.info(f"{method} {endpoint}", extra=extra)


def log_error(logger: logging.Logger, error: Exception, context: Dict[str, Any] = None):
    """Log error with context information"""
    extra = context or {}
    logger.error(f"Error: {str(error)}", exc_info=True, extra=extra)