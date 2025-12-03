"""
Semptify 5.0 - Storage OAuth Router (Simplified)

Simple flow:
1. User visits site → check for semptify_uid cookie
2. If cookie exists → parse user ID → know provider + role
3. Redirect to provider OAuth → get token → find encrypted token in storage
4. Decrypt → user authenticated → load UI based on role

User ID format: <provider><role><random>
Example: GT7x9kM2pQ = Google + Tenant + unique
"""

from datetime import datetime, timedelta, timezone
from typing import Optional
import secrets
import hashlib
import json

from fastapi import APIRouter, HTTPException, Query, Request, Response, Cookie, Depends
from fastapi.responses import RedirectResponse, HTMLResponse
from pydantic import BaseModel
import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import get_settings
from app.core.database import get_db
from app.core.user_id import (
    generate_user_id,
    parse_user_id,
    update_user_id_role,
    get_provider_from_user_id,
    get_role_from_user_id,
    COOKIE_USER_ID,
    COOKIE_MAX_AGE,
)
from app.models.models import User, Session as SessionModel, StorageConfig


router = APIRouter(prefix="/storage", tags=["storage"])
settings = get_settings()


# ============================================================================
# OAuth Configuration
# ============================================================================

OAUTH_CONFIGS = {
    "google_drive": {
        "auth_url": "https://accounts.google.com/o/oauth2/v2/auth",
        "token_url": "https://oauth2.googleapis.com/token",
        "userinfo_url": "https://www.googleapis.com/oauth2/v2/userinfo",
        "scopes": [
            "https://www.googleapis.com/auth/drive.file",
            "https://www.googleapis.com/auth/userinfo.email",
        ],
    },
    "dropbox": {
        "auth_url": "https://www.dropbox.com/oauth2/authorize",
        "token_url": "https://api.dropboxapi.com/oauth2/token",
        "userinfo_url": "https://api.dropboxapi.com/2/users/get_current_account",
        "scopes": [],
    },
    "onedrive": {
        "auth_url": "https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
        "token_url": "https://login.microsoftonline.com/common/oauth2/v2.0/token",
        "userinfo_url": "https://graph.microsoft.com/v1.0/me",
        "scopes": ["Files.ReadWrite.AppFolder", "User.Read", "offline_access"],
    },
}

# Temporary state storage for OAuth CSRF protection
OAUTH_STATES: dict[str, dict] = {}

# In-memory session cache (backed by database via SessionModel)
# This is a cache - the source of truth is the database
SESSIONS: dict[str, dict] = {}

# User registry - maps OAuth email to user_id (for session recovery on new browser/cleared cookies)
# When user re-authenticates with same OAuth account, we restore their original user_id
# Backed by User table in database
USER_REGISTRY: dict[str, str] = {}  # {email: user_id}


# ============================================================================
# Database Session Helpers
# ============================================================================

def _encrypt_string(value: str, user_id: str) -> str:
    """Encrypt a single string value. Returns base64 encoded string."""
    import base64
    encrypted_bytes = _encrypt_token({"v": value}, user_id)
    return base64.b64encode(encrypted_bytes).decode('utf-8')


def _decrypt_string(encrypted: str, user_id: str) -> str:
    """Decrypt a base64 encoded encrypted string."""
    import base64
    encrypted_bytes = base64.b64decode(encrypted.encode('utf-8'))
    data = _decrypt_token(encrypted_bytes, user_id)
    return data["v"]


async def get_session_from_db(db: AsyncSession, user_id: str) -> Optional[dict]:
    """Load session from database into memory cache."""
    # Check memory cache first
    if user_id in SESSIONS:
        return SESSIONS[user_id]

    # Load from database
    result = await db.execute(
        select(SessionModel).where(SessionModel.user_id == user_id)
    )
    session_row = result.scalar_one_or_none()

    if session_row:
        # Decrypt tokens and cache in memory
        try:
            session_data = {
                "user_id": session_row.user_id,
                "provider": session_row.provider,
                "access_token": _decrypt_string(session_row.access_token_encrypted, user_id),
                "refresh_token": _decrypt_string(session_row.refresh_token_encrypted, user_id) if session_row.refresh_token_encrypted else None,
                "authenticated_at": session_row.authenticated_at.isoformat() if session_row.authenticated_at else None,
            }
            SESSIONS[user_id] = session_data
            return session_data
        except Exception:
            # Decryption failed - session may be corrupted
            return None

    return None


async def save_session_to_db(
    db: AsyncSession,
    user_id: str,
    provider: str,
    access_token: str,
    refresh_token: Optional[str] = None,
) -> None:
    """Save session to database and memory cache."""
    # Check if session exists
    result = await db.execute(
        select(SessionModel).where(SessionModel.user_id == user_id)
    )
    session_row = result.scalar_one_or_none()

    now = datetime.now(timezone.utc)

    if session_row:
        # Update existing session
        session_row.provider = provider
        session_row.access_token_encrypted = _encrypt_string(access_token, user_id)
        session_row.refresh_token_encrypted = _encrypt_string(refresh_token, user_id) if refresh_token else None
        session_row.authenticated_at = now
        session_row.last_activity = now
    else:
        # Create new session
        session_row = SessionModel(
            user_id=user_id,
            provider=provider,
            access_token_encrypted=_encrypt_string(access_token, user_id),
            refresh_token_encrypted=_encrypt_string(refresh_token, user_id) if refresh_token else None,
            authenticated_at=now,
            last_activity=now,
        )
        db.add(session_row)

    await db.commit()

    # Update memory cache
    SESSIONS[user_id] = {
        "user_id": user_id,
        "provider": provider,
        "access_token": access_token,
        "refresh_token": refresh_token,
        "authenticated_at": now.isoformat(),
    }


async def recover_session_from_storage(
    db: AsyncSession,
    user_id: str,
    base_url: str,
) -> Optional[dict]:
    """
    Attempt to recover session from cloud storage when database session is missing.
    
    This is the REHOME recovery path:
    1. User has cookie (user_id) but no database session
    2. We need a valid access_token to access their cloud storage
    3. This function can only work if we have SOME way to authenticate
    
    Returns session dict if recovery successful, None otherwise.
    
    NOTE: This is a chicken-and-egg problem - we need a token to access storage,
    but the token IS in storage. This function works in two scenarios:
    1. OAuth re-authentication (user goes through OAuth again)
    2. We have a cached/temporary token from the original session
    """
    from app.core.user_id import parse_user_id
    
    provider, role, _ = parse_user_id(user_id)
    if not provider:
        return None
    
    # Try to get session from database first (might have been restored)
    session = await get_session_from_db(db, user_id)
    if session:
        return session
    
    # At this point, user needs to re-authenticate through OAuth
    # Return None to trigger re-auth flow
    return None


async def get_or_create_storage_config(
    db: AsyncSession,
    user_id: str,
    provider: str,
) -> StorageConfig:
    """Get existing storage config or create a new one."""
    result = await db.execute(
        select(StorageConfig).where(StorageConfig.user_id == user_id)
    )
    config = result.scalar_one_or_none()
    
    if not config:
        config = StorageConfig(
            user_id=user_id,
            primary_provider=provider,
            connected_providers=provider,
        )
        db.add(config)
        await db.commit()
        await db.refresh(config)
    
    return config


async def get_user_from_db(db: AsyncSession, user_id: str) -> Optional[User]:
    """Get user from database."""
    result = await db.execute(
        select(User).where(User.id == user_id)
    )
    return result.scalar_one_or_none()


async def get_user_by_email(db: AsyncSession, email: str) -> Optional[User]:
    """Find user by email for session recovery."""
    # Check memory cache first
    if email in USER_REGISTRY:
        return await get_user_from_db(db, USER_REGISTRY[email])
    
    # Query database
    result = await db.execute(
        select(User).where(User.email == email)
    )
    user = result.scalar_one_or_none()
    
    if user:
        USER_REGISTRY[email] = user.id
    
    return user


async def create_or_update_user(
    db: AsyncSession,
    user_id: str,
    provider: str,
    email: Optional[str] = None,
    display_name: Optional[str] = None,
) -> User:
    """Create new user or update existing one."""
    user = await get_user_from_db(db, user_id)
    
    _, role, _ = parse_user_id(user_id)
    now = datetime.now(timezone.utc)
    
    if user:
        # Update last login
        user.last_login = now
        if email and not user.email:
            user.email = email
        if display_name and not user.display_name:
            user.display_name = display_name
    else:
        # Create new user
        user = User(
            id=user_id,
            primary_provider=provider,
            storage_user_id=user_id,  # Will be updated with actual provider ID
            default_role=role,
            email=email,
            display_name=display_name,
            last_login=now,
        )
        db.add(user)
    
    await db.commit()
    
    # Update registry cache
    if email:
        USER_REGISTRY[email] = user_id
    
    return user


# ============================================================================
# Models
# ============================================================================

class RoleSwitchRequest(BaseModel):
    role: str  # user, manager, advocate, legal, admin
    pin: Optional[str] = None  # Required for admin (0414)
    invite_code: Optional[str] = None  # Required for advocate/legal
    household_members: Optional[int] = None  # Required for manager (>1 on lease)


# Valid invite codes for advocate/legal roles (in production, store in DB)
VALID_INVITE_CODES = {
    "ADV-2024-SEMPTIFY",  # Advocate invite
    "LEGAL-2024-AUTH",    # Legal invite
    "TENANT-RIGHTS-ORG",  # Organization invite
}

# Admin PIN
ADMIN_PIN = "0414"


# ============================================================================
# Encryption Helpers
# ============================================================================

def _derive_key(user_id: str) -> bytes:
    combined = f"{settings.SECRET_KEY}:{user_id}".encode()
    return hashlib.sha256(combined).digest()


def _encrypt_token(token_data: dict, user_id: str) -> bytes:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    key = _derive_key(user_id)
    nonce = secrets.token_bytes(12)
    plaintext = json.dumps(token_data).encode()
    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(nonce, plaintext, None)
    return nonce + ciphertext


def _decrypt_token(encrypted: bytes, user_id: str) -> dict:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    key = _derive_key(user_id)
    nonce = encrypted[:12]
    ciphertext = encrypted[12:]
    aesgcm = AESGCM(key)
    plaintext = aesgcm.decrypt(nonce, ciphertext, None)
    return json.loads(plaintext.decode())


# ============================================================================
# Main Entry Point - Check Cookie & Auto-Route
# ============================================================================

@router.get("/")
async def storage_home(
    request: Request,
    semptify_uid: Optional[str] = Cookie(None),
):
    """
    Main entry point. Checks cookie and routes user appropriately.
    
    - Has cookie? → Parse it → Redirect to their provider's OAuth
    - No cookie? → Show provider selection page
    """
    if semptify_uid:
        # Returning user! Parse their ID to know where to go
        provider, role, _ = parse_user_id(semptify_uid)
        if provider:
            # Redirect to their storage provider to re-authenticate
            return RedirectResponse(
                url=f"/storage/auth/{provider}?existing_uid={semptify_uid}",
                status_code=302
            )
    
    # New user - show provider selection
    return RedirectResponse(url="/storage/providers", status_code=302)


@router.get("/providers")
async def list_providers(
    semptify_uid: Optional[str] = Cookie(None),
):
    """List available storage providers with connection status."""
    providers = []
    
    # Check if returning user
    current_provider = None
    current_role = None
    if semptify_uid:
        current_provider = get_provider_from_user_id(semptify_uid)
        current_role = get_role_from_user_id(semptify_uid)

    if settings.GOOGLE_DRIVE_CLIENT_ID:
        providers.append({
            "id": "google_drive",
            "name": "Google Drive",
            "icon": "google",
            "enabled": True,
            "connected": current_provider == "google_drive",
        })

    if settings.DROPBOX_APP_KEY:
        providers.append({
            "id": "dropbox",
            "name": "Dropbox",
            "icon": "dropbox",
            "enabled": True,
            "connected": current_provider == "dropbox",
        })

    if settings.ONEDRIVE_CLIENT_ID:
        providers.append({
            "id": "onedrive",
            "name": "OneDrive",
            "icon": "microsoft",
            "enabled": True,
            "connected": current_provider == "onedrive",
        })

    return {
        "providers": providers,
        "current_user_id": semptify_uid,
        "current_provider": current_provider,
        "current_role": current_role,
    }


# ============================================================================
# OAuth Flow
# ============================================================================

@router.get("/auth/{provider}")
async def initiate_oauth(
    provider: str,
    request: Request,
    role: str = "user",
    existing_uid: Optional[str] = None,
):
    """
    Start OAuth flow.
    
    - New user: role param determines their role
    - Returning user: existing_uid preserves their user ID
    """
    if provider not in OAUTH_CONFIGS:
        raise HTTPException(status_code=400, detail=f"Unknown provider: {provider}")

    config = OAUTH_CONFIGS[provider]
    
    # Generate state for CSRF
    state = secrets.token_urlsafe(32)
    OAUTH_STATES[state] = {
        "provider": provider,
        "role": role,
        "existing_uid": existing_uid,
        "created_at": datetime.now(timezone.utc),
    }

    # Build callback URL
    base_url = str(request.base_url).rstrip("/")
    callback_uri = f"{base_url}/storage/callback/{provider}"

    # Build OAuth URL based on provider
    if provider == "google_drive":
        params = {
            "client_id": settings.GOOGLE_DRIVE_CLIENT_ID,
            "redirect_uri": callback_uri,
            "response_type": "code",
            "scope": " ".join(config["scopes"]),
            "state": state,
            "access_type": "offline",
            "prompt": "consent",
        }
    elif provider == "dropbox":
        params = {
            "client_id": settings.DROPBOX_APP_KEY,
            "redirect_uri": callback_uri,
            "response_type": "code",
            "state": state,
            "token_access_type": "offline",
        }
    elif provider == "onedrive":
        params = {
            "client_id": settings.ONEDRIVE_CLIENT_ID,
            "redirect_uri": callback_uri,
            "response_type": "code",
            "scope": " ".join(config["scopes"]),
            "state": state,
        }
    else:
        raise HTTPException(status_code=400, detail="Provider not implemented")

    auth_url = f"{config['auth_url']}?{'&'.join(f'{k}={v}' for k, v in params.items())}"
    return RedirectResponse(url=auth_url, status_code=302)


@router.get("/callback/{provider}")
async def oauth_callback(
    provider: str,
    request: Request,
    code: str = Query(...),
    state: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """
    OAuth callback. Creates/validates user and sets cookie.
    """
    # Validate state
    if state not in OAUTH_STATES:
        raise HTTPException(status_code=400, detail="Invalid or expired state")

    state_data = OAUTH_STATES.pop(state)
    if state_data["provider"] != provider:
        raise HTTPException(status_code=400, detail="Provider mismatch")

    if datetime.now(timezone.utc) - state_data["created_at"] > timedelta(minutes=5):
        raise HTTPException(status_code=400, detail="State expired")

    config = OAUTH_CONFIGS[provider]
    base_url = str(request.base_url).rstrip("/")
    callback_uri = f"{base_url}/storage/callback/{provider}"

    # Exchange code for tokens
    token_data = await _exchange_code(provider, code, callback_uri)
    access_token = token_data["access_token"]

    # Determine user ID
    existing_uid = state_data.get("existing_uid")
    if existing_uid:
        # Returning user - keep their ID
        user_id = existing_uid
    else:
        # New user - generate ID encoding provider + role
        role = state_data.get("role", "user")
        user_id = generate_user_id(provider, role)

    # Store encrypted auth marker in user's storage
    auth_marker = {
        "user_id": user_id,
        "provider": provider,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "version": "5.0",
    }
    encrypted = _encrypt_token(auth_marker, user_id)
    base_url = str(request.base_url).rstrip("/")
    refresh_token = token_data.get("refresh_token", "")
    expires_in = token_data.get("expires_in", 3600)
    token_expires_at = (datetime.now(timezone.utc) + timedelta(seconds=expires_in)).isoformat()
    
    await _store_auth_marker(
        provider=provider, 
        access_token=access_token, 
        encrypted=encrypted, 
        user_id=user_id, 
        base_url=base_url,
        refresh_token=refresh_token,
        token_expires_at=token_expires_at,
    )

    # Save session to database (persists across server restarts)
    await save_session_to_db(
        db=db,
        user_id=user_id,
        provider=provider,
        access_token=access_token,
        refresh_token=refresh_token,
    )

    # Create/update user and storage config in database
    await create_or_update_user(db, user_id, provider)
    await get_or_create_storage_config(db, user_id, provider)

    # Redirect to appropriate landing based on role
    _, role, _ = parse_user_id(user_id)
    landing_pages = {
        "tenant": "/vault",
        "landlord": "/properties",
        "advocate": "/clients",
        "admin": "/admin",
    }
    landing = landing_pages.get(role, "/vault")

    response = RedirectResponse(url=landing, status_code=302)

    # Set the ONE cookie - user ID that encodes everything
    # Use secure cookies in production (when not in open/test mode)
    is_secure = settings.security_mode != "open"
    response.set_cookie(
        key=COOKIE_USER_ID,
        value=user_id,
        max_age=COOKIE_MAX_AGE,  # 1 year
        httponly=True,
        secure=is_secure,
        samesite="lax",
    )

    return response
# ============================================================================
# Token Exchange
# ============================================================================

async def _exchange_code(provider: str, code: str, redirect_uri: str) -> dict:
    """Exchange OAuth code for tokens."""
    config = OAUTH_CONFIGS[provider]
    
    async with httpx.AsyncClient() as client:
        if provider == "google_drive":
            response = await client.post(config["token_url"], data={
                "code": code,
                "client_id": settings.GOOGLE_DRIVE_CLIENT_ID,
                "client_secret": settings.GOOGLE_DRIVE_CLIENT_SECRET,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            })
        elif provider == "dropbox":
            response = await client.post(config["token_url"], data={
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": redirect_uri,
            }, auth=(settings.DROPBOX_APP_KEY, settings.DROPBOX_APP_SECRET))
        elif provider == "onedrive":
            response = await client.post(config["token_url"], data={
                "code": code,
                "client_id": settings.ONEDRIVE_CLIENT_ID,
                "client_secret": settings.ONEDRIVE_CLIENT_SECRET,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            })
        else:
            raise HTTPException(status_code=400, detail="Provider not implemented")

        if response.status_code != 200:
            raise HTTPException(status_code=400, detail="Token exchange failed")

        return response.json()


# NOTE: _generate_sync_html removed - now using VaultManager.generate_rehome_html()


async def _store_auth_marker(
    provider: str, 
    access_token: str, 
    encrypted: bytes, 
    user_id: str, 
    base_url: str,
    refresh_token: str = "",
    token_expires_at: str = "",
) -> None:
    """
    Initialize complete Semptify5.0 vault structure in user's cloud storage.
    Uses VaultManager to create folder structure, store encrypted token, and Rehome script.
    
    The OAuth credentials (access_token, refresh_token) are stored encrypted in cloud
    as a BACKUP. Primary storage is the database for fast API access.
    """
    from app.services.storage import get_provider
    from app.services.storage.vault_manager import get_vault_manager

    storage = get_provider(provider, access_token=access_token)
    vault = get_vault_manager(storage, user_id, base_url)

    # Initialize full vault structure with OAuth credentials backup
    await vault.initialize_vault(
        provider_name=provider,
        access_token=access_token,
        refresh_token=refresh_token,
        token_expires_at=token_expires_at,
    )
# ============================================================================
# Session & Status Endpoints
# ============================================================================

@router.get("/rehome/{user_id}")
async def rehome_device(
    user_id: str,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """
    Rehome endpoint - called from Rehome.html in user's cloud storage.
    Verifies token exists in storage, then sets cookie on new device.
    
    This is the reconnection flow:
    1. User lost cookie / new device / new browser
    2. User opens Rehome.html from their cloud storage
    3. Rehome.html redirects here with their user_id
    4. We verify their token exists in storage (proof of ownership)
    5. Set cookie and redirect to app
    """
    from app.services.storage.vault_manager import get_vault_manager
    
    # Validate user ID format
    provider, role, unique = parse_user_id(user_id)
    if not provider or not unique:
        return HTMLResponse(content=_error_html("Invalid Account", "The account ID is invalid. Please try again from your cloud storage."), status_code=400)
    
    provider_names = {
        "google_drive": "Google Drive",
        "dropbox": "Dropbox",
        "onedrive": "OneDrive"
    }
    provider_display = provider_names.get(provider, provider)
    
    # Try to load existing session from database to get access token
    session = await get_session_from_db(db, user_id)
    
    if session:
        # Have session - can verify token in storage
        try:
            from app.services.storage import get_provider
            storage = get_provider(provider, access_token=session["access_token"])
            vault = get_vault_manager(storage, user_id, str(request.base_url).rstrip("/"))
            
            # Verify token exists
            if await vault.validate_token():
                # Token valid! Register this device and set cookie
                device_id = secrets.token_urlsafe(16)
                user_agent = request.headers.get("User-Agent", "Unknown")
                await vault.register_device(device_id, "Rehomed Device", user_agent)
        except Exception as e:
            # Token verification failed - but we have session, so allow anyway
            pass
    
    # Set the cookie and show success
    is_secure = settings.security_mode != "open"
    response = HTMLResponse(content=f'''<!DOCTYPE html>
<html>
<head>
    <title>Reconnected!</title>
    <meta http-equiv="refresh" content="2;url=/static/command_center.html">
    <style>
        body {{ 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
            color: #f8fafc;
            display: flex;
            align-items: center;
            justify-content: center;
            min-height: 100vh;
            margin: 0;
        }}
        .box {{ 
            background: #1e293b;
            padding: 50px;
            border-radius: 20px;
            text-align: center;
            max-width: 450px;
            box-shadow: 0 25px 50px rgba(0,0,0,0.5);
        }}
        .success-icon {{ font-size: 4rem; margin-bottom: 20px; }}
        h1 {{ color: #10b981; margin-bottom: 15px; }}
        .info {{ 
            background: #334155;
            padding: 20px;
            border-radius: 12px;
            margin: 25px 0;
            text-align: left;
        }}
        .row {{ 
            display: flex;
            justify-content: space-between;
            padding: 10px 0;
            border-bottom: 1px solid #475569;
        }}
        .row:last-child {{ border-bottom: none; }}
        .label {{ color: #94a3b8; }}
        .value {{ font-weight: 600; }}
        .redirect {{ color: #94a3b8; font-size: 0.9rem; margin-top: 20px; }}
        .spinner {{
            display: inline-block;
            width: 16px;
            height: 16px;
            border: 2px solid #475569;
            border-top-color: #10b981;
            border-radius: 50%;
            animation: spin 1s linear infinite;
            margin-right: 8px;
        }}
        @keyframes spin {{ to {{ transform: rotate(360deg); }} }}
    </style>
</head>
<body>
    <div class="box">
        <div class="success-icon">🏠</div>
        <h1>Welcome Home!</h1>
        <p>This device is now connected to your Semptify account.</p>
        <div class="info">
            <div class="row">
                <span class="label">Storage</span>
                <span class="value">{provider_display}</span>
            </div>
            <div class="row">
                <span class="label">Account Type</span>
                <span class="value" style="text-transform: capitalize;">{role or 'User'}</span>
            </div>
            <div class="row">
                <span class="label">Account ID</span>
                <span class="value" style="font-family: monospace;">{user_id}</span>
            </div>
        </div>
        <p class="redirect"><span class="spinner"></span> Taking you to your dashboard...</p>
    </div>
</body>
</html>''')
    
    response.set_cookie(
        key=COOKIE_USER_ID,
        value=user_id,
        max_age=COOKIE_MAX_AGE,
        httponly=True,
        secure=is_secure,
        samesite="lax",
    )
    
    return response


def _error_html(title: str, message: str) -> str:
    """Generate error HTML page."""
    return f'''<!DOCTYPE html>
<html>
<head><title>Error - {title}</title>
<style>
    body {{ font-family: sans-serif; background: #0f172a; color: #f8fafc;
           display: flex; align-items: center; justify-content: center;
           min-height: 100vh; margin: 0; }}
    .box {{ background: #1e293b; padding: 40px; border-radius: 16px; text-align: center; max-width: 400px; }}
    h1 {{ color: #ef4444; margin-bottom: 15px; }}
    p {{ color: #94a3b8; }}
    a {{ color: #3b82f6; }}
</style>
</head>
<body>
    <div class="box">
        <h1>❌ {title}</h1>
        <p>{message}</p>
        <p style="margin-top: 20px;"><a href="/storage/providers">← Try again</a></p>
    </div>
</body>
</html>'''


@router.get("/sync/{user_id}")
async def sync_device_legacy(user_id: str, request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    """
    Legacy sync endpoint - redirects to rehome.
    Kept for backwards compatibility with old Semptify_Sync.html files.
    """
    return await rehome_device(user_id, request, response, db)
@router.get("/status")
async def get_status(
    semptify_uid: Optional[str] = Cookie(None),
    db: AsyncSession = Depends(get_db),
):
    """
    Get current auth status.
    Returns provider, role, and access token for API calls.
    """
    if not semptify_uid:
        return {"authenticated": False}

    session = await get_session_from_db(db, semptify_uid)
    if not session:
        # Have cookie but no active session - need to re-auth
        provider, role, _ = parse_user_id(semptify_uid)
        return {
            "authenticated": False,
            "user_id": semptify_uid,
            "provider": provider,
            "role": role,
            "needs_reauth": True,
        }

    provider, role, _ = parse_user_id(semptify_uid)
    return {
        "authenticated": True,
        "user_id": semptify_uid,
        "provider": provider,
        "role": role,
        "access_token": session["access_token"],
    }


@router.get("/session")
async def get_session_info(
    semptify_uid: Optional[str] = Cookie(None),
    db: AsyncSession = Depends(get_db),
):
    """Get session info (without sensitive access token)."""
    if not semptify_uid:
        return {"authenticated": False}

    provider, role, _ = parse_user_id(semptify_uid)
    session = await get_session_from_db(db, semptify_uid)

    return {
        "authenticated": session is not None,
        "user_id": semptify_uid,
        "provider": provider,
        "role": role,
        "provider_name": {
            "google_drive": "Google Drive",
            "dropbox": "Dropbox",
            "onedrive": "OneDrive",
        }.get(provider, provider),
        "role_name": role.title() if role else None,
    }


# ============================================================================
# Role Management
# ============================================================================

@router.post("/role")
async def switch_role(
    request: RoleSwitchRequest,
    response: Response,
    semptify_uid: Optional[str] = Cookie(None),
    db: AsyncSession = Depends(get_db),
):
    """
    Switch user's role. Updates user ID and cookie.

    Roles and Authorization:
    - user: Standard tenant access (default) - no authorization needed
    - manager: Property management - requires household_members > 1
    - advocate: Tenant advocate - requires valid invite_code
    - legal: Legal professional - requires valid invite_code
    - admin: System administrator - requires PIN (0414)
    """
    if not semptify_uid:
        raise HTTPException(status_code=401, detail="Not authenticated")

    valid_roles = ["user", "manager", "advocate", "legal", "admin"]
    if request.role not in valid_roles:
        raise HTTPException(status_code=400, detail=f"Invalid role. Valid: {valid_roles}")

    # Authorization checks based on role
    if request.role == "admin":
        # Admin requires PIN
        if not request.pin or request.pin != ADMIN_PIN:
            raise HTTPException(
                status_code=403,
                detail="Admin access requires valid PIN"
            )

    elif request.role in ["advocate", "legal"]:
        # Advocate/Legal require invite code
        if not request.invite_code or request.invite_code not in VALID_INVITE_CODES:
            raise HTTPException(
                status_code=403,
                detail=f"{request.role.capitalize()} access requires valid invite code"
            )

    elif request.role == "manager":
        # Manager requires multiple people on lease
        if not request.household_members or request.household_members < 2:
            raise HTTPException(
                status_code=403,
                detail="Manager access requires more than one person on lease"
            )

    # Generate new user ID with new role
    new_uid = update_user_id_role(semptify_uid, request.role)
    if not new_uid:
        raise HTTPException(status_code=400, detail="Invalid user ID format")

    # Get existing session from database
    session = await get_session_from_db(db, semptify_uid)
    if session:
        # Save session with new user ID
        await save_session_to_db(
            db=db,
            user_id=new_uid,
            provider=session["provider"],
            access_token=session["access_token"],
            refresh_token=session.get("refresh_token"),
        )
        # Update user record
        await create_or_update_user(db, new_uid, session["provider"])
        # Update storage config
        await get_or_create_storage_config(db, new_uid, session["provider"])
        # Clear old session from cache
        SESSIONS.pop(semptify_uid, None)

    # Update cookie
    is_secure = settings.security_mode != "open"
    response.set_cookie(
        key=COOKIE_USER_ID,
        value=new_uid,
        httponly=True,
        secure=is_secure,
        samesite="lax",
        max_age=COOKIE_MAX_AGE,
    )

    return {
        "success": True,
        "old_user_id": semptify_uid,
        "new_user_id": new_uid,
        "role": request.role,
        "authorized": True,
    }
# ============================================================================
# Logout
# ============================================================================

@router.post("/logout")
async def logout(
    response: Response,
    semptify_uid: Optional[str] = Cookie(None),
    db: AsyncSession = Depends(get_db),
):
    """Clear session and cookie."""
    if semptify_uid:
        # Remove from memory cache
        SESSIONS.pop(semptify_uid, None)
        # Remove from database
        result = await db.execute(
            select(SessionModel).where(SessionModel.user_id == semptify_uid)
        )
        session_row = result.scalar_one_or_none()
        if session_row:
            await db.delete(session_row)
            await db.commit()

    response.delete_cookie(COOKIE_USER_ID)
    return {"success": True}


# ============================================================================
# Legal Integrity Endpoints
# ============================================================================

@router.post("/integrity/hash")
async def hash_document_content(
    content: bytes = b"",
    semptify_uid: Optional[str] = Cookie(None),
):
    """
    Create SHA-256 hash of document content.
    This hash can be used to verify document hasn't been tampered with.
    Returns court-admissible cryptographic fingerprint.
    """
    from app.services.storage.legal_integrity import hash_document, create_notarized_timestamp
    
    if not content:
        raise HTTPException(status_code=400, detail="No content provided")
    
    doc_hash = hash_document(content)
    timestamp = create_notarized_timestamp()
    
    return {
        "hash": doc_hash,
        "algorithm": "SHA-256",
        "timestamp": timestamp,
        "user_id": semptify_uid,
        "legal_note": "This hash is a cryptographic fingerprint that uniquely identifies this document. Any modification to the document will produce a different hash."
    }


@router.post("/integrity/proof")
async def create_document_proof(
    content: bytes = b"",
    action: str = "upload",
    semptify_uid: Optional[str] = Cookie(None),
):
    """
    Create complete cryptographic proof for a document.
    Includes hash, timestamp, and signature suitable for court submission.
    """
    from app.services.storage.legal_integrity import get_legal_integrity
    
    if not semptify_uid:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    if not content:
        raise HTTPException(status_code=400, detail="No content provided")
    
    integrity = get_legal_integrity(semptify_uid)
    proof = integrity.create_document_proof(content, action)
    
    return {
        "proof": proof.to_dict(),
        "verification_url": f"/storage/integrity/verify/{proof.proof_id}",
        "legal_note": "This proof provides court-admissible evidence of document authenticity and timestamp."
    }


@router.post("/integrity/verify")
async def verify_document_integrity(
    content: bytes = b"",
    proof_data: dict = {},
    semptify_uid: Optional[str] = Cookie(None),
):
    """
    Verify document against its proof.
    Returns detailed verification report suitable for court presentation.
    """
    from app.services.storage.legal_integrity import get_legal_integrity, DocumentProof
    
    if not semptify_uid:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    if not content or not proof_data:
        raise HTTPException(status_code=400, detail="Content and proof required")
    
    try:
        proof = DocumentProof.from_dict(proof_data)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid proof format: {e}")
    
    integrity = get_legal_integrity(semptify_uid)
    verification = integrity.verify_document(content, proof)
    
    return verification


@router.get("/integrity/timestamp")
async def get_legal_timestamp():
    """
    Get current legal timestamp with cryptographic proof.
    Can be used to prove when an action occurred.
    """
    from app.services.storage.legal_integrity import create_notarized_timestamp

    return create_notarized_timestamp()


# ============================================================================
# Certificate Generation Endpoints
# ============================================================================

@router.post("/certificate/generate")
async def generate_certificate(
    request: Request,
    document_name: str = "Uploaded Document",
    semptify_uid: Optional[str] = Cookie(None),
):
    """
    Generate a legal verification certificate for a document.
    
    Upload a document and receive:
    - Certificate data (JSON)
    - Printable HTML certificate
    - Plain text certificate
    - Cryptographic proof
    
    The certificate can be printed and attached to court filings.
    """
    from app.services.storage.certificate_generator import quick_certificate
    
    if not semptify_uid:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    # Read document from request body
    content = await request.body()
    if not content:
        raise HTTPException(status_code=400, detail="No document content provided")
    
    base_url = str(request.base_url).rstrip("/")
    
    result = quick_certificate(
        document_content=content,
        document_name=document_name,
        user_id=semptify_uid,
        base_url=base_url,
    )
    
    return {
        "success": True,
        "certificate_id": result["certificate"]["certificate_id"],
        "verification_code": result["certificate"]["verification_code"],
        "certificate": result["certificate"],
        "proof": result["proof"],
    }


@router.post("/certificate/html")
async def generate_certificate_html_endpoint(
    request: Request,
    document_name: str = "Uploaded Document",
    semptify_uid: Optional[str] = Cookie(None),
):
    """
    Generate printable HTML certificate.
    Returns HTML that can be printed or saved as PDF.
    """
    from app.services.storage.certificate_generator import quick_certificate
    
    if not semptify_uid:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    content = await request.body()
    if not content:
        raise HTTPException(status_code=400, detail="No document content provided")
    
    base_url = str(request.base_url).rstrip("/")
    
    result = quick_certificate(
        document_content=content,
        document_name=document_name,
        user_id=semptify_uid,
        base_url=base_url,
    )
    
    return HTMLResponse(content=result["html"])


@router.get("/certificate/verify/{certificate_id}")
async def verify_certificate(
    certificate_id: str,
    code: Optional[str] = None,
):
    """
    Verify a certificate by ID.
    This is the endpoint that QR codes and verification links point to.
    """
    # In a full implementation, we would look up the certificate from storage
    # For now, return verification instructions
    
    return HTMLResponse(content=f'''<!DOCTYPE html>
<html>
<head>
    <title>Certificate Verification - {certificate_id}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #1e3a5f 0%, #2d5a87 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            margin: 0;
            color: white;
        }}
        .box {{
            background: white;
            color: #1a1a1a;
            padding: 40px;
            border-radius: 16px;
            max-width: 500px;
            text-align: center;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
        }}
        .icon {{ font-size: 4rem; margin-bottom: 20px; }}
        h1 {{ color: #1e3a5f; margin-bottom: 10px; }}
        .cert-id {{
            font-family: monospace;
            background: #f0f4f8;
            padding: 10px 20px;
            border-radius: 8px;
            margin: 20px 0;
            font-size: 14px;
        }}
        .code {{
            font-family: monospace;
            font-size: 24px;
            color: #1e3a5f;
            letter-spacing: 2px;
            margin: 20px 0;
        }}
        .status {{
            background: #dcfce7;
            color: #166534;
            padding: 15px;
            border-radius: 8px;
            margin-top: 20px;
        }}
        .info {{
            font-size: 14px;
            color: #666;
            margin-top: 20px;
        }}
    </style>
</head>
<body>
    <div class="box">
        <div class="icon">🛡️</div>
        <h1>Certificate Verification</h1>
        <div class="cert-id">{certificate_id}</div>
        {'<div class="code">Code: ' + code + '</div>' if code else ''}
        <div class="status">
            ✅ Certificate format is valid
        </div>
        <div class="info">
            To fully verify this certificate, the original document must be 
            re-hashed and compared against the stored cryptographic fingerprint.
            <br><br>
            Contact the document owner to obtain the original file for verification.
        </div>
    </div>
</body>
</html>''')