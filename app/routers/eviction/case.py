"""
Eviction Case Router - Unified Case Management

This router provides the API endpoints that connect Semptify's
data collection to court-ready eviction defense packages.

One-Click Flow:
1. GET /eviction/case/build - Pull all data, analyze, generate forms
2. GET /eviction/case/compliance - Check if ready to file
3. POST /eviction/case/generate-packet - Generate court filing ZIP
"""

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.core.security import require_user, StorageUser
from app.services.eviction.case_builder import (
    EvictionCaseBuilder,
    MNCourtRules,
    get_case_builder,
)


router = APIRouter()


# =============================================================================
# Schemas
# =============================================================================

class CaseOverview(BaseModel):
    """Quick overview of case status."""
    user_id: str
    has_tenant_info: bool
    has_landlord_info: bool
    has_court_date: bool
    evidence_count: int
    timeline_count: int
    applicable_defenses: list[str]
    compliance_status: str
    ready_to_file: bool
    next_action: str


class CaseBuildRequest(BaseModel):
    """Request to build/refresh case."""
    language: str = Field("en", description="Language: en, es, so, ar")
    include_analysis: bool = Field(True, description="Include defense analysis")
    include_compliance: bool = Field(True, description="Include compliance check")


class CaseUpdateRequest(BaseModel):
    """Manual updates to case data."""
    tenant_name: Optional[str] = None
    tenant_address: Optional[str] = None
    tenant_city: Optional[str] = None
    tenant_state: Optional[str] = "MN"
    tenant_zip: Optional[str] = None
    tenant_phone: Optional[str] = None
    landlord_name: Optional[str] = None
    landlord_address: Optional[str] = None
    case_number: Optional[str] = None
    court_date: Optional[str] = None  # ISO format
    notice_type: Optional[str] = None
    amount_claimed: Optional[int] = None  # cents


class DefenseSelection(BaseModel):
    """Select which defenses to include in Answer."""
    selected_defenses: list[str] = Field(..., description="List of defense codes")
    additional_facts: Optional[str] = None
    

class CounterclaimRequest(BaseModel):
    """Add counterclaim to case."""
    title: str
    facts: str
    relief_requested: str
    amount: Optional[int] = None  # cents


class GeneratePacketRequest(BaseModel):
    """Request to generate court filing packet."""
    language: str = "en"
    selected_defenses: list[str] = []
    include_evidence: bool = True
    include_timeline: bool = True
    include_rent_ledger: bool = True
    counterclaims: list[CounterclaimRequest] = []


# =============================================================================
# Endpoints
# =============================================================================

@router.get("/case/overview", response_model=CaseOverview)
async def get_case_overview(
    user: StorageUser = Depends(require_user),
    builder: EvictionCaseBuilder = Depends(get_case_builder),
):
    """
    Get a quick overview of case readiness.
    
    This is the first endpoint to call - it shows what data
    Semptify has and what's still needed.
    """
    case = await builder.build_case(user.user_id)
    
    applicable_defenses = [d.code for d in case.defenses if d.applicable]
    
    # Determine next action
    if not case.tenant or not case.tenant.full_name:
        next_action = "Add your name to your profile"
    elif not case.landlord or not case.landlord.name:
        next_action = "Upload your lease or summons to identify landlord"
    elif not case.notice or not case.notice.court_date:
        next_action = "Add your court date from the summons"
    elif len(case.evidence) == 0:
        next_action = "Upload evidence documents to strengthen your case"
    elif case.compliance and not case.compliance.ready_to_file:
        next_action = "Review compliance issues before filing"
    else:
        next_action = "Ready to generate court filing packet!"
    
    return CaseOverview(
        user_id=user.user_id,
        has_tenant_info=case.tenant is not None and bool(case.tenant.full_name),
        has_landlord_info=case.landlord is not None and bool(case.landlord.name),
        has_court_date=case.notice is not None and case.notice.court_date is not None,
        evidence_count=len(case.evidence),
        timeline_count=len(case.timeline),
        applicable_defenses=applicable_defenses,
        compliance_status=case.compliance.overall_status.value if case.compliance else "unknown",
        ready_to_file=case.compliance.ready_to_file if case.compliance else False,
        next_action=next_action,
    )


@router.post("/case/build")
async def build_case(
    request: CaseBuildRequest,
    user: StorageUser = Depends(require_user),
    builder: EvictionCaseBuilder = Depends(get_case_builder),
):
    """
    Build complete eviction case from all Semptify data.
    
    This pulls from:
    - User profile
    - Document vault
    - Timeline events
    - Calendar
    - Rent ledger
    - AI analysis
    
    Returns a complete case object ready for form generation.
    """
    case = await builder.build_case(user.user_id, request.language)
    return case.to_dict()


@router.get("/case/compliance")
async def check_compliance(
    user: StorageUser = Depends(require_user),
    builder: EvictionCaseBuilder = Depends(get_case_builder),
):
    """
    Check case for Minnesota court compliance.
    
    Returns:
    - List of compliance checks (pass/fail/warning)
    - Blocking issues that must be fixed
    - Whether case is ready to file
    """
    case = await builder.build_case(user.user_id)
    
    if not case.compliance:
        raise HTTPException(
            status_code=500,
            detail="Compliance check failed",
        )
    
    return {
        "ready_to_file": case.compliance.ready_to_file,
        "overall_status": case.compliance.overall_status.value,
        "blocking_issues": case.compliance.blocking_issues,
        "warnings": case.compliance.warnings,
        "checks": [
            {
                "rule": c.rule,
                "status": c.status.value,
                "message": c.message,
                "fix_action": c.fix_action,
                "deadline": c.deadline.isoformat() if c.deadline else None,
            }
            for c in case.compliance.checks
        ],
        "court_info": {
            "county": "Dakota",
            "address": MNCourtRules.COURT_ADDRESS,
            "efiling_url": MNCourtRules.EFILING_URL,
            "guide_and_file_url": MNCourtRules.GUIDE_AND_FILE_URL,
        },
    }


@router.get("/case/defenses")
async def get_applicable_defenses(
    user: StorageUser = Depends(require_user),
    builder: EvictionCaseBuilder = Depends(get_case_builder),
):
    """
    Get list of potentially applicable defenses.
    
    Analyzes case data to suggest defenses that may apply.
    Returns strength assessment and required evidence.
    """
    case = await builder.build_case(user.user_id)
    
    return {
        "defenses": [
            {
                "code": d.code,
                "name": d.name,
                "description": d.description,
                "applicable": d.applicable,
                "strength": d.strength,
                "evidence_ids": d.evidence_ids,
                "notes": d.notes,
            }
            for d in case.defenses
        ],
        "recommended": [d.code for d in case.defenses if d.applicable and d.strength in ["strong", "moderate"]],
    }


@router.get("/case/evidence")
async def get_evidence_list(
    user: StorageUser = Depends(require_user),
    builder: EvictionCaseBuilder = Depends(get_case_builder),
):
    """
    Get list of evidence with exhibit labels.
    
    Returns documents organized for court submission.
    """
    case = await builder.build_case(user.user_id)
    
    return {
        "total_exhibits": len(case.evidence),
        "evidence": [
            {
                "document_id": e.document_id,
                "filename": e.filename,
                "document_type": e.document_type,
                "description": e.description,
                "date_created": e.date_created.isoformat() if e.date_created else None,
                "exhibit_label": e.exhibit_label,
                "relevance": e.relevance,
            }
            for e in case.evidence
        ],
    }


@router.get("/case/timeline")
async def get_timeline(
    user: StorageUser = Depends(require_user),
    builder: EvictionCaseBuilder = Depends(get_case_builder),
):
    """
    Get chronological timeline for court narrative.
    
    This is the story of what happened, in order.
    """
    case = await builder.build_case(user.user_id)
    
    return {
        "total_events": len(case.timeline),
        "timeline": [
            {
                "date": t.date.isoformat(),
                "event_type": t.event_type,
                "title": t.title,
                "description": t.description,
                "has_evidence": t.has_evidence,
                "evidence_ids": t.evidence_ids,
            }
            for t in case.timeline
        ],
    }


@router.get("/case/rent-ledger")
async def get_rent_ledger(
    user: StorageUser = Depends(require_user),
    builder: EvictionCaseBuilder = Depends(get_case_builder),
):
    """
    Get rent payment history formatted for court.
    
    Shows payments made vs. what landlord claims is owed.
    """
    case = await builder.build_case(user.user_id)
    
    return {
        "summary": {
            "total_paid_cents": case.total_paid,
            "total_paid_formatted": f"${case.total_paid / 100:.2f}",
            "total_owed_cents": case.total_owed,
            "total_owed_formatted": f"${case.total_owed / 100:.2f}",
            "payments_count": len(case.rent_history),
        },
        "payments": case.rent_history,
    }


@router.get("/case/form-data")
async def get_form_data(
    user: StorageUser = Depends(require_user),
    builder: EvictionCaseBuilder = Depends(get_case_builder),
):
    """
    Get all data needed to fill court forms.
    
    Returns data mapped to form field names for:
    - Answer to Eviction Summons and Complaint
    - Affidavit of Service
    - Motion forms
    """
    case = await builder.build_case(user.user_id)
    
    # Build form data from case
    form_data = {
        "case_number": case.case_number or "",
        "tenant_name": case.tenant.full_name if case.tenant else "",
        "tenant_address": case.tenant.address if case.tenant else "",
        "tenant_city": case.tenant.city if case.tenant else "",
        "tenant_state": case.tenant.state if case.tenant else "MN",
        "tenant_zip": case.tenant.zip_code if case.tenant else "",
        "tenant_phone": case.tenant.phone if case.tenant else "",
        "tenant_email": case.tenant.email if case.tenant else "",
        "landlord_name": case.landlord.name if case.landlord else "",
        "landlord_address": case.landlord.address if case.landlord else "",
        "court_date": case.notice.court_date.strftime("%m/%d/%Y") if case.notice and case.notice.court_date else "",
        "notice_type": case.notice.notice_type if case.notice else "",
        "amount_claimed_cents": case.notice.amount_claimed if case.notice else 0,
        "amount_claimed_formatted": f"${((case.notice.amount_claimed if case.notice else 0) or 0) / 100:.2f}",
        "monthly_rent_cents": case.tenant.monthly_rent if case.tenant else 0,
        "monthly_rent_formatted": f"${((case.tenant.monthly_rent if case.tenant else 0) or 0) / 100:.2f}",
        "answer_date": datetime.now(timezone.utc).strftime("%m/%d/%Y"),
        
        # Pre-checked defenses
        "applicable_defenses": [d.code for d in case.defenses if d.applicable],
        
        # Evidence summary
        "evidence_count": len(case.evidence),
        "evidence_list": ", ".join(e.exhibit_label or "" for e in case.evidence[:5] if e.exhibit_label),
    }
    
    return form_data


@router.get("/court-info")
async def get_court_info():
    """
    Get Dakota County court information.
    
    No authentication required - public info.
    """
    return {
        "county": "Dakota",
        "state": "Minnesota",
        "court_type": "Housing Court (District Court)",
        "address": MNCourtRules.COURT_ADDRESS,
        "efiling": {
            "available": True,
            "url": MNCourtRules.EFILING_URL,
            "guide_and_file": MNCourtRules.GUIDE_AND_FILE_URL,
        },
        "filing_requirements": {
            "copies_required": MNCourtRules.REQUIRED_COPIES,
            "allowed_formats": MNCourtRules.ALLOWED_FORMATS,
            "max_file_size_mb": MNCourtRules.MAX_FILE_SIZE_MB,
        },
        "fees": {
            "counterclaim_filing": MNCourtRules.COUNTERCLAIM_FILING_FEE,
            "fee_waiver_available": True,
            "fee_waiver_name": "In Forma Pauperis (IFP)",
        },
        "appearance": {
            "zoom_allowed": MNCourtRules.ZOOM_APPEARANCE_ALLOWED,
            "in_person_required_for": MNCourtRules.IN_PERSON_REQUIRED_FOR,
        },
        "deadlines": {
            "answer_deadline_days": MNCourtRules.ANSWER_DEADLINE_DAYS,
        },
        "helpful_links": {
            "mn_courts": "https://www.mncourts.gov/",
            "legal_aid": "https://www.lawhelpmn.org/",
            "tenant_rights": "https://www.ag.state.mn.us/Consumer/Handbooks/LT/default.asp",
            "home_line": "https://homelinemn.org/",
        },
    }
