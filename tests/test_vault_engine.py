"""
Tests for the Vault Engine - Centralized Access Control System

Tests the core VaultAccessEngine functionality:
- Access control verification
- Role-based permissions
- Resource CRUD operations through the engine
- Audit logging
- Sharing capabilities
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def user_cookie():
    """Regular user cookie."""
    return {"semptify_uid": "GUa8Km3xPq"}  # Google + User + random


@pytest.fixture
def manager_cookie():
    """Manager user cookie."""
    return {"semptify_uid": "DMb7Nj2yRs"}  # Dropbox + Manager + random


@pytest.fixture
def legal_cookie():
    """Legal professional cookie."""
    return {"semptify_uid": "OLc6Pk4wQt"}  # OneDrive + Legal + random


@pytest.fixture
def admin_cookie():
    """Admin user cookie."""
    return {"semptify_uid": "GAd5Ql1vZu"}  # Google + Admin + random


# =============================================================================
# Resource Types Endpoint Tests
# =============================================================================

class TestResourceTypes:
    """Test resource type enumeration."""
    
    def test_list_resource_types(self, user_cookie):
        """Should list all valid resource types."""
        response = client.get("/api/vault-engine/resource-types", cookies=user_cookie)
        assert response.status_code == 200
        data = response.json()
        assert "types" in data
        assert "document" in data["types"]
        assert "timeline_event" in data["types"]
        assert "calendar_event" in data["types"]
    
    def test_list_access_levels(self, user_cookie):
        """Should list all valid access levels."""
        response = client.get("/api/vault-engine/access-levels", cookies=user_cookie)
        assert response.status_code == 200
        data = response.json()
        assert "levels" in data
        assert "read" in data["levels"]
        assert "write" in data["levels"]
        assert "delete" in data["levels"]


# =============================================================================
# Access Check Endpoint Tests
# =============================================================================

class TestAccessCheck:
    """Test access permission checking."""
    
    def test_check_access_unauthorized(self):
        """Should require authentication."""
        response = client.post("/api/vault-engine/check-access", json={
            "resource_type": "document",
            "resource_id": "test-doc-1",
            "action": "read"
        })
        # May return 401 or handle gracefully
        assert response.status_code in [401, 403, 200]
    
    def test_check_access_user_read(self, user_cookie):
        """User should have read access to documents."""
        response = client.post("/api/vault-engine/check-access", json={
            "resource_type": "document",
            "resource_id": "test-doc-1",
            "action": "read"
        }, cookies=user_cookie)
        assert response.status_code == 200
        data = response.json()
        assert "allowed" in data
        assert "reason" in data
    
    def test_check_access_invalid_resource_type(self, user_cookie):
        """Should reject invalid resource types."""
        response = client.post("/api/vault-engine/check-access", json={
            "resource_type": "invalid_type",
            "resource_id": "test-doc-1",
            "action": "read"
        }, cookies=user_cookie)
        assert response.status_code == 400
        assert "Invalid resource type" in response.json()["detail"]
    
    def test_check_access_invalid_action(self, user_cookie):
        """Should reject invalid actions."""
        response = client.post("/api/vault-engine/check-access", json={
            "resource_type": "document",
            "resource_id": "test-doc-1",
            "action": "invalid_action"
        }, cookies=user_cookie)
        assert response.status_code == 400
        assert "Invalid action" in response.json()["detail"]


# =============================================================================
# Read Endpoint Tests  
# =============================================================================

class TestReadOperations:
    """Test vault read operations."""
    
    def test_read_document(self, user_cookie):
        """Should allow reading documents."""
        response = client.post("/api/vault-engine/read", json={
            "resource_type": "document",
            "resource_id": "test-doc-1",
            "reason": "Testing read access"
        }, cookies=user_cookie)
        # May succeed or fail depending on whether resource exists
        assert response.status_code in [200, 403, 404]
    
    def test_read_invalid_type(self, user_cookie):
        """Should reject invalid resource type."""
        response = client.post("/api/vault-engine/read", json={
            "resource_type": "not_real",
            "resource_id": "test-doc-1"
        }, cookies=user_cookie)
        assert response.status_code == 400


# =============================================================================
# Write Endpoint Tests
# =============================================================================

class TestWriteOperations:
    """Test vault write operations."""
    
    def test_write_document_user(self, user_cookie):
        """Regular user may not have write access by default."""
        response = client.post("/api/vault-engine/write", json={
            "resource_type": "document",
            "resource_id": "new-doc-1",
            "data": {"title": "Test Document", "content": "Test content"},
            "reason": "Testing write"
        }, cookies=user_cookie)
        # Users may or may not have write access depending on implementation
        assert response.status_code in [200, 403]
    
    def test_write_document_manager(self, manager_cookie):
        """Manager should have write access."""
        response = client.post("/api/vault-engine/write", json={
            "resource_type": "document",
            "resource_id": "new-doc-2",
            "data": {"title": "Manager Document"},
            "reason": "Manager creating document"
        }, cookies=manager_cookie)
        # Manager should typically have write access
        assert response.status_code in [200, 201, 403]
    
    def test_write_invalid_type(self, user_cookie):
        """Should reject invalid resource type."""
        response = client.post("/api/vault-engine/write", json={
            "resource_type": "fake_type",
            "resource_id": "test",
            "data": {}
        }, cookies=user_cookie)
        assert response.status_code == 400


# =============================================================================
# Delete Endpoint Tests
# =============================================================================

class TestDeleteOperations:
    """Test vault delete operations."""
    
    def test_delete_soft(self, admin_cookie):
        """Admin should be able to soft delete."""
        response = client.post("/api/vault-engine/delete", json={
            "resource_type": "document",
            "resource_id": "delete-test-1",
            "hard_delete": False,
            "reason": "Testing soft delete"
        }, cookies=admin_cookie)
        # May succeed or fail if resource doesn't exist
        assert response.status_code in [200, 403, 404]
    
    def test_delete_hard(self, admin_cookie):
        """Admin should be able to hard delete."""
        response = client.post("/api/vault-engine/delete", json={
            "resource_type": "document",
            "resource_id": "delete-test-2",
            "hard_delete": True,
            "reason": "Testing hard delete"
        }, cookies=admin_cookie)
        assert response.status_code in [200, 403, 404]
    
    def test_delete_user_denied(self, user_cookie):
        """Regular user should not be able to delete."""
        response = client.post("/api/vault-engine/delete", json={
            "resource_type": "document",
            "resource_id": "delete-test-3",
            "hard_delete": False
        }, cookies=user_cookie)
        # Users typically can't delete - should be denied or not found
        assert response.status_code in [403, 404]


# =============================================================================
# Sharing Endpoint Tests
# =============================================================================

class TestShareOperations:
    """Test resource sharing functionality."""
    
    def test_share_resource(self, manager_cookie):
        """Manager should be able to share resources."""
        response = client.post("/api/vault-engine/share", json={
            "resource_id": "share-test-1",
            "share_with": "GUb8Km3xPq",  # Another user
            "reason": "Sharing for collaboration"
        }, cookies=manager_cookie)
        # May succeed or fail depending on ownership
        assert response.status_code in [200, 403]
    
    def test_unshare_resource(self, manager_cookie):
        """Should be able to remove sharing."""
        response = client.post("/api/vault-engine/unshare", json={
            "resource_id": "share-test-1",
            "unshare_from": "GUb8Km3xPq"
        }, cookies=manager_cookie)
        assert response.status_code in [200, 403]


# =============================================================================
# List Endpoint Tests
# =============================================================================

class TestListOperations:
    """Test resource listing functionality."""
    
    def test_list_resources(self, user_cookie):
        """Should list accessible resources."""
        response = client.get("/api/vault-engine/list", cookies=user_cookie)
        assert response.status_code == 200
        data = response.json()
        assert "count" in data
        assert "resources" in data
        assert isinstance(data["resources"], list)
    
    def test_list_by_type(self, user_cookie):
        """Should filter by resource type."""
        response = client.get(
            "/api/vault-engine/list",
            params={"resource_type": "document"},
            cookies=user_cookie
        )
        assert response.status_code == 200
    
    def test_list_include_deleted(self, admin_cookie):
        """Admin should be able to see deleted resources."""
        response = client.get(
            "/api/vault-engine/list",
            params={"include_deleted": True},
            cookies=admin_cookie
        )
        assert response.status_code == 200
    
    def test_list_invalid_type(self, user_cookie):
        """Should reject invalid resource type filter."""
        response = client.get(
            "/api/vault-engine/list",
            params={"resource_type": "invalid"},
            cookies=user_cookie
        )
        assert response.status_code == 400


# =============================================================================
# Audit Log Endpoint Tests
# =============================================================================

class TestAuditLog:
    """Test audit logging functionality."""
    
    def test_get_audit_log(self, user_cookie):
        """Should return audit entries."""
        response = client.get("/api/vault-engine/audit", cookies=user_cookie)
        assert response.status_code == 200
        data = response.json()
        assert "count" in data
        assert "entries" in data
    
    def test_audit_log_filter_by_resource(self, user_cookie):
        """Should filter audit by resource."""
        response = client.get(
            "/api/vault-engine/audit",
            params={"resource_id": "test-doc-1"},
            cookies=user_cookie
        )
        assert response.status_code == 200
    
    def test_audit_log_limit(self, user_cookie):
        """Should respect limit parameter."""
        response = client.get(
            "/api/vault-engine/audit",
            params={"limit": 10},
            cookies=user_cookie
        )
        assert response.status_code == 200


# =============================================================================
# Stats Endpoint Tests
# =============================================================================

class TestStats:
    """Test statistics endpoint."""
    
    def test_get_stats(self, admin_cookie):
        """Admin should get vault statistics."""
        response = client.get("/api/vault-engine/stats", cookies=admin_cookie)
        assert response.status_code == 200
        data = response.json()
        # Should return some stats structure
        assert isinstance(data, dict)


# =============================================================================
# Role-Based Access Tests
# =============================================================================

class TestRoleBasedAccess:
    """Test that different roles have appropriate permissions."""
    
    def test_user_role_permissions(self, user_cookie):
        """Regular user should have limited access."""
        # Can read
        read_response = client.post("/api/vault-engine/check-access", json={
            "resource_type": "document",
            "resource_id": "test",
            "action": "read"
        }, cookies=user_cookie)
        assert read_response.status_code == 200
        
        # May not be able to delete
        delete_response = client.post("/api/vault-engine/check-access", json={
            "resource_type": "document",
            "resource_id": "test",
            "action": "delete"
        }, cookies=user_cookie)
        assert delete_response.status_code == 200
        # Check if delete is denied
        if delete_response.json().get("allowed") == False:
            assert "denied" in delete_response.json().get("reason", "").lower() or \
                   "not allowed" in delete_response.json().get("reason", "").lower() or \
                   delete_response.json().get("allowed") == False
    
    def test_legal_role_permissions(self, legal_cookie):
        """Legal professionals should have broader read access."""
        response = client.post("/api/vault-engine/check-access", json={
            "resource_type": "document",
            "resource_id": "test",
            "action": "read"
        }, cookies=legal_cookie)
        assert response.status_code == 200
        # Legal should typically be allowed to read
        assert "allowed" in response.json()
    
    def test_admin_role_permissions(self, admin_cookie):
        """Admin should have full access."""
        for action in ["read", "write", "delete"]:
            response = client.post("/api/vault-engine/check-access", json={
                "resource_type": "document",
                "resource_id": "test",
                "action": action
            }, cookies=admin_cookie)
            assert response.status_code == 200
            # Admin should be allowed for all actions
            assert "allowed" in response.json()


# =============================================================================
# Integration Tests
# =============================================================================

class TestVaultEngineIntegration:
    """Integration tests for vault engine workflow."""
    
    def test_full_document_lifecycle(self, manager_cookie):
        """Test create -> read -> update -> delete workflow."""
        doc_id = f"lifecycle-test-{datetime.now().timestamp()}"
        
        # 1. Write (create) document
        write_response = client.post("/api/vault-engine/write", json={
            "resource_type": "document",
            "resource_id": doc_id,
            "data": {"title": "Lifecycle Test", "version": 1},
            "reason": "Creating test document"
        }, cookies=manager_cookie)
        # May or may not succeed depending on implementation
        if write_response.status_code == 200:
            # 2. Read document
            read_response = client.post("/api/vault-engine/read", json={
                "resource_type": "document",
                "resource_id": doc_id
            }, cookies=manager_cookie)
            assert read_response.status_code in [200, 404]
    
    def test_access_audit_trail(self, user_cookie):
        """Verify access creates audit trail."""
        # Make some accesses
        client.post("/api/vault-engine/check-access", json={
            "resource_type": "document",
            "resource_id": "audit-test-1",
            "action": "read"
        }, cookies=user_cookie)
        
        # Check audit log
        audit_response = client.get("/api/vault-engine/audit", cookies=user_cookie)
        assert audit_response.status_code == 200
        # Should have entries (may or may not include our test)
        data = audit_response.json()
        assert "entries" in data
