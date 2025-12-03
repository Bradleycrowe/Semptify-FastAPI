"""
Semptify 5.0 - Vault Manager
Manages the Semptify5.0 folder structure in user's cloud storage.

Folder Structure:
    Semptify5.0/
    ├── .auth/                      # Hidden auth files
    │   ├── token.enc               # Encrypted master token
    │   ├── token.enc.backup        # Token backup
    │   └── device_keys.json        # Authorized devices
    ├── Vault/                      # User documents
    │   ├── documents/
    │   ├── forms/
    │   └── exports/
    ├── Rehome.html                 # Reconnection script
    └── README.txt                  # Don't delete notice

The master token NEVER leaves storage - it's used for:
- Encrypting/decrypting vault files
- Authorizing module access
- Validating user identity across devices
"""

import json
import secrets
import hashlib
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from dataclasses import dataclass, asdict

from app.core.config import get_settings

settings = get_settings()


# =============================================================================
# Constants
# =============================================================================

SEMPTIFY_ROOT = "Semptify5.0"
AUTH_FOLDER = f"{SEMPTIFY_ROOT}/.auth"
VAULT_FOLDER = f"{SEMPTIFY_ROOT}/Vault"
TOKEN_FILE = f"{AUTH_FOLDER}/token.enc"
TOKEN_BACKUP = f"{AUTH_FOLDER}/token.enc.backup"
DEVICE_KEYS_FILE = f"{AUTH_FOLDER}/device_keys.json"
REHOME_FILE = f"{SEMPTIFY_ROOT}/Rehome.html"
README_FILE = f"{SEMPTIFY_ROOT}/README.txt"


# =============================================================================
# Token Structure
# =============================================================================

@dataclass
class MasterToken:
    """
    Master token stored encrypted in user's cloud storage.
    This token NEVER leaves storage - server fetches and decrypts in-memory only.
    
    Contains:
    - Module authorizations (what features user can access)
    - OAuth credentials (access_token, refresh_token) as BACKUP
    
    The OAuth tokens in cloud are a BACKUP of the database tokens.
    This allows recovery if database is lost, and enables Rehome flow.
    """
    token_id: str                    # Unique token identifier
    user_id: str                     # User ID (GU2L3wyfBy format)
    created_at: str                  # ISO timestamp
    provider: str = ""               # Storage provider (google_drive, dropbox, onedrive)
    version: str = "5.0"             # Semptify version

    # OAuth credentials (backup - also stored in database for fast access)
    access_token: str = ""           # Provider OAuth access token
    refresh_token: str = ""          # Provider OAuth refresh token
    token_expires_at: str = ""       # When access_token expires

    # Module authorizations - which features this token unlocks
    modules: Optional[Dict[str, bool]] = None

    # Security
    last_validated: Optional[str] = None       # Last time token was used
    validation_count: int = 0        # How many times validated

    def __post_init__(self):
        if self.modules is None:
            self.modules = {
                "vault": True,
                "forms": True,
                "timeline": True,
                "copilot": True,
                "calendar": True,
                "defense": True,
                "zoom_court": True,
            }
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> "MasterToken":
        return cls(**data)
    
    def authorize_module(self, module: str) -> bool:
        """Check if this token authorizes access to a module."""
        if self.modules is None:
            return False
        return self.modules.get(module, False)
    
    def record_validation(self):
        """Record that token was validated."""
        self.last_validated = datetime.now(timezone.utc).isoformat()
        self.validation_count += 1


@dataclass
class DeviceKey:
    """Tracks authorized devices."""
    device_id: str
    device_name: str
    authorized_at: str
    last_seen: str
    user_agent: str = ""


# =============================================================================
# Encryption Helpers
# =============================================================================

def _derive_key(user_id: str) -> bytes:
    """Derive encryption key from user_id + server secret."""
    combined = f"{settings.SECRET_KEY}:token:{user_id}".encode()
    return hashlib.sha256(combined).digest()


def encrypt_token(token: MasterToken, user_id: str) -> bytes:
    """
    Encrypt master token for storage with integrity verification.
    Uses AES-GCM which provides both encryption AND authentication (tamper detection).
    """
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from app.services.storage.legal_integrity import TokenIntegrity

    key = _derive_key(user_id)
    nonce = secrets.token_bytes(12)
    
    # Wrap token with integrity hash before encryption
    wrapped = TokenIntegrity.wrap_token(token.to_dict(), user_id)
    plaintext = json.dumps(wrapped).encode()

    # AES-GCM provides authenticated encryption - any tampering will cause decryption to fail
    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(nonce, plaintext, None)

    return nonce + ciphertext


def decrypt_token(encrypted: bytes, user_id: str) -> MasterToken:
    """
    Decrypt master token from storage with integrity verification.
    AES-GCM will raise InvalidTag if data was tampered with.
    """
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from app.services.storage.legal_integrity import TokenIntegrity

    key = _derive_key(user_id)
    nonce = encrypted[:12]
    ciphertext = encrypted[12:]

    # AES-GCM decryption - will fail if tampered
    aesgcm = AESGCM(key)
    plaintext = aesgcm.decrypt(nonce, ciphertext, None)

    wrapped = json.loads(plaintext.decode())
    
    # Handle both wrapped (with integrity) and legacy (without) formats
    if "integrity" in wrapped and "data" in wrapped:
        # New format with integrity verification
        data, is_valid = TokenIntegrity.verify_token(wrapped, user_id)
        if not is_valid:
            raise ValueError("Token integrity verification failed - possible tampering detected")
        return MasterToken.from_dict(data)
    else:
        # Legacy format (pre-integrity) - just use data directly
        return MasterToken.from_dict(wrapped)
# =============================================================================
# File Generation
# =============================================================================

def generate_rehome_html(user_id: str, provider: str, base_url: str) -> str:
    """
    Generate Rehome.html - the reconnection script users click to sync new devices.
    This file is stored in user's cloud storage root Semptify5.0 folder.
    """
    from app.core.user_id import parse_user_id
    
    _, role, _ = parse_user_id(user_id)
    
    provider_names = {
        "google_drive": "Google Drive",
        "dropbox": "Dropbox",
        "onedrive": "OneDrive"
    }
    provider_display = provider_names.get(provider, provider)
    
    provider_icons = {
        "google_drive": "🔷",
        "dropbox": "📦",
        "onedrive": "☁️"
    }
    provider_icon = provider_icons.get(provider, "📁")
    
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Semptify - Reconnect Device</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            color: #f8fafc;
        }}
        .container {{
            background: #1e293b;
            border-radius: 20px;
            padding: 40px;
            max-width: 420px;
            text-align: center;
            box-shadow: 0 25px 50px rgba(0,0,0,0.5);
            border: 1px solid #334155;
        }}
        .logo {{ font-size: 3.5rem; margin-bottom: 15px; }}
        h1 {{ font-size: 1.8rem; margin-bottom: 8px; color: #f8fafc; }}
        .subtitle {{ color: #94a3b8; margin-bottom: 25px; font-size: 0.95rem; }}
        .info-box {{
            background: #334155;
            border-radius: 12px;
            padding: 20px;
            margin-bottom: 25px;
            text-align: left;
        }}
        .info-row {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 10px 0;
            border-bottom: 1px solid #475569;
        }}
        .info-row:last-child {{ border-bottom: none; }}
        .info-label {{ color: #94a3b8; font-size: 0.9rem; }}
        .info-value {{ font-weight: 600; display: flex; align-items: center; gap: 8px; }}
        .btn {{
            width: 100%;
            padding: 16px 30px;
            font-size: 1.1rem;
            font-weight: 600;
            border: none;
            border-radius: 12px;
            cursor: pointer;
            transition: all 0.2s;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 10px;
        }}
        .btn-primary {{
            background: linear-gradient(135deg, #3b82f6, #8b5cf6);
            color: white;
        }}
        .btn-primary:hover {{
            transform: translateY(-2px);
            box-shadow: 0 10px 30px rgba(59,130,246,0.4);
        }}
        .btn-primary:active {{ transform: translateY(0); }}
        .status {{
            margin-top: 20px;
            padding: 15px;
            border-radius: 10px;
            display: none;
            font-size: 0.95rem;
        }}
        .status.loading {{
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 10px;
            background: #334155;
        }}
        .status.error {{
            display: block;
            background: rgba(239,68,68,0.2);
            color: #ef4444;
        }}
        .spinner {{
            width: 20px;
            height: 20px;
            border: 3px solid #475569;
            border-top-color: #3b82f6;
            border-radius: 50%;
            animation: spin 1s linear infinite;
        }}
        @keyframes spin {{ to {{ transform: rotate(360deg); }} }}
        .security-note {{
            margin-top: 20px;
            padding: 12px;
            background: rgba(16,185,129,0.1);
            border-radius: 8px;
            font-size: 0.8rem;
            color: #10b981;
        }}
        .security-note strong {{ display: block; margin-bottom: 4px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="logo">🏠</div>
        <h1>Welcome Back</h1>
        <p class="subtitle">Reconnect this device to your Semptify account</p>
        
        <div class="info-box">
            <div class="info-row">
                <span class="info-label">Storage Provider</span>
                <span class="info-value">{provider_icon} {provider_display}</span>
            </div>
            <div class="info-row">
                <span class="info-label">Account Type</span>
                <span class="info-value" style="text-transform: capitalize;">🏷️ {role or 'User'}</span>
            </div>
            <div class="info-row">
                <span class="info-label">Account ID</span>
                <span class="info-value" style="font-family: 'SF Mono', Monaco, monospace; font-size: 0.85rem;">🔑 {user_id}</span>
            </div>
        </div>
        
        <button class="btn btn-primary" onclick="rehome()" id="rehomeBtn">
            <span>🔗</span> Connect This Device
        </button>
        
        <div class="status" id="status"></div>
        
        <div class="security-note">
            <strong>🔒 Secure Connection</strong>
            Your data stays encrypted in your {provider_display}. 
            Semptify never stores your files on external servers.
        </div>
    </div>
    
    <script>
        const USER_ID = "{user_id}";
        const SEMPTIFY_URL = "{base_url}";
        
        function rehome() {{
            const status = document.getElementById("status");
            const btn = document.getElementById("rehomeBtn");
            
            btn.disabled = true;
            btn.innerHTML = '<span class="spinner"></span> Connecting...';
            
            status.className = "status loading";
            status.innerHTML = '<span class="spinner"></span> Verifying your account...';
            
            // Small delay for UX, then redirect
            setTimeout(() => {{
                window.location.href = SEMPTIFY_URL + "/storage/rehome/" + USER_ID;
            }}, 800);
        }}
        
        // Check if we can reach Semptify
        fetch(SEMPTIFY_URL + "/health")
            .then(r => r.json())
            .catch(() => {{
                document.getElementById("status").className = "status error";
                document.getElementById("status").innerHTML = "⚠️ Cannot reach Semptify server. Make sure it's running at " + SEMPTIFY_URL;
            }});
    </script>
</body>
</html>'''


def generate_readme() -> str:
    """Generate README.txt for Semptify folder."""
    return '''╔══════════════════════════════════════════════════════════════╗
║                    SEMPTIFY 5.0                               ║
║              Your Legal Defense Vault                         ║
╚══════════════════════════════════════════════════════════════╝

⚠️  IMPORTANT: DO NOT DELETE THIS FOLDER

This folder contains your encrypted legal documents and 
authentication data for Semptify.

📁 FOLDER CONTENTS:
   • Vault/      - Your encrypted documents
   • Rehome.html - Click to reconnect on new devices
   • .auth/      - Authentication (hidden, do not modify)

🔒 SECURITY:
   • All files are encrypted with your personal key
   • Your data never leaves your cloud storage
   • Only you can decrypt your documents

🔄 RECONNECTING:
   If you need to use Semptify on a new device or browser:
   1. Open this folder in your cloud storage
   2. Click on "Rehome.html"
   3. You'll be automatically reconnected

📞 SUPPORT:
   Visit: https://semptify.com/help
   
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
'''


# =============================================================================
# Vault Manager Class
# =============================================================================

class VaultManager:
    """
    Manages the Semptify5.0 folder structure and token operations.
    Token NEVER leaves storage - all operations happen server-side.
    """
    
    def __init__(self, storage_provider, user_id: str, base_url: str):
        """
        Args:
            storage_provider: Storage provider instance (GoogleDrive, Dropbox, etc.)
            user_id: User ID like GU2L3wyfBy
            base_url: Semptify server URL for Rehome script
        """
        self.storage = storage_provider
        self.user_id = user_id
        self.base_url = base_url
        self._cached_token: Optional[MasterToken] = None
    
    async def initialize_vault(
        self, 
        provider_name: str,
        access_token: str = "",
        refresh_token: str = "",
        token_expires_at: str = "",
    ) -> dict:
        """
        Create the complete Semptify5.0 folder structure for a new user.
        Called after successful OAuth.

        Args:
            provider_name: Storage provider (google_drive, dropbox, onedrive)
            access_token: OAuth access token (stored encrypted as backup)
            refresh_token: OAuth refresh token (stored encrypted as backup)
            token_expires_at: When access token expires

        Returns:
            dict with created folders/files info
        """
        created = []

        # Create folder structure
        folders = [
            SEMPTIFY_ROOT,
            AUTH_FOLDER,
            VAULT_FOLDER,
            f"{VAULT_FOLDER}/documents",
            f"{VAULT_FOLDER}/forms",
            f"{VAULT_FOLDER}/exports",
        ]

        for folder in folders:
            try:
                await self.storage.create_folder(folder)
                created.append({"type": "folder", "path": folder})
            except Exception as e:
                # Folder might already exist
                pass

        # Generate and store master token WITH OAuth credentials
        token = MasterToken(
            token_id=secrets.token_urlsafe(32),
            user_id=self.user_id,
            created_at=datetime.now(timezone.utc).isoformat(),
            provider=provider_name,
            access_token=access_token,
            refresh_token=refresh_token,
            token_expires_at=token_expires_at,
        )

        encrypted_token = encrypt_token(token, self.user_id)
        
        # Store token and backup
        await self.storage.upload_file(
            file_content=encrypted_token,
            destination_path=AUTH_FOLDER,
            filename="token.enc",
            mime_type="application/octet-stream",
        )
        created.append({"type": "file", "path": TOKEN_FILE})
        
        await self.storage.upload_file(
            file_content=encrypted_token,
            destination_path=AUTH_FOLDER,
            filename="token.enc.backup",
            mime_type="application/octet-stream",
        )
        created.append({"type": "file", "path": TOKEN_BACKUP})
        
        # Initialize device keys
        device_keys = {"devices": [], "created_at": datetime.now(timezone.utc).isoformat()}
        await self.storage.upload_file(
            file_content=json.dumps(device_keys, indent=2).encode(),
            destination_path=AUTH_FOLDER,
            filename="device_keys.json",
            mime_type="application/json",
        )
        created.append({"type": "file", "path": DEVICE_KEYS_FILE})
        
        # Create Rehome.html
        rehome_html = generate_rehome_html(self.user_id, provider_name, self.base_url)
        await self.storage.upload_file(
            file_content=rehome_html.encode(),
            destination_path=SEMPTIFY_ROOT,
            filename="Rehome.html",
            mime_type="text/html",
        )
        created.append({"type": "file", "path": REHOME_FILE})
        
        # Create README
        readme = generate_readme()
        await self.storage.upload_file(
            file_content=readme.encode(),
            destination_path=SEMPTIFY_ROOT,
            filename="README.txt",
            mime_type="text/plain",
        )
        created.append({"type": "file", "path": README_FILE})
        
        return {
            "success": True,
            "user_id": self.user_id,
            "vault_path": SEMPTIFY_ROOT,
            "created": created,
        }
    
    async def get_token(self) -> Optional[MasterToken]:
        """
        Fetch and decrypt the master token from storage.
        Token is decrypted in-memory only - never sent to client.
        """
        if self._cached_token:
            return self._cached_token
        
        try:
            encrypted = await self.storage.download_file(TOKEN_FILE)
            token = decrypt_token(encrypted, self.user_id)
            token.record_validation()
            self._cached_token = token
            return token
        except Exception as e:
            # Try backup
            try:
                encrypted = await self.storage.download_file(TOKEN_BACKUP)
                token = decrypt_token(encrypted, self.user_id)
                token.record_validation()
                self._cached_token = token
                
                # Restore main token from backup
                await self.storage.upload_file(
                    file_content=encrypted,
                    destination_path=AUTH_FOLDER,
                    filename="token.enc",
                    mime_type="application/octet-stream",
                )
                
                return token
            except:
                return None
    
    async def validate_token(self) -> bool:
        """Check if user has valid token in storage."""
        token = await self.get_token()
        return token is not None

    async def get_oauth_credentials(self) -> Optional[Dict[str, str]]:
        """
        Get OAuth credentials from cloud storage.
        
        This is the RECOVERY path - used when database doesn't have the token
        (e.g., after Rehome, or database loss). The primary path is database lookup.
        
        Returns:
            dict with access_token, refresh_token, provider if available
        """
        token = await self.get_token()
        if not token or not token.access_token:
            return None
        
        return {
            "access_token": token.access_token,
            "refresh_token": token.refresh_token,
            "provider": token.provider,
            "token_expires_at": token.token_expires_at,
        }

    async def update_oauth_credentials(
        self, 
        access_token: str, 
        refresh_token: str = "",
        token_expires_at: str = "",
    ) -> bool:
        """
        Update OAuth credentials in cloud storage after token refresh.
        
        Call this whenever the access_token is refreshed to keep 
        cloud backup in sync with database.
        """
        try:
            token = await self.get_token()
            if not token:
                return False
            
            # Update credentials
            token.access_token = access_token
            if refresh_token:
                token.refresh_token = refresh_token
            if token_expires_at:
                token.token_expires_at = token_expires_at
            token.record_validation()
            
            # Re-encrypt and store
            encrypted = encrypt_token(token, self.user_id)
            
            await self.storage.upload_file(
                file_content=encrypted,
                destination_path=AUTH_FOLDER,
                filename="token.enc",
                mime_type="application/octet-stream",
            )
            
            # Update backup too
            await self.storage.upload_file(
                file_content=encrypted,
                destination_path=AUTH_FOLDER,
                filename="token.enc.backup",
                mime_type="application/octet-stream",
            )
            
            # Update cache
            self._cached_token = token
            return True
            
        except Exception:
            return False

    async def authorize_module(self, module: str) -> bool:
        """
        Check if token authorizes access to a specific module.
        This is how modules verify user has access.
        """
        token = await self.get_token()
        if not token:
            return False
        return token.authorize_module(module)
    
    async def register_device(self, device_id: str, device_name: str, user_agent: str = "") -> bool:
        """Register a new device as authorized."""
        try:
            # Load existing device keys
            content = await self.storage.download_file(DEVICE_KEYS_FILE)
            device_data = json.loads(content.decode())
            
            # Add new device
            now = datetime.now(timezone.utc).isoformat()
            new_device = {
                "device_id": device_id,
                "device_name": device_name,
                "authorized_at": now,
                "last_seen": now,
                "user_agent": user_agent,
            }
            
            # Check if device already registered
            existing = next((d for d in device_data["devices"] if d["device_id"] == device_id), None)
            if existing:
                existing["last_seen"] = now
            else:
                device_data["devices"].append(new_device)
            
            # Save updated device keys
            await self.storage.upload_file(
                file_content=json.dumps(device_data, indent=2).encode(),
                destination_path=AUTH_FOLDER,
                filename="device_keys.json",
                mime_type="application/json",
            )
            
            return True
        except Exception:
            return False
    
    async def vault_exists(self) -> bool:
        """Check if Semptify vault folder exists in storage."""
        try:
            # Try to list the auth folder
            await self.storage.download_file(TOKEN_FILE)
            return True
        except:
            return False


# =============================================================================
# Factory Function
# =============================================================================

def get_vault_manager(storage_provider, user_id: str, base_url: str) -> VaultManager:
    """Get a VaultManager instance for the user."""
    return VaultManager(storage_provider, user_id, base_url)
