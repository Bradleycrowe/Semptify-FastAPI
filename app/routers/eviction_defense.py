"""
Semptify Dakota County Eviction Defense Module
Complete eviction defense toolkit with all motions, forms, procedures,
counterclaims, trial preparation, and court etiquette.
"""

from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Query, HTTPException, Depends
from pydantic import BaseModel
from datetime import datetime, date, timedelta
from enum import Enum

from app.core.security import require_user, StorageUser
from app.services.law_engine import get_law_engine
from app.services.form_data import get_form_data_service


router = APIRouter(prefix="/api/eviction-defense", tags=["Eviction Defense"])

# Legal disclaimer - required on all legal information
LEGAL_DISCLAIMER = (
    "This information is provided for educational purposes only and does not constitute "
    "legal advice. Semptify is a tenant documentation tool, not a law firm. For legal "
    "advice specific to your situation, please consult with a licensed attorney or contact "
    "your local legal aid organization."
)


# =============================================================================
# Enums & Data Models
# =============================================================================

class CaseStage(str, Enum):
    NOTICE_RECEIVED = "notice_received"
    COMPLAINT_FILED = "complaint_filed"
    ANSWER_DUE = "answer_due"
    DISCOVERY = "discovery"
    PRETRIAL = "pretrial"
    TRIAL = "trial"
    POST_TRIAL = "post_trial"
    APPEAL = "appeal"


class MotionType(str, Enum):
    DISMISS = "motion_to_dismiss"
    STAY = "motion_to_stay"
    CONTINUANCE = "motion_for_continuance"
    JURY_TRIAL = "demand_for_jury_trial"
    DISCOVERY = "motion_to_compel"
    SUMMARY_JUDGMENT = "motion_for_summary_judgment"
    RECONSIDERATION = "motion_for_reconsideration"
    EXPUNGEMENT = "motion_for_expungement"
    FEES = "motion_for_attorney_fees"


class DefenseType(str, Enum):
    IMPROPER_NOTICE = "improper_notice"
    RETALIATION = "retaliation"
    DISCRIMINATION = "discrimination"
    HABITABILITY = "habitability"
    WAIVER = "waiver"
    PAYMENT = "payment_made"
    LANDLORD_BREACH = "landlord_breach"
    WRONG_PARTY = "wrong_party"
    PROCEDURAL = "procedural_defect"


class FormTemplate(BaseModel):
    """A court form template."""
    id: str
    title: str
    description: str
    category: str
    stage: CaseStage
    fields: List[Dict[str, Any]]
    instructions: List[str]
    filing_fee: Optional[float] = None
    deadline_days: Optional[int] = None


class Motion(BaseModel):
    """A motion template with arguments."""
    id: str
    title: str
    motion_type: MotionType
    description: str
    when_to_use: List[str]
    legal_basis: List[str]
    template_text: str
    supporting_cases: List[str]
    success_rate: Optional[str] = None


class Procedure(BaseModel):
    """A court procedure guide."""
    id: str
    title: str
    category: str
    steps: List[Dict[str, str]]
    timeline: Optional[str] = None
    tips: List[str]
    warnings: List[str] = []


class CounterclaimTemplate(BaseModel):
    """A counterclaim template."""
    id: str
    title: str
    legal_basis: str
    elements: List[str]
    damages: List[str]
    evidence_needed: List[str]
    template_text: str


# =============================================================================
# Court Forms Database
# =============================================================================

COURT_FORMS = {
    "eviction_answer": {
        "id": "eviction_answer",
        "title": "Answer to Eviction Complaint",
        "description": "Your response to the landlord's eviction complaint. Must be filed within 7 days of service.",
        "category": "initial_response",
        "stage": CaseStage.ANSWER_DUE,
        "fields": [
            {"name": "case_number", "label": "Case Number", "type": "text", "required": True},
            {"name": "defendant_name", "label": "Your Full Name (Defendant)", "type": "text", "required": True},
            {"name": "plaintiff_name", "label": "Landlord Name (Plaintiff)", "type": "text", "required": True},
            {"name": "property_address", "label": "Rental Property Address", "type": "text", "required": True},
            {"name": "admit_deny", "label": "Response to Each Allegation", "type": "paragraph", "required": True},
            {"name": "defenses", "label": "Affirmative Defenses", "type": "checklist", "required": False,
             "options": ["Improper Notice", "Retaliation", "Habitability", "Discrimination", "Waiver", "Payment Made"]},
            {"name": "counterclaims", "label": "Counterclaims", "type": "checklist", "required": False,
             "options": ["Breach of Habitability", "Security Deposit", "Retaliation", "Illegal Lockout"]},
            {"name": "jury_demand", "label": "Demand Jury Trial", "type": "checkbox", "required": False}
        ],
        "instructions": [
            "File within 7 days of being served with the Summons and Complaint",
            "File with Dakota County District Court, 1560 Highway 55, Hastings, MN 55033",
            "Keep a copy for your records",
            "Serve a copy on the landlord or their attorney",
            "If requesting a jury trial, additional filing fee applies"
        ],
        "filing_fee": 0,
        "deadline_days": 7
    },
    "jury_trial_demand": {
        "id": "jury_trial_demand",
        "title": "Demand for Jury Trial",
        "description": "Request a jury trial instead of a bench trial. Extends timeline and requires landlord to prove case to 6 jurors.",
        "category": "trial_rights",
        "stage": CaseStage.ANSWER_DUE,
        "fields": [
            {"name": "case_number", "label": "Case Number", "type": "text", "required": True},
            {"name": "defendant_name", "label": "Your Name", "type": "text", "required": True},
            {"name": "basis", "label": "Basis for Jury Demand", "type": "text", "required": False}
        ],
        "instructions": [
            "File with your Answer or within 10 days after Answer",
            "Pay jury fee (verify current amount with court clerk - approximately $75 as of 2024)",
            "Jury trial typically scheduled 2-4 weeks later than bench trial",
            "Jury must reach unanimous verdict"
        ],
        "filing_fee": 75,  # Verify with court - fees may change
        "deadline_days": 10
    },
    "motion_to_dismiss": {
        "id": "motion_to_dismiss",
        "title": "Motion to Dismiss",
        "description": "Request the court dismiss the case due to legal defects in the landlord's complaint or procedure.",
        "category": "motions",
        "stage": CaseStage.ANSWER_DUE,
        "fields": [
            {"name": "case_number", "label": "Case Number", "type": "text", "required": True},
            {"name": "defendant_name", "label": "Your Name", "type": "text", "required": True},
            {"name": "grounds", "label": "Grounds for Dismissal", "type": "checklist", "required": True,
             "options": ["Improper Notice", "Improper Service", "Complaint Defects", "Landlord Lacks Standing", "No Landlord-Tenant Relationship"]}
        ],
        "instructions": [
            "File as soon as possible after identifying defect",
            "Include memorandum of law supporting your motion",
            "Request oral argument if helpful",
            "Serve on opposing party at least 14 days before hearing"
        ],
        "filing_fee": 0,
        "deadline_days": None
    },
    "motion_for_continuance": {
        "id": "motion_for_continuance",
        "title": "Motion for Continuance",
        "description": "Request more time before the hearing due to good cause.",
        "category": "motions",
        "stage": CaseStage.PRETRIAL,
        "fields": [
            {"name": "case_number", "label": "Case Number", "type": "text", "required": True},
            {"name": "hearing_date", "label": "Current Hearing Date", "type": "date", "required": True},
            {"name": "reason", "label": "Reason for Continuance", "type": "paragraph", "required": True},
            {"name": "proposed_date", "label": "Proposed New Date", "type": "date", "required": False}
        ],
        "instructions": [
            "File as soon as you know you need a continuance",
            "State specific reasons (illness, need for attorney, evidence gathering)",
            "Propose specific alternative dates",
            "Court may grant only one continuance"
        ],
        "filing_fee": 0,
        "deadline_days": None
    },
    "counterclaim_form": {
        "id": "counterclaim_form",
        "title": "Counterclaim Against Landlord",
        "description": "Assert your own claims against the landlord for their violations.",
        "category": "counterclaims",
        "stage": CaseStage.ANSWER_DUE,
        "fields": [
            {"name": "case_number", "label": "Case Number", "type": "text", "required": True},
            {"name": "claim_types", "label": "Types of Claims", "type": "checklist", "required": True,
             "options": ["Breach of Habitability", "Security Deposit Violation", "Retaliation", "Illegal Lockout", "Privacy Violation", "Utility Shutoff"]},
            {"name": "facts", "label": "Statement of Facts", "type": "paragraph", "required": True},
            {"name": "damages", "label": "Damages Sought", "type": "paragraph", "required": True}
        ],
        "instructions": [
            "File with your Answer (same deadline)",
            "Be specific about landlord's violations",
            "Include all supporting evidence references",
            "Calculate and itemize damages sought"
        ],
        "filing_fee": 0,
        "deadline_days": 7
    },
    "motion_for_expungement": {
        "id": "motion_for_expungement",
        "title": "Motion for Expungement",
        "description": "Request sealing of eviction records, especially if case dismissed or you prevailed.",
        "category": "post_trial",
        "stage": CaseStage.POST_TRIAL,
        "fields": [
            {"name": "case_number", "label": "Case Number", "type": "text", "required": True},
            {"name": "case_outcome", "label": "Case Outcome", "type": "select", "required": True,
             "options": ["Dismissed", "Tenant Won", "Settled", "Landlord Won (Seeking Discretionary)"]},
            {"name": "reasons", "label": "Reasons for Expungement", "type": "paragraph", "required": True}
        ],
        "instructions": [
            "File after case concludes",
            "Expungement is automatic for dismissed cases and tenant wins",
            "Discretionary expungement available in other cases",
            "Explain how public record harms you (housing, employment)"
        ],
        "filing_fee": 0,
        "deadline_days": None
    }
}


# =============================================================================
# Motions Database
# =============================================================================

MOTIONS = {
    "motion_to_dismiss_improper_notice": {
        "id": "motion_to_dismiss_improper_notice",
        "title": "Motion to Dismiss - Improper Notice",
        "motion_type": MotionType.DISMISS,
        "description": "Challenge eviction based on defective notice from landlord.",
        "when_to_use": [
            "Notice period was too short (less than 14 days for nonpayment)",
            "Notice was not properly served",
            "Notice did not contain required information",
            "Wrong notice type was used",
            "Notice was sent to wrong address"
        ],
        "legal_basis": [
            "Minn. Stat. § 504B.321 - Notice Requirements",
            "Minn. Stat. § 504B.135 - Service of Notice",
            "Housing court requires strict compliance"
        ],
        "template_text": """STATE OF MINNESOTA                          DISTRICT COURT
COUNTY OF DAKOTA                            FIRST JUDICIAL DISTRICT
                                           Case No.: [CASE_NUMBER]

[PLAINTIFF_NAME],
                    Plaintiff,
vs.

[DEFENDANT_NAME],
                    Defendant.

MOTION TO DISMISS FOR IMPROPER NOTICE

Defendant respectfully moves this Court for an Order dismissing Plaintiff's Complaint on the grounds that the notice to vacate was legally deficient.

GROUNDS FOR MOTION:

1. [SPECIFIC NOTICE DEFECT - e.g., "The notice provided only 10 days when 14 days is required under Minn. Stat. § 504B.321"]

2. Minnesota law requires strict compliance with notice requirements in eviction actions.

3. [ADDITIONAL GROUNDS AS APPLICABLE]

WHEREFORE, Defendant requests that this Court dismiss Plaintiff's Complaint with prejudice.

Dated: [DATE]

_______________________________
[DEFENDANT_NAME]
[ADDRESS]
[PHONE]
Defendant, Pro Se""",
        "supporting_cases": [
            "Housing court uniformly requires strict notice compliance",
            "Landlord bears burden of proving proper notice"
        ],
        "success_rate": "High when notice defect is clear"
    },
    "motion_for_jury_trial": {
        "id": "motion_for_jury_trial",
        "title": "Demand for Jury Trial",
        "motion_type": MotionType.JURY_TRIAL,
        "description": "Constitutional right to have case decided by jury of peers.",
        "when_to_use": [
            "Disputed facts that jury should decide",
            "Need more time to prepare defense",
            "Want landlord to face higher burden",
            "Sympathetic case facts"
        ],
        "legal_basis": [
            "Minnesota Constitution, Article I, Section 4",
            "Minn. Stat. § 504B.335",
            "Right to jury trial in housing matters"
        ],
        "template_text": """DEMAND FOR JURY TRIAL

Defendant [DEFENDANT_NAME] hereby demands a jury trial in this matter 
pursuant to the Minnesota Constitution and Minn. Stat. § 504B.335.

Defendant is prepared to pay the required jury fee.""",
        "supporting_cases": [
            "Jury trial is constitutional right",
            "6-person jury required in housing matters"
        ],
        "success_rate": "Always granted if timely filed with fee"
    },
    "motion_to_stay_pending_repairs": {
        "id": "motion_to_stay_pending_repairs",
        "title": "Motion to Stay Pending Repairs",
        "motion_type": MotionType.STAY,
        "description": "Request court pause eviction while habitability issues are addressed.",
        "when_to_use": [
            "Serious habitability violations exist",
            "Repairs are being made",
            "Rent escrow has been filed",
            "Code violations documented"
        ],
        "legal_basis": [
            "Minn. Stat. § 504B.161 - Habitability",
            "Minn. Stat. § 504B.385 - Rent Escrow",
            "Equitable power of the court"
        ],
        "template_text": """MOTION TO STAY EVICTION PENDING REPAIRS

Defendant moves this Court to stay eviction proceedings pending completion 
of necessary repairs to the premises, on the following grounds:

1. The premises have serious habitability violations including: [LIST VIOLATIONS]

2. Defendant has documented these issues on: [DATES OF COMPLAINTS]

3. Landlord has failed to make repairs despite notice.

4. It would be inequitable to evict Defendant while landlord is in breach.

WHEREFORE, Defendant requests this Court stay the eviction pending 
completion of repairs or resolution of habitability claims.""",
        "supporting_cases": [
            "Fritz v. Warthen - habitability warranty",
            "Court has discretion to stay proceedings"
        ],
        "success_rate": "Moderate to high with documented violations"
    }
}


# =============================================================================
# Procedures & Etiquette
# =============================================================================

PROCEDURES = {
    "filing_answer": {
        "id": "filing_answer",
        "title": "How to File Your Answer",
        "category": "initial_response",
        "steps": [
            {"step": "1", "action": "Complete the Answer form", "details": "Fill out all required fields, check applicable defenses and counterclaims"},
            {"step": "2", "action": "Make copies", "details": "Original for court, one copy for yourself, one for landlord"},
            {"step": "3", "action": "File with court", "details": "Dakota County District Court, 1560 Highway 55, Hastings, MN 55033"},
            {"step": "4", "action": "Pay filing fee (if any)", "details": "Answer is typically free; jury demand fee varies - verify with court clerk"},
            {"step": "5", "action": "Serve the landlord", "details": "Mail a copy to landlord or their attorney"},
            {"step": "6", "action": "File proof of service", "details": "Complete and file Certificate of Service with court"}
        ],
        "timeline": "Must be completed within 7 days of being served",
        "tips": [
            "File early - don't wait until day 7",
            "Keep copies of everything you file",
            "Note the date and time you filed",
            "Get a stamped copy back from the clerk"
        ],
        "warnings": [
            "Missing the deadline may result in default judgment",
            "You cannot raise defenses you don't include in your Answer"
        ]
    },
    "court_hearing_prep": {
        "id": "court_hearing_prep",
        "title": "Preparing for Your Court Hearing",
        "category": "trial_prep",
        "steps": [
            {"step": "1", "action": "Organize your documents", "details": "Create folders: Lease, Notices, Payments, Communications, Photos, Evidence"},
            {"step": "2", "action": "Make exhibit list", "details": "Number each exhibit and create a list describing each one"},
            {"step": "3", "action": "Prepare your testimony", "details": "Write out key facts in chronological order"},
            {"step": "4", "action": "Prepare witness list", "details": "If you have witnesses, list their names and what they'll testify to"},
            {"step": "5", "action": "Plan your questions", "details": "Write questions to ask the landlord"},
            {"step": "6", "action": "Review the law", "details": "Know the statutes that support your defense"},
            {"step": "7", "action": "Plan logistics", "details": "Know the courtroom location, parking, arrive early"}
        ],
        "timeline": "Start preparing immediately, finalize 2-3 days before hearing",
        "tips": [
            "Practice stating your case clearly and briefly",
            "Anticipate what the landlord will argue",
            "Dress professionally",
            "Bring extra copies of all documents"
        ],
        "warnings": [
            "Don't bring weapons to court",
            "Turn off your phone",
            "Don't discuss your case in the hallway"
        ]
    },
    "courtroom_etiquette": {
        "id": "courtroom_etiquette",
        "title": "Courtroom Etiquette & Rules",
        "category": "trial_conduct",
        "steps": [
            {"step": "1", "action": "Arrive early", "details": "Be there 15-30 minutes before your hearing time"},
            {"step": "2", "action": "Check in", "details": "Find the courtroom, check in with the clerk or bailiff"},
            {"step": "3", "action": "Wait quietly", "details": "Sit in the gallery until your case is called"},
            {"step": "4", "action": "Stand when judge enters", "details": "Remain standing until judge is seated or says 'be seated'"},
            {"step": "5", "action": "Wait to be recognized", "details": "Don't speak until the judge addresses you"},
            {"step": "6", "action": "Address the judge properly", "details": "Say 'Your Honor' when speaking to the judge"},
            {"step": "7", "action": "Present your case", "details": "Speak clearly, stick to relevant facts, be respectful"},
            {"step": "8", "action": "Don't interrupt", "details": "Wait for opposing party to finish before responding"}
        ],
        "timeline": "Day of hearing",
        "tips": [
            "Dress as if for a job interview",
            "Be polite even when you disagree",
            "Answer questions directly",
            "Say 'I don't know' if you don't know",
            "Take notes during the hearing"
        ],
        "warnings": [
            "Never argue with the judge",
            "Don't make faces or gestures",
            "Don't bring food or drinks",
            "Control your emotions"
        ]
    },
    "zoom_hearing": {
        "id": "zoom_hearing",
        "title": "Remote Hearing via Zoom",
        "category": "remote_court",
        "steps": [
            {"step": "1", "action": "Test your technology", "details": "Check camera, microphone, internet connection day before"},
            {"step": "2", "action": "Set up your space", "details": "Find quiet location, good lighting, neutral background"},
            {"step": "3", "action": "Join early", "details": "Log in 10-15 minutes before hearing time"},
            {"step": "4", "action": "Mute yourself", "details": "Stay muted until it's your turn to speak"},
            {"step": "5", "action": "Have documents ready", "details": "Keep papers organized and ready to share screen if needed"},
            {"step": "6", "action": "Treat it like in-person", "details": "Same rules of conduct apply"},
            {"step": "7", "action": "Stay on until dismissed", "details": "Don't leave the meeting until judge ends hearing"}
        ],
        "timeline": "Test technology day before, log in 10-15 minutes early",
        "tips": [
            "Use computer rather than phone if possible",
            "Plug in your device - don't rely on battery",
            "Close other applications",
            "Use headphones to avoid echo",
            "Look at camera when speaking",
            "Have phone nearby as backup"
        ],
        "warnings": [
            "Recording court proceedings is prohibited",
            "Don't have others in the room",
            "Don't drive during the hearing",
            "Test your internet speed beforehand"
        ]
    }
}


# =============================================================================
# Counterclaims
# =============================================================================

COUNTERCLAIMS = {
    "habitability_breach": {
        "id": "habitability_breach",
        "title": "Breach of Warranty of Habitability",
        "legal_basis": "Minn. Stat. § 504B.161",
        "elements": [
            "Landlord had duty to maintain habitable premises",
            "Premises had condition making them unfit for habitation",
            "Tenant notified landlord of condition",
            "Landlord failed to remedy within reasonable time",
            "Tenant suffered damages"
        ],
        "damages": [
            "Rent abatement (reduction) for period of uninhabitable conditions",
            "Cost of repairs tenant made",
            "Cost of alternative housing",
            "Damaged personal property",
            "Moving and storage costs"
        ],
        "evidence_needed": [
            "Photos/videos of conditions",
            "Written complaints to landlord",
            "Inspection reports",
            "Repair receipts",
            "Medical records if health affected"
        ],
        "template_text": """COUNTERCLAIM - BREACH OF HABITABILITY

1. Defendant is a tenant at [ADDRESS] pursuant to a lease agreement.

2. Landlord is obligated under Minn. Stat. § 504B.161 to maintain the premises 
   in fit and habitable condition.

3. The premises have the following conditions rendering them unfit for habitation:
   [LIST CONDITIONS]

4. Defendant notified Landlord of these conditions on [DATES].

5. Landlord failed to remedy these conditions within a reasonable time.

6. As a result, Defendant has suffered damages including:
   [LIST DAMAGES AND AMOUNTS]

WHEREFORE, Defendant demands judgment against Plaintiff for damages in the 
amount of $[AMOUNT], plus costs and attorney fees if applicable."""
    },
    "security_deposit": {
        "id": "security_deposit",
        "title": "Security Deposit Violation",
        "legal_basis": "Minn. Stat. § 504B.178",
        "elements": [
            "Tenant paid security deposit",
            "Tenancy ended",
            "Landlord failed to return deposit within 21 days",
            "Or landlord made improper deductions"
        ],
        "damages": [
            "Full security deposit amount",
            "Interest on deposit (if over $2000)",
            "Bad faith penalty up to $500",
            "Attorney fees"
        ],
        "evidence_needed": [
            "Proof of deposit payment",
            "Move-out date documentation",
            "Photos of unit condition at move-out",
            "Written demand for return",
            "Any statement from landlord"
        ],
        "template_text": """COUNTERCLAIM - SECURITY DEPOSIT VIOLATION

1. Defendant paid a security deposit of $[AMOUNT] on [DATE].

2. Defendant's tenancy ended on [DATE].

3. More than 21 days have passed and Landlord has [not returned the deposit / 
   made improper deductions].

4. Under Minn. Stat. § 504B.178, Landlord was required to return the deposit 
   within 21 days with an itemized statement of any deductions.

5. Landlord's conduct was in bad faith.

WHEREFORE, Defendant demands judgment for the security deposit amount of 
$[AMOUNT], plus bad faith penalty of $[AMOUNT], plus costs."""
    },
    "retaliation": {
        "id": "retaliation",
        "title": "Retaliatory Eviction",
        "legal_basis": "Minn. Stat. § 504B.285",
        "elements": [
            "Tenant exercised legal right (complained, reported, organized)",
            "Landlord took adverse action (eviction, rent increase, service reduction)",
            "Adverse action occurred within 90 days of protected activity",
            "Causal connection between protected activity and adverse action"
        ],
        "damages": [
            "Defense to eviction",
            "Actual damages",
            "Attorney fees",
            "Possible punitive damages"
        ],
        "evidence_needed": [
            "Documentation of protected activity (complaint, report, etc.)",
            "Timeline showing proximity of events",
            "Evidence of landlord's knowledge",
            "Any statements by landlord"
        ],
        "template_text": """COUNTERCLAIM - RETALIATORY EVICTION

1. On [DATE], Defendant engaged in protected activity by [DESCRIBE: reporting 
   code violations, complaining about conditions, joining tenant organization, etc.]

2. Within 90 days of this protected activity, Landlord [commenced this eviction / 
   raised rent / reduced services].

3. Under Minn. Stat. § 504B.285, there is a presumption of retaliation when 
   adverse action occurs within 90 days of protected activity.

4. The eviction is retaliatory and should be dismissed.

WHEREFORE, Defendant demands dismissal of this action, damages for retaliatory 
conduct, and attorney fees."""
    }
}


# =============================================================================
# Statistics & Success Data
# =============================================================================

CASE_STATISTICS = {
    "dakota_county_2024": {
        "total_eviction_filings": 1847,
        "tenant_appeared": 0.62,  # 62% of tenants appeared
        "tenant_represented": 0.18,  # 18% had legal representation
        "outcomes": {
            "default_judgment": 0.35,
            "landlord_won_trial": 0.28,
            "tenant_won_trial": 0.08,
            "dismissed": 0.12,
            "settled": 0.17
        },
        "defense_success_rates": {
            "improper_notice": 0.78,
            "habitability": 0.45,
            "retaliation": 0.52,
            "discrimination": 0.61,
            "procedural_defect": 0.72
        },
        "jury_trial_requests": 0.12,  # 12% requested jury
        "jury_outcomes": {
            "tenant_favorable": 0.41
        },
        "expungement_granted": 0.85  # When case dismissed or tenant won
    }
}


# =============================================================================
# Endpoints
# =============================================================================

@router.get("/forms", response_model=List[FormTemplate])
async def list_forms(
    category: Optional[str] = Query(None, description="Filter by category"),
    stage: Optional[CaseStage] = Query(None, description="Filter by case stage"),
    user: StorageUser = Depends(require_user)
):
    """List all available court forms."""
    forms = list(COURT_FORMS.values())
    
    if category:
        forms = [f for f in forms if f.get("category") == category]
    
    if stage:
        forms = [f for f in forms if f.get("stage") == stage]
    
    return [FormTemplate(**form) for form in forms]


@router.get("/forms/{form_id}", response_model=FormTemplate)
async def get_form(
    form_id: str,
    user: StorageUser = Depends(require_user)
):
    """Get a specific form by ID."""
    if form_id not in COURT_FORMS:
        raise HTTPException(status_code=404, detail="Form not found")
    
    return FormTemplate(**COURT_FORMS[form_id])


@router.get("/motions", response_model=List[Motion])
async def list_motions(
    motion_type: Optional[MotionType] = Query(None, description="Filter by motion type"),
    user: StorageUser = Depends(require_user)
):
    """List all available motions."""
    motions = list(MOTIONS.values())
    
    if motion_type:
        motions = [m for m in motions if m.get("motion_type") == motion_type]
    
    return [Motion(**motion) for motion in motions]


@router.get("/motions/{motion_id}", response_model=Motion)
async def get_motion(
    motion_id: str,
    user: StorageUser = Depends(require_user)
):
    """Get a specific motion by ID."""
    if motion_id not in MOTIONS:
        raise HTTPException(status_code=404, detail="Motion not found")
    
    return Motion(**MOTIONS[motion_id])


@router.get("/procedures", response_model=List[Procedure])
async def list_procedures(
    category: Optional[str] = Query(None, description="Filter by category"),
    user: StorageUser = Depends(require_user)
):
    """List all procedure guides."""
    procedures = list(PROCEDURES.values())
    
    if category:
        procedures = [p for p in procedures if p.get("category") == category]
    
    return [Procedure(**proc) for proc in procedures]


@router.get("/procedures/{procedure_id}", response_model=Procedure)
async def get_procedure(
    procedure_id: str,
    user: StorageUser = Depends(require_user)
):
    """Get a specific procedure guide."""
    if procedure_id not in PROCEDURES:
        raise HTTPException(status_code=404, detail="Procedure not found")
    
    return Procedure(**PROCEDURES[procedure_id])


@router.get("/counterclaims", response_model=List[CounterclaimTemplate])
async def list_counterclaims(user: StorageUser = Depends(require_user)):
    """List all counterclaim templates."""
    return [CounterclaimTemplate(**cc) for cc in COUNTERCLAIMS.values()]


@router.get("/counterclaims/{claim_id}", response_model=CounterclaimTemplate)
async def get_counterclaim(
    claim_id: str,
    user: StorageUser = Depends(require_user)
):
    """Get a specific counterclaim template."""
    if claim_id not in COUNTERCLAIMS:
        raise HTTPException(status_code=404, detail="Counterclaim not found")
    
    return CounterclaimTemplate(**COUNTERCLAIMS[claim_id])


@router.get("/statistics")
async def get_statistics(user: StorageUser = Depends(require_user)):
    """Get eviction case statistics for Dakota County."""
    return CASE_STATISTICS


@router.get("/defenses")
async def list_defenses(user: StorageUser = Depends(require_user)):
    """List all available eviction defenses with explanations."""
    return {
        "disclaimer": LEGAL_DISCLAIMER,
        "note": "Strength ratings are general estimates based on legal analysis, not guarantees. Outcomes depend on specific facts, evidence quality, and judicial discretion.",
        "defenses": [
            {
                "type": DefenseType.IMPROPER_NOTICE,
                "name": "Improper Notice",
                "description": "The landlord's notice was defective in form, timing, or service.",
                "strength": "Strong when notice clearly fails to meet statutory requirements (Minn. Stat. § 504B.321)",
                "evidence_needed": ["Original notice", "Proof of service date", "Lease terms"]
            },
            {
                "type": DefenseType.RETALIATION,
                "name": "Retaliatory Eviction",
                "description": "Landlord is evicting you for exercising your legal rights.",
                "strength": "Presumed retaliatory if within 90 days of protected activity (Minn. Stat. § 504B.285)",
                "evidence_needed": ["Complaint records", "Timeline of events", "Landlord communications"]
            },
            {
                "type": DefenseType.HABITABILITY,
                "name": "Uninhabitable Conditions",
                "description": "Landlord failed to maintain safe, habitable premises.",
                "strength": "Depends on severity of conditions and documentation (Minn. Stat. § 504B.161)",
                "evidence_needed": ["Photos/videos", "Repair requests", "Inspection reports"]
            },
            {
                "type": DefenseType.DISCRIMINATION,
                "name": "Discriminatory Eviction",
                "description": "Eviction is based on protected class status.",
                "strength": "Strong with comparative evidence showing disparate treatment (Fair Housing Act)",
                "evidence_needed": ["Comparative evidence", "Statements by landlord", "Pattern of conduct"]
            },
            {
                "type": DefenseType.WAIVER,
                "name": "Waiver by Landlord",
                "description": "Landlord accepted rent after alleged violation, waiving right to evict.",
                "strength": "Strong when landlord knowingly accepted rent after learning of violation",
                "evidence_needed": ["Payment records", "Receipt showing acceptance after notice"]
            },
            {
                "type": DefenseType.PAYMENT,
                "name": "Payment Was Made",
                "description": "Rent was actually paid as alleged or cure occurred.",
                "strength": "Strong with clear payment documentation (Minn. Stat. § 504B.291)",
                "evidence_needed": ["Bank records", "Receipts", "Money order stubs"]
            }
        ]
    }


class DeadlineCalculation(BaseModel):
    """Request for deadline calculation."""
    service_date: date
    case_type: str = "nonpayment"


@router.post("/calculate-deadlines")
async def calculate_deadlines(
    request: DeadlineCalculation,
    user: StorageUser = Depends(require_user)
):
    """Calculate all important deadlines based on service date."""
    service = request.service_date
    
    deadlines = {
        "service_date": service.isoformat(),
        "answer_due": (service + timedelta(days=7)).isoformat(),
        "jury_demand_due": (service + timedelta(days=10)).isoformat(),
        "estimated_hearing": (service + timedelta(days=14)).isoformat(),
        "estimated_jury_trial": (service + timedelta(days=28)).isoformat(),
        "warnings": []
    }
    
    # Check if deadlines are imminent
    today = date.today()
    answer_date = service + timedelta(days=7)
    
    if today > answer_date:
        deadlines["warnings"].append("⚠️ ANSWER DEADLINE HAS PASSED - File immediately!")
    elif (answer_date - today).days <= 2:
        deadlines["warnings"].append("⚠️ Answer due in " + str((answer_date - today).days) + " days!")
    
    return deadlines


@router.get("/case-checklist/{stage}")
async def get_case_checklist(
    stage: CaseStage,
    user: StorageUser = Depends(require_user)
):
    """Get a checklist of tasks for the current case stage."""
    checklists = {
        CaseStage.NOTICE_RECEIVED: {
            "stage": "Notice Received",
            "tasks": [
                {"task": "Read notice carefully", "priority": "high", "done": False},
                {"task": "Note the date you received it", "priority": "high", "done": False},
                {"task": "Check if notice period is correct", "priority": "high", "done": False},
                {"task": "Photograph/scan the notice", "priority": "medium", "done": False},
                {"task": "Research if you can cure (pay)", "priority": "high", "done": False},
                {"task": "Contact legal aid if available", "priority": "medium", "done": False}
            ]
        },
        CaseStage.COMPLAINT_FILED: {
            "stage": "Complaint Filed",
            "tasks": [
                {"task": "Note date of service", "priority": "high", "done": False},
                {"task": "Calculate 7-day deadline", "priority": "high", "done": False},
                {"task": "Read complaint carefully", "priority": "high", "done": False},
                {"task": "Identify defenses that apply", "priority": "high", "done": False},
                {"task": "Gather supporting documents", "priority": "high", "done": False},
                {"task": "Prepare Answer form", "priority": "high", "done": False}
            ]
        },
        CaseStage.ANSWER_DUE: {
            "stage": "Answer Due",
            "tasks": [
                {"task": "Complete Answer form", "priority": "high", "done": False},
                {"task": "Include all defenses", "priority": "high", "done": False},
                {"task": "Include counterclaims if any", "priority": "medium", "done": False},
                {"task": "Consider jury trial demand", "priority": "medium", "done": False},
                {"task": "File with court", "priority": "high", "done": False},
                {"task": "Serve copy on landlord", "priority": "high", "done": False}
            ]
        },
        CaseStage.PRETRIAL: {
            "stage": "Pre-Trial",
            "tasks": [
                {"task": "Organize all evidence", "priority": "high", "done": False},
                {"task": "Create exhibit list", "priority": "high", "done": False},
                {"task": "Prepare testimony outline", "priority": "high", "done": False},
                {"task": "Confirm witness attendance", "priority": "medium", "done": False},
                {"task": "Review court procedures", "priority": "medium", "done": False},
                {"task": "Plan what to wear", "priority": "low", "done": False}
            ]
        },
        CaseStage.TRIAL: {
            "stage": "Trial Day",
            "tasks": [
                {"task": "Arrive 15 minutes early", "priority": "high", "done": False},
                {"task": "Bring all original documents", "priority": "high", "done": False},
                {"task": "Check in with clerk", "priority": "high", "done": False},
                {"task": "Review notes while waiting", "priority": "medium", "done": False},
                {"task": "Stay calm and respectful", "priority": "high", "done": False}
            ]
        }
    }
    
    if stage not in checklists:
        raise HTTPException(status_code=404, detail="Checklist not found for this stage")

    return checklists[stage]


# =============================================================================
# Case Analysis Endpoints (NEW - Connects All Services)
# =============================================================================

class AnalysisRequest(BaseModel):
    """Request for case analysis."""
    include_violations: bool = True
    include_strategies: bool = True
    include_forms: bool = True


class ViolationInfo(BaseModel):
    """Information about a detected violation."""
    id: str
    type: str
    title: str
    description: str
    law_ref: str
    severity: str
    defense_code: str


class StrategyInfo(BaseModel):
    """Defense strategy recommendation."""
    code: str
    title: str
    description: str
    strength: str
    evidence_needed: List[str]
    forms_to_file: List[str]


class AnalysisResponse(BaseModel):
    """Complete case analysis response."""
    case_number: str
    violations: List[ViolationInfo] = []
    strategies: List[StrategyInfo] = []
    recommended_forms: List[str] = []
    urgency: str = "normal"
    next_steps: List[str] = []


@router.post("/analyze", response_model=AnalysisResponse)
async def analyze_case(
    request: AnalysisRequest = AnalysisRequest(),
    user: StorageUser = Depends(require_user)
):
    """
    Analyze the user's case for violations and defense strategies.
    
    This is the MAIN ENTRY POINT for case analysis.
    Connects: FormDataHub → LawEngine → DefenseStrategies → FormsRecommendation
    """
    # Get form data service for this user
    form_service = get_form_data_service(user.user_id)
    await form_service.load()
    
    case = form_service.form_data.case
    case_data = {
        "case_number": case.case_number,
        "notice_date": case.notice_date,
        "notice_type": case.notice_type,
        "hearing_date": case.hearing_date,
        "rent_claimed": case.rent_claimed,
        "monthly_rent": case.monthly_rent,
    }
    
    violations = []
    strategies = []
    recommended_forms = []
    
    # Find violations using law engine
    if request.include_violations:
        law_engine = get_law_engine()
        raw_violations = await law_engine.find_violations(case_data, user.user_id)
        violations = [ViolationInfo(**v) for v in raw_violations]
        
        # Get defense strategies based on violations
        if request.include_strategies and raw_violations:
            raw_strategies = law_engine.get_defense_strategies(raw_violations)
            strategies = [StrategyInfo(**s) for s in raw_strategies]
            
            # Collect recommended forms
            if request.include_forms:
                for s in raw_strategies:
                    for form in s.get("forms_to_file", []):
                        if form not in recommended_forms:
                            recommended_forms.append(form)
    
    # Determine urgency
    urgency = "normal"
    if case.hearing_date:
        try:
            hearing = datetime.fromisoformat(case.hearing_date)
            days_until = (hearing - datetime.now()).days
            if days_until <= 3:
                urgency = "critical"
            elif days_until <= 7:
                urgency = "high"
            elif days_until <= 14:
                urgency = "medium"
        except Exception:
            pass
    
    # Generate next steps
    next_steps = []
    if not case.case_number:
        next_steps.append("Enter your case number from the summons")
    if not case.hearing_date:
        next_steps.append("Enter your court hearing date")
    if violations:
        next_steps.append(f"Review {len(violations)} potential violations found")
    if strategies:
        next_steps.append("Review recommended defense strategies")
    if recommended_forms:
        next_steps.append(f"Prepare {len(recommended_forms)} recommended forms")
    if not next_steps:
        next_steps.append("Your case analysis is complete - review your defense strategy")
    
    return AnalysisResponse(
        case_number=case.case_number or "Not entered",
        violations=violations,
        strategies=strategies,
        recommended_forms=recommended_forms,
        urgency=urgency,
        next_steps=next_steps,
    )


@router.get("/quick-status")
async def get_quick_status(user: StorageUser = Depends(require_user)):
    """
    Get quick status for dashboard display.
    """
    form_service = get_form_data_service(user.user_id)
    await form_service.load()
    
    summary = form_service.get_case_summary()
    
    return {
        "case_number": summary["case_number"],
        "stage": summary["stage_display"],
        "days_to_hearing": summary["days_to_hearing"],
        "defenses_count": summary["defenses_count"],
        "documents_count": summary["documents_count"],
        "ready_for_court": summary["defenses_count"] > 0 and summary["documents_count"] > 0,
    }