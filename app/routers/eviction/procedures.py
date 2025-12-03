"""
Court Procedures, Rules, Motions & Objections API Router.

Provides endpoints for:
- Minnesota eviction rules and statutes
- Motion templates and generation
- Objection responses
- Procedure step-by-step guide
- Counterclaim types
- Defense strategies
- Hearing preparation
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Optional

from app.services.eviction.court_procedures import (
    get_procedures_engine,
    MotionType,
    ObjectionType,
    ProcedurePhase,
    DefenseCategory,
)


router = APIRouter(prefix="/dakota/procedures", tags=["Dakota Procedures"])


# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class RuleResponse(BaseModel):
    """A Minnesota eviction rule."""
    rule_id: str
    title: str
    statute: str
    summary: str
    deadline_days: Optional[int] = None
    applies_to: list[str] = []
    tenant_action: Optional[str] = None
    landlord_obligation: Optional[str] = None
    consequence_if_violated: Optional[str] = None


class MotionTemplateResponse(BaseModel):
    """A motion template."""
    motion_type: str
    title: str
    legal_basis: list[str]
    required_facts: list[str]
    template_text: str
    supporting_evidence: list[str]
    success_factors: list[str]
    common_responses: list[str]


class ObjectionResponseModel(BaseModel):
    """How to respond to an objection."""
    objection_type: str
    definition: str
    when_valid: str
    how_to_overcome: list[str]
    example_response: str
    supporting_rule: str


class ProcedureStepResponse(BaseModel):
    """A step in the eviction procedure."""
    phase: str
    step_number: int
    title: str
    description: str
    deadline: Optional[str] = None
    tenant_tasks: list[str] = []
    documents_needed: list[str] = []
    tips: list[str] = []


class CounterclaimResponse(BaseModel):
    """A counterclaim type."""
    code: str
    title: str
    legal_basis: str
    elements_to_prove: list[str]
    damages_available: list[str]
    evidence_needed: list[str]
    statute_of_limitations: str


class DefenseStrategyResponse(BaseModel):
    """Defense strategies for a category."""
    name: str
    description: str
    defenses: list[dict]


class GenerateMotionRequest(BaseModel):
    """Request to generate a motion."""
    motion_type: MotionType
    tenant_name: str = Field(..., description="Tenant's full legal name")
    case_number: str = Field(..., description="Court case number")
    landlord_name: Optional[str] = None
    tenant_address: Optional[str] = None
    tenant_phone: Optional[str] = None
    specific_facts: Optional[str] = Field(
        None,
        description="Specific facts to include in the motion"
    )


class HearingChecklistResponse(BaseModel):
    """Hearing preparation checklist."""
    before_hearing: list[str]
    bring_to_court: list[str]
    during_hearing: list[str]
    what_to_say: list[str]
    after_hearing: list[str]


# =============================================================================
# RULES ENDPOINTS
# =============================================================================

@router.get("/rules", response_model=list[RuleResponse])
async def get_all_rules():
    """
    Get all Minnesota eviction rules and statutes.
    
    Returns comprehensive list of rules including:
    - Notice requirements
    - Service requirements
    - Answer deadlines
    - Execution procedures
    - Tenant protections
    """
    engine = get_procedures_engine()
    rules = engine.get_all_rules()
    return [
        RuleResponse(
            rule_id=r.rule_id,
            title=r.title,
            statute=r.statute,
            summary=r.summary,
            deadline_days=r.deadline_days,
            applies_to=[p.value for p in r.applies_to],
            tenant_action=r.tenant_action,
            landlord_obligation=r.landlord_obligation,
            consequence_if_violated=r.consequence_if_violated
        )
        for r in rules
    ]


@router.get("/rules/{rule_id}", response_model=RuleResponse)
async def get_rule(rule_id: str):
    """Get a specific rule by ID."""
    engine = get_procedures_engine()
    rule = engine.get_rule(rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail=f"Rule '{rule_id}' not found")
    return RuleResponse(
        rule_id=rule.rule_id,
        title=rule.title,
        statute=rule.statute,
        summary=rule.summary,
        deadline_days=rule.deadline_days,
        applies_to=[p.value for p in rule.applies_to],
        tenant_action=rule.tenant_action,
        landlord_obligation=rule.landlord_obligation,
        consequence_if_violated=rule.consequence_if_violated
    )


@router.get("/rules/phase/{phase}", response_model=list[RuleResponse])
async def get_rules_by_phase(phase: ProcedurePhase):
    """Get rules applicable to a specific procedure phase."""
    engine = get_procedures_engine()
    rules = engine.get_rules_by_phase(phase)
    return [
        RuleResponse(
            rule_id=r.rule_id,
            title=r.title,
            statute=r.statute,
            summary=r.summary,
            deadline_days=r.deadline_days,
            applies_to=[p.value for p in r.applies_to],
            tenant_action=r.tenant_action,
            landlord_obligation=r.landlord_obligation,
            consequence_if_violated=r.consequence_if_violated
        )
        for r in rules
    ]


# =============================================================================
# MOTIONS ENDPOINTS
# =============================================================================

@router.get("/motions", response_model=list[MotionTemplateResponse])
async def get_all_motions():
    """
    Get all available motion templates.
    
    Includes templates for:
    - Motion to Dismiss (various grounds)
    - Motion for Continuance
    - Motion for Stay of Execution
    - Motion for Expungement
    """
    engine = get_procedures_engine()
    motions = engine.get_all_motions()
    return [
        MotionTemplateResponse(
            motion_type=m.motion_type.value,
            title=m.title,
            legal_basis=m.legal_basis,
            required_facts=m.required_facts,
            template_text=m.template_text,
            supporting_evidence=m.supporting_evidence,
            success_factors=m.success_factors,
            common_responses=m.common_responses
        )
        for m in motions
    ]


@router.get("/motions/{motion_type}", response_model=MotionTemplateResponse)
async def get_motion_template(motion_type: MotionType):
    """Get a specific motion template."""
    engine = get_procedures_engine()
    motion = engine.get_motion_template(motion_type)
    if not motion:
        raise HTTPException(status_code=404, detail=f"Motion type '{motion_type}' not found")
    return MotionTemplateResponse(
        motion_type=motion.motion_type.value,
        title=motion.title,
        legal_basis=motion.legal_basis,
        required_facts=motion.required_facts,
        template_text=motion.template_text,
        supporting_evidence=motion.supporting_evidence,
        success_factors=motion.success_factors,
        common_responses=motion.common_responses
    )


@router.post("/motions/generate")
async def generate_motion(request: GenerateMotionRequest):
    """
    Generate a complete motion document with tenant's specific information.
    
    Returns formatted motion ready for filing.
    """
    engine = get_procedures_engine()
    
    facts = {
        "landlord_name": request.landlord_name,
        "tenant_address": request.tenant_address,
        "tenant_phone": request.tenant_phone,
        "specific_facts": request.specific_facts
    }
    
    motion_text = engine.generate_motion(
        motion_type=request.motion_type,
        tenant_name=request.tenant_name,
        case_number=request.case_number,
        facts=facts
    )
    
    return {
        "motion_type": request.motion_type.value,
        "case_number": request.case_number,
        "tenant_name": request.tenant_name,
        "generated_motion": motion_text,
        "instructions": [
            "Review the motion and fill in any [BRACKETED] sections",
            "Make 3 copies (original for court, copy for you, copy for landlord)",
            "File with the court clerk before your hearing",
            "Serve a copy on the landlord or their attorney",
            "Complete the Certificate of Service"
        ]
    }


# =============================================================================
# OBJECTIONS ENDPOINTS
# =============================================================================

@router.get("/objections", response_model=list[ObjectionResponseModel])
async def get_all_objection_responses():
    """
    Get all objection types and how to respond to them.
    
    Covers common objections:
    - Hearsay
    - Relevance
    - Foundation
    - Leading questions
    - And more
    """
    engine = get_procedures_engine()
    objections = engine.get_all_objection_responses()
    return [
        ObjectionResponseModel(
            objection_type=o.objection_type.value,
            definition=o.definition,
            when_valid=o.when_valid,
            how_to_overcome=o.how_to_overcome,
            example_response=o.example_response,
            supporting_rule=o.supporting_rule
        )
        for o in objections
    ]


@router.get("/objections/{objection_type}", response_model=ObjectionResponseModel)
async def get_objection_response(objection_type: ObjectionType):
    """Get how to respond to a specific objection type."""
    engine = get_procedures_engine()
    objection = engine.get_objection_response(objection_type)
    if not objection:
        raise HTTPException(status_code=404, detail=f"Objection type '{objection_type}' not found")
    return ObjectionResponseModel(
        objection_type=objection.objection_type.value,
        definition=objection.definition,
        when_valid=objection.when_valid,
        how_to_overcome=objection.how_to_overcome,
        example_response=objection.example_response,
        supporting_rule=objection.supporting_rule
    )


# =============================================================================
# PROCEDURES ENDPOINTS
# =============================================================================

@router.get("/steps", response_model=list[ProcedureStepResponse])
async def get_procedure_steps(phase: Optional[ProcedurePhase] = None):
    """
    Get step-by-step eviction procedure guide.
    
    Optionally filter by phase:
    - pre_filing
    - summons_service
    - answer_period
    - hearing
    - post_hearing
    """
    engine = get_procedures_engine()
    steps = engine.get_procedure_steps(phase)
    return [
        ProcedureStepResponse(
            phase=s.phase.value,
            step_number=s.step_number,
            title=s.title,
            description=s.description,
            deadline=s.deadline,
            tenant_tasks=s.tenant_tasks,
            documents_needed=s.documents_needed,
            tips=s.tips
        )
        for s in steps
    ]


# =============================================================================
# COUNTERCLAIMS ENDPOINTS
# =============================================================================

@router.get("/counterclaims", response_model=list[CounterclaimResponse])
async def get_counterclaim_types():
    """
    Get all available counterclaim types.
    
    Includes:
    - Breach of Habitability
    - Retaliation
    - Security Deposit Violations
    - Illegal Lockout
    - Housing Code Violations
    """
    engine = get_procedures_engine()
    counterclaims = engine.get_counterclaim_types()
    return [
        CounterclaimResponse(
            code=c.code,
            title=c.title,
            legal_basis=c.legal_basis,
            elements_to_prove=c.elements_to_prove,
            damages_available=c.damages_available,
            evidence_needed=c.evidence_needed,
            statute_of_limitations=c.statute_of_limitations
        )
        for c in counterclaims
    ]


@router.get("/counterclaims/{code}", response_model=CounterclaimResponse)
async def get_counterclaim(code: str):
    """Get a specific counterclaim type by code."""
    engine = get_procedures_engine()
    counterclaim = engine.get_counterclaim(code)
    if not counterclaim:
        raise HTTPException(status_code=404, detail=f"Counterclaim '{code}' not found")
    return CounterclaimResponse(
        code=counterclaim.code,
        title=counterclaim.title,
        legal_basis=counterclaim.legal_basis,
        elements_to_prove=counterclaim.elements_to_prove,
        damages_available=counterclaim.damages_available,
        evidence_needed=counterclaim.evidence_needed,
        statute_of_limitations=counterclaim.statute_of_limitations
    )


# =============================================================================
# DEFENSES ENDPOINTS
# =============================================================================

@router.get("/defenses")
async def get_all_defenses():
    """
    Get all defense strategies organized by category.
    
    Categories:
    - Procedural defenses
    - Habitability defenses
    - Retaliation defenses
    - Payment defenses
    """
    engine = get_procedures_engine()
    return engine.get_defense_strategies()


@router.get("/defenses/{category}", response_model=DefenseStrategyResponse)
async def get_defense_by_category(category: DefenseCategory):
    """Get defense strategies for a specific category."""
    engine = get_procedures_engine()
    defense = engine.get_defense_strategies(category)
    if not defense:
        raise HTTPException(status_code=404, detail=f"Category '{category}' not found")
    return DefenseStrategyResponse(
        name=defense["name"],
        description=defense["description"],
        defenses=defense["defenses"]
    )


# =============================================================================
# HEARING PREPARATION
# =============================================================================

@router.get("/hearing-checklist", response_model=HearingChecklistResponse)
async def get_hearing_checklist():
    """
    Get comprehensive hearing preparation checklist.
    
    Covers:
    - What to do before the hearing
    - What to bring to court
    - How to behave during the hearing
    - What to say
    - What to do after the hearing
    """
    engine = get_procedures_engine()
    return engine.get_hearing_checklist()


# =============================================================================
# QUICK REFERENCE
# =============================================================================

@router.get("/quick-reference")
async def get_quick_reference():
    """
    Get quick reference guide for eviction defense.
    
    Essential information at a glance.
    """
    return {
        "critical_deadlines": {
            "notice_period_nonpayment": "14 days",
            "service_before_hearing": "7 days minimum",
            "stay_request_after_judgment": "24 hours (request 7-day stay)",
            "appeal_deadline": "15 days from judgment",
            "retaliation_presumption": "90 days"
        },
        "common_dismissal_grounds": [
            "Improper or insufficient notice",
            "Improper service of summons",
            "Less than 7 days between service and hearing",
            "Landlord lacks standing (not the owner)",
            "Wrong venue (wrong county)"
        ],
        "key_statutes": {
            "notice_requirements": "Minn. Stat. § 504B.135",
            "service_requirements": "Minn. Stat. § 504B.331",
            "habitability": "Minn. Stat. § 504B.161",
            "retaliation": "Minn. Stat. § 504B.441",
            "security_deposit": "Minn. Stat. § 504B.178",
            "lockout_prohibition": "Minn. Stat. § 504B.375",
            "expungement": "Minn. Stat. § 484.014"
        },
        "emergency_contacts": {
            "legal_aid": "Legal Aid Society of Minneapolis: 612-334-5970",
            "housing_court_help": "Dakota County Self-Help Center",
            "tenant_hotline": "HOME Line: 612-728-5767"
        },
        "court_info": {
            "court": "Dakota County District Court",
            "address": "1560 Highway 55, Hastings, MN 55033",
            "efiling": "https://minnesota.tylertech.cloud/ofsweb"
        }
    }


# =============================================================================
# ENUM VALUES (for frontend)
# =============================================================================

@router.get("/enums/motion-types")
async def get_motion_types():
    """Get all available motion types."""
    return [{"value": m.value, "name": m.name} for m in MotionType]


@router.get("/enums/objection-types")
async def get_objection_types():
    """Get all available objection types."""
    return [{"value": o.value, "name": o.name} for o in ObjectionType]


@router.get("/enums/procedure-phases")
async def get_procedure_phases():
    """Get all procedure phases."""
    return [{"value": p.value, "name": p.name} for p in ProcedurePhase]


@router.get("/enums/defense-categories")
async def get_defense_categories():
    """Get all defense categories."""
    return [{"value": d.value, "name": d.name} for d in DefenseCategory]
