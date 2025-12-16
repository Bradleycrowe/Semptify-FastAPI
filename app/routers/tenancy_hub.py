"""
Tenancy Hub API Router

Provides unified access to all tenancy documentation, with search,
cross-referencing, and context-aware information retrieval.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Body
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime, timezone

from app.core.security import get_user_id
from ..services.tenancy_hub import (
    get_tenancy_hub_service,
    TenancyCase,
    Party, PartyRole,
    Property,
    LeaseTerms,
    Payment,
    TenancyDocument, DocumentCategory,
    TimelineEvent, EventType,
    Issue, IssueCategory, IssueSeverity,
    LegalCase, CaseStatus,
)


router = APIRouter(prefix="/api/tenancy", tags=["Tenancy Hub"])


# =============================================================================
# REQUEST/RESPONSE MODELS
# =============================================================================

class CreateCaseRequest(BaseModel):
    case_name: str = ""
    
class PartyRequest(BaseModel):
    role: str
    name: str
    address: str = ""
    city: str = ""
    state: str = ""
    zip_code: str = ""
    phone: str = ""
    email: str = ""
    company_name: str = ""
    relationship_notes: str = ""

class PropertyRequest(BaseModel):
    street_address: str
    unit_number: str = ""
    city: str
    state: str
    zip_code: str
    county: str = ""
    property_type: str = ""
    bedrooms: int = 0
    bathrooms: float = 0.0
    square_feet: int = 0
    year_built: int = 0
    amenities: List[str] = []
    utilities_included: List[str] = []

class LeaseRequest(BaseModel):
    lease_start: str
    lease_end: str = ""
    move_in_date: str = ""
    monthly_rent: float
    security_deposit: float = 0.0
    rent_due_day: int = 1
    grace_period_days: int = 0
    late_fee_amount: float = 0.0
    lease_type: str = "fixed"
    notice_to_vacate_days: int = 30
    authorized_occupants: List[str] = []
    pets_allowed: bool = False
    tenant_pays: List[str] = []
    landlord_pays: List[str] = []

class PaymentRequest(BaseModel):
    payment_date: str
    due_date: str = ""
    amount: float
    payment_type: str = "rent"
    payment_method: str = ""
    status: str = "completed"
    receipt_number: str = ""
    check_number: str = ""
    period_start: str = ""
    period_end: str = ""
    notes: str = ""

class DocumentRequest(BaseModel):
    filename: str
    title: str = ""
    category: str = "other"
    description: str = ""
    document_date: str = ""
    full_text: str = ""
    summary: str = ""
    key_points: List[str] = []
    tags: List[str] = []
    storage_path: str = ""
    related_party_ids: List[str] = []

class EventRequest(BaseModel):
    event_type: str
    event_date: str
    event_time: str = ""
    title: str
    description: str = ""
    location: str = ""
    party_ids: List[str] = []
    document_ids: List[str] = []
    is_deadline: bool = False
    deadline_date: str = ""
    case_number: str = ""
    court_name: str = ""
    notes: str = ""

class IssueRequest(BaseModel):
    category: str
    severity: str = "medium"
    title: str
    description: str = ""
    reported_date: str = ""
    location_in_property: str = ""
    is_habitability_issue: bool = False
    is_lease_violation: bool = False
    violates_statute: str = ""

class LegalCaseRequest(BaseModel):
    case_number: str
    case_type: str = "eviction"
    court_name: str = ""
    county: str = ""
    judicial_district: str = ""
    filed_date: str = ""
    served_date: str = ""
    answer_due_date: str = ""
    hearing_date: str = ""
    hearing_time: str = ""
    amount_claimed: float = 0.0
    claims: List[str] = []
    defenses: List[str] = []
    counterclaims: List[str] = []
    plaintiff_ids: List[str] = []
    defendant_ids: List[str] = []

class SearchRequest(BaseModel):
    query: str
    entity_types: List[str] = []


# =============================================================================
# CASE MANAGEMENT ENDPOINTS
# =============================================================================

@router.post("/cases")
async def create_case(
    request: CreateCaseRequest,
    user_id: str = Depends(get_user_id)
):
    """Create a new tenancy case."""
    service = get_tenancy_hub_service()
    case = service.create_case(user_id, request.case_name)
    return {
        "success": True,
        "case_id": case.id,
        "case": case.to_dict()
    }


@router.get("/cases")
async def list_cases(user_id: str = Depends(get_user_id)):
    """List all tenancy cases for a user."""
    service = get_tenancy_hub_service()
    cases = service.get_user_cases(user_id)
    return {
        "success": True,
        "count": len(cases),
        "cases": [c.to_dict() for c in cases]
    }


@router.get("/cases/{case_id}")
async def get_case(case_id: str):
    """Get a tenancy case by ID."""
    service = get_tenancy_hub_service()
    case = service.get_case(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    return {
        "success": True,
        "case": case.to_dict()
    }


@router.get("/cases/{case_id}/summary")
async def get_case_summary(case_id: str):
    """Get a summary of a tenancy case."""
    service = get_tenancy_hub_service()
    case = service.get_case(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    return {
        "success": True,
        "summary": case.get_summary(),
        "tenant": case.tenant.to_dict() if case.tenant else None,
        "landlord": case.landlord.to_dict() if case.landlord else None,
        "property": case.property.to_dict() if case.property else None,
    }


# =============================================================================
# PARTY ENDPOINTS
# =============================================================================

@router.post("/cases/{case_id}/parties")
async def add_party(case_id: str, request: PartyRequest):
    """Add a party to a tenancy case."""
    service = get_tenancy_hub_service()
    
    try:
        role = PartyRole(request.role)
    except ValueError:
        role = PartyRole.OTHER
    
    party = Party(
        id="",
        role=role,
        name=request.name,
        address=request.address,
        city=request.city,
        state=request.state,
        zip_code=request.zip_code,
        phone=request.phone,
        email=request.email,
        company_name=request.company_name,
        relationship_notes=request.relationship_notes,
    )
    
    try:
        party = service.add_party(case_id, party)
        return {"success": True, "party": party.to_dict()}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/cases/{case_id}/parties")
async def list_parties(case_id: str, role: Optional[str] = None):
    """List all parties in a tenancy case."""
    service = get_tenancy_hub_service()
    case = service.get_case(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    
    parties = list(case.parties.values())
    if role:
        parties = [p for p in parties if p.role.value == role]
    
    return {
        "success": True,
        "count": len(parties),
        "parties": [p.to_dict() for p in parties]
    }


# =============================================================================
# PROPERTY ENDPOINTS
# =============================================================================

@router.post("/cases/{case_id}/property")
async def set_property(case_id: str, request: PropertyRequest):
    """Set the property for a tenancy case."""
    service = get_tenancy_hub_service()
    case = service.get_case(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    
    property_obj = Property(
        id=f"prop_{case_id[:8]}",
        street_address=request.street_address,
        unit_number=request.unit_number,
        city=request.city,
        state=request.state,
        zip_code=request.zip_code,
        county=request.county,
        property_type=request.property_type,
        bedrooms=request.bedrooms,
        bathrooms=request.bathrooms,
        square_feet=request.square_feet,
        year_built=request.year_built,
        amenities=request.amenities,
        utilities_included=request.utilities_included,
    )
    
    case.property = property_obj
    case.updated_at = datetime.now(timezone.utc).isoformat()
    
    return {"success": True, "property": property_obj.to_dict()}


@router.get("/cases/{case_id}/property")
async def get_property(case_id: str):
    """Get the property for a tenancy case."""
    service = get_tenancy_hub_service()
    case = service.get_case(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    
    if not case.property:
        return {"success": True, "property": None}
    
    return {"success": True, "property": case.property.to_dict()}


# =============================================================================
# LEASE ENDPOINTS
# =============================================================================

@router.post("/cases/{case_id}/lease")
async def set_lease(case_id: str, request: LeaseRequest):
    """Set the lease terms for a tenancy case."""
    service = get_tenancy_hub_service()
    case = service.get_case(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    
    lease = LeaseTerms(
        id=f"lease_{case_id[:8]}",
        lease_start=request.lease_start,
        lease_end=request.lease_end,
        move_in_date=request.move_in_date,
        monthly_rent=request.monthly_rent,
        security_deposit=request.security_deposit,
        rent_due_day=request.rent_due_day,
        grace_period_days=request.grace_period_days,
        late_fee_amount=request.late_fee_amount,
        lease_type=request.lease_type,
        notice_to_vacate_days=request.notice_to_vacate_days,
        authorized_occupants=request.authorized_occupants,
        pets_allowed=request.pets_allowed,
        tenant_pays=request.tenant_pays,
        landlord_pays=request.landlord_pays,
    )
    
    case.lease = lease
    case.updated_at = datetime.now(timezone.utc).isoformat()
    
    return {"success": True, "lease": lease.to_dict()}


@router.get("/cases/{case_id}/lease")
async def get_lease(case_id: str):
    """Get the lease terms for a tenancy case."""
    service = get_tenancy_hub_service()
    case = service.get_case(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    
    if not case.lease:
        return {"success": True, "lease": None}
    
    return {"success": True, "lease": case.lease.to_dict()}


# =============================================================================
# PAYMENT ENDPOINTS
# =============================================================================

@router.post("/cases/{case_id}/payments")
async def add_payment(case_id: str, request: PaymentRequest):
    """Add a payment record to a tenancy case."""
    service = get_tenancy_hub_service()
    
    payment = Payment(
        id="",
        payment_date=request.payment_date,
        due_date=request.due_date,
        amount=request.amount,
        payment_type=request.payment_type,
        payment_method=request.payment_method,
        status=request.status,
        receipt_number=request.receipt_number,
        check_number=request.check_number,
        period_start=request.period_start,
        period_end=request.period_end,
        notes=request.notes,
    )
    
    try:
        payment = service.add_payment(case_id, payment)
        return {"success": True, "payment": payment.to_dict()}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/cases/{case_id}/payments")
async def list_payments(
    case_id: str,
    payment_type: Optional[str] = None,
    status: Optional[str] = None
):
    """List all payments in a tenancy case."""
    service = get_tenancy_hub_service()
    case = service.get_case(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    
    payments = list(case.payments.values())
    
    if payment_type:
        payments = [p for p in payments if p.payment_type == payment_type]
    if status:
        payments = [p for p in payments if p.status == status]
    
    # Sort by date
    payments.sort(key=lambda p: p.payment_date or "", reverse=True)
    
    return {
        "success": True,
        "count": len(payments),
        "payments": [p.to_dict() for p in payments]
    }


# =============================================================================
# DOCUMENT ENDPOINTS
# =============================================================================

@router.post("/cases/{case_id}/documents")
async def add_document(case_id: str, request: DocumentRequest):
    """Add a document to a tenancy case."""
    service = get_tenancy_hub_service()
    
    try:
        category = DocumentCategory(request.category)
    except ValueError:
        category = DocumentCategory.OTHER
    
    doc = TenancyDocument(
        id="",
        filename=request.filename,
        title=request.title or request.filename,
        category=category,
        description=request.description,
        document_date=request.document_date,
        full_text=request.full_text,
        summary=request.summary,
        key_points=request.key_points,
        tags=request.tags,
        storage_path=request.storage_path,
        related_party_ids=request.related_party_ids,
    )
    
    try:
        doc = service.add_document(case_id, doc)
        return {"success": True, "document": doc.to_dict()}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/cases/{case_id}/documents")
async def list_documents(
    case_id: str,
    category: Optional[str] = None
):
    """List all documents in a tenancy case."""
    service = get_tenancy_hub_service()
    case = service.get_case(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    
    docs = list(case.documents.values())
    
    if category:
        docs = [d for d in docs if (d.category.value if isinstance(d.category, DocumentCategory) else d.category) == category]
    
    return {
        "success": True,
        "count": len(docs),
        "documents": [d.to_dict() for d in docs]
    }


# =============================================================================
# EVENT/TIMELINE ENDPOINTS
# =============================================================================

@router.post("/cases/{case_id}/events")
async def add_event(case_id: str, request: EventRequest):
    """Add an event to a tenancy case timeline."""
    service = get_tenancy_hub_service()
    
    try:
        event_type = EventType(request.event_type)
    except ValueError:
        event_type = EventType.OTHER
    
    event = TimelineEvent(
        id="",
        event_type=event_type,
        event_date=request.event_date,
        event_time=request.event_time,
        title=request.title,
        description=request.description,
        location=request.location,
        party_ids=request.party_ids,
        document_ids=request.document_ids,
        is_deadline=request.is_deadline,
        deadline_date=request.deadline_date,
        case_number=request.case_number,
        court_name=request.court_name,
        notes=request.notes,
    )
    
    try:
        event = service.add_event(case_id, event)
        return {"success": True, "event": event.to_dict()}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/cases/{case_id}/timeline")
async def get_timeline(
    case_id: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
):
    """Get the timeline of events for a tenancy case."""
    service = get_tenancy_hub_service()
    timeline = service.get_timeline(case_id, start_date, end_date)
    
    return {
        "success": True,
        "count": len(timeline),
        "timeline": timeline
    }


@router.get("/cases/{case_id}/deadlines")
async def get_deadlines(
    case_id: str,
    include_completed: bool = False
):
    """Get all deadlines for a tenancy case."""
    service = get_tenancy_hub_service()
    deadlines = service.get_deadlines(case_id, include_completed)
    
    return {
        "success": True,
        "count": len(deadlines),
        "deadlines": deadlines
    }


# =============================================================================
# ISSUE ENDPOINTS
# =============================================================================

@router.post("/cases/{case_id}/issues")
async def add_issue(case_id: str, request: IssueRequest):
    """Add an issue to a tenancy case."""
    service = get_tenancy_hub_service()
    
    try:
        category = IssueCategory(request.category)
    except ValueError:
        category = IssueCategory.OTHER
    
    try:
        severity = IssueSeverity(request.severity)
    except ValueError:
        severity = IssueSeverity.MEDIUM
    
    issue = Issue(
        id="",
        category=category,
        severity=severity,
        title=request.title,
        description=request.description,
        reported_date=request.reported_date or datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        location_in_property=request.location_in_property,
        is_habitability_issue=request.is_habitability_issue,
        is_lease_violation=request.is_lease_violation,
        violates_statute=request.violates_statute,
    )
    
    try:
        issue = service.add_issue(case_id, issue)
        return {"success": True, "issue": issue.to_dict()}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/cases/{case_id}/issues")
async def list_issues(
    case_id: str,
    status: Optional[str] = None,
    category: Optional[str] = None,
    severity: Optional[str] = None
):
    """List all issues in a tenancy case."""
    service = get_tenancy_hub_service()
    case = service.get_case(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    
    issues = list(case.issues.values())
    
    if status:
        issues = [i for i in issues if i.status == status]
    if category:
        issues = [i for i in issues if (i.category.value if isinstance(i.category, IssueCategory) else i.category) == category]
    if severity:
        issues = [i for i in issues if (i.severity.value if isinstance(i.severity, IssueSeverity) else i.severity) == severity]
    
    return {
        "success": True,
        "count": len(issues),
        "issues": [i.to_dict() for i in issues]
    }


# =============================================================================
# LEGAL CASE ENDPOINTS
# =============================================================================

@router.post("/cases/{case_id}/legal-cases")
async def add_legal_case(case_id: str, request: LegalCaseRequest):
    """Add a legal case to a tenancy case."""
    service = get_tenancy_hub_service()
    
    legal_case = LegalCase(
        id="",
        case_number=request.case_number,
        case_type=request.case_type,
        court_name=request.court_name,
        county=request.county,
        judicial_district=request.judicial_district,
        filed_date=request.filed_date,
        served_date=request.served_date,
        answer_due_date=request.answer_due_date,
        hearing_date=request.hearing_date,
        hearing_time=request.hearing_time,
        amount_claimed=request.amount_claimed,
        claims=request.claims,
        defenses=request.defenses,
        counterclaims=request.counterclaims,
        plaintiff_ids=request.plaintiff_ids,
        defendant_ids=request.defendant_ids,
    )
    
    try:
        legal_case = service.add_legal_case(case_id, legal_case)
        return {"success": True, "legal_case": legal_case.to_dict()}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/cases/{case_id}/legal-cases")
async def list_legal_cases(case_id: str, status: Optional[str] = None):
    """List all legal cases in a tenancy case."""
    service = get_tenancy_hub_service()
    case = service.get_case(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    
    legal_cases = list(case.legal_cases.values())
    
    if status:
        legal_cases = [lc for lc in legal_cases if (lc.status.value if isinstance(lc.status, CaseStatus) else lc.status) == status]
    
    return {
        "success": True,
        "count": len(legal_cases),
        "legal_cases": [lc.to_dict() for lc in legal_cases]
    }


# =============================================================================
# SEARCH & CROSS-REFERENCE ENDPOINTS
# =============================================================================

@router.post("/cases/{case_id}/search")
async def search_case(case_id: str, request: SearchRequest):
    """
    Search across all entities in a tenancy case.
    
    entity_types can include: party, document, event, payment, issue, legal_case
    """
    service = get_tenancy_hub_service()
    results = service.search(case_id, request.query, request.entity_types if request.entity_types else None)
    
    total = sum(len(v) for v in results.values())
    
    return {
        "success": True,
        "query": request.query,
        "total_results": total,
        "results": results
    }


@router.get("/cases/{case_id}/cross-reference/{entity_type}/{entity_id}")
async def get_cross_references(case_id: str, entity_type: str, entity_id: str):
    """
    Get all entities that reference the given entity.
    
    entity_type: party, document, event, issue, legal_case
    """
    service = get_tenancy_hub_service()
    refs = service.get_cross_references(case_id, entity_type, entity_id)
    
    total = sum(len(v) for v in refs.values())
    
    return {
        "success": True,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "total_references": total,
        "references": refs
    }


# =============================================================================
# CONTEXT PACK ENDPOINTS
# =============================================================================

@router.get("/cases/{case_id}/context/{context_type}")
async def get_context_pack(case_id: str, context_type: str):
    """
    Get a context-specific pack of information.
    
    context_type options:
    - court_hearing: All info needed for a court hearing
    - repair_history: All issues and repairs
    - payment_history: All payment records
    - communication_log: All communications
    - evidence_pack: All evidence documents
    - lease_summary: Lease terms and amendments
    """
    service = get_tenancy_hub_service()
    pack = service.get_context_pack(case_id, context_type)
    
    if "error" in pack:
        raise HTTPException(status_code=400, detail=pack["error"])
    
    return {
        "success": True,
        "context_type": context_type,
        "pack": pack
    }


# =============================================================================
# METADATA ENDPOINTS
# =============================================================================

@router.get("/enums")
async def get_enums():
    """Get all available enum values for the tenancy hub."""
    return {
        "success": True,
        "enums": {
            "party_roles": [e.value for e in PartyRole],
            "document_categories": [e.value for e in DocumentCategory],
            "event_types": [e.value for e in EventType],
            "issue_categories": [e.value for e in IssueCategory],
            "issue_severities": [e.value for e in IssueSeverity],
            "case_statuses": [e.value for e in CaseStatus],
        }
    }


@router.get("/context-types")
async def get_context_types():
    """Get available context pack types."""
    return {
        "success": True,
        "context_types": [
            {
                "type": "court_hearing",
                "description": "All info needed for a court hearing",
                "includes": ["parties", "legal_cases", "key_documents", "timeline", "issues", "deadlines"]
            },
            {
                "type": "repair_history",
                "description": "All issues and repairs",
                "includes": ["issues", "repair_events", "photos", "communications"]
            },
            {
                "type": "payment_history",
                "description": "All payment records",
                "includes": ["lease_terms", "payments", "payment_events", "summary"]
            },
            {
                "type": "communication_log",
                "description": "All communications",
                "includes": ["communications", "documents"]
            },
            {
                "type": "evidence_pack",
                "description": "All evidence documents",
                "includes": ["photos", "videos", "documents", "witness_statements"]
            },
            {
                "type": "lease_summary",
                "description": "Lease terms and amendments",
                "includes": ["lease", "amendments", "lease_document", "amendment_documents"]
            }
        ]
    }
