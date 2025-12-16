"""
Structured Logging Configuration for Semptify.

Provides JSON-formatted logs for production (log aggregation systems)
and human-readable logs for development.
"""

import logging
import sys
import json
from datetime import datetime, timezone
from typing import Any


class JSONFormatter(logging.Formatter):
    """
    JSON log formatter for production environments.
    Compatible with ELK Stack, CloudWatch, Datadog, etc.
    """
    
    def __init__(self, include_extras: bool = True):
        super().__init__()
        self.include_extras = include_extras
    
    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
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
        
        # Add extra fields from record
        if self.include_extras:
            # Standard extra fields we add
            for key in ["request_id", "user_id", "path", "method", "status_code", 
                       "duration_ms", "error_code", "client_ip"]:
                if hasattr(record, key):
                    log_data[key] = getattr(record, key)
            
            # Any other extra fields
            for key, value in record.__dict__.items():
                if key not in ["name", "msg", "args", "created", "filename", 
                              "funcName", "levelname", "levelno", "lineno",
                              "module", "msecs", "pathname", "process",
                              "processName", "relativeCreated", "stack_info",
                              "exc_info", "exc_text", "thread", "threadName",
                              "message", "taskName"]:
                    if not key.startswith("_"):
                        log_data[key] = value
        
        return json.dumps(log_data, default=str)


class ColoredFormatter(logging.Formatter):
    """
    Colored log formatter for development.
    Makes logs easier to read in terminal.
    """
    
    # ANSI color codes
    COLORS = {
        "DEBUG": "\033[36m",     # Cyan
        "INFO": "\033[32m",      # Green
        "WARNING": "\033[33m",   # Yellow
        "ERROR": "\033[31m",     # Red
        "CRITICAL": "\033[35m",  # Magenta
    }
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    
    def format(self, record: logging.LogRecord) -> str:
        # Get color for level
        color = self.COLORS.get(record.levelname, "")
        
        # Format timestamp
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        # Build log message
        level_str = f"{color}{record.levelname:8}{self.RESET}"
        name_str = f"{self.DIM}{record.name}{self.RESET}"
        
        message = f"{self.DIM}{timestamp}{self.RESET} {level_str} {name_str} - {record.getMessage()}"
        
        # Add exception if present
        if record.exc_info:
            message += f"\n{self.formatException(record.exc_info)}"
        
        return message


def setup_logging(
    level: str = "INFO",
    json_format: bool = False,
    log_file: str | None = None,
) -> None:
    """
    Configure application logging.
    
    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        json_format: Use JSON formatting (for production)
        log_file: Optional file path for log output
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper()))
    
    # Remove existing handlers
    root_logger.handlers.clear()
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, level.upper()))
    
    if json_format:
        console_handler.setFormatter(JSONFormatter())
    else:
        console_handler.setFormatter(ColoredFormatter())
    
    root_logger.addHandler(console_handler)
    
    # File handler (if specified)
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(getattr(logging, level.upper()))
        # Always use JSON for file logs
        file_handler.setFormatter(JSONFormatter())
        root_logger.addHandler(file_handler)
    
    # Reduce noise from third-party libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance.
    
    Usage:
        from app.core.logging_config import get_logger
        logger = get_logger(__name__)
        logger.info("Something happened", extra={"user_id": "123"})
    """
    return logging.getLogger(name)


# Context manager for adding request context to logs
class LogContext:
    """
    Context manager for adding contextual information to logs.
    
    Usage:
        with LogContext(request_id="abc123", user_id="user1"):
            logger.info("Processing request")  # Will include request_id and user_id
    """
    
    _context: dict[str, Any] = {}
    
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.old_values = {}
    
    def __enter__(self):
        for key, value in self.kwargs.items():
            self.old_values[key] = LogContext._context.get(key)
            LogContext._context[key] = value
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        for key, old_value in self.old_values.items():
            if old_value is None:
                LogContext._context.pop(key, None)
            else:
                LogContext._context[key] = old_value
    
    @classmethod
    def get_context(cls) -> dict[str, Any]:
        return cls._context.copy()
