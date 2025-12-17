"""
Semptify 5.0 - Role Validation System
Validates user qualifications for elevated roles.

Validation Methods:
1. TENANT (USER) - Default, no validation needed
2. ADVOCATE - Organization email, invite code, or HUD certification
3. LEGAL - Bar number verification, organization email, or attestation
4. ADMIN - Manual database entry only (never self-service)

Privacy Note: We store minimal verification data - just enough to audit.
"""

import re
import logging
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

from app.core.user_context import UserRole

logger = logging.getLogger(__name__)


# =============================================================================
# Trusted Organizations (expandable)
# =============================================================================

TRUSTED_ADVOCATE_DOMAINS = {
    # Minnesota Housing Organizations
    "homeline.org",                    # HOME Line - Tenant Hotline
    "legalaidmn.org",                  # Legal Aid MN
    "smrls.org",                       # Southern MN Regional Legal Services
    "mylsm.org",                       # Legal Services of NW MN
    "centralmnlegal.org",              # Central MN Legal Services
    "housinglink.org",                 # HousingLink
    "mnhousing.gov",                   # MN Housing Finance Agency
    "metrocouncil.org",                # Met Council Housing
    "hennepinus.attorney",             # Hennepin Co Public Defender
    "ramseycounty.us",                 # Ramsey County
    # Community Organizations
    "midmnlegalaid.org",
    "volunteerlawyersnetwork.org",
    "tubman.org",
    "hmong.org",
    # Add more as partnerships form
}

TRUSTED_LEGAL_DOMAINS = {
    # All advocate domains also qualify
    *TRUSTED_ADVOCATE_DOMAINS,
    # Law Firms (pro bono partners)
    "faegredrinker.com",
    "fredlaw.com",
    "stinson.com",
    "briggs.com",
    "gpmlaw.com",
    # Law Schools (clinical programs)
    "umn.edu",                         # U of M Law Clinic
    "stthomas.edu",                    # St. Thomas Law Clinic
    "mitchellhamline.edu",             # Mitchell Hamline
    # Add verified partners
}


# =============================================================================
# Verification Status
# =============================================================================

class VerificationStatus(str, Enum):
    """Status of role verification request."""
    PENDING = "pending"          # Awaiting review
    VERIFIED = "verified"        # Approved
    REJECTED = "rejected"        # Denied
    EXPIRED = "expired"          # Was verified, now expired
    REVOKED = "revoked"          # Manually revoked


class VerificationMethod(str, Enum):
    """How the role was verified."""
    EMAIL_DOMAIN = "email_domain"        # Trusted org email
    INVITE_CODE = "invite_code"          # Partner invite code
    BAR_NUMBER = "bar_number"            # MN Bar verification
    HUD_CERT = "hud_certification"       # HUD Housing Counselor
    ATTESTATION = "attestation"          # Self-attestation (logged)
    ADMIN_MANUAL = "admin_manual"        # Admin approved manually


@dataclass
class RoleVerification:
    """Record of a role verification."""
    user_id: str
    role: UserRole
    status: VerificationStatus
    method: VerificationMethod
    verified_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    verification_data: Dict[str, Any] = None  # Bar #, cert #, etc.
    notes: str = ""
    verified_by: Optional[str] = None  # Admin who approved (if manual)
    
    def is_valid(self) -> bool:
        """Check if verification is currently valid."""
        if self.status != VerificationStatus.VERIFIED:
            return False
        if self.expires_at and datetime.utcnow() > self.expires_at:
            return False
        return True


# =============================================================================
# Role Validation Logic
# =============================================================================

class RoleValidator:
    """
    Validates user eligibility for elevated roles.
    
    Usage:
        validator = RoleValidator()
        result = validator.validate_for_role(
            user_id="user123",
            requested_role=UserRole.LEGAL,
            email="attorney@legalaidmn.org",
            bar_number="0123456"
        )
    """
    
    def __init__(self):
        # In production, this would be database-backed
        self._pending_verifications: Dict[str, RoleVerification] = {}
        self._active_invite_codes: Dict[str, Dict] = {}
        self._load_invite_codes()
    
    def _load_invite_codes(self):
        """Load active invite codes. In production: from database."""
        # Example codes - in production these would be in DB
        self._active_invite_codes = {
            # Format: code -> {role, org, expires, uses_remaining}
            "HOMELINE2025": {
                "role": UserRole.ADVOCATE,
                "org": "HOME Line",
                "expires": datetime(2025, 12, 31),
                "uses_remaining": 50,
            },
            "LEGALAID-MN": {
                "role": UserRole.LEGAL,
                "org": "Legal Aid MN",
                "expires": datetime(2025, 12, 31),
                "uses_remaining": 100,
            },
            # Demo codes for testing
            "DEMO-ADVOCATE": {
                "role": UserRole.ADVOCATE,
                "org": "Demo",
                "expires": datetime(2026, 12, 31),
                "uses_remaining": 999,
            },
            "DEMO-LEGAL": {
                "role": UserRole.LEGAL,
                "org": "Demo",
                "expires": datetime(2026, 12, 31),
                "uses_remaining": 999,
            },
        }
    
    # -------------------------------------------------------------------------
    # Main Validation Entry Point
    # -------------------------------------------------------------------------
    
    def validate_for_role(
        self,
        user_id: str,
        requested_role: UserRole,
        email: Optional[str] = None,
        bar_number: Optional[str] = None,
        hud_cert_number: Optional[str] = None,
        invite_code: Optional[str] = None,
        attestation: bool = False,
    ) -> RoleVerification:
        """
        Validate a user's request for an elevated role.
        
        Returns RoleVerification with status indicating result.
        """
        # ADMIN is never self-service
        if requested_role == UserRole.ADMIN:
            return RoleVerification(
                user_id=user_id,
                role=requested_role,
                status=VerificationStatus.REJECTED,
                method=VerificationMethod.ADMIN_MANUAL,
                notes="Admin role requires manual database entry"
            )
        
        # USER is default, always valid
        if requested_role == UserRole.USER:
            return RoleVerification(
                user_id=user_id,
                role=requested_role,
                status=VerificationStatus.VERIFIED,
                method=VerificationMethod.ADMIN_MANUAL,
                verified_at=datetime.utcnow(),
                notes="Default role, no verification required"
            )
        
        # Try each verification method in order of trust
        
        # 1. Invite Code (highest trust - org vouches for user)
        if invite_code:
            result = self._verify_invite_code(user_id, requested_role, invite_code)
            if result.status == VerificationStatus.VERIFIED:
                return result
        
        # 2. Email Domain (trusted organization)
        if email:
            result = self._verify_email_domain(user_id, requested_role, email)
            if result.status == VerificationStatus.VERIFIED:
                return result
        
        # 3. Bar Number (for LEGAL role)
        if requested_role == UserRole.LEGAL and bar_number:
            result = self._verify_bar_number(user_id, bar_number)
            if result.status == VerificationStatus.VERIFIED:
                return result
        
        # 4. HUD Certification (for ADVOCATE role)
        if requested_role == UserRole.ADVOCATE and hud_cert_number:
            result = self._verify_hud_cert(user_id, hud_cert_number)
            if result.status == VerificationStatus.VERIFIED:
                return result
        
        # 5. Attestation (lowest trust, but auditable)
        if attestation:
            return self._create_attestation(user_id, requested_role, email)
        
        # No valid verification method provided
        return RoleVerification(
            user_id=user_id,
            role=requested_role,
            status=VerificationStatus.PENDING,
            method=VerificationMethod.ADMIN_MANUAL,
            notes="No automatic verification available. Pending admin review."
        )
    
    # -------------------------------------------------------------------------
    # Verification Methods
    # -------------------------------------------------------------------------
    
    def _verify_invite_code(
        self, 
        user_id: str, 
        requested_role: UserRole, 
        code: str
    ) -> RoleVerification:
        """Verify using partner organization invite code."""
        code = code.upper().strip()
        
        if code not in self._active_invite_codes:
            return RoleVerification(
                user_id=user_id,
                role=requested_role,
                status=VerificationStatus.REJECTED,
                method=VerificationMethod.INVITE_CODE,
                notes=f"Invalid invite code: {code}"
            )
        
        code_data = self._active_invite_codes[code]
        
        # Check if code is for requested role or higher
        if not self._role_qualifies(code_data["role"], requested_role):
            return RoleVerification(
                user_id=user_id,
                role=requested_role,
                status=VerificationStatus.REJECTED,
                method=VerificationMethod.INVITE_CODE,
                notes=f"Code {code} is for {code_data['role'].value}, not {requested_role.value}"
            )
        
        # Check expiration
        if datetime.utcnow() > code_data["expires"]:
            return RoleVerification(
                user_id=user_id,
                role=requested_role,
                status=VerificationStatus.REJECTED,
                method=VerificationMethod.INVITE_CODE,
                notes=f"Invite code {code} has expired"
            )
        
        # Check uses remaining
        if code_data["uses_remaining"] <= 0:
            return RoleVerification(
                user_id=user_id,
                role=requested_role,
                status=VerificationStatus.REJECTED,
                method=VerificationMethod.INVITE_CODE,
                notes=f"Invite code {code} has no uses remaining"
            )
        
        # Success! Decrement uses
        self._active_invite_codes[code]["uses_remaining"] -= 1
        
        logger.info(f"✅ User {user_id} verified as {requested_role.value} via invite code from {code_data['org']}")
        
        return RoleVerification(
            user_id=user_id,
            role=requested_role,
            status=VerificationStatus.VERIFIED,
            method=VerificationMethod.INVITE_CODE,
            verified_at=datetime.utcnow(),
            verification_data={"code": code, "org": code_data["org"]},
            notes=f"Verified via invite code from {code_data['org']}"
        )
    
    def _verify_email_domain(
        self, 
        user_id: str, 
        requested_role: UserRole, 
        email: str
    ) -> RoleVerification:
        """Verify using trusted organization email domain."""
        email = email.lower().strip()
        
        # Extract domain
        match = re.search(r'@([a-zA-Z0-9.-]+)$', email)
        if not match:
            return RoleVerification(
                user_id=user_id,
                role=requested_role,
                status=VerificationStatus.REJECTED,
                method=VerificationMethod.EMAIL_DOMAIN,
                notes=f"Invalid email format: {email}"
            )
        
        domain = match.group(1)
        
        # Check against trusted domains based on role
        trusted_domains = (
            TRUSTED_LEGAL_DOMAINS if requested_role == UserRole.LEGAL
            else TRUSTED_ADVOCATE_DOMAINS
        )
        
        if domain not in trusted_domains:
            return RoleVerification(
                user_id=user_id,
                role=requested_role,
                status=VerificationStatus.PENDING,
                method=VerificationMethod.EMAIL_DOMAIN,
                notes=f"Domain {domain} not in trusted list. Pending manual review."
            )
        
        logger.info(f"✅ User {user_id} verified as {requested_role.value} via trusted domain {domain}")
        
        return RoleVerification(
            user_id=user_id,
            role=requested_role,
            status=VerificationStatus.VERIFIED,
            method=VerificationMethod.EMAIL_DOMAIN,
            verified_at=datetime.utcnow(),
            verification_data={"email": email, "domain": domain},
            notes=f"Verified via trusted organization email ({domain})"
        )
    
    def _verify_bar_number(self, user_id: str, bar_number: str) -> RoleVerification:
        """
        Verify Minnesota Bar number.
        
        In production, this would call the MN Bar API or scrape their directory:
        https://www.mnbar.org/attorney-directory
        
        For now, we do format validation and flag for manual review.
        """
        bar_number = bar_number.strip()
        
        # MN Bar numbers are typically 6-7 digits
        if not re.match(r'^\d{5,7}$', bar_number):
            return RoleVerification(
                user_id=user_id,
                role=UserRole.LEGAL,
                status=VerificationStatus.REJECTED,
                method=VerificationMethod.BAR_NUMBER,
                notes=f"Invalid MN Bar number format: {bar_number}"
            )
        
        # TODO: In production, verify against MN Bar API
        # For now, mark as pending manual verification
        logger.info(f"⏳ Bar number {bar_number} submitted for verification (user: {user_id})")
        
        return RoleVerification(
            user_id=user_id,
            role=UserRole.LEGAL,
            status=VerificationStatus.PENDING,
            method=VerificationMethod.BAR_NUMBER,
            verification_data={"bar_number": bar_number, "state": "MN"},
            notes=f"Bar number {bar_number} pending verification. Manual review required."
        )
    
    def _verify_hud_cert(self, user_id: str, cert_number: str) -> RoleVerification:
        """
        Verify HUD Housing Counselor certification.
        
        HUD maintains a database of certified counselors:
        https://apps.hud.gov/offices/hsg/sfh/hcc/hcs.cfm
        
        For now, format validation + manual review.
        """
        cert_number = cert_number.strip().upper()
        
        # TODO: Verify against HUD database
        logger.info(f"⏳ HUD cert {cert_number} submitted for verification (user: {user_id})")
        
        return RoleVerification(
            user_id=user_id,
            role=UserRole.ADVOCATE,
            status=VerificationStatus.PENDING,
            method=VerificationMethod.HUD_CERT,
            verification_data={"hud_cert": cert_number},
            notes=f"HUD certification {cert_number} pending verification."
        )
    
    def _create_attestation(
        self, 
        user_id: str, 
        requested_role: UserRole,
        email: Optional[str] = None
    ) -> RoleVerification:
        """
        Create attestation-based verification.
        
        User attests they're qualified. This creates an audit trail.
        For LEGAL role, additional warnings about UPL are logged.
        """
        if requested_role == UserRole.LEGAL:
            attestation_text = (
                "I attest that I am a licensed attorney in good standing, "
                "authorized to practice law in Minnesota. I understand that "
                "unauthorized practice of law is a crime under MN Statute 481.02."
            )
        else:
            attestation_text = (
                "I attest that I work for a housing advocacy organization "
                "and am qualified to assist tenants with housing issues."
            )
        
        logger.warning(
            f"⚠️ ATTESTATION: User {user_id} attested for {requested_role.value} role. "
            f"Email: {email or 'not provided'}. Audit trail created."
        )
        
        return RoleVerification(
            user_id=user_id,
            role=requested_role,
            status=VerificationStatus.VERIFIED,
            method=VerificationMethod.ATTESTATION,
            verified_at=datetime.utcnow(),
            verification_data={
                "attestation": attestation_text,
                "email": email,
                "timestamp": datetime.utcnow().isoformat(),
                "ip_logged": True  # Would capture IP in production
            },
            notes=f"Verified via self-attestation. User accepted responsibility."
        )
    
    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------
    
    def _role_qualifies(self, code_role: UserRole, requested_role: UserRole) -> bool:
        """Check if a code's role qualifies for the requested role."""
        # LEGAL code can be used for ADVOCATE or LEGAL
        # ADVOCATE code can only be used for ADVOCATE
        if code_role == UserRole.LEGAL:
            return requested_role in (UserRole.LEGAL, UserRole.ADVOCATE)
        return code_role == requested_role
    
    def get_role_requirements(self, role: UserRole) -> Dict[str, Any]:
        """Get human-readable requirements for a role."""
        requirements = {
            UserRole.USER: {
                "name": "Tenant",
                "requirements": "None - default role for all users",
                "verification_options": []
            },
            UserRole.MANAGER: {
                "name": "Manager",
                "requirements": "Property management or case management authorization",
                "verification_options": [
                    "Organization email domain",
                    "Admin approval"
                ]
            },
            UserRole.ADVOCATE: {
                "name": "Housing Advocate",
                "requirements": "Work for housing advocacy organization OR HUD-certified housing counselor",
                "verification_options": [
                    "Organization email (e.g., @homeline.org, @legalaidmn.org)",
                    "Partner organization invite code",
                    "HUD Housing Counselor certification number",
                    "Self-attestation (logged)"
                ]
            },
            UserRole.LEGAL: {
                "name": "Licensed Attorney",
                "requirements": "Active license to practice law in Minnesota",
                "verification_options": [
                    "Minnesota Bar number (verified)",
                    "Legal organization email domain",
                    "Partner organization invite code",
                    "Self-attestation with UPL acknowledgment (logged)"
                ],
                "warning": (
                    "⚠️ Attorney-client privilege protections apply only to licensed attorneys. "
                    "Unauthorized practice of law is a crime under MN Statute 481.02."
                )
            },
            UserRole.ADMIN: {
                "name": "System Administrator",
                "requirements": "Internal authorization only",
                "verification_options": [
                    "Manual database entry by existing admin"
                ]
            }
        }
        return requirements.get(role, {})


# =============================================================================
# Singleton instance
# =============================================================================

_validator_instance: Optional[RoleValidator] = None

def get_role_validator() -> RoleValidator:
    """Get the role validator singleton."""
    global _validator_instance
    if _validator_instance is None:
        _validator_instance = RoleValidator()
    return _validator_instance
