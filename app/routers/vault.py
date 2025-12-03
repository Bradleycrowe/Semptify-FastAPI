"""
Document Vault Router (Cloud Storage Version)
Secure document upload to user's cloud storage with certification.

Semptify 5.0 Architecture:
- Documents stored in USER's cloud storage (Google Drive, Dropbox, OneDrive)
- NOT stored locally on server
- User must be authenticated via storage OAuth
- Certificates stored alongside documents in .semptify/vault/
"""

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel, Field

from app.core.config import Settings, get_settings
from app.core.security import require_user, rate_limit_dependency, StorageUser
from app.services.storage import get_provider, StorageFile


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

    # Ensure vault folders exist
    await ensure_vault_folders(storage, user.provider)

    # Upload file to user's storage
    storage_path = f"{VAULT_FOLDER}/{safe_filename}"
    await storage.upload_file(
        file_content=content,
        destination_path=VAULT_FOLDER,
        filename=safe_filename,
        mime_type=file.content_type or "application/octet-stream",
    )

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
    await storage.upload_file(
        file_content=cert_content,
        destination_path=CERTS_FOLDER,
        filename=f"{certificate_id}.json",
        mime_type="application/json",
    )

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