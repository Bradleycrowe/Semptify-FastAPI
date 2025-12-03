"""
Authentication Router (Semptify 5.0)
Redirects to storage-based authentication.

In Semptify 5.0, there's no traditional registration/login.
Users authenticate by connecting their cloud storage.
This router provides backward-compatible endpoints that redirect appropriately.
"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from app.core.config import Settings, get_settings
from app.core.security import require_user, StorageUser, rate_limit_dependency


router = APIRouter()


# =============================================================================
# Response Schemas
# =============================================================================

class AuthInfoResponse(BaseModel):
    """Info about authentication method."""
    method: str = "storage-based"
    message: str
    providers_url: str


class UserProfileResponse(BaseModel):
    """Current user profile."""
    user_id: str
    provider: str
    email: str | None = None
    authenticated_at: str | None = None


# =============================================================================
# Endpoints
# =============================================================================

@router.get("/register")
async def register_redirect():
    """
    Redirect to storage provider selection.
    
    In Semptify 5.0, there's no traditional registration.
    Users authenticate by connecting their cloud storage.
    """
    return RedirectResponse(url="/storage/providers", status_code=302)


@router.post(
    "/register",
    response_model=AuthInfoResponse,
    dependencies=[Depends(rate_limit_dependency("auth", window=60, max_requests=10))],
)
async def register_info():
    """
    Registration info endpoint.
    
    Explains that Semptify 5.0 uses storage-based authentication.
    """
    return AuthInfoResponse(
        method="storage-based",
        message="Semptify 5.0 uses storage-based authentication. "
                "Connect your cloud storage (Google Drive, Dropbox, or OneDrive) "
                "to create your account. Your identity IS your storage access.",
        providers_url="/storage/providers",
    )


@router.post("/validate")
async def validate_info():
    """
    Token validation info.
    
    In storage-based auth, validation happens via /storage/session.
    """
    return {
        "message": "Use /storage/session to check authentication status",
        "redirect": "/storage/session",
    }


@router.get("/me", response_model=UserProfileResponse)
async def get_current_user_profile(
    user: StorageUser = Depends(require_user),
):
    """
    Get the current authenticated user's profile.
    
    Returns information about the user based on their storage authentication.
    """
    return UserProfileResponse(
        user_id=user.user_id,
        provider=user.provider,
        email=user.email,
        authenticated_at=user.authenticated_at.isoformat() if user.authenticated_at else None,
    )


@router.post("/logout")
async def logout():
    """
    Logout redirect.
    
    Redirects to storage logout endpoint.
    """
    return RedirectResponse(url="/storage/logout", status_code=307)