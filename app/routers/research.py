"""
Research Module Router - API Endpoints for Landlord/Property Research
=====================================================================

Provides API access to landlord/property research including:
- Tax records, assessments
- Liens, deeds, UCC filings
- Emergency call history
- News mentions
- Business registry (SOS)
- Bankruptcy records
- Insurance broker info
"""

import io
from fastapi import APIRouter, HTTPException, Query, Depends
from fastapi.responses import StreamingResponse
from typing import Any, Dict, List, Optional
from pydantic import BaseModel

from app.core.security import require_user, StorageUser
from app.services.research_module import get_research_service

router = APIRouter(prefix="/api/research", tags=["Research Module"])


# Request/Response Models
class ResearchRequest(BaseModel):
    """Request to research a property"""
    property_id: str
    user_id: Optional[str] = "anonymous"


class FraudFlagResponse(BaseModel):
    """Fraud flag in response"""
    type: str
    detail: str
    severity: str


class ResearchSummary(BaseModel):
    """Summary of research findings"""
    property_id: str
    owner_name: Optional[str]
    site_address: Optional[str]
    lien_count: int
    ucc_filing_count: int
    emergency_call_count: int
    news_mention_count: int
    bankruptcy_case_count: int
    fraud_flag_count: int
    fraud_flags: List[FraudFlagResponse]


# Health Check
@router.get("/health")
async def research_health_check():
    """Health check for research module"""
    return {"status": "healthy", "service": "research_module"}


# Main Research Endpoint
@router.post("/property/{property_id}")
async def research_property(
    property_id: str,
    user: StorageUser = Depends(require_user),
):
    """
    Run full research pipeline on a property.
    
    Collects:
    - Assessor data (taxes, ownership)
    - Recorder data (deeds, liens)
    - UCC filings
    - Emergency call history
    - News mentions
    - Secretary of State records
    - Bankruptcy records
    - Insurance broker info
    
    Returns comprehensive profile with fraud flags.
    """
    service = get_research_service()
    
    try:
        result = await service.collect_landlord_data(
            user_id=user.user_id,
            property_id=property_id,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Research failed: {str(e)}")


@router.get("/property/{property_id}")
async def get_property_profile(
    property_id: str,
    user: StorageUser = Depends(require_user)
):
    """Get cached profile for a property (must run research first)"""
    service = get_research_service()
    profile = service.get_profile(property_id)
    
    if not profile:
        raise HTTPException(
            status_code=404,
            detail=f"No profile found for {property_id}. Run POST /research/property/{property_id} first.",
        )
    
    return profile.to_dict()


@router.get("/property/{property_id}/summary")
async def get_property_summary(
    property_id: str,
    user: StorageUser = Depends(require_user)
):
    """Get a summary of research findings for a property"""
    service = get_research_service()
    profile = service.get_profile(property_id)
    
    if not profile:
        raise HTTPException(
            status_code=404,
            detail=f"No profile found for {property_id}. Run POST /research/property/{property_id} first.",
        )
    
    return {
        "property_id": profile.property_id,
        "owner_name": profile.owner_name,
        "site_address": profile.site_address,
        "lien_count": len(profile.liens),
        "ucc_filing_count": len(profile.ucc_filings),
        "deed_count": len(profile.deeds),
        "emergency_call_count": len(profile.emergency_calls),
        "news_mention_count": len(profile.news_mentions),
        "bankruptcy_case_count": len(profile.bankruptcy_cases),
        "fraud_flag_count": len(profile.fraud_flags),
        "fraud_flags": [f.to_dict() for f in profile.fraud_flags],
        "generated_at": profile.generated_at.isoformat(),
    }


@router.get("/property/{property_id}/fraud-flags")
async def get_property_fraud_flags(
    property_id: str,
    user: StorageUser = Depends(require_user)
):
    """Get fraud flags for a property"""
    service = get_research_service()
    profile = service.get_profile(property_id)
    
    if not profile:
        raise HTTPException(
            status_code=404,
            detail=f"No profile found for {property_id}. Run research first.",
        )
    
    return {
        "property_id": property_id,
        "flags": [f.to_dict() for f in profile.fraud_flags],
        "count": len(profile.fraud_flags),
        "has_high_severity": any(f.severity in ("high", "critical") for f in profile.fraud_flags),
    }


@router.get("/property/{property_id}/download")
async def download_evidence_zip(
    property_id: str,
    user: StorageUser = Depends(require_user)
):
    """
    Download the evidence ZIP for a property.
    
    Contains:
    - profile.json: Full research profile
    - checkpoint.json: Research checkpoint
    - summary.txt: Human-readable summary
    """
    service = get_research_service()
    zip_bytes = service.get_zip(property_id)
    
    if not zip_bytes:
        raise HTTPException(
            status_code=404,
            detail=f"No evidence ZIP found for {property_id}. Run research first.",
        )
    
    filename = f"{property_id}_evidence.zip"
    return StreamingResponse(
        io.BytesIO(zip_bytes),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/checkpoint/{checkpoint_id}")
async def get_checkpoint(
    checkpoint_id: str,
    user: StorageUser = Depends(require_user)
):
    """Get a research checkpoint by ID"""
    service = get_research_service()
    checkpoint = service.get_checkpoint(checkpoint_id)
    
    if not checkpoint:
        raise HTTPException(status_code=404, detail="Checkpoint not found")
    
    return checkpoint.to_dict()


# Data Source Endpoints (for individual lookups)
@router.get("/assessor")
async def get_assessor_data_query(
    property_id: Optional[str] = Query(None, description="Property ID to lookup"),
    user: StorageUser = Depends(require_user)
):
    """Get assessor data for a property (taxes, ownership)"""
    if not property_id:
        raise HTTPException(status_code=422, detail="property_id is required")
    
    service = get_research_service()
    try:
        data = await service.fetch_assessor(property_id)
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class AssessorRequest(BaseModel):
    """Request for assessor lookup"""
    property_id: str
    county: Optional[str] = "hennepin"


@router.post("/assessor")
async def post_assessor_data(
    request: AssessorRequest,
    user: StorageUser = Depends(require_user)
):
    """Get assessor data for a property via POST"""
    service = get_research_service()
    try:
        data = await service.fetch_assessor(request.property_id)
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/assessor/{property_id}")
async def get_assessor_data(
    property_id: str,
    user: StorageUser = Depends(require_user)
):
    """Get assessor data for a property (taxes, ownership)"""
    service = get_research_service()
    try:
        data = await service.fetch_assessor(property_id)
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/recorder/{property_id}")
async def get_recorder_data(
    property_id: str,
    user: StorageUser = Depends(require_user)
):
    """Get recorder data for a property (deeds, liens)"""
    service = get_research_service()
    try:
        data = await service.fetch_recorder_deeds(property_id)
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ucc")
async def get_ucc_filings(
    entity_name: str = Query(..., description="Entity name to search"),
    user: StorageUser = Depends(require_user)
):
    """Search UCC filings for an entity"""
    service = get_research_service()
    try:
        data = await service.fetch_ucc(entity_name)
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/dispatch")
async def get_dispatch_calls(
    property_id: Optional[str] = Query(None),
    address: Optional[str] = Query(None),
    user: StorageUser = Depends(require_user),
):
    """Get emergency dispatch calls near a property"""
    if not property_id and not address:
        raise HTTPException(status_code=400, detail="Provide property_id or address")
    
    service = get_research_service()
    try:
        data = await service.fetch_dispatch(property_id or "", address)
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/news")
async def get_news_mentions(
    entity_name: Optional[str] = Query(None),
    address: Optional[str] = Query(None),
    query: Optional[str] = Query(None, description="Search query (alias for entity_name)"),
    user: StorageUser = Depends(require_user),
):
    """Search news for mentions of entity or address"""
    search_term = entity_name or query
    if not search_term and not address:
        raise HTTPException(status_code=422, detail="Provide entity_name, query, or address")

    service = get_research_service()
    try:
        data = await service.fetch_news(search_term or "", address)
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
@router.get("/sos")
async def get_sos_entity(
    entity_name: str = Query(..., description="Entity name to search"),
    user: StorageUser = Depends(require_user)
):
    """Search Secretary of State business registry"""
    service = get_research_service()
    try:
        data = await service.fetch_sos(entity_name)
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/bankruptcy")
async def get_bankruptcy_cases(
    entity_name: str = Query(..., description="Entity name to search"),
    user: StorageUser = Depends(require_user)
):
    """Search bankruptcy records for an entity"""
    service = get_research_service()
    try:
        data = await service.fetch_bankruptcy(entity_name)
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/insurance")
async def get_insurance_info(
    entity_name: str = Query(..., description="Entity name to search"),
    user: StorageUser = Depends(require_user)
):
    """Get insurance broker/policy info for an entity"""
    service = get_research_service()
    try:
        data = await service.fetch_insurance(entity_name)
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sources")
async def list_data_sources(
    user: StorageUser = Depends(require_user)
):
    """List configured data sources and their endpoints"""
    from app.services.research_module import CFG

    # Return list directly with id field for test compatibility
    return [
        {"id": "assessor", "name": "Assessor", "base_url": CFG["ASSESSOR_BASE"], "provides": ["taxes", "ownership", "legal_description"]},
        {"id": "recorder", "name": "Recorder", "base_url": CFG["RECORDER_BASE"], "provides": ["deeds", "liens"]},
        {"id": "ucc", "name": "UCC", "base_url": CFG["RECORDER_UCC_BASE"], "provides": ["ucc_filings"]},
        {"id": "dispatch", "name": "Dispatch", "base_url": CFG["DISPATCH_BASE"], "provides": ["emergency_calls"]},
        {"id": "news", "name": "News", "base_url": CFG["NEWS_BASE"], "provides": ["news_mentions"]},
        {"id": "sos", "name": "SOS", "base_url": CFG["SOS_BASE"], "provides": ["entity_info", "registered_agents"]},
        {"id": "bankruptcy", "name": "Bankruptcy", "base_url": CFG["BANKRUPTCY_BASE"], "provides": ["bankruptcy_cases"]},
        {"id": "insurance", "name": "Insurance", "base_url": CFG["INSURANCE_BASE"], "provides": ["brokers", "policies"]},
    ]