"""
Vault Upload Service - Centralized Document Upload Handler

ALL document uploads from ANY module go through this service.
Documents are stored in the user's vault first, then modules access them from vault.

Flow:
1. Any module calls vault_upload_service.upload()
2. Document is stored in user's cloud storage vault (.semptify/vault/)
3. Document metadata is indexed locally for fast queries
4. Modules access documents via vault_id reference

This ensures:
- Single source of truth for all documents
- User owns their data in their cloud storage
- Modules can reference documents without storing duplicates
- Consistent security and certification across all uploads
"""

import hashlib
import json
import uuid
import logging
from datetime import datetime, timezone
from typing import Optional
from dataclasses import dataclass, asdict
from pathlib import Path

logger = logging.getLogger(__name__)

# Import storage provider
try:
    from app.services.storage import get_provider, StorageFile
    HAS_STORAGE = True
except ImportError:
    HAS_STORAGE = False
    logger.warning("Storage provider not available - using local fallback")


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class VaultDocument:
    """A document stored in user's vault."""
    vault_id: str  # Primary identifier
    user_id: str
    filename: str  # Original filename
    safe_filename: str  # Safe filename in vault (uuid.ext)
    sha256_hash: str
    file_size: int
    mime_type: str
    document_type: Optional[str]  # lease, notice, photo, etc.
    description: Optional[str]
    tags: list[str]
    storage_path: str  # Path in cloud storage
    storage_provider: str  # google_drive, dropbox, onedrive, local
    certificate_id: Optional[str]
    uploaded_at: str
    # Processing state
    processed: bool = False
    extracted_data: Optional[dict] = None
    # Source tracking
    source_module: str = "direct"  # Which module initiated upload
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> "VaultDocument":
        return cls(**data)


# =============================================================================
# Vault Document Index (Local cache for fast queries)
# =============================================================================

class VaultDocumentIndex:
    """Local index of vault documents for fast queries without hitting cloud storage."""
    
    def __init__(self, data_dir: str = "data/vault_index"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._documents: dict[str, VaultDocument] = {}
        self._user_index: dict[str, list[str]] = {}  # user_id -> [vault_ids]
        self._hash_index: dict[str, str] = {}  # sha256 -> vault_id (dedup)
        self._load()
    
    def _load(self):
        """Load index from disk."""
        index_file = self.data_dir / "vault_index.json"
        if index_file.exists():
            try:
                with open(index_file) as f:
                    data = json.load(f)
                for vault_id, doc_data in data.get("documents", {}).items():
                    doc = VaultDocument.from_dict(doc_data)
                    self._documents[vault_id] = doc
                    # Build user index
                    if doc.user_id not in self._user_index:
                        self._user_index[doc.user_id] = []
                    self._user_index[doc.user_id].append(vault_id)
                    # Build hash index
                    self._hash_index[doc.sha256_hash] = vault_id
            except Exception as e:
                logger.error(f"Failed to load vault index: {e}")
    
    def _save(self):
        """Save index to disk."""
        index_file = self.data_dir / "vault_index.json"
        data = {
            "documents": {vid: doc.to_dict() for vid, doc in self._documents.items()},
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        with open(index_file, "w") as f:
            json.dump(data, f, indent=2)
    
    def add(self, doc: VaultDocument) -> None:
        """Add document to index."""
        self._documents[doc.vault_id] = doc
        if doc.user_id not in self._user_index:
            self._user_index[doc.user_id] = []
        self._user_index[doc.user_id].append(doc.vault_id)
        self._hash_index[doc.sha256_hash] = doc.vault_id
        self._save()
    
    def get(self, vault_id: str) -> Optional[VaultDocument]:
        """Get document by vault ID."""
        return self._documents.get(vault_id)
    
    def get_by_hash(self, sha256_hash: str) -> Optional[VaultDocument]:
        """Find document by hash (deduplication)."""
        vault_id = self._hash_index.get(sha256_hash)
        return self._documents.get(vault_id) if vault_id else None
    
    def get_user_documents(self, user_id: str, document_type: Optional[str] = None) -> list[VaultDocument]:
        """Get all documents for a user, optionally filtered by type."""
        vault_ids = self._user_index.get(user_id, [])
        docs = [self._documents[vid] for vid in vault_ids if vid in self._documents]
        if document_type:
            docs = [d for d in docs if d.document_type == document_type]
        return docs
    
    def update(self, vault_id: str, **kwargs) -> Optional[VaultDocument]:
        """Update document metadata."""
        doc = self._documents.get(vault_id)
        if doc:
            for key, value in kwargs.items():
                if hasattr(doc, key):
                    setattr(doc, key, value)
            self._save()
        return doc
    
    def delete(self, vault_id: str) -> bool:
        """Remove document from index (does not delete from storage)."""
        doc = self._documents.pop(vault_id, None)
        if doc:
            if doc.user_id in self._user_index:
                self._user_index[doc.user_id] = [
                    vid for vid in self._user_index[doc.user_id] if vid != vault_id
                ]
            self._hash_index.pop(doc.sha256_hash, None)
            self._save()
            return True
        return False


# =============================================================================
# Vault Upload Service
# =============================================================================

class VaultUploadService:
    """
    Centralized service for all document uploads.
    Routes uploads to user's vault, then modules access from there.
    """
    
    VAULT_FOLDER = ".semptify/vault"
    CERTS_FOLDER = ".semptify/vault/certificates"
    LOCAL_FALLBACK_DIR = "data/vault_storage"
    
    def __init__(self):
        self.index = VaultDocumentIndex()
        # Local fallback storage
        self._local_dir = Path(self.LOCAL_FALLBACK_DIR)
        self._local_dir.mkdir(parents=True, exist_ok=True)
    
    def _compute_sha256(self, content: bytes) -> str:
        """Compute SHA-256 hash of file content."""
        return hashlib.sha256(content).hexdigest()
    
    def _get_safe_filename(self, vault_id: str, original_filename: str) -> str:
        """Generate safe filename for storage."""
        ext = original_filename.rsplit(".", 1)[-1].lower() if "." in original_filename else "bin"
        return f"{vault_id}.{ext}"
    
    async def _ensure_folders(self, storage) -> None:
        """Ensure vault folders exist in storage."""
        try:
            await storage.create_folder(".semptify")
            await storage.create_folder(self.VAULT_FOLDER)
            await storage.create_folder(self.CERTS_FOLDER)
        except Exception as e:
            logger.warning(f"Could not create folders: {e}")
    
    async def upload(
        self,
        user_id: str,
        filename: str,
        content: bytes,
        mime_type: str,
        document_type: Optional[str] = None,
        description: Optional[str] = None,
        tags: Optional[list[str]] = None,
        source_module: str = "direct",
        access_token: Optional[str] = None,
        storage_provider: str = "local",
    ) -> VaultDocument:
        """
        Upload a document to user's vault.
        
        This is THE method all modules should call to store documents.
        
        Args:
            user_id: User ID
            filename: Original filename
            content: File content bytes
            mime_type: MIME type
            document_type: Type of document (lease, notice, photo, etc.)
            description: Optional description
            tags: Optional tags list
            source_module: Which module initiated upload (intake, briefcase, etc.)
            access_token: Cloud storage access token (if using cloud storage)
            storage_provider: Storage provider (google_drive, dropbox, onedrive, local)
        
        Returns:
            VaultDocument with vault_id and storage details
        """
        # Compute hash for deduplication
        sha256_hash = self._compute_sha256(content)
        
        # Check for duplicate
        existing = self.index.get_by_hash(sha256_hash)
        if existing and existing.user_id == user_id:
            logger.info(f"Document already in vault: {existing.vault_id}")
            return existing
        
        # Generate IDs
        vault_id = str(uuid.uuid4())
        safe_filename = self._get_safe_filename(vault_id, filename)
        file_size = len(content)
        now = datetime.now(timezone.utc).isoformat()
        
        # Store document
        storage_path = await self._store_document(
            vault_id=vault_id,
            user_id=user_id,
            safe_filename=safe_filename,
            content=content,
            mime_type=mime_type,
            access_token=access_token,
            storage_provider=storage_provider,
        )
        
        # Create certificate
        certificate_id = await self._create_certificate(
            vault_id=vault_id,
            user_id=user_id,
            original_filename=filename,
            sha256_hash=sha256_hash,
            file_size=file_size,
            mime_type=mime_type,
            document_type=document_type,
            storage_path=storage_path,
            storage_provider=storage_provider,
            access_token=access_token,
        )
        
        # Create vault document record
        doc = VaultDocument(
            vault_id=vault_id,
            user_id=user_id,
            filename=filename,
            safe_filename=safe_filename,
            sha256_hash=sha256_hash,
            file_size=file_size,
            mime_type=mime_type,
            document_type=document_type,
            description=description,
            tags=tags or [],
            storage_path=storage_path,
            storage_provider=storage_provider,
            certificate_id=certificate_id,
            uploaded_at=now,
            source_module=source_module,
        )
        
        # Add to index
        self.index.add(doc)
        
        logger.info(f"📁 Document uploaded to vault: {vault_id} ({filename}) via {source_module}")
        
        # Emit event for other modules
        await self._emit_upload_event(doc)
        
        return doc
    
    async def _store_document(
        self,
        vault_id: str,
        user_id: str,
        safe_filename: str,
        content: bytes,
        mime_type: str,
        access_token: Optional[str],
        storage_provider: str,
    ) -> str:
        """Store document in user's storage (cloud or local fallback)."""
        
        # Try cloud storage if available
        if HAS_STORAGE and storage_provider != "local" and access_token:
            try:
                storage = get_provider(storage_provider, access_token=access_token)
                await self._ensure_folders(storage)
                
                await storage.upload_file(
                    file_content=content,
                    destination_path=self.VAULT_FOLDER,
                    filename=safe_filename,
                    mime_type=mime_type,
                )
                return f"{self.VAULT_FOLDER}/{safe_filename}"
            except Exception as e:
                logger.warning(f"Cloud storage failed, using local fallback: {e}")
        
        # Local fallback
        user_dir = self._local_dir / user_id
        user_dir.mkdir(parents=True, exist_ok=True)
        file_path = user_dir / safe_filename
        file_path.write_bytes(content)
        return str(file_path)
    
    async def _create_certificate(
        self,
        vault_id: str,
        user_id: str,
        original_filename: str,
        sha256_hash: str,
        file_size: int,
        mime_type: str,
        document_type: Optional[str],
        storage_path: str,
        storage_provider: str,
        access_token: Optional[str],
    ) -> Optional[str]:
        """Create certification record for document."""
        certificate_id = f"cert_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{vault_id[:8]}"
        
        certificate = {
            "certificate_id": certificate_id,
            "vault_id": vault_id,
            "sha256": sha256_hash,
            "original_filename": original_filename,
            "file_size": file_size,
            "mime_type": mime_type,
            "document_type": document_type,
            "certified_at": datetime.now(timezone.utc).isoformat(),
            "storage_path": storage_path,
            "storage_provider": storage_provider,
            "user_id": user_id,
            "version": "5.0",
            "platform": "Semptify Vault Service",
        }
        
        cert_content = json.dumps(certificate, indent=2).encode("utf-8")
        
        # Try cloud storage
        if HAS_STORAGE and storage_provider != "local" and access_token:
            try:
                storage = get_provider(storage_provider, access_token=access_token)
                await storage.upload_file(
                    file_content=cert_content,
                    destination_path=self.CERTS_FOLDER,
                    filename=f"{certificate_id}.json",
                    mime_type="application/json",
                )
                return certificate_id
            except Exception as e:
                logger.warning(f"Cloud cert storage failed: {e}")
        
        # Local fallback
        user_dir = self._local_dir / user_id / "certificates"
        user_dir.mkdir(parents=True, exist_ok=True)
        cert_path = user_dir / f"{certificate_id}.json"
        cert_path.write_bytes(cert_content)
        return certificate_id
    
    async def _emit_upload_event(self, doc: VaultDocument) -> None:
        """Emit event for document upload so other modules can react."""
        try:
            from app.core.event_bus import event_bus, EventType
            await event_bus.publish(
                EventType.DOCUMENT_ADDED,
                {
                    "vault_id": doc.vault_id,
                    "user_id": doc.user_id,
                    "filename": doc.filename,
                    "document_type": doc.document_type,
                    "storage_path": doc.storage_path,
                    "source_module": doc.source_module,
                },
                user_id=doc.user_id,
            )
        except Exception as e:
            logger.debug(f"Event emission failed: {e}")
    
    # =========================================================================
    # Document Access Methods (for modules to use)
    # =========================================================================
    
    def get_document(self, vault_id: str) -> Optional[VaultDocument]:
        """Get document metadata by vault ID."""
        return self.index.get(vault_id)
    
    def get_user_documents(
        self,
        user_id: str,
        document_type: Optional[str] = None
    ) -> list[VaultDocument]:
        """Get all documents for a user."""
        return self.index.get_user_documents(user_id, document_type)
    
    async def get_document_content(
        self,
        vault_id: str,
        access_token: Optional[str] = None,
    ) -> Optional[bytes]:
        """
        Get document content from storage.
        Modules call this to read document content from vault.
        """
        doc = self.index.get(vault_id)
        if not doc:
            return None
        
        # Try cloud storage
        if HAS_STORAGE and doc.storage_provider != "local" and access_token:
            try:
                storage = get_provider(doc.storage_provider, access_token=access_token)
                result = await storage.download_file(doc.storage_path)
                if result:
                    return result
            except Exception as e:
                logger.warning(f"Cloud download failed: {e}")
        
        # Local fallback
        local_path = Path(doc.storage_path)
        if local_path.exists():
            return local_path.read_bytes()
        
        return None
    
    def mark_processed(
        self,
        vault_id: str,
        extracted_data: Optional[dict] = None
    ) -> Optional[VaultDocument]:
        """Mark document as processed and store extracted data."""
        return self.index.update(
            vault_id,
            processed=True,
            extracted_data=extracted_data
        )
    
    def update_document_type(
        self,
        vault_id: str,
        document_type: str
    ) -> Optional[VaultDocument]:
        """Update document type after classification."""
        return self.index.update(vault_id, document_type=document_type)


# =============================================================================
# Module-level singleton
# =============================================================================

_vault_service: Optional[VaultUploadService] = None


def get_vault_service() -> VaultUploadService:
    """Get or create the vault upload service singleton."""
    global _vault_service
    if _vault_service is None:
        _vault_service = VaultUploadService()
    return _vault_service
