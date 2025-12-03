"""
Semptify 5.0 - Basic Tests
Verifies the FastAPI application structure and storage-based auth.
"""

import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import patch, MagicMock

# We need to set up the test before importing the app
import os
os.environ["SECURITY_MODE"] = "open"
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test_semptify.db"

from app.main import app


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def client():
    """Create test client."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# =============================================================================
# Health Check Tests
# =============================================================================

@pytest.mark.anyio
async def test_healthz(client: AsyncClient):
    """Test health endpoint."""
    response = await client.get("/healthz")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "timestamp" in data


@pytest.mark.anyio
async def test_root(client: AsyncClient):
    """Test root endpoint returns app info or redirects."""
    response = await client.get("/")
    # Root may return JSON, HTML, or redirect depending on configuration
    assert response.status_code in [200, 302, 307]
    if response.status_code == 200:
        content_type = response.headers.get("content-type", "")
        if "application/json" in content_type:
            data = response.json()
            assert "name" in data or "status" in data


# =============================================================================
# Storage Provider Tests
# =============================================================================

@pytest.mark.anyio
async def test_storage_providers_list(client: AsyncClient):
    """Test listing available storage providers."""
    response = await client.get("/storage/providers")
    assert response.status_code == 200
    data = response.json()
    assert "providers" in data
    # In test mode without OAuth credentials, providers list may be empty
    assert isinstance(data["providers"], list)


@pytest.mark.anyio
async def test_storage_session_unauthenticated(client: AsyncClient):
    """Test session endpoint without auth."""
    response = await client.get("/storage/session")
    assert response.status_code == 200
    data = response.json()
    assert data["authenticated"] is False


# =============================================================================
# Timeline Tests (Open Mode)
# =============================================================================

@pytest.mark.anyio
async def test_timeline_create_event(client: AsyncClient):
    """Test creating a timeline event in open mode."""
    response = await client.post(
        "/api/timeline/",
        json={
            "event_type": "notice",
            "title": "Test Notice Received",
            "description": "Testing timeline creation",
            "event_date": "2025-11-29T10:00:00",
            "is_evidence": True,
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Test Notice Received"
    assert data["is_evidence"] is True
    assert "id" in data


@pytest.mark.anyio
async def test_timeline_list_events(client: AsyncClient):
    """Test listing timeline events."""
    # Create an event first
    await client.post(
        "/api/timeline/",
        json={
            "event_type": "payment",
            "title": "Rent Payment",
            "event_date": "2025-11-01T00:00:00",
            "is_evidence": False,
        },
    )
    
    response = await client.get("/api/timeline/")
    assert response.status_code == 200
    data = response.json()
    assert "events" in data
    assert "total" in data


# =============================================================================
# Calendar Tests (Open Mode)
# =============================================================================

@pytest.mark.anyio
async def test_calendar_create_event(client: AsyncClient):
    """Test creating a calendar event in open mode."""
    response = await client.post(
        "/api/calendar/",
        json={
            "title": "Court Hearing",
            "start_datetime": "2025-12-15T09:00:00",
            "event_type": "hearing",
            "is_critical": True,
            "reminder_days": 7,
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Court Hearing"
    assert data["is_critical"] is True


@pytest.mark.anyio
async def test_calendar_upcoming(client: AsyncClient):
    """Test upcoming deadlines endpoint."""
    response = await client.get("/api/calendar/upcoming?days=30")
    assert response.status_code == 200
    data = response.json()
    assert "critical" in data
    assert "upcoming" in data


# =============================================================================
# Copilot Tests
# =============================================================================

@pytest.mark.anyio
async def test_copilot_status(client: AsyncClient):
    """Test AI copilot status endpoint."""
    response = await client.get("/api/copilot/status")
    assert response.status_code == 200
    data = response.json()
    assert "available" in data
    assert "provider" in data


# =============================================================================
# Auth Tests (Legacy - should redirect to storage)
# =============================================================================

@pytest.mark.anyio
async def test_auth_me_open_mode(client: AsyncClient):
    """Test auth/me endpoint in open mode returns dummy user."""
    response = await client.get("/api/auth/me")
    assert response.status_code == 200
    data = response.json()
    # In open mode, should return open-mode-user
    assert "user_id" in data or "provider" in data


# =============================================================================
# Cleanup
# =============================================================================

@pytest.fixture(autouse=True)
async def cleanup():
    """Clean up test database after tests."""
    yield
    import os
    if os.path.exists("test_semptify.db"):
        try:
            os.remove("test_semptify.db")
        except PermissionError:
            pass
