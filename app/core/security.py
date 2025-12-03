"""
Semptify 5.0 - Security Module
Storage-based authentication: Access to cloud storage = Identity

Core Principle:
- User authenticates with their cloud storage (Google Drive, Dropbox, OneDrive)
- Encrypted auth token stored in their storage (.semptify/auth_token.enc)
- If they can access their storage and we can decrypt the token, they're authenticated
- No passwords, no email verification, no traditional sign-up/sign-in

Additional Features (Flask Parity):
- Anonymous user tokens (12-digit digits-only tokens)
- Breakglass emergency admin access
- Event logging to logs/events.log
- Prometheus-compatible metrics
"""

import hashlib
import json
import os
import secrets
import string
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional
from collections import defaultdict
from contextlib import contextmanager
import logging
import tempfile

from fastapi import Depends, HTTPException, Request, Cookie, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.core.config import Settings, get_settings
from app.core.user_context import (
    UserContext,
    UserRole,
    StorageProvider,
    StoredSession,
    get_permissions,
    get_ui_config,
)


# =============================================================================
# Logging Setup
# =============================================================================

logger = logging.getLogger("semptify.security")


# =============================================================================
# Metrics (Prometheus-compatible)
# =============================================================================

_metrics: dict[str, int] = {
    "requests_total": 0,
    "admin_requests_total": 0,
    "admin_actions_total": 0,
    "errors_total": 0,
    "releases_total": 0,
    "rate_limited_total": 0,
    "breakglass_used_total": 0,
    "token_rotations_total": 0,
    "user_registrations_total": 0,
}

_latencies: list[float] = []
_startup_time: float = time.time()


def incr_metric(name: str, delta: int = 1) -> None:
    """Increment a counter metric."""
    if name in _metrics:
        _metrics[name] += delta


def record_request_latency(latency_ms: float) -> None:
    """Record request latency for percentile calculations."""
    _latencies.append(latency_ms)
    # Keep last 1000 samples
    if len(_latencies) > 1000:
        _latencies.pop(0)


def get_metrics() -> dict:
    """Get all metrics for /metrics endpoint."""
    uptime = time.time() - _startup_time
    
    # Calculate latency percentiles
    latency_stats = {}
    if _latencies:
        sorted_lat = sorted(_latencies)
        n = len(sorted_lat)
        latency_stats = {
            "p50_ms": sorted_lat[int(n * 0.50)] if n > 0 else 0,
            "p95_ms": sorted_lat[int(n * 0.95)] if n >= 20 else 0,
            "p99_ms": sorted_lat[int(n * 0.99)] if n >= 100 else 0,
            "mean_ms": sum(sorted_lat) / n if n > 0 else 0,
            "max_ms": max(sorted_lat) if n > 0 else 0,
        }
    
    return {
        **_metrics,
        "uptime_seconds": uptime,
        "latency": latency_stats,
    }


# =============================================================================
# Event Logging (JSON events to logs/events.log)
# =============================================================================

_events_log_path: Optional[Path] = None


def _get_events_log_path() -> Path:
    """Get or initialize events log path."""
    global _events_log_path
    if _events_log_path is None:
        logs_dir = Path("logs")
        logs_dir.mkdir(exist_ok=True)
        _events_log_path = logs_dir / "events.log"
    return _events_log_path


def log_event(event_type: str, details: Optional[dict] = None) -> None:
    """
    Log a structured JSON event to events.log.
    
    Args:
        event_type: Type of event (e.g., "admin_login", "rate_limited", "breakglass_used")
        details: Additional event details
    """
    try:
        event = {
            "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "type": event_type,
            "details": details or {},
        }

        log_path = _get_events_log_path()
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(event) + "\n")
        
        logger.debug(f"Event logged: {event_type}")
    except Exception as e:
        logger.error(f"Failed to log event {event_type}: {e}")


# =============================================================================
# Anonymous User Tokens (Flask Parity)
# =============================================================================

class UserTokenStore:
    """
    Manages anonymous user tokens stored in security/users.json.
    These are 12-digit numeric tokens for vault access.
    """

    def __init__(self, security_dir: str = "security"):
        self.security_dir = Path(security_dir)
        self.security_dir.mkdir(exist_ok=True)
        self.users_file = self.security_dir / "users.json"
        self._ensure_file()

    def _ensure_file(self):
        """Create users file if it doesn't exist."""
        if not self.users_file.exists():
            self._atomic_write({})

    def _atomic_write(self, data: dict):
        """Write JSON atomically (temp file + rename)."""
        temp_path = self.users_file.with_suffix(".tmp")
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        temp_path.replace(self.users_file)

    def _read_json(self) -> dict:
        """Read JSON file safely."""
        try:
            with open(self.users_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return {}

    def generate_user_token(self) -> str:
        """Generate a 12-digit numeric token."""
        return "".join(secrets.choice(string.digits) for _ in range(12))

    def save_user_token(self, token: Optional[str] = None) -> tuple[str, str]:
        """
        Generate and save a new user token.
        Returns: (token, user_id)
        """
        if token is None:
            token = self.generate_user_token()
        
        token_hash = hash_token(token)
        user_id = f"user_{secrets.token_hex(8)}"
        
        users = self._read_json()
        users[user_id] = {
            "hash": token_hash,
            "created": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "type": "vault_user",
        }
        self._atomic_write(users)

        incr_metric("user_registrations_total")
        log_event("user_registered", {"user_id": user_id})
        return token, user_id

    def validate_user_token(self, token: str) -> Optional[str]:
        """
        Validate a user token.
        Returns user_id if valid, None otherwise.
        """
        if not token:
            return None
        
        token_hash = hash_token(token)
        users = self._read_json()
        
        for user_id, user_data in users.items():
            if user_data.get("hash") == token_hash:
                return user_id
        
        return None


_user_token_store: Optional[UserTokenStore] = None


def get_user_token_store() -> UserTokenStore:
    """Get or create user token store singleton."""
    global _user_token_store
    if _user_token_store is None:
        _user_token_store = UserTokenStore()
    return _user_token_store


def validate_user_token(token: Optional[str]) -> Optional[str]:
    """Convenience function: validate user token and return user_id."""
    if not token:
        return None
    store = get_user_token_store()
    return store.validate_user_token(token)


def save_user_token() -> tuple[str, str]:
    """Convenience function: generate and save a new user token."""
    store = get_user_token_store()
    return store.save_user_token()


# =============================================================================
# Breakglass Emergency Admin Access (Flask Parity)
# =============================================================================

def is_breakglass_active() -> bool:
    """Check if breakglass flag file exists."""
    return Path("security/breakglass.flag").exists()


def consume_breakglass() -> None:
    """Remove breakglass flag (one-time use)."""
    flag_path = Path("security/breakglass.flag")
    if flag_path.exists():
        flag_path.unlink()
        incr_metric("breakglass_used_total")
        log_event("breakglass_consumed")


# =============================================================================
# Session Store (In-memory, use Redis in production)
# =============================================================================

ACTIVE_SESSIONS: dict[str, StoredSession] = {}


def get_session(session_id: str) -> Optional[StoredSession]:
    """Get session by ID."""
    session = ACTIVE_SESSIONS.get(session_id)
    if not session:
        return None

    # Check expiry
    if session.expires_at and session.expires_at < datetime.now(timezone.utc):
        del ACTIVE_SESSIONS[session_id]
        return None

    return session


def create_session(
    user_id: str,
    provider: str,
    storage_user_id: str,
    access_token: str,
    refresh_token: Optional[str] = None,
    email: Optional[str] = None,
    display_name: Optional[str] = None,
    role: str = "user",
    ttl_hours: int = 24,
) -> StoredSession:
    """Create a new session for an authenticated user."""
    session_id = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)

    session = StoredSession(
        session_id=session_id,
        user_id=user_id,
        provider=provider,
        storage_user_id=storage_user_id,
        access_token=access_token,
        refresh_token=refresh_token,
        role=role,
        email=email,
        display_name=display_name,
        created_at=now,
        expires_at=now + timedelta(hours=ttl_hours),
    )
    
    ACTIVE_SESSIONS[session_id] = session
    return session


def update_session_role(session_id: str, role: str) -> Optional[StoredSession]:
    """Update the role for an existing session."""
    session = ACTIVE_SESSIONS.get(session_id)
    if session:
        session.role = role
        return session
    return None


def update_session_token(session_id: str, access_token: str) -> Optional[StoredSession]:
    """Update the access token for an existing session."""
    session = ACTIVE_SESSIONS.get(session_id)
    if session:
        session.access_token = access_token
        return session
    return None


def invalidate_session(session_id: str) -> bool:
    """Invalidate/logout a session."""
    if session_id in ACTIVE_SESSIONS:
        del ACTIVE_SESSIONS[session_id]
        return True
    return False


# =============================================================================
# User ID Generation
# =============================================================================

def derive_user_id(provider: str, storage_user_id: str) -> str:
    """
    Derive a stable internal user ID from storage identity.
    
    This is deterministic - same provider + storage_user_id always gets same internal ID.
    The user ID does NOT encode role or provider - those are in the session.
    """
    combined = f"{provider}:{storage_user_id}"
    return hashlib.sha256(combined.encode()).hexdigest()[:24]


# =============================================================================
# Token Generation & Hashing
# =============================================================================

def generate_token() -> str:
    """Generate a secure token (hex string)."""
    return secrets.token_hex(32)


def hash_token(token: str) -> str:
    """SHA-256 hash a token for secure storage."""
    return hashlib.sha256(token.encode()).hexdigest()


# =============================================================================
# Admin Token Storage
# =============================================================================

class AdminTokenStore:
    """
    Manages admin token storage in JSON files.
    Admin access is separate from user storage-based auth.
    Supports breakglass emergency access.
    """

    def __init__(self, security_dir: str = "security"):
        self.security_dir = Path(security_dir)
        self.security_dir.mkdir(exist_ok=True)
        self.admin_file = self.security_dir / "admin_tokens.json"
        self._ensure_files()

    def _ensure_files(self):
        """Create token files if they don't exist."""
        if not self.admin_file.exists():
            self._atomic_write(self.admin_file, [])

    def _atomic_write(self, path: Path, data: dict | list):
        """Write JSON atomically (temp file + rename)."""
        temp_path = path.with_suffix(".tmp")
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        temp_path.replace(path)

    def _read_json(self, path: Path) -> dict | list:
        """Read JSON file safely."""
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return []

    def validate_admin_token(self, token: str) -> Optional[dict]:
        """
        Validate an admin token.
        
        Priority:
        1. MASTER_KEY env var -> returns {"id": "master_admin"}
        2. Breakglass flag + token with breakglass:true -> returns {"id": "breakglass_<id>"}
        3. ADMIN_TOKEN env var (legacy) -> returns {"id": "env_admin"}
        4. admin_tokens.json lookup -> returns token data
        """
        # 1. Check MASTER_KEY
        master_key = os.getenv("MASTER_KEY")
        if master_key and token == master_key:
            log_event("admin_auth", {"method": "master_key"})
            incr_metric("admin_requests_total")
            return {"id": "master_admin", "method": "master_key"}
        
        token_hash = hash_token(token)
        admins = self._read_json(self.admin_file)

        # 2. Check breakglass
        if is_breakglass_active():
            if isinstance(admins, list):
                for admin in admins:
                    if admin.get("hash") == token_hash and admin.get("breakglass"):
                        consume_breakglass()
                        log_event("admin_auth", {"method": "breakglass", "id": admin.get("id")})
                        incr_metric("admin_requests_total")
                        return {"id": f"breakglass_{admin.get('id')}", "method": "breakglass"}
            elif isinstance(admins, dict):
                for admin_id, admin_data in admins.items():
                    if admin_data.get("hash") == token_hash and admin_data.get("breakglass"):
                        consume_breakglass()
                        log_event("admin_auth", {"method": "breakglass", "id": admin_id})
                        incr_metric("admin_requests_total")
                        return {"id": f"breakglass_{admin_id}", "method": "breakglass"}

        # 3. Check ADMIN_TOKEN env var (legacy)
        env_admin_token = os.getenv("ADMIN_TOKEN")
        if env_admin_token and token == env_admin_token:
            log_event("admin_auth", {"method": "env_var"})
            incr_metric("admin_requests_total")
            return {"id": "env_admin", "method": "env_var"}

        # 4. Check admin_tokens.json
        if isinstance(admins, list):
            for admin in admins:
                if admin.get("hash") == token_hash:
                    log_event("admin_auth", {"method": "token_file", "id": admin.get("id")})
                    incr_metric("admin_requests_total")
                    return admin
        elif isinstance(admins, dict):
            for admin_id, admin_data in admins.items():
                if admin_data.get("hash") == token_hash:
                    log_event("admin_auth", {"method": "token_file", "id": admin_id})
                    incr_metric("admin_requests_total")
                    return {"id": admin_id, **admin_data}
        
        return None


_admin_token_store: Optional[AdminTokenStore] = None


def get_admin_token_store() -> AdminTokenStore:
    """Get or create the admin token store singleton."""
    global _admin_token_store
    if _admin_token_store is None:
        _admin_token_store = AdminTokenStore()
    return _admin_token_store


# =============================================================================
# Rate Limiting
# =============================================================================

class RateLimiter:
    """In-memory sliding window rate limiter."""

    def __init__(self):
        self._requests: dict[str, list[float]] = defaultdict(list)

    def check(
        self,
        key: str,
        window_seconds: int = 60,
        max_requests: int = 100,
    ) -> tuple[bool, Optional[int]]:
        """
        Check if request is allowed.
        Returns: (allowed: bool, retry_after: Optional[int])
        """
        now = time.time()
        window_start = now - window_seconds

        self._requests[key] = [
            ts for ts in self._requests[key] if ts > window_start
        ]

        if len(self._requests[key]) >= max_requests:
            oldest_in_window = min(self._requests[key])
            retry_after = int(oldest_in_window + window_seconds - now) + 1
            return False, retry_after

        self._requests[key].append(now)
        return True, None


_rate_limiter: Optional[RateLimiter] = None


def get_rate_limiter() -> RateLimiter:
    """Get or create rate limiter singleton."""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter()
    return _rate_limiter


# =============================================================================
# Request Token Extraction (Flask Parity)
# =============================================================================

def get_token_from_request(request: Request) -> Optional[str]:
    """
    Extract user token from request (multiple sources).
    
    Priority:
    1. X-User-Token header
    2. user_token query parameter
    3. token query parameter
    4. Form field user_token (for POST requests)
    """
    # Header
    token = request.headers.get("X-User-Token")
    if token:
        return token
    
    # Query params
    token = request.query_params.get("user_token")
    if token:
        return token
    
    token = request.query_params.get("token")
    if token:
        return token
    
    # Note: Form data extraction requires async, so handled in route
    return None


def get_admin_token_from_request(request: Request) -> Optional[str]:
    """
    Extract admin token from request.
    
    Priority:
    1. X-Admin-Token header
    2. Authorization: Bearer <token>
    3. admin_token query parameter
    4. token query parameter
    """
    # Header
    token = request.headers.get("X-Admin-Token")
    if token:
        return token
    
    # Authorization header
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header[7:]
    
    # Query params
    token = request.query_params.get("admin_token")
    if token:
        return token
    
    token = request.query_params.get("token")
    if token:
        return token
    
    return None


# =============================================================================
# FastAPI Dependencies
# =============================================================================

security_bearer = HTTPBearer(auto_error=False)


async def get_current_user(
    request: Request,
    semptify_session: Optional[str] = Cookie(None),
    semptify_uid: Optional[str] = Cookie(None),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_bearer),
    settings: Settings = Depends(get_settings),
) -> Optional[UserContext]:
    """
    Get current user context from session.

    Authentication sources (priority order):
    1. semptify_session cookie (OAuth session)
    2. semptify_uid cookie (welcome sequence user ID)
    3. Authorization: Bearer <session_id>
    4. X-Session-Id header
    """
    session_id = None

    # Check for OAuth session first
    if semptify_session:
        session_id = semptify_session
    elif credentials:
        session_id = credentials.credentials
    else:
        session_id = request.headers.get("X-Session-Id")

    if session_id:
        session = get_session(session_id)
        if session:
            return session.to_context()

    # Check for welcome sequence user ID cookie
    if semptify_uid and len(semptify_uid) >= 6:
        # User created via welcome sequence - create a context from the UID
        return UserContext(
            user_id=semptify_uid,
            provider=StorageProvider.GOOGLE_DRIVE,  # Default, will change when they connect
            storage_user_id=semptify_uid,
            access_token="welcome-user-token",
            role=UserRole.USER,
        )

    return None


async def require_user(
    user: Optional[UserContext] = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> UserContext:
    """
    Require authenticated user.
    Returns UserContext with role, provider, and permissions.
    
    In open mode, ALWAYS use open-mode-user for data consistency (demo mode).
    This ensures all pre-populated timeline/case data is accessible.
    """
    # In open mode, always use the demo user for data consistency
    if settings.security_mode == "open":
        return UserContext(
            user_id="open-mode-user",
            provider=StorageProvider.GOOGLE_DRIVE,
            storage_user_id="test",
            access_token="open-mode-token",
            role=UserRole.USER,
        )

    # If we have a user from cookie/session, use it
    if user:
        return user

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required. Connect your cloud storage at /storage/providers",
        headers={"WWW-Authenticate": "Bearer"},
    )
def require_role(*roles: UserRole):
    """
    Dependency factory: require specific role(s).
    
    Usage:
        @router.get("/admin-only")
        async def admin_endpoint(user: UserContext = Depends(require_role(UserRole.ADMIN))):
            ...
    """
    async def check_role(
        user: UserContext = Depends(require_user),
        settings: Settings = Depends(get_settings),
    ) -> UserContext:
        if settings.security_mode == "open":
            return user
        
        if user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"This action requires one of these roles: {[r.value for r in roles]}",
            )
        return user
    
    return check_role


def require_permission(*permissions: str):
    """
    Dependency factory: require specific permission(s).
    
    Usage:
        @router.post("/upload")
        async def upload(user: UserContext = Depends(require_permission("vault_write"))):
            ...
    """
    async def check_permission(
        user: UserContext = Depends(require_user),
        settings: Settings = Depends(get_settings),
    ) -> UserContext:
        if settings.security_mode == "open":
            return user
        
        if not user.can(*permissions):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing required permissions: {permissions}",
            )
        return user
    
    return check_permission


async def require_admin(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_bearer),
    settings: Settings = Depends(get_settings),
) -> dict:
    """Require admin authentication (separate from user auth)."""
    if settings.security_mode == "open":
        return {"id": "open-mode-admin", "mode": "open"}

    # Rate limiting for admin routes
    limiter = get_rate_limiter()
    client_ip = request.client.host if request.client else "unknown"
    key = f"admin:{client_ip}:{request.url.path}"
    
    allowed, retry_after = limiter.check(
        key, 
        settings.admin_rate_limit_window, 
        settings.admin_rate_limit_max_requests
    )
    
    if not allowed:
        incr_metric("rate_limited_total")
        log_event("rate_limited", {"key": key, "retry_after": retry_after})
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded",
            headers={"Retry-After": str(retry_after)},
        )

    # Extract token from multiple sources
    token = get_admin_token_from_request(request)
    if not token and credentials:
        token = credentials.credentials

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Admin authentication required",
        )

    admin_store = get_admin_token_store()
    admin = admin_store.validate_admin_token(token)

    if not admin:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid admin token",
        )

    return admin


def rate_limit_dependency(
    key_prefix: str = "api",
    window: Optional[int] = None,
    max_requests: Optional[int] = None,
):
    """Create a rate limiting dependency."""
    async def check_rate_limit(
        request: Request,
        settings: Settings = Depends(get_settings),
    ):
        limiter = get_rate_limiter()
        client_ip = request.client.host if request.client else "unknown"
        key = f"{key_prefix}:{client_ip}:{request.url.path}"

        _window = window or settings.rate_limit_window
        _max = max_requests or settings.rate_limit_max_requests

        allowed, retry_after = limiter.check(key, _window, _max)

        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded",
                headers={"Retry-After": str(retry_after)},
            )

    return check_rate_limit


# =============================================================================
# CSRF Protection
# =============================================================================

def generate_csrf_token() -> str:
    """Generate a CSRF token."""
    return secrets.token_hex(32)


async def validate_csrf(
    request: Request,
    settings: Settings = Depends(get_settings),
) -> None:
    """Validate CSRF token for state-changing requests."""
    if settings.security_mode == "open":
        return

    if request.method in ("POST", "PUT", "DELETE", "PATCH"):
        content_type = request.headers.get("content-type", "")
        if content_type.startswith("application/x-www-form-urlencoded"):
            form_data = await request.form()
            csrf_token = form_data.get("csrf_token")
        else:
            csrf_token = request.headers.get("X-CSRF-Token")

        session_token = request.cookies.get("csrf_token")

        if not csrf_token or csrf_token != session_token:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="CSRF token validation failed",
            )


# =============================================================================
# Anonymous User Auth Dependency (Flask Parity)
# =============================================================================

async def require_anonymous_user(
    request: Request,
    settings: Settings = Depends(get_settings),
) -> str:
    """
    Require anonymous user token authentication.
    Used for vault access with 12-digit tokens.
    Returns user_id if valid.
    """
    if settings.security_mode == "open":
        return "open-mode-user"
    
    # Extract token from request
    token = get_token_from_request(request)
    
    # Also try form data for POST requests
    if not token and request.method == "POST":
        try:
            form_data = await request.form()
            token = form_data.get("user_token")
        except Exception:
            pass
    
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User token required. Provide via X-User-Token header or user_token query param.",
        )
    
    user_id = validate_user_token(token)
    
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user token",
        )
    
    return user_id


def optional_anonymous_user(request: Request) -> Optional[str]:
    """
    Optional anonymous user token - returns user_id or None.
    Use when auth is optional.
    """
    token = get_token_from_request(request)
    if token:
        return validate_user_token(token)
    return None


# =============================================================================
# Legacy Exports (for backward compatibility)
# =============================================================================

# Re-export for backward compatibility with routers using StorageUser
StorageUser = UserContext

# Export all security functions for easy imports
__all__ = [
    # Session management
    "ACTIVE_SESSIONS",
    "get_session",
    "create_session",
    "update_session_role",
    "update_session_token",
    "invalidate_session",
    # User ID
    "derive_user_id",
    # Tokens
    "generate_token",
    "hash_token",
    # Anonymous user tokens
    "validate_user_token",
    "save_user_token",
    "get_user_token_store",
    # Admin tokens
    "get_admin_token_store",
    "AdminTokenStore",
    # Breakglass
    "is_breakglass_active",
    "consume_breakglass",
    # Rate limiting
    "get_rate_limiter",
    "RateLimiter",
    # Request helpers
    "get_token_from_request",
    "get_admin_token_from_request",
    # FastAPI dependencies
    "get_current_user",
    "require_user",
    "require_role",
    "require_permission",
    "require_admin",
    "require_anonymous_user",
    "optional_anonymous_user",
    "rate_limit_dependency",
    # CSRF
    "generate_csrf_token",
    "validate_csrf",
    # Metrics & Events
    "incr_metric",
    "get_metrics",
    "record_request_latency",
    "log_event",
    # Legacy
    "StorageUser",
]
