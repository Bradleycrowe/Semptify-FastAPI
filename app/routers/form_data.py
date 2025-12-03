"""
Form Data Router
API endpoints for the central form data hub.
Connects document processing, defense modules, and form generation.
"""

from typing import Optional, Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.core.security import require_user, StorageUser
from app.services.form_data import get_form_data_service, FormDataService


router = APIRouter()


# =============================================================================
# Request/Response Models
# =============================================================================

class PartyInfoUpdate(BaseModel):
    name: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None


class CaseInfoUpdate(BaseModel):
    case_number: Optional[str] = None
    property_address: Optional[str] = None
    property_city: Optional[str] = None
    property_state: Optional[str] = None
    property_zip: Optional[str] = None
    unit_number: Optional[str] = None
    lease_start_date: Optional[str] = None
    lease_end_date: Optional[str] = None
    monthly_rent: Optional[float] = None
    security_deposit: Optional[float] = None
    notice_date: Optional[str] = None
    notice_type: Optional[str] = None
    summons_date: Optional[str] = None
    hearing_date: Optional[str] = None
    hearing_time: Optional[str] = None
    rent_claimed: Optional[float] = None
    late_fees_claimed: Optional[float] = None
    total_claimed: Optional[float] = None
    tenant: Optional[PartyInfoUpdate] = None
    landlord: Optional[PartyInfoUpdate] = None
    notes: Optional[str] = None


class DefenseAction(BaseModel):
    defense_code: str


class CounterclaimAction(BaseModel):
    claim_code: str


# =============================================================================
# Endpoints
# =============================================================================

@router.get("/")
async def get_form_data(
    user: StorageUser = Depends(require_user),
):
    """
    Get all form data for the current user.
    
    This is the central data hub - returns:
    - Case information (parties, property, dates)
    - All documents and their extracted data
    - Timeline events
    - Pre-filled form data for all court forms
    """
    service = get_form_data_service(user.user_id)
    await service.load()
    return service.to_dict()


@router.get("/summary")
async def get_case_summary(
    user: StorageUser = Depends(require_user),
):
    """
    Get a summary of the current case status.
    
    Quick overview including:
    - Case number and stage
    - Days until hearing
    - Defense and counterclaim counts
    - Document counts
    """
    service = get_form_data_service(user.user_id)
    await service.load()
    return service.get_case_summary()


@router.put("/case")
async def update_case_info(
    updates: CaseInfoUpdate,
    user: StorageUser = Depends(require_user),
):
    """
    Update case information.
    
    All fields are optional - only provided fields will be updated.
    This data flows to all form generation endpoints.
    """
    service = get_form_data_service(user.user_id)
    await service.load()
    
    update_dict = updates.model_dump(exclude_unset=True)
    
    # Convert nested models
    if updates.tenant:
        update_dict["tenant"] = updates.tenant.model_dump(exclude_unset=True)
    if updates.landlord:
        update_dict["landlord"] = updates.landlord.model_dump(exclude_unset=True)
    
    service.update_case_info(update_dict)
    return {"status": "updated", "case": service.get_case_summary()}


@router.get("/forms/answer")
async def get_answer_form_data(
    user: StorageUser = Depends(require_user),
):
    """
    Get pre-filled data for the Answer to Eviction Complaint form.
    
    Returns all fields needed for HOU301 form, populated from:
    - Case information entered by user
    - Data extracted from uploaded documents
    - Timeline events
    """
    service = get_form_data_service(user.user_id)
    await service.load()
    return {
        "form_id": "HOU301",
        "form_name": "Answer to Eviction Complaint",
        "data": service.get_answer_form_data(),
        "instructions": [
            "Review all pre-filled information for accuracy",
            "Select your defenses from the list",
            "Add any counterclaims if applicable",
            "Sign and date the form",
            "File with the court before your deadline",
        ]
    }


@router.get("/forms/motion/{motion_type}")
async def get_motion_form_data(
    motion_type: str,
    user: StorageUser = Depends(require_user),
):
    """
    Get pre-filled data for motion forms.
    
    Supported motion types:
    - dismiss: Motion to Dismiss
    - continuance: Motion for Continuance  
    - stay: Motion to Stay Eviction
    - fee_waiver: Fee Waiver Application
    """
    valid_types = ["dismiss", "continuance", "stay", "fee_waiver"]
    if motion_type not in valid_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid motion type. Must be one of: {valid_types}"
        )
    
    service = get_form_data_service(user.user_id)
    await service.load()
    return {
        "motion_type": motion_type,
        "data": service.get_motion_form_data(motion_type),
    }


@router.get("/forms/counterclaim")
async def get_counterclaim_form_data(
    user: StorageUser = Depends(require_user),
):
    """
    Get pre-filled data for counterclaim form.
    
    Returns data for filing counterclaims against the landlord.
    """
    service = get_form_data_service(user.user_id)
    await service.load()
    return {
        "form_name": "Counterclaim",
        "data": service.get_counterclaim_form_data(),
    }


@router.post("/defenses/add")
async def add_defense(
    action: DefenseAction,
    user: StorageUser = Depends(require_user),
):
    """
    Add a defense to the case.
    
    Defense codes come from /dakota/procedures/defenses endpoint.
    Selected defenses will be included in generated forms.
    """
    service = get_form_data_service(user.user_id)
    await service.load()
    defenses = service.add_defense(action.defense_code)
    return {"defenses": defenses, "count": len(defenses)}


@router.post("/defenses/remove")
async def remove_defense(
    action: DefenseAction,
    user: StorageUser = Depends(require_user),
):
    """Remove a defense from the case."""
    service = get_form_data_service(user.user_id)
    await service.load()
    defenses = service.remove_defense(action.defense_code)
    return {"defenses": defenses, "count": len(defenses)}


@router.get("/defenses")
async def get_selected_defenses(
    user: StorageUser = Depends(require_user),
):
    """Get all selected defenses for this case."""
    service = get_form_data_service(user.user_id)
    await service.load()
    return {
        "defenses": service.form_data.case.selected_defenses,
        "count": len(service.form_data.case.selected_defenses),
    }


@router.post("/counterclaims/add")
async def add_counterclaim(
    action: CounterclaimAction,
    user: StorageUser = Depends(require_user),
):
    """
    Add a counterclaim to the case.
    
    Counterclaim codes come from /dakota/procedures/counterclaims endpoint.
    """
    service = get_form_data_service(user.user_id)
    await service.load()
    claims = service.add_counterclaim(action.claim_code)
    return {"counterclaims": claims, "count": len(claims)}


@router.get("/counterclaims")
async def get_counterclaims(
    user: StorageUser = Depends(require_user),
):
    """Get all counterclaims for this case."""
    service = get_form_data_service(user.user_id)
    await service.load()
    return {
        "counterclaims": service.form_data.case.counterclaims,
        "count": len(service.form_data.case.counterclaims),
    }


@router.get("/documents")
async def get_case_documents(
    user: StorageUser = Depends(require_user),
):
    """
    Get all documents associated with this case.
    
    Returns documents from the vault with extracted data.
    """
    service = get_form_data_service(user.user_id)
    await service.load()
    return {
        "documents": service.form_data.documents,
        "count": len(service.form_data.documents),
        "extracted_dates": service.form_data.extracted_dates,
        "extracted_amounts": service.form_data.extracted_amounts,
    }


@router.get("/timeline")
async def get_case_timeline(
    user: StorageUser = Depends(require_user),
):
    """
    Get timeline events for this case.
    
    Events are derived from uploaded documents and manual entries.
    """
    service = get_form_data_service(user.user_id)
    await service.load()
    return {
        "events": service.form_data.timeline_events,
        "count": len(service.form_data.timeline_events),
    }


@router.post("/refresh")
async def refresh_form_data(
    user: StorageUser = Depends(require_user),
):
    """
    Refresh form data by re-processing all documents.
    
    Call this after uploading new documents to update extracted data.
    """
    # Clear cached service to force reload
    from app.services.form_data import _form_data_services
    if user.user_id in _form_data_services:
        del _form_data_services[user.user_id]
    
    service = get_form_data_service(user.user_id)
    await service.load()
    return {
        "status": "refreshed",
        "summary": service.get_case_summary(),
    }
