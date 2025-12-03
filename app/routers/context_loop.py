"""
Context Loop API Router

Endpoints to interact with the Context Data Loop core.
This is the nervous system of Semptify - everything flows through here.
"""

from fastapi import APIRouter, Header, Query, Body
from typing import Optional
from datetime import datetime, timezone

from app.services.context_loop import (
    context_loop,
    EventType,
)


router = APIRouter(prefix="/api/core", tags=["Context Loop"])


@router.get("/state")
async def get_state(
    x_user_id: Optional[str] = Header(None, alias="X-User-ID"),
    user_id: Optional[str] = Query(None),
):
    """
    Get complete state for a user.
    
    This is the unified view of everything Semptify knows about this user:
    - Documents
    - Issues
    - Deadlines
    - Applicable laws
    - Predictions
    - Recommended actions
    """
    uid = x_user_id or user_id or "anonymous"
    return context_loop.get_state(uid)


@router.get("/intensity")
async def get_intensity(
    x_user_id: Optional[str] = Header(None, alias="X-User-ID"),
    user_id: Optional[str] = Query(None),
):
    """
    Get intensity report for a user.
    
    Shows how urgent their situation is on a 0-100 scale,
    with breakdown of contributing factors.
    """
    uid = x_user_id or user_id or "anonymous"
    return context_loop.get_intensity_report(uid)


@router.get("/context")
async def get_context(
    x_user_id: Optional[str] = Header(None, alias="X-User-ID"),
    user_id: Optional[str] = Query(None),
):
    """Get raw context data for a user."""
    uid = x_user_id or user_id or "anonymous"
    context = context_loop.get_context(uid)
    return {
        "user_id": uid,
        "context": context.to_dict(),
    }


@router.post("/event")
async def emit_event(
    event_type: str = Body(..., embed=True),
    data: dict = Body(default={}),
    source: str = Body(default="api"),
    x_user_id: Optional[str] = Header(None, alias="X-User-ID"),
    user_id: Optional[str] = Query(None),
):
    """
    Emit an event into the context loop.
    
    Events flow through the loop and update user state.
    """
    uid = x_user_id or user_id or "anonymous"
    
    # Map string to EventType
    try:
        etype = EventType(event_type)
    except ValueError:
        # Default to action taken for unknown types
        etype = EventType.ACTION_TAKEN
        data["original_type"] = event_type
    
    event = context_loop.emit_event(etype, uid, data, source)
    
    return {
        "status": "processed",
        "event": event.to_dict(),
        "new_state": context_loop.get_state(uid),
    }


@router.post("/document")
async def process_document(
    document_type: str = Body(...),
    document_id: str = Body(default=None),
    filename: str = Body(default=None),
    analysis: dict = Body(default=None),
    x_user_id: Optional[str] = Header(None, alias="X-User-ID"),
    user_id: Optional[str] = Query(None),
):
    """
    Process a document through the context loop.
    
    This is called after a document is uploaded and analyzed.
    Updates user context with document info and any detected issues.
    """
    uid = x_user_id or user_id or "anonymous"
    
    # Emit document uploaded event
    upload_event = context_loop.emit_event(
        EventType.DOCUMENT_UPLOADED,
        uid,
        {
            "type": document_type,
            "id": document_id,
            "filename": filename,
        },
        source="document_upload",
    )
    
    # If we have analysis, emit analyzed event
    if analysis:
        analyzed_event = context_loop.emit_event(
            EventType.DOCUMENT_ANALYZED,
            uid,
            {
                "document_id": document_id,
                "type": document_type,
                **analysis,
            },
            source="document_analysis",
        )
    
    return {
        "status": "processed",
        "document_type": document_type,
        "intensity": upload_event.intensity,
        "severity": upload_event.severity.value,
        "state": context_loop.get_state(uid),
    }


@router.post("/issue")
async def report_issue(
    issue_type: str = Body(...),
    description: str = Body(default=""),
    deadline: str = Body(default=None),
    x_user_id: Optional[str] = Header(None, alias="X-User-ID"),
    user_id: Optional[str] = Query(None),
):
    """
    Report an issue through the context loop.
    
    Issues are things like habitability problems, harassment, etc.
    """
    uid = x_user_id or user_id or "anonymous"
    
    issue_data = {
        "type": issue_type,
        "description": description,
        "reported_at": datetime.now(timezone.utc).isoformat(),
    }

    if deadline:
        issue_data["deadline"] = deadline

    event = context_loop.emit_event(
        EventType.ISSUE_DETECTED,
        uid,
        issue_data,
        source="user_report",
    )
    
    return {
        "status": "recorded",
        "issue": issue_data,
        "intensity": event.intensity,
        "severity": event.severity.value,
        "recommended_actions": context_loop._get_recommended_actions(
            context_loop.get_context(uid)
        ),
    }


@router.post("/deadline")
async def add_deadline(
    deadline_type: str = Body(...),
    date: str = Body(...),
    description: str = Body(default=""),
    x_user_id: Optional[str] = Header(None, alias="X-User-ID"),
    user_id: Optional[str] = Query(None),
):
    """
    Add a deadline to track.

    Deadlines affect intensity calculations significantly.
    """
    uid = x_user_id or user_id or "anonymous"

    deadline_data = {
        "type": deadline_type,
        "date": date,
        "deadline": date,  # Also store as "deadline" for intensity calculation
        "description": description,
        "id": f"dl_{datetime.now(timezone.utc).timestamp()}",
    }

    event = context_loop.emit_event(
        EventType.DEADLINE_APPROACHING,
        uid,
        deadline_data,
        source="user_input",
    )
    
    return {
        "status": "tracked",
        "deadline": deadline_data,
        "intensity_impact": event.intensity,
        "state": context_loop.get_state(uid),
    }


@router.post("/action")
async def record_action(
    action: str = Body(...),
    details: dict = Body(default={}),
    x_user_id: Optional[str] = Header(None, alias="X-User-ID"),
    user_id: Optional[str] = Query(None),
):
    """
    Record that the user took an action.
    
    This feeds into the learning system.
    """
    uid = x_user_id or user_id or "anonymous"
    
    event = context_loop.emit_event(
        EventType.ACTION_TAKEN,
        uid,
        {
            "action": action,
            **details,
        },
        source="user_action",
    )
    
    return {
        "status": "recorded",
        "action": action,
    }


@router.get("/predictions")
async def get_predictions(
    x_user_id: Optional[str] = Header(None, alias="X-User-ID"),
    user_id: Optional[str] = Query(None),
):
    """
    Get predictions for what the user might need.
    
    Based on their documents, issues, and phase.
    """
    uid = x_user_id or user_id or "anonymous"
    context = context_loop.get_context(uid)
    
    return {
        "user_id": uid,
        "predictions": context.predicted_needs,
        "recommended_actions": context_loop._get_recommended_actions(context),
        "based_on": {
            "phase": context.phase,
            "documents": list(context.document_types),
            "active_issues": len(context.active_issues),
            "intensity": context.intensity_score,
        },
    }


@router.get("/events")
async def get_events(
    limit: int = Query(default=50, le=200),
    x_user_id: Optional[str] = Header(None, alias="X-User-ID"),
    user_id: Optional[str] = Query(None),
):
    """Get recent events for a user."""
    uid = x_user_id or user_id or "anonymous"
    context = context_loop.get_context(uid)
    
    events = context.events[-limit:] if context.events else []
    events.reverse()  # Most recent first
    
    return {
        "user_id": uid,
        "event_count": len(events),
        "events": events,
    }


@router.get("/health")
async def loop_health():
    """Check context loop health."""
    return {
        "status": "healthy",
        "active_contexts": len(context_loop.contexts),
        "queued_events": len(context_loop.event_queue),
        "processors": len(context_loop.processors),
        "listeners": len(context_loop.listeners),
    }
