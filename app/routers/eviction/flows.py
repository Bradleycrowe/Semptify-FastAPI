"""
Dakota County Eviction Defense - Flows Router
Handles Answer, Counterclaim, Motion, and Hearing Prep flows.
"""

import io
from datetime import datetime, timedelta
from typing import Optional, List

from fastapi import APIRouter, Request, Query, Form, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from app.services.eviction.i18n import get_string, get_all_strings, is_rtl
from app.services.eviction.pdf import (
    generate_answer_pdf,
    generate_counterclaim_pdf,
    generate_motion_pdf,
    generate_hearing_prep_pdf
)

router = APIRouter()


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


# ============================================================================
# Helper Functions
# ============================================================================

def get_html_page(title: str, content: str, lang: str = "en") -> str:
    """Generate full HTML page with styling."""
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
        .container {{ max-width: 800px; margin: 0 auto; padding: 1rem; }}
        header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 1rem 0;
            border-bottom: 1px solid rgba(255,255,255,0.1);
            margin-bottom: 2rem;
        }}
        h1 {{ font-size: 1.5rem; }}
        .warning {{
            background: rgba(245, 158, 11, 0.2);
            border: 1px solid #f59e0b;
            border-radius: 0.5rem;
            padding: 1rem;
            margin-bottom: 1.5rem;
        }}
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
            padding: 0.75rem 1.5rem;
            background: #3b82f6;
            color: white;
            text-decoration: none;
            border-radius: 0.5rem;
            border: none;
            cursor: pointer;
            font-size: 1rem;
            transition: all 0.2s;
            margin: 0.25rem;
        }}
        .btn:hover {{ background: #2563eb; }}
        .btn-secondary {{ background: #475569; }}
        .btn-secondary:hover {{ background: #64748b; }}
        .btn-success {{ background: #10b981; }}
        .btn-success:hover {{ background: #059669; }}
        .grid {{ display: grid; gap: 1rem; }}
        .grid-2 {{ grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); }}
        .form-group {{ margin-bottom: 1rem; }}
        .form-group label {{ display: block; margin-bottom: 0.5rem; color: #94a3b8; }}
        .form-group input, .form-group textarea, .form-group select {{
            width: 100%;
            padding: 0.75rem;
            border: 1px solid rgba(255,255,255,0.2);
            border-radius: 0.5rem;
            background: rgba(255,255,255,0.05);
            color: white;
            font-size: 1rem;
        }}
        .form-group input:focus, .form-group textarea:focus {{
            outline: none;
            border-color: #3b82f6;
        }}
        .checkbox-group {{ display: flex; flex-wrap: wrap; gap: 0.5rem; }}
        .checkbox-item {{
            display: flex;
            align-items: center;
            gap: 0.5rem;
            padding: 0.5rem 1rem;
            background: rgba(255,255,255,0.05);
            border-radius: 0.5rem;
            cursor: pointer;
        }}
        .checkbox-item:hover {{ background: rgba(255,255,255,0.1); }}
        .checkbox-item input {{ width: auto; }}
        .steps {{ display: flex; gap: 0.5rem; margin-bottom: 1.5rem; }}
        .step {{
            padding: 0.5rem 1rem;
            background: rgba(255,255,255,0.1);
            border-radius: 2rem;
            font-size: 0.875rem;
        }}
        .step.active {{ background: #3b82f6; }}
        .step.complete {{ background: #10b981; }}
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
        .menu-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 1rem; }}
        .menu-card {{
            display: block;
            padding: 1.5rem;
            background: rgba(255,255,255,0.05);
            border: 1px solid rgba(255,255,255,0.1);
            border-radius: 1rem;
            text-decoration: none;
            color: white;
            transition: all 0.2s;
        }}
        .menu-card:hover {{ background: rgba(255,255,255,0.1); transform: translateY(-2px); }}
        .menu-card h3 {{ margin-bottom: 0.5rem; }}
        .menu-card p {{ color: #94a3b8; font-size: 0.875rem; }}
        .icon {{ font-size: 2rem; margin-bottom: 0.5rem; }}
        .nav-buttons {{ display: flex; justify-content: space-between; margin-top: 1.5rem; }}
        footer {{ margin-top: 2rem; padding-top: 1rem; border-top: 1px solid rgba(255,255,255,0.1); font-size: 0.875rem; color: #64748b; }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🏠 {strings.get('app_title', 'Eviction Defense')}</h1>
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
# Main Dashboard
# ============================================================================

@router.get("/", response_class=HTMLResponse)
async def eviction_home(lang: str = Query("en")):
    """Dakota County Eviction Defense home page."""
    strings = get_all_strings(lang)
    
    content = f"""
        <div class="warning">
            <strong>{strings.get('deadline_warning', '⚠️ You typically have only 7 days to respond!')}</strong>
        </div>
        
        <div class="menu-grid">
            <a href="/eviction/answer?lang={lang}" class="menu-card">
                <div class="icon">📝</div>
                <h3>{strings.get('answer_summons', 'Answer the Summons')}</h3>
                <p>Respond to your eviction complaint within the deadline</p>
            </a>
            
            <a href="/eviction/counterclaim?lang={lang}" class="menu-card">
                <div class="icon">⚖️</div>
                <h3>{strings.get('file_counterclaim', 'File a Counterclaim')}</h3>
                <p>Assert claims against your landlord</p>
            </a>
            
            <a href="/eviction/motions?lang={lang}" class="menu-card">
                <div class="icon">📋</div>
                <h3>{strings.get('motions', 'Motions & Requests')}</h3>
                <p>Dismiss, continuance, stay, fee waiver</p>
            </a>
            
            <a href="/eviction/hearing?lang={lang}" class="menu-card">
                <div class="icon">🎯</div>
                <h3>{strings.get('hearing_prep', 'Hearing Preparation')}</h3>
                <p>Get ready for your court date</p>
            </a>
            
            <a href="/eviction/forms/library?lang={lang}" class="menu-card">
                <div class="icon">📁</div>
                <h3>{strings.get('forms_library', 'Court Forms Library')}</h3>
                <p>Official Minnesota court forms</p>
            </a>
            
            <a href="/eviction/zoom?lang={lang}" class="menu-card">
                <div class="icon">💻</div>
                <h3>{strings.get('zoom_court', 'Zoom Court Helper')}</h3>
                <p>Tips for virtual hearings</p>
            </a>
        </div>
        
        <div class="card" style="margin-top: 2rem;">
            <h2>{strings.get('resources_title', 'Legal Resources')}</h2>
            <div class="grid grid-2">
                <div>
                    <strong>HOME Line</strong>: 612-728-5767<br>
                    <small>{strings.get('homeline_desc', 'Free tenant hotline')}</small>
                </div>
                <div>
                    <strong>Southern MN Regional Legal Services</strong><br>
                    <small>{strings.get('legal_aid_desc', 'Free legal services')}</small>
                </div>
            </div>
        </div>
    """
    
    return get_html_page(strings.get('app_title', 'Eviction Defense'), content, lang)


# ============================================================================
# Answer Flow
# ============================================================================

@router.get("/answer", response_class=HTMLResponse)
async def answer_step1(lang: str = Query("en")):
    """Answer flow - Step 1: Basic information."""
    strings = get_all_strings(lang)
    
    content = f"""
        <div class="steps">
            <span class="step active">1</span>
            <span class="step">2</span>
            <span class="step">3</span>
        </div>
        
        <div class="card">
            <h2>{strings.get('step', 'Step')} 1: {strings.get('your_information', 'Your Information')}</h2>
            
            <form action="/eviction/answer/step2" method="GET">
                <input type="hidden" name="lang" value="{lang}">
                
                <div class="form-group">
                    <label>{strings.get('tenant_name', 'Your Full Name')}</label>
                    <input type="text" name="tenant_name" required>
                </div>
                
                <div class="form-group">
                    <label>{strings.get('landlord_name', "Landlord's Name")}</label>
                    <input type="text" name="landlord_name" required>
                </div>
                
                <div class="form-group">
                    <label>{strings.get('case_number', 'Case Number (if known)')}</label>
                    <input type="text" name="case_number">
                </div>
                
                <div class="form-group">
                    <label>{strings.get('property_address', 'Property Address')}</label>
                    <input type="text" name="address" required>
                </div>
                
                <div class="form-group">
                    <label>{strings.get('served_date', 'Date You Were Served')}</label>
                    <input type="date" name="served_date">
                </div>
                
                <div class="nav-buttons">
                    <a href="/eviction?lang={lang}" class="btn btn-secondary">{strings.get('back', 'Back')}</a>
                    <button type="submit" class="btn">{strings.get('next', 'Next')}</button>
                </div>
            </form>
        </div>
    """
    
    return get_html_page(strings.get('answer_summons', 'Answer'), content, lang)


@router.get("/answer/step2", response_class=HTMLResponse)
async def answer_step2(
    lang: str = Query("en"),
    tenant_name: str = Query(""),
    landlord_name: str = Query(""),
    case_number: str = Query(""),
    address: str = Query(""),
    served_date: str = Query("")
):
    """Answer flow - Step 2: Select defenses."""
    strings = get_all_strings(lang)
    
    defenses = [
        ("nonpayment", strings.get('defense_nonpayment', 'I paid the rent')),
        ("habitability", strings.get('defense_habitability', 'Property has problems')),
        ("retaliation", strings.get('defense_retaliation', 'Eviction is retaliation')),
        ("discrimination", strings.get('defense_discrimination', 'Eviction is discriminatory')),
        ("improper_notice", strings.get('defense_improper_notice', 'Improper notice')),
        ("lease_violation", strings.get('defense_lease_violation', 'Did not violate lease')),
    ]
    
    defense_checkboxes = ""
    for value, label in defenses:
        defense_checkboxes += f"""
            <label class="checkbox-item">
                <input type="checkbox" name="defenses" value="{value}">
                {label}
            </label>
        """
    
    content = f"""
        <div class="steps">
            <span class="step complete">1</span>
            <span class="step active">2</span>
            <span class="step">3</span>
        </div>
        
        <div class="card">
            <h2>{strings.get('step', 'Step')} 2: {strings.get('select_defenses', 'Select Your Defenses')}</h2>
            
            <form action="/eviction/answer/step3" method="GET">
                <input type="hidden" name="lang" value="{lang}">
                <input type="hidden" name="tenant_name" value="{tenant_name}">
                <input type="hidden" name="landlord_name" value="{landlord_name}">
                <input type="hidden" name="case_number" value="{case_number}">
                <input type="hidden" name="address" value="{address}">
                <input type="hidden" name="served_date" value="{served_date}">
                
                <div class="form-group">
                    <label>{strings.get('select_defenses', 'Select all that apply')}:</label>
                    <div class="checkbox-group">
                        {defense_checkboxes}
                    </div>
                </div>
                
                <div class="form-group">
                    <label>Additional details about your defenses:</label>
                    <textarea name="defense_details" rows="4" placeholder="Explain your situation..."></textarea>
                </div>
                
                <div class="nav-buttons">
                    <a href="/eviction/answer?lang={lang}" class="btn btn-secondary">{strings.get('back', 'Back')}</a>
                    <button type="submit" class="btn">{strings.get('next', 'Next')}</button>
                </div>
            </form>
        </div>
    """
    
    return get_html_page(strings.get('answer_summons', 'Answer'), content, lang)


@router.get("/answer/step3", response_class=HTMLResponse)
async def answer_step3(
    request: Request,
    lang: str = Query("en"),
    tenant_name: str = Query(""),
    landlord_name: str = Query(""),
    case_number: str = Query(""),
    address: str = Query(""),
    served_date: str = Query(""),
    defense_details: str = Query("")
):
    """Answer flow - Step 3: Review and generate."""
    strings = get_all_strings(lang)
    
    # Get defenses from query params (can be multiple)
    defenses = request.query_params.getlist("defenses")
    defenses_str = ",".join(defenses)
    
    content = f"""
        <div class="steps">
            <span class="step complete">1</span>
            <span class="step complete">2</span>
            <span class="step active">3</span>
        </div>
        
        <div class="card">
            <h2>{strings.get('step', 'Step')} 3: Review & Generate</h2>
            
            <div style="margin-bottom: 1rem;">
                <strong>Tenant:</strong> {tenant_name}<br>
                <strong>Landlord:</strong> {landlord_name}<br>
                <strong>Case:</strong> {case_number or 'Not provided'}<br>
                <strong>Address:</strong> {address}<br>
                <strong>Served:</strong> {served_date or 'Not provided'}<br>
                <strong>Defenses:</strong> {', '.join(defenses) if defenses else 'None selected'}
            </div>
            
            <form action="/eviction/answer/generate" method="POST">
                <input type="hidden" name="lang" value="{lang}">
                <input type="hidden" name="tenant_name" value="{tenant_name}">
                <input type="hidden" name="landlord_name" value="{landlord_name}">
                <input type="hidden" name="case_number" value="{case_number}">
                <input type="hidden" name="address" value="{address}">
                <input type="hidden" name="served_date" value="{served_date}">
                <input type="hidden" name="defenses" value="{defenses_str}">
                <input type="hidden" name="defense_details" value="{defense_details}">
                
                <div class="nav-buttons">
                    <a href="/eviction/answer/step2?lang={lang}&tenant_name={tenant_name}&landlord_name={landlord_name}" class="btn btn-secondary">{strings.get('back', 'Back')}</a>
                    <button type="submit" class="btn btn-success">{strings.get('download', 'Download')} PDF</button>
                </div>
            </form>
        </div>
    """
    
    return get_html_page(strings.get('answer_summons', 'Answer'), content, lang)


@router.post("/answer/generate")
async def generate_answer(
    tenant_name: str = Form(...),
    landlord_name: str = Form(...),
    case_number: str = Form(""),
    address: str = Form(""),
    served_date: str = Form(""),
    defenses: str = Form(""),
    defense_details: str = Form("")
):
    """Generate Answer PDF."""
    defense_list = [d for d in defenses.split(",") if d]
    
    pdf_bytes = generate_answer_pdf(
        tenant_name=tenant_name,
        landlord_name=landlord_name,
        case_number=case_number,
        address=address,
        served_date=served_date,
        defenses=defense_list,
        defense_details=defense_details
    )
    
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=answer_{datetime.now().strftime('%Y%m%d')}.pdf"}
    )


# ============================================================================
# Counterclaim Flow
# ============================================================================

@router.get("/counterclaim", response_class=HTMLResponse)
async def counterclaim_start(lang: str = Query("en")):
    """Counterclaim flow - Start."""
    strings = get_all_strings(lang)
    
    claims = [
        ("security_deposit", strings.get('claim_security_deposit', 'Security deposit not returned')),
        ("repairs", strings.get('claim_repairs', 'Failed to make repairs')),
        ("harassment", strings.get('claim_harassment', 'Harassment or illegal entry')),
        ("utilities", strings.get('claim_utilities', 'Illegal utility shutoff')),
    ]
    
    claims_checkboxes = ""
    for value, label in claims:
        claims_checkboxes += f"""
            <label class="checkbox-item">
                <input type="checkbox" name="claims" value="{value}">
                {label}
            </label>
        """
    
    content = f"""
        <div class="card">
            <h2>{strings.get('counterclaim_title', 'File a Counterclaim')}</h2>
            
            <form action="/eviction/counterclaim/generate" method="POST">
                <input type="hidden" name="lang" value="{lang}">
                
                <div class="form-group">
                    <label>{strings.get('tenant_name', 'Your Full Name')}</label>
                    <input type="text" name="tenant_name" required>
                </div>
                
                <div class="form-group">
                    <label>{strings.get('landlord_name', "Landlord's Name")}</label>
                    <input type="text" name="landlord_name" required>
                </div>
                
                <div class="form-group">
                    <label>{strings.get('case_number', 'Case Number')}</label>
                    <input type="text" name="case_number">
                </div>
                
                <div class="form-group">
                    <label>Select your claims:</label>
                    <div class="checkbox-group">
                        {claims_checkboxes}
                    </div>
                </div>
                
                <div class="form-group">
                    <label>Describe your claims in detail:</label>
                    <textarea name="claim_details" rows="4"></textarea>
                </div>
                
                <div class="form-group">
                    <label>Damages requested ($ amount):</label>
                    <input type="text" name="damages_requested">
                </div>
                
                <div class="nav-buttons">
                    <a href="/eviction?lang={lang}" class="btn btn-secondary">{strings.get('back', 'Back')}</a>
                    <button type="submit" class="btn btn-success">{strings.get('download', 'Download')} PDF</button>
                </div>
            </form>
        </div>
    """
    
    return get_html_page(strings.get('counterclaim_title', 'Counterclaim'), content, lang)


@router.post("/counterclaim/generate")
async def generate_counterclaim_doc(
    tenant_name: str = Form(...),
    landlord_name: str = Form(...),
    case_number: str = Form(""),
    claims: List[str] = Form([]),
    claim_details: str = Form(""),
    damages_requested: str = Form("")
):
    """Generate Counterclaim PDF."""
    pdf_bytes = generate_counterclaim_pdf(
        tenant_name=tenant_name,
        landlord_name=landlord_name,
        case_number=case_number,
        claims=claims if isinstance(claims, list) else [claims],
        claim_details=claim_details,
        damages_requested=damages_requested
    )
    
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=counterclaim_{datetime.now().strftime('%Y%m%d')}.pdf"}
    )


# ============================================================================
# Motions Menu
# ============================================================================

@router.get("/motions", response_class=HTMLResponse)
async def motions_menu(lang: str = Query("en")):
    """Motions selection menu."""
    strings = get_all_strings(lang)
    
    content = f"""
        <div class="card">
            <h2>{strings.get('motions', 'Motions & Requests')}</h2>
            
            <div class="menu-grid">
                <a href="/eviction/motions/dismiss?lang={lang}" class="menu-card">
                    <div class="icon">❌</div>
                    <h3>{strings.get('motion_dismiss', 'Motion to Dismiss')}</h3>
                    <p>Ask the court to dismiss the case</p>
                </a>
                
                <a href="/eviction/motions/continuance?lang={lang}" class="menu-card">
                    <div class="icon">📅</div>
                    <h3>{strings.get('motion_continuance', 'Motion for Continuance')}</h3>
                    <p>Request more time before the hearing</p>
                </a>
                
                <a href="/eviction/motions/stay?lang={lang}" class="menu-card">
                    <div class="icon">🛑</div>
                    <h3>{strings.get('motion_stay', 'Motion to Stay')}</h3>
                    <p>Pause the eviction process</p>
                </a>
                
                <a href="/eviction/motions/ifp?lang={lang}" class="menu-card">
                    <div class="icon">💰</div>
                    <h3>{strings.get('motion_fee_waiver', 'Fee Waiver (IFP)')}</h3>
                    <p>Request waiver of court fees</p>
                </a>
            </div>
            
            <div class="nav-buttons" style="justify-content: flex-start;">
                <a href="/eviction?lang={lang}" class="btn btn-secondary">{strings.get('back', 'Back')}</a>
            </div>
        </div>
    """
    
    return get_html_page(strings.get('motions', 'Motions'), content, lang)


@router.get("/motions/{motion_type}", response_class=HTMLResponse)
async def motion_form(motion_type: str, lang: str = Query("en")):
    """Individual motion form."""
    strings = get_all_strings(lang)
    
    titles = {
        "dismiss": strings.get('motion_dismiss', 'Motion to Dismiss'),
        "continuance": strings.get('motion_continuance', 'Motion for Continuance'),
        "stay": strings.get('motion_stay', 'Motion to Stay'),
        "ifp": strings.get('motion_fee_waiver', 'Fee Waiver')
    }
    
    title = titles.get(motion_type, "Motion")
    actual_type = "fee_waiver" if motion_type == "ifp" else motion_type
    
    content = f"""
        <div class="card">
            <h2>{title}</h2>
            
            <form action="/eviction/motions/generate" method="POST">
                <input type="hidden" name="lang" value="{lang}">
                <input type="hidden" name="motion_type" value="{actual_type}">
                
                <div class="form-group">
                    <label>{strings.get('tenant_name', 'Your Full Name')}</label>
                    <input type="text" name="tenant_name" required>
                </div>
                
                <div class="form-group">
                    <label>{strings.get('landlord_name', "Landlord's Name")}</label>
                    <input type="text" name="landlord_name" required>
                </div>
                
                <div class="form-group">
                    <label>{strings.get('case_number', 'Case Number')}</label>
                    <input type="text" name="case_number">
                </div>
                
                <div class="form-group">
                    <label>{strings.get('hearing_date', 'Hearing Date')} (if scheduled)</label>
                    <input type="date" name="hearing_date">
                </div>
                
                <div class="form-group">
                    <label>Grounds/Reasons for this motion:</label>
                    <textarea name="grounds" rows="4" required></textarea>
                </div>
                
                <div class="nav-buttons">
                    <a href="/eviction/motions?lang={lang}" class="btn btn-secondary">{strings.get('back', 'Back')}</a>
                    <button type="submit" class="btn btn-success">{strings.get('download', 'Download')} PDF</button>
                </div>
            </form>
        </div>
    """
    
    return get_html_page(title, content, lang)


@router.post("/motions/generate")
async def generate_motion_doc(
    motion_type: str = Form(...),
    tenant_name: str = Form(...),
    landlord_name: str = Form(...),
    case_number: str = Form(""),
    hearing_date: str = Form(""),
    grounds: str = Form("")
):
    """Generate Motion PDF."""
    pdf_bytes = generate_motion_pdf(
        motion_type=motion_type,
        tenant_name=tenant_name,
        landlord_name=landlord_name,
        case_number=case_number,
        hearing_date=hearing_date,
        grounds=grounds
    )
    
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=motion_{motion_type}_{datetime.now().strftime('%Y%m%d')}.pdf"}
    )


# ============================================================================
# Hearing Preparation
# ============================================================================

@router.get("/hearing", response_class=HTMLResponse)
async def hearing_prep(lang: str = Query("en")):
    """Hearing preparation page."""
    strings = get_all_strings(lang)
    
    content = f"""
        <div class="card">
            <h2>{strings.get('hearing_prep', 'Hearing Preparation')}</h2>
            
            <form action="/eviction/hearing/generate" method="POST">
                <input type="hidden" name="lang" value="{lang}">
                
                <div class="form-group">
                    <label>{strings.get('tenant_name', 'Your Full Name')}</label>
                    <input type="text" name="tenant_name" required>
                </div>
                
                <div class="form-group">
                    <label>{strings.get('hearing_date', 'Hearing Date')}</label>
                    <input type="date" name="hearing_date" required>
                </div>
                
                <div class="form-group">
                    <label>{strings.get('hearing_time', 'Hearing Time')}</label>
                    <input type="time" name="hearing_time">
                </div>
                
                <div class="form-group">
                    <label class="checkbox-item">
                        <input type="checkbox" name="is_zoom" value="true">
                        {strings.get('is_zoom_hearing', 'Is this a Zoom hearing?')}
                    </label>
                </div>
                
                <div class="nav-buttons">
                    <a href="/eviction?lang={lang}" class="btn btn-secondary">{strings.get('back', 'Back')}</a>
                    <button type="submit" class="btn btn-success">{strings.get('download', 'Download')} Checklist</button>
                </div>
            </form>
        </div>
    """
    
    return get_html_page(strings.get('hearing_prep', 'Hearing Prep'), content, lang)


@router.post("/hearing/generate")
async def generate_hearing_doc(
    tenant_name: str = Form(...),
    hearing_date: str = Form(""),
    hearing_time: str = Form(""),
    is_zoom: str = Form("")
):
    """Generate Hearing Prep PDF."""
    pdf_bytes = generate_hearing_prep_pdf(
        tenant_name=tenant_name,
        hearing_date=hearing_date,
        hearing_time=hearing_time,
        is_zoom=is_zoom == "true"
    )
    
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=hearing_prep_{datetime.now().strftime('%Y%m%d')}.pdf"}
    )


# ============================================================================
# Zoom Court Helper
# ============================================================================

@router.get("/zoom", response_class=HTMLResponse)
async def zoom_helper(lang: str = Query("en")):
    """Zoom court tips page."""
    strings = get_all_strings(lang)
    
    tips = [
        strings.get('zoom_tip_1', 'Test your audio and video'),
        strings.get('zoom_tip_2', 'Find a quiet place'),
        strings.get('zoom_tip_3', 'Dress professionally'),
        strings.get('zoom_tip_4', 'Mute when not speaking'),
    ]
    
    tips_html = "".join([f"<li>{tip}</li>" for tip in tips])
    
    content = f"""
        <div class="card">
            <h2>{strings.get('zoom_tips_title', 'Zoom Court Tips')}</h2>
            
            <ul style="list-style: none; padding: 0;">
                {tips_html.replace('<li>', '<li style="padding: 0.75rem; background: rgba(255,255,255,0.05); margin-bottom: 0.5rem; border-radius: 0.5rem;">✓ ')}
            </ul>
            
            <div style="margin-top: 1.5rem;">
                <h3>Dakota County Zoom Information</h3>
                <p style="margin-top: 0.5rem; color: #94a3b8;">
                    The court will send you a Zoom link by email before your hearing.
                    Make sure to check your email (including spam folder) for the meeting details.
                </p>
            </div>
            
            <div class="nav-buttons" style="justify-content: flex-start;">
                <a href="/eviction?lang={lang}" class="btn btn-secondary">{strings.get('back', 'Back')}</a>
            </div>
        </div>
    """
    
    return get_html_page(strings.get('zoom_court', 'Zoom Helper'), content, lang)


# ============================================================================
# API Endpoints
# ============================================================================

@router.get("/api/strings/{lang}")
async def get_translations(lang: str):
    """Get all translation strings for a language."""
    return JSONResponse(content=get_all_strings(lang))


@router.get("/api/deadlines")
async def calculate_deadlines(served_date: str = Query(...)):
    """Calculate important deadlines from service date."""
    try:
        served = datetime.strptime(served_date, "%Y-%m-%d")
        return JSONResponse(content={
            "served_date": served_date,
            "answer_deadline": (served + timedelta(days=7)).strftime("%Y-%m-%d"),
            "answer_deadline_note": "Typical deadline to file Answer (7 days)",
            "hearing_earliest": (served + timedelta(days=7)).strftime("%Y-%m-%d"),
            "hearing_latest": (served + timedelta(days=14)).strftime("%Y-%m-%d"),
        })
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
