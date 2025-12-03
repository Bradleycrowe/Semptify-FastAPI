"""
Calendar Router (Database-backed)
Scheduling, deadlines, and reminders.
"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.security import require_user, StorageUser
from app.models.models import CalendarEvent as CalendarEventModel


router = APIRouter()


# =============================================================================
# Schemas
# =============================================================================

VALID_EVENT_TYPES = ["deadline", "hearing", "reminder", "appointment", "rent_due"]

class CalendarEventCreate(BaseModel):
    """Create a calendar event or deadline."""
    title: str = Field(..., max_length=255)
    description: Optional[str] = None
    start_datetime: str = Field(..., description="ISO format datetime")
    end_datetime: Optional[str] = Field(None, description="ISO format datetime (optional)")
    all_day: bool = False
    event_type: str = Field(..., description="Type: deadline, hearing, reminder, appointment, rent_due")
    is_critical: bool = Field(False, description="Critical events affect intensity engine")
    reminder_days: Optional[int] = Field(None, ge=0, le=30, description="Days before to remind")


class CalendarEventUpdate(BaseModel):
    """Update a calendar event."""
    title: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    start_datetime: Optional[str] = None
    end_datetime: Optional[str] = None
    all_day: Optional[bool] = None
    event_type: Optional[str] = None
    is_critical: Optional[bool] = None
    reminder_days: Optional[int] = Field(None, ge=0, le=30)


class CalendarEventResponse(BaseModel):
    """Calendar event response."""
    id: str
    title: str
    description: Optional[str] = None
    start_datetime: str
    end_datetime: Optional[str] = None
    all_day: bool
    event_type: str
    is_critical: bool
    reminder_days: Optional[int] = None
    created_at: str


class CalendarListResponse(BaseModel):
    """List of calendar events."""
    events: list[CalendarEventResponse]
    total: int


class UpcomingDeadlinesResponse(BaseModel):
    """Upcoming deadlines summary."""
    critical: list[CalendarEventResponse]
    upcoming: list[CalendarEventResponse]
    days_to_next_critical: Optional[int] = None


# =============================================================================
# Helper Functions
# =============================================================================

def _parse_datetime(dt_str: str) -> datetime:
    """Parse ISO datetime string to datetime."""
    try:
        return datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
    except ValueError:
        raise HTTPException(status_code=422, detail=f"Invalid datetime format: {dt_str}")


def _model_to_response(event: CalendarEventModel) -> CalendarEventResponse:
    """Convert database model to response schema."""
    return CalendarEventResponse(
        id=event.id,
        title=event.title,
        description=event.description,
        start_datetime=event.start_datetime.isoformat() if event.start_datetime else "",
        end_datetime=event.end_datetime.isoformat() if event.end_datetime else None,
        all_day=event.all_day or False,
        event_type=event.event_type or "reminder",
        is_critical=event.is_critical or False,
        reminder_days=event.reminder_days,
        created_at=event.created_at.isoformat() if event.created_at else "",
    )


# =============================================================================
# Endpoints
# =============================================================================

@router.post(
    "/",
    response_model=CalendarEventResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_event(
    event: CalendarEventCreate,
    user: StorageUser = Depends(require_user),
):
    """
    Create a calendar event or deadline.

    Event types:
    - **deadline**: Legal deadline (response due, filing deadline)
    - **hearing**: Court hearing or mediation
    - **reminder**: General reminder
    - **appointment**: Meeting with attorney, inspector, etc.
    - **rent_due**: Rent payment due date
    """
    if event.event_type not in VALID_EVENT_TYPES:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid event_type. Must be one of: {VALID_EVENT_TYPES}"
        )

    start_dt = _parse_datetime(event.start_datetime)
    end_dt = _parse_datetime(event.end_datetime) if event.end_datetime else None

    async with get_db_session() as session:
        db_event = CalendarEventModel(
            id=str(uuid.uuid4()),
            user_id=user.user_id,
            title=event.title,
            description=event.description,
            start_datetime=start_dt,
            end_datetime=end_dt,
            all_day=event.all_day,
            event_type=event.event_type,
            is_critical=event.is_critical,
            reminder_days=event.reminder_days,
            created_at=datetime.now(timezone.utc),
        )
        session.add(db_event)
        await session.commit()
        await session.refresh(db_event)
        return _model_to_response(db_event)
@router.get("/", response_model=CalendarListResponse)
async def list_events(
    start: Optional[str] = Query(None, description="Start of date range (ISO)"),
    end: Optional[str] = Query(None, description="End of date range (ISO)"),
    event_type: Optional[str] = Query(None, description="Filter by event type"),
    critical_only: bool = Query(False, description="Only show critical events"),
    user: StorageUser = Depends(require_user),
):
    """
    List calendar events, optionally filtered by date range and type.
    """
    async with get_db_session() as session:
        query = select(CalendarEventModel).where(
            CalendarEventModel.user_id == user.user_id
        )

        if start:
            start_dt = _parse_datetime(start)
            query = query.where(CalendarEventModel.start_datetime >= start_dt)

        if end:
            end_dt = _parse_datetime(end)
            query = query.where(CalendarEventModel.start_datetime <= end_dt)

        if event_type:
            query = query.where(CalendarEventModel.event_type == event_type)

        if critical_only:
            query = query.where(CalendarEventModel.is_critical == True)

        # Sort by start datetime
        query = query.order_by(CalendarEventModel.start_datetime.asc())
        
        result = await session.execute(query)
        events = result.scalars().all()

        return CalendarListResponse(
            events=[_model_to_response(e) for e in events],
            total=len(events),
        )
@router.get("/upcoming", response_model=UpcomingDeadlinesResponse)
async def upcoming_deadlines(
    days: int = Query(30, ge=1, le=90, description="Look ahead days"),
    user: StorageUser = Depends(require_user),
):
    """
    Get upcoming deadlines and critical events.

    This endpoint is designed for dashboard widgets and the intensity engine.
    """
    now = datetime.now(timezone.utc)
    cutoff = now + timedelta(days=days)

    async with get_db_session() as session:
        query = select(CalendarEventModel).where(
            and_(
                CalendarEventModel.user_id == user.user_id,
                CalendarEventModel.start_datetime >= now,
                CalendarEventModel.start_datetime <= cutoff
            )
        ).order_by(CalendarEventModel.start_datetime.asc())

        result = await session.execute(query)
        upcoming = result.scalars().all()

        # Separate critical events
        critical = [e for e in upcoming if e.is_critical]

        # Calculate days to next critical
        days_to_next = None
        if critical:
            next_critical_date = critical[0].start_datetime
            if next_critical_date.tzinfo is None:
                next_critical_date = next_critical_date.replace(tzinfo=timezone.utc)
            days_to_next = (next_critical_date - now).days

        return UpcomingDeadlinesResponse(
            critical=[_model_to_response(e) for e in critical],
            upcoming=[_model_to_response(e) for e in upcoming[:10]],
            days_to_next_critical=days_to_next,
        )


@router.get("/{event_id}", response_model=CalendarEventResponse)
async def get_event(
    event_id: str,
    user: StorageUser = Depends(require_user),
):
    """Get a specific calendar event."""
    async with get_db_session() as session:
        query = select(CalendarEventModel).where(
            and_(
                CalendarEventModel.id == event_id,
                CalendarEventModel.user_id == user.user_id
            )
        )
        result = await session.execute(query)
        event = result.scalar_one_or_none()

        if not event:
            raise HTTPException(status_code=404, detail="Event not found")

        return _model_to_response(event)


@router.patch("/{event_id}", response_model=CalendarEventResponse)
async def update_event(
    event_id: str,
    updates: CalendarEventUpdate,
    user: StorageUser = Depends(require_user),
):
    """Update a calendar event."""
    async with get_db_session() as session:
        query = select(CalendarEventModel).where(
            and_(
                CalendarEventModel.id == event_id,
                CalendarEventModel.user_id == user.user_id
            )
        )
        result = await session.execute(query)
        event = result.scalar_one_or_none()

        if not event:
            raise HTTPException(status_code=404, detail="Event not found")

        update_data = updates.model_dump(exclude_unset=True)
        
        # Parse datetime fields if provided
        if "start_datetime" in update_data and update_data["start_datetime"]:
            update_data["start_datetime"] = _parse_datetime(update_data["start_datetime"])
        if "end_datetime" in update_data and update_data["end_datetime"]:
            update_data["end_datetime"] = _parse_datetime(update_data["end_datetime"])
        
        for field, value in update_data.items():
            setattr(event, field, value)

        await session.commit()
        await session.refresh(event)
        return _model_to_response(event)


@router.delete("/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_event(
    event_id: str,
    user: StorageUser = Depends(require_user),
):
    """Delete a calendar event."""
    async with get_db_session() as session:
        query = select(CalendarEventModel).where(
            and_(
                CalendarEventModel.id == event_id,
                CalendarEventModel.user_id == user.user_id
            )
        )
        result = await session.execute(query)
        event = result.scalar_one_or_none()

        if not event:
            raise HTTPException(status_code=404, detail="Event not found")

        await session.delete(event)
        await session.commit()