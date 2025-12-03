"""
Adaptive UI API Router

Endpoints for the self-building interface.
The frontend calls these to get widgets to display.
Now integrated with the Context Loop for unified state.
"""

from fastapi import APIRouter, Header, Query
from typing import Optional

from app.services.adaptive_ui import (
    adaptive_ui, 
    TenancyPhase,
    sync_from_context_loop,
    build_ui_with_intensity,
)


router = APIRouter(prefix="/api/ui", tags=["Adaptive UI"])


@router.get("/widgets")
async def get_widgets(
    x_user_id: Optional[str] = Header(None, alias="X-User-ID"),
    user_id: Optional[str] = Query(None),
):
    """
    Get the adaptive UI widgets for this user.
    
    Now synced with Context Loop for unified state.
    The frontend renders these widgets dynamically.
    Order matters - first widgets are highest priority.
    """
    uid = x_user_id or user_id or "anonymous"
    
    # Use integrated builder with intensity
    result = build_ui_with_intensity(uid)
    
    return {
        "user_id": uid,
        "widget_count": len(result["widgets"]),
        "widgets": result["widgets"],
        "intensity": result.get("intensity", {}),
    }


@router.get("/context")
async def get_context(
    x_user_id: Optional[str] = Header(None, alias="X-User-ID"),
    user_id: Optional[str] = Query(None),
):
    """Get the current user context (what we know about them)."""
    uid = x_user_id or user_id or "anonymous"
    
    ctx = adaptive_ui.get_or_create_context(uid)
    
    return {
        "user_id": uid,
        "context": ctx.to_dict(),
    }


@router.post("/dismiss/{widget_id}")
async def dismiss_widget(
    widget_id: str,
    x_user_id: Optional[str] = Header(None, alias="X-User-ID"),
    user_id: Optional[str] = Query(None),
):
    """Dismiss a widget so it doesn't show again."""
    uid = x_user_id or user_id or "anonymous"
    
    adaptive_ui.dismiss_widget(uid, widget_id)
    
    return {"status": "dismissed", "widget_id": widget_id}


@router.post("/action/{action}")
async def record_action(
    action: str,
    x_user_id: Optional[str] = Header(None, alias="X-User-ID"),
    user_id: Optional[str] = Query(None),
):
    """Record that the user took an action (for learning)."""
    uid = x_user_id or user_id or "anonymous"
    
    adaptive_ui.record_action(uid, action)
    
    return {"status": "recorded", "action": action}


@router.post("/context/update")
async def update_context(
    phase: Optional[str] = None,
    jurisdiction: Optional[str] = None,
    x_user_id: Optional[str] = Header(None, alias="X-User-ID"),
    user_id: Optional[str] = Query(None),
):
    """Manually update user context."""
    uid = x_user_id or user_id or "anonymous"
    
    ctx = adaptive_ui.get_or_create_context(uid)
    
    if phase:
        try:
            ctx.phase = TenancyPhase(phase)
        except ValueError:
            pass
    
    if jurisdiction:
        ctx.jurisdiction = jurisdiction
    
    return {
        "status": "updated",
        "context": ctx.to_dict(),
    }


@router.get("/predictions")
async def get_predictions(
    x_user_id: Optional[str] = Header(None, alias="X-User-ID"),
    user_id: Optional[str] = Query(None),
):
    """
    Get predictions about what the user might need.
    
    This is Semptify being smart - anticipating needs
    based on their situation and patterns.
    """
    uid = x_user_id or user_id or "anonymous"
    
    ctx = adaptive_ui.get_or_create_context(uid)
    predictions = adaptive_ui._predict_next_needs(ctx)
    
    return {
        "user_id": uid,
        "predictions": [p.to_dict() for p in predictions],
        "based_on": {
            "documents": ctx.documents,
            "phase": ctx.phase.value,
            "issues": adaptive_ui.detect_issues(ctx),
        },
    }
