"""
Rate Limiting Configuration for Semptify API.

Uses slowapi with configurable limits per endpoint category.
Supports Redis backend for production distributed rate limiting.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi import Request
from fastapi.responses import JSONResponse
import logging

logger = logging.getLogger(__name__)


def get_user_identifier(request: Request) -> str:
    """
    Get rate limit key based on user identity.
    Uses storage token if authenticated, falls back to IP address.
    """
    # Check for storage token (authenticated user)
    storage_token = request.cookies.get("storage_token")
    if storage_token:
        # Use first 16 chars of token as identifier (enough for uniqueness)
        return f"user:{storage_token[:16]}"
    
    # Check X-Forwarded-For for proxy setups
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        # Take first IP in chain (original client)
        return f"ip:{forwarded.split(',')[0].strip()}"
    
    # Fall back to direct client IP
    return f"ip:{get_remote_address(request)}"


# Create limiter with user identifier
limiter = Limiter(
    key_func=get_user_identifier,
    default_limits=["200/minute", "1000/hour"],  # Default for all endpoints
    storage_uri="memory://",  # Use Redis URI for production: "redis://localhost:6379"
    strategy="fixed-window",  # Options: fixed-window, moving-window
)


# =============================================================================
# Rate Limit Presets (use as decorators)
# =============================================================================

# Standard API endpoints
RATE_STANDARD = "60/minute"

# Read-heavy endpoints (documents, timeline, etc.)
RATE_READ = "120/minute"

# Write endpoints (create, update, delete)
RATE_WRITE = "30/minute"

# AI/LLM endpoints (expensive operations)
RATE_AI = "10/minute"

# Authentication endpoints (prevent brute force)
RATE_AUTH = "5/minute"

# Health/metrics (allow more frequent checks)
RATE_HEALTH = "300/minute"

# File uploads (resource intensive)
RATE_UPLOAD = "20/minute"

# Search/query endpoints
RATE_SEARCH = "30/minute"

# Court packet generation (very expensive)
RATE_COURT_PACKET = "5/minute"


def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """
    Custom handler for rate limit exceeded errors.
    Returns a user-friendly JSON response with retry information.
    """
    # Extract limit details
    limit_value = str(exc.detail) if hasattr(exc, 'detail') else "Rate limit exceeded"
    
    # Log rate limit hit
    identifier = get_user_identifier(request)
    logger.warning(
        "Rate limit exceeded: %s on %s %s",
        identifier,
        request.method,
        request.url.path
    )
    
    return JSONResponse(
        status_code=429,
        content={
            "error": "rate_limit_exceeded",
            "message": "Too many requests. Please slow down.",
            "detail": limit_value,
            "retry_after": 60,  # seconds
            "documentation": "https://semptify.com/docs/api/rate-limits"
        },
        headers={
            "Retry-After": "60",
            "X-RateLimit-Limit": limit_value,
        }
    )


# =============================================================================
# Helper decorators for common patterns
# =============================================================================

def limit_ai(func):
    """Decorator for AI/LLM endpoints."""
    return limiter.limit(RATE_AI)(func)


def limit_auth(func):
    """Decorator for authentication endpoints."""
    return limiter.limit(RATE_AUTH)(func)


def limit_upload(func):
    """Decorator for file upload endpoints."""
    return limiter.limit(RATE_UPLOAD)(func)


def limit_search(func):
    """Decorator for search endpoints."""
    return limiter.limit(RATE_SEARCH)(func)


def limit_court_packet(func):
    """Decorator for court packet generation."""
    return limiter.limit(RATE_COURT_PACKET)(func)
