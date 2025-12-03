"""
Court Learning Router - Bidirectional Information Flow

Endpoints for:
1. Recording case outcomes (FROM court → Semptify)
2. Querying learned patterns (Semptify → better recommendations)
3. Getting data-driven strategy suggestions
"""

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.core.security import require_user, StorageUser
from app.services.eviction.court_learning import (
    CourtLearningEngine,
    CaseOutcome,
    DefenseEffectiveness,
    MotionOutcome,
    get_learning_engine,
)


router = APIRouter()


# =============================================================================
# Request/Response Schemas
# =============================================================================

class RecordOutcomeRequest(BaseModel):
    """Request to record a case outcome."""
    case_number: str = Field(..., description="Court case number")
    outcome: str = Field(..., description="won, lost, settled, dismissed, continued, default")
    
    # Defenses
    defenses_used: list[str] = Field(default=[], description="Defense codes used")
    primary_defense: Optional[str] = Field(None, description="Most effective defense")
    
    # Case details
    notice_type: Optional[str] = Field(None, description="14-day, lease_violation, etc.")
    amount_claimed_cents: Optional[int] = Field(None, description="Amount landlord claimed")
    landlord_type: Optional[str] = Field(None, description="individual, property_management, corporate")
    landlord_attorney: Optional[str] = Field(None, description="Landlord's attorney name")
    judge_name: Optional[str] = Field(None, description="Judge who heard the case")
    
    # Settlement details
    settlement_amount_cents: Optional[int] = Field(None, description="Settlement amount if settled")
    settlement_terms: Optional[str] = Field(None, description="Settlement terms summary")
    move_out_date: Optional[str] = Field(None, description="Move-out date if agreed (ISO format)")
    record_expunged: bool = Field(False, description="Was record expunged?")
    
    # Timeline
    served_date: Optional[str] = Field(None, description="Date served (ISO format)")
    hearing_date: Optional[str] = Field(None, description="Hearing date (ISO format)")
    
    # Meta
    tenant_represented: bool = Field(False, description="Did tenant have attorney?")
    notes: Optional[str] = Field(None, description="Additional notes")


class RecordDefenseEffectivenessRequest(BaseModel):
    """Request to record how effective a defense was."""
    case_outcome_id: str
    defense_code: str
    effectiveness: str = Field(..., description="highly_effective, effective, neutral, ineffective, counterproductive")
    judge_response: Optional[str] = Field(None, description="How the judge responded")
    notes: Optional[str] = None


class RecordMotionOutcomeRequest(BaseModel):
    """Request to record a motion outcome."""
    case_outcome_id: str
    motion_type: str = Field(..., description="dismiss, continuance, stay, fee_waiver, etc.")
    outcome: str = Field(..., description="granted, denied, partially_granted, moot")
    judge_name: Optional[str] = None
    reasoning: Optional[str] = None


class StrategyRequest(BaseModel):
    """Request for strategy recommendations."""
    notice_type: str
    amount_claimed_cents: int = 0
    available_defenses: list[str] = []
    judge_name: Optional[str] = None
    landlord_name: Optional[str] = None


# =============================================================================
# Endpoints - Recording Outcomes (FROM Court)
# =============================================================================

@router.post("/outcome/record")
async def record_case_outcome(
    request: RecordOutcomeRequest,
    user: StorageUser = Depends(require_user),
    engine: CourtLearningEngine = Depends(get_learning_engine),
):
    """
    Record a case outcome for learning.
    
    This is how Semptify learns from the court - after a case concludes,
    the tenant records what happened so future tenants benefit.
    """
    try:
        outcome_enum = CaseOutcome(request.outcome)
    except ValueError:
        raise HTTPException(400, f"Invalid outcome: {request.outcome}")
    
    # Parse dates
    served_date = None
    hearing_date = None
    move_out_date = None
    
    if request.served_date:
        served_date = datetime.fromisoformat(request.served_date.replace("Z", "+00:00"))
    if request.hearing_date:
        hearing_date = datetime.fromisoformat(request.hearing_date.replace("Z", "+00:00"))
    if request.move_out_date:
        move_out_date = datetime.fromisoformat(request.move_out_date.replace("Z", "+00:00"))
    
    record = await engine.record_case_outcome(
        user_id=user.user_id,
        case_number=request.case_number,
        outcome=outcome_enum,
        defenses_used=request.defenses_used,
        primary_defense=request.primary_defense,
        notice_type=request.notice_type or "",
        amount_claimed_cents=request.amount_claimed_cents or 0,
        landlord_type=request.landlord_type or "",
        landlord_attorney=request.landlord_attorney,
        judge_name=request.judge_name,
        settlement_amount_cents=request.settlement_amount_cents,
        settlement_terms=request.settlement_terms or "",
        move_out_date=move_out_date,
        record_expunged=request.record_expunged,
        served_date=served_date,
        hearing_date=hearing_date,
        tenant_represented=request.tenant_represented,
        outcome_notes=request.notes or "",
    )
    
    return {
        "success": True,
        "case_outcome_id": record.id,
        "message": "Thank you! Your case outcome helps future tenants.",
        "days_to_resolution": record.days_to_resolution,
    }


@router.post("/outcome/defense")
async def record_defense_effectiveness(
    request: RecordDefenseEffectivenessRequest,
    user: StorageUser = Depends(require_user),
    engine: CourtLearningEngine = Depends(get_learning_engine),
):
    """
    Record how effective a specific defense was.
    
    Call this after recording the case outcome to provide detailed
    feedback on each defense used.
    """
    try:
        effectiveness = DefenseEffectiveness(request.effectiveness)
    except ValueError:
        raise HTTPException(400, f"Invalid effectiveness: {request.effectiveness}")
    
    record = await engine.record_defense_effectiveness(
        case_outcome_id=request.case_outcome_id,
        defense_code=request.defense_code,
        effectiveness=effectiveness,
        judge_response=request.judge_response or "",
        notes=request.notes or "",
    )
    
    return {
        "success": True,
        "defense_outcome_id": record.id,
    }


@router.post("/outcome/motion")
async def record_motion_outcome(
    request: RecordMotionOutcomeRequest,
    user: StorageUser = Depends(require_user),
    engine: CourtLearningEngine = Depends(get_learning_engine),
):
    """
    Record the outcome of a motion.
    
    Helps Semptify learn which motions work in which situations.
    """
    try:
        outcome = MotionOutcome(request.outcome)
    except ValueError:
        raise HTTPException(400, f"Invalid outcome: {request.outcome}")
    
    record = await engine.record_motion_outcome(
        case_outcome_id=request.case_outcome_id,
        motion_type=request.motion_type,
        outcome=outcome,
        judge_name=request.judge_name,
        reasoning=request.reasoning or "",
    )
    
    return {
        "success": True,
        "motion_outcome_id": record.id,
    }


# =============================================================================
# Endpoints - Querying Learned Patterns
# =============================================================================

@router.get("/learn/defense-rates")
async def get_defense_success_rates(
    county: str = "Dakota",
    min_cases: int = 3,
    engine: CourtLearningEngine = Depends(get_learning_engine),
):
    """
    Get success rates for each defense based on recorded outcomes.
    
    No authentication required - this is public aggregate data.
    """
    rates = await engine.get_defense_success_rates(county, min_cases)
    
    return {
        "county": county,
        "defense_rates": [
            {
                "code": r.defense_code,
                "name": r.defense_name,
                "total_uses": r.total_uses,
                "wins": r.wins,
                "partial_wins": r.partial_wins,
                "losses": r.losses,
                "win_rate": r.win_rate,
                "win_rate_percent": f"{r.win_rate * 100:.1f}%",
                "confidence": r.confidence,
                "avg_settlement_savings": f"${r.avg_settlement_savings_cents / 100:.2f}" if r.avg_settlement_savings_cents else None,
            }
            for r in rates
        ],
    }


@router.get("/learn/judge-patterns")
async def get_judge_patterns(
    county: str = "Dakota",
    engine: CourtLearningEngine = Depends(get_learning_engine),
):
    """
    Get learned patterns about judges.
    
    Helps tenants understand what to expect from their assigned judge.
    """
    patterns = await engine.get_judge_patterns(county)
    
    return {
        "county": county,
        "judges": [
            {
                "name": p.judge_name,
                "total_cases": p.total_cases,
                "tenant_win_rate": p.tenant_win_rate,
                "tenant_win_rate_percent": f"{p.tenant_win_rate * 100:.1f}%",
                "favored_defenses": p.favored_defenses,
                "motion_grant_rate": p.motion_grant_rate,
                "avg_days_to_decision": p.avg_days_to_decision,
            }
            for p in patterns
        ],
    }


@router.get("/learn/landlord-patterns")
async def get_landlord_patterns(
    landlord_name: Optional[str] = None,
    engine: CourtLearningEngine = Depends(get_learning_engine),
):
    """
    Get learned patterns about landlords/property managers.
    
    Helps predict landlord behavior and optimal negotiation approach.
    """
    patterns = await engine.get_landlord_patterns(landlord_name)
    
    return {
        "landlords": [
            {
                "name": p.landlord_name,
                "total_cases": p.total_cases,
                "settlement_rate": p.settlement_rate,
                "settlement_rate_percent": f"{p.settlement_rate * 100:.1f}%",
                "avg_settlement_percent": f"{p.avg_settlement_percent * 100:.1f}%",
                "typical_attorney": p.typical_attorney,
            }
            for p in patterns
        ],
    }


@router.get("/learn/stats")
async def get_learning_stats(
    engine: CourtLearningEngine = Depends(get_learning_engine),
):
    """
    Get overall learning statistics.
    
    Shows how much data Semptify has learned from.
    """
    stats = await engine.get_learning_stats()
    
    return {
        "total_cases": stats["total_cases_recorded"],
        "total_defense_outcomes": stats["total_defense_outcomes"],
        "total_motion_outcomes": stats["total_motion_outcomes"],
        "counties": stats["counties_covered"],
        "learning_since": stats["date_range"]["earliest"].isoformat() if stats["date_range"] and stats["date_range"]["earliest"] else None,
    }


# =============================================================================
# Endpoints - Strategy Recommendations
# =============================================================================

@router.post("/strategy/recommend")
async def get_strategy_recommendation(
    request: StrategyRequest,
    engine: CourtLearningEngine = Depends(get_learning_engine),
):
    """
    Get data-driven strategy recommendations.
    
    This is the payoff of bidirectional learning - Semptify uses all
    recorded outcomes to suggest the optimal strategy for a new case.
    """
    recommendation = await engine.get_recommended_strategy(
        notice_type=request.notice_type,
        amount_claimed_cents=request.amount_claimed_cents,
        available_defenses=request.available_defenses,
        judge_name=request.judge_name,
        landlord_name=request.landlord_name,
    )
    
    return {
        "recommendation": recommendation,
        "disclaimer": (
            "These recommendations are based on aggregate data from past cases. "
            "Every case is unique. Consider consulting with a legal aid attorney."
        ),
    }


@router.get("/strategy/for-case")
async def get_strategy_for_current_case(
    user: StorageUser = Depends(require_user),
    engine: CourtLearningEngine = Depends(get_learning_engine),
):
    """
    Get strategy recommendation for the user's current case.
    
    Pulls case details from user's data and generates recommendations.
    """
    # This would integrate with the case builder to get current case details
    # For now, return a placeholder
    return {
        "message": "Strategy generation requires case details. Use /strategy/recommend with your case info.",
        "endpoints": {
            "manual": "POST /eviction/learn/strategy/recommend",
            "auto": "Coming soon - will auto-pull from your case data",
        },
    }
