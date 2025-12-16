"""
Semptify SDK - Custom Exceptions

Provides typed exceptions for API error handling.
"""

from typing import Optional, Dict, Any


class SemptifyError(Exception):
    """Base exception for all Semptify SDK errors."""
    
    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        response_data: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None,
    ):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.response_data = response_data or {}
        self.request_id = request_id
    
    def __str__(self) -> str:
        parts = [self.message]
        if self.status_code:
            parts.append(f"(HTTP {self.status_code})")
        if self.request_id:
            parts.append(f"[Request ID: {self.request_id}]")
        return " ".join(parts)


class AuthenticationError(SemptifyError):
    """Raised when authentication fails or is required."""
    
    def __init__(
        self,
        message: str = "Authentication required",
        redirect_url: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(message, **kwargs)
        self.redirect_url = redirect_url


class NotFoundError(SemptifyError):
    """Raised when a requested resource is not found."""
    
    def __init__(
        self,
        resource_type: str = "Resource",
        resource_id: Optional[str] = None,
        **kwargs,
    ):
        message = f"{resource_type} not found"
        if resource_id:
            message = f"{resource_type} '{resource_id}' not found"
        super().__init__(message, status_code=404, **kwargs)
        self.resource_type = resource_type
        self.resource_id = resource_id


class ValidationError(SemptifyError):
    """Raised when request validation fails."""
    
    def __init__(
        self,
        message: str = "Validation error",
        errors: Optional[list] = None,
        **kwargs,
    ):
        super().__init__(message, status_code=422, **kwargs)
        self.errors = errors or []


class RateLimitError(SemptifyError):
    """Raised when rate limit is exceeded."""
    
    def __init__(
        self,
        message: str = "Rate limit exceeded",
        retry_after: Optional[int] = None,
        **kwargs,
    ):
        super().__init__(message, status_code=429, **kwargs)
        self.retry_after = retry_after


class ServerError(SemptifyError):
    """Raised when a server error occurs."""
    
    def __init__(
        self,
        message: str = "Internal server error",
        **kwargs,
    ):
        super().__init__(message, status_code=500, **kwargs)


class StorageRequiredError(AuthenticationError):
    """Raised when cloud storage connection is required."""
    
    def __init__(
        self,
        message: str = "Cloud storage connection required",
        redirect_url: str = "/storage/providers",
        **kwargs,
    ):
        super().__init__(message, redirect_url=redirect_url, status_code=401, **kwargs)


class PermissionError(SemptifyError):
    """Raised when user lacks required permissions."""
    
    def __init__(
        self,
        message: str = "Permission denied",
        required_role: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(message, status_code=403, **kwargs)
        self.required_role = required_role
