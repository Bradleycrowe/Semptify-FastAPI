"""
Semptify 5.0 - Simple User ID System
User ID encodes provider + role + unique identifier in one string.

Format: <provider><role><8-char-random>
Example: GU7x9kM2pQ = Google Drive + User + 7x9kM2pQ

Provider Codes (1 char):
- G = Google Drive
- D = Dropbox
- O = OneDrive

Role Codes (1 char):
- U = User (default)
- M = Manager
- V = Advocate
- L = Legal
- A = AdminThis keeps it simple:
1. User visits → read cookie → parse user ID
2. Know immediately: which storage to check, what role to load
3. One cookie, one ID, everything works
"""

import secrets
import string
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Tuple


# =============================================================================
# Provider & Role Codes
# =============================================================================

class ProviderCode(str, Enum):
    """Single-character provider codes."""
    GOOGLE_DRIVE = "G"
    DROPBOX = "D"
    ONEDRIVE = "O"


class RoleCode(str, Enum):
    """Single-character role codes."""
    ADMIN = "A"
    MANAGER = "M"
    USER = "U"
    ADVOCATE = "V"  # V for adVocate since A is Admin
    LEGAL = "L"


# Mappings for conversion
PROVIDER_TO_CODE = {
    "google_drive": ProviderCode.GOOGLE_DRIVE,
    "dropbox": ProviderCode.DROPBOX,
    "onedrive": ProviderCode.ONEDRIVE,
}

CODE_TO_PROVIDER = {
    ProviderCode.GOOGLE_DRIVE: "google_drive",
    ProviderCode.DROPBOX: "dropbox",
    ProviderCode.ONEDRIVE: "onedrive",
    "G": "google_drive",
    "D": "dropbox",
    "O": "onedrive",
}

ROLE_TO_CODE = {
    "admin": RoleCode.ADMIN,
    "manager": RoleCode.MANAGER,
    "user": RoleCode.USER,
    "advocate": RoleCode.ADVOCATE,
    "legal": RoleCode.LEGAL,
}

CODE_TO_ROLE = {
    RoleCode.ADMIN: "admin",
    RoleCode.MANAGER: "manager",
    RoleCode.USER: "user",
    RoleCode.ADVOCATE: "advocate",
    RoleCode.LEGAL: "legal",
    "A": "admin",
    "M": "manager",
    "U": "user",
    "V": "advocate",
    "L": "legal",
}


# =============================================================================
# User ID Operations
# =============================================================================

def generate_user_id(provider: str, role: str = "user") -> str:
    """
    Generate a new user ID encoding provider and role.

    Args:
        provider: Storage provider (google_drive, dropbox, onedrive)
        role: User role (user, manager, advocate, legal, admin)

    Returns:
        User ID like "GU7x9kM2pQ" (10 chars total)

    Example:
        >>> generate_user_id("google_drive", "user")
        'GUa8Km3xPq'
    """
    # Get codes
    provider_code = PROVIDER_TO_CODE.get(provider, ProviderCode.GOOGLE_DRIVE)
    role_code = ROLE_TO_CODE.get(role, RoleCode.USER)
    
    # Generate 8-char random suffix (alphanumeric, easy to read)
    alphabet = string.ascii_letters + string.digits
    random_part = ''.join(secrets.choice(alphabet) for _ in range(8))
    
    return f"{provider_code.value}{role_code.value}{random_part}"


def parse_user_id(user_id: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Parse a user ID to extract provider, role, and unique part.
    
    Args:
        user_id: User ID like "GT7x9kM2pQ"
    
    Returns:
        Tuple of (provider, role, unique_id) or (None, None, None) if invalid
    
    Example:
        >>> parse_user_id("GU7x9kM2pQ")
        ('google_drive', 'user', '7x9kM2pQ')
    """
    if not user_id or len(user_id) < 3:
        return None, None, None
    
    provider_char = user_id[0].upper()
    role_char = user_id[1].upper()
    unique_part = user_id[2:]
    
    provider = CODE_TO_PROVIDER.get(provider_char)
    role = CODE_TO_ROLE.get(role_char)
    
    if not provider or not role:
        return None, None, None
    
    return provider, role, unique_part


def update_user_id_role(user_id: str, new_role: str) -> Optional[str]:
    """
    Create a new user ID with updated role (keeps provider and unique part).
    
    Args:
        user_id: Current user ID
        new_role: New role (user, manager, advocate, legal, admin)

    Returns:
        New user ID with updated role, or None if invalid    Example:
        >>> update_user_id_role("GT7x9kM2pQ", "landlord")
        'GL7x9kM2pQ'
    """
    provider, _, unique_part = parse_user_id(user_id)
    if not provider or not unique_part:
        return None
    
    role_code = ROLE_TO_CODE.get(new_role, RoleCode.USER)
    provider_code = PROVIDER_TO_CODE.get(provider, ProviderCode.GOOGLE_DRIVE)
    
    return f"{provider_code.value}{role_code.value}{unique_part}"


def get_provider_from_user_id(user_id: str) -> Optional[str]:
    """Quick helper to get just the provider from user ID."""
    provider, _, _ = parse_user_id(user_id)
    return provider


def get_role_from_user_id(user_id: str) -> Optional[str]:
    """Quick helper to get just the role from user ID."""
    _, role, _ = parse_user_id(user_id)
    return role


# =============================================================================
# Parsed User ID Object
# =============================================================================

@dataclass
class ParsedUserId:
    """Structured representation of a parsed user ID."""
    user_id: str
    provider: str
    role: str
    unique_part: str
    
    @classmethod
    def from_string(cls, user_id: str) -> Optional["ParsedUserId"]:
        """Parse user ID string into structured object."""
        provider, role, unique_part = parse_user_id(user_id)
        if not provider:
            return None
        return cls(
            user_id=user_id,
            provider=provider,
            role=role,
            unique_part=unique_part,
        )
    
    def with_role(self, new_role: str) -> "ParsedUserId":
        """Create new ParsedUserId with different role."""
        new_id = update_user_id_role(self.user_id, new_role)
        return ParsedUserId(
            user_id=new_id,
            provider=self.provider,
            role=new_role,
            unique_part=self.unique_part,
        )
    
    @property
    def provider_name(self) -> str:
        """Human-readable provider name."""
        names = {
            "google_drive": "Google Drive",
            "dropbox": "Dropbox",
            "onedrive": "OneDrive",
        }
        return names.get(self.provider, self.provider)
    
    @property 
    def role_name(self) -> str:
        """Human-readable role name."""
        return self.role.title()


# =============================================================================
# Cookie Name Constants
# =============================================================================

COOKIE_USER_ID = "semptify_uid"  # The one cookie we need
COOKIE_MAX_AGE = 365 * 24 * 60 * 60  # 1 year
