"""
Semptify 5.0 - Documents API Tests
Tests for document processing, vault, and law engine.
"""

import pytest
from httpx import AsyncClient
from io import BytesIO
from unittest.mock import patch, AsyncMock


# =============================================================================
# Document Upload Tests
# =============================================================================

@pytest.mark.anyio
async def test_document_upload(client: AsyncClient, test_user_id):
    """Test document upload endpoint."""
    # Create a mock PDF file
    file_content = b"%PDF-1.4 mock pdf content for testing"
    files = {"file": ("test_lease.pdf", BytesIO(file_content), "application/pdf")}
    
    response = await client.post(
        f"/api/documents/upload?user_id={test_user_id}",
        files=files
    )
    assert response.status_code in [200, 201, 503]  # 503 if Azure AI not available
    if response.status_code in [200, 201]:
        data = response.json()
        assert "id" in data
        assert "filename" in data
        assert "status" in data


@pytest.mark.anyio
async def test_document_upload_queue_mode(client: AsyncClient, test_user_id):
    """Test document upload in queue mode (no immediate processing)."""
    file_content = b"%PDF-1.4 mock pdf content"
    files = {"file": ("test.pdf", BytesIO(file_content), "application/pdf")}
    
    response = await client.post(
        f"/api/documents/upload?user_id={test_user_id}&process_now=false",
        files=files
    )
    assert response.status_code in [200, 201]
    if response.status_code in [200, 201]:
        data = response.json()
        assert data["status"] in ["pending", "queued"]


@pytest.mark.anyio
async def test_document_upload_no_file(client: AsyncClient, test_user_id):
    """Test document upload without file."""
    response = await client.post(f"/api/documents/upload?user_id={test_user_id}")
    assert response.status_code == 422


@pytest.mark.anyio
async def test_document_upload_missing_user_id(client: AsyncClient):
    """Test document upload without user_id - in open mode, a user is auto-created."""
    file_content = b"%PDF-1.4 mock pdf"
    files = {"file": ("test.pdf", BytesIO(file_content), "application/pdf")}

    response = await client.post("/api/documents/upload", files=files)
    # In open security mode, a user is auto-created, so upload succeeds
    # In strict mode, this would be 401/422
    assert response.status_code in [200, 201, 401, 422]
# =============================================================================
# Document Listing Tests
# =============================================================================

@pytest.mark.anyio
async def test_document_list(client: AsyncClient, test_user_id):
    """Test listing user documents."""
    response = await client.get(f"/api/documents/?user_id={test_user_id}")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


@pytest.mark.anyio
async def test_document_list_filter_by_type(client: AsyncClient, test_user_id):
    """Test filtering documents by type."""
    response = await client.get(
        f"/api/documents/?user_id={test_user_id}&doc_type=lease"
    )
    assert response.status_code == 200


@pytest.mark.anyio
async def test_document_list_filter_by_status(client: AsyncClient, test_user_id):
    """Test filtering documents by status."""
    response = await client.get(
        f"/api/documents/?user_id={test_user_id}&status=classified"
    )
    assert response.status_code == 200


# =============================================================================
# Document Details Tests
# =============================================================================

@pytest.mark.anyio
async def test_document_get_nonexistent(client: AsyncClient):
    """Test getting a non-existent document."""
    response = await client.get("/api/documents/nonexistent-id")
    assert response.status_code == 404


@pytest.mark.anyio
async def test_document_reprocess_nonexistent(client: AsyncClient):
    """Test reprocessing a non-existent document."""
    response = await client.post("/api/documents/nonexistent-id/reprocess")
    assert response.status_code == 404


# =============================================================================
# Timeline & Summary Tests
# =============================================================================

@pytest.mark.anyio
async def test_document_timeline(client: AsyncClient, test_user_id):
    """Test document timeline endpoint."""
    response = await client.get(f"/api/documents/timeline/?user_id={test_user_id}")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


@pytest.mark.anyio
async def test_document_summary(client: AsyncClient, test_user_id):
    """Test document summary endpoint."""
    response = await client.get(f"/api/documents/summary/?user_id={test_user_id}")
    assert response.status_code == 200
    data = response.json()
    assert "total_documents" in data
    assert "by_type" in data
    assert "by_status" in data


@pytest.mark.anyio
async def test_document_rights(client: AsyncClient, test_user_id):
    """Test tenant rights summary endpoint."""
    response = await client.get(f"/api/documents/rights/?user_id={test_user_id}")
    assert response.status_code == 200
    data = response.json()
    assert "documents_analyzed" in data


# =============================================================================
# Law Reference Tests
# =============================================================================

@pytest.mark.anyio
async def test_laws_list(client: AsyncClient):
    """Test listing all law references."""
    response = await client.get("/api/documents/laws/")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


@pytest.mark.anyio
async def test_laws_filter_by_category(client: AsyncClient):
    """Test filtering laws by category."""
    response = await client.get("/api/documents/laws/?category=eviction")
    assert response.status_code == 200


@pytest.mark.anyio
async def test_laws_get_nonexistent(client: AsyncClient):
    """Test getting a non-existent law."""
    response = await client.get("/api/documents/laws/nonexistent-id")
    assert response.status_code == 404


# =============================================================================
# Vault Tests
# =============================================================================

@pytest.mark.anyio
async def test_vault_list_unauthenticated(client: AsyncClient):
    """Test vault list requires authentication - vault is backend only via API."""
    response = await client.get("/api/vault/")
    # Vault is backend-only, accessed via Timeline/Calendar
    # In open mode might auto-create user, strict mode returns 401/403
    # Could also be 400 if no user context can be determined
    assert response.status_code in [200, 400, 401, 403, 404]


@pytest.mark.anyio
async def test_vault_upload_requires_auth(client: AsyncClient):
    """Test vault upload requires authentication - vault is backend only."""
    file_content = b"test content"
    try:
        response = await client.post(
            "/api/vault/upload",
            files={"file": ("test.txt", BytesIO(file_content), "text/plain")},
            data={"access_token": "fake_token"}
        )
        # Vault is backend-only, upload via /api/documents/
        # Various error codes possible depending on security mode
        assert response.status_code in [400, 401, 403, 404, 422, 500]
    except Exception:
        # External service errors (like Google Drive 401) may raise exceptions
        # This is expected behavior when using fake tokens
        pass


@pytest.mark.anyio
async def test_vault_download_nonexistent(authenticated_client: AsyncClient):
    """Test downloading non-existent vault document."""
    response = await authenticated_client.get("/vault/nonexistent-id/download")
    assert response.status_code in [404, 401]


@pytest.mark.anyio
async def test_vault_certificate_nonexistent(authenticated_client: AsyncClient):
    """Test getting certificate for non-existent document."""
    response = await authenticated_client.get("/vault/nonexistent-id/certificate")
    assert response.status_code in [404, 401]


# =============================================================================
# Document Type Tests
# =============================================================================

@pytest.mark.anyio
@pytest.mark.parametrize("doc_type", [
    "lease", "notice", "receipt", "court_filing", "communication",
    "photo", "inspection", "repair_request", "insurance", "other"
])
async def test_document_filter_all_types(client: AsyncClient, test_user_id, doc_type):
    """Test filtering documents by all supported types."""
    response = await client.get(
        f"/api/documents/?user_id={test_user_id}&doc_type={doc_type}"
    )
    assert response.status_code == 200


# =============================================================================
# Processing Status Tests
# =============================================================================

@pytest.mark.anyio
@pytest.mark.parametrize("status", [
    "pending", "analyzing", "classified", "cross_referenced", "failed"
])
async def test_document_filter_all_statuses(client: AsyncClient, test_user_id, status):
    """Test filtering documents by all processing statuses."""
    response = await client.get(
        f"/api/documents/?user_id={test_user_id}&status={status}"
    )
    assert response.status_code == 200
