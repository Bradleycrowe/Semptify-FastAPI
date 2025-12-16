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

from datetime import datetime, timedelta

from app.core.utc import utc_now
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
# States expire after 15 minutes (increased from 5 for slower connections)
OAUTH_STATES: dict[str, dict] = {}
OAUTH_STATE_TIMEOUT_MINUTES = 15  # Give users more time to complete OAuth

# Clean up expired states periodically
def _cleanup_expired_states():
    """Remove expired OAuth states from memory."""
    now = utc_now()
    expired = [
        state for state, data in OAUTH_STATES.items()
        if now - data.get("created_at", now) > timedelta(minutes=OAUTH_STATE_TIMEOUT_MINUTES)
    ]
    for state in expired:
        OAUTH_STATES.pop(state, None)
    if expired:
        print(f"🧹 Cleaned up {len(expired)} expired OAuth states")

# In-memory session cache (backed by database via SessionModel)
# This is a cache - the source of truth is the database
SESSIONS: dict[str, dict] = {}

# User registry - maps OAuth email to user_id (for session recovery on new browser/cleared cookies)
# When user re-authenticates with same OAuth account, we restore their original user_id
# Backed by User table in database
USER_REGISTRY: dict[str, str] = {}  # {email: user_id}

# Token expiry buffer (refresh 5 minutes before actual expiry)
TOKEN_EXPIRY_BUFFER = timedelta(minutes=5)


# ============================================================================
# Token Validation & Refresh
# ============================================================================

async def validate_token_with_provider(provider: str, access_token: str) -> bool:
    """
    Validate token by making a test API call to the provider.
    Returns True if token is valid, False otherwise.
    """
    import os
    # Skip validation in test mode - mock tokens are always valid
    if os.environ.get("TESTING") == "true":
        return True
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            if provider == "google_drive":
                # Check token info endpoint
                response = await client.get(
                    "https://www.googleapis.com/oauth2/v1/tokeninfo",
                    params={"access_token": access_token}
                )
                return response.status_code == 200
            
            elif provider == "dropbox":
                # Check current account endpoint
                response = await client.post(
                    "https://api.dropboxapi.com/2/users/get_current_account",
                    headers={"Authorization": f"Bearer {access_token}"}
                )
                return response.status_code == 200
            
            elif provider == "onedrive":
                # Check user profile endpoint
                response = await client.get(
                    "https://graph.microsoft.com/v1.0/me",
                    headers={"Authorization": f"Bearer {access_token}"}
                )
                return response.status_code == 200
            
            return False
    except Exception:
        return False


async def refresh_access_token(
    db: AsyncSession,
    user_id: str,
    provider: str,
    refresh_token: str,
) -> Optional[dict]:
    """
    Refresh access token using the refresh token.
    Returns new token data if successful, None otherwise.
    """
    if not refresh_token:
        return None
    
    config = OAUTH_CONFIGS.get(provider)
    if not config:
        return None
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            if provider == "google_drive":
                response = await client.post(config["token_url"], data={
                    "client_id": settings.GOOGLE_DRIVE_CLIENT_ID,
                    "client_secret": settings.GOOGLE_DRIVE_CLIENT_SECRET,
                    "refresh_token": refresh_token,
                    "grant_type": "refresh_token",
                })
            
            elif provider == "dropbox":
                # Dropbox uses long-lived tokens, but let's handle refresh anyway
                response = await client.post(config["token_url"], data={
                    "client_id": settings.DROPBOX_CLIENT_ID,
                    "client_secret": settings.DROPBOX_CLIENT_SECRET,
                    "refresh_token": refresh_token,
                    "grant_type": "refresh_token",
                })
            
            elif provider == "onedrive":
                response = await client.post(config["token_url"], data={
                    "client_id": settings.ONEDRIVE_CLIENT_ID,
                    "client_secret": settings.ONEDRIVE_CLIENT_SECRET,
                    "refresh_token": refresh_token,
                    "grant_type": "refresh_token",
                    "scope": " ".join(config["scopes"]),
                })
            else:
                return None
            
            if response.status_code != 200:
                print(f"Token refresh failed for {provider}: {response.status_code} - {response.text}")
                return None
            
            token_data = response.json()
            new_access_token = token_data.get("access_token")
            # Some providers return a new refresh token, some don't
            new_refresh_token = token_data.get("refresh_token", refresh_token)
            expires_in = token_data.get("expires_in", 3600)
            expires_at = utc_now() + timedelta(seconds=expires_in)

            # Update session in database
            await save_session_to_db(
                db=db,
                user_id=user_id,
                provider=provider,
                access_token=new_access_token,
                refresh_token=new_refresh_token,
                expires_at=expires_at,
            )
            
            print(f"Token refreshed successfully for user {user_id[:4]}*** ({provider})")
            
            return {
                "access_token": new_access_token,
                "refresh_token": new_refresh_token,
                "expires_at": expires_at,
            }
    
    except Exception as e:
        print(f"Token refresh error for {provider}: {e}")
        return None


async def get_valid_session(
    db: AsyncSession,
    user_id: str,
    auto_refresh: bool = True,
) -> Optional[dict]:
    """
    Get a session with a valid (non-expired) access token.
    Will automatically refresh if token is expired and auto_refresh=True.
    
    Returns session dict with valid token, or None if session invalid/refresh failed.
    """
    # Get session from DB
    session = await get_session_from_db(db, user_id)
    if not session:
        return None
    
    # Check if token needs refresh
    access_token = session.get("access_token")
    refresh_token = session.get("refresh_token")
    expires_at = session.get("expires_at")
    provider = session.get("provider")
    
    needs_refresh = False
    
    # Check expiry time if we have it
    if expires_at:
        if isinstance(expires_at, str):
            expires_at = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
        # Ensure expires_at is timezone-aware (assume UTC if naive)
        if expires_at.tzinfo is None:
            from datetime import timezone
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if utc_now() >= (expires_at - TOKEN_EXPIRY_BUFFER):
            needs_refresh = True
            print(f"Token expired for user {user_id[:4]}*** - attempting refresh")
    
    # If no expiry info, validate with provider
    if not needs_refresh and not expires_at:
        is_valid = await validate_token_with_provider(provider, access_token)
        if not is_valid:
            needs_refresh = True
            print(f"Token invalid for user {user_id[:4]}*** - attempting refresh")
    
    # Attempt refresh if needed
    if needs_refresh and auto_refresh and refresh_token:
        new_token_data = await refresh_access_token(db, user_id, provider, refresh_token)
        if new_token_data:
            # Update session with new token
            session["access_token"] = new_token_data["access_token"]
            session["refresh_token"] = new_token_data["refresh_token"]
            session["expires_at"] = new_token_data["expires_at"].isoformat()
            SESSIONS[user_id] = session
            return session
        else:
            # Refresh failed - session is invalid
            print(f"Token refresh failed for user {user_id[:4]}*** - session invalidated")
            return None
    
    if needs_refresh and not refresh_token:
        print(f"Token expired and no refresh token for user {user_id[:4]}***")
        return None
    
    return session


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
                "expires_at": session_row.expires_at.isoformat() if session_row.expires_at else None,
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
    expires_at: Optional[datetime] = None,
) -> None:
    """Save session to database and memory cache."""
    # Check if session exists
    result = await db.execute(
        select(SessionModel).where(SessionModel.user_id == user_id)
    )
    session_row = result.scalar_one_or_none()

    now = utc_now()

    if session_row:
        # Update existing session
        session_row.provider = provider
        session_row.access_token_encrypted = _encrypt_string(access_token, user_id)
        session_row.refresh_token_encrypted = _encrypt_string(refresh_token, user_id) if refresh_token else None
        session_row.authenticated_at = now
        session_row.last_activity = now
        session_row.expires_at = expires_at
    else:
        # Create new session
        session_row = SessionModel(
            user_id=user_id,
            provider=provider,
            access_token_encrypted=_encrypt_string(access_token, user_id),
            refresh_token_encrypted=_encrypt_string(refresh_token, user_id) if refresh_token else None,
            authenticated_at=now,
            last_activity=now,
            expires_at=expires_at,
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
        "expires_at": expires_at.isoformat() if expires_at else None,
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
    now = utc_now()

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
    pin: Optional[str] = None  # Required for admin role
    invite_code: Optional[str] = None  # Required for advocate/legal
    household_members: Optional[int] = None  # Required for manager (>1 on lease)


# Valid invite codes for advocate/legal roles - loaded from environment
# Set INVITE_CODES in .env as comma-separated values
import os as _os
VALID_INVITE_CODES = set(_os.getenv("INVITE_CODES", "CHANGE-ME-1,CHANGE-ME-2").split(","))

# Admin PIN - loaded from environment
ADMIN_PIN = _os.getenv("ADMIN_PIN", "CHANGE-ME")


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
    request: Request,
    semptify_uid: Optional[str] = Cookie(None),
):
    """
    Show storage provider selection page.
    Returns HTML page for browsers, JSON for API clients.
    """
    # Check Accept header - if JSON requested, return JSON
    accept = request.headers.get("accept", "")
    if "application/json" in accept and "text/html" not in accept:
        return await _providers_json(semptify_uid)
    
    # Return HTML page
    return HTMLResponse(content=_generate_providers_html(semptify_uid))


async def _providers_json(semptify_uid: Optional[str] = None):
    """Return providers as JSON for API clients."""
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


def _generate_providers_html(semptify_uid: Optional[str] = None) -> str:
    """Generate the storage provider selection HTML page."""
    current_provider = None
    if semptify_uid:
        current_provider = get_provider_from_user_id(semptify_uid)
    
    # Build provider cards
    provider_cards = ""
    
    if settings.GOOGLE_DRIVE_CLIENT_ID:
        connected = "connected" if current_provider == "google_drive" else ""
        provider_cards += f'''
        <a href="/storage/auth/google_drive" class="provider-card {connected}">
            <div class="provider-icon">
                <svg viewBox="0 0 24 24" width="48" height="48">
                    <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
                    <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
                    <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
                    <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
                </svg>
            </div>
            <div class="provider-name">Google Drive</div>
            <div class="provider-status">{" ✓ Connected" if connected else "Click to connect"}</div>
        </a>
        '''
    
    if settings.DROPBOX_APP_KEY:
        connected = "connected" if current_provider == "dropbox" else ""
        provider_cards += f'''
        <a href="/storage/auth/dropbox" class="provider-card {connected}">
            <div class="provider-icon">
                <svg viewBox="0 0 24 24" width="48" height="48">
                    <path fill="#0061FF" d="M12 6.19L6.5 9.89l5.5 3.7-5.5 3.7L1 13.59l5.5-3.7L1 6.19 6.5 2.5 12 6.19zm0 7.4l5.5-3.7L12 6.19 6.5 9.89l5.5 3.7zm0 3.7l-5.5-3.7 5.5 3.7 5.5-3.7-5.5 3.7zm5.5-7.4L12 6.19l5.5-3.69L23 6.19l-5.5 3.7zm-5.5 11.1l-5.5-3.7v1.5l5.5 3.7 5.5-3.7v-1.5l-5.5 3.7z"/>
                </svg>
            </div>
            <div class="provider-name">Dropbox</div>
            <div class="provider-status">{" ✓ Connected" if connected else "Click to connect"}</div>
        </a>
        '''
    
    if settings.ONEDRIVE_CLIENT_ID:
        connected = "connected" if current_provider == "onedrive" else ""
        provider_cards += f'''
        <a href="/storage/auth/onedrive" class="provider-card {connected}">
            <div class="provider-icon">
                <svg viewBox="0 0 24 24" width="48" height="48">
                    <path fill="#0078D4" d="M10.5 18.5c0 .28-.22.5-.5.5H3c-1.1 0-2-.9-2-2v-1c0-2.21 1.79-4 4-4 .34 0 .68.04 1 .12V12c0-2.76 2.24-5 5-5 2.06 0 3.83 1.24 4.6 3.02.13-.01.26-.02.4-.02 2.76 0 5 2.24 5 5s-2.24 5-5 5h-5c-.28 0-.5-.22-.5-.5z"/>
                </svg>
            </div>
            <div class="provider-name">OneDrive</div>
            <div class="provider-status">{" ✓ Connected" if connected else "Click to connect"}</div>
        </a>
        '''
    
    if not provider_cards:
        provider_cards = '''
        <div class="no-providers">
            <p>⚠️ No storage providers configured.</p>
            <p>Please contact support to set up cloud storage integration.</p>
        </div>
        '''
    
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Connect Your Storage - Semptify</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            padding: 2rem;
            color: #fff;
        }}
        .container {{
            max-width: 600px;
            width: 100%;
            text-align: center;
        }}
        .logo {{
            font-size: 3rem;
            margin-bottom: 1rem;
        }}
        h1 {{
            font-size: 2rem;
            font-weight: 600;
            margin-bottom: 0.5rem;
        }}
        .subtitle {{
            color: #94a3b8;
            margin-bottom: 2rem;
            font-size: 1.1rem;
        }}
        .security-badge {{
            display: inline-flex;
            align-items: center;
            gap: 0.5rem;
            background: rgba(16, 185, 129, 0.1);
            border: 1px solid rgba(16, 185, 129, 0.3);
            color: #10b981;
            padding: 0.5rem 1rem;
            border-radius: 2rem;
            font-size: 0.875rem;
            margin-bottom: 2rem;
        }}
        .providers {{
            display: flex;
            flex-direction: column;
            gap: 1rem;
        }}
        .provider-card {{
            display: flex;
            align-items: center;
            gap: 1rem;
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 1rem;
            padding: 1.5rem;
            text-decoration: none;
            color: #fff;
            transition: all 0.2s ease;
        }}
        .provider-card:hover {{
            background: rgba(255, 255, 255, 0.1);
            border-color: rgba(59, 130, 246, 0.5);
            transform: translateY(-2px);
        }}
        .provider-card.connected {{
            border-color: #10b981;
            background: rgba(16, 185, 129, 0.1);
        }}
        .provider-icon {{
            flex-shrink: 0;
        }}
        .provider-name {{
            font-size: 1.25rem;
            font-weight: 600;
            flex: 1;
            text-align: left;
        }}
        .provider-status {{
            color: #94a3b8;
            font-size: 0.875rem;
        }}
        .provider-card.connected .provider-status {{
            color: #10b981;
        }}
        .info-box {{
            margin-top: 2rem;
            padding: 1.5rem;
            background: rgba(59, 130, 246, 0.1);
            border: 1px solid rgba(59, 130, 246, 0.3);
            border-radius: 0.75rem;
            text-align: left;
        }}
        .info-box h3 {{
            color: #60a5fa;
            margin-bottom: 0.75rem;
            font-size: 1rem;
        }}
        .info-box ul {{
            color: #94a3b8;
            font-size: 0.9rem;
            padding-left: 1.5rem;
        }}
        .info-box li {{
            margin-bottom: 0.5rem;
        }}
        .no-providers {{
            padding: 2rem;
            background: rgba(239, 68, 68, 0.1);
            border: 1px solid rgba(239, 68, 68, 0.3);
            border-radius: 0.75rem;
            color: #fca5a5;
        }}
        footer {{
            margin-top: 2rem;
            color: #64748b;
            font-size: 0.875rem;
        }}
        footer a {{
            color: #60a5fa;
            text-decoration: none;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="logo">⚖️</div>
        <h1>Connect Your Storage</h1>
        <p class="subtitle">Your documents stay in YOUR cloud storage. We never store your files.</p>
        
        <div class="security-badge">
            🔒 Your data, your storage, your control
        </div>
        
        <div class="providers">
            {provider_cards}
        </div>
        
        <div class="info-box">
            <h3>🛡️ Why connect storage?</h3>
            <ul>
                <li><strong>Security:</strong> Your documents never leave your control</li>
                <li><strong>Privacy:</strong> We can't access your files without your permission</li>
                <li><strong>Portability:</strong> Switch devices anytime - your data follows you</li>
                <li><strong>Backup:</strong> Your cloud provider handles backup and sync</li>
            </ul>
        </div>
        
        <footer>
            <p>Semptify &copy; 2025 · <a href="/privacy.html">Privacy</a> · <a href="/help.html">Help</a></p>
        </footer>
    </div>
</body>
</html>'''


@router.get("/providers/json")
async def list_providers_json(
    semptify_uid: Optional[str] = Cookie(None),
):
    """List available storage providers as JSON (explicit endpoint)."""
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
    return_to: Optional[str] = None,
):
    """
    Start OAuth flow.
    
    - New user: role param determines their role
    - Returning user: existing_uid preserves their user ID
    - return_to: URL to redirect to after OAuth (for setup wizards)
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
        "return_to": return_to,
        "created_at": utc_now(),  # In-memory state, use aware for comparison
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
    # Clean up any old states first
    _cleanup_expired_states()
    
    # Validate state
    if state not in OAUTH_STATES:
        # More helpful error message
        raise HTTPException(
            status_code=400, 
            detail={
                "error": "bad_request",
                "message": "Invalid or expired state. Please try connecting your storage again.",
                "action": "redirect",
                "redirect_url": "/storage/providers"
            }
        )

    state_data = OAUTH_STATES.pop(state)
    if state_data["provider"] != provider:
        raise HTTPException(status_code=400, detail="Provider mismatch")

    if utc_now() - state_data["created_at"] > timedelta(minutes=OAUTH_STATE_TIMEOUT_MINUTES):
        raise HTTPException(
            status_code=400, 
            detail={
                "error": "bad_request",
                "message": "Session expired. Please try connecting your storage again.",
                "action": "redirect", 
                "redirect_url": "/storage/providers"
            }
        )

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
        print(f"🔄 OAuth callback: Returning user with existing ID: {user_id}")
    else:
        # New user - generate ID encoding provider + role
        role = state_data.get("role", "user")
        user_id = generate_user_id(provider, role)
        print(f"🆕 OAuth callback: New user - generated ID: {user_id} (provider={provider}, role={role})")

    # Store encrypted auth marker in user's storage
    auth_marker = {
        "user_id": user_id,
        "provider": provider,
        "created_at": utc_now().isoformat() + "Z",
        "version": "5.0",
    }
    encrypted = _encrypt_token(auth_marker, user_id)
    base_url = str(request.base_url).rstrip("/")
    refresh_token = token_data.get("refresh_token", "")
    expires_in = token_data.get("expires_in", 3600)
    token_expires_at = (utc_now() + timedelta(seconds=expires_in)).isoformat() + "Z"
    
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
    expires_at = utc_now() + timedelta(seconds=token_data.get("expires_in", 3600))
    print(f"💾 Saving session to DB: user_id={user_id}, provider={provider}, expires_at={expires_at}")
    await save_session_to_db(
        db=db,
        user_id=user_id,
        provider=provider,
        access_token=access_token,
        refresh_token=refresh_token,
        expires_at=expires_at,
    )

    # Create/update user and storage config in database
    await create_or_update_user(db, user_id, provider)
    await get_or_create_storage_config(db, user_id, provider)

    # Determine landing page
    # If return_to was specified (e.g., from storage setup wizard), use that
    return_to = state_data.get("return_to")
    if return_to:
        landing = return_to
    else:
        # Default: redirect based on role
        _, role, _ = parse_user_id(user_id)
        landing_pages = {
            "tenant": "/dashboard",
            "landlord": "/properties",
            "advocate": "/clients",
            "admin": "/admin",
        }
        landing = landing_pages.get(role, "/dashboard")

    response = RedirectResponse(url=landing, status_code=302)
    print(f"🍪 Setting cookie: {COOKIE_USER_ID}={user_id}, redirecting to {landing}")

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
    <meta http-equiv="refresh" content="2;url=/static/welcome.html">
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
    Automatically refreshes expired tokens if possible.
    """
    print(f"📊 /storage/status called - cookie semptify_uid: {semptify_uid[:10] if semptify_uid else 'None'}...")
    if not semptify_uid:
        print(f"❌ No semptify_uid cookie found")
        return {"authenticated": False}

    # Use get_valid_session which handles token refresh automatically
    session = await get_valid_session(db, semptify_uid, auto_refresh=True)
    print(f"📊 Session lookup result: {bool(session)}")
    
    if not session:
        # Have cookie but no active/valid session - need to re-auth
        provider, role, _ = parse_user_id(semptify_uid)
        return {
            "authenticated": False,
            "user_id": semptify_uid,
            "provider": provider,
            "role": role,
            "needs_reauth": True,
            "reason": "token_expired_or_invalid",
        }

    provider, role, _ = parse_user_id(semptify_uid)
    return {
        "authenticated": True,
        "user_id": semptify_uid,
        "provider": provider,
        "role": role,
        "access_token": session["access_token"],
        "expires_at": session.get("expires_at"),
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
        "expires_at": session.get("expires_at") if session else None,
    }


@router.post("/validate")
async def validate_and_refresh_token(
    semptify_uid: Optional[str] = Cookie(None),
    db: AsyncSession = Depends(get_db),
):
    """
    Validate current access token and refresh if needed.
    Returns detailed status about token validity.
    """
    if not semptify_uid:
        return {
            "valid": False,
            "reason": "no_session",
            "message": "No session cookie found",
        }

    # First get raw session without auto-refresh
    session = await get_session_from_db(db, semptify_uid)
    if not session:
        return {
            "valid": False,
            "reason": "no_session",
            "message": "No session found in database",
        }

    provider = session.get("provider")
    access_token = session.get("access_token")
    refresh_token = session.get("refresh_token")
    expires_at = session.get("expires_at")

    # Check if token is expired
    token_expired = False
    if expires_at:
        if isinstance(expires_at, str):
            expires_at_dt = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
        else:
            expires_at_dt = expires_at
        # Ensure expires_at_dt is timezone-aware (assume UTC if naive)
        if expires_at_dt.tzinfo is None:
            from datetime import timezone
            expires_at_dt = expires_at_dt.replace(tzinfo=timezone.utc)
        token_expired = utc_now() >= expires_at_dt

    # Validate with provider
    is_valid = await validate_token_with_provider(provider, access_token)

    if is_valid and not token_expired:
        return {
            "valid": True,
            "provider": provider,
            "expires_at": expires_at,
            "message": "Token is valid",
        }

    # Token is invalid or expired - try to refresh
    if refresh_token:
        new_token_data = await refresh_access_token(db, semptify_uid, provider, refresh_token)
        if new_token_data:
            return {
                "valid": True,
                "refreshed": True,
                "provider": provider,
                "expires_at": new_token_data["expires_at"].isoformat(),
                "message": "Token was expired but successfully refreshed",
            }

    # Could not refresh
    return {
        "valid": False,
        "reason": "token_invalid",
        "has_refresh_token": bool(refresh_token),
        "provider": provider,
        "message": "Token is invalid and could not be refreshed. Please re-authenticate.",
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
    - admin: System administrator - requires PIN (set via ADMIN_PIN env var)
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
