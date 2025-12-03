"""
Semptify 5.0 - Vault Access Engine

CENTRALIZED DATA FLOW CONTROL

All vault operations MUST go through this engine:
- Reads: verify user has access, log access, return data
- Writes: verify permissions, validate data, store, audit
- Deletes: verify ownership, soft-delete with audit trail

Access Control Matrix:
┌─────────────┬────────┬─────────┬────────┬──────────┬─────────┐
│ Role        │ Own    │ Shared  │ Case   │ Org      │ System  │
├─────────────┼────────┼─────────┼────────┼──────────┼─────────┤
│ User        │ RWD    │ R       │ -      │ -        │ -       │
│ Advocate    │ RWD    │ RW      │ RW     │ R        │ -       │
│ Legal       │ RWD    │ RW      │ RWD    │ RW       │ R       │
│ Manager     │ RWD    │ RW      │ RW     │ RWD      │ R       │
│ Admin       │ RWD    │ RWD     │ RWD    │ RWD      │ RWD     │
└─────────────┴────────┴─────────┴────────┴──────────┴─────────┘
R=Read, W=Write, D=Delete
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Optional, TypeVar
from uuid import uuid4
import hashlib
import json
import logging
import asyncio

from app.core.user_id import get_role_from_user_id, get_provider_from_user_id
from app.core.event_bus import event_bus, EventType

logger = logging.getLogger(__name__)


# =============================================================================
# Access Control Types
# =============================================================================

class AccessLevel(str, Enum):
    """What you can do."""
    NONE = "none"
    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    ADMIN = "admin"  # All permissions


class ResourceScope(str, Enum):
    """Whose data is it?"""
    OWN = "own"           # User's own data
    SHARED = "shared"     # Explicitly shared with user
    CASE = "case"         # Part of a case they're on
    ORG = "org"           # Organization-wide (for managers)
    SYSTEM = "system"     # System-level data


class ResourceType(str, Enum):
    """What kind of resource."""
    DOCUMENT = "document"
    TIMELINE_EVENT = "timeline_event"
    CALENDAR_EVENT = "calendar_event"
    CASE_FILE = "case_file"
    FORM_DATA = "form_data"
    SETTING = "setting"
    AUDIT_LOG = "audit_log"


class AuditAction(str, Enum):
    """What happened."""
    READ = "read"
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    SHARE = "share"
    UNSHARE = "unshare"
    EXPORT = "export"
    ACCESS_DENIED = "access_denied"


# =============================================================================
# Access Control Matrix
# =============================================================================

# Role -> Scope -> Permissions
ACCESS_MATRIX: dict[str, dict[ResourceScope, set[AccessLevel]]] = {
    "user": {
        ResourceScope.OWN: {AccessLevel.READ, AccessLevel.WRITE, AccessLevel.DELETE},
        ResourceScope.SHARED: {AccessLevel.READ},
        ResourceScope.CASE: set(),
        ResourceScope.ORG: set(),
        ResourceScope.SYSTEM: set(),
    },
    "advocate": {
        ResourceScope.OWN: {AccessLevel.READ, AccessLevel.WRITE, AccessLevel.DELETE},
        ResourceScope.SHARED: {AccessLevel.READ, AccessLevel.WRITE},
        ResourceScope.CASE: {AccessLevel.READ, AccessLevel.WRITE},
        ResourceScope.ORG: {AccessLevel.READ},
        ResourceScope.SYSTEM: set(),
    },
    "legal": {
        ResourceScope.OWN: {AccessLevel.READ, AccessLevel.WRITE, AccessLevel.DELETE},
        ResourceScope.SHARED: {AccessLevel.READ, AccessLevel.WRITE},
        ResourceScope.CASE: {AccessLevel.READ, AccessLevel.WRITE, AccessLevel.DELETE},
        ResourceScope.ORG: {AccessLevel.READ, AccessLevel.WRITE},
        ResourceScope.SYSTEM: {AccessLevel.READ},
    },
    "manager": {
        ResourceScope.OWN: {AccessLevel.READ, AccessLevel.WRITE, AccessLevel.DELETE},
        ResourceScope.SHARED: {AccessLevel.READ, AccessLevel.WRITE},
        ResourceScope.CASE: {AccessLevel.READ, AccessLevel.WRITE},
        ResourceScope.ORG: {AccessLevel.READ, AccessLevel.WRITE, AccessLevel.DELETE},
        ResourceScope.SYSTEM: {AccessLevel.READ},
    },
    "admin": {
        ResourceScope.OWN: {AccessLevel.ADMIN},
        ResourceScope.SHARED: {AccessLevel.ADMIN},
        ResourceScope.CASE: {AccessLevel.ADMIN},
        ResourceScope.ORG: {AccessLevel.ADMIN},
        ResourceScope.SYSTEM: {AccessLevel.ADMIN},
    },
}


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class AccessRequest:
    """Request to access vault data."""
    user_id: str
    resource_type: ResourceType
    resource_id: str
    action: AccessLevel
    
    # Optional context
    reason: Optional[str] = None
    case_id: Optional[str] = None
    
    # Computed at check time
    user_role: Optional[str] = None
    resource_owner: Optional[str] = None
    scope: Optional[ResourceScope] = None


@dataclass
class AccessResult:
    """Result of access check."""
    allowed: bool
    reason: str
    scope: Optional[ResourceScope] = None
    
    # Audit trail
    request_id: str = field(default_factory=lambda: str(uuid4())[:8])
    checked_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class AuditEntry:
    """Immutable audit log entry."""
    id: str
    timestamp: datetime
    user_id: str
    action: AuditAction
    resource_type: ResourceType
    resource_id: str
    scope: ResourceScope
    success: bool
    
    # Details
    details: dict = field(default_factory=dict)
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    
    # Integrity
    checksum: Optional[str] = None
    
    def compute_checksum(self) -> str:
        """Compute tamper-evident checksum."""
        data = f"{self.id}:{self.timestamp.isoformat()}:{self.user_id}:{self.action.value}"
        data += f":{self.resource_type.value}:{self.resource_id}:{self.success}"
        return hashlib.sha256(data.encode()).hexdigest()[:16]


@dataclass
class VaultResource:
    """A resource in the vault with access metadata."""
    id: str
    type: ResourceType
    owner_id: str
    created_at: datetime
    
    # Access control
    shared_with: list[str] = field(default_factory=list)  # User IDs
    case_ids: list[str] = field(default_factory=list)      # Associated cases
    org_id: Optional[str] = None                            # Organization
    
    # The actual data
    data: Any = None
    
    # Metadata
    tags: list[str] = field(default_factory=list)
    is_deleted: bool = False
    deleted_at: Optional[datetime] = None
    deleted_by: Optional[str] = None


# =============================================================================
# Vault Access Engine
# =============================================================================

class VaultAccessEngine:
    """
    THE GATEKEEPER.
    
    Every vault operation goes through here:
    1. Check access rights
    2. Log the attempt
    3. Execute if allowed
    4. Return result with audit trail
    """
    
    def __init__(self):
        # In-memory stores (would be DB in production)
        self._resources: dict[str, VaultResource] = {}
        self._audit_log: list[AuditEntry] = []
        self._access_grants: dict[str, set[str]] = {}  # resource_id -> set of user_ids
        
        # Hooks for custom validation
        self._pre_access_hooks: list[Callable] = []
        self._post_access_hooks: list[Callable] = []
        
        logger.info("VaultAccessEngine initialized")
    
    # =========================================================================
    # Access Control
    # =========================================================================
    
    def check_access(self, request: AccessRequest) -> AccessResult:
        """
        Check if user can perform action on resource.
        
        This is the CORE security check. Every operation calls this.
        """
        # Get user role from user_id
        request.user_role = get_role_from_user_id(request.user_id) or "user"
        
        # Get resource info
        resource = self._resources.get(request.resource_id)
        if resource:
            request.resource_owner = resource.owner_id
            request.scope = self._determine_scope(request.user_id, resource)
        else:
            # New resource - user is creating it
            request.scope = ResourceScope.OWN
            request.resource_owner = request.user_id
        
        # Check access matrix
        allowed_levels = ACCESS_MATRIX.get(request.user_role, {}).get(
            request.scope, set()
        )
        
        # Admin level includes all permissions
        if AccessLevel.ADMIN in allowed_levels:
            return AccessResult(
                allowed=True,
                reason=f"Admin access for {request.user_role}",
                scope=request.scope,
            )
        
        # Check specific permission
        if request.action in allowed_levels:
            return AccessResult(
                allowed=True,
                reason=f"{request.user_role} has {request.action.value} on {request.scope.value}",
                scope=request.scope,
            )
        
        # Access denied
        return AccessResult(
            allowed=False,
            reason=f"{request.user_role} cannot {request.action.value} {request.scope.value} resources",
            scope=request.scope,
        )
    
    def _determine_scope(self, user_id: str, resource: VaultResource) -> ResourceScope:
        """Determine the scope of access for this user-resource pair."""
        # Own resource?
        if resource.owner_id == user_id:
            return ResourceScope.OWN
        
        # Explicitly shared?
        if user_id in resource.shared_with:
            return ResourceScope.SHARED
        
        # Part of a case they're on?
        # (Would check case membership in production)
        if resource.case_ids:
            return ResourceScope.CASE
        
        # Organization resource?
        if resource.org_id:
            return ResourceScope.ORG
        
        # System resource
        return ResourceScope.SYSTEM
    
    # =========================================================================
    # CRUD Operations (All go through access control)
    # =========================================================================
    
    def read(
        self,
        user_id: str,
        resource_type: ResourceType,
        resource_id: str,
        reason: Optional[str] = None,
    ) -> tuple[bool, Any, AccessResult]:
        """
        Read a resource from the vault.
        
        Returns: (success, data_or_error, access_result)
        """
        request = AccessRequest(
            user_id=user_id,
            resource_type=resource_type,
            resource_id=resource_id,
            action=AccessLevel.READ,
            reason=reason,
        )
        
        result = self.check_access(request)
        
        # Audit the attempt
        self._audit(
            user_id=user_id,
            action=AuditAction.READ if result.allowed else AuditAction.ACCESS_DENIED,
            resource_type=resource_type,
            resource_id=resource_id,
            scope=result.scope or ResourceScope.OWN,
            success=result.allowed,
            details={"reason": reason} if reason else {},
        )
        
        if not result.allowed:
            logger.warning(f"Access denied: {user_id} -> {resource_id}: {result.reason}")
            return False, {"error": result.reason}, result
        
        resource = self._resources.get(resource_id)
        if not resource or resource.is_deleted:
            return False, {"error": "Resource not found"}, result
        
        return True, resource.data, result
    
    def write(
        self,
        user_id: str,
        resource_type: ResourceType,
        resource_id: str,
        data: Any,
        reason: Optional[str] = None,
    ) -> tuple[bool, Any, AccessResult]:
        """
        Write (create/update) a resource in the vault.
        """
        is_create = resource_id not in self._resources
        
        request = AccessRequest(
            user_id=user_id,
            resource_type=resource_type,
            resource_id=resource_id,
            action=AccessLevel.WRITE,
            reason=reason,
        )
        
        result = self.check_access(request)
        
        # Audit
        self._audit(
            user_id=user_id,
            action=AuditAction.CREATE if is_create else AuditAction.UPDATE,
            resource_type=resource_type,
            resource_id=resource_id,
            scope=result.scope or ResourceScope.OWN,
            success=result.allowed,
            details={"is_create": is_create, "reason": reason},
        )
        
        if not result.allowed:
            logger.warning(f"Write denied: {user_id} -> {resource_id}: {result.reason}")
            return False, {"error": result.reason}, result
        
        # Create or update
        if is_create:
            resource = VaultResource(
                id=resource_id,
                type=resource_type,
                owner_id=user_id,
                created_at=datetime.now(timezone.utc),
                data=data,
            )
        else:
            resource = self._resources[resource_id]
            resource.data = data
        
        self._resources[resource_id] = resource
        logger.info(f"{'Created' if is_create else 'Updated'}: {resource_id} by {user_id}")

        # Publish event to EventBus
        try:
            event_type = EventType.DOCUMENT_ADDED if is_create else EventType.DOCUMENT_UPDATED
            event_bus.publish_sync(
                event_type,
                {
                    "resource_id": resource_id,
                    "resource_type": resource_type.value,
                    "action": "created" if is_create else "updated",
                },
                source="vault_engine",
                user_id=user_id,
            )
        except Exception as e:
            logger.warning(f"Failed to publish event: {e}")

        return True, {"id": resource_id, "created": is_create}, result

    def delete(
        self,
        user_id: str,
        resource_type: ResourceType,
        resource_id: str,
        reason: Optional[str] = None,
        hard_delete: bool = False,
    ) -> tuple[bool, Any, AccessResult]:
        """
        Delete a resource (soft by default, hard if specified).
        """
        request = AccessRequest(
            user_id=user_id,
            resource_type=resource_type,
            resource_id=resource_id,
            action=AccessLevel.DELETE,
            reason=reason,
        )
        
        result = self.check_access(request)
        
        # Audit
        self._audit(
            user_id=user_id,
            action=AuditAction.DELETE,
            resource_type=resource_type,
            resource_id=resource_id,
            scope=result.scope or ResourceScope.OWN,
            success=result.allowed,
            details={"hard_delete": hard_delete, "reason": reason},
        )
        
        if not result.allowed:
            logger.warning(f"Delete denied: {user_id} -> {resource_id}: {result.reason}")
            return False, {"error": result.reason}, result
        
        resource = self._resources.get(resource_id)
        if not resource:
            return False, {"error": "Resource not found"}, result
        
        if hard_delete:
            del self._resources[resource_id]
            logger.info(f"Hard deleted: {resource_id} by {user_id}")
        else:
            resource.is_deleted = True
            resource.deleted_at = datetime.now(timezone.utc)
            resource.deleted_by = user_id
            logger.info(f"Soft deleted: {resource_id} by {user_id}")

        # Publish delete event
        try:
            event_bus.publish_sync(
                EventType.DOCUMENT_DELETED,
                {
                    "resource_id": resource_id,
                    "resource_type": resource_type.value,
                    "hard_delete": hard_delete,
                },
                source="vault_engine",
                user_id=user_id,
            )
        except Exception as e:
            logger.warning(f"Failed to publish delete event: {e}")

        return True, {"deleted": resource_id, "hard": hard_delete}, result    # =========================================================================
    # Sharing
    # =========================================================================
    
    def share(
        self,
        owner_id: str,
        resource_id: str,
        share_with: str,
        reason: Optional[str] = None,
    ) -> tuple[bool, str]:
        """Share a resource with another user."""
        resource = self._resources.get(resource_id)
        
        if not resource:
            return False, "Resource not found"
        
        if resource.owner_id != owner_id:
            # Check if user has share permission
            role = get_role_from_user_id(owner_id) or "user"
            if role not in ["advocate", "legal", "manager", "admin"]:
                return False, "Only owners or privileged users can share"
        
        if share_with not in resource.shared_with:
            resource.shared_with.append(share_with)
        
        self._audit(
            user_id=owner_id,
            action=AuditAction.SHARE,
            resource_type=resource.type,
            resource_id=resource_id,
            scope=ResourceScope.OWN,
            success=True,
            details={"shared_with": share_with, "reason": reason},
        )
        
        logger.info(f"Shared: {resource_id} with {share_with} by {owner_id}")
        return True, f"Shared with {share_with}"
    
    def unshare(
        self,
        owner_id: str,
        resource_id: str,
        unshare_from: str,
    ) -> tuple[bool, str]:
        """Remove sharing from a user."""
        resource = self._resources.get(resource_id)
        
        if not resource:
            return False, "Resource not found"
        
        if resource.owner_id != owner_id:
            return False, "Only owner can unshare"
        
        if unshare_from in resource.shared_with:
            resource.shared_with.remove(unshare_from)
        
        self._audit(
            user_id=owner_id,
            action=AuditAction.UNSHARE,
            resource_type=resource.type,
            resource_id=resource_id,
            scope=ResourceScope.OWN,
            success=True,
            details={"unshared_from": unshare_from},
        )
        
        return True, f"Removed sharing from {unshare_from}"
    
    # =========================================================================
    # Queries
    # =========================================================================
    
    def list_resources(
        self,
        user_id: str,
        resource_type: Optional[ResourceType] = None,
        include_shared: bool = True,
        include_deleted: bool = False,
    ) -> list[dict]:
        """List all resources accessible to a user."""
        results = []
        
        for resource_id, resource in self._resources.items():
            # Skip deleted unless requested
            if resource.is_deleted and not include_deleted:
                continue
            
            # Filter by type
            if resource_type and resource.type != resource_type:
                continue
            
            # Check access
            can_access = (
                resource.owner_id == user_id or
                (include_shared and user_id in resource.shared_with)
            )
            
            if can_access:
                results.append({
                    "id": resource.id,
                    "type": resource.type.value,
                    "owner_id": resource.owner_id,
                    "is_owner": resource.owner_id == user_id,
                    "is_shared": user_id in resource.shared_with,
                    "created_at": resource.created_at.isoformat(),
                    "tags": resource.tags,
                })
        
        return results
    
    def get_audit_log(
        self,
        user_id: str,
        resource_id: Optional[str] = None,
        limit: int = 100,
    ) -> list[dict]:
        """Get audit log entries for a user or resource."""
        role = get_role_from_user_id(user_id) or "user"
        
        # Only privileged roles can see full audit log
        if role not in ["legal", "manager", "admin"]:
            # Users can only see their own actions
            entries = [e for e in self._audit_log if e.user_id == user_id]
        else:
            entries = self._audit_log
        
        # Filter by resource if specified
        if resource_id:
            entries = [e for e in entries if e.resource_id == resource_id]
        
        # Sort by timestamp, newest first
        entries = sorted(entries, key=lambda e: e.timestamp, reverse=True)
        
        # Limit and convert to dicts
        return [
            {
                "id": e.id,
                "timestamp": e.timestamp.isoformat(),
                "user_id": e.user_id,
                "action": e.action.value,
                "resource_type": e.resource_type.value,
                "resource_id": e.resource_id,
                "success": e.success,
                "checksum": e.checksum,
            }
            for e in entries[:limit]
        ]
    
    # =========================================================================
    # Audit Logging
    # =========================================================================
    
    def _audit(
        self,
        user_id: str,
        action: AuditAction,
        resource_type: ResourceType,
        resource_id: str,
        scope: ResourceScope,
        success: bool,
        details: Optional[dict] = None,
    ):
        """Create an immutable audit log entry."""
        entry = AuditEntry(
            id=str(uuid4())[:12],
            timestamp=datetime.now(timezone.utc),
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            scope=scope,
            success=success,
            details=details or {},
        )
        entry.checksum = entry.compute_checksum()
        
        self._audit_log.append(entry)
        
        # Keep log bounded (would use proper DB/storage in production)
        if len(self._audit_log) > 10000:
            self._audit_log = self._audit_log[-5000:]
    
    # =========================================================================
    # Stats
    # =========================================================================
    
    def get_stats(self) -> dict:
        """Get vault statistics."""
        resources = self._resources.values()
        return {
            "total_resources": len(self._resources),
            "by_type": {
                rt.value: len([r for r in resources if r.type == rt])
                for rt in ResourceType
            },
            "deleted": len([r for r in resources if r.is_deleted]),
            "shared": len([r for r in resources if r.shared_with]),
            "audit_entries": len(self._audit_log),
        }


# =============================================================================
# Singleton Instance
# =============================================================================

_vault_engine: Optional[VaultAccessEngine] = None


def get_vault_engine() -> VaultAccessEngine:
    """Get the singleton vault engine instance."""
    global _vault_engine
    if _vault_engine is None:
        _vault_engine = VaultAccessEngine()
    return _vault_engine


# =============================================================================
# Convenience Decorators
# =============================================================================

def require_vault_access(
    resource_type: ResourceType,
    action: AccessLevel,
):
    """
    Decorator to require vault access for an endpoint.
    
    Usage:
        @require_vault_access(ResourceType.DOCUMENT, AccessLevel.READ)
        async def get_document(user_id: str, doc_id: str):
            ...
    """
    def decorator(func):
        async def wrapper(*args, **kwargs):
            # Extract user_id and resource_id from kwargs
            user_id = kwargs.get("user_id") or kwargs.get("user", {}).get("user_id")
            resource_id = kwargs.get("resource_id") or kwargs.get("doc_id") or kwargs.get("id")
            
            if not user_id or not resource_id:
                return {"error": "Missing user_id or resource_id"}
            
            engine = get_vault_engine()
            result = engine.check_access(AccessRequest(
                user_id=user_id,
                resource_type=resource_type,
                resource_id=resource_id,
                action=action,
            ))
            
            if not result.allowed:
                return {"error": result.reason, "allowed": False}
            
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator
