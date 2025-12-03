"""
Document Intake API Router

Provides endpoints for:
- Document upload and intake
- Processing status tracking
- Extraction results retrieval
- Issue detection results
- Batch processing
"""

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, Query
from pydantic import BaseModel, Field
from typing import Optional

from app.services.document_intake import (
    get_intake_engine,
    DocumentType,
    IntakeStatus,
    IssueSeverity,
    LanguageCode,
)


router = APIRouter(prefix="/api/intake", tags=["Document Intake"])


# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class IntakeStatusResponse(BaseModel):
    """Processing status response."""
    id: str
    status: str
    status_message: str
    progress_percent: int


class ExtractedDateResponse(BaseModel):
    """Extracted date response."""
    date: str
    label: str
    confidence: float
    source_text: str
    is_deadline: bool
    days_until: Optional[int] = None


class ExtractedPartyResponse(BaseModel):
    """Extracted party response."""
    name: str
    role: str
    address: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    confidence: float


class ExtractedAmountResponse(BaseModel):
    """Extracted amount response."""
    amount: float
    label: str
    currency: str
    period: Optional[str] = None
    confidence: float
    source_text: str


class DetectedIssueResponse(BaseModel):
    """Detected issue response."""
    issue_id: str
    severity: str
    title: str
    description: str
    affected_text: Optional[str] = None
    legal_basis: Optional[str] = None
    recommended_action: Optional[str] = None
    deadline: Optional[str] = None
    related_laws: list[str] = []


class ExtractionResultResponse(BaseModel):
    """Complete extraction result response."""
    doc_type: str
    doc_type_confidence: float
    language: str
    page_count: int
    word_count: int
    summary: str
    key_points: list[str]
    dates: list[ExtractedDateResponse]
    parties: list[ExtractedPartyResponse]
    amounts: list[ExtractedAmountResponse]
    issues: list[DetectedIssueResponse]
    extracted_at: str


class IntakeDocumentResponse(BaseModel):
    """Complete intake document response."""
    id: str
    user_id: str
    filename: str
    file_hash: str
    file_size: int
    mime_type: str
    status: str
    status_message: str
    progress_percent: int
    extraction: Optional[ExtractionResultResponse] = None
    uploaded_at: str
    processed_at: Optional[str] = None


class UploadResponse(BaseModel):
    """Upload response."""
    id: str
    filename: str
    status: str
    message: str


class BatchUploadResponse(BaseModel):
    """Batch upload response."""
    uploaded: list[UploadResponse]
    failed: list[dict]
    total_uploaded: int
    total_failed: int


# =============================================================================
# UPLOAD ENDPOINTS
# =============================================================================

@router.post("/upload", response_model=UploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    user_id: str = Form(..., description="User ID for the document owner"),
):
    """
    Upload a document for intake processing.
    
    The document will be:
    1. Received and validated
    2. Hashed for integrity
    3. Queued for processing
    
    Use the returned ID to check processing status.
    """
    engine = get_intake_engine()
    
    # Read file content
    content = await file.read()
    
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="Empty file")
    
    if len(content) > 25 * 1024 * 1024:  # 25MB limit
        raise HTTPException(status_code=400, detail="File too large (max 25MB)")
    
    # Intake the document
    doc = await engine.intake_document(
        user_id=user_id,
        file_content=content,
        filename=file.filename or "unknown",
        mime_type=file.content_type or "application/octet-stream",
    )
    
    return UploadResponse(
        id=doc.id,
        filename=doc.filename,
        status=doc.status.value,
        message="Document received. Use /process/{id} to begin processing.",
    )


@router.post("/upload/batch", response_model=BatchUploadResponse)
async def upload_documents_batch(
    files: list[UploadFile] = File(...),
    user_id: str = Form(...),
):
    """
    Upload multiple documents at once.
    
    Returns status for each file.
    """
    engine = get_intake_engine()
    
    uploaded = []
    failed = []
    
    for file in files:
        try:
            content = await file.read()
            
            if len(content) == 0:
                failed.append({"filename": file.filename, "error": "Empty file"})
                continue
            
            if len(content) > 25 * 1024 * 1024:
                failed.append({"filename": file.filename, "error": "File too large"})
                continue
            
            doc = await engine.intake_document(
                user_id=user_id,
                file_content=content,
                filename=file.filename or "unknown",
                mime_type=file.content_type or "application/octet-stream",
            )
            
            uploaded.append(UploadResponse(
                id=doc.id,
                filename=doc.filename,
                status=doc.status.value,
                message="Document received",
            ))
            
        except Exception as e:
            failed.append({"filename": file.filename, "error": str(e)})
    
    return BatchUploadResponse(
        uploaded=uploaded,
        failed=failed,
        total_uploaded=len(uploaded),
        total_failed=len(failed),
    )


# =============================================================================
# PROCESSING ENDPOINTS
# =============================================================================

@router.post("/process/{doc_id}", response_model=IntakeDocumentResponse)
async def process_document(doc_id: str):
    """
    Process an uploaded document.
    
    This runs the full pipeline:
    1. Validation
    2. Text extraction
    3. Content analysis
    4. Issue detection
    5. Context enrichment
    
    Returns the complete extraction result.
    """
    engine = get_intake_engine()
    
    doc = engine.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    if doc.status == IntakeStatus.COMPLETE:
        # Already processed, return existing result
        return _doc_to_response(doc)
    
    try:
        doc = await engine.process_document(doc_id)
        return _doc_to_response(doc)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")


@router.get("/status/{doc_id}", response_model=IntakeStatusResponse)
async def get_processing_status(doc_id: str):
    """
    Get the current processing status of a document.
    
    Use this to poll for completion during async processing.
    """
    engine = get_intake_engine()
    status = engine.get_processing_status(doc_id)
    
    if "error" in status:
        raise HTTPException(status_code=404, detail=status["error"])
    
    return IntakeStatusResponse(**status)


# =============================================================================
# RETRIEVAL ENDPOINTS
# =============================================================================

@router.get("/documents", response_model=list[IntakeDocumentResponse])
async def list_documents(
    user_id: str = Query(..., description="User ID to list documents for"),
    status: Optional[str] = Query(None, description="Filter by status"),
):
    """
    List all documents for a user.
    
    Optionally filter by processing status.
    """
    engine = get_intake_engine()
    docs = engine.get_user_documents(user_id)
    
    if status:
        try:
            status_filter = IntakeStatus(status)
            docs = [d for d in docs if d.status == status_filter]
        except ValueError:
            pass
    
    return [_doc_to_response(d) for d in docs]


@router.get("/documents/{doc_id}", response_model=IntakeDocumentResponse)
async def get_document(doc_id: str):
    """
    Get a specific document with all extraction results.
    """
    engine = get_intake_engine()
    doc = engine.get_document(doc_id)
    
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    return _doc_to_response(doc)


@router.get("/documents/{doc_id}/issues", response_model=list[DetectedIssueResponse])
async def get_document_issues(doc_id: str):
    """
    Get only the detected issues for a document.
    
    Useful for displaying alerts/warnings to the user.
    """
    engine = get_intake_engine()
    doc = engine.get_document(doc_id)
    
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    if not doc.extraction:
        raise HTTPException(status_code=400, detail="Document not yet processed")
    
    return [
        DetectedIssueResponse(
            issue_id=i.issue_id,
            severity=i.severity.value,
            title=i.title,
            description=i.description,
            affected_text=i.affected_text,
            legal_basis=i.legal_basis,
            recommended_action=i.recommended_action,
            deadline=i.deadline.isoformat() if i.deadline else None,
            related_laws=i.related_laws,
        )
        for i in doc.extraction.issues
    ]


@router.get("/documents/{doc_id}/dates", response_model=list[ExtractedDateResponse])
async def get_document_dates(doc_id: str):
    """
    Get only the extracted dates for a document.
    
    Includes deadline detection and days-until calculation.
    """
    engine = get_intake_engine()
    doc = engine.get_document(doc_id)
    
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    if not doc.extraction:
        raise HTTPException(status_code=400, detail="Document not yet processed")
    
    return [
        ExtractedDateResponse(
            date=d.date.isoformat(),
            label=d.label,
            confidence=d.confidence,
            source_text=d.source_text,
            is_deadline=d.is_deadline,
            days_until=d.days_until,
        )
        for d in doc.extraction.dates
    ]


@router.get("/documents/{doc_id}/amounts", response_model=list[ExtractedAmountResponse])
async def get_document_amounts(doc_id: str):
    """
    Get only the extracted monetary amounts for a document.
    """
    engine = get_intake_engine()
    doc = engine.get_document(doc_id)
    
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    if not doc.extraction:
        raise HTTPException(status_code=400, detail="Document not yet processed")
    
    return [
        ExtractedAmountResponse(
            amount=a.amount,
            label=a.label,
            currency=a.currency,
            period=a.period,
            confidence=a.confidence,
            source_text=a.source_text,
        )
        for a in doc.extraction.amounts
    ]


@router.get("/documents/{doc_id}/parties", response_model=list[ExtractedPartyResponse])
async def get_document_parties(doc_id: str):
    """
    Get only the extracted parties for a document.
    """
    engine = get_intake_engine()
    doc = engine.get_document(doc_id)
    
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    if not doc.extraction:
        raise HTTPException(status_code=400, detail="Document not yet processed")
    
    return [
        ExtractedPartyResponse(
            name=p.name,
            role=p.role,
            address=p.address,
            phone=p.phone,
            email=p.email,
            confidence=p.confidence,
        )
        for p in doc.extraction.parties
    ]


@router.get("/documents/{doc_id}/text")
async def get_document_text(doc_id: str):
    """
    Get the full extracted text for a document.
    """
    engine = get_intake_engine()
    doc = engine.get_document(doc_id)
    
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    if not doc.extraction:
        raise HTTPException(status_code=400, detail="Document not yet processed")
    
    return {
        "id": doc_id,
        "filename": doc.filename,
        "text": doc.extraction.full_text,
        "word_count": doc.extraction.word_count,
        "language": doc.extraction.language.value,
    }


# =============================================================================
# ANALYSIS ENDPOINTS
# =============================================================================

@router.get("/issues/critical")
async def get_critical_issues(user_id: str = Query(...)):
    """
    Get all CRITICAL issues across all user's documents.
    
    These require immediate attention.
    """
    engine = get_intake_engine()
    docs = engine.get_user_documents(user_id)
    
    critical_issues = []
    for doc in docs:
        if doc.extraction:
            for issue in doc.extraction.issues:
                if issue.severity == IssueSeverity.CRITICAL:
                    critical_issues.append({
                        "document_id": doc.id,
                        "document_name": doc.filename,
                        "issue": DetectedIssueResponse(
                            issue_id=issue.issue_id,
                            severity=issue.severity.value,
                            title=issue.title,
                            description=issue.description,
                            affected_text=issue.affected_text,
                            legal_basis=issue.legal_basis,
                            recommended_action=issue.recommended_action,
                            deadline=issue.deadline.isoformat() if issue.deadline else None,
                            related_laws=issue.related_laws,
                        ),
                    })
    
    return {
        "total_critical": len(critical_issues),
        "issues": critical_issues,
    }


@router.get("/deadlines/upcoming")
async def get_upcoming_deadlines(
    user_id: str = Query(...),
    days: int = Query(14, description="Number of days to look ahead"),
):
    """
    Get all upcoming deadlines across user's documents.
    """
    engine = get_intake_engine()
    docs = engine.get_user_documents(user_id)
    
    deadlines = []
    for doc in docs:
        if doc.extraction:
            for date in doc.extraction.dates:
                if date.is_deadline and date.days_until is not None:
                    if 0 <= date.days_until <= days:
                        deadlines.append({
                            "document_id": doc.id,
                            "document_name": doc.filename,
                            "date": date.date.isoformat(),
                            "label": date.label,
                            "days_until": date.days_until,
                            "source_text": date.source_text,
                        })
    
    # Sort by days until deadline
    deadlines.sort(key=lambda x: x["days_until"])
    
    return {
        "total_deadlines": len(deadlines),
        "deadlines": deadlines,
    }


@router.get("/summary")
async def get_user_intake_summary(user_id: str = Query(...)):
    """
    Get a summary of all intake documents for a user.
    """
    engine = get_intake_engine()
    docs = engine.get_user_documents(user_id)
    
    by_status = {}
    by_type = {}
    total_issues = 0
    critical_issues = 0
    
    for doc in docs:
        # Count by status
        status = doc.status.value
        by_status[status] = by_status.get(status, 0) + 1
        
        # Count by type and issues
        if doc.extraction:
            doc_type = doc.extraction.doc_type.value
            by_type[doc_type] = by_type.get(doc_type, 0) + 1
            
            total_issues += len(doc.extraction.issues)
            critical_issues += sum(
                1 for i in doc.extraction.issues 
                if i.severity == IssueSeverity.CRITICAL
            )
    
    return {
        "total_documents": len(docs),
        "by_status": by_status,
        "by_type": by_type,
        "total_issues_detected": total_issues,
        "critical_issues": critical_issues,
    }


# =============================================================================
# ENUM ENDPOINTS (for frontend)
# =============================================================================

@router.get("/enums/document-types")
async def get_document_types():
    """Get all document types."""
    return [{"value": t.value, "name": t.name} for t in DocumentType]


@router.get("/enums/intake-statuses")
async def get_intake_statuses():
    """Get all intake statuses."""
    return [{"value": s.value, "name": s.name} for s in IntakeStatus]


@router.get("/enums/issue-severities")
async def get_issue_severities():
    """Get all issue severity levels."""
    return [{"value": s.value, "name": s.name} for s in IssueSeverity]


@router.get("/enums/languages")
async def get_languages():
    """Get supported languages."""
    return [{"value": l.value, "name": l.name} for l in LanguageCode]


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def _doc_to_response(doc) -> IntakeDocumentResponse:
    """Convert IntakeDocument to response model."""
    extraction_response = None
    
    if doc.extraction:
        ext = doc.extraction
        extraction_response = ExtractionResultResponse(
            doc_type=ext.doc_type.value,
            doc_type_confidence=ext.doc_type_confidence,
            language=ext.language.value,
            page_count=ext.page_count,
            word_count=ext.word_count,
            summary=ext.summary,
            key_points=ext.key_points,
            dates=[
                ExtractedDateResponse(
                    date=d.date.isoformat(),
                    label=d.label,
                    confidence=d.confidence,
                    source_text=d.source_text,
                    is_deadline=d.is_deadline,
                    days_until=d.days_until,
                )
                for d in ext.dates
            ],
            parties=[
                ExtractedPartyResponse(
                    name=p.name,
                    role=p.role,
                    address=p.address,
                    phone=p.phone,
                    email=p.email,
                    confidence=p.confidence,
                )
                for p in ext.parties
            ],
            amounts=[
                ExtractedAmountResponse(
                    amount=a.amount,
                    label=a.label,
                    currency=a.currency,
                    period=a.period,
                    confidence=a.confidence,
                    source_text=a.source_text,
                )
                for a in ext.amounts
            ],
            issues=[
                DetectedIssueResponse(
                    issue_id=i.issue_id,
                    severity=i.severity.value,
                    title=i.title,
                    description=i.description,
                    affected_text=i.affected_text,
                    legal_basis=i.legal_basis,
                    recommended_action=i.recommended_action,
                    deadline=i.deadline.isoformat() if i.deadline else None,
                    related_laws=i.related_laws,
                )
                for i in ext.issues
            ],
            extracted_at=ext.extracted_at.isoformat(),
        )
    
    return IntakeDocumentResponse(
        id=doc.id,
        user_id=doc.user_id,
        filename=doc.filename,
        file_hash=doc.file_hash,
        file_size=doc.file_size,
        mime_type=doc.mime_type,
        status=doc.status.value,
        status_message=doc.status_message,
        progress_percent=doc.progress_percent,
        extraction=extraction_response,
        uploaded_at=doc.uploaded_at.isoformat(),
        processed_at=doc.processed_at.isoformat() if doc.processed_at else None,
    )
