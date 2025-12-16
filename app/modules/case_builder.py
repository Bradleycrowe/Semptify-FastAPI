"""
Semptify Case Builder Module
============================

A comprehensive module for building eviction defense cases and counter-suits.
This module was created for Bradley Crowe's case (19AV-CV-25-3477) and can be
reused for any eviction defense case.

Features:
- Case timeline management with automatic deadline tracking
- Evidence collection and organization
- Counter-claim builder with legal basis
- Motion generator (Motion to Compel, Motion to Dismiss, etc.)
- Court deadline reminders
- Document generation and output
- Defense strategy recommendations
"""

import logging
import json
from datetime import datetime, date, timedelta
from typing import Any, Dict, List, Optional
from enum import Enum
from pydantic import BaseModel

from app.sdk import (
    ModuleSDK,
    ModuleDefinition,
    ModuleCategory,
    DocumentType,
    PackType,
)

logger = logging.getLogger(__name__)


# =============================================================================
# ENUMS & DATA MODELS
# =============================================================================

class CaseType(str, Enum):
    EVICTION_DEFENSE = "eviction_defense"
    COUNTER_SUIT = "counter_suit"
    HABITABILITY = "habitability"
    SECURITY_DEPOSIT = "security_deposit"
    DISCRIMINATION = "discrimination"
    RETALIATION = "retaliation"


class EvidenceType(str, Enum):
    VIDEO = "video"
    PHOTO = "photo"
    DOCUMENT = "document"
    TEXT_MESSAGE = "text_message"
    EMAIL = "email"
    WITNESS = "witness"
    RECEIPT = "receipt"
    RECORDING = "recording"
    INSPECTION_REPORT = "inspection_report"
    POLICE_REPORT = "police_report"


class MotionCategory(str, Enum):
    TO_COMPEL = "motion_to_compel"
    TO_DISMISS = "motion_to_dismiss"
    FOR_CONTINUANCE = "motion_for_continuance"
    FOR_SUMMARY_JUDGMENT = "motion_for_summary_judgment"
    TO_STRIKE = "motion_to_strike"
    FOR_SANCTIONS = "motion_for_sanctions"


class CounterclaimType(str, Enum):
    BREACH_OF_HABITABILITY = "breach_of_habitability"
    BREACH_OF_QUIET_ENJOYMENT = "breach_of_quiet_enjoyment"
    NEGLIGENT_MAINTENANCE = "negligent_maintenance"
    FRAUD = "fraud"
    HARASSMENT = "harassment"
    ILLEGAL_LOCKOUT = "illegal_lockout"
    SECURITY_DEPOSIT = "security_deposit"
    RETALIATION = "retaliation"


class ReminderPriority(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


# =============================================================================
# CASE DATA STRUCTURES
# =============================================================================

class CaseParty(BaseModel):
    """A party in the case (plaintiff or defendant)."""
    name: str
    role: str  # "plaintiff", "defendant", "witness", "attorney"
    address: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    is_pro_se: bool = True
    notes: Optional[str] = None


class TimelineEvent(BaseModel):
    """An event in the case timeline."""
    id: str
    date: date
    title: str
    description: str
    category: str  # "lease", "violation", "communication", "court", "evidence"
    evidence_ids: List[str] = []
    is_verified: bool = False
    source: Optional[str] = None
    importance: str = "medium"  # "critical", "high", "medium", "low"


class Evidence(BaseModel):
    """A piece of evidence."""
    id: str
    title: str
    evidence_type: EvidenceType
    date_obtained: date
    date_of_event: Optional[date] = None
    description: str
    file_path: Optional[str] = None
    source: str
    relevance: str  # What this proves
    verified: bool = False
    court_exhibit_number: Optional[str] = None
    notes: Optional[str] = None


class Counterclaim(BaseModel):
    """A counterclaim against the landlord."""
    id: str
    claim_type: CounterclaimType
    title: str
    legal_basis: List[str]
    facts: List[str]
    damages_sought: Dict[str, float]
    evidence_ids: List[str]
    statutory_reference: Optional[str] = None


class Motion(BaseModel):
    """A motion to file."""
    id: str
    motion_type: MotionCategory
    title: str
    deadline: date
    basis: List[str]
    relief_sought: str
    supporting_evidence: List[str]
    filed: bool = False
    filed_date: Optional[date] = None
    hearing_date: Optional[date] = None
    status: str = "pending"


class CourtDeadline(BaseModel):
    """A court deadline or reminder."""
    id: str
    title: str
    deadline: date
    description: str
    priority: ReminderPriority
    completed: bool = False
    reminder_days: List[int] = [7, 3, 1]  # Days before to remind
    notes: Optional[str] = None


class CaseDefense(BaseModel):
    """A defense strategy."""
    id: str
    defense_type: str
    title: str
    legal_basis: str
    facts_supporting: List[str]
    evidence_ids: List[str]
    strength: str = "medium"  # "strong", "medium", "weak"


class FullCase(BaseModel):
    """Complete case data structure."""
    case_number: str
    case_type: CaseType
    court: str
    judge: Optional[str] = None
    
    # Parties
    plaintiff: CaseParty
    defendant: CaseParty
    other_parties: List[CaseParty] = []
    
    # Key dates
    lease_start: Optional[date] = None
    lease_end: Optional[date] = None
    notice_date: Optional[date] = None
    complaint_filed: Optional[date] = None
    answer_due: Optional[date] = None
    hearing_date: Optional[date] = None
    
    # Case data
    timeline: List[TimelineEvent] = []
    evidence: List[Evidence] = []
    counterclaims: List[Counterclaim] = []
    motions: List[Motion] = []
    deadlines: List[CourtDeadline] = []
    defenses: List[CaseDefense] = []
    
    # Property info
    property_address: str
    rent_amount: float
    security_deposit: float = 0
    
    # Case notes
    notes: List[str] = []
    created_at: datetime = datetime.now()
    updated_at: datetime = datetime.now()


# =============================================================================
# MODULE DEFINITION
# =============================================================================

module_definition = ModuleDefinition(
    name="case_builder",
    display_name="Case Builder",
    description="Build and manage eviction defense cases and counter-suits with timeline tracking, evidence management, and document generation",
    version="1.0.0",
    category=ModuleCategory.LEGAL,
    handles_documents=[
        DocumentType.EVICTION_NOTICE,
        DocumentType.LEASE,
        DocumentType.COURT_FILING,
    ],
    accepts_packs=[
        PackType.EVICTION_DATA,
        PackType.LEASE_DATA,
    ],
    produces_packs=[
        PackType.CASE_DATA,
        PackType.ANALYSIS_RESULT,
    ],
    depends_on=["documents", "calendar", "timeline"],
    has_ui=True,
    has_background_tasks=True,
    requires_auth=True,
)

sdk = ModuleSDK(module_definition)


# =============================================================================
# TEMPLATE DATA - MINNESOTA EVICTION LAW
# =============================================================================

MN_EVICTION_DEFENSES = {
    "improper_notice": {
        "title": "Improper Notice",
        "legal_basis": "Minn. Stat. § 504B.135 - Notice requirements not followed",
        "common_issues": [
            "Notice not served properly",
            "Notice period too short",
            "Notice lacks required information",
            "Wrong notice type used"
        ]
    },
    "retaliation": {
        "title": "Retaliatory Eviction",
        "legal_basis": "Minn. Stat. § 504B.441 - Eviction within 90 days of protected activity",
        "common_issues": [
            "Eviction after complaint to city inspector",
            "Eviction after requesting repairs",
            "Eviction after withholding rent for repairs",
            "Eviction after organizing tenants"
        ]
    },
    "habitability": {
        "title": "Breach of Habitability",
        "legal_basis": "Minn. Stat. § 504B.161 - Covenant of habitability",
        "common_issues": [
            "No heat or hot water",
            "Pest infestation",
            "Structural defects",
            "No running water",
            "Exposed wiring/safety hazards"
        ]
    },
    "discrimination": {
        "title": "Discriminatory Eviction",
        "legal_basis": "Minn. Stat. § 363A.09 - Fair Housing violations",
        "common_issues": [
            "Race/color discrimination",
            "National origin discrimination",
            "Familial status discrimination",
            "Disability discrimination",
            "Source of income discrimination"
        ]
    },
    "landlord_breach": {
        "title": "Landlord Breach of Lease",
        "legal_basis": "Contract Law - Landlord failed to perform obligations",
        "common_issues": [
            "Failed to make repairs",
            "Failed to provide services",
            "Harassment",
            "Illegal entry",
            "Utility shutoffs"
        ]
    }
}

MN_COUNTERCLAIMS = {
    "breach_of_habitability": {
        "title": "Breach of Warranty of Habitability",
        "legal_basis": "Minn. Stat. § 504B.161",
        "elements": [
            "Landlord knew or should have known of defect",
            "Defect affected habitability",
            "Tenant notified landlord or defect was obvious",
            "Reasonable time to repair passed",
            "Defect not caused by tenant"
        ],
        "damages": [
            "Rent abatement (reduction based on diminished value)",
            "Repair costs if tenant fixed it",
            "Moving costs if forced to relocate",
            "Consequential damages (lost/damaged property)"
        ]
    },
    "breach_of_quiet_enjoyment": {
        "title": "Breach of Covenant of Quiet Enjoyment",
        "legal_basis": "Minn. Stat. § 504B.375",
        "elements": [
            "Landlord substantially interfered with tenant's use",
            "Interference was material and ongoing",
            "Tenant did not cause the interference"
        ],
        "damages": [
            "Rent abatement",
            "Emotional distress damages",
            "Consequential damages"
        ]
    },
    "negligent_maintenance": {
        "title": "Negligent Maintenance/Security",
        "legal_basis": "Common Law Negligence",
        "elements": [
            "Landlord owed duty of care",
            "Landlord breached that duty",
            "Breach caused injury/damage",
            "Actual damages resulted"
        ],
        "damages": [
            "Property damage",
            "Personal injury",
            "Emotional distress"
        ]
    },
    "fraud": {
        "title": "Fraud/Misrepresentation",
        "legal_basis": "Common Law Fraud, Minn. Stat. § 325F.69",
        "elements": [
            "Landlord made false statement",
            "Landlord knew it was false",
            "Tenant relied on statement",
            "Tenant suffered damages"
        ],
        "damages": [
            "Out of pocket losses",
            "Benefit of bargain damages",
            "Punitive damages possible"
        ]
    },
    "harassment": {
        "title": "Tenant Harassment",
        "legal_basis": "Minn. Stat. § 504B.395",
        "elements": [
            "Landlord engaged in harassment",
            "Pattern of conduct or severe incident",
            "Intent to interfere with tenant's rights"
        ],
        "damages": [
            "Statutory damages",
            "Actual damages",
            "Attorney fees"
        ]
    }
}

MOTION_TEMPLATES = {
    "motion_to_compel": {
        "title": "Motion to Compel Discovery",
        "when_to_use": [
            "Landlord refuses to provide documents",
            "Landlord ignores discovery requests",
            "Need video/security footage before deletion"
        ],
        "basis": [
            "Minn. R. Civ. P. 37 - Motion to Compel Discovery",
            "Party failed to respond to proper discovery request",
            "Information is relevant and discoverable"
        ]
    },
    "motion_to_dismiss": {
        "title": "Motion to Dismiss",
        "when_to_use": [
            "Improper notice",
            "Improper service",
            "Complaint fails to state a claim",
            "Landlord lacks standing"
        ],
        "basis": [
            "Minn. R. Civ. P. 12.02 - Motion to Dismiss",
            "Failure to state a claim",
            "Procedural defects"
        ]
    },
    "motion_for_continuance": {
        "title": "Motion for Continuance",
        "when_to_use": [
            "Need more time to prepare",
            "Waiting for discovery",
            "Scheduling conflict",
            "Illness or emergency"
        ],
        "basis": [
            "Good cause shown",
            "No prejudice to opposing party",
            "First request"
        ]
    }
}


# =============================================================================
# SDK ACTIONS
# =============================================================================

@sdk.action(
    "create_case",
    description="Create a new case with basic information",
    required_params=["case_number", "case_type", "court", "property_address"],
    optional_params=["plaintiff_name", "defendant_name", "hearing_date", "rent_amount"],
    produces=["case_created", "case_id"],
)
async def create_case(
    user_id: str,
    params: Dict[str, Any],
    context: Dict[str, Any],
) -> Dict[str, Any]:
    """Create a new case."""
    case = FullCase(
        case_number=params["case_number"],
        case_type=CaseType(params.get("case_type", "eviction_defense")),
        court=params["court"],
        property_address=params["property_address"],
        rent_amount=params.get("rent_amount", 0),
        plaintiff=CaseParty(
            name=params.get("plaintiff_name", "Unknown Plaintiff"),
            role="plaintiff"
        ),
        defendant=CaseParty(
            name=params.get("defendant_name", "Unknown Defendant"),
            role="defendant",
            is_pro_se=True
        ),
    )
    
    if params.get("hearing_date"):
        case.hearing_date = datetime.strptime(params["hearing_date"], "%Y-%m-%d").date()
    
    logger.info(f"Created case {case.case_number} for user {user_id}")
    
    return {
        "case_created": True,
        "case_id": case.case_number,
        "case": case.dict()
    }


@sdk.action(
    "add_timeline_event",
    description="Add an event to the case timeline",
    required_params=["case_id", "date", "title", "description", "category"],
    optional_params=["evidence_ids", "importance", "source"],
    produces=["event_added", "event_id"],
)
async def add_timeline_event(
    user_id: str,
    params: Dict[str, Any],
    context: Dict[str, Any],
) -> Dict[str, Any]:
    """Add a timeline event."""
    event_id = f"evt_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    
    event = TimelineEvent(
        id=event_id,
        date=datetime.strptime(params["date"], "%Y-%m-%d").date(),
        title=params["title"],
        description=params["description"],
        category=params["category"],
        evidence_ids=params.get("evidence_ids", []),
        importance=params.get("importance", "medium"),
        source=params.get("source"),
    )
    
    return {
        "event_added": True,
        "event_id": event_id,
        "event": event.dict()
    }


@sdk.action(
    "add_evidence",
    description="Add evidence to the case",
    required_params=["case_id", "title", "evidence_type", "description", "source", "relevance"],
    optional_params=["date_obtained", "date_of_event", "file_path", "notes"],
    produces=["evidence_added", "evidence_id"],
)
async def add_evidence(
    user_id: str,
    params: Dict[str, Any],
    context: Dict[str, Any],
) -> Dict[str, Any]:
    """Add evidence to a case."""
    evidence_id = f"evi_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    
    evidence = Evidence(
        id=evidence_id,
        title=params["title"],
        evidence_type=EvidenceType(params["evidence_type"]),
        date_obtained=datetime.strptime(params.get("date_obtained", datetime.now().strftime("%Y-%m-%d")), "%Y-%m-%d").date(),
        date_of_event=datetime.strptime(params["date_of_event"], "%Y-%m-%d").date() if params.get("date_of_event") else None,
        description=params["description"],
        file_path=params.get("file_path"),
        source=params["source"],
        relevance=params["relevance"],
        notes=params.get("notes"),
    )
    
    return {
        "evidence_added": True,
        "evidence_id": evidence_id,
        "evidence": evidence.dict()
    }


@sdk.action(
    "add_counterclaim",
    description="Add a counterclaim to the case",
    required_params=["case_id", "claim_type", "title", "facts"],
    optional_params=["damages_sought", "evidence_ids"],
    produces=["counterclaim_added", "counterclaim_id"],
)
async def add_counterclaim(
    user_id: str,
    params: Dict[str, Any],
    context: Dict[str, Any],
) -> Dict[str, Any]:
    """Add a counterclaim."""
    claim_id = f"clm_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    
    # Get template data
    claim_type = params["claim_type"]
    template = MN_COUNTERCLAIMS.get(claim_type, {})
    
    counterclaim = Counterclaim(
        id=claim_id,
        claim_type=CounterclaimType(claim_type),
        title=params["title"],
        legal_basis=template.get("legal_basis", []) if isinstance(template.get("legal_basis"), list) else [template.get("legal_basis", "")],
        facts=params["facts"] if isinstance(params["facts"], list) else [params["facts"]],
        damages_sought=params.get("damages_sought", {}),
        evidence_ids=params.get("evidence_ids", []),
    )
    
    return {
        "counterclaim_added": True,
        "counterclaim_id": claim_id,
        "counterclaim": counterclaim.dict(),
        "template_info": template
    }


@sdk.action(
    "add_deadline",
    description="Add a court deadline or reminder",
    required_params=["case_id", "title", "deadline", "priority"],
    optional_params=["description", "reminder_days", "notes"],
    produces=["deadline_added", "deadline_id"],
)
async def add_deadline(
    user_id: str,
    params: Dict[str, Any],
    context: Dict[str, Any],
) -> Dict[str, Any]:
    """Add a deadline."""
    deadline_id = f"ddl_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    
    deadline = CourtDeadline(
        id=deadline_id,
        title=params["title"],
        deadline=datetime.strptime(params["deadline"], "%Y-%m-%d").date(),
        description=params.get("description", ""),
        priority=ReminderPriority(params["priority"]),
        reminder_days=params.get("reminder_days", [7, 3, 1]),
        notes=params.get("notes"),
    )
    
    return {
        "deadline_added": True,
        "deadline_id": deadline_id,
        "deadline": deadline.dict()
    }


@sdk.action(
    "get_upcoming_deadlines",
    description="Get all upcoming deadlines within a time range",
    required_params=["case_id"],
    optional_params=["days_ahead"],
    produces=["deadlines", "urgent_count"],
)
async def get_upcoming_deadlines(
    user_id: str,
    params: Dict[str, Any],
    context: Dict[str, Any],
) -> Dict[str, Any]:
    """Get upcoming deadlines."""
    days_ahead = params.get("days_ahead", 30)
    today = date.today()
    cutoff = today + timedelta(days=days_ahead)
    
    # This would fetch from database - return example
    return {
        "deadlines": [],
        "urgent_count": 0,
        "days_ahead": days_ahead
    }


@sdk.action(
    "generate_counterclaim_document",
    description="Generate an amended counterclaim document",
    required_params=["case_id"],
    optional_params=["include_prayer", "format"],
    produces=["document_text", "document_path"],
)
async def generate_counterclaim_document(
    user_id: str,
    params: Dict[str, Any],
    context: Dict[str, Any],
) -> Dict[str, Any]:
    """Generate counterclaim document text."""
    case = context.get("case", {})
    
    # This would generate the full document
    return {
        "document_text": "AMENDED COUNTERCLAIM...",
        "document_path": None,
        "generated": True
    }


@sdk.action(
    "generate_motion",
    description="Generate a motion document",
    required_params=["case_id", "motion_type"],
    optional_params=["specific_relief", "supporting_facts"],
    produces=["document_text", "motion"],
)
async def generate_motion(
    user_id: str,
    params: Dict[str, Any],
    context: Dict[str, Any],
) -> Dict[str, Any]:
    """Generate a motion document."""
    motion_type = params["motion_type"]
    template = MOTION_TEMPLATES.get(motion_type, {})
    
    return {
        "document_text": f"MOTION: {template.get('title', motion_type)}...",
        "motion": template,
        "generated": True
    }


@sdk.action(
    "analyze_defenses",
    description="Analyze available defenses based on case facts",
    required_params=["case_id"],
    optional_params=["timeline_events"],
    produces=["defenses", "recommendations"],
)
async def analyze_defenses(
    user_id: str,
    params: Dict[str, Any],
    context: Dict[str, Any],
) -> Dict[str, Any]:
    """Analyze potential defenses."""
    available_defenses = []
    recommendations = []
    
    for defense_id, defense_info in MN_EVICTION_DEFENSES.items():
        available_defenses.append({
            "id": defense_id,
            "title": defense_info["title"],
            "legal_basis": defense_info["legal_basis"],
            "common_issues": defense_info["common_issues"]
        })
    
    recommendations.append("Review your notice - check dates and service method")
    recommendations.append("Document all habitability issues with photos/video")
    recommendations.append("Keep records of all communications with landlord")
    
    return {
        "defenses": available_defenses,
        "recommendations": recommendations
    }


@sdk.action(
    "get_case_summary",
    description="Get a complete summary of the case",
    required_params=["case_id"],
    produces=["summary", "status", "next_steps"],
)
async def get_case_summary(
    user_id: str,
    params: Dict[str, Any],
    context: Dict[str, Any],
) -> Dict[str, Any]:
    """Get case summary."""
    return {
        "summary": {},
        "status": "active",
        "next_steps": []
    }


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def calculate_days_until(target_date: date) -> int:
    """Calculate days until a target date."""
    today = date.today()
    delta = target_date - today
    return delta.days


def get_deadline_status(deadline: date) -> str:
    """Get status based on deadline proximity."""
    days = calculate_days_until(deadline)
    if days < 0:
        return "overdue"
    elif days == 0:
        return "today"
    elif days <= 3:
        return "urgent"
    elif days <= 7:
        return "soon"
    else:
        return "upcoming"


def format_date_display(d: date) -> str:
    """Format date for display."""
    return d.strftime("%B %d, %Y")


# =============================================================================
# INITIALIZE
# =============================================================================

def initialize():
    """Initialize the case builder module."""
    sdk.initialize()
    logger.info("Case Builder module initialized")


# Export for use in other parts of the application
__all__ = [
    "module_definition",
    "sdk",
    "initialize",
    "FullCase",
    "CaseParty",
    "TimelineEvent",
    "Evidence",
    "Counterclaim",
    "Motion",
    "CourtDeadline",
    "CaseDefense",
    "MN_EVICTION_DEFENSES",
    "MN_COUNTERCLAIMS",
    "MOTION_TEMPLATES",
]
