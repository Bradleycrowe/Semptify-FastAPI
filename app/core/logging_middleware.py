"""
Request Logging Middleware for Semptify.

Provides structured request/response logging with timing metrics.
Supports JSON format for log aggregation systems.
"""

import logging
import time
import uuid
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("semptify.requests")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware for logging HTTP requests and responses.
    
    Features:
    - Request ID tracking
    - Response timing
    - Structured logging format
    - Configurable path exclusions
    """
    
    # Paths to exclude from logging (health checks, static files)
    EXCLUDE_PATHS = {
        "/healthz",
        "/readyz",
        "/health",
        "/metrics",
        "/favicon.ico",
    }
    
    # Paths that start with these prefixes are excluded
    EXCLUDE_PREFIXES = (
        "/static/",
        "/_next/",
        "/assets/",
    )
    
    def __init__(self, app, log_body: bool = False, log_headers: bool = False):
        super().__init__(app)
        self.log_body = log_body
        self.log_headers = log_headers
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip logging for excluded paths
        path = request.url.path
        if path in self.EXCLUDE_PATHS or path.startswith(self.EXCLUDE_PREFIXES):
            return await call_next(request)
        
        # Generate or extract request ID
        request_id = request.headers.get("X-Request-Id", str(uuid.uuid4())[:8])
        
        # Record start time
        start_time = time.perf_counter()
        
        # Log request
        log_data = {
            "request_id": request_id,
            "method": request.method,
            "path": path,
            "query": str(request.query_params) if request.query_params else None,
            "client_ip": self._get_client_ip(request),
            "user_agent": request.headers.get("User-Agent", "")[:100],
        }
        
        if self.log_headers:
            log_data["headers"] = dict(request.headers)
        
        logger.info("Request started: %s %s", request.method, path, extra=log_data)
        
        # Process request
        try:
            response = await call_next(request)
            
            # Calculate duration
            duration_ms = (time.perf_counter() - start_time) * 1000
            
            # Log response
            log_data.update({
                "status_code": response.status_code,
                "duration_ms": round(duration_ms, 2),
            })
            
            # Determine log level based on status
            if response.status_code >= 500:
                logger.error(
                    "Request completed: %s %s -> %d (%.2fms)",
                    request.method, path, response.status_code, duration_ms,
                    extra=log_data
                )
            elif response.status_code >= 400:
                logger.warning(
                    "Request completed: %s %s -> %d (%.2fms)",
                    request.method, path, response.status_code, duration_ms,
                    extra=log_data
                )
            else:
                logger.info(
                    "Request completed: %s %s -> %d (%.2fms)",
                    request.method, path, response.status_code, duration_ms,
                    extra=log_data
                )
            
            # Add request ID to response headers
            response.headers["X-Request-Id"] = request_id
            response.headers["X-Response-Time"] = f"{duration_ms:.2f}ms"
            
            return response
            
        except Exception as e:
            # Log exception
            duration_ms = (time.perf_counter() - start_time) * 1000
            log_data.update({
                "status_code": 500,
                "duration_ms": round(duration_ms, 2),
                "error": str(e),
            })
            logger.exception(
                "Request failed: %s %s -> 500 (%.2fms) - %s",
                request.method, path, duration_ms, str(e),
                extra=log_data
            )
            raise
    
    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP, respecting proxy headers."""
        # Check X-Forwarded-For (set by reverse proxies)
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        
        # Check X-Real-IP (nginx)
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        
        # Fall back to direct connection
        if request.client:
            return request.client.host
        
        return "unknown"


class SlowRequestMiddleware(BaseHTTPMiddleware):
    """
    Middleware to detect and log slow requests.
    """
    
    def __init__(self, app, threshold_ms: float = 1000.0):
        super().__init__(app)
        self.threshold_ms = threshold_ms
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start_time = time.perf_counter()
        
        response = await call_next(request)
        
        duration_ms = (time.perf_counter() - start_time) * 1000
        
        if duration_ms > self.threshold_ms:
            logger.warning(
                "Slow request detected: %s %s took %.2fms (threshold: %.2fms)",
                request.method,
                request.url.path,
                duration_ms,
                self.threshold_ms,
                extra={
                    "slow_request": True,
                    "duration_ms": duration_ms,
                    "threshold_ms": self.threshold_ms,
                    "path": request.url.path,
                    "method": request.method,
                }
            )
        
        return response
