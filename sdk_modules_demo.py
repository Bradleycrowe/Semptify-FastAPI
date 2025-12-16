# app.py
import logging
from typing import Any, Dict, List, Optional
from datetime import datetime
from enum import Enum
from dataclasses import dataclass, field
from functools import wraps
import asyncio
import uuid

from fastapi import FastAPI, Body

logger = logging.getLogger(__name__)

# =============================================================================
# SDK CORE
# =============================================================================

class ModuleCategory(str, Enum):
    DOCUMENT = "document"
    LEGAL = "legal"
    CALENDAR = "calendar"
    COMMUNICATION = "communication"
    ANALYSIS = "analysis"
    STORAGE = "storage"
    UI = "ui"
    UTILITY = "utility"
    AI = "ai"
    INTEGRATION = "integration"

class DocumentType(str, Enum):
    EVICTION_NOTICE = "eviction_notice"
    LEASE = "lease"
    COURT_FILING = "court_filing"
    PAYMENT_RECORD = "payment_record"
    COMMUNICATION = "communication"
    PHOTO = "photo"
    LEGAL_FORM = "legal_form"
    ID_DOCUMENT = "id_document"
    UNKNOWN = "unknown"

class PackType(str, Enum):
    EVICTION_DATA = "eviction_data"
    LEASE_DATA = "lease_data"
    DEADLINE_DATA = "deadline_data"
    CASE_DATA = "case_data"
    USER_DATA = "user_data"
    FORM_DATA = "form_data"
    ANALYSIS_RESULT = "analysis_result"
    CUSTOM = "custom"

@dataclass
class ActionDefinition:
    name: str
    handler: Any
    description: str = ""
    required_params: List[str] = field(default_factory=list)
    optional_params: List[str] = field(default_factory=list)
    produces: List[str] = field(default_factory=list)
    requires_context: List[str] = field(default_factory=list)
    is_async: bool = True
    timeout_seconds: int = 30

@dataclass
class ModuleDefinition:
    name: str
    display_name: str
    description: str
    version: str = "1.0.0"
    category: ModuleCategory = ModuleCategory.UTILITY
    handles_documents: List[DocumentType] = field(default_factory=list)
    accepts_packs: List[PackType] = field(default_factory=list)
    produces_packs: List[PackType] = field(default_factory=list)
    depends_on: List[str] = field(default_factory=list)
    has_ui: bool = False
    has_background_tasks: bool = False
    requires_auth: bool = True

@dataclass
class InfoPack:
    id: str
    pack_type: PackType
    source_module: str
    target_module: Optional[str]
    user_id: str
    data: Dict[str, Any]
    created_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    priority: int = 5

class ModuleSDK:
    def __init__(self, definition: ModuleDefinition):
        self.definition = definition
        self.actions: Dict[str, ActionDefinition] = {}
        self._initialized = False

    def action(self, name: str, description: str = "", required_params=None,
               optional_params=None, produces=None, requires_context=None,
               timeout_seconds: int = 30):
        def decorator(func):
            if not asyncio.iscoroutinefunction(func):
                @wraps(func)
                async def async_wrapper(*args, **kwargs):
                    return func(*args, **kwargs)
                handler = async_wrapper
            else:
                handler = func
            self.actions[name] = ActionDefinition(
                name=name, handler=handler, description=description,
                required_params=required_params or [],
                optional_params=optional_params or [],
                produces=produces or [],
                requires_context=requires_context or [],
            )
            return handler
        return decorator

    async def invoke_action(self, module: str, action: str, user_id: str, params: Dict[str, Any]):
        if module != self.definition.name:
            return {"error": f"Wrong module {module}"}
        if action not in self.actions:
            return {"error": f"Unknown action {action}"}
        return await self.actions[action].handler(user_id, params, {})

    def initialize(self):
        self._initialized = True
        logger.info(f"✅ {self.definition.display_name} initialized")

# =============================================================================
# MODULES
# =============================================================================

# Complaints
complaints_def = ModuleDefinition(
    name="complaints", display_name="Complaints", description="Complaint filing"
)
complaints_sdk = ModuleSDK(complaints_def)

@complaints_sdk.action("file_complaint", required_params=["target_agency","violation_type","facts","language"], produces=["complaint_record"])
async def file_complaint(user_id, params, context):
    record = {"id": f"cmp_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}", **params, "status":"submitted"}
    return {"complaint_record": record}

@complaints_sdk.action("update_status", required_params=["complaint_id","status"], produces=["complaint_status"])
async def update_status(user_id, params, context):
    return {"complaint_status": {**params, "updated_at": datetime.utcnow().isoformat()}}

@complaints_sdk.action("export_zip", required_params=["complaint_id"], produces=["zip_bundle"])
async def export_zip(user_id, params, context):
    return {"zip_bundle": {"complaint_id": params["complaint_id"], "zip_path": f"/exports/{params['complaint_id']}.zip"}}

complaints_sdk.initialize()

# Fraud Exposure
fraud_def = ModuleDefinition(
    name="fraud_exposure", display_name="Fraud Exposure", description="Fraud analysis"
)
fraud_sdk = ModuleSDK(fraud_def)

@fraud_sdk.action("analyze_fraud", required_params=["landlord_id","case_docs","subsidies","lenders"], produces=["fraud_report"])
async def analyze_fraud(user_id, params, context):
    findings = []
    if any(d.get("signature_status")=="missing" for d in params["case_docs"]):
        findings.append({"rule":"unsigned_documents"})
    report = {"landlord_id":params["landlord_id"],"findings":findings,"created_at":datetime.utcnow().isoformat()}
    return {"fraud_report": report}

fraud_sdk.initialize()

# Public Exposure
public_def = ModuleDefinition(
    name="public_exposure", display_name="Public Exposure", description="Press releases"
)
public_sdk = ModuleSDK(public_def)

@public_sdk.action("generate_press_release", required_params=["property","violations","contact","bundle_link","language"], produces=["press_release"])
async def generate_press_release(user_id, params, context):
    return {"press_release": {"headline":"Tenants expose misconduct","lede":f"{params['property']} issues: {params['violations']}", "cta":f"Contact {params['contact']}", "bundle":params["bundle_link"]}}

public_sdk.initialize()

# =============================================================================
# FASTAPI APP
# =============================================================================

app = FastAPI(title="Semptify One-File API")

@app.post("/complaints/file")
async def api_file(payload: Dict[str,Any]):
    return await complaints_sdk.invoke_action("complaints","file_complaint","user",payload)

@app.post("/fraud/analyze")
async def api_fraud(payload: Dict[str,Any]):
    return await fraud_sdk.invoke_action("fraud_exposure","analyze_fraud","user",payload)

@app.post("/public/press")
async def api_press(payload: Dict[str,Any]):
    return await public_sdk.invoke_action("public_exposure","generate_press_release","user",payload)

@app.post("/campaign/launch")
async def launch_campaign(payload: Dict[str,Any]=Body(...)):
    complaint = await complaints_sdk.invoke_action("complaints","file_complaint","user",payload.get("complaint",{}))
    fraud = await fraud_sdk.invoke_action("fraud_exposure","analyze_fraud","user",payload.get("fraud",{}))
    press = await public_sdk.invoke_action("public_exposure","generate_press_release","user",payload.get("press",{}))
    export = await complaints_sdk.invoke_action("complaints","export_zip","user",{"complaint_id": complaint["complaint_record"]["id"]})
    return {"complaint":complaint,"fraud":fraud,"press":press,"zip":export}

@app.get("/health")
async def health():
    return {"status":"ok"}
