"""
Semptify 5.0 - Role Upgrade API
Allows users to request elevated roles with verification.
"""

from fastapi import APIRouter, Request, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
import logging

from app.core.user_context import UserRole, UserContext
from app.core.role_validation import (
    RoleValidator,
    RoleVerification,
    VerificationStatus,
    get_role_validator,
)
from app.core.security import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/roles", tags=["Role Management"])


# =============================================================================
# Request Models
# =============================================================================

class RoleUpgradeRequest(BaseModel):
    """Request to upgrade to an elevated role."""
    requested_role: str  # "advocate" or "legal"
    email: Optional[str] = None
    bar_number: Optional[str] = None
    hud_cert_number: Optional[str] = None
    invite_code: Optional[str] = None
    attestation: bool = False
    
    class Config:
        json_schema_extra = {
            "example": {
                "requested_role": "advocate",
                "email": "counselor@homeline.org",
                "invite_code": "HOMELINE2025"
            }
        }


class RoleRequirementsResponse(BaseModel):
    """Requirements for a specific role."""
    role: str
    name: str
    requirements: str
    verification_options: list
    warning: Optional[str] = None


class RoleVerificationResponse(BaseModel):
    """Response from role verification request."""
    success: bool
    status: str
    role: str
    method: str
    message: str
    next_steps: Optional[str] = None


# =============================================================================
# Endpoints
# =============================================================================

@router.get("/available")
async def get_available_roles():
    """
    Get all available roles and their requirements.
    """
    validator = get_role_validator()
    
    roles = []
    for role in [UserRole.USER, UserRole.ADVOCATE, UserRole.LEGAL]:
        req = validator.get_role_requirements(role)
        roles.append({
            "role": role.value,
            "name": req.get("name", role.value),
            "requirements": req.get("requirements", ""),
            "verification_options": req.get("verification_options", []),
            "warning": req.get("warning"),
            "self_service": role != UserRole.ADMIN
        })
    
    return {
        "roles": roles,
        "note": "Admin role is not available via self-service"
    }


@router.get("/requirements/{role}")
async def get_role_requirements(role: str):
    """
    Get detailed requirements for a specific role.
    """
    validator = get_role_validator()
    
    try:
        user_role = UserRole(role.lower())
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid role: {role}")
    
    requirements = validator.get_role_requirements(user_role)
    
    return RoleRequirementsResponse(
        role=role,
        name=requirements.get("name", role),
        requirements=requirements.get("requirements", ""),
        verification_options=requirements.get("verification_options", []),
        warning=requirements.get("warning")
    )


@router.post("/upgrade")
async def request_role_upgrade(
    request: RoleUpgradeRequest,
    user: Optional[UserContext] = Depends(get_current_user)
):
    """
    Request an upgrade to an elevated role.
    
    Verification methods (in order of trust):
    1. Partner invite code
    2. Trusted organization email domain
    3. MN Bar number (for attorney role)
    4. HUD certification number (for advocate role)
    5. Self-attestation (creates audit trail)
    """
    validator = get_role_validator()
    
    # Parse requested role
    try:
        requested_role = UserRole(request.requested_role.lower())
    except ValueError:
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid role: {request.requested_role}. Valid: user, advocate, legal"
        )
    
    # Reject admin requests
    if requested_role == UserRole.ADMIN:
        raise HTTPException(
            status_code=403,
            detail="Admin role cannot be requested via API. Contact system administrator."
        )
    
    # Get user ID (from session or generate temp)
    user_id = user.user_id if user else "temp_" + str(hash(request.email or "anon"))[:8]
    
    # Perform verification
    verification = validator.validate_for_role(
        user_id=user_id,
        requested_role=requested_role,
        email=request.email,
        bar_number=request.bar_number,
        hud_cert_number=request.hud_cert_number,
        invite_code=request.invite_code,
        attestation=request.attestation,
    )
    
    # Build response
    if verification.status == VerificationStatus.VERIFIED:
        return RoleVerificationResponse(
            success=True,
            status="verified",
            role=requested_role.value,
            method=verification.method.value,
            message=f"✅ Role upgrade approved! You now have {requested_role.value} access.",
            next_steps="Refresh the page to access your new dashboard."
        )
    
    elif verification.status == VerificationStatus.PENDING:
        return RoleVerificationResponse(
            success=False,
            status="pending",
            role=requested_role.value,
            method=verification.method.value,
            message="⏳ Your request is pending manual review.",
            next_steps=(
                "An administrator will review your request within 1-2 business days. "
                "You'll receive an email when approved."
            )
        )
    
    else:  # REJECTED
        return RoleVerificationResponse(
            success=False,
            status="rejected",
            role=requested_role.value,
            method=verification.method.value,
            message=f"❌ Verification failed: {verification.notes}",
            next_steps=(
                "Please verify your credentials and try again, or contact support "
                "if you believe this is an error."
            )
        )


@router.get("/my-role")
async def get_my_role(user: Optional[UserContext] = Depends(get_current_user)):
    """
    Get current user's role and permissions.
    """
    if not user:
        return {
            "role": "user",
            "display_name": "Tenant",
            "permissions": [],
            "verified": False,
            "message": "Not logged in. Default tenant role applies."
        }
    
    validator = get_role_validator()
    requirements = validator.get_role_requirements(user.role)
    
    return {
        "role": user.role.value,
        "display_name": requirements.get("name", user.role.value),
        "permissions": list(user.permissions),
        "verified": True,
        "storage_provider": user.provider.value if user.provider else None,
    }


@router.get("/trusted-organizations")
async def get_trusted_organizations():
    """
    Get list of trusted organizations whose email domains auto-verify.
    """
    from app.core.role_validation import TRUSTED_ADVOCATE_DOMAINS, TRUSTED_LEGAL_DOMAINS
    
    return {
        "advocate_domains": sorted(TRUSTED_ADVOCATE_DOMAINS),
        "legal_domains": sorted(TRUSTED_LEGAL_DOMAINS - TRUSTED_ADVOCATE_DOMAINS),
        "note": (
            "Users with email addresses from these organizations can be automatically "
            "verified for elevated roles. Contact us to add your organization."
        )
    }
