"""
Semptify 5.0 - Document Processing Pipeline
Handles the full lifecycle: Upload → Analyze → Classify → Store → Cross-reference
"""

import hashlib
import json
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Optional
from uuid import uuid4

from app.services.azure_ai import get_azure_ai, DocumentType, ExtractedDocument

# Import context loop for event emission
try:
    from app.services.context_loop import context_loop, EventType
    HAS_CONTEXT_LOOP = True
except ImportError:
    HAS_CONTEXT_LOOP = False


class ProcessingStatus(str, Enum):
    """Document processing states."""
    PENDING = "pending"
    ANALYZING = "analyzing"
    CLASSIFIED = "classified"
    CROSS_REFERENCED = "cross_referenced"
    FAILED = "failed"


@dataclass
class TenancyDocument:
    """A document in a tenant's record."""
    id: str
    user_id: str
    filename: str
    file_hash: str
    mime_type: str
    file_size: int
    storage_path: str
    
    # Processing state
    status: ProcessingStatus
    
    # Analysis results (populated after processing)
    doc_type: Optional[DocumentType] = None
    confidence: Optional[float] = None
    title: Optional[str] = None
    summary: Optional[str] = None
    full_text: Optional[str] = None
    
    # Extracted data
    key_dates: Optional[list] = None
    key_parties: Optional[list] = None
    key_amounts: Optional[list] = None
    key_terms: Optional[list] = None
    
    # Law cross-references (populated by law engine)
    law_references: Optional[list] = None
    
    # Timestamps
    uploaded_at: Optional[datetime] = None
    analyzed_at: Optional[datetime] = None
    
    def to_dict(self) -> dict:
        """Convert to dictionary for storage/API."""
        data = asdict(self)
        # Convert enums and datetimes
        if self.status:
            data["status"] = self.status.value
        if self.doc_type:
            data["doc_type"] = self.doc_type.value
        if self.uploaded_at:
            data["uploaded_at"] = self.uploaded_at.isoformat()
        if self.analyzed_at:
            data["analyzed_at"] = self.analyzed_at.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "TenancyDocument":
        """Create from dictionary."""
        if data.get("status"):
            data["status"] = ProcessingStatus(data["status"])
        if data.get("doc_type"):
            data["doc_type"] = DocumentType(data["doc_type"])
        if data.get("uploaded_at") and isinstance(data["uploaded_at"], str):
            data["uploaded_at"] = datetime.fromisoformat(data["uploaded_at"])
        if data.get("analyzed_at") and isinstance(data["analyzed_at"], str):
            data["analyzed_at"] = datetime.fromisoformat(data["analyzed_at"])
        return cls(**data)


class DocumentPipeline:
    """
    Document processing pipeline.
    Manages the flow from upload to fully analyzed and cross-referenced document.
    """

    def __init__(self, data_dir: str = "data/documents"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.azure_ai = get_azure_ai()
        
        # In-memory document index (would be database in production)
        self._documents: dict[str, TenancyDocument] = {}
        self._load_index()

    def _load_index(self):
        """Load document index from disk."""
        index_file = self.data_dir / "index.json"
        if index_file.exists():
            try:
                with open(index_file) as f:
                    data = json.load(f)
                    for doc_id, doc_data in data.items():
                        self._documents[doc_id] = TenancyDocument.from_dict(doc_data)
            except Exception:
                pass

    def _save_index(self):
        """Save document index to disk."""
        index_file = self.data_dir / "index.json"
        data = {doc_id: doc.to_dict() for doc_id, doc in self._documents.items()}
        with open(index_file, "w") as f:
            json.dump(data, f, indent=2, default=str)

    async def ingest(
        self,
        user_id: str,
        filename: str,
        content: bytes,
        mime_type: str
    ) -> TenancyDocument:
        """
        Ingest a new document into the pipeline.
        Returns immediately with pending status, processing happens async.
        Deduplicates by file hash - returns existing doc if already uploaded.
        """
        # Generate hash first to check for duplicates
        file_hash = hashlib.sha256(content).hexdigest()
        
        # Check if this exact file already exists for this user
        existing = self._find_by_hash(user_id, file_hash)
        if existing:
            # Return existing document instead of creating duplicate
            return existing
        
        # Generate IDs
        doc_id = str(uuid4())

        # Store file
        user_dir = self.data_dir / user_id
        user_dir.mkdir(exist_ok=True)
        file_path = user_dir / f"{doc_id}_{filename}"
        file_path.write_bytes(content)
        
        # Create document record
        doc = TenancyDocument(
            id=doc_id,
            user_id=user_id,
            filename=filename,
            file_hash=file_hash,
            mime_type=mime_type,
            file_size=len(content),
            storage_path=str(file_path),
            status=ProcessingStatus.PENDING,
            uploaded_at=datetime.now(timezone.utc)
        )

        self._documents[doc_id] = doc
        self._save_index()

        return doc

    def _find_by_hash(self, user_id: str, file_hash: str) -> Optional[TenancyDocument]:
        """Find an existing document by file hash for a specific user."""
        for doc in self._documents.values():
            if doc.user_id == user_id and doc.file_hash == file_hash:
                return doc
        return None

    async def process(self, doc_id: str) -> TenancyDocument:
        """
        Process a document through the full pipeline.
        1. Azure Document Intelligence (OCR)
        2. AI Classification
        3. Key information extraction
        """
        doc = self._documents.get(doc_id)
        if not doc:
            raise ValueError(f"Document not found: {doc_id}")
        
        doc.status = ProcessingStatus.ANALYZING
        self._save_index()
        
        try:
            # Read file content
            content = Path(doc.storage_path).read_bytes()
            
            # Analyze with Azure AI
            result: ExtractedDocument = await self.azure_ai.analyze_document(
                content=content,
                filename=doc.filename,
                mime_type=doc.mime_type
            )
            
            # Update document with results
            doc.doc_type = result.doc_type
            doc.confidence = result.confidence
            doc.title = result.title
            doc.summary = result.summary
            doc.full_text = result.full_text
            doc.key_dates = result.key_dates
            doc.key_parties = result.key_parties
            doc.key_amounts = result.key_amounts
            doc.key_terms = result.key_terms
            doc.analyzed_at = result.analyzed_at
            doc.status = ProcessingStatus.CLASSIFIED
            
        except Exception as e:
            doc.status = ProcessingStatus.FAILED
            doc.summary = f"Processing failed: {str(e)}"

        self._save_index()
        
        # Emit event to context loop
        if HAS_CONTEXT_LOOP and doc.status == ProcessingStatus.CLASSIFIED:
            try:
                # Emit document uploaded event
                context_loop.emit_event(
                    EventType.DOCUMENT_UPLOADED,
                    doc.user_id,
                    {
                        "type": doc.doc_type.value if doc.doc_type else "unknown",
                        "id": doc.id,
                        "filename": doc.filename,
                    },
                    source="document_pipeline",
                )
                
                # Emit analyzed event with details
                context_loop.emit_event(
                    EventType.DOCUMENT_ANALYZED,
                    doc.user_id,
                    {
                        "document_id": doc.id,
                        "type": doc.doc_type.value if doc.doc_type else "unknown",
                        "title": doc.title,
                        "summary": doc.summary,
                        "key_dates": doc.key_dates,
                        "key_parties": doc.key_parties,
                        "confidence": doc.confidence,
                    },
                    source="document_pipeline",
                )
            except Exception as ctx_err:
                print(f"Context loop event failed: {ctx_err}")
        
        return doc

    async def ingest_and_process(
        self,
        user_id: str,
        filename: str,
        content: bytes,
        mime_type: str
    ) -> TenancyDocument:
        """Convenience method: ingest and process in one call."""
        doc = await self.ingest(user_id, filename, content, mime_type)
        return await self.process(doc.id)

    def get_document(self, doc_id: str) -> Optional[TenancyDocument]:
        """Get a document by ID."""
        return self._documents.get(doc_id)

    def get_user_documents(self, user_id: str) -> list[TenancyDocument]:
        """Get all documents for a user."""
        return [
            doc for doc in self._documents.values()
            if doc.user_id == user_id
        ]

    def get_user_documents_by_type(
        self,
        user_id: str,
        doc_type: DocumentType
    ) -> list[TenancyDocument]:
        """Get user documents filtered by type."""
        return [
            doc for doc in self._documents.values()
            if doc.user_id == user_id and doc.doc_type == doc_type
        ]

    def get_timeline(self, user_id: str) -> list[dict]:
        """
        Get chronological timeline of all documents/events for a user.
        Combines document dates into a single timeline.
        """
        timeline = []
        
        for doc in self.get_user_documents(user_id):
            # Add document upload event
            timeline.append({
                "date": doc.uploaded_at.isoformat() if doc.uploaded_at else None,
                "type": "document_uploaded",
                "doc_id": doc.id,
                "doc_type": doc.doc_type.value if doc.doc_type else "unknown",
                "title": doc.title or doc.filename,
                "summary": doc.summary
            })
            
            # Add key dates from document
            if doc.key_dates:
                for date_info in doc.key_dates:
                    timeline.append({
                        "date": date_info.get("date"),
                        "type": "document_date",
                        "doc_id": doc.id,
                        "doc_type": doc.doc_type.value if doc.doc_type else "unknown",
                        "title": date_info.get("description", "Date"),
                        "summary": f"From: {doc.title or doc.filename}"
                    })
        
        # Sort by date
        timeline.sort(key=lambda x: x.get("date") or "")
        return timeline

    def get_summary(self, user_id: str) -> dict:
        """Get summary statistics for a user's documents."""
        docs = self.get_user_documents(user_id)
        
        by_type = {}
        for doc in docs:
            doc_type = doc.doc_type.value if doc.doc_type else "unknown"
            by_type[doc_type] = by_type.get(doc_type, 0) + 1
        
        by_status = {}
        for doc in docs:
            status = doc.status.value
            by_status[status] = by_status.get(status, 0) + 1
        
        return {
            "total_documents": len(docs),
            "by_type": by_type,
            "by_status": by_status,
            "total_parties": len(set(
                p.get("name", "") 
                for doc in docs 
                for p in (doc.key_parties or [])
            )),
            "date_range": self._get_date_range(docs)
        }

    def _get_date_range(self, docs: list[TenancyDocument]) -> dict:
        """Get earliest and latest dates from documents."""
        all_dates = []
        for doc in docs:
            if doc.uploaded_at:
                all_dates.append(doc.uploaded_at)
            for date_info in (doc.key_dates or []):
                if date_info.get("date"):
                    try:
                        all_dates.append(datetime.fromisoformat(date_info["date"]))
                    except ValueError:
                        pass
        
        if not all_dates:
            return {"earliest": None, "latest": None}
        
        return {
            "earliest": min(all_dates).isoformat(),
            "latest": max(all_dates).isoformat()
        }


# Singleton instance
_pipeline: Optional[DocumentPipeline] = None


def get_document_pipeline() -> DocumentPipeline:
    """Get or create document pipeline instance."""
    global _pipeline
    if _pipeline is None:
        _pipeline = DocumentPipeline()
    return _pipeline
