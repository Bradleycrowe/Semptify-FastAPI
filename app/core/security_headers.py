"""
Security Headers Middleware for Semptify.

Adds security headers to all responses following OWASP guidelines.
"""

from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Middleware to add security headers to all responses.
    
    Headers added:
    - X-Content-Type-Options: Prevent MIME sniffing
    - X-Frame-Options: Prevent clickjacking
    - X-XSS-Protection: XSS filter (legacy browsers)
    - Referrer-Policy: Control referrer information
    - Permissions-Policy: Restrict browser features
    - Content-Security-Policy: Control resource loading (configurable)
    - Strict-Transport-Security: Force HTTPS (production only)
    """
    
    def __init__(
        self,
        app,
        enable_hsts: bool = False,
        hsts_max_age: int = 31536000,  # 1 year
        csp_policy: str | None = None,
        frame_options: str = "SAMEORIGIN",
    ):
        super().__init__(app)
        self.enable_hsts = enable_hsts
        self.hsts_max_age = hsts_max_age
        self.frame_options = frame_options
        
        # Default CSP - restrictive but functional
        self.csp_policy = csp_policy or self._default_csp()
    
    def _default_csp(self) -> str:
        """
        Default Content Security Policy.
        Allows self-hosted resources and common CDNs.
        """
        return "; ".join([
            "default-src 'self'",
            "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com",
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdn.jsdelivr.net",
            "font-src 'self' https://fonts.gstatic.com",
            "img-src 'self' data: https: blob:",
            "connect-src 'self' https://api.openai.com https://api.anthropic.com wss:",
            "frame-ancestors 'self'",
            "form-action 'self'",
            "base-uri 'self'",
        ])
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)
        
        # Basic security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = self.frame_options
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        
        # Permissions Policy (replaces Feature-Policy)
        response.headers["Permissions-Policy"] = (
            "accelerometer=(), camera=(), geolocation=(self), "
            "gyroscope=(), magnetometer=(), microphone=(), "
            "payment=(), usb=()"
        )
        
        # Content Security Policy
        # Skip for API JSON responses to avoid breaking clients
        content_type = response.headers.get("Content-Type", "")
        if "text/html" in content_type:
            response.headers["Content-Security-Policy"] = self.csp_policy
        
        # HSTS (only enable in production with HTTPS)
        if self.enable_hsts:
            response.headers["Strict-Transport-Security"] = (
                f"max-age={self.hsts_max_age}; includeSubDomains"
            )
        
        # Cache control for sensitive pages
        if request.url.path.startswith("/api/") and request.method in ("GET", "HEAD"):
            # Don't cache authenticated API responses by default
            if "Authorization" in request.headers or "storage_token" in request.cookies:
                response.headers.setdefault("Cache-Control", "private, no-store")
        
        return response


class TrustedHostMiddleware(BaseHTTPMiddleware):
    """
    Middleware to validate Host header against allowed hosts.
    Prevents host header attacks.
    """
    
    def __init__(self, app, allowed_hosts: list[str] | None = None):
        super().__init__(app)
        # Default: allow localhost and common dev hosts
        self.allowed_hosts = allowed_hosts or [
            "localhost",
            "127.0.0.1",
            "0.0.0.0",
        ]
        # Add wildcard support
        self.allow_all = "*" in self.allowed_hosts
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if self.allow_all:
            return await call_next(request)
        
        host = request.headers.get("host", "").split(":")[0]  # Remove port
        
        if host not in self.allowed_hosts:
            # Check if it matches any wildcard patterns
            for allowed in self.allowed_hosts:
                if allowed.startswith("*.") and host.endswith(allowed[1:]):
                    return await call_next(request)
            
            # Host not allowed
            from fastapi.responses import JSONResponse
            return JSONResponse(
                status_code=400,
                content={"detail": "Invalid host header"}
            )
        
        return await call_next(request)
