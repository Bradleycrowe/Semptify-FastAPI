"""
Action Router API
==================

API endpoints for the Smart Action Router that provides
personalized action recommendations based on emotional state
and case context.
"""

from fastapi import APIRouter, Query
from typing import Dict, Any, Optional, List
from pydantic import BaseModel

from ..services.action_router import action_router, ActionCategory, ActionPriority
from ..services.emotion_engine import emotion_engine


router = APIRouter(prefix="/actions", tags=["Smart Actions"])


class CaseContext(BaseModel):
    """Context about the user's case"""
    has_court_date: bool = False
    court_date: Optional[str] = None
    has_lease: bool = False
    has_payment_records: bool = False
    maintenance_issues: bool = False
    has_notice: bool = False
    case_type: Optional[str] = None
    urgency_level: Optional[str] = None
    documents_count: int = 0


@router.get("/plan")
async def get_action_plan(
    has_court_date: bool = Query(False),
    has_lease: bool = Query(False),
    has_payment_records: bool = Query(False),
    maintenance_issues: bool = Query(False),
    has_notice: bool = Query(False)
):
    """
    Get a personalized action plan based on current emotional state and case context.
    
    This endpoint combines the emotion engine state with case context to generate
    the most appropriate next actions for the user.
    """
    # Get current emotional state
    emotional_state = emotion_engine.get_state()
    
    # Build case context
    case_context = {
        "has_court_date": has_court_date,
        "has_lease": has_lease,
        "has_payment_records": has_payment_records,
        "maintenance_issues": maintenance_issues,
        "has_notice": has_notice
    }
    
    # Generate action plan
    plan = action_router.generate_action_plan(
        emotional_state=emotional_state,
        case_context=case_context
    )
    
    return plan.to_dict()


@router.post("/plan")
async def get_action_plan_with_context(context: CaseContext):
    """
    Get a personalized action plan with full case context.
    """
    # Get current emotional state
    emotional_state = emotion_engine.get_state()
    
    # Convert context to dict
    case_context = context.dict()
    
    # Generate action plan
    plan = action_router.generate_action_plan(
        emotional_state=emotional_state,
        case_context=case_context
    )
    
    return plan.to_dict()


@router.get("/quick-wins")
async def get_quick_wins():
    """
    Get a list of quick win actions - low time, low effort, immediate benefit.
    Good for building momentum when feeling overwhelmed.
    """
    quick_wins = action_router.get_quick_wins({})
    return {
        "quick_wins": [a.to_dict() for a in quick_wins],
        "message": "These are small actions that can help build momentum."
    }


@router.get("/by-category/{category}")
async def get_actions_by_category(category: str):
    """
    Get all actions in a specific category.
    
    Categories: legal_deadline, evidence_collection, document_preparation,
    court_preparation, communication, self_care, learning, organization
    """
    try:
        cat = ActionCategory(category)
        actions = action_router.get_actions_by_category(cat)
        return {
            "category": category,
            "actions": [a.to_dict() for a in actions]
        }
    except ValueError:
        return {
            "error": f"Unknown category: {category}",
            "valid_categories": [c.value for c in ActionCategory]
        }


@router.get("/all")
async def get_all_actions():
    """
    Get all available actions in the system.
    """
    return {
        "actions": [a.to_dict() for a in action_router.action_library.values()],
        "categories": [c.value for c in ActionCategory],
        "priorities": [p.value for p in ActionPriority]
    }


@router.get("/capacity")
async def get_current_capacity():
    """
    Get the current emotional capacity assessment.
    """
    emotional_state = emotion_engine.get_state()
    capacity = action_router.assess_emotional_capacity(emotional_state)
    mode = action_router.get_dashboard_mode(emotional_state)
    
    capacity_descriptions = {
        "minimal": "You're handling a lot right now. Let's keep it simple - just one thing at a time.",
        "limited": "You have some capacity. Let's focus on 2-3 manageable tasks.",
        "moderate": "You're in a good place to tackle a normal workload.",
        "high": "You have strong capacity right now. Great time for challenging tasks.",
        "peak": "You're at peak capacity! This is the time for your most important work."
    }
    
    return {
        "capacity": capacity.value,
        "description": capacity_descriptions.get(capacity.value, ""),
        "mode": mode,
        "emotional_state": emotional_state,
        "recommendations": {
            "minimal": "Focus on self-care and only critical items",
            "limited": "Prioritize urgent items, skip non-essentials",
            "moderate": "Work through your planned tasks",
            "high": "Great time for complex tasks or learning",
            "peak": "Tackle challenging work and make big progress"
        }.get(capacity.value, "")
    }


@router.get("/self-care")
async def get_self_care_suggestions():
    """
    Get self-care action suggestions.
    """
    return {
        "self_care_actions": [a.to_dict() for a in action_router.self_care_actions],
        "message": "Self-care isn't optional - it's fuel for your fight."
    }


@router.get("/encouragement")
async def get_encouragement():
    """
    Get an encouragement message based on current emotional state.
    """
    import random
    
    emotional_state = emotion_engine.get_state()
    mode = action_router.get_dashboard_mode(emotional_state)
    
    messages = action_router.encouragements.get(mode, action_router.encouragements["guided"])
    message = random.choice(messages)
    
    return {
        "mode": mode,
        "message": message
    }


@router.get("/next")
async def get_next_action():
    """
    Get just the single most important next action.
    Simplified endpoint for crisis mode or quick access.
    """
    emotional_state = emotion_engine.get_state()
    
    # Simple case context - will be improved with actual case data
    case_context = {
        "has_court_date": False,
        "has_lease": False,
        "has_payment_records": False,
        "maintenance_issues": False,
        "has_notice": False
    }
    
    plan = action_router.generate_action_plan(
        emotional_state=emotional_state,
        case_context=case_context
    )
    
    if plan.primary_action:
        return {
            "action": plan.primary_action.to_dict(),
            "encouragement": plan.encouragement_message,
            "self_care": plan.self_care_reminder.to_dict() if plan.self_care_reminder else None
        }
    else:
        return {
            "action": None,
            "message": "No actions needed right now. Take a moment to rest.",
            "encouragement": "You're doing great. Sometimes the best action is to pause."
        }
