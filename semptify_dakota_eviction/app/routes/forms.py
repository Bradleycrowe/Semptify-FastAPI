"""
Dakota County Eviction Defense - Court Forms Routes
Handles official court forms library and downloads.
"""

import json
import httpx
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Request, Query, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.templating import Jinja2Templates

# Import services
import sys
sys.path.append(str(Path(__file__).parent.parent))
from services.i18n import get_string, get_all_strings, get_supported_languages, is_rtl

# ============================================================================
# Router Setup
# ============================================================================

router = APIRouter()

BASE_DIR = Path(__file__).parent.parent
TEMPLATES_DIR = BASE_DIR / "templates"
ASSETS_DIR = BASE_DIR / "assets"
FORMS_CACHE_DIR = ASSETS_DIR / "forms"

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
templates.env.globals["_"] = get_string
templates.env.globals["is_rtl"] = is_rtl


# ============================================================================
# Forms Library Routes
# ============================================================================

@router.get("/library", response_class=HTMLResponse)
async def forms_library(
    request: Request,
    lang: str = Query("en"),
    category: Optional[str] = Query(None, description="Filter by category")
):
    """
    Court Forms Library - Browse and download official MN court forms.
    """
    strings = get_all_strings(lang)
    
    # Load forms manifest
    forms_path = ASSETS_DIR / "forms.json"
    forms = []
    resources = []
    
    if forms_path.exists():
        with open(forms_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            forms = data.get("forms", [])
            resources = data.get("resources", [])
    
    # Filter by category if specified
    if category:
        forms = [f for f in forms if f.get("category") == category]
    
    # Get unique categories
    categories = list(set(f.get("category", "other") for f in data.get("forms", [])))
    
    # Localize form names
    for form in forms:
        name_key = f"name_{lang}" if lang != "en" else "name"
        form["display_name"] = form.get(name_key, form.get("name", "Unknown Form"))
    
    return templates.TemplateResponse("forms/library.html", {
        "request": request,
        "lang": lang,
        "is_rtl": is_rtl(lang),
        "strings": strings,
        "forms": forms,
        "categories": categories,
        "selected_category": category,
        "resources": resources,
        "languages": get_supported_languages()
    })


@router.get("/api/list")
async def list_all_forms(
    lang: str = Query("en"),
    category: Optional[str] = Query(None)
):
    """API: List all available court forms."""
    forms_path = ASSETS_DIR / "forms.json"
    
    if not forms_path.exists():
        return JSONResponse(content={"forms": [], "error": "Forms manifest not found"})
    
    with open(forms_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    forms = data.get("forms", [])
    
    # Filter by category
    if category:
        forms = [f for f in forms if f.get("category") == category]
    
    # Add localized names
    for form in forms:
        name_key = f"name_{lang}" if lang != "en" else "name"
        form["display_name"] = form.get(name_key, form.get("name", "Unknown"))
    
    return JSONResponse(content={
        "forms": forms,
        "total": len(forms),
        "language": lang
    })


@router.get("/api/form/{form_id}")
async def get_form_details(form_id: str, lang: str = Query("en")):
    """API: Get details for a specific form."""
    forms_path = ASSETS_DIR / "forms.json"
    
    if not forms_path.exists():
        raise HTTPException(status_code=500, detail="Forms manifest not found")
    
    with open(forms_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    forms = data.get("forms", [])
    form = next((f for f in forms if f.get("id") == form_id), None)
    
    if not form:
        raise HTTPException(status_code=404, detail=f"Form {form_id} not found")
    
    # Add localized name
    name_key = f"name_{lang}" if lang != "en" else "name"
    form["display_name"] = form.get(name_key, form.get("name", "Unknown"))
    
    return JSONResponse(content=form)


@router.get("/download/{form_id}")
async def download_form(form_id: str):
    """
    Redirect to official court form download.
    We don't host court forms directly - redirect to mncourts.gov.
    """
    forms_path = ASSETS_DIR / "forms.json"
    
    if not forms_path.exists():
        raise HTTPException(status_code=500, detail="Forms manifest not found")
    
    with open(forms_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    forms = data.get("forms", [])
    form = next((f for f in forms if f.get("id") == form_id), None)
    
    if not form:
        raise HTTPException(status_code=404, detail=f"Form {form_id} not found")
    
    url = form.get("url")
    if not url:
        raise HTTPException(status_code=404, detail=f"No download URL for form {form_id}")
    
    # Redirect to official source
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url=url, status_code=302)


@router.get("/proxy/{form_id}")
async def proxy_form_download(form_id: str):
    """
    Proxy download of court form (for offline/caching use).
    Fetches from official source and returns to client.
    """
    forms_path = ASSETS_DIR / "forms.json"
    
    if not forms_path.exists():
        raise HTTPException(status_code=500, detail="Forms manifest not found")
    
    with open(forms_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    forms = data.get("forms", [])
    form = next((f for f in forms if f.get("id") == form_id), None)
    
    if not form:
        raise HTTPException(status_code=404, detail=f"Form {form_id} not found")
    
    url = form.get("url")
    if not url:
        raise HTTPException(status_code=404, detail=f"No download URL for form {form_id}")
    
    try:
        # Check cache first
        cached_path = FORMS_CACHE_DIR / form.get("local", f"{form_id}.pdf")
        if cached_path.exists():
            return StreamingResponse(
                open(cached_path, "rb"),
                media_type="application/pdf",
                headers={
                    "Content-Disposition": f'attachment; filename="{form.get("local", form_id + ".pdf")}"'
                }
            )
        
        # Fetch from source
        async with httpx.AsyncClient() as client:
            response = await client.get(url, follow_redirects=True, timeout=30.0)
            response.raise_for_status()
        
        content_type = response.headers.get("content-type", "application/pdf")
        filename = form.get("local", f"{form_id}.pdf")
        
        return StreamingResponse(
            iter([response.content]),
            media_type=content_type,
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"'
            }
        )
    
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"Failed to fetch form: {str(e)}")


# ============================================================================
# Resources Routes
# ============================================================================

@router.get("/resources", response_class=HTMLResponse)
async def legal_resources(request: Request, lang: str = Query("en")):
    """
    Legal Aid Resources - Contact information and helpful links.
    """
    strings = get_all_strings(lang)
    
    # Load resources from forms.json
    forms_path = ASSETS_DIR / "forms.json"
    resources = []
    
    if forms_path.exists():
        with open(forms_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            resources = data.get("resources", [])
    
    return templates.TemplateResponse("forms/resources.html", {
        "request": request,
        "lang": lang,
        "is_rtl": is_rtl(lang),
        "strings": strings,
        "resources": resources,
        "languages": get_supported_languages()
    })


@router.get("/api/resources")
async def list_resources():
    """API: List all legal aid resources."""
    forms_path = ASSETS_DIR / "forms.json"
    
    if not forms_path.exists():
        return JSONResponse(content={"resources": []})
    
    with open(forms_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    return JSONResponse(content={
        "resources": data.get("resources", []),
        "zoom_court": data.get("zoom_court", {})
    })


# ============================================================================
# Form Categories
# ============================================================================

FORM_CATEGORIES = {
    "answer": {
        "en": "Answer & Response",
        "es": "Respuesta",
        "so": "Jawaab",
        "ar": "الرد"
    },
    "motion": {
        "en": "Motions",
        "es": "Mociones",
        "so": "Codsiyada",
        "ar": "الطلبات"
    },
    "counterclaim": {
        "en": "Counterclaims",
        "es": "Contrademandas",
        "so": "Dacwadaha Lid ah",
        "ar": "الدعاوى المضادة"
    },
    "fee_waiver": {
        "en": "Fee Waivers",
        "es": "Exenciones de Tarifas",
        "so": "Cafinta Kharashka",
        "ar": "الإعفاءات من الرسوم"
    },
    "expungement": {
        "en": "Expungement",
        "es": "Eliminación de Registro",
        "so": "Tirtirida Diiwaanka",
        "ar": "محو السجل"
    },
    "evidence": {
        "en": "Evidence & Documentation",
        "es": "Evidencia y Documentación",
        "so": "Caddayn iyo Dukumeenti",
        "ar": "الأدلة والتوثيق"
    },
    "rent_escrow": {
        "en": "Rent Escrow",
        "es": "Depósito de Alquiler",
        "so": "Kaydinta Kirada",
        "ar": "حجز الإيجار"
    },
    "service": {
        "en": "Service of Process",
        "es": "Notificación",
        "so": "Adeegga",
        "ar": "التبليغ"
    }
}


@router.get("/api/categories")
async def list_categories(lang: str = Query("en")):
    """API: List all form categories with localized names."""
    categories = []
    
    for cat_id, names in FORM_CATEGORIES.items():
        categories.append({
            "id": cat_id,
            "name": names.get(lang, names.get("en", cat_id))
        })
    
    return JSONResponse(content={"categories": categories})
