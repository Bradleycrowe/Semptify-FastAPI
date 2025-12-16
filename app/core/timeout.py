"""
Request Timeout Middleware for Semptify.

Prevents requests from running indefinitely and consuming resources.
Returns 504 Gateway Timeout for requests exceeding the timeout.
"""

import asyncio
import logging
from typing import Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class TimeoutMiddleware(BaseHTTPMiddleware):
    """
    Middleware to enforce request timeout.
    
    Usage:
        app.add_middleware(TimeoutMiddleware, timeout=30.0)
    """
    
    # Paths that should have longer or no timeout
    EXTENDED_TIMEOUT_PATHS = {
        "/api/copilot": 120.0,      # AI requests need more time
        "/api/court-packet": 180.0,  # PDF generation is slow
        "/api/research": 90.0,       # Research aggregation
        "/api/extraction": 60.0,     # Document extraction
    }
    
    # Paths excluded from timeout (streaming, websockets)
    EXCLUDED_PATHS = {
        "/ws",           # WebSocket connections
        "/api/stream",   # Streaming responses
    }
    
    def __init__(self, app, timeout: float = 30.0):
        super().__init__(app)
        self.default_timeout = timeout
    
    def _get_timeout(self, path: str) -> float | None:
        """Get timeout for a specific path."""
        # Check excluded paths
        for excluded in self.EXCLUDED_PATHS:
            if path.startswith(excluded):
                return None  # No timeout
        
        # Check extended timeout paths
        for prefix, timeout in self.EXTENDED_TIMEOUT_PATHS.items():
            if path.startswith(prefix):
                return timeout
        
        return self.default_timeout
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        timeout = self._get_timeout(request.url.path)
        
        # No timeout for excluded paths
        if timeout is None:
            return await call_next(request)
        
        try:
            return await asyncio.wait_for(
                call_next(request),
                timeout=timeout
            )
        except asyncio.TimeoutError:
            logger.warning(
                "Request timeout: %s %s (%.1fs)",
                request.method,
                request.url.path,
                timeout,
                extra={
                    "timeout_seconds": timeout,
                    "path": request.url.path,
                    "method": request.method,
                }
            )
            
            return JSONResponse(
                status_code=504,
                content={
                    "error": "gateway_timeout",
                    "message": f"Request timed out after {timeout} seconds",
                    "timeout_seconds": timeout,
                },
                headers={
                    "Retry-After": "30",
                }
            )


class SlowRequestLoggerMiddleware(BaseHTTPMiddleware):
    """
    Middleware to log slow requests for monitoring.
    Does not cancel requests, only logs them.
    """
    
    def __init__(self, app, threshold_ms: float = 1000.0):
        super().__init__(app)
        self.threshold_ms = threshold_ms
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        import time
        start = time.perf_counter()
        
        response = await call_next(request)
        
        duration_ms = (time.perf_counter() - start) * 1000
        
        if duration_ms > self.threshold_ms:
            logger.warning(
                "Slow request: %s %s took %.0fms (threshold: %.0fms)",
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
                    "status_code": response.status_code,
                }
            )
        
        return response
