"""
Semptify SDK - Vault Client

Handles secure vault access, permissions, and sensitive document management.
"""

from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from .base import BaseClient


class VaultPermission(str, Enum):
    """Vault permission levels."""
    NONE = "none"
    VIEW = "view"
    DOWNLOAD = "download"
    EDIT = "edit"
    ADMIN = "admin"


class AccessType(str, Enum):
    """Access type for vault items."""
    PRIVATE = "private"
    SHARED = "shared"
    PUBLIC = "public"


@dataclass
class VaultItem:
    """Vault item (secure document or resource)."""
    id: str
    name: str
    item_type: str
    access_type: str = "private"
    description: Optional[str] = None
    document_id: Optional[str] = None
    encrypted: bool = True
    tags: List[str] = None
    created_at: Optional[datetime] = None
    accessed_at: Optional[datetime] = None
    
    def __post_init__(self):
        if self.tags is None:
            self.tags = []


@dataclass
class VaultAccess:
    """Vault access record."""
    id: str
    user_email: str
    permission: str
    granted_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    granted_by: Optional[str] = None


@dataclass
class VaultAuditEntry:
    """Vault audit log entry."""
    id: str
    action: str
    item_id: str
    user_id: str
    timestamp: datetime
    details: Optional[Dict[str, Any]] = None
    ip_address: Optional[str] = None


@dataclass
class VaultStats:
    """Vault statistics."""
    total_items: int
    total_size_bytes: int
    encrypted_items: int
    shared_items: int
    recent_access_count: int


class VaultClient(BaseClient):
    """Client for vault operations."""
    
    def add_item(
        self,
        name: str,
        document_id: Optional[str] = None,
        item_type: str = "document",
        description: Optional[str] = None,
        access_type: str = "private",
        tags: Optional[List[str]] = None,
        encrypt: bool = True,
    ) -> VaultItem:
        """
        Add an item to the vault.
        
        Args:
            name: Item name
            document_id: Associated document ID
            item_type: Type of item
            description: Item description
            access_type: Access level (private, shared, public)
            tags: Tags for organization
            encrypt: Whether to encrypt the item
            
        Returns:
            Created vault item
        """
        data = {
            "name": name,
            "item_type": item_type,
            "access_type": access_type,
            "encrypt": encrypt,
        }
        
        if document_id:
            data["document_id"] = document_id
        if description:
            data["description"] = description
        if tags:
            data["tags"] = tags
        
        response = self.post("/api/vault/items", json=data)
        
        return VaultItem(
            id=response.get("id", ""),
            name=response.get("name", name),
            item_type=response.get("item_type", item_type),
            access_type=response.get("access_type", access_type),
            description=response.get("description", description),
            document_id=response.get("document_id", document_id),
            encrypted=response.get("encrypted", encrypt),
            tags=response.get("tags", tags or []),
        )
    
    def get_item(self, item_id: str) -> VaultItem:
        """
        Get a vault item by ID.
        
        Args:
            item_id: The item ID
            
        Returns:
            Vault item details
        """
        response = self.get(f"/api/vault/items/{item_id}")
        
        return VaultItem(
            id=response.get("id", item_id),
            name=response.get("name", ""),
            item_type=response.get("item_type", ""),
            access_type=response.get("access_type", "private"),
            description=response.get("description"),
            document_id=response.get("document_id"),
            encrypted=response.get("encrypted", True),
            tags=response.get("tags", []),
        )
    
    def list_items(
        self,
        access_type: Optional[str] = None,
        item_type: Optional[str] = None,
        tags: Optional[List[str]] = None,
        limit: int = 50,
    ) -> List[VaultItem]:
        """
        List vault items.
        
        Args:
            access_type: Filter by access type
            item_type: Filter by item type
            tags: Filter by tags
            limit: Maximum number to return
            
        Returns:
            List of vault items
        """
        params = {"limit": limit}
        if access_type:
            params["access_type"] = access_type
        if item_type:
            params["item_type"] = item_type
        if tags:
            params["tags"] = ",".join(tags)
        
        response = self.get("/api/vault/items", params=params)
        items = response if isinstance(response, list) else response.get("items", [])
        
        return [
            VaultItem(
                id=item.get("id", ""),
                name=item.get("name", ""),
                item_type=item.get("item_type", ""),
                access_type=item.get("access_type", "private"),
                description=item.get("description"),
                document_id=item.get("document_id"),
                encrypted=item.get("encrypted", True),
                tags=item.get("tags", []),
            )
            for item in items
        ]
    
    def delete_item(self, item_id: str) -> bool:
        """
        Delete a vault item.
        
        Args:
            item_id: The item ID
            
        Returns:
            True if deleted successfully
        """
        self.delete(f"/api/vault/items/{item_id}")
        return True
    
    def grant_access(
        self,
        item_id: str,
        email: str,
        permission: VaultPermission = VaultPermission.VIEW,
        expires_in_days: Optional[int] = None,
    ) -> VaultAccess:
        """
        Grant access to a vault item.
        
        Args:
            item_id: The item ID
            email: Email of user to grant access
            permission: Permission level
            expires_in_days: Number of days until access expires
            
        Returns:
            Access record
        """
        data = {
            "email": email,
            "permission": permission.value if isinstance(permission, VaultPermission) else permission,
        }
        if expires_in_days:
            data["expires_in_days"] = expires_in_days
        
        response = self.post(f"/api/vault/items/{item_id}/access", json=data)
        
        return VaultAccess(
            id=response.get("id", ""),
            user_email=response.get("user_email", email),
            permission=response.get("permission", data["permission"]),
            granted_by=response.get("granted_by"),
        )
    
    def revoke_access(self, item_id: str, email: str) -> bool:
        """
        Revoke access to a vault item.
        
        Args:
            item_id: The item ID
            email: Email of user to revoke access
            
        Returns:
            True if revoked successfully
        """
        self.delete(f"/api/vault/items/{item_id}/access/{email}")
        return True
    
    def list_access(self, item_id: str) -> List[VaultAccess]:
        """
        List access records for a vault item.
        
        Args:
            item_id: The item ID
            
        Returns:
            List of access records
        """
        response = self.get(f"/api/vault/items/{item_id}/access")
        records = response if isinstance(response, list) else response.get("access", [])
        
        return [
            VaultAccess(
                id=r.get("id", ""),
                user_email=r.get("user_email", ""),
                permission=r.get("permission", "view"),
                granted_by=r.get("granted_by"),
            )
            for r in records
        ]
    
    def get_audit_log(
        self,
        item_id: Optional[str] = None,
        action: Optional[str] = None,
        limit: int = 100,
    ) -> List[VaultAuditEntry]:
        """
        Get vault audit log.
        
        Args:
            item_id: Filter by specific item
            action: Filter by action type
            limit: Maximum entries to return
            
        Returns:
            List of audit entries
        """
        params = {"limit": limit}
        if item_id:
            params["item_id"] = item_id
        if action:
            params["action"] = action
        
        response = self.get("/api/vault/audit", params=params)
        entries = response if isinstance(response, list) else response.get("entries", [])
        
        return [
            VaultAuditEntry(
                id=e.get("id", ""),
                action=e.get("action", ""),
                item_id=e.get("item_id", ""),
                user_id=e.get("user_id", ""),
                timestamp=datetime.fromisoformat(e["timestamp"]) if e.get("timestamp") else datetime.now(),
                details=e.get("details"),
                ip_address=e.get("ip_address"),
            )
            for e in entries
        ]
    
    def get_stats(self) -> VaultStats:
        """
        Get vault statistics.
        
        Returns:
            Vault statistics
        """
        response = self.get("/api/vault/stats")
        
        return VaultStats(
            total_items=response.get("total_items", 0),
            total_size_bytes=response.get("total_size_bytes", 0),
            encrypted_items=response.get("encrypted_items", 0),
            shared_items=response.get("shared_items", 0),
            recent_access_count=response.get("recent_access_count", 0),
        )
    
    def lock(self) -> bool:
        """
        Lock the vault (require re-authentication for access).
        
        Returns:
            True if locked successfully
        """
        self.post("/api/vault/lock")
        return True
    
    def unlock(self, password: Optional[str] = None) -> bool:
        """
        Unlock the vault.
        
        Args:
            password: Vault password if additional auth required
            
        Returns:
            True if unlocked successfully
        """
        data = {}
        if password:
            data["password"] = password
        
        self.post("/api/vault/unlock", json=data)
        return True
    
    def download_item(self, item_id: str) -> bytes:
        """
        Download a vault item's content.
        
        Args:
            item_id: The item ID
            
        Returns:
            Decrypted content as bytes
        """
        response = self.client.get(f"/api/vault/items/{item_id}/download")
        return response.content
