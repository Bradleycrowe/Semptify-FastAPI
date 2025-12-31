"""
Document Vault Router (Cloud Storage Version)
Secure document upload to user's cloud storage with certification.

Semptify 5.0 Architecture:
- ALL DOCUMENTS GO TO VAULT FIRST
- Documents stored in USER's cloud storage (Google Drive, Dropbox, OneDrive)
- Modules access documents FROM the vault
- User must be authenticated via storage OAuth
- Certificates stored alongside documents in .semptify/vault/
"""

import hashlib
import json
import uuid
import logging
from datetime import datetime, timezone
from typing import Optional, List

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status, Query
from pydantic import BaseModel, Field

from app.core.config import Settings, get_settings
from app.core.security import require_user, rate_limit_dependency, StorageUser
from app.services.storage import get_provider, StorageFile

# Import vault upload service - central document storage
try:
    from app.services.vault_upload_service import get_vault_service, VaultDocument
    HAS_VAULT_SERVICE = True
except ImportError:
    HAS_VAULT_SERVICE = False

logger = logging.getLogger(__name__)

router = APIRouter()


# =============================================================================
# Schemas
# =============================================================================

class DocumentMetadata(BaseModel):
    """Document metadata for upload."""
    document_type: Optional[str] = Field(None, description="Type: lease, notice, photo, receipt, other")
    description: Optional[str] = Field(None, description="Description of the document")
    tags: Optional[str] = Field(None, description="Comma-separated tags")
    event_date: Optional[str] = Field(None, description="Date related to this document (ISO format)")


class DocumentResponse(BaseModel):
    """Response after document upload."""
    id: str
    filename: str
    original_filename: str
    file_size: int
    mime_type: str
    sha256_hash: str
    certificate_id: str
    uploaded_at: str
    document_type: Optional[str] = None
    storage_provider: str
    storage_path: str


class DocumentListResponse(BaseModel):
    """List of documents."""
    documents: list[DocumentResponse]
    total: int
    storage_provider: str


class CertificateResponse(BaseModel):
    """Document certification details."""
    document_id: str
    sha256_hash: str
    certified_at: str
    original_filename: str
    file_size: int
    request_id: str
    storage_provider: str


# =============================================================================
# Constants
# =============================================================================

VAULT_FOLDER = ".semptify/vault"
CERTS_FOLDER = ".semptify/vault/certificates"


# =============================================================================
# Helper Functions
# =============================================================================

def compute_sha256(file_content: bytes) -> str:
    """Compute SHA-256 hash of file content."""
    return hashlib.sha256(file_content).hexdigest()


def is_allowed_extension(filename: str, settings: Settings) -> bool:
    """Check if file extension is allowed."""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return ext in settings.allowed_extensions_set


async def ensure_vault_folders(storage, provider_name: str) -> None:
    """Ensure vault folders exist in user's storage."""
    await storage.create_folder(".semptify")
    await storage.create_folder(VAULT_FOLDER)
    await storage.create_folder(CERTS_FOLDER)


# =============================================================================
# Endpoints
# =============================================================================

@router.post(
    "/upload",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limit_dependency("vault-upload", window=60, max_requests=20))],
)
async def upload_document(
    file: UploadFile = File(...),
    document_type: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    tags: Optional[str] = Form(None),
    access_token: str = Form(..., description="Storage provider access token"),
    user: StorageUser = Depends(require_user),
    settings: Settings = Depends(get_settings),
):
    """
    Upload a document to the user's cloud storage vault.

    The document is stored in the user's connected cloud storage (not on server):
    - File: .semptify/vault/{document_id}.{ext}
    - Certificate: .semptify/vault/certificates/cert_{document_id}.json
    
    Requires:
    - User authenticated via storage OAuth
    - access_token: Current access token for user's storage provider
    """
    # Validate file
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename required")

    if not is_allowed_extension(file.filename, settings):
        raise HTTPException(
            status_code=400,
            detail=f"File type not allowed. Allowed: {settings.allowed_extensions}",
        )

    # Read file content
    content = await file.read()
    file_size = len(content)

    # Check size limit
    max_size = settings.max_upload_size_mb * 1024 * 1024
    if file_size > max_size:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum: {settings.max_upload_size_mb}MB",
        )

    # Generate IDs and hash
    document_id = str(uuid.uuid4())
    sha256_hash = compute_sha256(content)

    # Determine safe filename
    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else "bin"
    safe_filename = f"{document_id}.{ext}"

    # Get storage provider for user
    try:
        storage = get_provider(user.provider, access_token=access_token)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Ensure vault folders exist and upload file
    try:
        await ensure_vault_folders(storage, user.provider)

        # Upload file to user's storage
        storage_path = f"{VAULT_FOLDER}/{safe_filename}"
        await storage.upload_file(
            file_content=content,
            destination_path=VAULT_FOLDER,
            filename=safe_filename,
            mime_type=file.content_type or "application/octet-stream",
        )
    except Exception as e:
        # Storage authentication or access errors
        error_msg = str(e)
        if "401" in error_msg or "Unauthorized" in error_msg or "access" in error_msg.lower():
            raise HTTPException(status_code=401, detail=f"Storage authentication failed: {error_msg}")
        elif "403" in error_msg or "Forbidden" in error_msg:
            raise HTTPException(status_code=403, detail=f"Storage access denied: {error_msg}")
        else:
            raise HTTPException(status_code=500, detail=f"Storage error: {error_msg}")

    # Create certificate
    certificate_id = f"cert_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{document_id[:8]}"
    certificate = {
        "certificate_id": certificate_id,
        "document_id": document_id,
        "sha256": sha256_hash,
        "original_filename": file.filename,
        "file_size": file_size,
        "mime_type": file.content_type or "application/octet-stream",
        "document_type": document_type,
        "description": description,
        "tags": tags.split(",") if tags else [],
        "certified_at": datetime.now(timezone.utc).isoformat(),
        "request_id": str(uuid.uuid4()),
        "storage_path": storage_path,
        "storage_provider": user.provider,
        "user_id": user.user_id,
        "version": "5.0",
        "platform": "Semptify FastAPI Cloud Storage",
    }

    # Upload certificate to user's storage
    cert_content = json.dumps(certificate, indent=2).encode("utf-8")
    try:
        await storage.upload_file(
            file_content=cert_content,
            destination_path=CERTS_FOLDER,
            filename=f"{certificate_id}.json",
            mime_type="application/json",
        )
    except Exception as e:
        # Certificate upload failed, but file was already uploaded
        # Log this but don't fail the request
        pass

    # Build response
    return DocumentResponse(
        id=document_id,
        filename=safe_filename,
        original_filename=file.filename,
        file_size=file_size,
        mime_type=file.content_type or "application/octet-stream",
        sha256_hash=sha256_hash,
        certificate_id=certificate_id,
        uploaded_at=datetime.now(timezone.utc).isoformat(),
        document_type=document_type,
        storage_provider=user.provider,
        storage_path=storage_path,
    )


@router.post(
    "/copy-from-sync",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limit_dependency("vault-copy", window=60, max_requests=20))],
)
async def copy_from_sync_to_vault(
    file_id: str = Form(..., description="File ID from cloud sync storage"),
    filename: str = Form(..., description="Original filename"),
    document_type: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    tags: Optional[str] = Form(None),
    access_token: str = Form(..., description="Storage provider access token"),
    user: StorageUser = Depends(require_user),
    settings: Settings = Depends(get_settings),
):
    """
    Copy a document from sync storage (.semptify/documents/) to vault (.semptify/vault/).
    
    This is used when the original File object is no longer available (e.g., after page refresh)
    but the document was already uploaded to cloud storage via the sync endpoint.
    """
    # Get storage provider for user
    try:
        storage = get_provider(user.provider, access_token=access_token)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Try to download from sync documents folder
    sync_path = f".semptify/documents/{filename}"
    
    try:
        content = await storage.download_file(sync_path)
    except Exception as e:
        # Try alternative paths
        try:
            content = await storage.download_file(f".semptify/documents/{file_id}")
        except Exception:
            raise HTTPException(
                status_code=404, 
                detail=f"Could not find document in cloud storage. Path tried: {sync_path}"
            )
    
    if not content:
        raise HTTPException(status_code=404, detail="Document content is empty")
    
    file_size = len(content)
    
    # Check size limit
    max_size = settings.max_upload_size_mb * 1024 * 1024
    if file_size > max_size:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum: {settings.max_upload_size_mb}MB",
        )

    # Generate IDs and hash
    document_id = str(uuid.uuid4())
    sha256_hash = compute_sha256(content)

    # Determine safe filename
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "bin"
    safe_filename = f"{document_id}.{ext}"
    
    # Detect mime type from extension
    mime_types = {
        "pdf": "application/pdf",
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "png": "image/png",
        "gif": "image/gif",
        "doc": "application/msword",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "txt": "text/plain",
    }
    mime_type = mime_types.get(ext, "application/octet-stream")

    # Ensure vault folders exist and upload file
    try:
        await ensure_vault_folders(storage, user.provider)

        # Upload file to user's vault
        storage_path = f"{VAULT_FOLDER}/{safe_filename}"
        await storage.upload_file(
            file_content=content,
            destination_path=VAULT_FOLDER,
            filename=safe_filename,
            mime_type=mime_type,
        )
    except Exception as e:
        error_msg = str(e)
        if "401" in error_msg or "Unauthorized" in error_msg or "access" in error_msg.lower():
            raise HTTPException(status_code=401, detail=f"Storage authentication failed: {error_msg}")
        elif "403" in error_msg or "Forbidden" in error_msg:
            raise HTTPException(status_code=403, detail=f"Storage access denied: {error_msg}")
        else:
            raise HTTPException(status_code=500, detail=f"Storage error: {error_msg}")

    # Create certificate
    certificate_id = f"cert_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{document_id[:8]}"
    certificate = {
        "certificate_id": certificate_id,
        "document_id": document_id,
        "sha256": sha256_hash,
        "original_filename": filename,
        "file_size": file_size,
        "mime_type": mime_type,
        "document_type": document_type,
        "description": description,
        "tags": tags.split(",") if tags else [],
        "certified_at": datetime.now(timezone.utc).isoformat(),
        "request_id": str(uuid.uuid4()),
        "storage_path": storage_path,
        "storage_provider": user.provider,
        "user_id": user.user_id,
        "version": "5.0",
        "platform": "Semptify FastAPI Cloud Storage",
        "source": "copy-from-sync",
        "source_path": sync_path,
    }

    # Upload certificate to user's storage
    cert_content = json.dumps(certificate, indent=2).encode("utf-8")
    try:
        await storage.upload_file(
            file_content=cert_content,
            destination_path=CERTS_FOLDER,
            filename=f"{certificate_id}.json",
            mime_type="application/json",
        )
    except Exception:
        pass  # Certificate upload failed but file was uploaded

    return DocumentResponse(
        id=document_id,
        filename=safe_filename,
        original_filename=filename,
        file_size=file_size,
        mime_type=mime_type,
        sha256_hash=sha256_hash,
        certificate_id=certificate_id,
        uploaded_at=datetime.now(timezone.utc).isoformat(),
        document_type=document_type,
        storage_provider=user.provider,
        storage_path=storage_path,
    )


@router.get("/", response_model=DocumentListResponse)
async def list_documents(
    document_type: Optional[str] = None,
    access_token: str = None,
    user: StorageUser = Depends(require_user),
    settings: Settings = Depends(get_settings),
):
    """
    List all documents in the user's cloud storage vault.
    
    Reads certificates from .semptify/vault/certificates/ in user's storage.
    """
    if not access_token:
        raise HTTPException(status_code=400, detail="access_token required")

    try:
        storage = get_provider(user.provider, access_token=access_token)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    documents = []

    # List certificate files from user's storage
    try:
        cert_files = await storage.list_files(CERTS_FOLDER)
    except Exception:
        # Folder might not exist yet
        cert_files = []

    for cert_file in cert_files:
        if not cert_file.name.endswith(".json"):
            continue

        try:
            cert_content = await storage.download_file(f"{CERTS_FOLDER}/{cert_file.name}")
            cert = json.loads(cert_content.decode("utf-8"))

            # Filter by type if specified
            if document_type and cert.get("document_type") != document_type:
                continue

            documents.append(DocumentResponse(
                id=cert.get("document_id", ""),
                filename=f"{cert.get('document_id', '')}.{cert.get('original_filename', '').rsplit('.', 1)[-1]}",
                original_filename=cert.get("original_filename", ""),
                file_size=cert.get("file_size", 0),
                mime_type=cert.get("mime_type", "application/octet-stream"),
                sha256_hash=cert.get("sha256", ""),
                certificate_id=cert.get("certificate_id", ""),
                uploaded_at=cert.get("certified_at", ""),
                document_type=cert.get("document_type"),
                storage_provider=cert.get("storage_provider", user.provider),
                storage_path=cert.get("storage_path", ""),
            ))
        except Exception:
            continue

    # Sort by upload date, newest first
    documents.sort(key=lambda d: d.uploaded_at, reverse=True)

    return DocumentListResponse(
        documents=documents,
        total=len(documents),
        storage_provider=user.provider,
    )


@router.get("/{document_id}/download")
async def download_document(
    document_id: str,
    access_token: str = None,
    user: StorageUser = Depends(require_user),
    settings: Settings = Depends(get_settings),
):
    """
    Download a document from the user's cloud storage vault.
    
    Returns the file content and original filename.
    """
    if not access_token:
        raise HTTPException(status_code=400, detail="access_token required")

    try:
        storage = get_provider(user.provider, access_token=access_token)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Find certificate to get file info
    cert_files = await storage.list_files(CERTS_FOLDER)
    target_cert = None

    for cert_file in cert_files:
        if document_id[:8] in cert_file.name:
            cert_content = await storage.download_file(f"{CERTS_FOLDER}/{cert_file.name}")
            cert = json.loads(cert_content.decode("utf-8"))
            if cert.get("document_id") == document_id:
                target_cert = cert
                break

    if not target_cert:
        raise HTTPException(status_code=404, detail="Document not found")

    # Download file from storage
    storage_path = target_cert.get("storage_path", "")
    if not storage_path:
        raise HTTPException(status_code=404, detail="Document path not found")

    file_content = await storage.download_file(storage_path)

    from fastapi.responses import Response
    return Response(
        content=file_content,
        media_type=target_cert.get("mime_type", "application/octet-stream"),
        headers={
            "Content-Disposition": f'attachment; filename="{target_cert.get("original_filename", "document")}"'
        },
    )


@router.get("/{document_id}/certificate", response_model=CertificateResponse)
async def get_certificate(
    document_id: str,
    access_token: str = None,
    user: StorageUser = Depends(require_user),
    settings: Settings = Depends(get_settings),
):
    """
    Get the certification details for a document.
    """
    if not access_token:
        raise HTTPException(status_code=400, detail="access_token required")

    try:
        storage = get_provider(user.provider, access_token=access_token)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Find certificate
    cert_files = await storage.list_files(CERTS_FOLDER)

    for cert_file in cert_files:
        if document_id[:8] in cert_file.name:
            cert_content = await storage.download_file(f"{CERTS_FOLDER}/{cert_file.name}")
            cert = json.loads(cert_content.decode("utf-8"))
            if cert.get("document_id") == document_id:
                return CertificateResponse(
                    document_id=cert.get("document_id", document_id),
                    sha256_hash=cert.get("sha256", ""),
                    certified_at=cert.get("certified_at", ""),
                    original_filename=cert.get("original_filename", ""),
                    file_size=cert.get("file_size", 0),
                    request_id=cert.get("request_id", ""),
                    storage_provider=cert.get("storage_provider", user.provider),
                )

    raise HTTPException(status_code=404, detail="Certificate not found")


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: str,
    access_token: str = None,
    user: StorageUser = Depends(require_user),
    settings: Settings = Depends(get_settings),
):
    """
    Delete a document from the user's cloud storage vault.
    Note: Certificates are kept for audit trail.
    """
    if not access_token:
        raise HTTPException(status_code=400, detail="access_token required")

    try:
        storage = get_provider(user.provider, access_token=access_token)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Find certificate to get file path
    cert_files = await storage.list_files(CERTS_FOLDER)

    for cert_file in cert_files:
        if document_id[:8] in cert_file.name:
            cert_content = await storage.download_file(f"{CERTS_FOLDER}/{cert_file.name}")
            cert = json.loads(cert_content.decode("utf-8"))
            if cert.get("document_id") == document_id:
                storage_path = cert.get("storage_path", "")
                if storage_path:
                    await storage.delete_file(storage_path)
                    return

    raise HTTPException(status_code=404, detail="Document not found")


# =============================================================================
# Vault Service Endpoints - For modules to access documents
# =============================================================================

class VaultDocumentSummary(BaseModel):
    """Summary of a vault document."""
    vault_id: str
    filename: str
    document_type: Optional[str] = None
    file_size: int
    mime_type: str
    uploaded_at: str
    processed: bool = False
    source_module: str = "direct"
    in_vault: bool = True


class VaultListResponse(BaseModel):
    """List of vault documents."""
    documents: List[VaultDocumentSummary]
    total: int


@router.get("/all", response_model=VaultListResponse)
async def list_all_vault_documents(
    document_type: Optional[str] = Query(None, description="Filter by document type"),
    user: StorageUser = Depends(require_user),
):
    """
    List ALL documents in user's vault.
    
    This endpoint is for modules to discover available documents.
    Documents can be accessed by their vault_id.
    """
    if not HAS_VAULT_SERVICE:
        return VaultListResponse(documents=[], total=0)
    
    vault_service = get_vault_service()
    docs = vault_service.get_user_documents(user.user_id, document_type)
    
    summaries = [
        VaultDocumentSummary(
            vault_id=doc.vault_id,
            filename=doc.filename,
            document_type=doc.document_type,
            file_size=doc.file_size,
            mime_type=doc.mime_type,
            uploaded_at=doc.uploaded_at,
            processed=doc.processed,
            source_module=doc.source_module,
            in_vault=True,
        )
        for doc in docs
    ]
    
    return VaultListResponse(documents=summaries, total=len(summaries))


@router.get("/document/{vault_id}")
async def get_vault_document_metadata(
    vault_id: str,
    user: StorageUser = Depends(require_user),
):
    """
    Get metadata for a vault document by vault_id.
    
    Modules use this to get document details before processing.
    """
    if not HAS_VAULT_SERVICE:
        raise HTTPException(status_code=404, detail="Vault service not available")
    
    vault_service = get_vault_service()
    doc = vault_service.get_document(vault_id)
    
    if not doc or doc.user_id != user.user_id:
        raise HTTPException(status_code=404, detail="Document not found")
    
    return doc.to_dict()


@router.get("/document/{vault_id}/content")
async def get_vault_document_content(
    vault_id: str,
    access_token: Optional[str] = Query(None, description="Storage provider access token"),
    user: StorageUser = Depends(require_user),
):
    """
    Get document content from vault.
    
    Modules call this to read document bytes for processing.
    Returns raw file content.
    """
    if not HAS_VAULT_SERVICE:
        raise HTTPException(status_code=404, detail="Vault service not available")
    
    vault_service = get_vault_service()
    doc = vault_service.get_document(vault_id)
    
    if not doc or doc.user_id != user.user_id:
        raise HTTPException(status_code=404, detail="Document not found")
    
    content = await vault_service.get_document_content(vault_id, access_token)
    
    if not content:
        raise HTTPException(status_code=404, detail="Document content not available")
    
    from fastapi.responses import Response
    return Response(
        content=content,
        media_type=doc.mime_type,
        headers={
            "Content-Disposition": f"attachment; filename={doc.filename}",
            "X-Vault-ID": vault_id,
        }
    )


@router.post("/document/{vault_id}/mark-processed")
async def mark_vault_document_processed(
    vault_id: str,
    extracted_data: Optional[dict] = None,
    document_type: Optional[str] = None,
    user: StorageUser = Depends(require_user),
):
    """
    Mark a vault document as processed by a module.
    
    Modules call this after processing to update vault metadata.
    """
    if not HAS_VAULT_SERVICE:
        raise HTTPException(status_code=404, detail="Vault service not available")
    
    vault_service = get_vault_service()
    doc = vault_service.get_document(vault_id)
    
    if not doc or doc.user_id != user.user_id:
        raise HTTPException(status_code=404, detail="Document not found")
    
    vault_service.mark_processed(vault_id, extracted_data)
    
    if document_type:
        vault_service.update_document_type(vault_id, document_type)
    
    return {"success": True, "vault_id": vault_id, "processed": True}
