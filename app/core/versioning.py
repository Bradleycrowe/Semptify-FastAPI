"""
API Versioning Module for Semptify.

Provides versioned API endpoints while maintaining backward compatibility.
Current version: v1
"""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse


# Version prefix constants
V1_PREFIX = "/api/v1"
LATEST_VERSION = "v1"
SUPPORTED_VERSIONS = ["v1"]


def create_versioned_router(
    prefix: str = "",
    tags: list[str] | None = None,
    **kwargs
) -> APIRouter:
    """
    Create a router with versioning support.
    
    Args:
        prefix: Additional prefix after version (e.g., "/documents")
        tags: OpenAPI tags
        **kwargs: Additional APIRouter kwargs
    
    Returns:
        APIRouter configured for versioning
    """
    full_prefix = f"{V1_PREFIX}{prefix}" if prefix else V1_PREFIX
    return APIRouter(prefix=full_prefix, tags=tags, **kwargs)


# Pre-configured routers for common resources
def get_v1_documents_router() -> APIRouter:
    """Router for /api/v1/documents"""
    return create_versioned_router("/documents", tags=["Documents"])


def get_v1_timeline_router() -> APIRouter:
    """Router for /api/v1/timeline"""
    return create_versioned_router("/timeline", tags=["Timeline"])


def get_v1_copilot_router() -> APIRouter:
    """Router for /api/v1/copilot"""
    return create_versioned_router("/copilot", tags=["AI Copilot"])


def get_v1_vault_router() -> APIRouter:
    """Router for /api/v1/vault"""
    return create_versioned_router("/vault", tags=["Vault"])


def get_v1_calendar_router() -> APIRouter:
    """Router for /api/v1/calendar"""
    return create_versioned_router("/calendar", tags=["Calendar"])


async def api_version_info(request: Request) -> JSONResponse:
    """
    Return API version information.
    
    GET /api/version
    """
    return JSONResponse({
        "current_version": LATEST_VERSION,
        "supported_versions": SUPPORTED_VERSIONS,
        "deprecation_notices": [],
        "documentation": {
            "v1": "/docs",
            "openapi": "/openapi.json"
        }
    })


# Router for version info endpoint
version_router = APIRouter(prefix="/api", tags=["API Info"])
version_router.add_api_route("/version", api_version_info, methods=["GET"])


# =============================================================================
# Version Deprecation Utilities
# =============================================================================

def deprecation_warning(version: str, sunset_date: str) -> dict:
    """
    Generate deprecation warning headers.
    
    Use in endpoint response:
        return JSONResponse(
            content={...},
            headers=deprecation_warning("v0", "2025-06-01")
        )
    """
    return {
        "Deprecation": f"version={version}",
        "Sunset": sunset_date,
        "Link": f'</api/version>; rel="successor-version"'
    }


class APIVersionHeader:
    """
    Dependency to extract and validate API version from header.
    
    Usage:
        @router.get("/resource")
        async def get_resource(version: str = Depends(APIVersionHeader())):
            ...
    """
    
    def __init__(self, default: str = LATEST_VERSION):
        self.default = default
    
    async def __call__(self, request: Request) -> str:
        version = request.headers.get("X-API-Version", self.default)
        if version not in SUPPORTED_VERSIONS:
            version = self.default
        return version
