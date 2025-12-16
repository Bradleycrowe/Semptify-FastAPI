"""
Timeline Router (Database-backed)
Event tracking and history for tenant journey.
"""

import uuid
from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query, status, UploadFile, File, Form
from pydantic import BaseModel, Field
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.security import require_user, StorageUser
from app.core.utc import utc_now
from app.models.models import TimelineEvent as TimelineEventModel
from app.services.timeline_builder import TimelineBuilder, extract_timeline_from_text


router = APIRouter()


# =============================================================================
# Schemas
# =============================================================================

VALID_EVENT_TYPES = ["notice", "payment", "maintenance", "communication", "court", "other"]


class TimelineEventCreate(BaseModel):
    """Create a new timeline event."""
    event_type: str = Field(..., description="Type: notice, payment, maintenance, communication, court, other")
    title: str = Field(..., max_length=255)
    description: Optional[str] = None
    event_date: str = Field(..., description="ISO format date when event occurred")
    document_id: Optional[str] = Field(None, description="Link to a vault document")
    is_evidence: bool = Field(False, description="Mark as evidence for court")


class TimelineEventUpdate(BaseModel):
    """Update an existing timeline event."""
    title: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    event_date: Optional[str] = None
    document_id: Optional[str] = None
    is_evidence: Optional[bool] = None


class TimelineEventResponse(BaseModel):
    """Timeline event response."""
    id: str
    event_type: str
    title: str
    description: Optional[str] = None
    event_date: str
    document_id: Optional[str] = None
    is_evidence: bool
    created_at: str


class TimelineListResponse(BaseModel):
    """List of timeline events."""
    events: list[TimelineEventResponse]
    total: int


# =============================================================================
# Helper Functions
# =============================================================================

def _parse_date(date_str: str) -> datetime:
    """Parse ISO date string to datetime."""
    try:
        return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
    except ValueError:
        raise HTTPException(status_code=422, detail=f"Invalid date format: {date_str}")


def _model_to_response(event: TimelineEventModel) -> TimelineEventResponse:
    """Convert database model to response schema."""
    return TimelineEventResponse(
        id=event.id,
        event_type=event.event_type or "other",
        title=event.title,
        description=event.description,
        event_date=event.event_date.isoformat() if event.event_date else "",
        document_id=event.document_id,
        is_evidence=event.is_evidence or False,
        created_at=event.created_at.isoformat() if event.created_at else "",
    )


# =============================================================================
# Endpoints
# =============================================================================

@router.post(
    "/",
    response_model=TimelineEventResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_event(
    event: TimelineEventCreate,
    user: StorageUser = Depends(require_user),
):
    """
    Create a new timeline event.

    Events track important moments in your tenant journey:
    - Notices received or sent
    - Rent payments
    - Maintenance requests
    - Communications with landlord
    - Court dates or filings
    """
    if event.event_type not in VALID_EVENT_TYPES:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid event_type. Must be one of: {VALID_EVENT_TYPES}"
        )

    event_date = _parse_date(event.event_date)

    async with get_db_session() as session:
        db_event = TimelineEventModel(
            id=str(uuid.uuid4()),
            user_id=user.user_id,
            event_type=event.event_type,
            title=event.title,
            description=event.description,
            event_date=event_date,
            document_id=event.document_id,
            is_evidence=event.is_evidence,
            created_at=datetime.utcnow(),
        )
        session.add(db_event)
        await session.commit()
        await session.refresh(db_event)
        
        # Emit brain event for timeline update
        try:
            from app.services.positronic_brain import get_brain, BrainEvent, EventType as BrainEventType, ModuleType
            brain = get_brain()
            await brain.emit(BrainEvent(
                event_type=BrainEventType.TIMELINE_EVENT_ADDED,
                source_module=ModuleType.TIMELINE,
                data={
                    "event_id": db_event.id,
                    "event_type": db_event.event_type,
                    "title": db_event.title,
                    "event_date": db_event.event_date.isoformat() if db_event.event_date else None,
                    "is_evidence": db_event.is_evidence
                },
                user_id=user.user_id
            ))
        except Exception:
            pass  # Brain integration is optional
        
        return _model_to_response(db_event)
@router.get("/", response_model=TimelineListResponse)
async def list_events(
    event_type: Optional[str] = Query(None, description="Filter by event type"),
    evidence_only: bool = Query(False, description="Only show evidence-marked events"),
    start_date: Optional[str] = Query(None, description="Filter events after this date (ISO)"),
    end_date: Optional[str] = Query(None, description="Filter events before this date (ISO)"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: StorageUser = Depends(require_user),
):
    """
    List timeline events with optional filtering.
    
    Events come from two sources:
    1. User's vault documents (auto-generated based on document type/date)
    2. Manually created timeline events
    
    Events are returned in reverse chronological order (newest first).
    """
    from app.models.models import Document as DocumentModel
    
    async with get_db_session() as session:
        # Get timeline events from database
        query = select(TimelineEventModel).where(
            TimelineEventModel.user_id == user.user_id
        )

        # Apply filters to manual events
        if event_type:
            query = query.where(TimelineEventModel.event_type == event_type)
        if evidence_only:
            query = query.where(TimelineEventModel.is_evidence == True)
        if start_date:
            start_dt = _parse_date(start_date)
            query = query.where(TimelineEventModel.event_date >= start_dt)
        if end_date:
            end_dt = _parse_date(end_date)
            query = query.where(TimelineEventModel.event_date <= end_dt)

        result = await session.execute(query)
        manual_events = result.scalars().all()
        
        # Get documents from vault to generate timeline events
        doc_query = select(DocumentModel).where(
            DocumentModel.user_id == user.user_id
        )
        doc_result = await session.execute(doc_query)
        documents = doc_result.scalars().all()
        
        # Convert documents to timeline events
        doc_events = []
        doc_type_to_event_type = {
            "notice": "notice",
            "lease": "other",
            "legal": "court",
            "correspondence": "communication",
            "photo": "other",
            "receipt": "payment",
            "payment": "payment",
        }
        
        for doc in documents:
            doc_event_type = doc_type_to_event_type.get(doc.document_type, "other")
            
            # Apply event_type filter
            if event_type and doc_event_type != event_type:
                continue
            
            # Apply date filters
            doc_date = doc.uploaded_at
            if start_date:
                start_dt = _parse_date(start_date)
                if doc_date < start_dt:
                    continue
            if end_date:
                end_dt = _parse_date(end_date)
                if doc_date > end_dt:
                    continue
            
            # Skip if evidence_only and not marked (docs are evidence by default)
            # All vault documents are considered potential evidence
            
            doc_events.append(TimelineEventResponse(
                id=f"doc_{doc.id}",
                event_type=doc_event_type,
                title=f"Document: {doc.original_filename}",
                description=doc.description or f"Uploaded {doc.document_type or 'document'}: {doc.original_filename}",
                event_date=doc_date.isoformat() if doc_date else "",
                document_id=doc.id,
                is_evidence=True,  # All vault docs are potential evidence
                created_at=doc_date.isoformat() if doc_date else "",
            ))
        
        # Combine manual events and document events
        all_events = [_model_to_response(e) for e in manual_events] + doc_events
        
        # Sort by event_date descending
        all_events.sort(key=lambda e: e.event_date, reverse=True)
        
        # Apply pagination
        total = len(all_events)
        paginated_events = all_events[offset:offset + limit]

        return TimelineListResponse(
            events=paginated_events,
            total=total,
        )
@router.get("/{event_id}", response_model=TimelineEventResponse)
async def get_event(
    event_id: str,
    user: StorageUser = Depends(require_user),
):
    """Get a specific timeline event."""
    async with get_db_session() as session:
        query = select(TimelineEventModel).where(
            and_(
                TimelineEventModel.id == event_id,
                TimelineEventModel.user_id == user.user_id
            )
        )
        result = await session.execute(query)
        event = result.scalar_one_or_none()

        if not event:
            raise HTTPException(status_code=404, detail="Event not found")

        return _model_to_response(event)


@router.patch("/{event_id}", response_model=TimelineEventResponse)
async def update_event(
    event_id: str,
    updates: TimelineEventUpdate,
    user: StorageUser = Depends(require_user),
):
    """Update a timeline event."""
    async with get_db_session() as session:
        query = select(TimelineEventModel).where(
            and_(
                TimelineEventModel.id == event_id,
                TimelineEventModel.user_id == user.user_id
            )
        )
        result = await session.execute(query)
        event = result.scalar_one_or_none()

        if not event:
            raise HTTPException(status_code=404, detail="Event not found")

        # Update fields
        update_data = updates.model_dump(exclude_unset=True)
        
        # Parse event_date if provided
        if "event_date" in update_data and update_data["event_date"]:
            update_data["event_date"] = _parse_date(update_data["event_date"])
        
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
    """Delete a timeline event."""
    async with get_db_session() as session:
        query = select(TimelineEventModel).where(
            and_(
                TimelineEventModel.id == event_id,
                TimelineEventModel.user_id == user.user_id
            )
        )
        result = await session.execute(query)
        event = result.scalar_one_or_none()

        if not event:
            raise HTTPException(status_code=404, detail="Event not found")

        await session.delete(event)
        await session.commit()


@router.get("/types/summary")
async def event_type_summary(
    user: StorageUser = Depends(require_user),
):
    """
    Get a summary of events by type.
    Useful for dashboard widgets.
    """
    async with get_db_session() as session:
        # Get all events for user
        query = select(TimelineEventModel).where(
            TimelineEventModel.user_id == user.user_id
        )
        result = await session.execute(query)
        events = result.scalars().all()

        summary = {}
        for event in events:
            event_type = event.event_type or "other"
            if event_type not in summary:
                summary[event_type] = {"count": 0, "evidence_count": 0}
            summary[event_type]["count"] += 1
            if event.is_evidence:
                summary[event_type]["evidence_count"] += 1

        return {
            "summary": summary,
            "total_events": len(events),
            "total_evidence": sum(1 for e in events if e.is_evidence),
        }


# =============================================================================
# Auto-Build Timeline from Documents
# =============================================================================

class AutoBuildRequest(BaseModel):
    """Request to auto-build timeline from document text."""
    text: str = Field(..., description="Document text to extract events from")
    document_id: Optional[str] = Field(None, description="Source document ID")
    filename: Optional[str] = Field(None, description="Source filename")
    document_type: Optional[str] = Field(None, description="Type of document (notice, lease, etc.)")
    auto_save: bool = Field(True, description="Automatically save extracted events to timeline")


class ExtractedEventResponse(BaseModel):
    """An extracted timeline event."""
    id: str
    event_type: str
    title: str
    description: str
    event_date: Optional[str]
    event_date_text: str
    is_deadline: bool
    is_evidence: bool
    urgency: str
    confidence: float
    source_document_id: Optional[str]
    source_filename: Optional[str]


class AutoBuildResponse(BaseModel):
    """Response from auto-build timeline."""
    events: List[ExtractedEventResponse]
    total_events_found: int
    total_deadlines_found: int
    events_saved: int
    earliest_date: Optional[str]
    latest_date: Optional[str]
    warnings: List[str]


@router.post("/auto-build", response_model=AutoBuildResponse)
async def auto_build_timeline(
    request: AutoBuildRequest,
    user: StorageUser = Depends(require_user),
):
    """
    Automatically extract timeline events from document text.
    
    This endpoint analyzes document text for dates and events,
    then optionally saves them to the user's timeline.
    
    Perfect for:
    - Processing uploaded documents
    - Building case history from evidence
    - Identifying deadlines from notices
    """
    builder = TimelineBuilder()
    result = await builder.build_from_text(
        text=request.text,
        document_id=request.document_id,
        filename=request.filename,
        document_type=request.document_type,
    )
    
    events_saved = 0
    
    # Save events to database if requested
    if request.auto_save and result.events:
        async with get_db_session() as session:
            for event in result.events:
                if event.event_date:
                    db_event = TimelineEventModel(
                        id=event.id,
                        user_id=user.user_id,
                        event_type=event.event_type.value if hasattr(event.event_type, 'value') else str(event.event_type),
                        title=event.title,
                        description=event.description,
                        event_date=datetime.combine(event.event_date, datetime.min.time()),
                        document_id=event.source_document_id,
                        is_evidence=event.is_evidence,
                        created_at=utc_now(),
                    )
                    session.add(db_event)
                    events_saved += 1
            
            await session.commit()
    
    # Convert to response format
    response_events = [
        ExtractedEventResponse(
            id=e.id,
            event_type=e.event_type.value if hasattr(e.event_type, 'value') else str(e.event_type),
            title=e.title,
            description=e.description,
            event_date=e.event_date.isoformat() if e.event_date else None,
            event_date_text=e.event_date_text,
            is_deadline=e.is_deadline,
            is_evidence=e.is_evidence,
            urgency=e.urgency,
            confidence=e.confidence,
            source_document_id=e.source_document_id,
            source_filename=e.source_filename,
        )
        for e in result.events
    ]
    
    return AutoBuildResponse(
        events=response_events,
        total_events_found=result.total_events_found,
        total_deadlines_found=result.total_deadlines_found,
        events_saved=events_saved,
        earliest_date=result.earliest_date.isoformat() if result.earliest_date else None,
        latest_date=result.latest_date.isoformat() if result.latest_date else None,
        warnings=result.warnings,
    )


@router.post("/auto-build/preview")
async def preview_auto_build(
    request: AutoBuildRequest,
    user: StorageUser = Depends(require_user),
):
    """
    Preview timeline events without saving.
    
    Same as auto-build but doesn't persist to database.
    Use this to show users what will be extracted before committing.
    """
    # Force auto_save off for preview
    request.auto_save = False
    
    builder = TimelineBuilder()
    result = await builder.build_from_text(
        text=request.text,
        document_id=request.document_id,
        filename=request.filename,
        document_type=request.document_type,
    )
    
    return {
        "preview": True,
        "events": [e.to_dict() for e in result.events],
        "total_events_found": result.total_events_found,
        "total_deadlines_found": result.total_deadlines_found,
        "earliest_date": result.earliest_date.isoformat() if result.earliest_date else None,
        "latest_date": result.latest_date.isoformat() if result.latest_date else None,
        "warnings": result.warnings,
    }


@router.post("/auto-build/from-document/{document_id}")
async def auto_build_from_document(
    document_id: str,
    auto_save: bool = Query(True, description="Save events to timeline"),
    user: StorageUser = Depends(require_user),
):
    """
    Auto-build timeline from an existing vault document.
    
    Fetches the document text and extracts timeline events.
    """
    from app.models.models import Document as DocumentModel
    
    async with get_db_session() as session:
        # Get the document
        query = select(DocumentModel).where(
            and_(
                DocumentModel.id == document_id,
                DocumentModel.user_id == user.user_id
            )
        )
        result = await session.execute(query)
        document = result.scalar_one_or_none()
        
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")
        
        # Get document text (from extracted_text or content)
        text = document.extracted_text or ""
        if not text and document.content:
            text = document.content.decode('utf-8', errors='ignore') if isinstance(document.content, bytes) else str(document.content)
        
        if not text:
            raise HTTPException(status_code=400, detail="Document has no extractable text")
        
        # Build timeline
        builder = TimelineBuilder()
        build_result = await builder.build_from_text(
            text=text,
            document_id=document_id,
            filename=document.filename,
            document_type=document.document_type,
        )
        
        events_saved = 0
        
        # Save events if requested
        if auto_save and build_result.events:
            for event in build_result.events:
                if event.event_date:
                    db_event = TimelineEventModel(
                        id=event.id,
                        user_id=user.user_id,
                        event_type=event.event_type.value if hasattr(event.event_type, 'value') else str(event.event_type),
                        title=event.title,
                        description=event.description,
                        event_date=datetime.combine(event.event_date, datetime.min.time()),
                        document_id=document_id,
                        is_evidence=True,
                        created_at=utc_now(),
                    )
                    session.add(db_event)
                    events_saved += 1
            
            await session.commit()
        
        return {
            "document_id": document_id,
            "document_filename": document.filename,
            "events": [e.to_dict() for e in build_result.events],
            "total_events_found": build_result.total_events_found,
            "total_deadlines_found": build_result.total_deadlines_found,
            "events_saved": events_saved,
            "warnings": build_result.warnings,
        }