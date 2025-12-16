"""
Case Builder API Router
=======================

REST API endpoints for the Case Builder module.
Provides endpoints for creating cases, managing timelines, evidence,
counterclaims, motions, and generating court documents.
"""

import os
import json
import logging
from datetime import datetime, date, timedelta
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, Depends, Query, Body
from pydantic import BaseModel
from enum import Enum

from app.core.security import require_user, StorageUser
from app.core.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/case-builder", tags=["Case Builder"])


# =============================================================================
# MODELS
# =============================================================================

class CaseCreate(BaseModel):
    case_number: str
    case_type: str = "eviction_defense"
    court: str
    property_address: str
    rent_amount: float = 0
    security_deposit: float = 0
    plaintiff_name: str
    defendant_name: str
    hearing_date: Optional[str] = None
    lease_start: Optional[str] = None
    lease_end: Optional[str] = None
    notes: Optional[str] = None


class TimelineEventCreate(BaseModel):
    date: str
    title: str
    description: str
    category: str  # lease, violation, communication, court, evidence
    importance: str = "medium"  # critical, high, medium, low
    evidence_ids: List[str] = []
    source: Optional[str] = None


class EvidenceCreate(BaseModel):
    title: str
    evidence_type: str  # video, photo, document, text_message, email, witness
    date_obtained: Optional[str] = None
    date_of_event: Optional[str] = None
    description: str
    source: str
    relevance: str
    file_path: Optional[str] = None
    notes: Optional[str] = None


class CounterclaimCreate(BaseModel):
    claim_type: str
    title: str
    facts: List[str]
    damages_sought: Dict[str, float] = {}
    evidence_ids: List[str] = []
    notes: Optional[str] = None


class MotionCreate(BaseModel):
    motion_type: str
    title: str
    deadline: str
    basis: List[str]
    relief_sought: str
    supporting_evidence: List[str] = []
    notes: Optional[str] = None


class DeadlineCreate(BaseModel):
    title: str
    deadline: str
    description: str
    priority: str = "medium"  # critical, high, medium, low
    reminder_days: List[int] = [7, 3, 1]
    notes: Optional[str] = None


class DefenseCreate(BaseModel):
    defense_type: str
    title: str
    legal_basis: str
    facts_supporting: List[str]
    evidence_ids: List[str] = []
    strength: str = "medium"


# =============================================================================
# DATA STORAGE PATH - USER-SCOPED FOR PRIVACY
# =============================================================================

def get_user_case_data_dir(user_id: str):
    """Get/create the user-specific case data directory."""
    # Sanitize user_id to prevent path traversal
    safe_user_id = "".join(c for c in user_id if c.isalnum() or c in '_-')
    data_dir = os.path.join(os.getcwd(), "data", "cases", safe_user_id)
    os.makedirs(data_dir, exist_ok=True)
    return data_dir


def get_case_data_dir():
    """Get/create the legacy case data directory (for migration only)."""
    data_dir = os.path.join(os.getcwd(), "data", "cases")
    os.makedirs(data_dir, exist_ok=True)
    return data_dir


def get_case_file(case_id: str, user_id: str) -> str:
    """Get path to case file for a specific user."""
    data_dir = get_user_case_data_dir(user_id)
    safe_case_id = case_id.replace('-', '_').replace(' ', '_').replace('/', '_').replace('\\', '_')
    return os.path.join(data_dir, f"{safe_case_id}.json")


def load_case(case_id: str, user_id: str) -> Optional[Dict]:
    """Load case from file, ensuring user ownership."""
    file_path = get_case_file(case_id, user_id)
    if os.path.exists(file_path):
        with open(file_path, 'r') as f:
            case = json.load(f)
            # Verify user ownership (defense in depth)
            if case.get("user_id") and case.get("user_id") != user_id:
                logger.warning(f"User {user_id} attempted to access case owned by {case.get('user_id')}")
                return None
            return case
    return None


def save_case(case_id: str, case_data: Dict, user_id: str):
    """Save case to file in user's directory."""
    # Ensure user_id is set in case data
    case_data["user_id"] = user_id
    case_data["updated_at"] = datetime.now().isoformat()
    
    file_path = get_case_file(case_id, user_id)
    with open(file_path, 'w') as f:
        json.dump(case_data, f, indent=2, default=str)


def verify_case_ownership(case_id: str, user_id: str) -> bool:
    """Verify that a case belongs to a specific user."""
    file_path = get_case_file(case_id, user_id)
    if not os.path.exists(file_path):
        return False
    
    with open(file_path, 'r') as f:
        case = json.load(f)
        # Case is owned if user_id matches or user_id not set (legacy)
        stored_user_id = case.get("user_id")
        if stored_user_id and stored_user_id != user_id:
            return False
    return True


# =============================================================================
# TEMPLATE DATA - MINNESOTA LAW
# =============================================================================

MN_DEFENSES = {
    "improper_notice": {
        "title": "Improper Notice",
        "legal_basis": "Minn. Stat. § 504B.135",
        "description": "The eviction notice was defective or not properly served",
        "elements": [
            "Notice was not served properly (in person, posted, or mailed)",
            "Notice period was too short (14 days for non-payment, varies for other causes)",
            "Notice lacked required information",
            "Wrong type of notice used"
        ]
    },
    "retaliation": {
        "title": "Retaliatory Eviction",
        "legal_basis": "Minn. Stat. § 504B.441",
        "description": "Eviction is retaliation for exercising legal rights",
        "elements": [
            "You engaged in protected activity (complained to inspector, requested repairs, etc.)",
            "Eviction was filed within 90 days of protected activity",
            "Landlord knew about your protected activity"
        ]
    },
    "habitability": {
        "title": "Breach of Habitability",
        "legal_basis": "Minn. Stat. § 504B.161",
        "description": "Landlord failed to maintain habitable conditions",
        "elements": [
            "Serious defects exist affecting health/safety",
            "You notified landlord of defects (or defects were obvious)",
            "Landlord failed to repair within reasonable time",
            "Defects not caused by you"
        ]
    },
    "discrimination": {
        "title": "Discriminatory Eviction",
        "legal_basis": "Minn. Stat. § 363A.09, Fair Housing Act",
        "description": "Eviction based on protected class status",
        "elements": [
            "You are member of protected class",
            "Eviction is based on protected status",
            "Similarly situated non-protected tenants treated differently"
        ]
    },
    "waiver": {
        "title": "Waiver",
        "legal_basis": "Contract Law",
        "description": "Landlord waived right to evict by accepting rent or delay",
        "elements": [
            "Landlord accepted rent after breach",
            "Landlord knew of breach when accepting rent",
            "Landlord's conduct indicated waiver"
        ]
    },
    "landlord_breach": {
        "title": "Landlord Breach of Lease",
        "legal_basis": "Contract Law",
        "description": "Landlord breached lease first, excusing your performance",
        "elements": [
            "Landlord had obligation under lease",
            "Landlord failed to perform obligation",
            "Failure was material breach"
        ]
    }
}

MN_COUNTERCLAIMS = {
    "breach_of_habitability": {
        "title": "Breach of Warranty of Habitability",
        "legal_basis": "Minn. Stat. § 504B.161",
        "description": "Landlord failed to maintain habitable conditions",
        "elements": [
            "Landlord knew or should have known of defect",
            "Defect substantially affected habitability",
            "Tenant notified landlord or defect was obvious",
            "Reasonable time to repair passed",
            "Defect not caused by tenant"
        ],
        "damages": [
            "Rent reduction/abatement for diminished value",
            "Repair costs if tenant fixed problem",
            "Moving costs if forced to relocate",
            "Property damage",
            "Medical expenses if health affected"
        ]
    },
    "breach_of_quiet_enjoyment": {
        "title": "Breach of Covenant of Quiet Enjoyment",
        "legal_basis": "Minn. Stat. § 504B.375",
        "description": "Landlord substantially interfered with your use of premises",
        "elements": [
            "Landlord's actions substantially interfered with use",
            "Interference was material and ongoing",
            "You did not cause the interference"
        ],
        "damages": [
            "Rent abatement",
            "Emotional distress",
            "Consequential damages"
        ]
    },
    "negligent_maintenance": {
        "title": "Negligent Maintenance",
        "legal_basis": "Common Law Negligence",
        "description": "Landlord's negligence caused injury or damage",
        "elements": [
            "Landlord owed duty of care",
            "Landlord breached that duty",
            "Breach caused injury/damage",
            "Actual damages resulted"
        ],
        "damages": [
            "Property damage",
            "Personal injury costs",
            "Medical expenses",
            "Lost wages"
        ]
    },
    "fraud": {
        "title": "Fraud/Misrepresentation",
        "legal_basis": "Common Law Fraud, Minn. Stat. § 325F.69",
        "description": "Landlord made false statements you relied on",
        "elements": [
            "Landlord made false statement of material fact",
            "Landlord knew it was false (or was reckless)",
            "Landlord intended you to rely on it",
            "You actually relied on it",
            "You suffered damages"
        ],
        "damages": [
            "Out of pocket losses",
            "Benefit of bargain damages",
            "Punitive damages (possible)"
        ]
    },
    "harassment": {
        "title": "Tenant Harassment",
        "legal_basis": "Minn. Stat. § 504B.395",
        "description": "Landlord engaged in harassment to force you out",
        "elements": [
            "Landlord engaged in harassing conduct",
            "Conduct was intentional",
            "Conduct was designed to interfere with tenancy"
        ],
        "damages": [
            "Statutory damages",
            "Actual damages",
            "Attorney fees"
        ]
    },
    "illegal_lockout": {
        "title": "Illegal Lockout/Self-Help Eviction",
        "legal_basis": "Minn. Stat. § 504B.375",
        "description": "Landlord attempted to evict without court process",
        "elements": [
            "Landlord changed locks, removed belongings, or cut utilities",
            "Done without court order",
            "Intent to exclude tenant"
        ],
        "damages": [
            "Up to $500 statutory penalty",
            "Actual damages",
            "Hotel/moving costs",
            "Lost property value"
        ]
    },
    "security_deposit": {
        "title": "Security Deposit Violations",
        "legal_basis": "Minn. Stat. § 504B.178",
        "description": "Landlord improperly withheld security deposit",
        "elements": [
            "You paid security deposit",
            "Tenancy ended",
            "Landlord failed to return within 21 days",
            "Or landlord made improper deductions"
        ],
        "damages": [
            "Return of wrongfully withheld deposit",
            "Bad faith penalty (up to $500)",
            "Interest on deposit"
        ]
    }
}

MOTION_TEMPLATES = {
    "motion_to_compel": {
        "title": "Motion to Compel Discovery",
        "description": "Force opposing party to provide requested documents or information",
        "when_to_use": [
            "Landlord refuses to provide documents you requested",
            "Landlord ignores discovery requests",
            "Need video/security footage before it's deleted",
            "Need financial records or communications"
        ],
        "legal_basis": [
            "Minn. R. Civ. P. 37.01 - Motion to Compel Discovery",
            "Minn. R. Civ. P. 34 - Production of Documents",
            "Minn. R. Civ. P. 33 - Interrogatories"
        ],
        "template": """STATE OF MINNESOTA                          DISTRICT COURT
COUNTY OF {county}                          {judicial_district} JUDICIAL DISTRICT

{plaintiff_name},
    Plaintiff,                              Case No. {case_number}

vs.                                         MOTION TO COMPEL DISCOVERY

{defendant_name},
    Defendant.

TO: THE ABOVE-NAMED COURT AND PLAINTIFF:

    Defendant {defendant_name}, appearing pro se, respectfully moves this Court for an 
order compelling Plaintiff to respond to Defendant's discovery requests, specifically:

    1. {discovery_requests}

GROUNDS:

    This motion is made pursuant to Minnesota Rules of Civil Procedure 37.01 on the 
following grounds:

    1. On {request_date}, Defendant served discovery requests on Plaintiff.
    2. Plaintiff's responses were due by {due_date}.
    3. As of this date, Plaintiff has failed to {failure_description}.
    4. The requested information is relevant to Defendant's defenses and counterclaims.
    5. Defendant requires this information to prepare for the hearing scheduled on {hearing_date}.

RELIEF SOUGHT:

    Defendant respectfully requests that this Court:
    1. Order Plaintiff to fully respond to Defendant's discovery requests within 10 days;
    2. Award Defendant costs and expenses incurred in bringing this motion;
    3. Grant such other relief as the Court deems just.

Dated: {today_date}

                                            _______________________________
                                            {defendant_name}
                                            {defendant_address}
                                            {defendant_phone}
                                            Defendant, Pro Se"""
    },
    "motion_to_dismiss": {
        "title": "Motion to Dismiss",
        "description": "Request dismissal due to legal defects",
        "when_to_use": [
            "Notice was defective (wrong dates, wrong method)",
            "Complaint was not properly served",
            "Complaint fails to state a valid claim",
            "Wrong party named as landlord"
        ],
        "legal_basis": [
            "Minn. R. Civ. P. 12.02 - Defenses and Objections",
            "Minn. Stat. § 504B.135 - Notice Requirements",
            "Minn. Stat. § 504B.321 - Service Requirements"
        ],
        "template": """STATE OF MINNESOTA                          DISTRICT COURT
COUNTY OF {county}                          {judicial_district} JUDICIAL DISTRICT

{plaintiff_name},
    Plaintiff,                              Case No. {case_number}

vs.                                         MOTION TO DISMISS

{defendant_name},
    Defendant.

    Defendant {defendant_name} moves this Court for an order dismissing this action 
pursuant to Minnesota Rule of Civil Procedure 12.02 on the following grounds:

    {grounds}

MEMORANDUM OF LAW:

    {legal_argument}

CONCLUSION:

    For the foregoing reasons, Defendant respectfully requests that this Court dismiss 
Plaintiff's Complaint with prejudice.

Dated: {today_date}

                                            _______________________________
                                            {defendant_name}, Pro Se"""
    },
    "motion_for_continuance": {
        "title": "Motion for Continuance",
        "description": "Request postponement of hearing",
        "when_to_use": [
            "Need more time to gather evidence",
            "Waiting for discovery responses",
            "Scheduling conflict",
            "Need time to find legal assistance"
        ],
        "legal_basis": [
            "Minn. R. Civ. P. 6.02 - Enlargement of Time",
            "Court's inherent scheduling authority"
        ],
        "template": """STATE OF MINNESOTA                          DISTRICT COURT
COUNTY OF {county}                          {judicial_district} JUDICIAL DISTRICT

{plaintiff_name},
    Plaintiff,                              Case No. {case_number}

vs.                                         MOTION FOR CONTINUANCE

{defendant_name},
    Defendant.

    Defendant {defendant_name} respectfully moves this Court for a continuance of the 
hearing currently scheduled for {current_hearing_date}.

GROUNDS:

    1. {reason_for_continuance}
    
    2. This is Defendant's {number} request for continuance.
    
    3. A continuance will not prejudice the Plaintiff.
    
    4. Good cause exists for granting this motion.

PROPOSED NEW DATE:

    Defendant requests the hearing be rescheduled to on or after {proposed_date}.

Dated: {today_date}

                                            _______________________________
                                            {defendant_name}, Pro Se"""
    }
}


# =============================================================================
# API ENDPOINTS
# =============================================================================

@router.get("/")
async def case_builder_info():
    """Get Case Builder module information."""
    return {
        "module": "case_builder",
        "version": "1.0.0",
        "description": "Build and manage eviction defense cases and counter-suits",
        "features": [
            "Case creation and management",
            "Timeline tracking",
            "Evidence organization",
            "Counterclaim builder",
            "Motion generator",
            "Deadline reminders",
            "Document generation"
        ]
    }


# -----------------------------------------------------------------------------
# Cases
# -----------------------------------------------------------------------------

@router.get("/cases")
async def list_cases(user: StorageUser = Depends(require_user)):
    """List all cases for the authenticated user with computed status and progress."""
    user_id = user.user_id
    data_dir = get_user_case_data_dir(user_id)
    cases = []
    
    # Only list cases from user's directory
    if not os.path.exists(data_dir):
        return {"cases": [], "count": 0}
    
    for filename in os.listdir(data_dir):
        if filename.endswith('.json'):
            file_path = os.path.join(data_dir, filename)
            try:
                with open(file_path, 'r') as f:
                    case = json.load(f)
                
                # Double-check user ownership (defense in depth)
                if case.get("user_id") and case.get("user_id") != user_id:
                    logger.warning(f"Skipping case with mismatched user_id in {filename}")
                    continue
                
                # Compute case status based on data
                status = case.get("status", "draft")
                if not status:
                    # Auto-determine status
                    has_answer = any(m.get("motion_type") == "answer" for m in case.get("motions", []))
                    has_hearing = bool(case.get("hearing_date"))
                    if has_answer:
                        status = "filed"
                    elif has_hearing:
                        status = "active"
                    else:
                        status = "draft"
                
                # Compute progress
                progress = 0
                if case.get("case_number"):
                    progress += 10
                if case.get("property_address"):
                    progress += 10
                if case.get("plaintiff", {}).get("name"):
                    progress += 10
                if len(case.get("timeline", [])) > 0:
                    progress += 15
                if len(case.get("evidence", [])) > 0:
                    progress += 20
                if len(case.get("defenses", [])) > 0:
                    progress += 15
                if len(case.get("motions", [])) > 0:
                    progress += 20
                progress = min(progress, 100)
                
                # Find next deadline
                deadlines = case.get("deadlines", [])
                next_deadline = None
                next_deadline_task = None
                urgent = False
                
                if deadlines:
                    today = date.today()
                    upcoming = sorted([
                        d for d in deadlines 
                        if d.get("deadline") and datetime.fromisoformat(d["deadline"]).date() >= today
                    ], key=lambda x: x["deadline"])
                    
                    if upcoming:
                        next_dl = upcoming[0]
                        next_deadline = next_dl.get("deadline")
                        next_deadline_task = next_dl.get("title", "Deadline")
                        days_until = (datetime.fromisoformat(next_deadline).date() - today).days
                        urgent = days_until <= 7
                
                # If no deadline set but has hearing, use hearing as deadline
                if not next_deadline and case.get("hearing_date"):
                    next_deadline = case.get("hearing_date")
                    next_deadline_task = "Hearing"
                    try:
                        days_until = (datetime.fromisoformat(next_deadline).date() - date.today()).days
                        urgent = days_until <= 7
                    except:
                        pass
                
                # Build case ID from filename
                case_id = filename.replace('.json', '')
                
                cases.append({
                    "id": case_id,
                    "case_number": case.get("case_number"),
                    "case_type": case.get("case_type"),
                    "status": status,
                    "court": case.get("court"),
                    "property_address": case.get("property_address"),
                    "hearing_date": case.get("hearing_date"),
                    "plaintiff_name": case.get("plaintiff", {}).get("name"),
                    "defendant_name": case.get("defendant", {}).get("name"),
                    "progress": progress,
                    "next_deadline": next_deadline,
                    "next_deadline_task": next_deadline_task,
                    "urgent": urgent,
                    "defenses": [d.get("defense_type") for d in case.get("defenses", [])],
                    "evidence_count": len(case.get("evidence", [])),
                    "timeline_events": [
                        {"date": e.get("date"), "title": e.get("title")}
                        for e in (case.get("timeline", []) or [])[:5]
                    ],
                    "updated_at": case.get("updated_at")
                })
            except Exception as e:
                logger.error(f"Error loading case file {filename}: {e}")
                continue
    
    # Sort by updated_at descending
    cases.sort(key=lambda x: x.get("updated_at") or "", reverse=True)
    
    return {"cases": cases, "count": len(cases)}


@router.get("/cases/{case_id}")
async def get_case(case_id: str, user: StorageUser = Depends(require_user)):
    """Get a specific case belonging to the authenticated user."""
    user_id = user.user_id
    case = load_case(case_id, user_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    return case


@router.post("/cases")
async def create_case(case: CaseCreate, user: StorageUser = Depends(require_user)):
    """Create a new case for the authenticated user."""
    user_id = user.user_id
    
    case_data = {
        "user_id": user_id,  # Store user ownership
        "case_number": case.case_number,
        "case_type": case.case_type,
        "court": case.court,
        "property_address": case.property_address,
        "rent_amount": case.rent_amount,
        "security_deposit": case.security_deposit,
        "plaintiff": {
            "name": case.plaintiff_name,
            "role": "plaintiff"
        },
        "defendant": {
            "name": case.defendant_name,
            "role": "defendant",
            "is_pro_se": True
        },
        "hearing_date": case.hearing_date,
        "lease_start": case.lease_start,
        "lease_end": case.lease_end,
        "timeline": [],
        "evidence": [],
        "counterclaims": [],
        "motions": [],
        "deadlines": [],
        "defenses": [],
        "notes": [case.notes] if case.notes else [],
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat()
    }
    
    save_case(case.case_number, case_data, user_id)
    
    return {"success": True, "case_number": case.case_number, "case": case_data}


@router.put("/cases/{case_id}")
async def update_case(case_id: str, updates: Dict[str, Any] = Body(...), user: StorageUser = Depends(require_user)):
    """Update a case belonging to the authenticated user."""
    user_id = user.user_id
    
    # Verify ownership before loading
    if not verify_case_ownership(case_id, user_id):
        raise HTTPException(status_code=404, detail="Case not found")
    
    case = load_case(case_id, user_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    
    # Prevent user_id from being changed
    updates.pop("user_id", None)
    
    case.update(updates)
    save_case(case_id, case, user_id)
    
    return {"success": True, "case": case}


@router.delete("/cases/{case_id}")
async def delete_case(case_id: str, user: StorageUser = Depends(require_user)):
    """Delete a case belonging to the authenticated user."""
    user_id = user.user_id
    
    # Verify ownership before deletion
    if not verify_case_ownership(case_id, user_id):
        raise HTTPException(status_code=404, detail="Case not found")
    
    file_path = get_case_file(case_id, user_id)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Case not found")
    
    os.remove(file_path)
    return {"success": True, "message": f"Case {case_id} deleted"}


# -----------------------------------------------------------------------------
# Timeline Events
# -----------------------------------------------------------------------------

@router.get("/cases/{case_id}/timeline")
async def get_timeline(case_id: str, user: StorageUser = Depends(require_user)):
    """Get all timeline events for a case belonging to the authenticated user."""
    user_id = user.user_id
    case = load_case(case_id, user_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    
    timeline = case.get("timeline", [])
    # Sort by date
    timeline.sort(key=lambda x: x.get("date", ""))
    
    return {"timeline": timeline, "count": len(timeline)}


@router.post("/cases/{case_id}/timeline")
async def add_timeline_event(case_id: str, event: TimelineEventCreate, user: StorageUser = Depends(require_user)):
    """Add a timeline event to a case belonging to the authenticated user."""
    user_id = user.user_id
    case = load_case(case_id, user_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    
    event_id = f"evt_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    event_data = {
        "id": event_id,
        "date": event.date,
        "title": event.title,
        "description": event.description,
        "category": event.category,
        "importance": event.importance,
        "evidence_ids": event.evidence_ids,
        "source": event.source,
        "created_at": datetime.now().isoformat()
    }
    
    if "timeline" not in case:
        case["timeline"] = []
    case["timeline"].append(event_data)
    save_case(case_id, case, user_id)
    
    return {"success": True, "event_id": event_id, "event": event_data}


@router.delete("/cases/{case_id}/timeline/{event_id}")
async def delete_timeline_event(case_id: str, event_id: str, user: StorageUser = Depends(require_user)):
    """Delete a timeline event from a case belonging to the authenticated user."""
    user_id = user.user_id
    case = load_case(case_id, user_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    
    case["timeline"] = [e for e in case.get("timeline", []) if e.get("id") != event_id]
    save_case(case_id, case, user_id)
    
    return {"success": True}


# -----------------------------------------------------------------------------
# Evidence
# -----------------------------------------------------------------------------

@router.get("/cases/{case_id}/evidence")
async def get_evidence(case_id: str, user: StorageUser = Depends(require_user)):
    """Get all evidence for a case belonging to the authenticated user."""
    user_id = user.user_id
    case = load_case(case_id, user_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    
    return {"evidence": case.get("evidence", []), "count": len(case.get("evidence", []))}


@router.post("/cases/{case_id}/evidence")
async def add_evidence(case_id: str, evidence: EvidenceCreate, user: StorageUser = Depends(require_user)):
    """Add evidence to a case belonging to the authenticated user."""
    user_id = user.user_id
    case = load_case(case_id, user_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    
    evidence_id = f"evi_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    evidence_data = {
        "id": evidence_id,
        "title": evidence.title,
        "evidence_type": evidence.evidence_type,
        "date_obtained": evidence.date_obtained or datetime.now().strftime("%Y-%m-%d"),
        "date_of_event": evidence.date_of_event,
        "description": evidence.description,
        "source": evidence.source,
        "relevance": evidence.relevance,
        "file_path": evidence.file_path,
        "notes": evidence.notes,
        "created_at": datetime.now().isoformat()
    }
    
    if "evidence" not in case:
        case["evidence"] = []
    case["evidence"].append(evidence_data)
    save_case(case_id, case, user_id)
    
    return {"success": True, "evidence_id": evidence_id, "evidence": evidence_data}


# -----------------------------------------------------------------------------
# Counterclaims
# -----------------------------------------------------------------------------

@router.get("/cases/{case_id}/counterclaims")
async def get_counterclaims(case_id: str, user: StorageUser = Depends(require_user)):
    """Get all counterclaims for a case belonging to the authenticated user."""
    user_id = user.user_id
    case = load_case(case_id, user_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    
    return {"counterclaims": case.get("counterclaims", []), "count": len(case.get("counterclaims", []))}


@router.post("/cases/{case_id}/counterclaims")
async def add_counterclaim(case_id: str, claim: CounterclaimCreate, user: StorageUser = Depends(require_user)):
    """Add a counterclaim to a case belonging to the authenticated user."""
    user_id = user.user_id
    case = load_case(case_id, user_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    
    # Get template info
    template = MN_COUNTERCLAIMS.get(claim.claim_type, {})
    
    claim_id = f"clm_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    claim_data = {
        "id": claim_id,
        "claim_type": claim.claim_type,
        "title": claim.title,
        "legal_basis": template.get("legal_basis", ""),
        "description": template.get("description", ""),
        "elements": template.get("elements", []),
        "potential_damages": template.get("damages", []),
        "facts": claim.facts,
        "damages_sought": claim.damages_sought,
        "evidence_ids": claim.evidence_ids,
        "notes": claim.notes,
        "created_at": datetime.now().isoformat()
    }
    
    if "counterclaims" not in case:
        case["counterclaims"] = []
    case["counterclaims"].append(claim_data)
    save_case(case_id, case, user_id)
    
    return {"success": True, "claim_id": claim_id, "counterclaim": claim_data}


# -----------------------------------------------------------------------------
# Motions
# -----------------------------------------------------------------------------

@router.get("/cases/{case_id}/motions")
async def get_motions(case_id: str, user: StorageUser = Depends(require_user)):
    """Get all motions for a case belonging to the authenticated user."""
    user_id = user.user_id
    case = load_case(case_id, user_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    
    return {"motions": case.get("motions", []), "count": len(case.get("motions", []))}


@router.post("/cases/{case_id}/motions")
async def add_motion(case_id: str, motion: MotionCreate, user: StorageUser = Depends(require_user)):
    """Add a motion to a case belonging to the authenticated user."""
    user_id = user.user_id
    case = load_case(case_id, user_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    
    # Get template info
    template = MOTION_TEMPLATES.get(motion.motion_type, {})
    
    motion_id = f"mot_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    motion_data = {
        "id": motion_id,
        "motion_type": motion.motion_type,
        "title": motion.title,
        "deadline": motion.deadline,
        "basis": motion.basis,
        "relief_sought": motion.relief_sought,
        "supporting_evidence": motion.supporting_evidence,
        "legal_basis": template.get("legal_basis", []),
        "when_to_use": template.get("when_to_use", []),
        "template": template.get("template", ""),
        "status": "pending",
        "filed": False,
        "notes": motion.notes,
        "created_at": datetime.now().isoformat()
    }
    
    if "motions" not in case:
        case["motions"] = []
    case["motions"].append(motion_data)
    save_case(case_id, case, user_id)
    
    return {"success": True, "motion_id": motion_id, "motion": motion_data}


# -----------------------------------------------------------------------------
# Deadlines
# -----------------------------------------------------------------------------

@router.get("/cases/{case_id}/deadlines")
async def get_deadlines(case_id: str, user: StorageUser = Depends(require_user)):
    """Get all deadlines for a case belonging to the authenticated user."""
    user_id = user.user_id
    case = load_case(case_id, user_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    
    deadlines = case.get("deadlines", [])
    
    # Calculate days until each deadline
    today = date.today()
    for d in deadlines:
        if d.get("deadline"):
            try:
                deadline_date = datetime.strptime(d["deadline"], "%Y-%m-%d").date()
                d["days_until"] = (deadline_date - today).days
                if d["days_until"] < 0:
                    d["status"] = "overdue"
                elif d["days_until"] == 0:
                    d["status"] = "today"
                elif d["days_until"] <= 3:
                    d["status"] = "urgent"
                elif d["days_until"] <= 7:
                    d["status"] = "soon"
                else:
                    d["status"] = "upcoming"
            except:
                d["days_until"] = None
                d["status"] = "unknown"
    
    return {"deadlines": deadlines, "count": len(deadlines)}


@router.post("/cases/{case_id}/deadlines")
async def add_deadline(case_id: str, deadline: DeadlineCreate, user: StorageUser = Depends(require_user)):
    """Add a deadline to a case belonging to the authenticated user."""
    user_id = user.user_id
    case = load_case(case_id, user_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    
    deadline_id = f"ddl_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    deadline_data = {
        "id": deadline_id,
        "title": deadline.title,
        "deadline": deadline.deadline,
        "description": deadline.description,
        "priority": deadline.priority,
        "reminder_days": deadline.reminder_days,
        "notes": deadline.notes,
        "completed": False,
        "created_at": datetime.now().isoformat()
    }
    
    if "deadlines" not in case:
        case["deadlines"] = []
    case["deadlines"].append(deadline_data)
    save_case(case_id, case, user_id)
    
    return {"success": True, "deadline_id": deadline_id, "deadline": deadline_data}


@router.put("/cases/{case_id}/deadlines/{deadline_id}/complete")
async def complete_deadline(case_id: str, deadline_id: str, user: StorageUser = Depends(require_user)):
    """Mark a deadline as complete for a case belonging to the authenticated user."""
    user_id = user.user_id
    case = load_case(case_id, user_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    
    for d in case.get("deadlines", []):
        if d.get("id") == deadline_id:
            d["completed"] = True
            d["completed_at"] = datetime.now().isoformat()
    
    save_case(case_id, case, user_id)
    return {"success": True}


# -----------------------------------------------------------------------------
# Defenses
# -----------------------------------------------------------------------------

@router.get("/cases/{case_id}/defenses")
async def get_defenses(case_id: str, user: StorageUser = Depends(require_user)):
    """Get all defenses for a case belonging to the authenticated user."""
    user_id = user.user_id
    case = load_case(case_id, user_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    
    return {"defenses": case.get("defenses", []), "count": len(case.get("defenses", []))}


@router.post("/cases/{case_id}/defenses")
async def add_defense(case_id: str, defense: DefenseCreate, user: StorageUser = Depends(require_user)):
    """Add a defense strategy to a case belonging to the authenticated user."""
    user_id = user.user_id
    case = load_case(case_id, user_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    
    # Get template info
    template = MN_DEFENSES.get(defense.defense_type, {})
    
    defense_id = f"def_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    defense_data = {
        "id": defense_id,
        "defense_type": defense.defense_type,
        "title": defense.title,
        "legal_basis": defense.legal_basis or template.get("legal_basis", ""),
        "description": template.get("description", ""),
        "elements": template.get("elements", []),
        "facts_supporting": defense.facts_supporting,
        "evidence_ids": defense.evidence_ids,
        "strength": defense.strength,
        "created_at": datetime.now().isoformat()
    }
    
    if "defenses" not in case:
        case["defenses"] = []
    case["defenses"].append(defense_data)
    save_case(case_id, case, user_id)
    
    return {"success": True, "defense_id": defense_id, "defense": defense_data}


# -----------------------------------------------------------------------------
# Templates & Reference
# -----------------------------------------------------------------------------

@router.get("/templates/defenses")
async def get_defense_templates():
    """Get all available defense templates."""
    return {"defenses": MN_DEFENSES}


@router.get("/templates/counterclaims")
async def get_counterclaim_templates():
    """Get all available counterclaim templates."""
    return {"counterclaims": MN_COUNTERCLAIMS}


@router.get("/templates/motions")
async def get_motion_templates():
    """Get all available motion templates."""
    return {"motions": MOTION_TEMPLATES}


# -----------------------------------------------------------------------------
# Document Generation
# -----------------------------------------------------------------------------

@router.post("/cases/{case_id}/generate/counterclaim")
async def generate_counterclaim_doc(case_id: str, user: StorageUser = Depends(require_user)):
    """Generate the counterclaim document for a case belonging to the authenticated user."""
    user_id = user.user_id
    case = load_case(case_id, user_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    
    # Build the document
    doc_lines = []
    doc_lines.append("STATE OF MINNESOTA                          DISTRICT COURT")
    doc_lines.append(f"COUNTY OF DAKOTA                           FIRST JUDICIAL DISTRICT")
    doc_lines.append("")
    doc_lines.append(f"{case.get('plaintiff', {}).get('name', 'PLAINTIFF')},")
    doc_lines.append(f"    Plaintiff,                              Case No. {case.get('case_number', '')}")
    doc_lines.append("")
    doc_lines.append("vs.                                         AMENDED ANSWER AND COUNTERCLAIM")
    doc_lines.append("")
    doc_lines.append(f"{case.get('defendant', {}).get('name', 'DEFENDANT')},")
    doc_lines.append("    Defendant.")
    doc_lines.append("")
    doc_lines.append("=" * 70)
    doc_lines.append("")
    
    # Defenses section
    defenses = case.get("defenses", [])
    if defenses:
        doc_lines.append("AFFIRMATIVE DEFENSES")
        doc_lines.append("-" * 30)
        for i, defense in enumerate(defenses, 1):
            doc_lines.append(f"\n{i}. {defense.get('title', 'Defense')}")
            doc_lines.append(f"   Legal Basis: {defense.get('legal_basis', '')}")
            for fact in defense.get("facts_supporting", []):
                doc_lines.append(f"   - {fact}")
    
    # Counterclaims section
    counterclaims = case.get("counterclaims", [])
    if counterclaims:
        doc_lines.append("")
        doc_lines.append("=" * 70)
        doc_lines.append("COUNTERCLAIMS")
        doc_lines.append("=" * 70)
        
        for i, claim in enumerate(counterclaims, 1):
            doc_lines.append(f"\nCOUNT {i}: {claim.get('title', 'Counterclaim')}")
            doc_lines.append("-" * 30)
            doc_lines.append(f"Legal Basis: {claim.get('legal_basis', '')}")
            doc_lines.append("")
            doc_lines.append("Facts:")
            for fact in claim.get("facts", []):
                doc_lines.append(f"  - {fact}")
            
            damages = claim.get("damages_sought", {})
            if damages:
                doc_lines.append("")
                doc_lines.append("Damages Sought:")
                for damage_type, amount in damages.items():
                    doc_lines.append(f"  - {damage_type}: ${amount:,.2f}")
    
    # Prayer for relief
    doc_lines.append("")
    doc_lines.append("=" * 70)
    doc_lines.append("PRAYER FOR RELIEF")
    doc_lines.append("=" * 70)
    doc_lines.append("")
    doc_lines.append("WHEREFORE, Defendant respectfully requests that this Court:")
    doc_lines.append("1. Deny Plaintiff's complaint for eviction;")
    doc_lines.append("2. Enter judgment in Defendant's favor on all counterclaims;")
    doc_lines.append("3. Award Defendant actual damages as proven at trial;")
    doc_lines.append("4. Award Defendant statutory penalties as applicable;")
    doc_lines.append("5. Award costs and disbursements;")
    doc_lines.append("6. Grant such other relief as the Court deems just and equitable.")
    doc_lines.append("")
    doc_lines.append("")
    doc_lines.append(f"Dated: {datetime.now().strftime('%B %d, %Y')}")
    doc_lines.append("")
    doc_lines.append("")
    doc_lines.append("_______________________________")
    doc_lines.append(case.get("defendant", {}).get("name", "Defendant"))
    doc_lines.append("Defendant, Pro Se")
    
    document_text = "\n".join(doc_lines)
    
    # Save to file
    output_dir = os.path.join(os.getcwd(), "data", "case_outputs")
    os.makedirs(output_dir, exist_ok=True)
    output_file = os.path.join(output_dir, f"COUNTERCLAIM_{case.get('case_number', 'case').replace('-', '_')}.txt")
    
    with open(output_file, 'w') as f:
        f.write(document_text)
    
    return {
        "success": True,
        "document": document_text,
        "file_path": output_file
    }


@router.post("/cases/{case_id}/generate/motion/{motion_type}")
async def generate_motion_doc(case_id: str, motion_type: str, params: Dict[str, Any] = Body(default={}), user: StorageUser = Depends(require_user)):
    """Generate a motion document for a case belonging to the authenticated user."""
    user_id = user.user_id
    case = load_case(case_id, user_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    
    template = MOTION_TEMPLATES.get(motion_type)
    if not template:
        raise HTTPException(status_code=404, detail="Motion template not found")
    
    # Fill in template
    doc_text = template.get("template", "")
    
    replacements = {
        "{county}": "DAKOTA",
        "{judicial_district}": "FIRST",
        "{plaintiff_name}": case.get("plaintiff", {}).get("name", "PLAINTIFF"),
        "{defendant_name}": case.get("defendant", {}).get("name", "DEFENDANT"),
        "{case_number}": case.get("case_number", ""),
        "{defendant_address}": case.get("property_address", ""),
        "{defendant_phone}": "",
        "{today_date}": datetime.now().strftime("%B %d, %Y"),
        "{hearing_date}": case.get("hearing_date", ""),
        "{current_hearing_date}": case.get("hearing_date", ""),
    }
    
    # Add any custom params
    for key, value in params.items():
        replacements[f"{{{key}}}"] = str(value)
    
    for placeholder, value in replacements.items():
        doc_text = doc_text.replace(placeholder, value)
    
    # Save to file
    output_dir = os.path.join(os.getcwd(), "data", "case_outputs")
    os.makedirs(output_dir, exist_ok=True)
    output_file = os.path.join(output_dir, f"{motion_type.upper()}_{case.get('case_number', 'case').replace('-', '_')}.txt")
    
    with open(output_file, 'w') as f:
        f.write(doc_text)
    
    return {
        "success": True,
        "document": doc_text,
        "file_path": output_file,
        "motion_type": motion_type,
        "title": template.get("title")
    }


# -----------------------------------------------------------------------------
# Case Summary
# -----------------------------------------------------------------------------

@router.get("/cases/{case_id}/summary")
async def get_case_summary(case_id: str, user: StorageUser = Depends(require_user)):
    """Get a complete case summary with reminders for the authenticated user."""
    user_id = user.user_id
    case = load_case(case_id, user_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    
    today = date.today()
    
    # Calculate hearing days
    hearing_days = None
    if case.get("hearing_date"):
        try:
            hearing_date = datetime.strptime(case["hearing_date"], "%Y-%m-%d").date()
            hearing_days = (hearing_date - today).days
        except:
            pass
    
    # Get urgent deadlines
    urgent_deadlines = []
    for d in case.get("deadlines", []):
        if d.get("deadline") and not d.get("completed"):
            try:
                deadline_date = datetime.strptime(d["deadline"], "%Y-%m-%d").date()
                days = (deadline_date - today).days
                if days <= 7:
                    urgent_deadlines.append({
                        **d,
                        "days_until": days
                    })
            except:
                pass
    
    # Build reminders
    reminders = []
    
    if hearing_days is not None:
        if hearing_days <= 0:
            reminders.append({
                "type": "critical",
                "title": "HEARING TODAY!" if hearing_days == 0 else "HEARING PASSED",
                "message": f"Your hearing {'is today' if hearing_days == 0 else 'was ' + str(abs(hearing_days)) + ' days ago'}!"
            })
        elif hearing_days <= 3:
            reminders.append({
                "type": "critical",
                "title": f"Hearing in {hearing_days} days!",
                "message": f"Your court hearing is on {case.get('hearing_date')}. Make sure all documents are prepared."
            })
        elif hearing_days <= 7:
            reminders.append({
                "type": "high",
                "title": f"Hearing in {hearing_days} days",
                "message": "Review your evidence and practice your arguments."
            })
    
    for d in urgent_deadlines:
        reminders.append({
            "type": "high" if d["days_until"] > 3 else "critical",
            "title": f"Deadline: {d.get('title', 'Unknown')}",
            "message": f"Due in {d['days_until']} days on {d.get('deadline')}"
        })
    
    # Next steps
    next_steps = []
    
    if not case.get("defenses"):
        next_steps.append("Add your defense strategies")
    if not case.get("counterclaims"):
        next_steps.append("Consider adding counterclaims against landlord")
    if not case.get("evidence"):
        next_steps.append("Upload and organize your evidence")
    if not case.get("timeline"):
        next_steps.append("Build your case timeline with key events")
    
    if hearing_days and hearing_days <= 14:
        next_steps.append("Prepare copies of all documents for court (3 copies: you, judge, landlord)")
        next_steps.append("Organize evidence in chronological order")
        next_steps.append("Practice your opening statement")
    
    return {
        "case_number": case.get("case_number"),
        "hearing_date": case.get("hearing_date"),
        "days_until_hearing": hearing_days,
        "stats": {
            "timeline_events": len(case.get("timeline", [])),
            "evidence_items": len(case.get("evidence", [])),
            "counterclaims": len(case.get("counterclaims", [])),
            "motions": len(case.get("motions", [])),
            "defenses": len(case.get("defenses", [])),
            "pending_deadlines": len([d for d in case.get("deadlines", []) if not d.get("completed")])
        },
        "reminders": reminders,
        "urgent_deadlines": urgent_deadlines,
        "next_steps": next_steps
    }
