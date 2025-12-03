"""
Semptify 5.0 - Documents API Router
Fresh API for document management, processing, and law cross-referencing.
"""

from typing import Optional

from fastapi import APIRouter, File, UploadFile, HTTPException, Query, Depends
from pydantic import BaseModel

from app.core.config import get_settings, Settings
from app.core.security import require_user, StorageUser
from app.core.event_bus import event_bus, EventType
from app.services.document_pipeline import (
    get_document_pipeline,
    TenancyDocument,
    ProcessingStatus,
    DocumentType
)
from app.services.law_engine import get_law_engine


router = APIRouter(prefix="/api/documents", tags=["Documents"])


# =============================================================================
# Response Models
# =============================================================================

class DocumentResponse(BaseModel):
    """Response for a single document."""
    id: str
    filename: str
    status: str
    doc_type: Optional[str] = None
    confidence: Optional[float] = None
    title: Optional[str] = None
    summary: Optional[str] = None
    uploaded_at: Optional[str] = None
    analyzed_at: Optional[str] = None


class DocumentDetailResponse(DocumentResponse):
    """Detailed document response with extracted data."""
    key_dates: Optional[list] = None
    key_parties: Optional[list] = None
    key_amounts: Optional[list] = None
    key_terms: Optional[list] = None
    law_references: Optional[list] = None


class UploadResponse(BaseModel):
    """Response after document upload."""
    id: str
    filename: str
    status: str
    message: str


class TimelineEvent(BaseModel):
    """A single timeline event."""
    date: Optional[str]
    type: str
    doc_id: str
    doc_type: str
    title: str
    summary: Optional[str]


class SummaryResponse(BaseModel):
    """User's document summary."""
    total_documents: int
    by_type: dict
    by_status: dict
    total_parties: int
    date_range: dict


class RightsResponse(BaseModel):
    """Tenant rights summary based on documents."""
    categories_involved: list[str]
    your_rights: list[str]
    important_deadlines: list[dict]
    documents_analyzed: int


# =============================================================================
# Endpoints
# =============================================================================

@router.post("/upload", response_model=UploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    process_now: bool = Query(True, description="Process immediately or queue"),
    user: StorageUser = Depends(require_user),
):
    """
    Upload a document for processing.

    The document will be:
    1. Stored securely
    2. Analyzed with Azure Document Intelligence (OCR)
    3. Classified by type (lease, notice, receipt, etc.)
    4. Cross-referenced with applicable tenant laws
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename required")

    content = await file.read()
    if len(content) > 50 * 1024 * 1024:  # 50MB limit
        raise HTTPException(status_code=400, detail="File too large (max 50MB)")

    # Use authenticated user ID instead of query parameter
    user_id = user.user_id
    pipeline = get_document_pipeline()

    if process_now:
        doc = await pipeline.ingest_and_process(
            user_id=user_id,
            filename=file.filename,
            content=content,
            mime_type=file.content_type or "application/octet-stream"
        )

        # Cross-reference with laws
        if doc.status == ProcessingStatus.CLASSIFIED:
            law_engine = get_law_engine()
            doc.law_references = law_engine.get_applicable_laws(
                doc_type=doc.doc_type.value if doc.doc_type else "unknown",
                doc_text=doc.full_text or "",
                doc_terms=doc.key_terms or []
            )
        
        # Publish document processed event
        event_bus.publish_sync(EventType.DOCUMENT_ADDED, {
            "user_id": user_id,
            "document_id": doc.id,
            "filename": doc.filename,
            "doc_type": doc.doc_type.value if doc.doc_type else "unknown",
            "status": doc.status.value,
            "has_text": bool(doc.full_text),
            "law_refs_count": len(doc.law_references) if doc.law_references else 0
        })
        
        # Trigger timeline extraction if document was classified
        if doc.status == ProcessingStatus.CLASSIFIED and doc.full_text:
            event_bus.publish_sync(EventType.DOCUMENT_CLASSIFIED, {
                "user_id": user_id,
                "document_id": doc.id,
                "doc_type": doc.doc_type.value if doc.doc_type else "unknown",
                "ready_for_extraction": True
            })
    else:
        doc = await pipeline.ingest(
            user_id=user_id,
            filename=file.filename,
            content=content,
            mime_type=file.content_type or "application/octet-stream"
        )
    
    return UploadResponse(
        id=doc.id,
        filename=doc.filename,
        status=doc.status.value,
        message=f"Document {'processed' if process_now else 'queued'} successfully"
    )


@router.get("/", response_model=list[DocumentResponse])
async def list_documents(
    doc_type: Optional[str] = Query(None, description="Filter by document type"),
    status: Optional[str] = Query(None, description="Filter by status"),
    user: StorageUser = Depends(require_user),
):
    """List all documents for the authenticated user."""
    user_id = user.user_id
    pipeline = get_document_pipeline()
    
    if doc_type:
        try:
            dtype = DocumentType(doc_type)
            docs = pipeline.get_user_documents_by_type(user_id, dtype)
        except ValueError:
            docs = pipeline.get_user_documents(user_id)
    else:
        docs = pipeline.get_user_documents(user_id)
    
    if status:
        try:
            pstatus = ProcessingStatus(status)
            docs = [d for d in docs if d.status == pstatus]
        except ValueError:
            pass
    
    return [
        DocumentResponse(
            id=d.id,
            filename=d.filename,
            status=d.status.value,
            doc_type=d.doc_type.value if d.doc_type else None,
            confidence=d.confidence,
            title=d.title,
            summary=d.summary,
            uploaded_at=d.uploaded_at.isoformat() if d.uploaded_at else None,
            analyzed_at=d.analyzed_at.isoformat() if d.analyzed_at else None
        )
        for d in docs
    ]


@router.get("/{doc_id}", response_model=DocumentDetailResponse)
async def get_document(doc_id: str):
    """Get detailed information about a document."""
    pipeline = get_document_pipeline()
    doc = pipeline.get_document(doc_id)
    
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Get law references if not already set
    if doc.status == ProcessingStatus.CLASSIFIED and not doc.law_references:
        law_engine = get_law_engine()
        doc.law_references = law_engine.get_applicable_laws(
            doc_type=doc.doc_type.value if doc.doc_type else "unknown",
            doc_text=doc.full_text or "",
            doc_terms=doc.key_terms or []
        )
    
    return DocumentDetailResponse(
        id=doc.id,
        filename=doc.filename,
        status=doc.status.value,
        doc_type=doc.doc_type.value if doc.doc_type else None,
        confidence=doc.confidence,
        title=doc.title,
        summary=doc.summary,
        uploaded_at=doc.uploaded_at.isoformat() if doc.uploaded_at else None,
        analyzed_at=doc.analyzed_at.isoformat() if doc.analyzed_at else None,
        key_dates=doc.key_dates,
        key_parties=doc.key_parties,
        key_amounts=doc.key_amounts,
        key_terms=doc.key_terms,
        law_references=doc.law_references
    )


@router.post("/{doc_id}/reprocess")
async def reprocess_document(doc_id: str):
    """Reprocess an existing document."""
    pipeline = get_document_pipeline()
    doc = pipeline.get_document(doc_id)

    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    doc = await pipeline.process(doc_id)

    return {"status": doc.status.value, "message": "Document reprocessed"}


class DocumentTextResponse(BaseModel):
    """Response for document text content."""
    doc_id: str
    filename: str
    text: str
    doc_type: Optional[str] = None


class CategoryUpdateRequest(BaseModel):
    """Request to update document category."""
    doc_type: str


@router.get("/{doc_id}/text", response_model=DocumentTextResponse)
async def get_document_text(
    doc_id: str,
    user: StorageUser = Depends(require_user)
):
    """Get the full text content of a document."""
    pipeline = get_document_pipeline()
    doc = pipeline.get_document(doc_id)

    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    if doc.user_id != user.user_id:
        raise HTTPException(status_code=403, detail="Access denied")

    if not doc.full_text:
        raise HTTPException(
            status_code=400,
            detail="Document has no extracted text. Reprocess the document first."
        )

    return DocumentTextResponse(
        doc_id=doc_id,
        filename=doc.filename,
        text=doc.full_text,
        doc_type=doc.doc_type.value if doc.doc_type else None
    )


@router.put("/{doc_id}/category")
async def update_document_category(
    doc_id: str,
    request: CategoryUpdateRequest,
    user: StorageUser = Depends(require_user)
):
    """Update the category/type of a document."""
    pipeline = get_document_pipeline()
    doc = pipeline.get_document(doc_id)

    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    if doc.user_id != user.user_id:
        raise HTTPException(status_code=403, detail="Access denied")

    # Validate document type
    valid_types = ['court_filing', 'lease', 'notice', 'correspondence', 'financial', 'other']
    if request.doc_type not in valid_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid document type. Must be one of: {', '.join(valid_types)}"
        )

    # Update the document type
    try:
        new_type = DocumentType(request.doc_type)
        doc.doc_type = new_type
        pipeline._save_index()
        
        return {
            "doc_id": doc_id,
            "doc_type": request.doc_type,
            "message": "Category updated successfully"
        }
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid document type")


@router.get("/{doc_id}/download")
async def download_document(
    doc_id: str,
    user: StorageUser = Depends(require_user)
):
    """Download the original document file."""
    from fastapi.responses import FileResponse
    import os

    pipeline = get_document_pipeline()
    doc = pipeline.get_document(doc_id)

    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    if doc.user_id != user.user_id:
        raise HTTPException(status_code=403, detail="Access denied")

    # Find the file path
    if hasattr(doc, 'file_path') and doc.file_path and os.path.exists(doc.file_path):
        return FileResponse(
            path=doc.file_path,
            filename=doc.filename,
            media_type="application/octet-stream"
        )

    raise HTTPException(status_code=404, detail="Document file not found")


@router.get("/timeline/", response_model=list[TimelineEvent])
async def get_timeline(user: StorageUser = Depends(require_user)):
    """Get chronological timeline of all documents and events."""
    user_id = user.user_id
    pipeline = get_document_pipeline()
    events = pipeline.get_timeline(user_id)
    
    return [TimelineEvent(**e) for e in events]


@router.get("/summary/", response_model=SummaryResponse)
async def get_summary(user: StorageUser = Depends(require_user)):
    """Get summary statistics for the authenticated user's documents."""
    user_id = user.user_id
    pipeline = get_document_pipeline()
    summary = pipeline.get_summary(user_id)
    
    return SummaryResponse(**summary)


@router.get("/rights/", response_model=RightsResponse)
async def get_rights_summary(user: StorageUser = Depends(require_user)):
    """
    Get a summary of tenant rights based on uploaded documents.
    Analyzes documents and cross-references with tenant law.
    """
    user_id = user.user_id
    pipeline = get_document_pipeline()
    law_engine = get_law_engine()
    
    docs = pipeline.get_user_documents(user_id)
    classified_docs = [d for d in docs if d.status == ProcessingStatus.CLASSIFIED]
    
    if not classified_docs:
        return RightsResponse(
            categories_involved=[],
            your_rights=["Upload documents to see applicable rights"],
            important_deadlines=[],
            documents_analyzed=0
        )
    
    rights = law_engine.get_rights_summary(user_id, classified_docs)
    return RightsResponse(**rights)


# =============================================================================
# Law Reference Endpoints
# =============================================================================

@router.get("/laws/", response_model=list[dict])
async def list_laws(category: Optional[str] = Query(None, description="Filter by category")):
    """List all law references in the system."""
    law_engine = get_law_engine()
    
    if category:
        from app.services.law_engine import LawCategory
        try:
            cat = LawCategory(category)
            laws = law_engine.get_laws_by_category(cat)
        except ValueError:
            laws = law_engine.get_all_laws()
    else:
        laws = law_engine.get_all_laws()
    
    return [law.to_dict() for law in laws]


@router.get("/laws/{law_id}")
async def get_law(law_id: str):
    """Get details about a specific law reference."""
    law_engine = get_law_engine()
    law = law_engine.get_law(law_id)

    if not law:
        raise HTTPException(status_code=404, detail="Law reference not found")

    return law.to_dict()


# =============================================================================
# Event Extraction & Auto-Timeline
# =============================================================================

class ExtractedEventResponse(BaseModel):
    """A single extracted event from a document."""
    date: str
    event_type: str
    title: str
    description: str
    confidence: float
    is_deadline: bool
    source_text: str


class ExtractEventsResponse(BaseModel):
    """Response with all extracted events from a document."""
    doc_id: str
    doc_type: Optional[str]
    events: list[ExtractedEventResponse]
    total_events: int


class AutoTimelineRequest(BaseModel):
    """Request to auto-populate timeline from document."""
    min_confidence: float = 0.7
    include_existing: bool = False


class AutoTimelineResponse(BaseModel):
    """Response after auto-populating timeline."""
    doc_id: str
    events_created: int
    events_skipped: int
    events: list[dict]


@router.get("/{doc_id}/events", response_model=ExtractEventsResponse)
async def extract_document_events(
    doc_id: str,
    min_confidence: float = Query(0.5, ge=0.0, le=1.0, description="Minimum confidence threshold"),
    user: StorageUser = Depends(require_user)
):
    """
    Extract dated events from a document.
    
    Analyzes the document text and extracts all dates with their context,
    classifying them as:
    - notice: Notice served, vacate deadlines
    - court: Filings, hearings, trials
    - payment: Rent due, payments made
    - maintenance: Inspections, repairs
    - communication: Letters sent/received
    - other: Lease dates, move-in/out
    
    Returns events sorted by date with confidence scores.
    """
    from app.services.event_extractor import get_event_extractor
    
    pipeline = get_document_pipeline()
    doc = pipeline.get_document(doc_id)
    
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    if doc.user_id != user.user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    if not doc.full_text:
        raise HTTPException(
            status_code=400, 
            detail="Document has no extracted text. Reprocess the document first."
        )
    
    extractor = get_event_extractor()
    events = extractor.extract_events(
        text=doc.full_text,
        doc_type=doc.doc_type.value if doc.doc_type else "unknown"
    )
    
    # Filter by confidence
    events = [e for e in events if e.confidence >= min_confidence]
    
    return ExtractEventsResponse(
        doc_id=doc_id,
        doc_type=doc.doc_type.value if doc.doc_type else None,
        events=[
            ExtractedEventResponse(
                date=e.date.isoformat(),
                event_type=e.event_type,
                title=e.title,
                description=e.description,
                confidence=e.confidence,
                is_deadline=e.is_deadline,
                source_text=e.source_text
            )
            for e in events
        ],
        total_events=len(events)
    )


@router.post("/{doc_id}/auto-timeline", response_model=AutoTimelineResponse)
async def auto_populate_timeline(
    doc_id: str,
    request: AutoTimelineRequest = AutoTimelineRequest(),
    user: StorageUser = Depends(require_user)
):
    """
    Automatically create timeline events from a document.
    
    Extracts all dated events from the document and adds them to the
    user's timeline. Links each event back to the source document.
    
    Use this after uploading a document to automatically build your
    case timeline with minimal interaction.
    """
    import uuid
    from datetime import datetime, timezone
    from app.services.event_extractor import get_event_extractor
    from app.core.database import get_db_session
    from app.models.models import TimelineEvent as TimelineEventModel
    from sqlalchemy import select, and_
    
    pipeline = get_document_pipeline()
    doc = pipeline.get_document(doc_id)
    
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    if doc.user_id != user.user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    if not doc.full_text:
        raise HTTPException(
            status_code=400,
            detail="Document has no extracted text. Reprocess the document first."
        )
    
    # Extract events
    extractor = get_event_extractor()
    events = extractor.extract_events(
        text=doc.full_text,
        doc_type=doc.doc_type.value if doc.doc_type else "unknown"
    )
    
    # Filter by confidence
    events = [e for e in events if e.confidence >= request.min_confidence]
    
    events_created = 0
    events_skipped = 0
    created_events = []
    
    async with get_db_session() as session:
        for event in events:
            # Check if similar event already exists (same date, type, doc)
            if not request.include_existing:
                existing_query = select(TimelineEventModel).where(
                    and_(
                        TimelineEventModel.user_id == user.user_id,
                        TimelineEventModel.document_id == doc_id,
                        TimelineEventModel.event_date == event.date,
                        TimelineEventModel.event_type == event.event_type
                    )
                )
                existing = await session.execute(existing_query)
                if existing.scalar_one_or_none():
                    events_skipped += 1
                    continue
            
            # Create timeline event
            db_event = TimelineEventModel(
                id=str(uuid.uuid4()),
                user_id=user.user_id,
                event_type=event.event_type,
                title=f"{event.title} ({doc.filename})",
                description=event.description,
                event_date=event.date,
                document_id=doc_id,
                is_evidence=event.is_deadline,  # Mark deadlines as evidence
                created_at=datetime.now(timezone.utc),
            )
            session.add(db_event)
            events_created += 1
            
            created_events.append({
                "id": db_event.id,
                "date": event.date.isoformat(),
                "event_type": event.event_type,
                "title": db_event.title,
                "description": event.description,
                "is_deadline": event.is_deadline,
                "confidence": event.confidence
            })
        
        await session.commit()
    
    return AutoTimelineResponse(
        doc_id=doc_id,
        events_created=events_created,
        events_skipped=events_skipped,
        events=created_events
    )


@router.post("/auto-timeline-all", response_model=dict)
async def auto_timeline_all_documents(
    min_confidence: float = Query(0.7, ge=0.0, le=1.0),
    user: StorageUser = Depends(require_user)
):
    """
    Extract events from ALL user documents and populate timeline.
    
    Processes every analyzed document and creates timeline events.
    Useful for building a complete case timeline in one action.
    """
    import uuid
    from datetime import datetime, timezone
    from app.services.event_extractor import get_event_extractor
    from app.core.database import get_db_session
    from app.models.models import TimelineEvent as TimelineEventModel
    from sqlalchemy import select, and_
    
    pipeline = get_document_pipeline()
    docs = pipeline.get_user_documents(user.user_id)
    
    # Only process analyzed documents
    docs = [d for d in docs if d.status == ProcessingStatus.CLASSIFIED and d.full_text]
    
    if not docs:
        return {
            "message": "No analyzed documents found",
            "documents_processed": 0,
            "total_events_created": 0
        }
    
    extractor = get_event_extractor()
    total_created = 0
    total_skipped = 0
    docs_processed = 0
    
    async with get_db_session() as session:
        for doc in docs:
            events = extractor.extract_events(
                text=doc.full_text,
                doc_type=doc.doc_type.value if doc.doc_type else "unknown"
            )
            events = [e for e in events if e.confidence >= min_confidence]
            
            for event in events:
                # Check for existing
                existing_query = select(TimelineEventModel).where(
                    and_(
                        TimelineEventModel.user_id == user.user_id,
                        TimelineEventModel.document_id == doc.id,
                        TimelineEventModel.event_date == event.date,
                        TimelineEventModel.event_type == event.event_type
                    )
                )
                existing = await session.execute(existing_query)
                if existing.scalar_one_or_none():
                    total_skipped += 1
                    continue
                
                db_event = TimelineEventModel(
                    id=str(uuid.uuid4()),
                    user_id=user.user_id,
                    event_type=event.event_type,
                    title=f"{event.title} ({doc.filename})",
                    description=event.description,
                    event_date=event.date,
                    document_id=doc.id,
                    is_evidence=event.is_deadline,
                    created_at=datetime.now(timezone.utc),
                )
                session.add(db_event)
                total_created += 1
            
            docs_processed += 1
        
        await session.commit()
    
    return {
        "message": "Timeline populated from all documents",
        "documents_processed": docs_processed,
        "total_events_created": total_created,
        "events_skipped": total_skipped
    }