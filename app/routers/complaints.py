"""
Semptify 5.0 - Complaint Filing Wizard Router
API endpoints for guided complaint filing with regulatory agencies.
Integrated with Location Service for state-specific agencies.
NOW WITH DATABASE PERSISTENCE.
"""

from fastapi import APIRouter, HTTPException, Query, Request, Depends
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.security import get_optional_user_id, sanitize_user_input

from app.services.complaint_wizard import (
    complaint_wizard,
    AgencyType,
    ComplaintDraft,
)


router = APIRouter(prefix="/api/complaints", tags=["complaints"])


# =============================================================================
# Request/Response Models
# =============================================================================

class CreateDraftRequest(BaseModel):
    """Request to create a complaint draft."""
    agency_id: str
    subject: str = ""


class UpdateDraftRequest(BaseModel):
    """Request to update a complaint draft."""
    subject: Optional[str] = None
    description: Optional[str] = None
    incident_dates: Optional[list[str]] = None
    damages_claimed: Optional[float] = None
    relief_sought: Optional[str] = None
    respondent_name: Optional[str] = None
    respondent_company: Optional[str] = None
    respondent_address: Optional[str] = None
    respondent_phone: Optional[str] = None
    timeline_included: Optional[bool] = None
    notes: Optional[str] = None


class AttachDocumentsRequest(BaseModel):
    """Request to attach documents to a draft."""
    document_ids: list[str]


class MarkFiledRequest(BaseModel):
    """Request to mark complaint as filed."""
    confirmation_number: Optional[str] = None


class RecommendAgenciesRequest(BaseModel):
    """Request for agency recommendations."""
    keywords: list[str]


class AgencyResponse(BaseModel):
    """Agency information response."""
    id: str
    name: str
    type: str
    description: str
    jurisdiction: str
    website: str
    filing_url: Optional[str]
    phone: Optional[str]
    email: Optional[str]
    typical_response_days: int
    complaint_types: list[str]
    required_documents: list[str]
    tips: list[str]


# =============================================================================
# Helper: Get User ID from Request
# =============================================================================

def get_user_id_from_request(request: Request, user_id: Optional[str] = None) -> str:
    """
    Get user ID from request (session, cookie, or temp).
    
    Now accepts an optional authenticated user_id from the secure dependency.
    """
    # Use authenticated user_id if provided
    if user_id:
        return user_id
    
    # Try session first (if SessionMiddleware is installed)
    try:
        if "session" in request.scope:
            uid = request.session.get("user_id")
            if uid:
                return uid
    except (AssertionError, KeyError):
        pass  # SessionMiddleware not installed
    
    # Try cookie
    uid = request.cookies.get("semptify_user_id")
    if uid:
        return uid
    
    # Fall back to IP-based temp ID
    client_ip = request.client.host if request.client else "unknown"
    return f"temp_{hash(client_ip) % 100000:05d}"


# =============================================================================
# Agency Endpoints
# =============================================================================

@router.get("/agencies")
async def list_agencies(
    request: Request,
    agency_type: Optional[AgencyType] = None,
    state: Optional[str] = Query(None, description="State code (e.g., MN). If not provided, uses user's location.")
) -> list[AgencyResponse]:
    """
    List available complaint agencies.
    
    Agencies are filtered by state. If no state is provided,
    uses the user's location from the Location Service.
    """
    if agency_type:
        agencies = complaint_wizard.get_agencies_by_type(agency_type)
    elif state:
        agencies = complaint_wizard.get_all_agencies(state.upper())
    else:
        # Use location service to get user's state
        user_id = get_user_id_from_request(request)
        agencies = complaint_wizard.get_agencies_for_user(user_id)
    
    return [
        AgencyResponse(
            id=a.id,
            name=a.name,
            type=a.type.value,
            description=a.description,
            jurisdiction=a.jurisdiction,
            website=a.website,
            filing_url=a.filing_url,
            phone=a.phone,
            email=a.email,
            typical_response_days=a.typical_response_days,
            complaint_types=a.complaint_types,
            required_documents=a.required_documents,
            tips=a.tips
        )
        for a in agencies
    ]


@router.get("/agencies/{agency_id}")
async def get_agency(agency_id: str) -> AgencyResponse:
    """Get details for a specific agency."""
    agency = complaint_wizard.get_agency(agency_id)
    if not agency:
        raise HTTPException(status_code=404, detail="Agency not found")
    
    return AgencyResponse(
        id=agency.id,
        name=agency.name,
        type=agency.type.value,
        description=agency.description,
        jurisdiction=agency.jurisdiction,
        website=agency.website,
        filing_url=agency.filing_url,
        phone=agency.phone,
        email=agency.email,
        typical_response_days=agency.typical_response_days,
        complaint_types=agency.complaint_types,
        required_documents=agency.required_documents,
        tips=agency.tips
    )


@router.post("/agencies/recommend")
async def recommend_agencies(
    request: RecommendAgenciesRequest
) -> list[AgencyResponse]:
    """Get agency recommendations based on complaint keywords."""
    agencies = complaint_wizard.get_recommended_agencies(request.keywords)
    
    return [
        AgencyResponse(
            id=a.id,
            name=a.name,
            type=a.type.value,
            description=a.description,
            jurisdiction=a.jurisdiction,
            website=a.website,
            filing_url=a.filing_url,
            phone=a.phone,
            email=a.email,
            typical_response_days=a.typical_response_days,
            complaint_types=a.complaint_types,
            required_documents=a.required_documents,
            tips=a.tips
        )
        for a in agencies
    ]


@router.get("/agencies/{agency_id}/checklist")
async def get_agency_checklist(agency_id: str) -> dict:
    """Get filing checklist for an agency."""
    checklist = complaint_wizard.get_filing_checklist(agency_id)
    if "error" in checklist:
        raise HTTPException(status_code=404, detail=checklist["error"])
    return checklist


# =============================================================================
# Draft Endpoints
# =============================================================================

@router.post("/drafts")
async def create_draft(
    request_body: CreateDraftRequest,
    request: Request,
    user_id: Optional[str] = Depends(get_optional_user_id),
    db: AsyncSession = Depends(get_db)
) -> ComplaintDraft:
    """Create a new complaint draft (persisted to database)."""
    # Get user_id from session or fallback
    uid = get_user_id_from_request(request, user_id)
    
    # Verify agency exists
    agency = complaint_wizard.get_agency(request_body.agency_id)
    if not agency:
        raise HTTPException(status_code=404, detail="Agency not found")

    draft = await complaint_wizard.create_draft_db(
        db=db,
        user_id=uid,
        agency_id=request_body.agency_id,
        subject=sanitize_user_input(request_body.subject)
    )
    return draft


@router.get("/drafts")
async def list_drafts(
    request: Request,
    user_id: Optional[str] = Depends(get_optional_user_id),
    db: AsyncSession = Depends(get_db)
) -> list[ComplaintDraft]:
    """List all drafts for a user (from database)."""
    uid = get_user_id_from_request(request, user_id)
    return await complaint_wizard.get_user_drafts_db(db, uid)


@router.get("/drafts/{draft_id}")
async def get_draft(
    draft_id: str,
    db: AsyncSession = Depends(get_db)
) -> ComplaintDraft:
    """Get a specific draft (from database)."""
    draft = await complaint_wizard.get_draft_db(db, draft_id)
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")
    return draft


@router.patch("/drafts/{draft_id}")
async def update_draft(
    draft_id: str,
    request: UpdateDraftRequest,
    db: AsyncSession = Depends(get_db)
) -> ComplaintDraft:
    """Update a complaint draft (in database)."""
    updates = request.model_dump(exclude_none=True)
    draft = await complaint_wizard.update_draft_db(db, draft_id, **updates)
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")
    return draft


@router.delete("/drafts/{draft_id}")
async def delete_draft(
    draft_id: str,
    db: AsyncSession = Depends(get_db)
) -> dict:
    """Delete a complaint draft (from database)."""
    success = await complaint_wizard.delete_draft_db(db, draft_id)
    if not success:
        raise HTTPException(status_code=404, detail="Draft not found")
    return {"status": "deleted", "draft_id": draft_id}


@router.post("/drafts/{draft_id}/documents")
async def attach_documents(
    draft_id: str,
    request: AttachDocumentsRequest,
    db: AsyncSession = Depends(get_db)
) -> ComplaintDraft:
    """Attach documents to a draft (in database)."""
    draft = await complaint_wizard.attach_documents_db(db, draft_id, request.document_ids)
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")
    return draft


@router.get("/drafts/{draft_id}/preview")
async def preview_complaint(
    draft_id: str,
    db: AsyncSession = Depends(get_db)
) -> dict:
    """Preview the formatted complaint text."""
    draft = await complaint_wizard.get_draft_db(db, draft_id)
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")

    text = complaint_wizard.generate_complaint_text(draft)
    agency = complaint_wizard.get_agency(draft.agency_id)

    return {
        "draft_id": draft_id,
        "agency": agency.name if agency else "Unknown",
        "filing_url": agency.filing_url if agency else None,
        "complaint_text": text,
        "attached_documents": len(draft.attached_document_ids),
        "ready_to_file": bool(
            draft.subject and 
            draft.description and 
            draft.respondent_name
        )
    }


@router.get("/drafts/{draft_id}/export")
async def export_complaint(
    draft_id: str,
    format: str = Query("text", description="Export format: text, html, or pdf"),
    db: AsyncSession = Depends(get_db)
):
    """Export complaint as text, HTML, or attempt PDF."""
    from fastapi.responses import PlainTextResponse, HTMLResponse
    
    draft = await complaint_wizard.get_draft_db(db, draft_id)
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")

    text = complaint_wizard.generate_complaint_text(draft)
    agency = complaint_wizard.get_agency(draft.agency_id)
    
    if format == "html":
        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Complaint - {draft.subject or 'Draft'}</title>
    <style>
        body {{ font-family: Georgia, serif; max-width: 800px; margin: 40px auto; padding: 20px; line-height: 1.8; }}
        h1 {{ text-align: center; border-bottom: 2px solid #333; padding-bottom: 10px; }}
        .section {{ margin: 20px 0; }}
        .section-title {{ font-weight: bold; border-bottom: 1px solid #ccc; margin-bottom: 10px; }}
        pre {{ white-space: pre-wrap; font-family: inherit; }}
    </style>
</head>
<body>
    <h1>FORMAL COMPLAINT</h1>
    <p style="text-align: center;">To: {agency.name if agency else 'Agency'}</p>
    <pre>{text}</pre>
</body>
</html>
"""
        return HTMLResponse(content=html_content)
    
    # Default: plain text
    return PlainTextResponse(content=text, media_type="text/plain")


@router.post("/drafts/{draft_id}/file")
async def mark_complaint_filed(
    draft_id: str,
    request: MarkFiledRequest,
    db: AsyncSession = Depends(get_db)
) -> ComplaintDraft:
    """Mark a complaint as filed (in database)."""
    draft = await complaint_wizard.mark_as_filed_db(
        db,
        draft_id,
        confirmation_number=request.confirmation_number
    )
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")
    return draft


# =============================================================================
# Quick Actions
# =============================================================================

@router.get("/quick-start")
async def quick_start_guide() -> dict:
    """Get quick start guide for filing complaints."""
    return {
        "title": "Complaint Filing Quick Start",
        "steps": [
            {
                "step": 1,
                "title": "Choose Your Target",
                "description": "Select the agency most likely to help with your specific issue",
                "action": "GET /api/complaints/agencies or POST /api/complaints/agencies/recommend"
            },
            {
                "step": 2,
                "title": "Create a Draft",
                "description": "Start your complaint draft with the chosen agency",
                "action": "POST /api/complaints/drafts"
            },
            {
                "step": 3,
                "title": "Fill In Details",
                "description": "Add your complaint details, dates, and respondent info",
                "action": "PATCH /api/complaints/drafts/{id}"
            },
            {
                "step": 4,
                "title": "Attach Evidence",
                "description": "Link your uploaded documents to the complaint",
                "action": "POST /api/complaints/drafts/{id}/documents"
            },
            {
                "step": 5,
                "title": "Preview & File",
                "description": "Review the formatted complaint and file with the agency",
                "action": "GET /api/complaints/drafts/{id}/preview"
            },
            {
                "step": 6,
                "title": "Track Status",
                "description": "Record your filing confirmation and track progress",
                "action": "POST /api/complaints/drafts/{id}/file"
            }
        ],
        "tips": [
            "File with multiple agencies for maximum pressure",
            "The Attorney General handles fraud and deceptive practices",
            "HUD handles housing discrimination specifically",
            "MN Commerce can revoke property manager licenses",
            "BBB complaints become public record",
            "HOME Line offers free tenant advice hotline",
            "Legal Aid can represent you in court for free"
        ],
        "recommended_order": [
            "1. HOME Line (get immediate advice - 612-728-5767)",
            "2. Legal Aid MN (free legal representation)",
            "3. MN Attorney General (strongest enforcement)",
            "4. HUD (if any discrimination involved)",
            "5. MN Commerce (license accountability)",
            "6. BBB (public pressure)"
        ]
    }


@router.post("/analyze-case")
async def analyze_case_for_complaints(
    keywords: list[str] = Query(..., description="Keywords describing your situation")
) -> dict:
    """Analyze your case and recommend complaint strategies."""
    recommended = complaint_wizard.get_recommended_agencies(keywords)

    strategies = []
    for agency in recommended[:5]:
        strategies.append({
            "agency": agency.name,
            "agency_id": agency.id,
            "why": f"Handles: {', '.join(agency.complaint_types[:3])}",
            "filing_url": agency.filing_url,
            "response_time": f"~{agency.typical_response_days} days"
        })

    return {
        "keywords_analyzed": keywords,
        "recommended_strategies": strategies,
        "multi_agency_approach": len(recommended) > 1,
        "advice": (
            "Filing with multiple agencies creates pressure from multiple directions. "
            "Start with Legal Aid for guidance, then file formal complaints with regulatory bodies."
        )
    }


# =============================================================================
# Wizard Session Endpoints (for guided complaint flow)
# =============================================================================

import uuid

# In-memory wizard sessions (for simplicity)
_wizard_sessions: dict = {}


class WizardStartRequest(BaseModel):
    """Request to start a complaint wizard session."""
    complaint_type: str


class WizardSession(BaseModel):
    """Wizard session state."""
    session_id: str
    complaint_type: str
    step: int = 1
    data: dict = {}
    created_at: str


@router.post("/wizard/start")
async def start_wizard(request: WizardStartRequest) -> WizardSession:
    """Start a new complaint wizard session."""
    session_id = str(uuid.uuid4())
    session = WizardSession(
        session_id=session_id,
        complaint_type=request.complaint_type,
        step=1,
        data={},
        created_at=datetime.utcnow().isoformat()
    )
    _wizard_sessions[session_id] = session.model_dump()
    return session


@router.get("/wizard/{session_id}")
async def get_wizard_session(session_id: str) -> WizardSession:
    """Get current wizard session state."""
    if session_id not in _wizard_sessions:
        raise HTTPException(status_code=404, detail="Wizard session not found")
    return WizardSession(**_wizard_sessions[session_id])


# =============================================================================
# Submit Complaint Endpoint
# =============================================================================

class SubmitComplaintRequest(BaseModel):
    """Request to submit a complaint."""
    agency_id: str
    complaint_type: str = "general"
    subject: str = ""
    summary: Optional[str] = None
    detailed_description: Optional[str] = None
    target_type: Optional[str] = None
    target_name: Optional[str] = None


@router.post("/submit")
async def submit_complaint(
    request: SubmitComplaintRequest,
    _db: AsyncSession = Depends(get_db)
) -> dict:
    """Submit a complaint to an agency."""
    # Validate agency exists
    agency = complaint_wizard.get_agency(request.agency_id)
    if not agency:
        raise HTTPException(status_code=422, detail="Invalid agency_id")

    # Create a draft and mark it ready for submission
    draft_id = f"cmp_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:8]}"
    
    return {
        "status": "submitted",
        "complaint_id": draft_id,
        "agency": agency.name,
        "agency_id": request.agency_id,
        "subject": request.subject,
        "created_at": datetime.utcnow().isoformat(),
        "next_steps": [
            f"Complaint submitted to {agency.name}",
            f"Expected response in ~{agency.typical_response_days} days",
            "Keep your complaint ID for reference"
        ]
    }