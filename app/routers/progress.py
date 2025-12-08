"""
Progress Tracker API
====================

API endpoints for tracking user progress through
their legal defense journey.
"""

from fastapi import APIRouter, Query
from typing import Dict, Any, Optional, List
from pydantic import BaseModel

from ..services.progress_tracker import progress_tracker, MilestoneCategory
from ..services.emotion_engine import emotion_engine


router = APIRouter(prefix="/progress", tags=["Progress Tracker"])


class MilestoneCompletion(BaseModel):
    """Request to complete a milestone"""
    milestone_id: str
    notes: Optional[str] = None
    evidence_ids: Optional[List[str]] = None


class CaseSetup(BaseModel):
    """Initial case setup data"""
    case_type: Optional[str] = None
    court_date: Optional[str] = None


@router.get("/")
async def get_progress(user_id: str = Query("default")):
    """
    Get full progress state for a user.
    """
    progress = progress_tracker.get_progress(user_id)
    return progress.to_dict()


@router.get("/readiness")
async def get_case_readiness(user_id: str = Query("default")):
    """
    Get overall case readiness assessment.
    """
    return progress_tracker.get_case_readiness(user_id)


@router.get("/milestones")
async def get_all_milestones(user_id: str = Query("default")):
    """
    Get all milestones with their status for a user.
    """
    return progress_tracker.get_all_milestones(user_id)


@router.get("/milestones/next")
async def get_next_milestones(
    user_id: str = Query("default"),
    limit: int = Query(3, ge=1, le=10)
):
    """
    Get recommended next milestones to complete.
    """
    next_milestones = progress_tracker.get_next_milestones(user_id, limit)
    return {
        "milestones": next_milestones,
        "message": "Focus on these next to build your case."
    }


@router.post("/milestones/complete")
async def complete_milestone(completion: MilestoneCompletion, user_id: str = Query("default")):
    """
    Mark a milestone as completed.
    """
    result = progress_tracker.complete_milestone(
        milestone_id=completion.milestone_id,
        user_id=user_id,
        notes=completion.notes,
        evidence_ids=completion.evidence_ids
    )
    
    # Trigger emotion engine if successful
    if result.get("success") and not result.get("already_completed"):
        emotion_engine.process_trigger("task_completed", {
            "milestone": completion.milestone_id,
            "points": result.get("points_earned", 0)
        })
        emotion_engine.process_trigger("progress_made")
    
    return result


@router.post("/milestones/skip/{milestone_id}")
async def skip_milestone(milestone_id: str, user_id: str = Query("default")):
    """
    Skip a milestone (mark as not applicable).
    """
    progress = progress_tracker.get_progress(user_id)
    
    if milestone_id not in progress_tracker.milestones:
        return {"success": False, "error": "Milestone not found"}
    
    progress.skipped_milestones.add(milestone_id)
    progress_tracker.save_progress(user_id)
    
    return {
        "success": True,
        "message": "Milestone marked as skipped"
    }


@router.get("/points")
async def get_points(user_id: str = Query("default")):
    """
    Get total points earned.
    """
    total = progress_tracker.get_total_points(user_id)
    progress = progress_tracker.get_progress(user_id)
    
    return {
        "total_points": total,
        "tasks_completed": progress.tasks_completed,
        "streak_days": progress.streak_days
    }


@router.get("/stats")
async def get_stats(user_id: str = Query("default")):
    """
    Get progress statistics.
    """
    progress = progress_tracker.get_progress(user_id)
    readiness = progress_tracker.get_case_readiness(user_id)
    
    return {
        "documents_uploaded": progress.documents_uploaded,
        "violations_found": progress.violations_found,
        "forms_generated": progress.forms_generated,
        "tasks_completed": progress.tasks_completed,
        "streak_days": progress.streak_days,
        "total_points": readiness["total_points"],
        "case_readiness": readiness["percent"],
        "readiness_level": readiness["level"],
        "journey_days": (
            (progress.last_active - progress.journey_started).days + 1
            if progress.journey_started and progress.last_active else 0
        )
    }


@router.post("/stat/{stat}")
async def increment_stat(
    stat: str,
    amount: int = Query(1),
    user_id: str = Query("default")
):
    """
    Increment a progress stat (documents_uploaded, violations_found, forms_generated).
    """
    valid_stats = ["documents_uploaded", "violations_found", "forms_generated"]
    if stat not in valid_stats:
        return {
            "success": False,
            "error": f"Invalid stat. Must be one of: {valid_stats}"
        }
    
    success = progress_tracker.increment_stat(stat, user_id, amount)
    return {"success": success}


@router.post("/setup")
async def setup_case(setup: CaseSetup, user_id: str = Query("default")):
    """
    Initialize or update case setup information.
    """
    from datetime import datetime
    
    progress = progress_tracker.get_progress(user_id)
    
    if setup.case_type:
        progress.case_type = setup.case_type
    
    if setup.court_date:
        try:
            progress.court_date = datetime.fromisoformat(setup.court_date)
        except:
            return {"success": False, "error": "Invalid date format"}
    
    progress_tracker.save_progress(user_id)
    
    return {
        "success": True,
        "progress": progress.to_dict()
    }


@router.get("/journey")
async def get_journey_overview(user_id: str = Query("default")):
    """
    Get a high-level journey overview for display.
    """
    progress = progress_tracker.get_progress(user_id)
    readiness = progress_tracker.get_case_readiness(user_id)
    next_milestones = progress_tracker.get_next_milestones(user_id, 3)
    
    # Calculate days
    journey_days = 0
    days_to_court = None
    if progress.journey_started:
        journey_days = (progress.last_active - progress.journey_started).days + 1 if progress.last_active else 1
    if progress.court_date:
        from datetime import datetime
        days_to_court = (progress.court_date - datetime.now()).days
    
    return {
        "case_type": progress.case_type,
        "journey_days": journey_days,
        "days_to_court": days_to_court,
        "court_date": progress.court_date.strftime("%b %d, %Y") if progress.court_date else None,
        "readiness": {
            "percent": readiness["percent"],
            "level": readiness["level"],
            "message": readiness["message"]
        },
        "stats": {
            "documents": progress.documents_uploaded,
            "violations": progress.violations_found,
            "streak": progress.streak_days,
            "points": readiness["total_points"]
        },
        "next_steps": next_milestones,
        "category_progress": readiness["category_progress"]
    }


@router.get("/achievements")
async def get_achievements(user_id: str = Query("default")):
    """
    Get earned achievements/completed milestones.
    """
    progress = progress_tracker.get_progress(user_id)
    
    achievements = []
    for milestone_id, completed in progress.completed_milestones.items():
        if milestone_id in progress_tracker.milestones:
            milestone = progress_tracker.milestones[milestone_id]
            achievements.append({
                "id": milestone_id,
                "name": milestone.name,
                "description": milestone.description,
                "category": milestone.category.value,
                "points": milestone.points,
                "completed_at": completed.completed_at.isoformat()
            })
    
    # Sort by completion time
    achievements.sort(key=lambda a: a["completed_at"], reverse=True)
    
    return {
        "achievements": achievements,
        "total_count": len(achievements),
        "total_points": progress_tracker.get_total_points(user_id)
    }
