"""
Unified Dashboard API
=====================

Single endpoint that combines data from:
- Emotion Engine (emotional state, UI adaptation)
- Progress Tracker (milestones, case readiness)
- Action Router (personalized actions)

This provides everything the frontend needs in one call.
"""

from fastapi import APIRouter, Query
from typing import Dict, Any, Optional
from pydantic import BaseModel
from datetime import datetime

from ..services.emotion_engine import emotion_engine
from ..services.progress_tracker import progress_tracker
from ..services.action_router import action_router


router = APIRouter(prefix="/dashboard", tags=["Unified Dashboard"])


class DashboardContext(BaseModel):
    """Context for dashboard generation"""
    has_court_date: bool = False
    has_lease: bool = False
    has_payment_records: bool = False
    maintenance_issues: bool = False
    has_notice: bool = False


@router.get("/")
async def get_unified_dashboard(user_id: str = Query("default")):
    """
    Get complete dashboard data in a single call.
    
    Returns:
    - Emotional state and UI adaptation
    - Progress and case readiness
    - Personalized action plan
    - Journey overview
    """
    # Get emotional state
    emotional_state = emotion_engine.get_state(user_id)
    ui_adaptation = emotion_engine.calculate_ui_adaptation(user_id)
    dashboard_config = emotion_engine.get_dashboard_config(user_id)
    
    # Get progress
    progress = progress_tracker.get_progress(user_id)
    readiness = progress_tracker.get_case_readiness(user_id)
    next_milestones = progress_tracker.get_next_milestones(user_id, 3)
    
    # Build case context from progress
    case_context = {
        "has_court_date": progress.court_date is not None,
        "has_lease": "upload_lease" in progress.completed_milestones,
        "has_payment_records": "upload_payment_proof" in progress.completed_milestones,
        "maintenance_issues": "upload_maintenance" in progress.completed_milestones,
        "has_notice": "upload_notice" in progress.completed_milestones
    }

    # Get action plan (convert EmotionalState to dict for action router)
    emotional_dict = {
        "intensity": emotional_state.intensity,
        "clarity": emotional_state.clarity,
        "confidence": emotional_state.confidence,
        "momentum": emotional_state.momentum,
        "overwhelm": emotional_state.overwhelm,
        "trust": emotional_state.trust,
        "resolve": emotional_state.resolve
    }
    action_plan = action_router.generate_action_plan(emotional_dict, case_context)    # Calculate timeline info
    journey_days = 0
    days_to_court = None
    if progress.journey_started:
        journey_days = (datetime.now() - progress.journey_started).days + 1
    if progress.court_date:
        days_to_court = (progress.court_date - datetime.now()).days
    
    return {
        "success": True,
        "timestamp": datetime.now().isoformat(),
        
        # Emotional Layer
        "emotion": {
            "state": emotional_state,
            "mode": dashboard_config.get("dashboard_mode", "guided"),
            "capacity": action_plan.emotional_capacity.value,
            "messages": dashboard_config.get("messages", {}),
            "ui_adaptation": {
                "color_warmth": ui_adaptation.color_warmth,
                "animation_level": ui_adaptation.animation_level,
                "max_items_shown": ui_adaptation.max_items_shown,
                "information_depth": ui_adaptation.information_depth,
                "guidance_level": ui_adaptation.guidance_level,
                "message_tone": ui_adaptation.message_tone
            }
        },
        
        # Progress Layer
        "progress": {
            "readiness": {
                "percent": readiness["percent"],
                "level": readiness["level"],
                "message": readiness["message"]
            },
            "stats": {
                "documents": progress.documents_uploaded,
                "violations": progress.violations_found,
                "points": readiness["total_points"],
                "streak": progress.streak_days,
                "tasks_completed": progress.tasks_completed
            },
            "next_milestones": next_milestones
        },
        
        # Timeline Layer
        "timeline": {
            "journey_days": journey_days,
            "days_to_court": days_to_court,
            "court_date": progress.court_date.strftime("%b %d, %Y") if progress.court_date else None,
            "case_type": progress.case_type
        },
        
        # Action Layer
        "actions": {
            "primary": action_plan.primary_action.to_dict() if action_plan.primary_action else None,
            "secondary": [a.to_dict() for a in action_plan.secondary_actions],
            "self_care": action_plan.self_care_reminder.to_dict() if action_plan.self_care_reminder else None,
            "encouragement": action_plan.encouragement_message,
            "total_estimated_time": action_plan.total_estimated_time
        },
        
        # Visible Sections (based on mode)
        "visible_sections": dashboard_config.get("visible_sections", [
            "mission_status", "today_tasks", "timeline", "quick_actions", "evidence_summary"
        ])
    }


@router.post("/refresh")
async def refresh_dashboard(context: DashboardContext, user_id: str = Query("default")):
    """
    Refresh dashboard with specific context (e.g., after document upload).
    """
    # Get emotional state
    emotional_state = emotion_engine.get_state(user_id)

    # Build case context
    case_context = context.dict()

    # Convert emotional state to dict for action router
    emotional_dict = {
        "intensity": emotional_state.intensity,
        "clarity": emotional_state.clarity,
        "confidence": emotional_state.confidence,
        "momentum": emotional_state.momentum,
        "overwhelm": emotional_state.overwhelm,
        "trust": emotional_state.trust,
        "resolve": emotional_state.resolve
    }

    # Get action plan with provided context
    action_plan = action_router.generate_action_plan(emotional_dict, case_context)    # Get dashboard config
    dashboard_config = emotion_engine.get_dashboard_config(user_id)

    return {
        "success": True,
        "mode": dashboard_config.get("dashboard_mode", "guided"),
        "actions": {
            "primary": action_plan.primary_action.to_dict() if action_plan.primary_action else None,
            "secondary": [a.to_dict() for a in action_plan.secondary_actions],
            "encouragement": action_plan.encouragement_message
        },
        "messages": dashboard_config.get("messages", {})
    }


@router.get("/status-bar")
async def get_status_bar(user_id: str = Query("default")):
    """
    Get minimal status bar data for quick updates.
    """
    progress = progress_tracker.get_progress(user_id)
    readiness = progress_tracker.get_case_readiness(user_id)
    emotional_state = emotion_engine.get_state(user_id)
    
    # Convert to dict for action router
    emotional_dict = {
        "intensity": emotional_state.intensity,
        "clarity": emotional_state.clarity,
        "confidence": emotional_state.confidence,
        "momentum": emotional_state.momentum,
        "overwhelm": emotional_state.overwhelm,
        "trust": emotional_state.trust,
        "resolve": emotional_state.resolve
    }
    mode = action_router.get_dashboard_mode(emotional_dict)
    
    days_to_court = None
    if progress.court_date:
        days_to_court = (progress.court_date - datetime.now()).days
    
    return {
        "mode": mode,
        "readiness_percent": readiness["percent"],
        "readiness_level": readiness["level"],
        "days_to_court": days_to_court,
        "court_date": progress.court_date.strftime("%b %d") if progress.court_date else None,
        "documents": progress.documents_uploaded,
        "violations": progress.violations_found,
        "streak": progress.streak_days,
        "urgent_count": 0  # TODO: Calculate from deadlines
    }


@router.get("/greeting")
async def get_personalized_greeting(user_id: str = Query("default")):
    """
    Get personalized greeting based on time and emotional state.
    """
    progress = progress_tracker.get_progress(user_id)
    emotional_state = emotion_engine.get_state(user_id)
    
    # Convert to dict for action router
    emotional_dict = {
        "intensity": emotional_state.intensity,
        "clarity": emotional_state.clarity,
        "confidence": emotional_state.confidence,
        "momentum": emotional_state.momentum,
        "overwhelm": emotional_state.overwhelm,
        "trust": emotional_state.trust,
        "resolve": emotional_state.resolve
    }
    mode = action_router.get_dashboard_mode(emotional_dict)
    
    # Time-based greeting
    hour = datetime.now().hour
    if hour < 12:
        time_greeting = "Good morning"
    elif hour < 17:
        time_greeting = "Good afternoon"
    else:
        time_greeting = "Good evening"
    
    # Mode-based suffix
    mode_messages = {
        "crisis": "Let's focus on what matters most right now.",
        "focused": "Ready to make progress today?",
        "guided": "Let me help you take the next step.",
        "flow": "You're doing great! Let's keep the momentum.",
        "power": "You're on fire today!"
    }
    
    # Streak recognition
    streak_message = ""
    if progress.streak_days >= 7:
        streak_message = f"🔥 {progress.streak_days} day streak!"
    elif progress.streak_days >= 3:
        streak_message = f"Great consistency - {progress.streak_days} days in a row!"
    
    # Court urgency
    urgency_message = ""
    if progress.court_date:
        days_to_court = (progress.court_date - datetime.now()).days
        if days_to_court <= 3:
            urgency_message = "⚠️ Court is very soon. Let's make sure you're ready."
        elif days_to_court <= 7:
            urgency_message = "Court is coming up. Time to finalize your preparation."
    
    return {
        "greeting": time_greeting,
        "message": mode_messages.get(mode, "Welcome back."),
        "streak_message": streak_message,
        "urgency_message": urgency_message,
        "mode": mode
    }


@router.get("/quick-stats")
async def get_quick_stats(user_id: str = Query("default")):
    """
    Get quick stats for display widgets.
    """
    progress = progress_tracker.get_progress(user_id)
    readiness = progress_tracker.get_case_readiness(user_id)
    
    return {
        "documents_uploaded": progress.documents_uploaded,
        "violations_found": progress.violations_found,
        "case_readiness": readiness["percent"],
        "days_active": (
            (datetime.now() - progress.journey_started).days + 1
            if progress.journey_started else 0
        ),
        "streak_days": progress.streak_days,
        "total_points": readiness["total_points"],
        "tasks_completed": progress.tasks_completed
    }
