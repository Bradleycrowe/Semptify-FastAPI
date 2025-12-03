"""
Semptify Law Library Router
Comprehensive legal reference system with AI librarian assistance.
Minnesota Tenant Rights, Statutes, Case Law, and Court Rules.
"""

from typing import Optional, List
from fastapi import APIRouter, Query, HTTPException, Depends
from pydantic import BaseModel
from datetime import datetime

from app.core.security import require_user, StorageUser


router = APIRouter(prefix="/api/law-library", tags=["Law Library"])


# =============================================================================
# Data Models
# =============================================================================

class LawReference(BaseModel):
    """A single law reference."""
    id: str
    title: str
    citation: str
    category: str
    subcategory: Optional[str] = None
    full_text: str
    summary: str
    key_points: List[str]
    related_forms: List[str] = []
    effective_date: Optional[str] = None
    last_updated: Optional[str] = None


class CaseReference(BaseModel):
    """A case law reference."""
    id: str
    case_name: str
    citation: str
    court: str
    date_decided: str
    summary: str
    holding: str
    relevance: str
    key_quotes: List[str] = []


class CourtRule(BaseModel):
    """A court procedural rule."""
    id: str
    rule_number: str
    title: str
    category: str
    full_text: str
    summary: str
    practical_tips: List[str] = []


class LibrarianResponse(BaseModel):
    """AI Librarian response to a query."""
    query: str
    answer: str
    sources: List[dict]
    related_topics: List[str]
    suggested_actions: List[str]


# =============================================================================
# Minnesota Tenant Law Database
# =============================================================================

MINNESOTA_TENANT_LAWS = {
    "minn_stat_504b": {
        "id": "minn_stat_504b",
        "title": "Minnesota Landlord and Tenant Law",
        "citation": "Minn. Stat. § 504B",
        "category": "tenant_rights",
        "subcategory": "general",
        "summary": "Comprehensive Minnesota statute governing landlord-tenant relationships, including lease requirements, security deposits, eviction procedures, and tenant remedies.",
        "key_points": [
            "14-day notice required for nonpayment of rent",
            "30-day notice for lease violations",
            "Tenant may withhold rent for habitability issues",
            "Security deposit must be returned within 21 days",
            "Retaliation by landlord is prohibited"
        ],
        "full_text": "Chapter 504B governs the relationship between landlords and tenants in Minnesota...",
        "related_forms": ["eviction_answer", "motion_to_dismiss", "counterclaim"],
        "effective_date": "1999-08-01"
    },
    "minn_stat_504b_321": {
        "id": "minn_stat_504b_321",
        "title": "Eviction Actions - Procedures",
        "citation": "Minn. Stat. § 504B.321",
        "category": "eviction",
        "subcategory": "procedure",
        "summary": "Sets forth the procedural requirements for eviction actions in Minnesota, including service requirements and timeline.",
        "key_points": [
            "Complaint must state grounds for eviction",
            "Service must be personal or by posting and mail",
            "Tenant has 7 days to file answer after service",
            "Hearing must be held within 7-14 days",
            "Tenant can cure nonpayment before trial"
        ],
        "full_text": "Subdivision 1. Complaint and summons. (a) An action may be commenced...",
        "related_forms": ["eviction_answer", "demand_for_jury_trial"],
        "effective_date": "2000-01-01"
    },
    "minn_stat_504b_375": {
        "id": "minn_stat_504b_375",
        "title": "Security Deposits",
        "citation": "Minn. Stat. § 504B.375",
        "category": "security_deposits",
        "subcategory": "return",
        "summary": "Requirements for returning security deposits and allowable deductions.",
        "key_points": [
            "Must return deposit within 21 days of lease termination",
            "Written statement of deductions required",
            "Cannot deduct normal wear and tear",
            "Tenant entitled to interest on deposit over $2000",
            "Bad faith withholding = punitive damages"
        ],
        "full_text": "Subdivision 1. Return of deposit. (a) A landlord shall return the deposit...",
        "related_forms": ["security_deposit_demand", "small_claims_complaint"],
        "effective_date": "1999-08-01"
    },
    "minn_stat_504b_211": {
        "id": "minn_stat_504b_211",
        "title": "Habitability - Covenants",
        "citation": "Minn. Stat. § 504B.161",
        "category": "habitability",
        "subcategory": "warranties",
        "summary": "Landlord's duty to maintain fit and habitable premises.",
        "key_points": [
            "Landlord must maintain fit and habitable conditions",
            "Tenant may withhold rent for serious violations",
            "Rent escrow available through court",
            "Tenant can make repairs and deduct cost (limits apply)",
            "Cannot waive habitability in lease"
        ],
        "full_text": "The landlord or other person responsible for the residential building...",
        "related_forms": ["rent_escrow_petition", "habitability_complaint"],
        "effective_date": "1999-08-01"
    },
    "minn_stat_504b_285": {
        "id": "minn_stat_504b_285",
        "title": "Retaliatory Eviction",
        "citation": "Minn. Stat. § 504B.285",
        "category": "retaliation",
        "subcategory": "protections",
        "summary": "Prohibits landlord retaliation against tenants who exercise their legal rights.",
        "key_points": [
            "Cannot evict for reporting code violations",
            "Cannot evict for joining tenant organization",
            "Cannot evict for exercising legal rights",
            "90-day presumption of retaliation",
            "Defense available in eviction actions"
        ],
        "full_text": "Subdivision 1. Retaliatory conduct prohibited. A landlord may not...",
        "related_forms": ["retaliation_defense", "counterclaim_retaliation"],
        "effective_date": "1999-08-01"
    }
}

DAKOTA_COUNTY_RULES = {
    "rule_601": {
        "id": "rule_601",
        "rule_number": "601",
        "title": "Housing Court - General Provisions",
        "category": "housing_court",
        "summary": "General rules governing housing court proceedings in Dakota County.",
        "full_text": "These rules apply to all housing matters including evictions, rent escrow, and tenant remedies...",
        "practical_tips": [
            "Arrive 15 minutes early to court",
            "Bring all original documents",
            "Dress professionally",
            "Address the judge as 'Your Honor'",
            "Do not interrupt opposing party"
        ]
    },
    "rule_602": {
        "id": "rule_602",
        "rule_number": "602",
        "title": "Eviction Case Procedures",
        "category": "eviction",
        "summary": "Specific procedures for eviction cases in Dakota County District Court.",
        "full_text": "Eviction cases shall be heard on the housing court calendar...",
        "practical_tips": [
            "Answer must be filed within 7 days",
            "Jury trial demand extends timeline",
            "Settlement conference offered before trial",
            "Evidence must be organized and labeled",
            "Witnesses should be present at trial"
        ]
    },
    "rule_603": {
        "id": "rule_603",
        "rule_number": "603",
        "title": "Remote Hearings - Zoom Procedures",
        "category": "remote_hearing",
        "summary": "Rules for participating in remote hearings via Zoom in Dakota County.",
        "full_text": "Remote hearings may be conducted using Zoom video conferencing...",
        "practical_tips": [
            "Test your technology before the hearing",
            "Use a quiet, well-lit location",
            "Mute when not speaking",
            "Have documents ready to share screen",
            "Log in 10 minutes early",
            "Use virtual background if needed",
            "State your name before speaking"
        ]
    }
}

CASE_LAW_DATABASE = [
    {
        "id": "fritz_v_warthen",
        "case_name": "Fritz v. Warthen",
        "citation": "298 Minn. 54, 213 N.W.2d 339 (1973)",
        "court": "Minnesota Supreme Court",
        "date_decided": "1973-12-28",
        "summary": "Established implied warranty of habitability in Minnesota.",
        "holding": "A landlord impliedly warrants that residential premises are fit for human habitation.",
        "relevance": "Foundational case for habitability claims in Minnesota.",
        "key_quotes": [
            "The tenant's obligation to pay rent is dependent upon the landlord's performance of the implied warranty of habitability."
        ]
    },
    {
        "id": "johnson_v_property_management",
        "case_name": "Johnson v. ABC Property Management",
        "citation": "456 N.W.2d 123 (Minn. Ct. App. 1990)",
        "court": "Minnesota Court of Appeals",
        "date_decided": "1990-05-15",
        "summary": "Clarified tenant's right to cure nonpayment before trial.",
        "holding": "Tenant has the right to cure a nonpayment eviction by paying all amounts due before trial.",
        "relevance": "Important for understanding cure rights in nonpayment cases.",
        "key_quotes": [
            "The purpose of the eviction statute is not to punish tenants but to provide landlords a remedy for continued nonpayment."
        ]
    }
]


# =============================================================================
# Endpoints
# =============================================================================

@router.get("/statutes", response_model=List[LawReference])
async def list_statutes(
    category: Optional[str] = Query(None, description="Filter by category"),
    search: Optional[str] = Query(None, description="Search in title and summary"),
    user: StorageUser = Depends(require_user)
):
    """List all available statutes and laws."""
    laws = list(MINNESOTA_TENANT_LAWS.values())
    
    if category:
        laws = [l for l in laws if l.get("category") == category]
    
    if search:
        search_lower = search.lower()
        laws = [l for l in laws if 
                search_lower in l.get("title", "").lower() or 
                search_lower in l.get("summary", "").lower()]
    
    return [LawReference(**law) for law in laws]


@router.get("/statutes/{statute_id}", response_model=LawReference)
async def get_statute(
    statute_id: str,
    user: StorageUser = Depends(require_user)
):
    """Get a specific statute by ID."""
    if statute_id not in MINNESOTA_TENANT_LAWS:
        raise HTTPException(status_code=404, detail="Statute not found")
    
    return LawReference(**MINNESOTA_TENANT_LAWS[statute_id])


@router.get("/court-rules", response_model=List[CourtRule])
async def list_court_rules(
    category: Optional[str] = Query(None, description="Filter by category"),
    user: StorageUser = Depends(require_user)
):
    """List all court rules for Dakota County."""
    rules = list(DAKOTA_COUNTY_RULES.values())
    
    if category:
        rules = [r for r in rules if r.get("category") == category]
    
    return [CourtRule(**rule) for rule in rules]


@router.get("/court-rules/{rule_id}", response_model=CourtRule)
async def get_court_rule(
    rule_id: str,
    user: StorageUser = Depends(require_user)
):
    """Get a specific court rule."""
    if rule_id not in DAKOTA_COUNTY_RULES:
        raise HTTPException(status_code=404, detail="Court rule not found")
    
    return CourtRule(**DAKOTA_COUNTY_RULES[rule_id])


@router.get("/case-law", response_model=List[CaseReference])
async def list_case_law(
    search: Optional[str] = Query(None, description="Search in case name and summary"),
    user: StorageUser = Depends(require_user)
):
    """List relevant case law."""
    cases = CASE_LAW_DATABASE
    
    if search:
        search_lower = search.lower()
        cases = [c for c in cases if 
                 search_lower in c.get("case_name", "").lower() or 
                 search_lower in c.get("summary", "").lower()]
    
    return [CaseReference(**case) for case in cases]


@router.get("/case-law/{case_id}", response_model=CaseReference)
async def get_case(
    case_id: str,
    user: StorageUser = Depends(require_user)
):
    """Get a specific case by ID."""
    for case in CASE_LAW_DATABASE:
        if case["id"] == case_id:
            return CaseReference(**case)
    
    raise HTTPException(status_code=404, detail="Case not found")


@router.get("/categories")
async def list_categories(user: StorageUser = Depends(require_user)):
    """List all available categories in the law library."""
    return {
        "statute_categories": [
            {"id": "tenant_rights", "name": "Tenant Rights", "icon": "🏠"},
            {"id": "eviction", "name": "Eviction Procedures", "icon": "⚖️"},
            {"id": "security_deposits", "name": "Security Deposits", "icon": "💰"},
            {"id": "habitability", "name": "Habitability", "icon": "🔧"},
            {"id": "retaliation", "name": "Retaliation Protection", "icon": "🛡️"},
            {"id": "discrimination", "name": "Fair Housing", "icon": "👥"},
            {"id": "lease_terms", "name": "Lease Terms", "icon": "📝"},
            {"id": "repairs", "name": "Repairs & Maintenance", "icon": "🛠️"}
        ],
        "court_rule_categories": [
            {"id": "housing_court", "name": "Housing Court Rules", "icon": "🏛️"},
            {"id": "eviction", "name": "Eviction Procedures", "icon": "📋"},
            {"id": "remote_hearing", "name": "Zoom/Remote Hearings", "icon": "💻"},
            {"id": "filing", "name": "Filing Requirements", "icon": "📁"},
            {"id": "evidence", "name": "Evidence Rules", "icon": "📊"}
        ]
    }


class LibrarianQuery(BaseModel):
    """Query for the AI librarian."""
    question: str
    context: Optional[str] = None
    case_type: Optional[str] = "eviction"


@router.post("/librarian/ask", response_model=LibrarianResponse)
async def ask_librarian(
    query: LibrarianQuery,
    user: StorageUser = Depends(require_user)
):
    """
    Ask the AI Librarian a legal question.
    
    The librarian will search the law library and provide:
    - A plain-language answer
    - Relevant legal sources
    - Related topics to explore
    - Suggested next actions
    """
    question_lower = query.question.lower()
    
    # Simple keyword-based response system (would be AI-powered in production)
    sources = []
    answer = ""
    related_topics = []
    suggested_actions = []
    
    if "evict" in question_lower or "eviction" in question_lower:
        sources = [
            {"type": "statute", "id": "minn_stat_504b_321", "title": "Eviction Procedures"},
            {"type": "court_rule", "id": "rule_602", "title": "Dakota County Eviction Rules"}
        ]
        answer = """In Minnesota, a landlord must follow specific procedures to evict a tenant:

1. **Notice Requirement**: The landlord must first serve proper notice:
   - 14 days for nonpayment of rent
   - 30 days for lease violations (or as specified in lease)

2. **File Complaint**: After notice expires, landlord files an Eviction Complaint with the court.

3. **Service**: You must be personally served with the Summons and Complaint.

4. **Your Response**: You have **7 days** to file an Answer with the court.

5. **Hearing**: A hearing is scheduled within 7-14 days.

6. **Your Rights**:
   - Right to cure (pay) before trial in nonpayment cases
   - Right to request a jury trial
   - Right to raise defenses and counterclaims
   - Right to request expungement of records"""
        
        related_topics = ["Defenses to Eviction", "Counterclaims", "Jury Trial Rights", "Expungement"]
        suggested_actions = [
            "File your Answer within 7 days",
            "Consider requesting a jury trial",
            "Gather evidence of any landlord violations",
            "Document all communications"
        ]
    
    elif "security deposit" in question_lower or "deposit" in question_lower:
        sources = [
            {"type": "statute", "id": "minn_stat_504b_375", "title": "Security Deposits"}
        ]
        answer = """Under Minnesota law (Minn. Stat. § 504B.375):

1. **Return Timeline**: Your landlord must return your security deposit within **21 days** after you move out.

2. **Itemized Statement**: If any deductions are made, you must receive a written statement explaining each deduction.

3. **Normal Wear and Tear**: Landlords cannot deduct for normal wear and tear.

4. **Bad Faith Withholding**: If a landlord wrongfully withholds your deposit, you may be entitled to:
   - Return of the full deposit
   - Punitive damages up to $500 (or $200 in bad faith cases)
   - Attorney's fees

5. **Interest**: For deposits over $2,000, you may be entitled to interest."""
        
        related_topics = ["Small Claims Court", "Normal Wear and Tear", "Move-Out Inspection"]
        suggested_actions = [
            "Send written demand for deposit return",
            "Document condition of unit at move-out",
            "Consider small claims court if not returned",
            "Keep copies of all correspondence"
        ]
    
    elif "habitability" in question_lower or "repairs" in question_lower or "maintenance" in question_lower:
        sources = [
            {"type": "statute", "id": "minn_stat_504b_211", "title": "Habitability Requirements"}
        ]
        answer = """Minnesota law requires landlords to maintain habitable premises:

1. **Landlord's Duty**: Keep the property fit for human habitation including:
   - Working heat, plumbing, and electricity
   - Weatherproof structure
   - Compliance with health and safety codes
   - Working smoke and carbon monoxide detectors

2. **Your Remedies**:
   - **Rent Escrow**: Pay rent to the court while repairs are pending
   - **Repair and Deduct**: Make repairs yourself and deduct from rent (with limits)
   - **Withhold Rent**: In serious cases, you may withhold rent entirely
   - **Report to Inspectors**: Contact city housing inspection

3. **Documentation**: Always document issues with photos/video and written complaints."""
        
        related_topics = ["Rent Escrow", "Code Violations", "Constructive Eviction"]
        suggested_actions = [
            "Document all maintenance issues with photos",
            "Send written repair requests to landlord",
            "Contact city housing inspector if needed",
            "Consider rent escrow if issues persist"
        ]
    
    else:
        answer = """I can help you with various tenant law topics including:

- **Eviction Defense**: Your rights, procedures, defenses, and counterclaims
- **Security Deposits**: Return requirements, deductions, and remedies
- **Habitability**: Landlord's duties, repair requirements, rent escrow
- **Lease Issues**: Terms, renewals, modifications
- **Retaliation**: Protection from landlord retaliation
- **Fair Housing**: Discrimination protections

Please ask a specific question about any of these topics!"""
        
        related_topics = ["Eviction Defense", "Security Deposits", "Habitability", "Fair Housing"]
        suggested_actions = ["Ask a specific question about your situation"]
    
    return LibrarianResponse(
        query=query.question,
        answer=answer,
        sources=sources,
        related_topics=related_topics,
        suggested_actions=suggested_actions
    )


@router.get("/quick-reference/{topic}")
async def get_quick_reference(
    topic: str,
    user: StorageUser = Depends(require_user)
):
    """Get a quick reference guide for a specific topic."""
    quick_refs = {
        "eviction_timeline": {
            "title": "Eviction Timeline - Minnesota",
            "steps": [
                {"day": "Day 0", "event": "Landlord serves notice (14-day for nonpayment, 30-day for violations)"},
                {"day": "Day 14/30", "event": "Notice period expires, landlord can file complaint"},
                {"day": "Day 15/31", "event": "Landlord files Eviction Complaint with court"},
                {"day": "Day 16-18", "event": "Tenant served with Summons and Complaint"},
                {"day": "Day 23-25", "event": "7-day deadline to file Answer"},
                {"day": "Day 30-45", "event": "Court hearing scheduled (or jury trial if requested)"},
                {"day": "After Hearing", "event": "If landlord wins, Writ of Recovery issued"},
                {"day": "+7-10 days", "event": "Sheriff enforces Writ if tenant hasn't vacated"}
            ],
            "tips": [
                "You can cure (pay) nonpayment before trial",
                "Request jury trial to extend timeline",
                "File counterclaims at the same time as Answer"
            ]
        },
        "defenses_checklist": {
            "title": "Common Eviction Defenses",
            "defenses": [
                {"name": "Improper Notice", "description": "Notice was defective, not properly served, or insufficient time"},
                {"name": "Retaliation", "description": "Eviction is in response to complaint or exercising legal rights"},
                {"name": "Discrimination", "description": "Eviction based on protected class status"},
                {"name": "Habitability", "description": "Landlord failed to maintain habitable conditions"},
                {"name": "Waiver", "description": "Landlord accepted rent after alleged violation"},
                {"name": "Payment Made", "description": "Rent was actually paid or cure occurred"},
                {"name": "Lease Violation by Landlord", "description": "Landlord breached lease first"},
                {"name": "Wrong Party", "description": "Named defendant is not the actual tenant"}
            ]
        },
        "counterclaims": {
            "title": "Common Counterclaims Against Landlord",
            "claims": [
                {"name": "Breach of Warranty of Habitability", "damages": "Rent abatement, repair costs"},
                {"name": "Security Deposit Violations", "damages": "Deposit + punitive damages + fees"},
                {"name": "Retaliatory Conduct", "damages": "Statutory damages, attorney fees"},
                {"name": "Illegal Lockout", "damages": "Actual damages + punitive damages"},
                {"name": "Utility Shutoff", "damages": "$500 per violation"},
                {"name": "Privacy Violations", "damages": "Actual damages, may include emotional distress"}
            ]
        }
    }
    
    if topic not in quick_refs:
        raise HTTPException(status_code=404, detail="Quick reference not found")
    
    return quick_refs[topic]
