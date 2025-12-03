"""
Dakota County Eviction Defense - Forms Router
Handles court forms library, auto-fill, and PDF generation.
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from fastapi import APIRouter, Query, HTTPException, Depends
from fastapi.responses import HTMLResponse, JSONResponse, Response
from pydantic import BaseModel

from app.services.eviction.i18n import get_string, get_all_strings, is_rtl
from app.services.eviction.pdf import (
    generate_answer_pdf,
    generate_counterclaim_pdf,
    generate_motion_pdf,
    generate_hearing_prep_pdf,
    WEASYPRINT_AVAILABLE,
)
from app.services.form_data import get_form_data_service, FormDataService
from app.core.user_context import UserContext
from app.core.security import get_current_user
from app.core.event_bus import event_bus, EventType

router = APIRouter()


# ============================================================================
# Pydantic Models for Form Generation
# ============================================================================

class AnswerFormRequest(BaseModel):
    """Request to generate Answer to Eviction form"""
    tenant_name: Optional[str] = None
    landlord_name: Optional[str] = None
    case_number: Optional[str] = None
    property_address: Optional[str] = None
    served_date: Optional[str] = None
    defenses: Optional[List[str]] = None
    defense_details: Optional[str] = None
    auto_fill: bool = True  # Use extracted case data


class CounterclaimRequest(BaseModel):
    """Request to generate Counterclaim form"""
    tenant_name: Optional[str] = None
    landlord_name: Optional[str] = None
    case_number: Optional[str] = None
    property_address: Optional[str] = None
    claims: Optional[List[str]] = None
    claim_details: Optional[str] = None
    damages_requested: Optional[str] = None
    auto_fill: bool = True


class MotionRequest(BaseModel):
    """Request to generate Motion form"""
    motion_type: str  # dismiss, continuance, stay, fee_waiver
    tenant_name: Optional[str] = None
    landlord_name: Optional[str] = None
    case_number: Optional[str] = None
    grounds: Optional[str] = None
    hearing_date: Optional[str] = None
    auto_fill: bool = True


class HearingPrepRequest(BaseModel):
    """Request to generate Hearing Prep checklist"""
    tenant_name: Optional[str] = None
    hearing_date: Optional[str] = None
    hearing_time: Optional[str] = None
    is_zoom: bool = False
    additional_items: Optional[List[str]] = None
    auto_fill: bool = True


# ============================================================================
# Court Forms Data
# ============================================================================

COURT_FORMS = [
    {
        "id": "HOU301",
        "name": "Answer to Eviction Complaint",
        "name_es": "Respuesta a la Demanda de Desalojo",
        "name_so": "Jawaabta Dacwadda Saarista",
        "name_ar": "الرد على شكوى الإخلاء",
        "description": "Official form to respond to an eviction complaint",
        "url": "https://www.mncourts.gov/GetForms.aspx?c=19&f=272",
        "category": "answer"
    },
    {
        "id": "HOU302",
        "name": "Motion to Dismiss",
        "name_es": "Moción para Desestimar",
        "name_so": "Codsiga Joojinta",
        "name_ar": "طلب رفض الدعوى",
        "description": "Request to dismiss the eviction case",
        "url": "https://www.mncourts.gov/GetForms.aspx?c=19",
        "category": "motion"
    },
    {
        "id": "HOU303",
        "name": "Motion for Continuance",
        "name_es": "Moción de Aplazamiento",
        "name_so": "Codsiga Dib u Dhigista",
        "name_ar": "طلب تأجيل",
        "description": "Request to postpone the hearing date",
        "url": "https://www.mncourts.gov/GetForms.aspx?c=19",
        "category": "motion"
    },
    {
        "id": "HOU304",
        "name": "Counterclaim Form",
        "name_es": "Formulario de Contrademanda",
        "name_so": "Foomka Dacwadda Lidka ah",
        "name_ar": "نموذج الدعوى المضادة",
        "description": "Assert claims against your landlord",
        "url": "https://www.mncourts.gov/GetForms.aspx?c=19",
        "category": "counterclaim"
    },
    {
        "id": "HOU305",
        "name": "Expungement Request",
        "name_es": "Solicitud de Eliminación",
        "name_so": "Codsiga Tirtirka",
        "name_ar": "طلب محو السجل",
        "description": "Request to seal eviction records",
        "url": "https://www.mncourts.gov/GetForms.aspx?c=19",
        "category": "expungement"
    },
    {
        "id": "HOU306",
        "name": "Motion to Stay Eviction",
        "name_es": "Moción para Suspender el Desalojo",
        "name_so": "Codsiga Joojinta Saarista",
        "name_ar": "طلب وقف الإخلاء",
        "description": "Request to pause the eviction process",
        "url": "https://www.mncourts.gov/GetForms.aspx?c=19",
        "category": "motion"
    },
    {
        "id": "IFP",
        "name": "Fee Waiver Application (IFP)",
        "name_es": "Solicitud de Exención de Tarifas",
        "name_so": "Codsiga Ka Dhaafida Kharashka",
        "name_ar": "طلب إعفاء من الرسوم",
        "description": "In Forma Pauperis - waive court fees if you cannot afford them",
        "url": "https://www.mncourts.gov/GetForms.aspx?c=11&f=92",
        "category": "fee_waiver"
    },
    {
        "id": "HOU307",
        "name": "Habitability Complaint",
        "name_es": "Queja de Habitabilidad",
        "name_so": "Cabasho ku saabsan Degganaanshaha",
        "name_ar": "شكوى صلاحية السكن",
        "description": "Document housing code violations",
        "url": "https://www.mncourts.gov/GetForms.aspx?c=19",
        "category": "habitability"
    },
    {
        "id": "HOU308",
        "name": "Rent Escrow Request",
        "name_es": "Solicitud de Depósito de Alquiler",
        "name_so": "Codsiga Kirada Ceymiska",
        "name_ar": "طلب حساب ضمان الإيجار",
        "description": "Pay rent to court instead of landlord due to repair issues",
        "url": "https://www.mncourts.gov/GetForms.aspx?c=19",
        "category": "rent_escrow"
    },
    {
        "id": "HOU309",
        "name": "Certificate of Service",
        "name_es": "Certificado de Servicio",
        "name_so": "Shahaadada Adeegga",
        "name_ar": "شهادة التبليغ",
        "description": "Prove you delivered documents to the other party",
        "url": "https://www.mncourts.gov/GetForms.aspx?c=19",
        "category": "service"
    }
]

RESOURCES = [
    {
        "name": "HOME Line",
        "phone": "612-728-5767",
        "description": "Free tenant hotline - legal advice and assistance",
        "url": "https://homelinemn.org"
    },
    {
        "name": "Southern MN Regional Legal Services (SMRLS)",
        "phone": "651-222-5863",
        "description": "Free legal services for qualifying tenants",
        "url": "https://www.smrls.org"
    },
    {
        "name": "Dakota County Housing Authority",
        "phone": "651-456-2476",
        "description": "Emergency rental assistance programs",
        "url": "https://www.dakotacda.org"
    },
    {
        "name": "MN Courts Self-Help Center",
        "phone": "651-435-6535",
        "description": "Court staff can help you understand forms and procedures",
        "url": "https://www.mncourts.gov/selfhelp"
    }
]


def get_html_page(title: str, content: str, lang: str = "en") -> str:
    """Generate full HTML page."""
    rtl = is_rtl(lang)
    strings = get_all_strings(lang)
    
    return f"""
<!DOCTYPE html>
<html lang="{lang}" dir="{'rtl' if rtl else 'ltr'}">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title} - {strings.get('app_title', 'Eviction Defense')}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #1e3a5f 0%, #0d1b2a 100%);
            color: #fff;
            min-height: 100vh;
            padding: 1rem;
        }}
        .container {{ max-width: 900px; margin: 0 auto; padding: 1rem; }}
        header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 1rem 0;
            border-bottom: 1px solid rgba(255,255,255,0.1);
            margin-bottom: 2rem;
        }}
        h1 {{ font-size: 1.5rem; }}
        .card {{
            background: rgba(255,255,255,0.05);
            border: 1px solid rgba(255,255,255,0.1);
            border-radius: 1rem;
            padding: 1.5rem;
            margin-bottom: 1.5rem;
        }}
        .card h2 {{ margin-bottom: 1rem; color: #94a3b8; font-size: 1.125rem; }}
        .btn {{
            display: inline-block;
            padding: 0.5rem 1rem;
            background: #3b82f6;
            color: white;
            text-decoration: none;
            border-radius: 0.5rem;
            font-size: 0.875rem;
            transition: all 0.2s;
        }}
        .btn:hover {{ background: #2563eb; }}
        .btn-secondary {{ background: #475569; }}
        .form-list {{ display: flex; flex-direction: column; gap: 1rem; }}
        .form-item {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 1rem;
            background: rgba(255,255,255,0.03);
            border-radius: 0.5rem;
            gap: 1rem;
        }}
        .form-info {{ flex: 1; }}
        .form-name {{ font-weight: 500; margin-bottom: 0.25rem; }}
        .form-desc {{ font-size: 0.875rem; color: #94a3b8; }}
        .form-id {{ font-size: 0.75rem; color: #64748b; }}
        .resource-item {{
            padding: 1rem;
            background: rgba(255,255,255,0.03);
            border-radius: 0.5rem;
            margin-bottom: 0.75rem;
        }}
        .resource-name {{ font-weight: 500; margin-bottom: 0.25rem; }}
        .resource-phone {{ color: #3b82f6; font-weight: 500; }}
        .resource-desc {{ font-size: 0.875rem; color: #94a3b8; margin-top: 0.25rem; }}
        .categories {{ display: flex; flex-wrap: wrap; gap: 0.5rem; margin-bottom: 1.5rem; }}
        .category-btn {{
            padding: 0.5rem 1rem;
            background: rgba(255,255,255,0.1);
            border: none;
            border-radius: 2rem;
            color: #94a3b8;
            cursor: pointer;
            font-size: 0.875rem;
            text-decoration: none;
        }}
        .category-btn:hover, .category-btn.active {{ background: #3b82f6; color: white; }}
        .lang-switcher {{ display: flex; gap: 0.5rem; }}
        .lang-switcher a {{
            padding: 0.25rem 0.75rem;
            background: rgba(255,255,255,0.1);
            border-radius: 0.25rem;
            color: #94a3b8;
            text-decoration: none;
            font-size: 0.875rem;
        }}
        .lang-switcher a:hover, .lang-switcher a.active {{ background: #3b82f6; color: white; }}
        .nav-buttons {{ margin-top: 1.5rem; }}
        footer {{ margin-top: 2rem; padding-top: 1rem; border-top: 1px solid rgba(255,255,255,0.1); font-size: 0.875rem; color: #64748b; }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>📁 {strings.get('forms_library', 'Court Forms Library')}</h1>
            <div class="lang-switcher">
                <a href="?lang=en" {'class="active"' if lang == 'en' else ''}>EN</a>
                <a href="?lang=es" {'class="active"' if lang == 'es' else ''}>ES</a>
                <a href="?lang=so" {'class="active"' if lang == 'so' else ''}>SO</a>
                <a href="?lang=ar" {'class="active"' if lang == 'ar' else ''}>عربي</a>
            </div>
        </header>
        
        {content}
        
        <footer>
            <p>{strings.get('disclaimer', 'This tool provides information only, not legal advice.')}</p>
        </footer>
    </div>
</body>
</html>
"""


# ============================================================================
# Forms Library UI
# ============================================================================

@router.get("/library", response_class=HTMLResponse)
async def forms_library(lang: str = Query("en"), category: str = Query("")):
    """Court forms library page."""
    strings = get_all_strings(lang)
    
    # Filter by category if specified
    forms = COURT_FORMS
    if category:
        forms = [f for f in forms if f.get("category") == category]
    
    # Category filter buttons
    categories_html = f"""
        <a href="/eviction/forms/library?lang={lang}" class="category-btn {'active' if not category else ''}">All</a>
        <a href="/eviction/forms/library?lang={lang}&category=answer" class="category-btn {'active' if category == 'answer' else ''}">Answer</a>
        <a href="/eviction/forms/library?lang={lang}&category=motion" class="category-btn {'active' if category == 'motion' else ''}">Motions</a>
        <a href="/eviction/forms/library?lang={lang}&category=counterclaim" class="category-btn {'active' if category == 'counterclaim' else ''}">Counterclaim</a>
        <a href="/eviction/forms/library?lang={lang}&category=fee_waiver" class="category-btn {'active' if category == 'fee_waiver' else ''}">Fee Waiver</a>
    """
    
    # Build forms list
    forms_html = ""
    for form in forms:
        # Get localized name
        name_key = f"name_{lang}" if lang != "en" else "name"
        name = form.get(name_key, form["name"])
        
        forms_html += f"""
            <div class="form-item">
                <div class="form-info">
                    <div class="form-name">{name}</div>
                    <div class="form-desc">{form['description']}</div>
                    <div class="form-id">Form: {form['id']}</div>
                </div>
                <a href="{form['url']}" target="_blank" class="btn">{strings.get('download', 'Download')}</a>
            </div>
        """
    
    # Build resources list
    resources_html = ""
    for resource in RESOURCES:
        resources_html += f"""
            <div class="resource-item">
                <div class="resource-name">{resource['name']}</div>
                <div class="resource-phone">📞 {resource['phone']}</div>
                <div class="resource-desc">{resource['description']}</div>
                <a href="{resource['url']}" target="_blank" style="color: #3b82f6; font-size: 0.875rem;">{resource['url']}</a>
            </div>
        """
    
    content = f"""
        <div class="categories">
            {categories_html}
        </div>
        
        <div class="card">
            <h2>Official Minnesota Court Forms</h2>
            <div class="form-list">
                {forms_html if forms_html else '<p style="color: #64748b;">No forms in this category</p>'}
            </div>
        </div>
        
        <div class="card">
            <h2>{strings.get('resources_title', 'Legal Resources')}</h2>
            {resources_html}
        </div>
        
        <div class="nav-buttons">
            <a href="/eviction?lang={lang}" class="btn btn-secondary">{strings.get('back', 'Back')}</a>
        </div>
    """
    
    return get_html_page(strings.get('forms_library', 'Forms Library'), content, lang)


# ============================================================================
# API Endpoints
# ============================================================================

@router.get("/api/list")
async def list_forms(category: str = Query(""), lang: str = Query("en")):
    """Get list of all court forms."""
    forms = COURT_FORMS
    if category:
        forms = [f for f in forms if f.get("category") == category]
    
    # Add localized names
    result = []
    for form in forms:
        name_key = f"name_{lang}" if lang != "en" else "name"
        result.append({
            **form,
            "display_name": form.get(name_key, form["name"])
        })
    
    return JSONResponse(content={"forms": result, "count": len(result)})


@router.get("/api/form/{form_id}")
async def get_form(form_id: str, lang: str = Query("en")):
    """Get details of a specific form."""
    form = next((f for f in COURT_FORMS if f["id"] == form_id), None)
    if not form:
        raise HTTPException(status_code=404, detail="Form not found")
    
    name_key = f"name_{lang}" if lang != "en" else "name"
    return JSONResponse(content={
        **form,
        "display_name": form.get(name_key, form["name"])
    })


@router.get("/api/resources")
async def get_resources():
    """Get list of legal resources."""
    return JSONResponse(content={"resources": RESOURCES})


# ============================================================================
# Auto-Fill Form Data Endpoints
# ============================================================================

@router.get("/api/autofill/answer")
async def get_answer_autofill(user: UserContext = Depends(get_current_user)):
    """Get auto-filled data for Answer to Eviction form."""
    user_id = getattr(user, 'user_id', None) or 'open-mode-user'
    form_service = get_form_data_service(user_id)
    await form_service.load()
    
    data = form_service.get_answer_form_data()
    summary = form_service.get_case_summary()
    
    return JSONResponse(content={
        "form_data": data,
        "case_summary": summary,
        "ready_to_generate": bool(data.get("defendant_name") or data.get("case_number")),
        "missing_fields": _get_missing_fields(data, ["defendant_name", "plaintiff_name", "property_address"]),
    })


@router.get("/api/autofill/counterclaim")
async def get_counterclaim_autofill(user: UserContext = Depends(get_current_user)):
    """Get auto-filled data for Counterclaim form."""
    user_id = getattr(user, 'user_id', None) or 'open-mode-user'
    form_service = get_form_data_service(user_id)
    await form_service.load()
    
    data = form_service.get_counterclaim_form_data()
    summary = form_service.get_case_summary()
    
    return JSONResponse(content={
        "form_data": data,
        "case_summary": summary,
        "ready_to_generate": bool(data.get("counter_plaintiff")),
        "missing_fields": _get_missing_fields(data, ["counter_plaintiff", "counter_defendant", "claims"]),
    })


@router.get("/api/autofill/motion/{motion_type}")
async def get_motion_autofill(
    motion_type: str,
    user: UserContext = Depends(get_current_user)
):
    """Get auto-filled data for Motion forms."""
    if motion_type not in ["dismiss", "continuance", "stay", "fee_waiver"]:
        raise HTTPException(status_code=400, detail="Invalid motion type")
    
    user_id = getattr(user, 'user_id', None) or 'open-mode-user'
    form_service = get_form_data_service(user_id)
    await form_service.load()
    
    data = form_service.get_motion_form_data(motion_type)
    summary = form_service.get_case_summary()
    
    return JSONResponse(content={
        "form_data": data,
        "case_summary": summary,
        "motion_type": motion_type,
        "ready_to_generate": bool(data.get("defendant_name")),
        "missing_fields": _get_missing_fields(data, ["defendant_name", "plaintiff_name"]),
    })


def _get_missing_fields(data: Dict, required: List[str]) -> List[str]:
    """Check which required fields are missing."""
    missing = []
    for field in required:
        value = data.get(field)
        if not value or value == "Not entered" or (isinstance(value, list) and len(value) == 0):
            missing.append(field)
    return missing


# ============================================================================
# PDF Generation Endpoints
# ============================================================================

@router.post("/api/generate/answer")
async def generate_answer(
    request: AnswerFormRequest,
    user: UserContext = Depends(get_current_user)
):
    """Generate Answer to Eviction PDF with auto-fill from case data."""
    user_id = getattr(user, 'user_id', None) or 'open-mode-user'
    form_service = get_form_data_service(user_id)
    
    # Auto-fill from case data if enabled
    if request.auto_fill:
        await form_service.load()
        case_data = form_service.get_answer_form_data()
        
        tenant_name = request.tenant_name or case_data.get("defendant_name") or "Tenant"
        landlord_name = request.landlord_name or case_data.get("plaintiff_name") or "Landlord"
        case_number = request.case_number or case_data.get("case_number") or ""
        property_address = request.property_address or case_data.get("property_address") or ""
        served_date = request.served_date or ""
        defenses = request.defenses or case_data.get("defenses") or []
    else:
        tenant_name = request.tenant_name or "Tenant"
        landlord_name = request.landlord_name or "Landlord"
        case_number = request.case_number or ""
        property_address = request.property_address or ""
        served_date = request.served_date or ""
        defenses = request.defenses or []
    
    # Map defense codes to descriptions
    defense_descriptions = _map_defenses_to_descriptions(defenses)
    
    # Generate PDF
    pdf_bytes = generate_answer_pdf(
        tenant_name=tenant_name,
        landlord_name=landlord_name,
        case_number=case_number,
        address=property_address,
        served_date=served_date,
        defenses=defense_descriptions,
        defense_details=request.defense_details or "",
    )
    
    # Publish event
    event_bus.publish_sync(
        EventType.FORM_GENERATED,
        {
            "form_type": "answer",
            "case_number": case_number,
            "defenses_count": len(defenses),
        },
        source="forms",
        user_id=user_id,
    )
    
    # Return PDF or HTML based on availability
    if WEASYPRINT_AVAILABLE:
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename=Answer_to_Eviction_{datetime.now().strftime('%Y%m%d')}.pdf"}
        )
    else:
        return Response(
            content=pdf_bytes,
            media_type="text/html",
            headers={"Content-Disposition": f"attachment; filename=Answer_to_Eviction_{datetime.now().strftime('%Y%m%d')}.html"}
        )


@router.post("/api/generate/counterclaim")
async def generate_counterclaim(
    request: CounterclaimRequest,
    user: UserContext = Depends(get_current_user)
):
    """Generate Counterclaim PDF with auto-fill from case data."""
    user_id = getattr(user, 'user_id', None) or 'open-mode-user'
    form_service = get_form_data_service(user_id)
    
    if request.auto_fill:
        await form_service.load()
        case_data = form_service.get_counterclaim_form_data()
        
        tenant_name = request.tenant_name or case_data.get("counter_plaintiff") or "Tenant"
        landlord_name = request.landlord_name or case_data.get("counter_defendant") or "Landlord"
        case_number = request.case_number or case_data.get("case_number") or ""
        property_address = request.property_address or case_data.get("property_address") or ""
        claims = request.claims or case_data.get("claims") or []
    else:
        tenant_name = request.tenant_name or "Tenant"
        landlord_name = request.landlord_name or "Landlord"
        case_number = request.case_number or ""
        property_address = request.property_address or ""
        claims = request.claims or []
    
    # Map claim codes to descriptions
    claim_descriptions = _map_claims_to_descriptions(claims)
    
    pdf_bytes = generate_counterclaim_pdf(
        tenant_name=tenant_name,
        landlord_name=landlord_name,
        case_number=case_number,
        address=property_address,
        claims=claim_descriptions,
        claim_details=request.claim_details or "",
        damages_requested=request.damages_requested or "",
    )
    
    event_bus.publish_sync(
        EventType.FORM_GENERATED,
        {"form_type": "counterclaim", "claims_count": len(claims)},
        source="forms",
        user_id=user_id,
    )
    
    if WEASYPRINT_AVAILABLE:
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename=Counterclaim_{datetime.now().strftime('%Y%m%d')}.pdf"}
        )
    else:
        return Response(
            content=pdf_bytes,
            media_type="text/html",
            headers={"Content-Disposition": f"attachment; filename=Counterclaim_{datetime.now().strftime('%Y%m%d')}.html"}
        )


@router.post("/api/generate/motion")
async def generate_motion(
    request: MotionRequest,
    user: UserContext = Depends(get_current_user)
):
    """Generate Motion PDF with auto-fill from case data."""
    if request.motion_type not in ["dismiss", "continuance", "stay", "fee_waiver"]:
        raise HTTPException(status_code=400, detail="Invalid motion type. Must be: dismiss, continuance, stay, or fee_waiver")
    
    user_id = getattr(user, 'user_id', None) or 'open-mode-user'
    form_service = get_form_data_service(user_id)
    
    if request.auto_fill:
        await form_service.load()
        case_data = form_service.get_motion_form_data(request.motion_type)
        
        tenant_name = request.tenant_name or case_data.get("defendant_name") or "Tenant"
        landlord_name = request.landlord_name or case_data.get("plaintiff_name") or "Landlord"
        case_number = request.case_number or case_data.get("case_number") or ""
        hearing_date = request.hearing_date or case_data.get("hearing_date") or ""
        
        # Auto-generate grounds based on motion type and selected defenses
        if not request.grounds:
            grounds = _generate_motion_grounds(request.motion_type, case_data.get("grounds", []))
        else:
            grounds = request.grounds
    else:
        tenant_name = request.tenant_name or "Tenant"
        landlord_name = request.landlord_name or "Landlord"
        case_number = request.case_number or ""
        hearing_date = request.hearing_date or ""
        grounds = request.grounds or ""
    
    pdf_bytes = generate_motion_pdf(
        motion_type=request.motion_type,
        tenant_name=tenant_name,
        landlord_name=landlord_name,
        case_number=case_number,
        grounds=grounds,
        hearing_date=hearing_date,
    )
    
    event_bus.publish_sync(
        EventType.FORM_GENERATED,
        {"form_type": f"motion_{request.motion_type}"},
        source="forms",
        user_id=user_id,
    )
    
    motion_names = {
        "dismiss": "Motion_to_Dismiss",
        "continuance": "Motion_for_Continuance",
        "stay": "Motion_to_Stay_Eviction",
        "fee_waiver": "Fee_Waiver_Application",
    }
    filename = motion_names.get(request.motion_type, "Motion")
    
    if WEASYPRINT_AVAILABLE:
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={filename}_{datetime.now().strftime('%Y%m%d')}.pdf"}
        )
    else:
        return Response(
            content=pdf_bytes,
            media_type="text/html",
            headers={"Content-Disposition": f"attachment; filename={filename}_{datetime.now().strftime('%Y%m%d')}.html"}
        )


@router.post("/api/generate/hearing-prep")
async def generate_hearing_prep(
    request: HearingPrepRequest,
    user: UserContext = Depends(get_current_user)
):
    """Generate Hearing Preparation Checklist PDF."""
    user_id = getattr(user, 'user_id', None) or 'open-mode-user'
    form_service = get_form_data_service(user_id)
    
    if request.auto_fill:
        await form_service.load()
        summary = form_service.get_case_summary()
        
        tenant_name = request.tenant_name or summary.get("tenant_name") or "Tenant"
        hearing_date = request.hearing_date or summary.get("hearing_date") or ""
        hearing_time = request.hearing_time or summary.get("hearing_time") or ""
    else:
        tenant_name = request.tenant_name or "Tenant"
        hearing_date = request.hearing_date or ""
        hearing_time = request.hearing_time or ""
    
    pdf_bytes = generate_hearing_prep_pdf(
        tenant_name=tenant_name,
        hearing_date=hearing_date,
        hearing_time=hearing_time,
        is_zoom=request.is_zoom,
        checklist_items=request.additional_items,
    )
    
    event_bus.publish_sync(
        EventType.FORM_GENERATED,
        {"form_type": "hearing_prep", "is_zoom": request.is_zoom},
        source="forms",
        user_id=user_id,
    )
    
    if WEASYPRINT_AVAILABLE:
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename=Hearing_Prep_{datetime.now().strftime('%Y%m%d')}.pdf"}
        )
    else:
        return Response(
            content=pdf_bytes,
            media_type="text/html",
            headers={"Content-Disposition": f"attachment; filename=Hearing_Prep_{datetime.now().strftime('%Y%m%d')}.html"}
        )


# ============================================================================
# Helper Functions
# ============================================================================

DEFENSE_DESCRIPTIONS = {
    "IMPROPER_NOTICE": "The notice of eviction was defective or improperly served.",
    "INSUFFICIENT_NOTICE": "The notice period provided was insufficient under Minnesota law.",
    "RETALIATION": "The eviction is in retaliation for exercising tenant rights (e.g., requesting repairs, complaining to authorities).",
    "DISCRIMINATION": "The eviction is based on discriminatory reasons (protected class status).",
    "HABITABILITY": "The landlord failed to maintain habitable conditions as required by law.",
    "BREACH_WARRANTY": "The landlord breached the warranty of habitability.",
    "RENT_PAID": "The rent claimed was already paid or is not owed.",
    "PAYMENT_REFUSED": "The landlord refused to accept timely rent payment.",
    "LEASE_VIOLATION": "No actual lease violation occurred as alleged.",
    "WAIVER": "The landlord waived the right to evict by accepting rent or other conduct.",
    "ESTOPPEL": "The landlord is estopped from evicting based on prior representations.",
    "CURE_COMPLETED": "Any alleged violation has been cured within the allowed time period.",
}

COUNTERCLAIM_DESCRIPTIONS = {
    "SECURITY_DEPOSIT": "Wrongful withholding of security deposit.",
    "HABITABILITY_DAMAGES": "Damages due to uninhabitable conditions.",
    "RETALIATION_DAMAGES": "Damages due to retaliatory conduct.",
    "LOCKOUT": "Illegal lockout or utility shutoff damages.",
    "HARASSMENT": "Landlord harassment or interference with quiet enjoyment.",
    "REPAIR_DEDUCTION": "Improper rejection of repair and deduct remedy.",
    "TRESPASS": "Unauthorized entry into the rental unit.",
    "DISCRIMINATION_DAMAGES": "Damages for discriminatory treatment.",
}


def _map_defenses_to_descriptions(defense_codes: List[str]) -> List[str]:
    """Map defense codes to full descriptions for the PDF."""
    descriptions = []
    for code in defense_codes:
        if code in DEFENSE_DESCRIPTIONS:
            descriptions.append(DEFENSE_DESCRIPTIONS[code])
        else:
            # Use the code as-is if not found
            descriptions.append(code.replace("_", " ").title())
    return descriptions


def _map_claims_to_descriptions(claim_codes: List[str]) -> List[str]:
    """Map counterclaim codes to full descriptions for the PDF."""
    descriptions = []
    for code in claim_codes:
        if code in COUNTERCLAIM_DESCRIPTIONS:
            descriptions.append(COUNTERCLAIM_DESCRIPTIONS[code])
        else:
            descriptions.append(code.replace("_", " ").title())
    return descriptions


def _generate_motion_grounds(motion_type: str, defenses: List[str]) -> str:
    """Generate motion grounds based on type and selected defenses."""
    if motion_type == "dismiss":
        grounds_parts = []
        if "IMPROPER_NOTICE" in defenses or "INSUFFICIENT_NOTICE" in defenses:
            grounds_parts.append("The notice provided was defective and failed to comply with Minnesota statutory requirements")
        if "HABITABILITY" in defenses or "BREACH_WARRANTY" in defenses:
            grounds_parts.append("The landlord materially breached the warranty of habitability")
        if "RETALIATION" in defenses:
            grounds_parts.append("The eviction action is retaliatory and prohibited under Minn. Stat. § 504B.285")
        
        if grounds_parts:
            return ". ".join(grounds_parts) + ". The complaint fails to state a claim upon which relief can be granted."
        return "The complaint fails to state a claim upon which relief can be granted."
    
    elif motion_type == "continuance":
        return "Defendant needs additional time to prepare their defense, gather evidence, and/or secure legal representation."
    
    elif motion_type == "stay":
        return "Defendant requests a stay of eviction to allow time to cure any alleged default, find alternative housing, or pursue appeal of an adverse judgment."
    
    elif motion_type == "fee_waiver":
        return "Defendant is unable to pay court fees due to financial hardship and requests waiver of filing fees to access the courts."
    
    return ""


# ============================================================================
# Quick Generate Endpoint (Simplified)
# ============================================================================

@router.post("/api/quick-generate/{form_type}")
async def quick_generate(
    form_type: str,
    user: UserContext = Depends(get_current_user)
):
    """
    Quick generate a form using all auto-filled data.
    No input required - uses all extracted case data.
    """
    if form_type == "answer":
        return await generate_answer(AnswerFormRequest(auto_fill=True), user)
    elif form_type == "counterclaim":
        return await generate_counterclaim(CounterclaimRequest(auto_fill=True), user)
    elif form_type in ["dismiss", "continuance", "stay", "fee_waiver"]:
        return await generate_motion(MotionRequest(motion_type=form_type, auto_fill=True), user)
    elif form_type == "hearing-prep":
        return await generate_hearing_prep(HearingPrepRequest(auto_fill=True), user)
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown form type: {form_type}. Valid types: answer, counterclaim, dismiss, continuance, stay, fee_waiver, hearing-prep"
        )
