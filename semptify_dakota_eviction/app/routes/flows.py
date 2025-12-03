"""
Dakota County Eviction Defense - Defense Flow Routes
Handles Answer, Counterclaim, Motion, and Hearing Prep flows.
"""

import json
import io
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List

from fastapi import APIRouter, Request, Query, Form, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

# Import services
import sys
sys.path.append(str(Path(__file__).parent.parent))
from services.i18n import get_string, get_all_strings, get_supported_languages, is_rtl
from services.pdf import (
    generate_answer_pdf,
    generate_counterclaim_pdf,
    generate_motion_pdf,
    generate_hearing_prep_pdf
)
from services.zip_service import create_defense_packet_zip

# ============================================================================
# Router Setup
# ============================================================================

router = APIRouter()

BASE_DIR = Path(__file__).parent.parent
TEMPLATES_DIR = BASE_DIR / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
templates.env.globals["_"] = get_string
templates.env.globals["is_rtl"] = is_rtl


# ============================================================================
# Pydantic Models
# ============================================================================

class AnswerData(BaseModel):
    tenant_name: str = Field(..., min_length=1)
    landlord_name: str = Field(..., min_length=1)
    case_number: str = ""
    address: str = ""
    served_date: str = ""
    defenses: List[str] = []
    defense_details: str = ""


class CounterclaimData(BaseModel):
    tenant_name: str = Field(..., min_length=1)
    landlord_name: str = Field(..., min_length=1)
    case_number: str = ""
    address: str = ""
    claims: List[str] = []
    claim_details: str = ""
    damages_requested: str = ""


class MotionData(BaseModel):
    motion_type: str = Field(..., pattern="^(dismiss|continuance|stay|fee_waiver)$")
    tenant_name: str = Field(..., min_length=1)
    landlord_name: str = Field(..., min_length=1)
    case_number: str = ""
    grounds: str = ""
    hearing_date: str = ""


class HearingPrepData(BaseModel):
    tenant_name: str = Field(..., min_length=1)
    hearing_date: str = ""
    hearing_time: str = ""
    is_zoom: bool = False
    checklist_items: List[str] = []
    documents_needed: List[str] = []


# ============================================================================
# Answer Flow Routes
# ============================================================================

@router.get("/answer", response_class=HTMLResponse)
async def answer_flow_start(
    request: Request,
    lang: str = Query("en"),
    step: int = Query(1, ge=1, le=5)
):
    """
    Answer to Eviction - Multi-step wizard.
    Step 1: Basic info (served date, case number)
    Step 2: Select defenses
    Step 3: Defense details
    Step 4: Review
    Step 5: Download
    """
    strings = get_all_strings(lang)
    
    # Defense options
    defenses = [
        {"id": "rent_paid", "label": get_string("defense_rent_paid", lang)},
        {"id": "habitability", "label": get_string("defense_habitability", lang)},
        {"id": "retaliation", "label": get_string("defense_retaliation", lang)},
        {"id": "improper_notice", "label": get_string("defense_improper_notice", lang)},
        {"id": "discrimination", "label": get_string("defense_discrimination", lang)},
        {"id": "nonpayment", "label": get_string("defense_nonpayment", lang)},
    ]
    
    return templates.TemplateResponse(f"flows/answer_step{step}.html", {
        "request": request,
        "lang": lang,
        "is_rtl": is_rtl(lang),
        "strings": strings,
        "step": step,
        "total_steps": 5,
        "defenses": defenses,
        "languages": get_supported_languages()
    })


@router.post("/answer/generate")
async def generate_answer(data: AnswerData, lang: str = Query("en")):
    """Generate Answer to Eviction PDF."""
    try:
        pdf_bytes = generate_answer_pdf(data.dict(), lang)
        
        filename = f"Answer_to_Eviction_{data.tenant_name.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.pdf"
        
        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"'
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Counterclaim Flow Routes
# ============================================================================

@router.get("/counterclaim", response_class=HTMLResponse)
async def counterclaim_flow_start(
    request: Request,
    lang: str = Query("en"),
    step: int = Query(1, ge=1, le=4)
):
    """
    Counterclaim - Multi-step wizard.
    Step 1: Basic info
    Step 2: Select claims
    Step 3: Details and damages
    Step 4: Review and download
    """
    strings = get_all_strings(lang)
    
    # Counterclaim options
    claims = [
        {"id": "repairs", "label": get_string("counterclaim_repairs", lang)},
        {"id": "deposit", "label": get_string("counterclaim_deposit", lang)},
        {"id": "illegal_fees", "label": get_string("counterclaim_illegal_fees", lang)},
        {"id": "lockout", "label": get_string("counterclaim_lockout", lang)},
        {"id": "utilities", "label": get_string("counterclaim_utilities", lang)},
    ]
    
    return templates.TemplateResponse(f"flows/counterclaim_step{step}.html", {
        "request": request,
        "lang": lang,
        "is_rtl": is_rtl(lang),
        "strings": strings,
        "step": step,
        "total_steps": 4,
        "claims": claims,
        "languages": get_supported_languages()
    })


@router.post("/counterclaim/generate")
async def generate_counterclaim(data: CounterclaimData, lang: str = Query("en")):
    """Generate Counterclaim PDF."""
    try:
        pdf_bytes = generate_counterclaim_pdf(data.dict(), lang)
        
        filename = f"Counterclaim_{data.tenant_name.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.pdf"
        
        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"'
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Motion Flow Routes
# ============================================================================

@router.get("/motions", response_class=HTMLResponse)
async def motions_menu(request: Request, lang: str = Query("en")):
    """Motions menu - Select motion type."""
    strings = get_all_strings(lang)
    
    motions = [
        {
            "id": "dismiss",
            "label": get_string("motion_dismiss", lang),
            "description": "Request dismissal of the eviction case"
        },
        {
            "id": "continuance",
            "label": get_string("motion_continuance", lang),
            "description": "Request to postpone the hearing"
        },
        {
            "id": "stay",
            "label": get_string("motion_stay", lang),
            "description": "Request to delay execution of judgment"
        },
        {
            "id": "fee_waiver",
            "label": get_string("motion_fee_waiver", lang),
            "description": "Request waiver of court filing fees"
        },
    ]
    
    return templates.TemplateResponse("flows/motions_menu.html", {
        "request": request,
        "lang": lang,
        "is_rtl": is_rtl(lang),
        "strings": strings,
        "motions": motions,
        "languages": get_supported_languages()
    })


@router.get("/motions/{motion_type}", response_class=HTMLResponse)
async def motion_form(
    request: Request,
    motion_type: str,
    lang: str = Query("en")
):
    """Motion form - Fill out specific motion."""
    if motion_type not in ["dismiss", "continuance", "stay", "fee_waiver"]:
        raise HTTPException(status_code=404, detail="Motion type not found")
    
    strings = get_all_strings(lang)
    
    return templates.TemplateResponse(f"flows/motion_{motion_type}.html", {
        "request": request,
        "lang": lang,
        "is_rtl": is_rtl(lang),
        "strings": strings,
        "motion_type": motion_type,
        "languages": get_supported_languages()
    })


@router.post("/motions/generate")
async def generate_motion(data: MotionData, lang: str = Query("en")):
    """Generate Motion PDF."""
    try:
        pdf_bytes = generate_motion_pdf(data.motion_type, data.dict(), lang)
        
        motion_names = {
            "dismiss": "Motion_to_Dismiss",
            "continuance": "Motion_for_Continuance",
            "stay": "Motion_to_Stay_Writ",
            "fee_waiver": "Fee_Waiver_Application"
        }
        
        filename = f"{motion_names.get(data.motion_type, 'Motion')}_{data.tenant_name.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.pdf"
        
        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"'
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Hearing Preparation Routes
# ============================================================================

@router.get("/hearing", response_class=HTMLResponse)
async def hearing_prep_start(
    request: Request,
    lang: str = Query("en"),
    step: int = Query(1, ge=1, le=3)
):
    """
    Hearing Preparation - Multi-step wizard.
    Step 1: Hearing info (date, time, format)
    Step 2: Document checklist
    Step 3: Generate prep packet
    """
    strings = get_all_strings(lang)
    
    # Standard documents to bring
    standard_docs = [
        "Lease/rental agreement",
        "All eviction papers received",
        "Rent receipts/payment records",
        "Photos of property conditions",
        "Written communications with landlord",
        "Witness contact information",
        "Any filed documents (Answer, Counterclaim, Motions)",
        "ID and proof of address"
    ]
    
    return templates.TemplateResponse(f"flows/hearing_step{step}.html", {
        "request": request,
        "lang": lang,
        "is_rtl": is_rtl(lang),
        "strings": strings,
        "step": step,
        "total_steps": 3,
        "standard_docs": standard_docs,
        "languages": get_supported_languages()
    })


@router.post("/hearing/generate")
async def generate_hearing_prep(data: HearingPrepData, lang: str = Query("en")):
    """Generate Hearing Preparation PDF."""
    try:
        pdf_bytes = generate_hearing_prep_pdf(data.dict(), lang)
        
        filename = f"Hearing_Prep_{data.tenant_name.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.pdf"
        
        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"'
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Complete Defense Packet
# ============================================================================

@router.post("/complete-packet")
async def generate_complete_packet(
    request: Request,
    lang: str = Query("en")
):
    """
    Generate complete defense packet ZIP with all documents.
    Expects JSON body with all form data.
    """
    try:
        body = await request.json()
        
        documents = []
        forms_to_include = []
        
        # Generate Answer if provided
        if "answer" in body:
            answer_pdf = generate_answer_pdf(body["answer"], lang)
            documents.append({
                "filename": "01_Answer_to_Eviction.pdf",
                "content": answer_pdf,
                "type": "answer"
            })
        
        # Generate Counterclaim if provided
        if "counterclaim" in body:
            counterclaim_pdf = generate_counterclaim_pdf(body["counterclaim"], lang)
            documents.append({
                "filename": "02_Counterclaim.pdf",
                "content": counterclaim_pdf,
                "type": "counterclaim"
            })
        
        # Generate Motions if provided
        if "motions" in body:
            for i, motion in enumerate(body["motions"], 1):
                motion_pdf = generate_motion_pdf(motion.get("motion_type", "dismiss"), motion, lang)
                documents.append({
                    "filename": f"03_{i:02d}_Motion_{motion.get('motion_type', 'unknown')}.pdf",
                    "content": motion_pdf,
                    "type": "motion"
                })
        
        # Generate Hearing Prep if provided
        if "hearing" in body:
            hearing_pdf = generate_hearing_prep_pdf(body["hearing"], lang)
            documents.append({
                "filename": "04_Hearing_Preparation.pdf",
                "content": hearing_pdf,
                "type": "hearing_prep"
            })
        
        # Load forms manifest
        forms_path = BASE_DIR / "assets" / "forms.json"
        if forms_path.exists():
            with open(forms_path, "r", encoding="utf-8") as f:
                forms_data = json.load(f)
                forms_to_include = forms_data.get("forms", [])
        
        # Create case info
        case_info = body.get("case_info", {
            "case_number": body.get("answer", {}).get("case_number", ""),
            "tenant_name": body.get("answer", {}).get("tenant_name", "Tenant"),
            "landlord_name": body.get("answer", {}).get("landlord_name", ""),
            "hearing_date": body.get("hearing", {}).get("hearing_date", "")
        })
        
        # Create ZIP bundle
        zip_bytes = create_defense_packet_zip(
            documents=documents,
            forms=forms_to_include,
            case_info=case_info,
            include_instructions=True
        )
        
        filename = f"Eviction_Defense_Packet_{case_info.get('tenant_name', 'Tenant').replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.zip"
        
        return StreamingResponse(
            io.BytesIO(zip_bytes),
            media_type="application/zip",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"'
            }
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Deadline Calculator
# ============================================================================

@router.get("/api/deadlines")
async def calculate_deadlines(
    served_date: str = Query(..., description="Date served (YYYY-MM-DD)"),
    hearing_date: Optional[str] = Query(None, description="Hearing date if known")
):
    """Calculate important deadlines based on served date."""
    try:
        served = datetime.strptime(served_date, "%Y-%m-%d")
        
        deadlines = {
            "answer_deadline": (served + timedelta(days=7)).strftime("%Y-%m-%d"),
            "answer_deadline_display": (served + timedelta(days=7)).strftime("%B %d, %Y"),
            "days_to_answer": max(0, (served + timedelta(days=7) - datetime.now()).days),
            "motion_deadline": None,
            "is_urgent": False
        }
        
        # If hearing date provided, calculate motion deadline
        if hearing_date:
            hearing = datetime.strptime(hearing_date, "%Y-%m-%d")
            motion_deadline = hearing - timedelta(days=3)
            deadlines["motion_deadline"] = motion_deadline.strftime("%Y-%m-%d")
            deadlines["motion_deadline_display"] = motion_deadline.strftime("%B %d, %Y")
            deadlines["days_to_hearing"] = max(0, (hearing - datetime.now()).days)
        
        # Check if urgent (less than 3 days to answer)
        if deadlines["days_to_answer"] <= 3:
            deadlines["is_urgent"] = True
        
        return JSONResponse(content=deadlines)
    
    except ValueError as e:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
