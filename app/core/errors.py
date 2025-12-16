"""
Standardized Error Handling for Semptify API.

Provides consistent error responses across all endpoints.
All errors return JSON with standard structure.
"""

import logging
import traceback
from typing import Any, Optional

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


# =============================================================================
# Error Response Models
# =============================================================================

class ErrorDetail(BaseModel):
    """Detail for a single error."""
    loc: list[str] | None = None  # Location of error (field path)
    msg: str  # Error message
    type: str  # Error type identifier


class ErrorResponse(BaseModel):
    """Standard error response format."""
    error: str  # Error code (e.g., "validation_error", "not_found")
    message: str  # Human-readable message
    details: list[ErrorDetail] | None = None  # Additional details
    request_id: str | None = None  # For tracking
    documentation: str | None = None  # Link to relevant docs


# =============================================================================
# Custom Exceptions
# =============================================================================

class SemptifyError(Exception):
    """Base exception for Semptify-specific errors."""
    
    def __init__(
        self,
        message: str,
        error_code: str = "semptify_error",
        status_code: int = 500,
        details: list[dict] | None = None,
    ):
        self.message = message
        self.error_code = error_code
        self.status_code = status_code
        self.details = details
        super().__init__(message)


class NotFoundError(SemptifyError):
    """Resource not found."""
    
    def __init__(self, resource: str, identifier: Any = None):
        message = f"{resource} not found"
        if identifier:
            message = f"{resource} '{identifier}' not found"
        super().__init__(
            message=message,
            error_code="not_found",
            status_code=404,
        )


class AuthenticationError(SemptifyError):
    """Authentication failed."""
    
    def __init__(self, message: str = "Authentication required"):
        super().__init__(
            message=message,
            error_code="authentication_required",
            status_code=401,
        )


class AuthorizationError(SemptifyError):
    """Authorization failed (authenticated but not permitted)."""
    
    def __init__(self, message: str = "Permission denied"):
        super().__init__(
            message=message,
            error_code="permission_denied",
            status_code=403,
        )


class ValidationError(SemptifyError):
    """Custom validation error."""
    
    def __init__(self, message: str, details: list[dict] | None = None):
        super().__init__(
            message=message,
            error_code="validation_error",
            status_code=422,
            details=details,
        )


class ConflictError(SemptifyError):
    """Resource conflict (e.g., duplicate)."""
    
    def __init__(self, message: str = "Resource conflict"):
        super().__init__(
            message=message,
            error_code="conflict",
            status_code=409,
        )


class RateLimitError(SemptifyError):
    """Rate limit exceeded."""
    
    def __init__(self, retry_after: int = 60):
        super().__init__(
            message=f"Rate limit exceeded. Retry after {retry_after} seconds.",
            error_code="rate_limit_exceeded",
            status_code=429,
            details=[{"retry_after": retry_after}],
        )


class ServiceUnavailableError(SemptifyError):
    """External service unavailable."""
    
    def __init__(self, service: str = "External service"):
        super().__init__(
            message=f"{service} is temporarily unavailable",
            error_code="service_unavailable",
            status_code=503,
        )


class AIProviderError(SemptifyError):
    """AI provider error."""
    
    def __init__(self, provider: str, message: str = "AI service error"):
        super().__init__(
            message=f"{provider}: {message}",
            error_code="ai_provider_error",
            status_code=502,
        )


class StorageError(SemptifyError):
    """Storage provider error."""
    
    def __init__(self, provider: str = "Storage", message: str = "Storage operation failed"):
        super().__init__(
            message=f"{provider}: {message}",
            error_code="storage_error",
            status_code=502,
        )


# =============================================================================
# Exception Handlers
# =============================================================================

def get_request_id(request: Request) -> Optional[str]:
    """Extract request ID from request."""
    return request.headers.get("X-Request-Id")


async def semptify_error_handler(request: Request, exc: SemptifyError) -> JSONResponse:
    """Handle Semptify-specific exceptions."""
    logger.warning(
        "SemptifyError: %s - %s",
        exc.error_code,
        exc.message,
        extra={"error_code": exc.error_code, "path": request.url.path}
    )
    
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.error_code,
            "message": exc.message,
            "details": exc.details,
            "request_id": get_request_id(request),
        },
    )


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """Handle standard HTTP exceptions."""
    # Map status codes to error codes
    error_codes = {
        400: "bad_request",
        401: "authentication_required",
        403: "permission_denied",
        404: "not_found",
        405: "method_not_allowed",
        409: "conflict",
        422: "validation_error",
        429: "rate_limit_exceeded",
        500: "internal_error",
        502: "bad_gateway",
        503: "service_unavailable",
    }
    
    error_code = error_codes.get(exc.status_code, "error")
    
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": error_code,
            "message": str(exc.detail) if exc.detail else f"HTTP {exc.status_code}",
            "request_id": get_request_id(request),
        },
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Handle Pydantic validation errors."""
    details = []
    for error in exc.errors():
        details.append({
            "loc": list(error.get("loc", [])),
            "msg": error.get("msg", ""),
            "type": error.get("type", ""),
        })
    
    logger.info(
        "Validation error on %s: %d issues",
        request.url.path,
        len(details),
    )
    
    return JSONResponse(
        status_code=422,
        content={
            "error": "validation_error",
            "message": "Request validation failed",
            "details": details,
            "request_id": get_request_id(request),
        },
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle unexpected exceptions."""
    # Log full traceback for debugging
    logger.error(
        "Unhandled exception on %s: %s",
        request.url.path,
        str(exc),
        exc_info=True,
        extra={
            "path": request.url.path,
            "method": request.method,
            "traceback": traceback.format_exc(),
        }
    )
    
    # Don't expose internal details in production
    return JSONResponse(
        status_code=500,
        content={
            "error": "internal_error",
            "message": "An unexpected error occurred",
            "request_id": get_request_id(request),
        },
    )


# =============================================================================
# Setup Function
# =============================================================================

def setup_exception_handlers(app: FastAPI) -> None:
    """
    Register all exception handlers with the FastAPI app.
    
    Call during app initialization:
        setup_exception_handlers(app)
    """
    app.add_exception_handler(SemptifyError, semptify_error_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, generic_exception_handler)


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    # Base classes
    "SemptifyError",
    "ErrorResponse",
    "ErrorDetail",
    # Specific exceptions
    "NotFoundError",
    "AuthenticationError",
    "AuthorizationError",
    "ValidationError",
    "ConflictError",
    "RateLimitError",
    "ServiceUnavailableError",
    "AIProviderError",
    "StorageError",
    # Setup
    "setup_exception_handlers",
]
