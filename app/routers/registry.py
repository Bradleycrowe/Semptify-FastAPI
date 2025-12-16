"""
Document Registry API Router

Provides endpoints for:
- Document registration with unique IDs
- Integrity verification
- Duplicate detection
- Case association
- Forgery flagging
- Chain of custody tracking
"""

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, Query, Request
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

from app.core.security import get_optional_user_id
from app.services.document_registry import (
    get_document_registry,
    DocumentStatus,
    IntegrityStatus,
    ForgeryIndicator,
    CustodyAction,
    RegisteredDocument,
    CustodyRecord,
    ForgeryAlert,
)


router = APIRouter(prefix="/api/registry", tags=["Document Registry"])


# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class CustodyRecordResponse(BaseModel):
    """Custody chain record response."""
    timestamp: str
    action: str
    actor: str
    details: str
    ip_address: Optional[str] = None
    integrity_hash: Optional[str] = None


class ForgeryAlertResponse(BaseModel):
    """Forgery alert response."""
    indicator: str
    severity: str
    description: str
    affected_area: Optional[str] = None
    evidence: Optional[str] = None
    detected_at: str


class DocumentRegistrationResponse(BaseModel):
    """Response after document registration."""
    document_id: str
    status: str
    is_duplicate: bool
    original_document_id: Optional[str] = None
    content_hash: str
    integrity_status: str
    forgery_score: float
    forgery_alerts: list[ForgeryAlertResponse]
    requires_review: bool
    registered_at: str
    message: str


class RegisteredDocumentResponse(BaseModel):
    """Full registered document response."""
    document_id: str
    user_id: str
    case_number: Optional[str] = None
    original_filename: str
    file_size: int
    mime_type: str
    content_hash: str
    metadata_hash: str
    combined_hash: str
    status: str
    integrity_status: str
    is_duplicate: bool
    original_document_id: Optional[str] = None
    duplicate_count: int
    forgery_alerts: list[ForgeryAlertResponse]
    forgery_score: float
    requires_review: bool
    registered_at: str
    last_verified_at: Optional[str] = None
    last_accessed_at: Optional[str] = None
    custody_chain: list[CustodyRecordResponse]
    intake_document_id: Optional[str] = None


class VerificationResponse(BaseModel):
    """Integrity verification response."""
    document_id: str
    status: str
    verified: bool
    message: str
    timestamp: str


class FlagDocumentRequest(BaseModel):
    """Request to flag a document."""
    reason: str
    indicator: Optional[str] = None


class AssociateCaseRequest(BaseModel):
    """Request to associate document with case."""
    case_number: str


class RegistryStatsResponse(BaseModel):
    """Registry statistics response."""
    total_documents: int
    total_cases: int
    total_users: int
    by_status: dict
    flagged_count: int
    duplicate_count: int


# =============================================================================
# REGISTRATION ENDPOINTS
# =============================================================================

@router.post("/register", response_model=DocumentRegistrationResponse)
async def register_document(
    request: Request,
    file: UploadFile = File(...),
    user_id: str = Form(..., description="User ID"),
    case_number: Optional[str] = Form(None, description="Case number to associate"),
    intake_document_id: Optional[str] = Form(None, description="Linked intake document ID"),
):
    """
    Register a new document in the system.
    
    Returns:
    - Unique SEMPTIFY document ID (SEM-YYYY-NNNNNN-XXXX)
    - Content hash for tamper detection
    - Duplicate detection results
    - Forgery analysis results
    - Initial custody record
    """
    registry = get_document_registry()
    
    # Read file content
    content = await file.read()
    
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="Empty file")
    
    if len(content) > 50 * 1024 * 1024:  # 50MB limit
        raise HTTPException(status_code=400, detail="File too large (max 50MB)")
    
    # Get client info for custody chain
    ip_address = request.client.host if request.client else None
    device_info = request.headers.get("User-Agent", "")[:200]
    
    # Register the document
    doc = registry.register_document(
        user_id=user_id,
        content=content,
        filename=file.filename or "unknown",
        mime_type=file.content_type or "application/octet-stream",
        case_number=case_number,
        intake_document_id=intake_document_id,
        ip_address=ip_address,
        device_info=device_info,
    )
    
    # Build message based on results
    messages = []
    messages.append(f"Document registered with ID: {doc.document_id}")
    
    if doc.is_duplicate:
        messages.append(f"⚠️ DUPLICATE: This is a copy of document {doc.original_document_id}")
    
    if doc.forgery_score > 0.7:
        messages.append("🚨 HIGH FORGERY RISK: Document quarantined for review")
    elif doc.forgery_score > 0.3:
        messages.append("⚠️ FORGERY INDICATORS DETECTED: Flagged for review")
    elif doc.forgery_alerts:
        messages.append("ℹ️ Minor concerns detected - see alerts")
    
    return DocumentRegistrationResponse(
        document_id=doc.document_id,
        status=doc.status.value,
        is_duplicate=doc.is_duplicate,
        original_document_id=doc.original_document_id,
        content_hash=doc.content_hash,
        integrity_status=doc.integrity_status.value,
        forgery_score=doc.forgery_score,
        forgery_alerts=[
            ForgeryAlertResponse(
                indicator=a.indicator.value,
                severity=a.severity,
                description=a.description,
                affected_area=a.affected_area,
                evidence=a.evidence,
                detected_at=a.detected_at.isoformat(),
            )
            for a in doc.forgery_alerts
        ],
        requires_review=doc.requires_review,
        registered_at=doc.registered_at.isoformat(),
        message=" | ".join(messages),
    )


# =============================================================================
# RETRIEVAL ENDPOINTS
# =============================================================================

@router.get("/documents/{doc_id}", response_model=RegisteredDocumentResponse)
async def get_document(doc_id: str, request: Request):
    """Get a registered document by its ID."""
    registry = get_document_registry()
    
    doc = registry.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail=f"Document {doc_id} not found")
    
    # Record access
    ip_address = request.client.host if request.client else None
    registry.record_access(
        doc_id=doc_id,
        actor="api_user",
        action=CustodyAction.ACCESSED,
        details="Document retrieved via API",
        ip_address=ip_address,
    )
    
    return _doc_to_response(doc)


@router.get("/documents", response_model=list[RegisteredDocumentResponse])
async def list_documents(
    user_id: Optional[str] = Depends(get_optional_user_id),
    case_number: Optional[str] = Query(None, description="Filter by case number"),
    status: Optional[str] = Query(None, description="Filter by status"),
):
    """List registered documents with optional filters."""
    registry = get_document_registry()
    
    if case_number:
        docs = registry.get_documents_by_case(case_number)
    elif user_id:
        docs = registry.get_documents_by_user(user_id)
    else:
        docs = list(registry._documents.values())
    
    if status:
        try:
            status_filter = DocumentStatus(status)
            docs = [d for d in docs if d.status == status_filter]
        except ValueError:
            pass
    
    return [_doc_to_response(d) for d in docs]


@router.delete("/documents/{doc_id}")
async def delete_document(doc_id: str):
    """Delete a single registered document."""
    registry = get_document_registry()
    
    doc = registry.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail=f"Document {doc_id} not found")
    
    # Remove from registry
    if doc_id in registry._documents:
        del registry._documents[doc_id]
    
    # Remove from hash index
    if doc.content_hash in registry._hash_index:
        registry._hash_index[doc.content_hash].discard(doc_id)
        if not registry._hash_index[doc.content_hash]:
            del registry._hash_index[doc.content_hash]
    
    return {"status": "deleted", "document_id": doc_id, "message": f"Document {doc_id} has been removed"}


@router.delete("/documents")
async def clear_all_documents(confirm: bool = Query(False, description="Set to true to confirm deletion")):
    """Clear ALL registered documents. Requires confirm=true."""
    if not confirm:
        raise HTTPException(
            status_code=400, 
            detail="Set confirm=true to delete all documents. This action cannot be undone."
        )
    
    registry = get_document_registry()
    count = len(registry._documents)
    
    # Clear all documents
    registry._documents.clear()
    registry._hash_index.clear()
    
    return {
        "status": "cleared",
        "deleted_count": count,
        "message": f"Successfully deleted {count} documents"
    }


@router.get("/documents/{doc_id}/duplicates", response_model=list[RegisteredDocumentResponse])
async def get_duplicates(doc_id: str):
    """Get all duplicates of a document."""
    registry = get_document_registry()
    
    doc = registry.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail=f"Document {doc_id} not found")
    
    duplicates = registry.get_duplicates(doc_id)
    return [_doc_to_response(d) for d in duplicates]


@router.get("/documents/{doc_id}/custody", response_model=list[CustodyRecordResponse])
async def get_custody_chain(doc_id: str):
    """Get the full chain of custody for a document."""
    registry = get_document_registry()
    
    chain = registry.get_custody_chain(doc_id)
    if not chain:
        raise HTTPException(status_code=404, detail=f"Document {doc_id} not found or no custody records")
    
    return [
        CustodyRecordResponse(
            timestamp=c.timestamp.isoformat(),
            action=c.action.value,
            actor=c.actor,
            details=c.details,
            ip_address=c.ip_address,
            integrity_hash=c.integrity_hash,
        )
        for c in chain
    ]


# =============================================================================
# VERIFICATION ENDPOINTS
# =============================================================================

@router.post("/documents/{doc_id}/verify", response_model=VerificationResponse)
async def verify_document(
    doc_id: str,
    file: UploadFile = File(..., description="File to verify against stored hash"),
):
    """
    Verify a document hasn't been tampered with.
    
    Compares the uploaded file's hash against the stored hash
    to detect any modifications.
    """
    registry = get_document_registry()
    
    doc = registry.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail=f"Document {doc_id} not found")
    
    content = await file.read()
    status = registry.verify_integrity(doc_id, content)
    
    verified = status == IntegrityStatus.VERIFIED
    
    messages = {
        IntegrityStatus.VERIFIED: "✅ Document integrity verified - no tampering detected",
        IntegrityStatus.TAMPERED: "🚨 TAMPER DETECTED - Document content has been modified!",
        IntegrityStatus.METADATA_CHANGED: "⚠️ Document metadata has been altered",
        IntegrityStatus.CORRUPTED: "❌ Document appears to be corrupted",
        IntegrityStatus.UNVERIFIED: "⏳ Document could not be verified",
    }
    
    return VerificationResponse(
        document_id=doc_id,
        status=status.value,
        verified=verified,
        message=messages.get(status, "Unknown status"),
        timestamp=datetime.utcnow().isoformat(),
    )


@router.get("/documents/{doc_id}/verify")
async def get_integrity_status(doc_id: str):
    """
    Get the current integrity status of a document.
    
    This returns the stored integrity status without re-verification.
    Use POST /verify with a file upload for full re-verification.
    """
    registry = get_document_registry()

    doc = registry.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail=f"Document {doc_id} not found")

    messages = {
        IntegrityStatus.VERIFIED: "✅ Document integrity verified - no tampering detected",
        IntegrityStatus.TAMPERED: "🚨 TAMPER DETECTED - Document content has been modified!",
        IntegrityStatus.METADATA_CHANGED: "⚠️ Document metadata has been altered",
        IntegrityStatus.CORRUPTED: "❌ Document appears to be corrupted",
        IntegrityStatus.UNVERIFIED: "⏳ Document has not been verified yet",
    }

    return {
        "document_id": doc.document_id,
        "status": doc.integrity_status.value,
        "is_valid": doc.integrity_status == IntegrityStatus.VERIFIED,
        "message": messages.get(doc.integrity_status, "Unknown status"),
        "content_hash": doc.content_hash,
        "registered_at": doc.registered_at.isoformat(),
    }


@router.get("/documents/{doc_id}/hash")
async def get_document_hash(doc_id: str):
    """Get the stored hashes for a document (for external verification)."""
    registry = get_document_registry()

    doc = registry.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail=f"Document {doc_id} not found")

    return {
        "document_id": doc.document_id,
        "content_hash": doc.content_hash,
        "metadata_hash": doc.metadata_hash,
        "combined_hash": doc.combined_hash,
        "algorithm": "SHA-256",
        "registered_at": doc.registered_at.isoformat(),
    }
# =============================================================================
# FLAGGING & CASE ASSOCIATION
# =============================================================================

@router.post("/documents/{doc_id}/flag")
async def flag_document(
    doc_id: str,
    flag_request: FlagDocumentRequest,
    request: Request,
):
    """Flag a document for review (suspected forgery, alteration, etc.)."""
    registry = get_document_registry()
    
    doc = registry.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail=f"Document {doc_id} not found")
    
    indicator = ForgeryIndicator.NONE
    if flag_request.indicator:
        try:
            indicator = ForgeryIndicator(flag_request.indicator)
        except ValueError:
            pass
    
    ip_address = request.client.host if request.client else None
    actor = f"api_user@{ip_address}" if ip_address else "api_user"
    
    success = registry.flag_document(
        doc_id=doc_id,
        reason=flag_request.reason,
        actor=actor,
        indicator=indicator,
    )
    
    if not success:
        raise HTTPException(status_code=500, detail="Failed to flag document")
    
    return {
        "document_id": doc_id,
        "status": "flagged",
        "reason": flag_request.reason,
        "message": "Document has been flagged for review",
    }


@router.post("/documents/{doc_id}/case")
async def associate_case(
    doc_id: str,
    case_request: AssociateCaseRequest,
    request: Request,
):
    """Associate a document with a case number."""
    registry = get_document_registry()
    
    doc = registry.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail=f"Document {doc_id} not found")
    
    ip_address = request.client.host if request.client else None
    actor = f"api_user@{ip_address}" if ip_address else "api_user"
    
    success = registry.associate_case(
        doc_id=doc_id,
        case_number=case_request.case_number,
        actor=actor,
    )
    
    if not success:
        raise HTTPException(status_code=500, detail="Failed to associate case")
    
    return {
        "document_id": doc_id,
        "case_number": case_request.case_number,
        "message": f"Document associated with case {case_request.case_number}",
    }


# =============================================================================
# FLAGGED DOCUMENTS & REVIEW
# =============================================================================

@router.get("/flagged", response_model=list[RegisteredDocumentResponse])
async def get_flagged_documents():
    """Get all documents flagged for review."""
    registry = get_document_registry()
    docs = registry.get_flagged_documents()
    return [_doc_to_response(d) for d in docs]


@router.get("/quarantined")
async def get_quarantined_documents():
    """Get all quarantined documents (high forgery risk)."""
    registry = get_document_registry()
    docs = [
        d for d in registry._documents.values()
        if d.status == DocumentStatus.QUARANTINED
    ]
    return {
        "count": len(docs),
        "documents": [_doc_to_response(d) for d in docs],
    }


# =============================================================================
# STATISTICS & ENUMS
# =============================================================================

@router.get("/stats", response_model=RegistryStatsResponse)
async def get_registry_stats():
    """Get registry statistics."""
    registry = get_document_registry()
    stats = registry.get_statistics()
    return RegistryStatsResponse(**stats)


@router.get("/enums/statuses")
async def get_document_statuses():
    """Get all document statuses."""
    return [{"value": s.value, "name": s.name} for s in DocumentStatus]


@router.get("/enums/integrity-statuses")
async def get_integrity_statuses():
    """Get all integrity statuses."""
    return [{"value": s.value, "name": s.name} for s in IntegrityStatus]


@router.get("/enums/forgery-indicators")
async def get_forgery_indicators():
    """Get all forgery indicators."""
    return [{"value": i.value, "name": i.name} for i in ForgeryIndicator]


@router.get("/enums/custody-actions")
async def get_custody_actions():
    """Get all custody actions."""
    return [{"value": a.value, "name": a.name} for a in CustodyAction]


# =============================================================================
# CASE ENDPOINTS
# =============================================================================

@router.get("/cases/{case_number}/documents", response_model=list[RegisteredDocumentResponse])
async def get_case_documents(case_number: str):
    """Get all documents for a specific case."""
    registry = get_document_registry()
    docs = registry.get_documents_by_case(case_number)
    
    if not docs:
        return []
    
    return [_doc_to_response(d) for d in docs]


@router.get("/cases")
async def list_cases():
    """List all cases with document counts."""
    registry = get_document_registry()
    
    cases = []
    for case_number, doc_ids in registry._case_index.items():
        docs = [registry._documents.get(did) for did in doc_ids if did in registry._documents]
        flagged = sum(1 for d in docs if d and d.requires_review)
        cases.append({
            "case_number": case_number,
            "document_count": len(doc_ids),
            "flagged_count": flagged,
        })
    
    return {
        "total_cases": len(cases),
        "cases": cases,
    }


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def _doc_to_response(doc: RegisteredDocument) -> RegisteredDocumentResponse:
    """Convert RegisteredDocument to response model."""
    return RegisteredDocumentResponse(
        document_id=doc.document_id,
        user_id=doc.user_id,
        case_number=doc.case_number,
        original_filename=doc.original_filename,
        file_size=doc.file_size,
        mime_type=doc.mime_type,
        content_hash=doc.content_hash,
        metadata_hash=doc.metadata_hash,
        combined_hash=doc.combined_hash,
        status=doc.status.value,
        integrity_status=doc.integrity_status.value,
        is_duplicate=doc.is_duplicate,
        original_document_id=doc.original_document_id,
        duplicate_count=doc.duplicate_count,
        forgery_alerts=[
            ForgeryAlertResponse(
                indicator=a.indicator.value,
                severity=a.severity,
                description=a.description,
                affected_area=a.affected_area,
                evidence=a.evidence,
                detected_at=a.detected_at.isoformat(),
            )
            for a in doc.forgery_alerts
        ],
        forgery_score=doc.forgery_score,
        requires_review=doc.requires_review,
        registered_at=doc.registered_at.isoformat(),
        last_verified_at=doc.last_verified_at.isoformat() if doc.last_verified_at else None,
        last_accessed_at=doc.last_accessed_at.isoformat() if doc.last_accessed_at else None,
        custody_chain=[
            CustodyRecordResponse(
                timestamp=c.timestamp.isoformat(),
                action=c.action.value,
                actor=c.actor,
                details=c.details,
                ip_address=c.ip_address,
                integrity_hash=c.integrity_hash,
            )
            for c in doc.custody_chain
        ],
        intake_document_id=doc.intake_document_id,
    )
