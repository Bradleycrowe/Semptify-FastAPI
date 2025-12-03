"""
Court Learning Engine - Bidirectional Information Flow

Semptify learns from court outcomes to improve future defense strategies.

INBOUND (From Court → Semptify):
- Case outcomes (won, lost, settled, dismissed)
- Which defenses worked vs. didn't
- Judge patterns and tendencies
- Successful motion types
- Timeline patterns (how long cases take)
- Common landlord attorney tactics

OUTBOUND (Semptify → Court):
- Pre-filled forms with validated data
- Properly formatted evidence packets
- Compliant filing packages

LEARNING LOOP:
1. Track case outcomes
2. Correlate with defenses used
3. Weight defense suggestions based on success rates
4. Surface patterns (e.g., "Habitability defense wins 73% in Dakota County")
5. Recommend optimal strategies based on case characteristics
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from uuid import uuid4

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session


# =============================================================================
# Enums
# =============================================================================

class CaseOutcome(Enum):
    """Possible case outcomes."""
    PENDING = "pending"
    WON = "won"  # Tenant prevailed
    LOST = "lost"  # Landlord prevailed
    SETTLED = "settled"  # Negotiated settlement
    DISMISSED = "dismissed"  # Case dismissed
    CONTINUED = "continued"  # Case continued/postponed
    DEFAULT = "default"  # Default judgment (tenant didn't appear)
    UNKNOWN = "unknown"


class DefenseEffectiveness(Enum):
    """How effective a defense was."""
    HIGHLY_EFFECTIVE = "highly_effective"  # Primary reason for win
    EFFECTIVE = "effective"  # Contributed to favorable outcome
    NEUTRAL = "neutral"  # Neither helped nor hurt
    INEFFECTIVE = "ineffective"  # Didn't help
    COUNTERPRODUCTIVE = "counterproductive"  # Made things worse
    NOT_USED = "not_used"


class MotionOutcome(Enum):
    """Outcome of filed motions."""
    GRANTED = "granted"
    DENIED = "denied"
    PARTIALLY_GRANTED = "partially_granted"
    MOOT = "moot"  # Case resolved before ruling
    PENDING = "pending"


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class CaseOutcomeRecord:
    """Record of a completed case for learning."""
    id: str = field(default_factory=lambda: str(uuid4()))
    user_id: str = ""
    case_number: str = ""
    
    # Case characteristics
    county: str = "Dakota"
    notice_type: str = ""  # 14-day, lease violation, etc.
    amount_claimed_cents: int = 0
    landlord_type: str = ""  # individual, property_management, corporate
    landlord_attorney: Optional[str] = None
    judge_name: Optional[str] = None
    
    # Outcome
    outcome: CaseOutcome = CaseOutcome.PENDING
    outcome_date: Optional[datetime] = None
    outcome_notes: str = ""
    
    # Settlement details (if settled)
    settlement_amount_cents: Optional[int] = None
    settlement_terms: str = ""
    move_out_date: Optional[datetime] = None
    record_expunged: bool = False
    
    # Defenses used
    defenses_used: list[str] = field(default_factory=list)
    primary_defense: Optional[str] = None
    
    # Motions filed
    motions_filed: list[str] = field(default_factory=list)
    
    # Timeline
    served_date: Optional[datetime] = None
    hearing_date: Optional[datetime] = None
    days_to_resolution: Optional[int] = None
    
    # Learning flags
    tenant_represented: bool = False  # Had attorney?
    used_semptify: bool = True
    
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class DefenseOutcomeRecord:
    """Track effectiveness of specific defenses."""
    id: str = field(default_factory=lambda: str(uuid4()))
    case_outcome_id: str = ""
    defense_code: str = ""
    effectiveness: DefenseEffectiveness = DefenseEffectiveness.NOT_USED
    judge_response: str = ""  # How judge reacted
    notes: str = ""


@dataclass
class MotionOutcomeRecord:
    """Track outcomes of specific motions."""
    id: str = field(default_factory=lambda: str(uuid4()))
    case_outcome_id: str = ""
    motion_type: str = ""
    outcome: MotionOutcome = MotionOutcome.PENDING
    filed_date: Optional[datetime] = None
    decided_date: Optional[datetime] = None
    judge_name: Optional[str] = None
    reasoning: str = ""


@dataclass 
class DefenseSuccessRate:
    """Aggregated success rate for a defense."""
    defense_code: str
    defense_name: str
    total_uses: int
    wins: int
    partial_wins: int  # Settlements, partial grants
    losses: int
    win_rate: float  # (wins + 0.5*partial) / total
    confidence: str  # "high", "medium", "low" based on sample size
    avg_settlement_savings_cents: Optional[int] = None
    notes: str = ""


@dataclass
class JudgePattern:
    """Learned patterns about specific judges."""
    judge_name: str
    total_cases: int
    tenant_win_rate: float
    favored_defenses: list[str]  # Defenses that work well with this judge
    motion_grant_rate: float
    avg_days_to_decision: int
    notes: str = ""


@dataclass
class LandlordPattern:
    """Learned patterns about landlords/property managers."""
    landlord_name: str
    total_cases: int
    settlement_rate: float
    avg_settlement_percent: float  # % of claimed amount
    common_violations: list[str]
    typical_attorney: Optional[str] = None
    notes: str = ""


# =============================================================================
# Court Learning Service
# =============================================================================

class CourtLearningEngine:
    """
    Bidirectional learning engine for court process optimization.
    
    Key capabilities:
    1. Record case outcomes
    2. Track defense effectiveness
    3. Learn judge patterns
    4. Learn landlord patterns
    5. Generate data-driven recommendations
    """
    
    # In-memory storage for now (would be DB in production)
    _case_outcomes: list[CaseOutcomeRecord] = []
    _defense_outcomes: list[DefenseOutcomeRecord] = []
    _motion_outcomes: list[MotionOutcomeRecord] = []
    
    # ==========================================================================
    # Recording Outcomes (FROM Court)
    # ==========================================================================
    
    async def record_case_outcome(
        self,
        user_id: str,
        case_number: str,
        outcome: CaseOutcome,
        defenses_used: list[str],
        primary_defense: Optional[str] = None,
        **kwargs
    ) -> CaseOutcomeRecord:
        """
        Record the outcome of a case for learning.
        
        This is the primary feedback mechanism - when a case concludes,
        the tenant (or system) records what happened.
        """
        record = CaseOutcomeRecord(
            user_id=user_id,
            case_number=case_number,
            outcome=outcome,
            defenses_used=defenses_used,
            primary_defense=primary_defense,
            outcome_date=datetime.now(timezone.utc),
            **kwargs
        )
        
        # Calculate days to resolution if we have dates
        if record.served_date and record.outcome_date:
            delta = record.outcome_date - record.served_date
            record.days_to_resolution = delta.days
        
        self._case_outcomes.append(record)
        return record
    
    async def record_defense_effectiveness(
        self,
        case_outcome_id: str,
        defense_code: str,
        effectiveness: DefenseEffectiveness,
        judge_response: str = "",
        notes: str = ""
    ) -> DefenseOutcomeRecord:
        """Record how effective a specific defense was."""
        record = DefenseOutcomeRecord(
            case_outcome_id=case_outcome_id,
            defense_code=defense_code,
            effectiveness=effectiveness,
            judge_response=judge_response,
            notes=notes,
        )
        self._defense_outcomes.append(record)
        return record
    
    async def record_motion_outcome(
        self,
        case_outcome_id: str,
        motion_type: str,
        outcome: MotionOutcome,
        judge_name: Optional[str] = None,
        reasoning: str = ""
    ) -> MotionOutcomeRecord:
        """Record the outcome of a motion."""
        record = MotionOutcomeRecord(
            case_outcome_id=case_outcome_id,
            motion_type=motion_type,
            outcome=outcome,
            decided_date=datetime.now(timezone.utc),
            judge_name=judge_name,
            reasoning=reasoning,
        )
        self._motion_outcomes.append(record)
        return record
    
    # ==========================================================================
    # Learning & Analysis
    # ==========================================================================
    
    async def get_defense_success_rates(
        self,
        county: str = "Dakota",
        min_cases: int = 5
    ) -> list[DefenseSuccessRate]:
        """
        Calculate success rates for each defense based on recorded outcomes.
        
        Returns defenses ranked by effectiveness.
        """
        # Aggregate by defense
        defense_stats: dict[str, dict] = {}
        
        for case in self._case_outcomes:
            if case.county != county:
                continue
                
            for defense in case.defenses_used:
                if defense not in defense_stats:
                    defense_stats[defense] = {
                        "total": 0,
                        "wins": 0,
                        "partial": 0,
                        "losses": 0,
                        "settlements_sum": 0,
                    }
                
                stats = defense_stats[defense]
                stats["total"] += 1
                
                if case.outcome == CaseOutcome.WON:
                    stats["wins"] += 1
                elif case.outcome == CaseOutcome.DISMISSED:
                    stats["wins"] += 1
                elif case.outcome == CaseOutcome.SETTLED:
                    stats["partial"] += 1
                    if case.settlement_amount_cents and case.amount_claimed_cents:
                        savings = case.amount_claimed_cents - case.settlement_amount_cents
                        stats["settlements_sum"] += savings
                elif case.outcome in [CaseOutcome.LOST, CaseOutcome.DEFAULT]:
                    stats["losses"] += 1
        
        # Build results
        results = []
        for code, stats in defense_stats.items():
            if stats["total"] < min_cases:
                continue
            
            total = stats["total"]
            win_rate = (stats["wins"] + 0.5 * stats["partial"]) / total if total > 0 else 0
            
            confidence = "low"
            if total >= 20:
                confidence = "high"
            elif total >= 10:
                confidence = "medium"
            
            avg_savings = None
            if stats["partial"] > 0:
                avg_savings = stats["settlements_sum"] // stats["partial"]
            
            results.append(DefenseSuccessRate(
                defense_code=code,
                defense_name=self._get_defense_name(code),
                total_uses=total,
                wins=stats["wins"],
                partial_wins=stats["partial"],
                losses=stats["losses"],
                win_rate=round(win_rate, 3),
                confidence=confidence,
                avg_settlement_savings_cents=avg_savings,
            ))
        
        # Sort by win rate
        results.sort(key=lambda x: x.win_rate, reverse=True)
        return results
    
    async def get_judge_patterns(
        self,
        county: str = "Dakota"
    ) -> list[JudgePattern]:
        """
        Analyze patterns by judge.
        
        Helps tenants understand what to expect and prepare accordingly.
        """
        judge_stats: dict[str, dict] = {}
        
        for case in self._case_outcomes:
            if case.county != county or not case.judge_name:
                continue
            
            judge = case.judge_name
            if judge not in judge_stats:
                judge_stats[judge] = {
                    "total": 0,
                    "tenant_wins": 0,
                    "defenses": {},
                    "days_sum": 0,
                }
            
            stats = judge_stats[judge]
            stats["total"] += 1
            
            if case.outcome in [CaseOutcome.WON, CaseOutcome.DISMISSED]:
                stats["tenant_wins"] += 1
            
            if case.days_to_resolution:
                stats["days_sum"] += case.days_to_resolution
            
            # Track which defenses won with this judge
            if case.outcome in [CaseOutcome.WON, CaseOutcome.DISMISSED, CaseOutcome.SETTLED]:
                for defense in case.defenses_used:
                    stats["defenses"][defense] = stats["defenses"].get(defense, 0) + 1
        
        results = []
        for judge, stats in judge_stats.items():
            total = stats["total"]
            if total < 3:
                continue
            
            # Find top defenses
            sorted_defenses = sorted(
                stats["defenses"].items(),
                key=lambda x: x[1],
                reverse=True
            )
            favored = [d[0] for d in sorted_defenses[:3]]
            
            results.append(JudgePattern(
                judge_name=judge,
                total_cases=total,
                tenant_win_rate=round(stats["tenant_wins"] / total, 3) if total > 0 else 0,
                favored_defenses=favored,
                motion_grant_rate=0.5,  # Would calculate from motion outcomes
                avg_days_to_decision=stats["days_sum"] // total if total > 0 else 0,
            ))
        
        return results
    
    async def get_landlord_patterns(
        self,
        landlord_name: Optional[str] = None
    ) -> list[LandlordPattern]:
        """
        Analyze patterns by landlord/property management company.
        
        Helps predict behavior and optimal negotiation strategies.
        """
        landlord_stats: dict[str, dict] = {}
        
        for case in self._case_outcomes:
            if not case.landlord_type:
                continue
            
            # Use landlord name or type as key
            key = case.landlord_attorney or case.landlord_type
            
            if landlord_name and key != landlord_name:
                continue
            
            if key not in landlord_stats:
                landlord_stats[key] = {
                    "total": 0,
                    "settled": 0,
                    "settlement_percents": [],
                    "attorneys": set(),
                }
            
            stats = landlord_stats[key]
            stats["total"] += 1
            
            if case.outcome == CaseOutcome.SETTLED:
                stats["settled"] += 1
                if case.settlement_amount_cents and case.amount_claimed_cents:
                    pct = case.settlement_amount_cents / case.amount_claimed_cents
                    stats["settlement_percents"].append(pct)
            
            if case.landlord_attorney:
                stats["attorneys"].add(case.landlord_attorney)
        
        results = []
        for name, stats in landlord_stats.items():
            total = stats["total"]
            if total < 2:
                continue
            
            avg_pct = 0
            if stats["settlement_percents"]:
                avg_pct = sum(stats["settlement_percents"]) / len(stats["settlement_percents"])
            
            results.append(LandlordPattern(
                landlord_name=name,
                total_cases=total,
                settlement_rate=round(stats["settled"] / total, 3) if total > 0 else 0,
                avg_settlement_percent=round(avg_pct, 3),
                common_violations=[],  # Would populate from case data
                typical_attorney=list(stats["attorneys"])[0] if stats["attorneys"] else None,
            ))
        
        return results
    
    # ==========================================================================
    # Smart Recommendations
    # ==========================================================================
    
    async def get_recommended_strategy(
        self,
        notice_type: str,
        amount_claimed_cents: int,
        available_defenses: list[str],
        judge_name: Optional[str] = None,
        landlord_name: Optional[str] = None,
    ) -> dict:
        """
        Generate data-driven strategy recommendations based on learned patterns.
        
        This is where the bidirectional learning pays off - Semptify uses
        past outcomes to suggest optimal strategies for new cases.
        """
        recommendations = {
            "primary_defense": None,
            "secondary_defenses": [],
            "motions_to_consider": [],
            "settlement_likelihood": 0.0,
            "expected_outcome": "unknown",
            "confidence": "low",
            "notes": [],
        }
        
        # Get defense success rates
        defense_rates = await self.get_defense_success_rates()
        defense_map = {d.defense_code: d for d in defense_rates}
        
        # Filter to available defenses and sort by success rate
        available_with_rates = []
        for defense in available_defenses:
            if defense in defense_map:
                available_with_rates.append((defense, defense_map[defense].win_rate))
            else:
                # No data, assume baseline 40%
                available_with_rates.append((defense, 0.4))
        
        available_with_rates.sort(key=lambda x: x[1], reverse=True)
        
        if available_with_rates:
            recommendations["primary_defense"] = available_with_rates[0][0]
            recommendations["secondary_defenses"] = [d[0] for d in available_with_rates[1:3]]
        
        # Check judge patterns
        if judge_name:
            judge_patterns = await self.get_judge_patterns()
            for jp in judge_patterns:
                if jp.judge_name == judge_name:
                    recommendations["notes"].append(
                        f"Judge {judge_name} has {jp.tenant_win_rate:.0%} tenant-favorable rate"
                    )
                    if jp.favored_defenses:
                        recommendations["notes"].append(
                            f"This judge responds well to: {', '.join(jp.favored_defenses)}"
                        )
                    break
        
        # Check landlord patterns
        if landlord_name:
            landlord_patterns = await self.get_landlord_patterns(landlord_name)
            for lp in landlord_patterns:
                if lp.landlord_name == landlord_name:
                    recommendations["settlement_likelihood"] = lp.settlement_rate
                    if lp.settlement_rate > 0.5:
                        recommendations["notes"].append(
                            f"This landlord settles {lp.settlement_rate:.0%} of cases, "
                            f"typically at {lp.avg_settlement_percent:.0%} of claimed amount"
                        )
                    break
        
        # Suggest motions based on case type
        if notice_type == "14-day" and amount_claimed_cents > 0:
            recommendations["motions_to_consider"].append("motion_to_dismiss")
            recommendations["notes"].append(
                "14-day notices often have technical defects - review notice carefully"
            )
        
        # Calculate confidence based on data availability
        data_points = len(self._case_outcomes)
        if data_points >= 50:
            recommendations["confidence"] = "high"
        elif data_points >= 20:
            recommendations["confidence"] = "medium"
        
        return recommendations
    
    # ==========================================================================
    # Helpers
    # ==========================================================================
    
    def _get_defense_name(self, code: str) -> str:
        """Get human-readable defense name from code."""
        names = {
            "improper_notice": "Improper Notice",
            "habitability": "Habitability/Repair Issues",
            "retaliation": "Retaliatory Eviction",
            "discrimination": "Discrimination",
            "payment": "Payment Made/Offered",
            "procedural": "Procedural Defects",
            "lease_violation_disputed": "Lease Violation Disputed",
            "covid_protections": "Emergency Protections",
            "subsidized_housing": "Subsidized Housing Protections",
        }
        return names.get(code, code.replace("_", " ").title())
    
    async def get_learning_stats(self) -> dict:
        """Get overall learning statistics."""
        return {
            "total_cases_recorded": len(self._case_outcomes),
            "total_defense_outcomes": len(self._defense_outcomes),
            "total_motion_outcomes": len(self._motion_outcomes),
            "counties_covered": list(set(c.county for c in self._case_outcomes)),
            "date_range": {
                "earliest": min((c.created_at for c in self._case_outcomes), default=None),
                "latest": max((c.created_at for c in self._case_outcomes), default=None),
            } if self._case_outcomes else None,
        }


# =============================================================================
# Dependency Injection
# =============================================================================

# Singleton instance
_learning_engine: Optional[CourtLearningEngine] = None


async def get_learning_engine() -> CourtLearningEngine:
    """Get the court learning engine instance."""
    global _learning_engine
    if _learning_engine is None:
        _learning_engine = CourtLearningEngine()
    return _learning_engine
