"""
Semptify 5.0 - Role-Based UI Router
Routes users to appropriate interface based on their role and device.

Role → UI Mapping:
- USER (Tenant):    Mobile-first, simplified wizard-driven interface
- ADVOCATE:         Responsive, multi-case management view
- LEGAL (Attorney): Desktop, full features + privilege separation
- ADMIN:            Desktop, system configuration + analytics
"""

from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import RedirectResponse, HTMLResponse
from typing import Optional
import logging

from app.core.user_context import (
    UserRole, 
    UserContext, 
    get_role_metadata,
    ROLE_METADATA
)
from app.core.security import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ui", tags=["Role UI"])


# =============================================================================
# Device Detection Helper
# =============================================================================

def detect_device_type(request: Request) -> str:
    """
    Detect if user is on mobile, tablet, or desktop.
    Returns: 'mobile', 'tablet', or 'desktop'
    """
    user_agent = request.headers.get("user-agent", "").lower()
    
    mobile_keywords = ["iphone", "android", "mobile", "phone", "ipod"]
    tablet_keywords = ["ipad", "tablet", "kindle"]
    
    if any(kw in user_agent for kw in tablet_keywords):
        return "tablet"
    elif any(kw in user_agent for kw in mobile_keywords):
        return "mobile"
    return "desktop"


# =============================================================================
# Role-Based Landing Pages
# =============================================================================

# Map roles to their landing pages
ROLE_LANDING_PAGES = {
    UserRole.USER: "/static/tenant/index.html",       # Mobile-first tenant UI
    UserRole.ADVOCATE: "/static/advocate/index.html", # Multi-case advocate UI  
    UserRole.LEGAL: "/static/legal/index.html",       # Attorney UI with privilege
    UserRole.MANAGER: "/static/manager/index.html",   # Property manager UI
    UserRole.ADMIN: "/static/admin/index.html",       # Admin dashboard
}

# Fallback pages if role-specific UI doesn't exist yet
ROLE_FALLBACK_PAGES = {
    UserRole.USER: "/static/tenant/index.html",          # Mobile-first tenant UI
    UserRole.ADVOCATE: "/static/advocate/index.html",    # Advocate multi-case UI
    UserRole.LEGAL: "/static/legal/index.html",          # Attorney with privilege
    UserRole.MANAGER: "/static/dashboard.html",
    UserRole.ADMIN: "/static/enterprise-dashboard.html",
}


@router.get("/")
async def ui_router(
    request: Request,
    user: Optional[UserContext] = Depends(get_current_user)
):
    """
    Main UI router - redirects to appropriate interface based on role.
    If not authenticated, redirects to welcome/login page.
    """
    if not user:
        return RedirectResponse(url="/static/welcome.html", status_code=302)
    
    device = detect_device_type(request)
    role_meta = get_role_metadata(user.role)
    
    logger.info(f"UI routing: user={user.user_id}, role={user.role.value}, device={device}")
    
    # Get the appropriate landing page
    landing_page = ROLE_FALLBACK_PAGES.get(user.role, "/static/welcome.html")
    
    # Log for debugging
    logger.info(f"Redirecting to: {landing_page}")
    
    return RedirectResponse(url=landing_page, status_code=302)


@router.get("/role-info")
async def get_role_info(
    user: Optional[UserContext] = Depends(get_current_user)
) -> dict:
    """
    Get current user's role information for UI customization.
    Returns role metadata, permissions, and UI configuration.
    """
    if not user:
        return {
            "authenticated": False,
            "role": None,
            "ui_mode": "public",
            "landing_page": "/static/welcome.html"
        }
    
    role_meta = get_role_metadata(user.role)
    
    return {
        "authenticated": True,
        "user_id": user.user_id,
        "role": user.role.value,
        "role_display": role_meta["display_name"],
        "role_icon": role_meta["icon"],
        "ui_mode": role_meta["ui_mode"],
        "landing_page": role_meta["landing_page"],
        "permissions": list(user.permissions),
        "can_view_privileged": user.has_permission("privileged_read"),
        "can_create_privileged": user.has_permission("privileged_create"),
        "can_help_multiple_users": user.has_permission("multi_user"),
    }


@router.get("/available-roles")
async def get_available_roles() -> dict:
    """
    Get all available roles with their metadata.
    Public endpoint for role selection UI.
    """
    roles = []
    for role in UserRole:
        meta = ROLE_METADATA.get(role, {})
        roles.append({
            "role": role.value,
            "display_name": meta.get("display_name", role.value),
            "description": meta.get("description", ""),
            "icon": meta.get("icon", "👤"),
            "ui_mode": meta.get("ui_mode", "desktop"),
        })
    
    return {
        "roles": roles,
        "default_role": UserRole.USER.value
    }


# =============================================================================
# Role-Specific Feature Flags
# =============================================================================

@router.get("/features")
async def get_role_features(
    user: Optional[UserContext] = Depends(get_current_user)
) -> dict:
    """
    Get feature flags based on user's role.
    Frontend uses this to show/hide UI elements.
    """
    if not user:
        return {
            "features": {
                "show_login": True,
                "show_demo": True,
            }
        }
    
    # Base features for all authenticated users
    features = {
        "show_login": False,
        "show_demo": False,
        "show_vault": user.has_permission("vault_read"),
        "show_timeline": user.has_permission("timeline_read"),
        "show_calendar": user.has_permission("calendar_read"),
        "show_copilot": user.has_permission("copilot_use"),
        "show_complaints": user.has_permission("complaints_create"),
        "show_ledger": user.has_permission("ledger_read"),
    }
    
    # Role-specific features
    if user.role == UserRole.USER:
        features.update({
            "ui_mode": "simplified",
            "show_wizard": True,           # Guided wizards for tenants
            "show_quick_actions": True,    # Big action buttons
            "show_help_request": True,     # Request advocate help
        })
    
    elif user.role == UserRole.ADVOCATE:
        features.update({
            "ui_mode": "standard",
            "show_client_list": True,      # List of assigned clients
            "show_case_queue": True,       # Incoming cases
            "show_intake_form": True,      # New client intake
            "show_case_notes": True,       # Non-privileged notes
        })
    
    elif user.role == UserRole.LEGAL:
        features.update({
            "ui_mode": "advanced",
            "show_client_list": True,
            "show_case_queue": True,
            "show_intake_form": True,
            "show_case_notes": True,
            # Attorney-specific
            "show_privileged_notes": True,   # Attorney-client privilege
            "show_work_product": True,       # Work product section
            "show_legal_research": True,     # Advanced legal tools
            "show_court_filing": True,       # Generate court docs
            "show_discovery_tools": True,    # Discovery prep
            "show_conflict_check": True,     # Conflict checking
            "privilege_indicator": True,     # Show privilege badges
        })
    
    elif user.role == UserRole.ADMIN:
        features.update({
            "ui_mode": "full",
            "show_system_config": True,
            "show_analytics": True,
            "show_user_management": True,
            "show_all_features": True,
        })
    
    return {"features": features, "role": user.role.value}


# =============================================================================
# Navigation Menu by Role
# =============================================================================

@router.get("/navigation")
async def get_navigation_menu(
    user: Optional[UserContext] = Depends(get_current_user)
) -> dict:
    """
    Get navigation menu items based on user's role.
    Returns ordered list of menu items for the UI.
    """
    if not user:
        return {
            "menu": [
                {"label": "Home", "path": "/", "icon": "🏠"},
                {"label": "Sign In", "path": "/auth/login", "icon": "🔑"},
            ]
        }
    
    # Base menu for all users
    menu = []
    
    # Tenant (USER) - simplified menu
    if user.role == UserRole.USER:
        menu = [
            {"label": "My Case", "path": "/tenant", "icon": "📁"},
            {"label": "Documents", "path": "/tenant/documents", "icon": "📄"},
            {"label": "Timeline", "path": "/tenant/timeline", "icon": "📅"},
            {"label": "Get Help", "path": "/tenant/help", "icon": "🆘"},
            {"label": "AI Assistant", "path": "/tenant/copilot", "icon": "🤖"},
        ]
    
    # Advocate - case management focus
    elif user.role == UserRole.ADVOCATE:
        menu = [
            {"label": "Dashboard", "path": "/advocate", "icon": "📊"},
            {"label": "My Clients", "path": "/advocate/clients", "icon": "👥"},
            {"label": "Case Queue", "path": "/advocate/queue", "icon": "📋"},
            {"label": "New Intake", "path": "/advocate/intake", "icon": "➕"},
            {"label": "Calendar", "path": "/advocate/calendar", "icon": "📅"},
            {"label": "Resources", "path": "/advocate/resources", "icon": "📚"},
        ]
    
    # Legal (Attorney) - full legal tools
    elif user.role == UserRole.LEGAL:
        menu = [
            {"label": "Dashboard", "path": "/legal", "icon": "⚖️"},
            {"label": "Clients", "path": "/legal/clients", "icon": "👥"},
            {"label": "Case Queue", "path": "/legal/queue", "icon": "📋"},
            {"label": "Calendar", "path": "/legal/calendar", "icon": "📅"},
            {"divider": True},
            {"label": "Privileged Notes", "path": "/legal/privileged", "icon": "🔒", "badge": "PRIV"},
            {"label": "Work Product", "path": "/legal/work-product", "icon": "📝", "badge": "WP"},
            {"label": "Court Filings", "path": "/legal/filings", "icon": "🏛️"},
            {"divider": True},
            {"label": "Legal Research", "path": "/legal/research", "icon": "🔍"},
            {"label": "Law Library", "path": "/legal/library", "icon": "📚"},
        ]
    
    # Admin - system management
    elif user.role == UserRole.ADMIN:
        menu = [
            {"label": "Dashboard", "path": "/admin", "icon": "📊"},
            {"label": "Users", "path": "/admin/users", "icon": "👥"},
            {"label": "System", "path": "/admin/system", "icon": "⚙️"},
            {"label": "Analytics", "path": "/admin/analytics", "icon": "📈"},
            {"label": "Logs", "path": "/admin/logs", "icon": "📋"},
            {"divider": True},
            {"label": "All Features", "path": "/static/dashboard.html", "icon": "🔧"},
        ]
    
    return {
        "menu": menu,
        "role": user.role.value,
        "role_display": get_role_metadata(user.role)["display_name"],
    }
