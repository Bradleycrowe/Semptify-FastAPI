"""
Semptify 5.0 - Vault Engine API Router

Exposes the VaultAccessEngine through REST endpoints.
All vault access should go through these endpoints or use the engine directly.
"""

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Body
from pydantic import BaseModel, Field

from app.core.security import require_user, StorageUser
from app.services.vault_engine import (
    VaultAccessEngine,
    get_vault_engine,
    ResourceType,
    AccessLevel,
    AccessRequest,
)


router = APIRouter(prefix="/api/vault-engine", tags=["Vault Engine"])


# =============================================================================
# Schemas
# =============================================================================

class ResourceReadRequest(BaseModel):
    """Request to read a vault resource."""
    resource_type: str = Field(..., description="Type: document, timeline_event, calendar_event, etc.")
    resource_id: str = Field(..., description="ID of the resource")
    reason: Optional[str] = Field(None, description="Reason for access (audit)")


class ResourceWriteRequest(BaseModel):
    """Request to write a vault resource."""
    resource_type: str = Field(..., description="Type: document, timeline_event, calendar_event, etc.")
    resource_id: str = Field(..., description="ID of the resource")
    data: Any = Field(..., description="Data to store")
    reason: Optional[str] = Field(None, description="Reason for access (audit)")


class ResourceDeleteRequest(BaseModel):
    """Request to delete a vault resource."""
    resource_type: str = Field(..., description="Type of resource")
    resource_id: str = Field(..., description="ID of the resource")
    hard_delete: bool = Field(False, description="Permanently delete (vs soft delete)")
    reason: Optional[str] = Field(None, description="Reason for deletion")


class ShareRequest(BaseModel):
    """Request to share a resource."""
    resource_id: str = Field(..., description="ID of the resource to share")
    share_with: str = Field(..., description="User ID to share with")
    reason: Optional[str] = Field(None, description="Reason for sharing")


class AccessCheckRequest(BaseModel):
    """Check if access is allowed."""
    resource_type: str
    resource_id: str
    action: str = Field(..., description="read, write, delete")


# =============================================================================
# Access Control Endpoints
# =============================================================================

@router.post("/check-access")
async def check_access(
    request: AccessCheckRequest,
    user: StorageUser = Depends(require_user),
    engine: VaultAccessEngine = Depends(get_vault_engine),
):
    """
    Check if current user can perform an action on a resource.
    
    Useful for UI to show/hide actions before attempting them.
    """
    try:
        resource_type = ResourceType(request.resource_type)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid resource type: {request.resource_type}")
    
    try:
        action = AccessLevel(request.action)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid action: {request.action}")
    
    access_request = AccessRequest(
        user_id=user.user_id,
        resource_type=resource_type,
        resource_id=request.resource_id,
        action=action,
    )
    
    result = engine.check_access(access_request)
    
    return {
        "allowed": result.allowed,
        "reason": result.reason,
        "scope": result.scope.value if result.scope else None,
        "request_id": result.request_id,
    }


# =============================================================================
# CRUD Endpoints
# =============================================================================

@router.post("/read")
async def read_resource(
    request: ResourceReadRequest,
    user: StorageUser = Depends(require_user),
    engine: VaultAccessEngine = Depends(get_vault_engine),
):
    """
    Read a resource from the vault.
    
    Access is verified and logged.
    """
    try:
        resource_type = ResourceType(request.resource_type)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid resource type: {request.resource_type}")
    
    success, data, result = engine.read(
        user_id=user.user_id,
        resource_type=resource_type,
        resource_id=request.resource_id,
        reason=request.reason,
    )
    
    if not success:
        if not result.allowed:
            raise HTTPException(status_code=403, detail=data.get("error", "Access denied"))
        raise HTTPException(status_code=404, detail=data.get("error", "Not found"))
    
    return {
        "success": True,
        "data": data,
        "access": {
            "scope": result.scope.value if result.scope else None,
            "request_id": result.request_id,
        },
    }


@router.post("/write")
async def write_resource(
    request: ResourceWriteRequest,
    user: StorageUser = Depends(require_user),
    engine: VaultAccessEngine = Depends(get_vault_engine),
):
    """
    Write (create/update) a resource in the vault.
    
    Access is verified and logged.
    """
    try:
        resource_type = ResourceType(request.resource_type)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid resource type: {request.resource_type}")
    
    success, data, result = engine.write(
        user_id=user.user_id,
        resource_type=resource_type,
        resource_id=request.resource_id,
        data=request.data,
        reason=request.reason,
    )
    
    if not success:
        raise HTTPException(status_code=403, detail=data.get("error", "Access denied"))
    
    return {
        "success": True,
        "id": data.get("id"),
        "created": data.get("created", False),
        "access": {
            "scope": result.scope.value if result.scope else None,
            "request_id": result.request_id,
        },
    }


@router.post("/delete")
async def delete_resource(
    request: ResourceDeleteRequest,
    user: StorageUser = Depends(require_user),
    engine: VaultAccessEngine = Depends(get_vault_engine),
):
    """
    Delete a resource from the vault.
    
    Soft delete by default (recoverable). Set hard_delete=true to permanently remove.
    """
    try:
        resource_type = ResourceType(request.resource_type)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid resource type: {request.resource_type}")
    
    success, data, result = engine.delete(
        user_id=user.user_id,
        resource_type=resource_type,
        resource_id=request.resource_id,
        reason=request.reason,
        hard_delete=request.hard_delete,
    )
    
    if not success:
        if not result.allowed:
            raise HTTPException(status_code=403, detail=data.get("error", "Access denied"))
        raise HTTPException(status_code=404, detail=data.get("error", "Not found"))
    
    return {
        "success": True,
        "deleted": data.get("deleted"),
        "hard_delete": data.get("hard", False),
    }


# =============================================================================
# Sharing Endpoints
# =============================================================================

@router.post("/share")
async def share_resource(
    request: ShareRequest,
    user: StorageUser = Depends(require_user),
    engine: VaultAccessEngine = Depends(get_vault_engine),
):
    """
    Share a resource with another user.
    
    Only owners or privileged users can share.
    """
    success, message = engine.share(
        owner_id=user.user_id,
        resource_id=request.resource_id,
        share_with=request.share_with,
        reason=request.reason,
    )
    
    if not success:
        raise HTTPException(status_code=403, detail=message)
    
    return {"success": True, "message": message}


@router.post("/unshare")
async def unshare_resource(
    resource_id: str = Body(...),
    unshare_from: str = Body(...),
    user: StorageUser = Depends(require_user),
    engine: VaultAccessEngine = Depends(get_vault_engine),
):
    """
    Remove sharing from a user.
    
    Only owners can unshare.
    """
    success, message = engine.unshare(
        owner_id=user.user_id,
        resource_id=resource_id,
        unshare_from=unshare_from,
    )
    
    if not success:
        raise HTTPException(status_code=403, detail=message)
    
    return {"success": True, "message": message}


# =============================================================================
# Query Endpoints
# =============================================================================

@router.get("/list")
async def list_resources(
    resource_type: Optional[str] = Query(None, description="Filter by type"),
    include_shared: bool = Query(True, description="Include shared resources"),
    include_deleted: bool = Query(False, description="Include deleted resources"),
    user: StorageUser = Depends(require_user),
    engine: VaultAccessEngine = Depends(get_vault_engine),
):
    """
    List all resources accessible to the current user.
    """
    rt = None
    if resource_type:
        try:
            rt = ResourceType(resource_type)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid resource type: {resource_type}")
    
    resources = engine.list_resources(
        user_id=user.user_id,
        resource_type=rt,
        include_shared=include_shared,
        include_deleted=include_deleted,
    )
    
    return {
        "count": len(resources),
        "resources": resources,
    }


@router.get("/audit")
async def get_audit_log(
    resource_id: Optional[str] = Query(None, description="Filter by resource"),
    limit: int = Query(100, ge=1, le=1000),
    user: StorageUser = Depends(require_user),
    engine: VaultAccessEngine = Depends(get_vault_engine),
):
    """
    Get audit log entries.
    
    Regular users see only their own actions.
    Privileged users (legal, manager, admin) see all entries.
    """
    entries = engine.get_audit_log(
        user_id=user.user_id,
        resource_id=resource_id,
        limit=limit,
    )
    
    return {
        "count": len(entries),
        "entries": entries,
    }


@router.get("/stats")
async def get_stats(
    user: StorageUser = Depends(require_user),
    engine: VaultAccessEngine = Depends(get_vault_engine),
):
    """Get vault statistics (admin only in production)."""
    return engine.get_stats()


# =============================================================================
# Resource Types Enum
# =============================================================================

@router.get("/resource-types")
async def list_resource_types():
    """List all valid resource types."""
    return {
        "types": [rt.value for rt in ResourceType],
    }


@router.get("/access-levels")
async def list_access_levels():
    """List all valid access levels."""
    return {
        "levels": [al.value for al in AccessLevel],
    }
