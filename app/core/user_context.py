"""
Semptify 5.0 - User Context System
Handles role, storage provider, and permissions for each user session.

Design Principles:
- User ID is stable (derived from first storage provider used)
- Role determines what UI/features to show
- Provider tells us where to look for documents/tokens
- Permissions are derived from role
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


# =============================================================================
# User Roles
# =============================================================================

class UserRole(str, Enum):
    """
    User roles determine what features/UI to show.
    A user can have ONE active role per session, but can switch.
    """
    ADMIN = "admin"            # System admin: full access
    MANAGER = "manager"        # Manager: property/case management
    USER = "user"              # Default: standard user access
    ADVOCATE = "advocate"      # Tenant advocate: help multiple users
    LEGAL = "legal"            # Legal professional: legal tools


# =============================================================================
# Storage Providers
# =============================================================================

class StorageProvider(str, Enum):
    """Supported cloud storage providers."""
    GOOGLE_DRIVE = "google_drive"
    DROPBOX = "dropbox"
    ONEDRIVE = "onedrive"
    # R2 is system-only, not for user auth


# =============================================================================
# Permissions (derived from role)
# =============================================================================

ROLE_PERMISSIONS = {
    # ==========================================================================
    # TENANT (USER) - Mobile-first, simplified access
    # Focus: Own case management, self-help tools, guided workflows
    # ==========================================================================
    UserRole.USER: {
        # Vault - own documents only
        "vault_read",
        "vault_write",
        # Timeline - own case history
        "timeline_read",
        "timeline_write",
        # Calendar - own deadlines
        "calendar_read",
        "calendar_write",
        # AI assistance
        "copilot_use",
        # File complaints on own behalf
        "complaints_create",
        # Rent ledger
        "ledger_read",
        "ledger_write",
        # Self-help tools
        "eviction_defense",
        "court_forms",
        "letter_builder",
    },
    
    # ==========================================================================
    # MANAGER - Property/case oversight (future: landlord-side?)
    # ==========================================================================
    UserRole.MANAGER: {
        "vault_read",
        "vault_write",
        "timeline_read",
        "calendar_read",
        "calendar_write",
        "property_manage",
        "user_view",  # View user info (not edit)
    },
    
    # ==========================================================================
    # ADVOCATE - Legal aid workers, paralegals, housing counselors
    # Focus: Help multiple tenants, case management across clients
    # ==========================================================================
    UserRole.ADVOCATE: {
        # All tenant permissions
        "vault_read",
        "vault_write",
        "timeline_read",
        "timeline_write",
        "calendar_read",
        "calendar_write",
        "copilot_use",
        "complaints_create",
        "ledger_read",
        "ledger_write",
        "eviction_defense",
        "court_forms",
        "letter_builder",
        # Advocate-specific
        "complaints_review",      # Review/help with complaints
        "multi_user",             # Access multiple tenant cases
        "case_assignment",        # Assign cases to self
        "case_notes",             # Add advocate notes (non-privileged)
        "client_intake",          # Intake new clients
        "bulk_export",            # Export case summaries
    },
    
    # ==========================================================================
    # LEGAL - Licensed attorneys (Legal Aid, pro bono, private)
    # Focus: Full legal tools + attorney-client privilege separation
    # ==========================================================================
    UserRole.LEGAL: {
        # All advocate permissions
        "vault_read",
        "vault_write",
        "timeline_read",
        "timeline_write",
        "calendar_read",
        "calendar_write",
        "copilot_use",
        "complaints_create",
        "complaints_review",
        "ledger_read",
        "ledger_write",
        "eviction_defense",
        "court_forms",
        "letter_builder",
        "multi_user",
        "case_assignment",
        "case_notes",
        "client_intake",
        "bulk_export",
        # Attorney-specific (PRIVILEGED)
        "legal_tools",            # Advanced legal analysis tools
        "privileged_create",      # Create attorney-client privileged notes
        "privileged_read",        # Read privileged work product
        "work_product",           # Attorney work product protection
        "legal_research",         # Advanced legal research tools
        "court_filing",           # Generate court-ready filings
        "discovery_prep",         # Prepare discovery responses
        "case_strategy",          # Strategic case planning
        "conflict_check",         # Check for conflicts of interest
    },
    
    # ==========================================================================
    # ADMIN - System administrators (you)
    # Focus: System config, analytics, full access
    # ==========================================================================
    UserRole.ADMIN: {
        "*",  # All permissions
    },
}


# =============================================================================
# Role Metadata (for UI routing and display)
# =============================================================================

ROLE_METADATA = {
    UserRole.USER: {
        "display_name": "Tenant",
        "description": "Individual facing housing issues",
        "ui_mode": "mobile",           # Mobile-first, simplified
        "landing_page": "/tenant",
        "icon": "🏠",
    },
    UserRole.MANAGER: {
        "display_name": "Manager",
        "description": "Property or case manager",
        "ui_mode": "desktop",
        "landing_page": "/manager",
        "icon": "📋",
    },
    UserRole.ADVOCATE: {
        "display_name": "Advocate",
        "description": "Housing counselor or paralegal",
        "ui_mode": "responsive",       # Tablet-friendly
        "landing_page": "/advocate",
        "icon": "🤝",
    },
    UserRole.LEGAL: {
        "display_name": "Attorney",
        "description": "Licensed legal professional",
        "ui_mode": "desktop",          # Full complexity
        "landing_page": "/legal",
        "icon": "⚖️",
    },
    UserRole.ADMIN: {
        "display_name": "Administrator",
        "description": "System administrator",
        "ui_mode": "desktop",          # Full complexity
        "landing_page": "/admin",
        "icon": "🔧",
    },
}


def get_role_metadata(role: UserRole) -> dict:
    """Get metadata for a role (display name, UI mode, etc.)."""
    return ROLE_METADATA.get(role, ROLE_METADATA[UserRole.USER])


def get_permissions(role: UserRole) -> set[str]:
    """Get permissions for a role."""
    perms = ROLE_PERMISSIONS.get(role, set())
    if "*" in perms:
        # Admin has all permissions
        all_perms = set()
        for role_perms in ROLE_PERMISSIONS.values():
            if "*" not in role_perms:
                all_perms.update(role_perms)
        return all_perms
    return perms


# =============================================================================
# User Context (carries all session context)
# =============================================================================

@dataclass
class UserContext:
    """
    Complete context for an authenticated user session.
    This is what gets passed to route handlers.
    """
    # Identity (stable)
    user_id: str                          # Internal ID (hash of provider:storage_id)
    
    # Storage info
    provider: StorageProvider             # Which storage provider authenticated
    storage_user_id: str                  # ID in the storage provider
    access_token: str                     # Current access token for API calls
    
    # Role & permissions
    role: UserRole = UserRole.USER        # Active role for this session
    permissions: set[str] = field(default_factory=set)
    
    # Optional info
    email: Optional[str] = None
    display_name: Optional[str] = None
    
    # Session tracking
    session_id: Optional[str] = None
    authenticated_at: Optional[datetime] = None
    
    def __post_init__(self):
        """Set permissions based on role if not provided."""
        if not self.permissions:
            self.permissions = get_permissions(self.role)
    
    def has_permission(self, permission: str) -> bool:
        """Check if user has a specific permission."""
        return permission in self.permissions or "*" in self.permissions
    
    def can(self, *permissions: str) -> bool:
        """Check if user has ALL specified permissions."""
        return all(self.has_permission(p) for p in permissions)
    
    def can_any(self, *permissions: str) -> bool:
        """Check if user has ANY of the specified permissions."""
        return any(self.has_permission(p) for p in permissions)
    
    @property
    def is_user(self) -> bool:
        return self.role == UserRole.USER

    @property
    def is_manager(self) -> bool:
        return self.role == UserRole.MANAGER    @property
    def is_advocate(self) -> bool:
        return self.role == UserRole.ADVOCATE

    @property
    def is_legal(self) -> bool:
        return self.role == UserRole.LEGAL

    @property
    def is_admin(self) -> bool:
        return self.role == UserRole.ADMIN


# =============================================================================
# Session Storage Structure
# =============================================================================

@dataclass
class StoredSession:
    """
    What we store in the session store (memory/Redis/DB).
    Contains everything needed to reconstruct UserContext.
    """
    session_id: str
    
    # Identity
    user_id: str
    provider: str  # StorageProvider value
    storage_user_id: str
    
    # Auth
    access_token: str
    refresh_token: Optional[str] = None
    token_expires_at: Optional[datetime] = None
    
    # Role (can be switched)
    role: str = "user"  # UserRole value
    
    # Profile
    email: Optional[str] = None
    display_name: Optional[str] = None
    
    # Timestamps
    created_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    
    def to_context(self) -> UserContext:
        """Convert stored session to UserContext for route handlers."""
        return UserContext(
            user_id=self.user_id,
            provider=StorageProvider(self.provider),
            storage_user_id=self.storage_user_id,
            access_token=self.access_token,
            role=UserRole(self.role),
            email=self.email,
            display_name=self.display_name,
            session_id=self.session_id,
            authenticated_at=self.created_at,
        )
    
    def to_dict(self) -> dict:
        """Serialize for storage."""
        return {
            "session_id": self.session_id,
            "user_id": self.user_id,
            "provider": self.provider,
            "storage_user_id": self.storage_user_id,
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "token_expires_at": self.token_expires_at.isoformat() if self.token_expires_at else None,
            "role": self.role,
            "email": self.email,
            "display_name": self.display_name,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "StoredSession":
        """Deserialize from storage."""
        return cls(
            session_id=data["session_id"],
            user_id=data["user_id"],
            provider=data["provider"],
            storage_user_id=data["storage_user_id"],
            access_token=data["access_token"],
            refresh_token=data.get("refresh_token"),
            token_expires_at=datetime.fromisoformat(data["token_expires_at"]) if data.get("token_expires_at") else None,
            role=data.get("role", "user"),
            email=data.get("email"),
            display_name=data.get("display_name"),
            created_at=datetime.fromisoformat(data["created_at"]),
            expires_at=datetime.fromisoformat(data["expires_at"]) if data.get("expires_at") else None,
        )


# =============================================================================
# UI Configuration by Role
# =============================================================================

ROLE_UI_CONFIG = {
    UserRole.USER: {
        "theme": "user",
        "nav_items": ["vault", "timeline", "calendar", "copilot", "complaints", "ledger"],
        "dashboard": "user_dashboard",
        "landing": "/vault",
    },
    UserRole.MANAGER: {
        "theme": "manager",
        "nav_items": ["properties", "users", "calendar", "documents"],
        "dashboard": "manager_dashboard",
        "landing": "/properties",
    },
    UserRole.ADVOCATE: {
        "theme": "advocate",
        "nav_items": ["clients", "vault", "timeline", "complaints", "resources"],
        "dashboard": "advocate_dashboard",
        "landing": "/clients",
    },
    UserRole.LEGAL: {
        "theme": "legal",
        "nav_items": ["cases", "vault", "timeline", "documents", "resources"],
        "dashboard": "legal_dashboard",
        "landing": "/cases",
    },
    UserRole.ADMIN: {
        "theme": "admin",
        "nav_items": ["users", "system", "logs", "metrics"],
        "dashboard": "admin_dashboard",
        "landing": "/admin",
    },
}


def get_ui_config(role: UserRole) -> dict:
    """Get UI configuration for a role."""
    return ROLE_UI_CONFIG.get(role, ROLE_UI_CONFIG[UserRole.USER])
