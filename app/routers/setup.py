"""
Setup Wizard Router
Guides users through initial system configuration.
Ensures all data is properly collected and integrated before use.
"""

from typing import Optional, List
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, EmailStr

from app.core.security import require_user, StorageUser
from app.core.database import get_db_session
from app.models.models import User, Document
from sqlalchemy import select, update


router = APIRouter()


# =============================================================================
# Data Models
# =============================================================================

class UserProfile(BaseModel):
    """User's personal information"""
    full_name: str = Field(..., min_length=2, max_length=100)
    email: Optional[str] = None
    phone: Optional[str] = None
    address: str = Field(..., min_length=5)
    city: str = Field(..., min_length=2)
    state: str = Field(default="MN", max_length=2)
    zip_code: str = Field(..., min_length=5, max_length=10)


class PartyInfo(BaseModel):
    """Information about a party (landlord/property manager)"""
    name: str = Field(..., min_length=2)
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = "MN"
    zip_code: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    attorney_name: Optional[str] = None
    attorney_bar_number: Optional[str] = None


class CaseInfo(BaseModel):
    """Case information from summons/complaint"""
    case_number: str = Field(..., min_length=5, description="Court case number")
    court_name: str = Field(default="Dakota County District Court")
    court_county: str = Field(default="Dakota")
    judicial_district: str = Field(default="First Judicial District")
    
    # Property info
    property_address: str = Field(..., min_length=5)
    property_city: str = Field(..., min_length=2)
    property_state: str = Field(default="MN")
    property_zip: str = Field(..., min_length=5)
    unit_number: Optional[str] = None
    
    # Landlord/Plaintiff
    landlord: PartyInfo
    
    # Key dates
    notice_date: Optional[str] = None
    notice_type: Optional[str] = None  # 14-day, 30-day, etc.
    summons_date: Optional[str] = None
    hearing_date: Optional[str] = None
    hearing_time: Optional[str] = None
    
    # Amounts
    rent_claimed: Optional[float] = None
    late_fees_claimed: Optional[float] = None
    other_fees_claimed: Optional[float] = None
    
    # Lease info
    monthly_rent: Optional[float] = None
    security_deposit: Optional[float] = None
    lease_start_date: Optional[str] = None
    lease_end_date: Optional[str] = None
    lease_type: Optional[str] = "month-to-month"


class StorageConfig(BaseModel):
    """Cloud storage configuration"""
    provider: str = Field(..., description="google_drive, onedrive, dropbox, or local")
    connected: bool = False
    folder_path: Optional[str] = None


class SetupProgress(BaseModel):
    """Track setup wizard progress"""
    current_step: int = 1
    total_steps: int = 7
    steps_completed: List[int] = []
    profile_complete: bool = False
    case_info_complete: bool = False
    storage_complete: bool = False
    documents_uploaded: bool = False
    documents_processed: bool = False
    review_complete: bool = False


class SetupStatus(BaseModel):
    """Overall setup status"""
    is_complete: bool = False
    progress: SetupProgress
    profile: Optional[dict] = None
    case_info: Optional[dict] = None
    storage: Optional[dict] = None
    documents_count: int = 0
    timeline_events_count: int = 0


# =============================================================================
# In-Memory Storage (will persist to DB)
# =============================================================================

# Temporary storage for setup data (per user)
_setup_data: dict = {}


def get_user_setup(user_id: str) -> dict:
    """Get or create setup data for user"""
    if user_id not in _setup_data:
        _setup_data[user_id] = {
            "progress": {
                "current_step": 1,
                "total_steps": 7,
                "steps_completed": [],
                "profile_complete": False,
                "case_info_complete": False,
                "storage_complete": False,
                "documents_uploaded": False,
                "documents_processed": False,
                "review_complete": False,
            },
            "profile": None,
            "case_info": None,
            "storage": {"provider": "local", "connected": True},
            "documents": [],
        }
    return _setup_data[user_id]


# =============================================================================
# Endpoints
# =============================================================================

@router.get("/check")
async def check_setup_needed():
    """
    Public endpoint - no auth required.
    Used by launcher to determine if setup wizard should be shown.
    Returns simple boolean for first-run detection.
    """
    # Check if any user has completed setup (simple file-based check)
    import os
    setup_marker = os.path.join(os.path.dirname(__file__), "..", "..", "data", ".setup_complete")

    return {
        "setup_complete": os.path.exists(setup_marker),
        "redirect": "/static/command_center.html" if os.path.exists(setup_marker) else "/static/setup_wizard.html"
    }


@router.post("/skip")
async def skip_setup():
    """
    Skip setup wizard (for development/demo mode).
    Creates the setup_complete marker without going through the wizard.
    """
    import os
    from datetime import datetime
    
    marker_path = os.path.join(os.path.dirname(__file__), "..", "..", "data", ".setup_complete")
    os.makedirs(os.path.dirname(marker_path), exist_ok=True)
    
    with open(marker_path, "w") as f:
        f.write(f"Setup skipped at {datetime.now().isoformat()}")
    
    return {
        "status": "skipped",
        "message": "Setup wizard skipped. You can configure later via settings.",
        "redirect": "/static/command_center.html"
    }


@router.post("/reset")
async def reset_setup():
    """
    Reset setup wizard (for development/testing).
    Removes the setup_complete marker to re-trigger the wizard.
    """
    import os
    
    marker_path = os.path.join(os.path.dirname(__file__), "..", "..", "data", ".setup_complete")
    
    if os.path.exists(marker_path):
        os.remove(marker_path)
        return {
            "status": "reset",
            "message": "Setup wizard will show again on next visit.",
            "redirect": "/static/setup_wizard.html"
        }
    
    return {
        "status": "already_reset",
        "message": "Setup was not completed.",
        "redirect": "/static/setup_wizard.html"
    }
@router.get("/status")
async def get_setup_status(
    user: StorageUser = Depends(require_user),
) -> SetupStatus:
    """
    Get current setup wizard status.
    
    Returns progress through the wizard and what's been completed.
    """
    setup = get_user_setup(user.user_id)
    
    # Count documents
    async with get_db_session() as session:
        result = await session.execute(
            select(Document).where(Document.user_id == user.user_id)
        )
        docs = result.scalars().all()
    
    return SetupStatus(
        is_complete=setup["progress"]["review_complete"],
        progress=SetupProgress(**setup["progress"]),
        profile=setup["profile"],
        case_info=setup["case_info"],
        storage=setup["storage"],
        documents_count=len(docs),
        timeline_events_count=0,  # Will count from DB
    )


@router.post("/profile")
async def save_profile(
    profile: UserProfile,
    user: StorageUser = Depends(require_user),
):
    """
    Step 2: Save user profile information.
    
    This is the tenant's personal information that will appear on court forms.
    """
    setup = get_user_setup(user.user_id)
    setup["profile"] = profile.model_dump()
    setup["progress"]["profile_complete"] = True
    
    if 2 not in setup["progress"]["steps_completed"]:
        setup["progress"]["steps_completed"].append(2)
    
    # Update Form Data Hub
    from app.services.form_data import get_form_data_service
    service = get_form_data_service(user.user_id)
    await service.load()
    service.update_case_info({
        "tenant": {
            "name": profile.full_name,
            "address": profile.address,
            "city": profile.city,
            "state": profile.state,
            "zip_code": profile.zip_code,
            "phone": profile.phone or "",
            "email": profile.email or "",
        }
    })
    
    return {
        "status": "saved",
        "message": "Profile saved successfully",
        "next_step": 3,
    }


@router.get("/profile")
async def get_profile(
    user: StorageUser = Depends(require_user),
):
    """Get saved profile information."""
    setup = get_user_setup(user.user_id)
    return {
        "profile": setup["profile"],
        "complete": setup["progress"]["profile_complete"],
    }


@router.post("/case")
async def save_case_info(
    case_info: CaseInfo,
    user: StorageUser = Depends(require_user),
):
    """
    Step 3: Save case information.
    
    Information from the summons and complaint documents.
    This data populates all court forms.
    """
    setup = get_user_setup(user.user_id)
    setup["case_info"] = case_info.model_dump()
    setup["progress"]["case_info_complete"] = True
    
    if 3 not in setup["progress"]["steps_completed"]:
        setup["progress"]["steps_completed"].append(3)
    
    # Calculate answer deadline (7 days from summons for eviction)
    answer_deadline = None
    if case_info.summons_date:
        try:
            summons = datetime.strptime(case_info.summons_date, "%Y-%m-%d")
            answer_deadline = (summons + timedelta(days=7)).strftime("%Y-%m-%d")
        except:
            pass
    
    # Update Form Data Hub
    from app.services.form_data import get_form_data_service
    service = get_form_data_service(user.user_id)
    await service.load()
    
    update_data = {
        "case_number": case_info.case_number,
        "court_name": case_info.court_name,
        "county": case_info.court_county,
        "judicial_district": case_info.judicial_district,
        "property_address": case_info.property_address,
        "property_city": case_info.property_city,
        "property_state": case_info.property_state,
        "property_zip": case_info.property_zip,
        "unit_number": case_info.unit_number or "",
        "notice_date": case_info.notice_date or "",
        "notice_type": case_info.notice_type or "",
        "summons_date": case_info.summons_date or "",
        "answer_deadline": answer_deadline or "",
        "hearing_date": case_info.hearing_date or "",
        "hearing_time": case_info.hearing_time or "",
        "rent_claimed": case_info.rent_claimed or 0,
        "late_fees_claimed": case_info.late_fees_claimed or 0,
        "other_fees_claimed": case_info.other_fees_claimed or 0,
        "monthly_rent": case_info.monthly_rent or 0,
        "security_deposit": case_info.security_deposit or 0,
        "lease_start_date": case_info.lease_start_date or "",
        "lease_end_date": case_info.lease_end_date or "",
        "lease_type": case_info.lease_type or "month-to-month",
        "landlord": case_info.landlord.model_dump() if case_info.landlord else {},
    }
    service.update_case_info(update_data)
    
    # Create calendar events for deadlines
    await _create_deadline_events(user.user_id, case_info, answer_deadline)
    
    return {
        "status": "saved",
        "message": "Case information saved successfully",
        "answer_deadline": answer_deadline,
        "next_step": 4,
    }


@router.get("/case")
async def get_case_info(
    user: StorageUser = Depends(require_user),
):
    """Get saved case information."""
    setup = get_user_setup(user.user_id)
    return {
        "case_info": setup["case_info"],
        "complete": setup["progress"]["case_info_complete"],
    }


@router.post("/storage")
async def configure_storage(
    config: StorageConfig,
    user: StorageUser = Depends(require_user),
):
    """
    Step 4: Configure document storage.
    
    Choose where to store your case documents:
    - local: Store on this server (default)
    - google_drive: Connect Google Drive
    - onedrive: Connect Microsoft OneDrive
    - dropbox: Connect Dropbox
    """
    setup = get_user_setup(user.user_id)
    setup["storage"] = config.model_dump()
    setup["progress"]["storage_complete"] = True
    
    if 4 not in setup["progress"]["steps_completed"]:
        setup["progress"]["steps_completed"].append(4)
    
    # If cloud provider, return OAuth URL
    oauth_url = None
    if config.provider != "local":
        oauth_url = f"/storage/auth/{config.provider}"
    
    return {
        "status": "configured",
        "provider": config.provider,
        "oauth_url": oauth_url,
        "next_step": 5,
    }


@router.get("/storage")
async def get_storage_config(
    user: StorageUser = Depends(require_user),
):
    """Get storage configuration."""
    setup = get_user_setup(user.user_id)
    return {
        "storage": setup["storage"],
        "complete": setup["progress"]["storage_complete"],
    }


@router.post("/documents/upload")
async def upload_document(
    file: UploadFile = File(...),
    document_type: str = Form(default="other"),
    description: str = Form(default=""),
    user: StorageUser = Depends(require_user),
):
    """
    Step 5: Upload a case document.
    
    Supported document types:
    - summons: Court summons
    - complaint: Eviction complaint
    - notice: Eviction notice (14-day, 30-day, etc.)
    - lease: Rental agreement/lease
    - payment: Rent payment records
    - communication: Emails, letters, texts
    - photo: Property condition photos
    - other: Other evidence
    
    Documents are automatically processed to extract:
    - Dates (for timeline)
    - Amounts (for forms)
    - Party names
    """
    import hashlib
    import os
    from pathlib import Path
    
    setup = get_user_setup(user.user_id)
    
    # Read file content
    content = await file.read()
    file_hash = hashlib.sha256(content).hexdigest()
    
    # Create vault directory
    vault_dir = Path(f"uploads/vault/{user.user_id}")
    vault_dir.mkdir(parents=True, exist_ok=True)
    
    # Save file
    safe_filename = f"{file_hash[:8]}_{file.filename}"
    file_path = vault_dir / safe_filename
    
    with open(file_path, "wb") as f:
        f.write(content)
    
    # Save to database
    async with get_db_session() as session:
        doc = Document(
            user_id=user.user_id,
            filename=safe_filename,
            original_filename=file.filename,
            file_path=str(file_path),
            file_size=len(content),
            mime_type=file.content_type or "application/octet-stream",
            sha256_hash=file_hash,
            document_type=document_type,
            description=description,
        )
        session.add(doc)
        await session.commit()
        await session.refresh(doc)
        doc_id = doc.id
    
    # Update setup progress
    setup["progress"]["documents_uploaded"] = True
    if 5 not in setup["progress"]["steps_completed"]:
        setup["progress"]["steps_completed"].append(5)
    
    # Process document to extract data
    extracted = await _process_document(user.user_id, doc_id, document_type, content, file.filename)
    
    return {
        "status": "uploaded",
        "document_id": doc_id,
        "filename": file.filename,
        "document_type": document_type,
        "hash": file_hash,
        "extracted_data": extracted,
        "message": f"Document '{file.filename}' uploaded and processed",
    }


@router.get("/documents")
async def get_uploaded_documents(
    user: StorageUser = Depends(require_user),
):
    """Get list of uploaded documents."""
    async with get_db_session() as session:
        result = await session.execute(
            select(Document).where(Document.user_id == user.user_id)
        )
        docs = result.scalars().all()
    
    return {
        "documents": [
            {
                "id": doc.id,
                "filename": doc.original_filename,
                "type": doc.document_type,
                "size": doc.file_size,
                "uploaded_at": doc.uploaded_at.isoformat() if doc.uploaded_at else None,
            }
            for doc in docs
        ],
        "count": len(docs),
    }


@router.post("/documents/process")
async def process_all_documents(
    user: StorageUser = Depends(require_user),
):
    """
    Step 6: Process all uploaded documents.
    
    Extracts data from all documents and updates:
    - Form Data Hub
    - Timeline
    - Calendar
    """
    setup = get_user_setup(user.user_id)
    
    async with get_db_session() as session:
        result = await session.execute(
            select(Document).where(Document.user_id == user.user_id)
        )
        docs = result.scalars().all()
    
    processed = []
    for doc in docs:
        # Read file and process
        try:
            with open(doc.file_path, "rb") as f:
                content = f.read()
            extracted = await _process_document(
                user.user_id, doc.id, doc.document_type, content, doc.original_filename
            )
            processed.append({
                "document_id": doc.id,
                "filename": doc.original_filename,
                "extracted": extracted,
            })
        except Exception as e:
            processed.append({
                "document_id": doc.id,
                "filename": doc.original_filename,
                "error": str(e),
            })
    
    setup["progress"]["documents_processed"] = True
    if 6 not in setup["progress"]["steps_completed"]:
        setup["progress"]["steps_completed"].append(6)
    
    return {
        "status": "processed",
        "documents_processed": len(processed),
        "results": processed,
        "next_step": 7,
    }


@router.post("/complete")
async def complete_setup(
    user: StorageUser = Depends(require_user),
):
    """
    Step 7: Complete setup wizard.
    
    Marks setup as complete and redirects to command center.
    """
    setup = get_user_setup(user.user_id)
    
    # Verify all required steps
    required = ["profile_complete", "case_info_complete"]
    missing = [step for step in required if not setup["progress"].get(step)]
    
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot complete setup. Missing: {missing}"
        )
    
    setup["progress"]["review_complete"] = True
    if 7 not in setup["progress"]["steps_completed"]:
        setup["progress"]["steps_completed"].append(7)
    
    # Get summary
    from app.services.form_data import get_form_data_service
    service = get_form_data_service(user.user_id)
    await service.load()
    summary = service.get_case_summary()

    # Create setup complete marker file
    import os
    marker_path = os.path.join(os.path.dirname(__file__), "..", "..", "data", ".setup_complete")
    os.makedirs(os.path.dirname(marker_path), exist_ok=True)
    with open(marker_path, "w") as f:
        f.write(f"Setup completed by user {user.user_id} at {datetime.now().isoformat()}")

    return {
        "status": "complete",
        "message": "Setup complete! Your case is ready.",
        "redirect": "/static/command_center.html",
        "case_summary": summary,
    }
@router.get("/summary")
async def get_setup_summary(
    user: StorageUser = Depends(require_user),
):
    """
    Get complete summary of all setup data.
    
    Used by Step 7 (Review) to show everything before completion.
    """
    setup = get_user_setup(user.user_id)
    
    # Get documents
    async with get_db_session() as session:
        result = await session.execute(
            select(Document).where(Document.user_id == user.user_id)
        )
        docs = result.scalars().all()
    
    # Get form data
    from app.services.form_data import get_form_data_service
    service = get_form_data_service(user.user_id)
    await service.load()
    
    return {
        "profile": setup["profile"],
        "case_info": setup["case_info"],
        "storage": setup["storage"],
        "documents": [
            {
                "id": doc.id,
                "filename": doc.original_filename,
                "type": doc.document_type,
            }
            for doc in docs
        ],
        "form_data_summary": service.get_case_summary(),
        "progress": setup["progress"],
    }


# =============================================================================
# Helper Functions
# =============================================================================

async def _process_document(
    user_id: str,
    doc_id: int,
    doc_type: str,
    content: bytes,
    filename: str,
) -> dict:
    """
    Process a document to extract data.
    
    Returns extracted dates, amounts, and other relevant information.
    """
    import re
    
    extracted = {
        "dates": [],
        "amounts": [],
        "parties": [],
        "case_numbers": [],
    }
    
    # Try to extract text (for PDFs, we'd need OCR)
    try:
        text = content.decode("utf-8", errors="ignore")
    except:
        text = ""
    
    # Extract dates (various formats)
    date_patterns = [
        r'\b(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})\b',  # MM/DD/YYYY or MM-DD-YYYY
        r'\b(\w+)\s+(\d{1,2}),?\s+(\d{4})\b',  # Month DD, YYYY
        r'\b(\d{4})[/-](\d{1,2})[/-](\d{1,2})\b',  # YYYY-MM-DD
    ]
    
    for pattern in date_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for match in matches:
            extracted["dates"].append("".join(match))
    
    # Extract amounts (money)
    amount_pattern = r'\$[\d,]+\.?\d*'
    amounts = re.findall(amount_pattern, text)
    extracted["amounts"] = amounts[:10]  # Limit to 10
    
    # Extract case numbers
    case_pattern = r'\b\d{2}[A-Z]{2}-[A-Z]{2}-\d{2}-\d+\b'
    cases = re.findall(case_pattern, text)
    extracted["case_numbers"] = cases
    
    # Create timeline event based on document type
    from app.models.models import TimelineEvent
    from app.core.database import get_db_session
    
    event_title = {
        "summons": "Summons Received",
        "complaint": "Complaint Filed",
        "notice": "Notice Received",
        "lease": "Lease Document",
        "payment": "Payment Record",
        "communication": "Communication",
        "photo": "Photo Evidence",
    }.get(doc_type, f"Document: {filename}")
    
    async with get_db_session() as session:
        event = TimelineEvent(
            user_id=user_id,
            event_type="document",
            title=event_title,
            description=f"Uploaded: {filename}",
            document_id=doc_id,
            is_evidence=doc_type in ["summons", "complaint", "notice", "lease", "payment", "photo"],
        )
        session.add(event)
        await session.commit()
    
    # Update Form Data Hub with extracted data
    from app.services.form_data import get_form_data_service
    service = get_form_data_service(user_id)
    await service.load()
    
    # Add extracted dates
    for date in extracted["dates"][:5]:
        service.form_data.extracted_dates.append({
            "date": date,
            "source": filename,
            "type": doc_type,
        })
    
    # Add extracted amounts
    for amount in extracted["amounts"][:5]:
        service.form_data.extracted_amounts.append({
            "amount": amount,
            "source": filename,
            "type": doc_type,
        })
    
    return extracted


async def _create_deadline_events(
    user_id: str,
    case_info: CaseInfo,
    answer_deadline: Optional[str],
):
    """Create calendar events for case deadlines."""
    from app.models.models import CalendarEvent
    from app.core.database import get_db_session
    
    events_to_create = []
    
    # Answer deadline
    if answer_deadline:
        events_to_create.append({
            "title": "⚠️ ANSWER DEADLINE",
            "description": f"File your Answer to Eviction Complaint by end of day. Case: {case_info.case_number}",
            "event_date": answer_deadline,
            "event_type": "deadline",
            "is_critical": True,
        })
    
    # Hearing date
    if case_info.hearing_date:
        time_str = case_info.hearing_time or "TBD"
        events_to_create.append({
            "title": "🏛️ COURT HEARING",
            "description": f"Eviction hearing at {case_info.court_name}. Time: {time_str}. Case: {case_info.case_number}",
            "event_date": case_info.hearing_date,
            "event_type": "hearing",
            "is_critical": True,
        })
    
    # Create events in database
    async with get_db_session() as session:
        for event_data in events_to_create:
            # Check if event already exists
            result = await session.execute(
                select(CalendarEvent).where(
                    CalendarEvent.user_id == user_id,
                    CalendarEvent.title == event_data["title"],
                )
            )
            existing = result.scalar_one_or_none()
            
            if not existing:
                event = CalendarEvent(
                    user_id=user_id,
                    title=event_data["title"],
                    description=event_data["description"],
                    event_date=datetime.strptime(event_data["event_date"], "%Y-%m-%d"),
                    event_type=event_data["event_type"],
                )
                session.add(event)
        
        await session.commit()
