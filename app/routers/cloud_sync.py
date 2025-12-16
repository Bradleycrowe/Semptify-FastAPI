"""
🔄 User Cloud Sync - API Router
================================

Endpoints for syncing user data with their cloud storage.
All data is stored in the user's connected cloud (Google Drive, Dropbox, OneDrive).
Semptify stores NOTHING - we just orchestrate the sync.
"""

from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.config import get_settings, Settings
from app.core.security import require_user, StorageUser
from app.services.user_cloud_sync import (
    UserCloudSync,
    UserProfile,
    CaseData,
    SyncStatus,
    QuickSyncData,
)

import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/sync", tags=["Cloud Sync"])


# =============================================================================
# Request/Response Models
# =============================================================================

class ProfileUpdate(BaseModel):
    """Profile update request."""
    display_name: Optional[str] = None
    theme: Optional[str] = None
    language: Optional[str] = None
    notifications: Optional[bool] = None
    auto_sync: Optional[bool] = None


class CaseUpdate(BaseModel):
    """Case update request."""
    case_number: Optional[str] = None
    tenant_name: Optional[str] = None
    tenant_address: Optional[str] = None
    landlord_name: Optional[str] = None
    landlord_address: Optional[str] = None
    property_address: Optional[str] = None
    notice_date: Optional[str] = None
    summons_date: Optional[str] = None
    hearing_date: Optional[str] = None
    answer_deadline: Optional[str] = None
    rent_amount: Optional[float] = None
    amount_owed: Optional[float] = None
    eviction_reason: Optional[str] = None
    defenses: Optional[list] = None
    notes: Optional[str] = None


class TimelineEventCreate(BaseModel):
    """Create timeline event."""
    event_type: str
    title: str
    description: Optional[str] = None
    event_date: str
    is_evidence: bool = False


class CalendarEventCreate(BaseModel):
    """Create calendar event."""
    title: str
    event_type: str
    start_datetime: str
    end_datetime: Optional[str] = None
    is_critical: bool = False
    reminder_days: int = 3


class ImportRequest(BaseModel):
    """Import data request."""
    data: dict


class SyncResponse(BaseModel):
    """Sync status response."""
    status: str
    user_id: str
    synced_at: Optional[str] = None
    profile: Optional[dict] = None
    case_summary: Optional[dict] = None
    counts: Optional[dict] = None
    message: Optional[str] = None


# =============================================================================
# Storage Client Helper
# =============================================================================

class MockStorageClient:
    """Mock storage client for open/demo mode."""

    def __init__(self, user_id: str):
        self.user_id = user_id
        self.provider_name = "demo_storage"
        self._data = {}
        self._folders = set()

    async def is_connected(self) -> bool:
        """Check if storage is connected - always True for mock."""
        return True

    async def read_file(self, path: str) -> Optional[str]:
        """Read file from mock storage."""
        return self._data.get(path)

    async def write_file(self, path: str, content: str) -> bool:
        """Write file to mock storage."""
        self._data[path] = content
        return True

    async def create_folder(self, path: str) -> bool:
        """Create folder in mock storage."""
        self._folders.add(path)
        return True

    async def create_folder_if_not_exists(self, path: str) -> bool:
        """Create folder if it doesn't exist."""
        self._folders.add(path)
        return True

    async def file_exists(self, path: str) -> bool:
        """Check if file exists."""
        return path in self._data
async def get_storage_client(user: StorageUser, db: AsyncSession, settings: Settings):
    """
    Get the appropriate storage client for the user's provider.
    This creates a client based on their OAuth tokens.
    In open mode, returns a mock client.
    """
    # In open mode, use mock storage
    if settings.security_mode == "open":
        return MockStorageClient(user.user_id)
    
    from app.routers.storage import get_valid_session

    session = await get_valid_session(db, user.user_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No valid storage session. Please reconnect your cloud storage."
        )

    provider = session.get("provider")
    access_token = session.get("access_token")

    if provider == "google_drive":
        from app.services.storage.google_drive import GoogleDriveClient
        return GoogleDriveClient(access_token)
    elif provider == "dropbox":
        from app.services.storage.dropbox import DropboxProvider
        return DropboxProvider(access_token)
    elif provider == "onedrive":
        from app.services.storage.onedrive import OneDriveProvider
        return OneDriveProvider(access_token)
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown storage provider: {provider}"
        )


async def get_sync_service(
    user: StorageUser,
    db: AsyncSession,
    settings: Settings,
) -> UserCloudSync:
    """
    Get UserCloudSync service for current user.
    
    NOTE: This is a regular async function, NOT a FastAPI dependency.
    Endpoints must resolve user, db, and settings via Depends() and pass them.
    """
    storage = await get_storage_client(user, db, settings)
    return UserCloudSync(storage, user.user_id)
# =============================================================================
# Sync Endpoints
# =============================================================================

@router.get("/status", response_model=SyncResponse)
async def get_sync_status(
    user: StorageUser = Depends(require_user),
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    """
    📊 Get current sync status.

    Returns the current sync state and summary of stored data.
    """
    try:
        sync = await get_sync_service(user, db, settings)        # Try to load cached data
        summary = QuickSyncData.from_sync(sync)

        return SyncResponse(
            status=sync.status.value,
            user_id=user.user_id,
            synced_at=datetime.now(timezone.utc).isoformat(),
            **summary,
        )
    except HTTPException:
        # No storage connected - return basic status
        return SyncResponse(
            status="disconnected",
            user_id=user.user_id,
            message="Connect cloud storage to enable sync",
        )
    except Exception as e:
        # Any other error - return disconnected status with error message
        logger.warning("Error getting sync status: %s", str(e))
        return SyncResponse(
            status="error",
            user_id=user.user_id,
            message=f"Sync service unavailable: {str(e)}",
        )
@router.post("/full", response_model=SyncResponse)
async def full_sync(
    background_tasks: BackgroundTasks,
    user: StorageUser = Depends(require_user),
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    """
    🔄 Perform full sync with cloud storage.

    Loads all data from user's cloud storage:
    - Profile settings
    - Case data
    - Timeline events
    - Calendar events
    - Document index
    """
    sync = await get_sync_service(user, db, settings)
    result = await sync.sync_all()
    
    return SyncResponse(
        status=result.get("status", "error"),
        user_id=user.user_id,
        synced_at=result.get("synced_at"),
        profile=result.get("profile"),
        case_summary={
            "case_number": result.get("case", {}).get("case_number") if result.get("case") else None,
        },
        counts={
            "timeline": result.get("timeline_count", 0),
            "calendar": result.get("calendar_count", 0),
            "documents": result.get("document_count", 0),
        },
        message="Full sync complete" if result.get("status") == "synced" else result.get("error"),
    )


# =============================================================================
# Profile Endpoints
# =============================================================================

@router.get("/profile")
async def get_profile(
    user: StorageUser = Depends(require_user),
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    """
    👤 Get user profile from cloud storage.
    """
    sync = await get_sync_service(user, db, settings)
    profile = await sync.get_or_create_profile()
    return profile.to_dict()


@router.put("/profile")
async def update_profile(
    update: ProfileUpdate,
    user: StorageUser = Depends(require_user),
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    """
    ✏️ Update user profile in cloud storage.
    """
    sync = await get_sync_service(user, db, settings)
    profile = await sync.get_or_create_profile()
    
    # Apply updates
    for field, value in update.model_dump(exclude_none=True).items():
        if hasattr(profile, field):
            setattr(profile, field, value)
    
    await sync.save_profile(profile)
    return profile.to_dict()


# =============================================================================
# Case Endpoints
# =============================================================================

@router.get("/case")
async def get_case(
    user: StorageUser = Depends(require_user),
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    """
    📋 Get case data from cloud storage.
    """
    sync = await get_sync_service(user, db, settings)
    case = await sync.get_or_create_case()
    return case.to_dict()


@router.put("/case")
async def update_case(
    update: CaseUpdate,
    user: StorageUser = Depends(require_user),
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    """
    ✏️ Update case data in cloud storage.
    """
    sync = await get_sync_service(user, db, settings)
    case = await sync.get_or_create_case()
    
    # Apply updates
    for field, value in update.model_dump(exclude_none=True).items():
        if hasattr(case, field):
            setattr(case, field, value)
    
    await sync.save_case(case)
    return case.to_dict()


# =============================================================================
# Timeline Endpoints (Cloud-backed)
# =============================================================================

@router.get("/timeline")
async def get_timeline(
    user: StorageUser = Depends(require_user),
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    """
    📅 Get timeline events from cloud storage.
    """
    sync = await get_sync_service(user, db, settings)
    events = await sync.load_timeline()
    return {"events": events, "count": len(events)}


@router.post("/timeline")
async def add_timeline_event(
    event: TimelineEventCreate,
    user: StorageUser = Depends(require_user),
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    """
    ➕ Add timeline event to cloud storage.
    """
    import uuid

    sync = await get_sync_service(user, db, settings)
    
    event_data = {
        "id": str(uuid.uuid4()),
        "event_type": event.event_type,
        "title": event.title,
        "description": event.description,
        "event_date": event.event_date,
        "is_evidence": event.is_evidence,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    
    await sync.add_timeline_event(event_data)
    return event_data


# =============================================================================
# Calendar Endpoints (Cloud-backed)
# =============================================================================

@router.get("/calendar")
async def get_calendar(
    user: StorageUser = Depends(require_user),
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    """
    🗓️ Get calendar events from cloud storage.
    """
    sync = await get_sync_service(user, db, settings)
    events = await sync.load_calendar()
    return {"events": events, "count": len(events)}


@router.post("/calendar")
async def add_calendar_event(
    event: CalendarEventCreate,
    user: StorageUser = Depends(require_user),
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    """
    ➕ Add calendar event to cloud storage.
    """
    import uuid

    sync = await get_sync_service(user, db, settings)
    events = await sync.load_calendar()

    event_data = {
        "id": str(uuid.uuid4()),
        "title": event.title,
        "event_type": event.event_type,
        "start_datetime": event.start_datetime,
        "end_datetime": event.end_datetime,
        "is_critical": event.is_critical,
        "reminder_days": event.reminder_days,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    
    events.append(event_data)
    await sync.save_calendar(events)
    return event_data


# =============================================================================
# Export/Import Endpoints
# =============================================================================

@router.get("/export")
async def export_all_data(
    user: StorageUser = Depends(require_user),
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    """
    📤 Export all user data as JSON.

    Returns a complete backup that can be imported later or on another device.
    """
    sync = await get_sync_service(user, db, settings)
    await sync.sync_all()  # Ensure cache is populated
    return await sync.export_all()


@router.post("/import")
async def import_all_data(
    request: ImportRequest,
    user: StorageUser = Depends(require_user),
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    """
    📥 Import user data from JSON backup.

    Restores data from an export backup.
    """
    sync = await get_sync_service(user, db, settings)
    success = await sync.import_all(request.data)
    
    if success:
        return {"status": "imported", "message": "Data imported successfully"}
    else:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to import data"
        )


# =============================================================================
# Document Endpoints
# =============================================================================

@router.get("/documents")
async def get_documents(
    user: StorageUser = Depends(require_user),
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    """
    📄 Get document index from cloud storage.
    """
    sync = await get_sync_service(user, db, settings)
    docs = await sync.load_document_index()
    return {"documents": docs, "count": len(docs)}


# =============================================================================
# Quick Connect Check
# =============================================================================

@router.get("/check")
async def check_storage_connection(
    user: StorageUser = Depends(require_user),
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    """
    🔌 Check if cloud storage is connected and accessible.

    Returns connection status without performing full sync.
    """
    try:
        sync = await get_sync_service(user, db, settings)
        connected = await sync.storage.is_connected()
        
        return {
            "connected": connected,
            "user_id": user.user_id,
            "provider": getattr(sync.storage, 'provider_name', 'unknown'),
            "message": "Storage connected" if connected else "Storage not accessible",
        }
    except HTTPException as e:
        return {
            "connected": False,
            "user_id": user.user_id,
            "provider": None,
            "message": e.detail,
        }
