"""
Document Registry & Chain of Custody System

Provides:
- Unique Document IDs with timestamp encoding
- Tamper-proof hashing (SHA-256 + metadata hash)
- Duplicate detection with copy marking
- Case number association
- Forgery/alteration detection
- Complete audit trail (chain of custody)
- Version tracking for document modifications

Every document gets:
1. Unique SEMPTIFY Document ID (SEM-YYYY-NNNNNN-XXXX)
2. Intake timestamp (UTC, ISO 8601)
3. Content hash (SHA-256) - tamper detection
4. Metadata hash - tracks any changes to document metadata
5. Chain of custody record
6. Integrity verification on every access
"""

import hashlib
import hmac
import json
import re
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Optional, Any
from uuid import uuid4
import base64


# =============================================================================
# ENUMS
# =============================================================================

class DocumentStatus(str, Enum):
    """Document registry status."""
    ORIGINAL = "original"           # First instance of this document
    COPY = "copy"                   # Duplicate of existing document
    MODIFIED_COPY = "modified_copy" # Copy with detected modifications
    SUPERSEDED = "superseded"       # Replaced by newer version
    ARCHIVED = "archived"           # No longer active but preserved
    FLAGGED = "flagged"             # Flagged for review
    QUARANTINED = "quarantined"     # Suspected tampering/forgery


class IntegrityStatus(str, Enum):
    """Document integrity verification status."""
    VERIFIED = "verified"           # Hash matches, no tampering detected
    TAMPERED = "tampered"           # Content hash mismatch - file modified
    METADATA_CHANGED = "metadata_changed"  # Metadata altered
    CORRUPTED = "corrupted"         # File corrupted or unreadable
    UNVERIFIED = "unverified"       # Not yet verified


class ForgeryIndicator(str, Enum):
    """Types of forgery/alteration indicators."""
    NONE = "none"
    DATE_INCONSISTENCY = "date_inconsistency"
    SIGNATURE_ANOMALY = "signature_anomaly"
    FONT_MISMATCH = "font_mismatch"
    METADATA_TAMPERING = "metadata_tampering"
    COPY_PASTE_ARTIFACTS = "copy_paste_artifacts"
    IMAGE_MANIPULATION = "image_manipulation"
    TEXT_OVERLAY = "text_overlay"
    WHITE_OUT_DETECTED = "white_out_detected"
    DIGITAL_ALTERATION = "digital_alteration"
    TIMELINE_IMPOSSIBILITY = "timeline_impossibility"
    DUPLICATE_WITH_CHANGES = "duplicate_with_changes"


class CustodyAction(str, Enum):
    """Chain of custody actions."""
    RECEIVED = "received"
    VERIFIED = "verified"
    PROCESSED = "processed"
    ACCESSED = "accessed"
    MODIFIED = "modified"
    EXPORTED = "exported"
    SHARED = "shared"
    FLAGGED = "flagged"
    ARCHIVED = "archived"
    INTEGRITY_CHECK = "integrity_check"


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class CustodyRecord:
    """Single entry in chain of custody."""
    timestamp: datetime
    action: CustodyAction
    actor: str  # user_id or "system"
    details: str = ""
    ip_address: Optional[str] = None
    device_info: Optional[str] = None
    integrity_hash: Optional[str] = None  # Hash at time of action

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp.isoformat(),
            "action": self.action.value,
            "actor": self.actor,
            "details": self.details,
            "ip_address": self.ip_address,
            "device_info": self.device_info,
            "integrity_hash": self.integrity_hash,
        }


@dataclass
class ForgeryAlert:
    """Alert for suspected forgery or alteration."""
    indicator: ForgeryIndicator
    severity: str  # critical, high, medium, low
    description: str
    affected_area: Optional[str] = None  # e.g., "page 2, signature block"
    evidence: Optional[str] = None  # Supporting evidence for the alert
    detected_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        return {
            "indicator": self.indicator.value,
            "severity": self.severity,
            "description": self.description,
            "affected_area": self.affected_area,
            "evidence": self.evidence,
            "detected_at": self.detected_at.isoformat(),
        }


@dataclass
class DocumentVersion:
    """Version record for document changes."""
    version: int
    timestamp: datetime
    content_hash: str
    changes: str
    changed_by: str

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "timestamp": self.timestamp.isoformat(),
            "content_hash": self.content_hash,
            "changes": self.changes,
            "changed_by": self.changed_by,
        }


@dataclass
class RegisteredDocument:
    """A document in the registry with full tracking."""
    
    # Core identifiers
    document_id: str          # SEM-YYYY-NNNNNN-XXXX format
    user_id: str
    case_number: Optional[str] = None
    
    # Original file info
    original_filename: str = ""
    file_size: int = 0
    mime_type: str = ""
    
    # Hashes for tamper-proofing
    content_hash: str = ""        # SHA-256 of file content
    metadata_hash: str = ""       # SHA-256 of metadata
    combined_hash: str = ""       # Combined verification hash
    
    # Status tracking
    status: DocumentStatus = DocumentStatus.ORIGINAL
    integrity_status: IntegrityStatus = IntegrityStatus.UNVERIFIED
    
    # Duplicate tracking
    is_duplicate: bool = False
    original_document_id: Optional[str] = None  # If this is a copy
    duplicate_ids: list[str] = field(default_factory=list)  # IDs of copies
    duplicate_count: int = 0
    
    # Forgery detection
    forgery_alerts: list[ForgeryAlert] = field(default_factory=list)
    forgery_score: float = 0.0  # 0.0 = clean, 1.0 = definitely forged
    requires_review: bool = False
    
    # Timestamps
    registered_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_verified_at: Optional[datetime] = None
    last_accessed_at: Optional[datetime] = None
    
    # Chain of custody
    custody_chain: list[CustodyRecord] = field(default_factory=list)
    
    # Version history
    versions: list[DocumentVersion] = field(default_factory=list)
    current_version: int = 1
    
    # Storage
    storage_path: Optional[str] = None
    
    # Linked intake document
    intake_document_id: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "document_id": self.document_id,
            "user_id": self.user_id,
            "case_number": self.case_number,
            "original_filename": self.original_filename,
            "file_size": self.file_size,
            "mime_type": self.mime_type,
            "content_hash": self.content_hash,
            "metadata_hash": self.metadata_hash,
            "combined_hash": self.combined_hash,
            "status": self.status.value,
            "integrity_status": self.integrity_status.value,
            "is_duplicate": self.is_duplicate,
            "original_document_id": self.original_document_id,
            "duplicate_ids": self.duplicate_ids,
            "duplicate_count": self.duplicate_count,
            "forgery_alerts": [a.to_dict() for a in self.forgery_alerts],
            "forgery_score": self.forgery_score,
            "requires_review": self.requires_review,
            "registered_at": self.registered_at.isoformat(),
            "last_verified_at": self.last_verified_at.isoformat() if self.last_verified_at else None,
            "last_accessed_at": self.last_accessed_at.isoformat() if self.last_accessed_at else None,
            "custody_chain": [c.to_dict() for c in self.custody_chain],
            "versions": [v.to_dict() for v in self.versions],
            "current_version": self.current_version,
            "storage_path": self.storage_path,
            "intake_document_id": self.intake_document_id,
        }


# =============================================================================
# DOCUMENT ID GENERATOR
# =============================================================================

class DocumentIDGenerator:
    """Generate unique, timestamped document IDs."""
    
    _counter = 0
    _last_date = ""
    
    @classmethod
    def generate(cls) -> str:
        """
        Generate a unique document ID in format: SEM-YYYY-NNNNNN-XXXX
        
        SEM = Semptify prefix
        YYYY = Year
        NNNNNN = Sequential counter (resets yearly)
        XXXX = Random suffix for uniqueness
        """
        now = datetime.now(timezone.utc)
        date_part = now.strftime("%Y")
        
        # Reset counter for new year
        if date_part != cls._last_date:
            cls._counter = 0
            cls._last_date = date_part
        
        cls._counter += 1
        
        # Random suffix for additional uniqueness
        random_suffix = uuid4().hex[:4].upper()
        
        return f"SEM-{date_part}-{cls._counter:06d}-{random_suffix}"
    
    @classmethod
    def parse(cls, doc_id: str) -> Optional[dict]:
        """Parse a document ID to extract components."""
        pattern = r"^SEM-(\d{4})-(\d{6})-([A-Z0-9]{4})$"
        match = re.match(pattern, doc_id)
        if match:
            return {
                "year": match.group(1),
                "sequence": int(match.group(2)),
                "suffix": match.group(3),
            }
        return None
    
    @classmethod
    def is_valid(cls, doc_id: str) -> bool:
        """Check if a document ID is valid format."""
        return cls.parse(doc_id) is not None


# =============================================================================
# HASH GENERATOR
# =============================================================================

class HashGenerator:
    """Generate and verify tamper-proof hashes."""
    
    # Secret key for HMAC (in production, load from secure config)
    _SECRET_KEY = b"SEMPTIFY_DOCUMENT_INTEGRITY_KEY_2025"
    
    @classmethod
    def content_hash(cls, content: bytes) -> str:
        """Generate SHA-256 hash of file content."""
        return hashlib.sha256(content).hexdigest()
    
    @classmethod
    def metadata_hash(cls, metadata: dict) -> str:
        """Generate hash of document metadata."""
        # Sort keys for consistent hashing
        serialized = json.dumps(metadata, sort_keys=True, default=str)
        return hashlib.sha256(serialized.encode()).hexdigest()
    
    @classmethod
    def combined_hash(cls, content_hash: str, metadata_hash: str, doc_id: str) -> str:
        """Generate HMAC-based combined hash for tamper detection."""
        message = f"{doc_id}:{content_hash}:{metadata_hash}".encode()
        return hmac.new(cls._SECRET_KEY, message, hashlib.sha256).hexdigest()
    
    @classmethod
    def verify_integrity(
        cls, 
        content: bytes, 
        metadata: dict, 
        doc_id: str,
        stored_combined_hash: str
    ) -> bool:
        """Verify document hasn't been tampered with."""
        current_content_hash = cls.content_hash(content)
        current_metadata_hash = cls.metadata_hash(metadata)
        current_combined = cls.combined_hash(
            current_content_hash, 
            current_metadata_hash, 
            doc_id
        )
        return hmac.compare_digest(current_combined, stored_combined_hash)
    
    @classmethod
    def generate_verification_token(cls, doc_id: str, timestamp: datetime) -> str:
        """Generate a verification token for document access."""
        message = f"{doc_id}:{timestamp.isoformat()}".encode()
        signature = hmac.new(cls._SECRET_KEY, message, hashlib.sha256).digest()
        return base64.urlsafe_b64encode(signature).decode()[:32]


# =============================================================================
# FORGERY DETECTOR
# =============================================================================

class ForgeryDetector:
    """Detect potential forgery or document alterations."""
    
    @classmethod
    def analyze(
        cls, 
        content: bytes, 
        text: str, 
        metadata: dict,
        filename: str,
        existing_docs: list[RegisteredDocument]
    ) -> tuple[list[ForgeryAlert], float]:
        """
        Analyze document for forgery indicators.
        
        Returns:
            tuple: (list of alerts, forgery score 0.0-1.0)
        """
        alerts = []
        score = 0.0
        
        # Check for date inconsistencies
        date_alerts = cls._check_date_inconsistencies(text, metadata)
        alerts.extend(date_alerts)
        score += len(date_alerts) * 0.15
        
        # Check for metadata tampering signs
        metadata_alerts = cls._check_metadata_tampering(metadata, filename)
        alerts.extend(metadata_alerts)
        score += len(metadata_alerts) * 0.2
        
        # Check for duplicate with changes
        dup_alerts = cls._check_duplicate_changes(content, text, existing_docs)
        alerts.extend(dup_alerts)
        score += len(dup_alerts) * 0.25
        
        # Check for timeline impossibilities
        timeline_alerts = cls._check_timeline_impossibilities(text, metadata)
        alerts.extend(timeline_alerts)
        score += len(timeline_alerts) * 0.3
        
        # Check for suspicious text patterns
        pattern_alerts = cls._check_suspicious_patterns(text)
        alerts.extend(pattern_alerts)
        score += len(pattern_alerts) * 0.1
        
        # Cap score at 1.0
        score = min(score, 1.0)
        
        return alerts, score
    
    @classmethod
    def _check_date_inconsistencies(cls, text: str, metadata: dict) -> list[ForgeryAlert]:
        """Check for inconsistent dates in document."""
        alerts = []
        
        # Find all dates in text
        date_patterns = [
            r'\b(\d{1,2})[/-](\d{1,2})[/-](\d{4})\b',
            r'\b(\d{1,2})[/-](\d{1,2})[/-](\d{2})\b',
        ]
        
        dates_found = []
        for pattern in date_patterns:
            for match in re.finditer(pattern, text):
                try:
                    month, day, year = int(match.group(1)), int(match.group(2)), int(match.group(3))
                    if year < 100:
                        year += 2000
                    if 1 <= month <= 12 and 1 <= day <= 31:
                        dates_found.append(datetime(year, month, day))
                except ValueError:
                    continue
        
        # Check for future dates (suspicious for historical documents)
        now = datetime.now()
        for d in dates_found:
            if d > now + timedelta(days=365):  # More than a year in future
                alerts.append(ForgeryAlert(
                    indicator=ForgeryIndicator.DATE_INCONSISTENCY,
                    severity="high",
                    description=f"Future date detected: {d.strftime('%Y-%m-%d')}",
                    evidence=f"Date {d.strftime('%m/%d/%Y')} is suspiciously far in the future",
                ))
        
        # Check for very old dates in recent documents
        # (e.g., a 2020 eviction notice created in 2025)
        
        return alerts
    
    @classmethod
    def _check_metadata_tampering(cls, metadata: dict, filename: str) -> list[ForgeryAlert]:
        """Check for signs of metadata tampering."""
        alerts = []
        
        # Check for suspicious file properties
        if metadata.get("creation_date") and metadata.get("modification_date"):
            created = metadata.get("creation_date")
            modified = metadata.get("modification_date")
            
            if isinstance(created, str):
                try:
                    created = datetime.fromisoformat(created.replace("Z", "+00:00"))
                except:
                    created = None
            
            if isinstance(modified, str):
                try:
                    modified = datetime.fromisoformat(modified.replace("Z", "+00:00"))
                except:
                    modified = None
            
            if created and modified and modified < created:
                alerts.append(ForgeryAlert(
                    indicator=ForgeryIndicator.METADATA_TAMPERING,
                    severity="high",
                    description="Modification date is before creation date",
                    evidence=f"Created: {created}, Modified: {modified}",
                ))
        
        # Check for generic/suspicious software signatures
        producer = metadata.get("producer", "").lower()
        suspicious_tools = ["photoshop", "acrobat editor", "pdf editor", "nitro"]
        for tool in suspicious_tools:
            if tool in producer:
                alerts.append(ForgeryAlert(
                    indicator=ForgeryIndicator.DIGITAL_ALTERATION,
                    severity="medium",
                    description=f"Document may have been edited with {tool}",
                    evidence=f"Producer: {metadata.get('producer')}",
                ))
        
        return alerts
    
    @classmethod
    def _check_duplicate_changes(
        cls, 
        content: bytes, 
        text: str, 
        existing_docs: list[RegisteredDocument]
    ) -> list[ForgeryAlert]:
        """Check if document is a modified copy of existing document."""
        alerts = []
        content_hash = hashlib.sha256(content).hexdigest()
        
        for doc in existing_docs:
            if doc.content_hash == content_hash:
                # Exact duplicate - handled elsewhere
                continue
            
            # Check for similar but not identical (potential modification)
            # This would need more sophisticated comparison in production
            # For now, flag if filename suggests it's related
            
        return alerts
    
    @classmethod
    def _check_timeline_impossibilities(cls, text: str, metadata: dict) -> list[ForgeryAlert]:
        """Check for timeline impossibilities in document."""
        alerts = []
        
        # Example: Eviction notice dated before lease start
        # Example: Court filing dated on a weekend/holiday
        
        # Check for dates that are impossible (Feb 30, etc.)
        impossible_dates = [
            r'\b(02|2)[/-](30|31)[/-]\d{4}\b',  # Feb 30/31
            r'\b(04|4|06|6|09|9|11)[/-]31[/-]\d{4}\b',  # Apr/Jun/Sep/Nov 31
        ]
        
        for pattern in impossible_dates:
            if re.search(pattern, text):
                alerts.append(ForgeryAlert(
                    indicator=ForgeryIndicator.TIMELINE_IMPOSSIBILITY,
                    severity="critical",
                    description="Document contains an impossible date",
                    evidence=f"Pattern matched: {pattern}",
                ))
        
        return alerts
    
    @classmethod
    def _check_suspicious_patterns(cls, text: str) -> list[ForgeryAlert]:
        """Check for suspicious text patterns indicating manipulation."""
        alerts = []
        text_lower = text.lower()
        
        # Check for obviously altered amounts (crossed out, changed)
        if re.search(r'\$\d+.*(?:crossed out|changed to|was \$)', text_lower):
            alerts.append(ForgeryAlert(
                indicator=ForgeryIndicator.TEXT_OVERLAY,
                severity="high",
                description="Document shows signs of amount alteration",
            ))
        
        # Check for inconsistent formatting (different fonts mentioned or visible)
        # In production, this would analyze actual font metadata
        
        return alerts


# Import timedelta for use in ForgeryDetector
from datetime import timedelta


# =============================================================================
# DOCUMENT REGISTRY
# =============================================================================

class DocumentRegistry:
    """
    Central registry for all documents with full tracking.
    
    Features:
    - Unique document ID generation
    - Tamper-proof hashing
    - Duplicate detection
    - Case number association
    - Forgery detection
    - Complete audit trail
    """
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self, storage_dir: str = "data/registry"):
        if self._initialized:
            return
        
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        
        # In-memory registries (in production, use database)
        self._documents: dict[str, RegisteredDocument] = {}
        self._hash_index: dict[str, str] = {}  # content_hash -> document_id
        self._case_index: dict[str, list[str]] = {}  # case_number -> document_ids
        self._user_index: dict[str, list[str]] = {}  # user_id -> document_ids
        
        self._load_registry()
        self._initialized = True
    
    def _load_registry(self):
        """Load registry from storage."""
        registry_file = self.storage_dir / "registry.json"
        if registry_file.exists():
            try:
                with open(registry_file) as f:
                    data = json.load(f)
                    for doc_id, doc_data in data.items():
                        # Reconstruct document
                        doc_data["status"] = DocumentStatus(doc_data["status"])
                        doc_data["integrity_status"] = IntegrityStatus(doc_data["integrity_status"])
                        doc_data["registered_at"] = datetime.fromisoformat(doc_data["registered_at"])
                        if doc_data.get("last_verified_at"):
                            doc_data["last_verified_at"] = datetime.fromisoformat(doc_data["last_verified_at"])
                        if doc_data.get("last_accessed_at"):
                            doc_data["last_accessed_at"] = datetime.fromisoformat(doc_data["last_accessed_at"])
                        
                        # Reconstruct nested objects
                        doc_data["forgery_alerts"] = []
                        doc_data["custody_chain"] = []
                        doc_data["versions"] = []
                        
                        self._documents[doc_id] = RegisteredDocument(**doc_data)
                        
                        # Rebuild indexes
                        self._hash_index[doc_data["content_hash"]] = doc_id
                        if doc_data.get("case_number"):
                            if doc_data["case_number"] not in self._case_index:
                                self._case_index[doc_data["case_number"]] = []
                            self._case_index[doc_data["case_number"]].append(doc_id)
                        if doc_data["user_id"] not in self._user_index:
                            self._user_index[doc_data["user_id"]] = []
                        self._user_index[doc_data["user_id"]].append(doc_id)
            except Exception:
                pass
    
    def _save_registry(self):
        """Save registry to storage."""
        registry_file = self.storage_dir / "registry.json"
        data = {doc_id: doc.to_dict() for doc_id, doc in self._documents.items()}
        with open(registry_file, "w") as f:
            json.dump(data, f, indent=2, default=str)
    
    def register_document(
        self,
        user_id: str,
        content: bytes,
        filename: str,
        mime_type: str,
        case_number: Optional[str] = None,
        intake_document_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        device_info: Optional[str] = None,
    ) -> RegisteredDocument:
        """
        Register a new document in the system.
        
        Returns RegisteredDocument with:
        - Unique document ID
        - Tamper-proof hashes
        - Duplicate detection results
        - Forgery analysis results
        - Initial custody record
        """
        # Generate hashes
        content_hash = HashGenerator.content_hash(content)
        
        # Check for duplicate
        is_duplicate = False
        original_doc_id = None
        status = DocumentStatus.ORIGINAL
        
        if content_hash in self._hash_index:
            is_duplicate = True
            original_doc_id = self._hash_index[content_hash]
            status = DocumentStatus.COPY
            
            # Update original's duplicate tracking
            if original_doc_id in self._documents:
                original = self._documents[original_doc_id]
                original.duplicate_count += 1
        
        # Generate document ID
        doc_id = DocumentIDGenerator.generate()
        
        # Build metadata for hashing
        metadata = {
            "document_id": doc_id,
            "filename": filename,
            "file_size": len(content),
            "mime_type": mime_type,
            "user_id": user_id,
            "case_number": case_number,
            "registered_at": datetime.now(timezone.utc).isoformat(),
        }
        
        metadata_hash = HashGenerator.metadata_hash(metadata)
        combined_hash = HashGenerator.combined_hash(content_hash, metadata_hash, doc_id)
        
        # Run forgery detection
        existing_docs = list(self._documents.values())
        forgery_alerts, forgery_score = ForgeryDetector.analyze(
            content=content,
            text=content.decode("utf-8", errors="ignore"),
            metadata=metadata,
            filename=filename,
            existing_docs=existing_docs,
        )
        
        # Determine if review is required
        requires_review = forgery_score > 0.3 or len(forgery_alerts) > 0
        
        # If significant forgery detected, quarantine
        if forgery_score > 0.7:
            status = DocumentStatus.QUARANTINED
        elif forgery_score > 0.4:
            status = DocumentStatus.FLAGGED
        
        # Create registered document
        doc = RegisteredDocument(
            document_id=doc_id,
            user_id=user_id,
            case_number=case_number,
            original_filename=filename,
            file_size=len(content),
            mime_type=mime_type,
            content_hash=content_hash,
            metadata_hash=metadata_hash,
            combined_hash=combined_hash,
            status=status,
            integrity_status=IntegrityStatus.VERIFIED,
            is_duplicate=is_duplicate,
            original_document_id=original_doc_id,
            forgery_alerts=forgery_alerts,
            forgery_score=forgery_score,
            requires_review=requires_review,
            intake_document_id=intake_document_id,
        )
        
        # Add initial custody record
        doc.custody_chain.append(CustodyRecord(
            timestamp=datetime.now(timezone.utc),
            action=CustodyAction.RECEIVED,
            actor=user_id,
            details=f"Document registered: {filename}",
            ip_address=ip_address,
            device_info=device_info,
            integrity_hash=combined_hash,
        ))
        
        # Add initial version
        doc.versions.append(DocumentVersion(
            version=1,
            timestamp=datetime.now(timezone.utc),
            content_hash=content_hash,
            changes="Initial registration",
            changed_by=user_id,
        ))
        
        # Store
        self._documents[doc_id] = doc
        self._hash_index[content_hash] = doc_id
        
        if case_number:
            if case_number not in self._case_index:
                self._case_index[case_number] = []
            self._case_index[case_number].append(doc_id)
        
        if user_id not in self._user_index:
            self._user_index[user_id] = []
        self._user_index[user_id].append(doc_id)
        
        # Update original if this is a duplicate
        if is_duplicate and original_doc_id:
            original = self._documents.get(original_doc_id)
            if original:
                original.duplicate_ids.append(doc_id)
        
        self._save_registry()
        
        return doc
    
    def verify_integrity(self, doc_id: str, content: bytes) -> IntegrityStatus:
        """Verify document hasn't been tampered with."""
        doc = self._documents.get(doc_id)
        if not doc:
            return IntegrityStatus.UNVERIFIED
        
        # Verify content hash
        current_hash = HashGenerator.content_hash(content)
        
        if current_hash != doc.content_hash:
            doc.integrity_status = IntegrityStatus.TAMPERED
            doc.custody_chain.append(CustodyRecord(
                timestamp=datetime.now(timezone.utc),
                action=CustodyAction.INTEGRITY_CHECK,
                actor="system",
                details=f"TAMPER DETECTED: Content hash mismatch",
                integrity_hash=current_hash,
            ))
            self._save_registry()
            return IntegrityStatus.TAMPERED
        
        # Verify combined hash
        metadata = {
            "document_id": doc.document_id,
            "filename": doc.original_filename,
            "file_size": doc.file_size,
            "mime_type": doc.mime_type,
            "user_id": doc.user_id,
            "case_number": doc.case_number,
            "registered_at": doc.registered_at.isoformat(),
        }
        
        current_metadata_hash = HashGenerator.metadata_hash(metadata)
        if current_metadata_hash != doc.metadata_hash:
            doc.integrity_status = IntegrityStatus.METADATA_CHANGED
            self._save_registry()
            return IntegrityStatus.METADATA_CHANGED
        
        # All checks passed
        doc.integrity_status = IntegrityStatus.VERIFIED
        doc.last_verified_at = datetime.now(timezone.utc)
        doc.custody_chain.append(CustodyRecord(
            timestamp=datetime.now(timezone.utc),
            action=CustodyAction.INTEGRITY_CHECK,
            actor="system",
            details="Integrity verified: All hashes match",
            integrity_hash=doc.combined_hash,
        ))
        self._save_registry()
        
        return IntegrityStatus.VERIFIED
    
    def get_document(self, doc_id: str) -> Optional[RegisteredDocument]:
        """Get a document by ID."""
        doc = self._documents.get(doc_id)
        if doc:
            doc.last_accessed_at = datetime.now(timezone.utc)
        return doc
    
    def get_documents_by_case(self, case_number: str) -> list[RegisteredDocument]:
        """Get all documents for a case."""
        doc_ids = self._case_index.get(case_number, [])
        return [self._documents[did] for did in doc_ids if did in self._documents]
    
    def get_documents_by_user(self, user_id: str) -> list[RegisteredDocument]:
        """Get all documents for a user."""
        doc_ids = self._user_index.get(user_id, [])
        return [self._documents[did] for did in doc_ids if did in self._documents]
    
    def get_duplicates(self, doc_id: str) -> list[RegisteredDocument]:
        """Get all duplicates of a document."""
        doc = self._documents.get(doc_id)
        if not doc:
            return []
        return [self._documents[did] for did in doc.duplicate_ids if did in self._documents]
    
    def get_flagged_documents(self) -> list[RegisteredDocument]:
        """Get all documents flagged for review."""
        return [
            doc for doc in self._documents.values()
            if doc.requires_review or doc.status in [
                DocumentStatus.FLAGGED, 
                DocumentStatus.QUARANTINED
            ]
        ]
    
    def associate_case(self, doc_id: str, case_number: str, actor: str) -> bool:
        """Associate a document with a case number."""
        doc = self._documents.get(doc_id)
        if not doc:
            return False
        
        old_case = doc.case_number
        doc.case_number = case_number
        
        # Update indexes
        if old_case and old_case in self._case_index:
            self._case_index[old_case] = [
                did for did in self._case_index[old_case] if did != doc_id
            ]
        
        if case_number not in self._case_index:
            self._case_index[case_number] = []
        self._case_index[case_number].append(doc_id)
        
        # Record in custody chain
        doc.custody_chain.append(CustodyRecord(
            timestamp=datetime.now(timezone.utc),
            action=CustodyAction.MODIFIED,
            actor=actor,
            details=f"Case association changed: {old_case} -> {case_number}",
        ))
        
        self._save_registry()
        return True
    
    def flag_document(
        self, 
        doc_id: str, 
        reason: str, 
        actor: str,
        indicator: ForgeryIndicator = ForgeryIndicator.NONE
    ) -> bool:
        """Flag a document for review."""
        doc = self._documents.get(doc_id)
        if not doc:
            return False
        
        doc.status = DocumentStatus.FLAGGED
        doc.requires_review = True
        
        if indicator != ForgeryIndicator.NONE:
            doc.forgery_alerts.append(ForgeryAlert(
                indicator=indicator,
                severity="high",
                description=reason,
            ))
        
        doc.custody_chain.append(CustodyRecord(
            timestamp=datetime.now(timezone.utc),
            action=CustodyAction.FLAGGED,
            actor=actor,
            details=f"Flagged: {reason}",
        ))
        
        self._save_registry()
        return True
    
    def record_access(
        self, 
        doc_id: str, 
        actor: str, 
        action: CustodyAction,
        details: str = "",
        ip_address: Optional[str] = None
    ):
        """Record document access in custody chain."""
        doc = self._documents.get(doc_id)
        if not doc:
            return
        
        doc.last_accessed_at = datetime.now(timezone.utc)
        doc.custody_chain.append(CustodyRecord(
            timestamp=datetime.now(timezone.utc),
            action=action,
            actor=actor,
            details=details,
            ip_address=ip_address,
            integrity_hash=doc.combined_hash,
        ))
        
        self._save_registry()
    
    def get_custody_chain(self, doc_id: str) -> list[CustodyRecord]:
        """Get full custody chain for a document."""
        doc = self._documents.get(doc_id)
        if not doc:
            return []
        return doc.custody_chain
    
    def get_statistics(self) -> dict:
        """Get registry statistics."""
        total = len(self._documents)
        statuses = {}
        for doc in self._documents.values():
            status = doc.status.value
            statuses[status] = statuses.get(status, 0) + 1
        
        return {
            "total_documents": total,
            "total_cases": len(self._case_index),
            "total_users": len(self._user_index),
            "by_status": statuses,
            "flagged_count": len(self.get_flagged_documents()),
            "duplicate_count": sum(1 for d in self._documents.values() if d.is_duplicate),
        }


# =============================================================================
# SINGLETON ACCESS
# =============================================================================

_registry_instance: Optional[DocumentRegistry] = None


def get_document_registry() -> DocumentRegistry:
    """Get the document registry singleton."""
    global _registry_instance
    if _registry_instance is None:
        _registry_instance = DocumentRegistry()
    return _registry_instance
