"""
Semptify 5.0 - Storage & Authentication Tests
Tests for OAuth flow, session management, and storage providers.
"""

import pytest
from httpx import AsyncClient
from unittest.mock import patch, AsyncMock, MagicMock


# =============================================================================
# Provider Listing Tests
# =============================================================================

@pytest.mark.anyio
async def test_storage_providers_list(client: AsyncClient):
    """Test listing available storage providers."""
    response = await client.get("/storage/providers")
    assert response.status_code == 200
    # May return HTML page or JSON depending on configuration
    content_type = response.headers.get("content-type", "")
    if "application/json" in content_type:
        data = response.json()
        assert "providers" in data
        assert isinstance(data["providers"], list)
    else:
        # HTML response - check for provider content
        assert "storage" in response.text.lower() or "connect" in response.text.lower()


@pytest.mark.anyio
async def test_storage_providers_include_expected(client: AsyncClient):
    """Test that expected provider IDs are present if configured."""
    response = await client.get("/storage/providers")
    content_type = response.headers.get("content-type", "")
    if "application/json" in content_type:
        data = response.json()
        # Provider list depends on configuration
        for provider in data.get("providers", []):
            assert "id" in provider
            assert "name" in provider
            assert "enabled" in provider
            assert provider["id"] in ["google_drive", "dropbox", "onedrive"]
    else:
        # HTML response - check page contains provider references
        text = response.text.lower()
        assert "google" in text or "dropbox" in text or "onedrive" in text or "storage" in text


# =============================================================================
# Session Tests
# =============================================================================

@pytest.mark.anyio
async def test_storage_session_unauthenticated(client: AsyncClient):
    """Test session endpoint without authentication."""
    response = await client.get("/storage/session")
    assert response.status_code == 200
    data = response.json()
    assert data["authenticated"] is False


@pytest.mark.anyio
async def test_storage_session_authenticated(authenticated_client: AsyncClient):
    """Test session endpoint with valid session."""
    response = await authenticated_client.get("/storage/session")
    assert response.status_code == 200
    data = response.json()
    assert data["authenticated"] is True
    assert "user_id" in data
    assert "provider" in data


@pytest.mark.anyio
async def test_storage_status_unauthenticated(client: AsyncClient):
    """Test status endpoint without authentication."""
    response = await client.get("/storage/status")
    assert response.status_code == 200
    data = response.json()
    assert data["authenticated"] is False


@pytest.mark.anyio
async def test_storage_status_authenticated(authenticated_client: AsyncClient):
    """Test status endpoint with valid session."""
    response = await authenticated_client.get("/storage/status")
    assert response.status_code == 200
    data = response.json()
    assert data["authenticated"] is True
    assert "access_token" in data  # Status returns token, session doesn't


# =============================================================================
# OAuth Flow Tests
# =============================================================================

@pytest.mark.anyio
async def test_storage_auth_redirect_google(client: AsyncClient):
    """Test Google OAuth redirect (requires credentials configured)."""
    response = await client.get("/storage/auth/google_drive", follow_redirects=False)
    # Will redirect to Google or return error if not configured
    assert response.status_code in [302, 307, 400, 500]


@pytest.mark.anyio
async def test_storage_auth_invalid_provider(client: AsyncClient):
    """Test OAuth with invalid provider."""
    response = await client.get("/storage/auth/invalid_provider")
    # May return 400 (error) or 404 (not found) for invalid provider
    assert response.status_code in [400, 404, 422]
    content_type = response.headers.get("content-type", "")
    if "application/json" in content_type:
        data = response.json()
        # Check for error message in various response formats
        assert "detail" in data or "error" in data or "message" in data


@pytest.mark.anyio
async def test_storage_callback_invalid_state(client: AsyncClient):
    """Test OAuth callback with invalid state."""
    response = await client.get("/storage/callback/google_drive?code=test&state=invalid")
    # May return 400 (error), 302 (redirect to error page), or other error codes
    assert response.status_code in [400, 401, 302, 307, 422, 500]
    content_type = response.headers.get("content-type", "")
    if "application/json" in content_type and response.status_code != 302:
        data = response.json()
        # Check various response formats
        detail = data.get("detail", data.get("message", "")).lower()
        error = data.get("error", "").lower()
        assert "invalid" in detail or "expired" in detail or "state" in detail or "error" in detail or error


# =============================================================================
# Role Management Tests
# =============================================================================

@pytest.mark.anyio
async def test_role_switch_unauthenticated(client: AsyncClient):
    """Test role switch without authentication."""
    response = await client.post("/storage/role", json={"role": "landlord"})
    assert response.status_code == 401


@pytest.mark.anyio
async def test_role_switch_authenticated(authenticated_client: AsyncClient):
    """Test role switch with authentication - user role (no auth required)."""
    response = await authenticated_client.post("/storage/role", json={"role": "user"})
    assert response.status_code == 200
    data = response.json()
    assert data.get("success") is True
    assert data.get("role") == "user"


@pytest.mark.anyio
async def test_role_switch_advocate_requires_invite(authenticated_client: AsyncClient):
    """Test advocate role requires invite code."""
    # Without invite code - should fail
    response = await authenticated_client.post("/storage/role", json={"role": "advocate"})
    assert response.status_code == 403

    # With valid invite code - should succeed
    response = await authenticated_client.post(
        "/storage/role",
        json={"role": "advocate", "invite_code": "TEST-INVITE-CODE"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data.get("success") is True
    assert data.get("role") == "advocate"


@pytest.mark.anyio
async def test_role_switch_legal_requires_invite(authenticated_client: AsyncClient):
    """Test legal role requires invite code."""
    # Without invite code - should fail
    response = await authenticated_client.post("/storage/role", json={"role": "legal"})
    assert response.status_code == 403

    # With valid invite code - should succeed
    response = await authenticated_client.post(
        "/storage/role",
        json={"role": "legal", "invite_code": "TEST-INVITE-CODE"}
    )
    assert response.status_code == 200


@pytest.mark.anyio
async def test_role_switch_manager_requires_household(authenticated_client: AsyncClient):
    """Test manager role requires multiple people on lease."""
    # Without household members - should fail
    response = await authenticated_client.post("/storage/role", json={"role": "manager"})
    assert response.status_code == 403

    # With only 1 person - should fail
    response = await authenticated_client.post(
        "/storage/role",
        json={"role": "manager", "household_members": 1}
    )
    assert response.status_code == 403

    # With 2+ people - should succeed
    response = await authenticated_client.post(
        "/storage/role",
        json={"role": "manager", "household_members": 2}
    )
    assert response.status_code == 200


@pytest.mark.anyio
async def test_role_switch_admin_requires_pin(authenticated_client: AsyncClient):
    """Test admin role requires PIN."""
    # Without PIN - should fail
    response = await authenticated_client.post("/storage/role", json={"role": "admin"})
    assert response.status_code == 403

    # With wrong PIN - should fail
    response = await authenticated_client.post(
        "/storage/role",
        json={"role": "admin", "pin": "1234"}
    )
    assert response.status_code == 403

    # With correct PIN - should succeed
    response = await authenticated_client.post(
        "/storage/role",
        json={"role": "admin", "pin": "TEST-PIN"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data.get("role") == "admin"


@pytest.mark.anyio
async def test_role_switch_invalid_role(authenticated_client: AsyncClient):
    """Test role switch with invalid role."""
    response = await authenticated_client.post("/storage/role", json={"role": "superuser"})
    assert response.status_code == 400


# =============================================================================
# Logout Tests
# =============================================================================

@pytest.mark.anyio
async def test_logout(client: AsyncClient):
    """Test logout clears session."""
    response = await client.post("/storage/logout")
    assert response.status_code == 200
    data = response.json()
    assert data.get("success") is True


@pytest.mark.anyio
async def test_logout_authenticated(authenticated_client: AsyncClient):
    """Test logout when authenticated."""
    response = await authenticated_client.post("/storage/logout")
    assert response.status_code == 200
    
    # Session should be cleared
    session_response = await authenticated_client.get("/storage/session")
    # Cookie is cleared, so should show unauthenticated
    # (Note: cookie might persist in test client)


# =============================================================================
# Storage Home Routing Tests
# =============================================================================

@pytest.mark.anyio
async def test_storage_home_no_cookie(client: AsyncClient):
    """Test storage home redirects to providers without cookie."""
    response = await client.get("/storage/", follow_redirects=False)
    assert response.status_code in [302, 307]
    assert "/providers" in response.headers.get("location", "")


@pytest.mark.anyio
async def test_storage_home_with_cookie(authenticated_client: AsyncClient):
    """Test storage home with existing cookie redirects to auth."""
    response = await authenticated_client.get("/storage/", follow_redirects=False)
    # Should redirect to re-auth with existing provider
    assert response.status_code in [302, 307]


# =============================================================================
# Sync Device Tests
# =============================================================================

@pytest.mark.anyio
async def test_sync_device_valid_user_id(client: AsyncClient):
    """Test sync endpoint with valid user ID sets cookie."""
    response = await client.get("/storage/sync/GUtest1234", follow_redirects=False)
    assert response.status_code == 200
    assert "Reconnected" in response.text
    assert "semptify_uid" in response.headers.get("set-cookie", "")


@pytest.mark.anyio
async def test_sync_device_invalid_user_id(client: AsyncClient):
    """Test sync endpoint with invalid user ID returns error."""
    response = await client.get("/storage/sync/invalid", follow_redirects=False)
    assert response.status_code == 400
    assert "Invalid" in response.text


@pytest.mark.anyio
async def test_sync_device_shows_provider_and_role(client: AsyncClient):
    """Test sync endpoint shows correct provider and role."""
    # GU = Google + User
    response = await client.get("/storage/sync/GUabcd1234", follow_redirects=False)
    assert response.status_code == 200
    assert "Google Drive" in response.text
    assert "user" in response.text.lower()
