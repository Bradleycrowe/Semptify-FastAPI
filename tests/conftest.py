"""
Semptify 5.0 - Shared Test Fixtures
Provides reusable fixtures for authentication, database, and mocking.
"""

import os
import pytest
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport

# Configure test environment BEFORE importing app
os.environ["SECURITY_MODE"] = "open"
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test_semptify.db"
os.environ["TESTING"] = "true"

from app.main import app
from app.core.config import get_settings


# =============================================================================
# Core Fixtures
# =============================================================================

@pytest.fixture
def anyio_backend():
    """Use asyncio for async tests."""
    return "asyncio"


@pytest.fixture(scope="function", autouse=True)
async def setup_test_database():
    """Create database tables before each test and clean up after."""
    from app.core.database import get_engine, Base
    from app.models import models  # Import all models to register them
    
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield
    
    # Cleanup after test
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    
    await engine.dispose()


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """Create async test client."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
async def authenticated_client() -> AsyncGenerator[AsyncClient, None]:
    """Create authenticated test client with mock session in both cache and database."""
    # Use properly formatted user ID: <provider><role><8-char-unique>
    # G=Google, U=User, followed by 8 alphanumeric chars = 10 chars total
    test_uid = "GUtest1234"  # Google + User + 8-char unique

    # Create session in database
    from app.core.database import get_engine
    from app.models.models import Session as SessionModel, User, StorageConfig
    from sqlalchemy.ext.asyncio import async_sessionmaker
    from app.routers.storage import _encrypt_string
    from datetime import datetime, timezone

    engine = get_engine()
    async_session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with async_session_factory() as session:
        # Create user
        user = User(
            id=test_uid,
            primary_provider="google_drive",
            storage_user_id=test_uid,
            default_role="user",
            email="test@example.com",
        )
        session.add(user)

        # Create session record
        session_record = SessionModel(
            user_id=test_uid,
            provider="google_drive",
            access_token_encrypted=_encrypt_string("mock_access_token", test_uid),
            refresh_token_encrypted=_encrypt_string("mock_refresh_token", test_uid),
            authenticated_at=datetime.now(timezone.utc),
            last_activity=datetime.now(timezone.utc),
        )
        session.add(session_record)

        # Create storage config
        storage_config = StorageConfig(
            user_id=test_uid,
            primary_provider="google_drive",
            connected_providers="google_drive",
        )
        session.add(storage_config)

        await session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        cookies={"semptify_uid": test_uid}
    ) as ac:
        # Also inject into memory cache for faster lookups
        from app.routers.storage import SESSIONS
        SESSIONS[test_uid] = {
            "user_id": test_uid,
            "provider": "google_drive",
            "role": "user",
            "access_token": "mock_access_token",
            "refresh_token": "mock_refresh_token",
            "authenticated_at": "2025-11-30T00:00:00",
        }
        yield ac
        # Cleanup
        SESSIONS.pop(test_uid, None)


@pytest.fixture
def test_user_id() -> str:
    """Return a consistent test user ID."""
    return "GUtest1234"


@pytest.fixture
def settings():
    """Get test settings."""
    return get_settings()


# =============================================================================
# Database Fixtures
# =============================================================================

@pytest.fixture
async def db_session():
    """Create a test database session."""
    from app.core.database import get_db_session
    async with get_db_session() as session:
        yield session


@pytest.fixture(autouse=True)
async def cleanup_test_db():
    """Clean up test database after tests."""
    yield
    import os
    for db_file in ["test_semptify.db", "test_semptify.db-shm", "test_semptify.db-wal"]:
        if os.path.exists(db_file):
            try:
                os.remove(db_file)
            except PermissionError:
                pass


# =============================================================================
# Mock Fixtures
# =============================================================================

@pytest.fixture
def mock_storage_provider():
    """Mock storage provider for testing."""
    mock = AsyncMock()
    mock.create_folder = AsyncMock(return_value=True)
    mock.upload_file = AsyncMock(return_value=MagicMock(
        id="mock_file_id",
        name="test.pdf",
        path="/.semptify/vault/test.pdf",
        size=1024,
    ))
    mock.download_file = AsyncMock(return_value=b"mock file content")
    mock.list_files = AsyncMock(return_value=[])
    mock.delete_file = AsyncMock(return_value=True)
    return mock


@pytest.fixture
def mock_azure_ai():
    """Mock Azure AI services."""
    with patch("app.services.azure_ai.AzureAIService") as mock:
        instance = mock.return_value
        instance.analyze_document = AsyncMock(return_value={
            "content": "Mock document content",
            "pages": [{"page_number": 1, "text": "Mock text"}],
        })
        instance.classify_document = AsyncMock(return_value={
            "doc_type": "lease",
            "confidence": 0.95,
        })
        yield mock


@pytest.fixture
def mock_openai():
    """Mock OpenAI for copilot tests."""
    with patch("httpx.AsyncClient") as mock:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{
                "message": {
                    "content": "This is a mock AI response for tenant rights."
                }
            }]
        }
        mock_response.raise_for_status = MagicMock()
        mock.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
        yield mock


# =============================================================================
# Test Data Fixtures
# =============================================================================

@pytest.fixture
def sample_document_data():
    """Sample document upload data."""
    return {
        "filename": "test_lease.pdf",
        "content": b"%PDF-1.4 mock pdf content",
        "content_type": "application/pdf",
    }


@pytest.fixture
def sample_timeline_event():
    """Sample timeline event data."""
    return {
        "event_type": "notice",
        "title": "14-Day Notice Received",
        "description": "Received 14-day notice for non-payment",
        "event_date": "2025-11-25T10:00:00",
        "is_evidence": True,
    }


@pytest.fixture
def sample_calendar_event():
    """Sample calendar event data."""
    return {
        "title": "Court Hearing",
        "start_datetime": "2025-12-15T09:00:00",
        "event_type": "hearing",
        "is_critical": True,
        "reminder_days": 7,
        "notes": "Dakota County Courthouse, Room 301",
    }


@pytest.fixture
def sample_eviction_form_data():
    """Sample eviction answer form data."""
    return {
        "tenant_name": "John Doe",
        "landlord_name": "ABC Properties LLC",
        "case_number": "27-CV-25-12345",
        "address": "123 Main Street, Apt 4B",
        "city": "Burnsville",
        "state": "MN",
        "zip_code": "55337",
        "served_date": "2025-11-20",
        "defenses": ["nonpayment", "habitability"],
        "defense_details": "Rent was withheld due to unrepaired heating system",
        "counterclaim": False,
    }


# =============================================================================
# Eviction Flow Fixtures
# =============================================================================

@pytest.fixture
def eviction_languages():
    """Supported languages for eviction forms."""
    return ["en", "es", "so", "ar"]


@pytest.fixture
def eviction_motion_types():
    """Available motion types."""
    return ["dismiss", "continuance", "stay", "fee_waiver"]


# =============================================================================
# Cleanup Helpers
# =============================================================================

# Note: Timeline and calendar now use database storage, 
# cleaned up by cleanup_test_db fixture
