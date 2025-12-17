"""
Semptify 5.0 - Advanced Document Recognition Engine
====================================================

World-class document recognition using multi-layered analysis:
1. Structural Analysis - Document layout, headers, signatures
2. Contextual Analysis - Surrounding text, document flow  
3. Keyword Pattern Matching - Legal terminology with weights
4. Reasoning Logic - Cross-referencing signals for confidence
5. Entity Extraction - Parties, dates, amounts with context
6. Legal Domain Knowledge - Minnesota tenant law specifics

This engine prioritizes QUALITY over speed - every classification
includes detailed reasoning and confidence scoring.
"""

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Tuple


# =============================================================================
# DOCUMENT TYPE TAXONOMY
# =============================================================================

class DocumentCategory(str, Enum):
    """High-level document categories."""
    COURT = "court"
    LANDLORD = "landlord"  
    TENANT = "tenant"
    FINANCIAL = "financial"
    PROPERTY = "property"
    COMMUNICATION = "communication"
    UNKNOWN = "unknown"


class DocumentType(str, Enum):
    """Specific document types within categories."""
    # Court documents
    SUMMONS = "summons"
    COMPLAINT = "complaint"
    EVICTION_FILING = "eviction_filing"
    MOTION = "motion"
    COURT_ORDER = "court_order"
    JUDGMENT = "judgment"
    WRIT = "writ"
    SUBPOENA = "subpoena"
    ANSWER = "answer"
    AFFIDAVIT = "affidavit"
    
    # Landlord documents
    LEASE = "lease"
    EVICTION_NOTICE = "eviction_notice"
    RENT_INCREASE = "rent_increase"
    NOTICE_TO_QUIT = "notice_to_quit"
    LATE_NOTICE = "late_notice"
    LEASE_VIOLATION = "lease_violation"
    NON_RENEWAL = "non_renewal"
    ENTRY_NOTICE = "entry_notice"
    
    # Financial documents
    RECEIPT = "receipt"
    INVOICE = "invoice"
    LEDGER = "ledger"
    DEPOSIT_STATEMENT = "deposit_statement"
    
    # Property documents  
    INSPECTION = "inspection"
    CONDITION_REPORT = "condition_report"
    REPAIR_REQUEST = "repair_request"
    WORK_ORDER = "work_order"
    
    # Communication
    LETTER = "letter"
    EMAIL = "email"
    TEXT_MESSAGE = "text_message"
    
    # Evidence
    PHOTO = "photo"
    VIDEO = "video"
    
    UNKNOWN = "unknown"


@dataclass
class RecognitionSignal:
    """A single signal contributing to document classification."""
    source: str  # "keyword", "structure", "context", "entity", "reasoning"
    indicator: str  # What was found
    weight: float  # 0.0 to 1.0
    evidence: str  # The actual text that triggered this
    reasoning: str  # Why this matters


@dataclass
class ExtractedEntity:
    """An extracted entity with context."""
    entity_type: str  # "date", "party", "amount", "address", "case_number"
    value: str  # The extracted value
    normalized: Optional[str] = None  # Normalized form (e.g., ISO date)
    context_label: str = ""  # What this entity represents
    confidence: float = 0.0
    source_text: str = ""  # Original text where found
    position: int = 0  # Character position in document


@dataclass  
class RecognitionResult:
    """Complete document recognition result."""
    # Classification
    category: DocumentCategory
    doc_type: DocumentType
    confidence: float  # 0.0 to 1.0
    
    # Detailed info
    title: str
    summary: str
    
    # Reasoning trail
    signals: list[RecognitionSignal] = field(default_factory=list)
    reasoning_chain: list[str] = field(default_factory=list)
    
    # Extracted entities
    dates: list[ExtractedEntity] = field(default_factory=list)
    parties: list[ExtractedEntity] = field(default_factory=list)
    amounts: list[ExtractedEntity] = field(default_factory=list)
    case_numbers: list[ExtractedEntity] = field(default_factory=list)
    addresses: list[ExtractedEntity] = field(default_factory=list)
    
    # Key terms for law matching
    key_terms: list[str] = field(default_factory=list)
    
    # Urgency indicators
    has_deadline: bool = False
    deadline_date: Optional[str] = None
    days_to_respond: Optional[int] = None
    urgency_level: str = "normal"  # "critical", "high", "normal", "low"
    
    def to_dict(self) -> dict:
        return {
            "category": self.category.value,
            "doc_type": self.doc_type.value,
            "confidence": self.confidence,
            "title": self.title,
            "summary": self.summary,
            "reasoning": self.reasoning_chain,
            "signals_count": len(self.signals),
            "key_dates": [{"date": d.normalized or d.value, "description": d.context_label} for d in self.dates],
            "key_parties": [{"name": p.value, "role": p.context_label} for p in self.parties],
            "key_amounts": [{"amount": a.value, "description": a.context_label} for a in self.amounts],
            "key_terms": self.key_terms,
            "has_deadline": self.has_deadline,
            "deadline_date": self.deadline_date,
            "urgency_level": self.urgency_level,
        }


# =============================================================================
# PATTERN DEFINITIONS - Carefully curated for legal documents
# =============================================================================

# Court document structural patterns
COURT_STRUCTURE_PATTERNS = {
    "header_format": [
        r"STATE\s+OF\s+\w+",
        r"COUNTY\s+OF\s+\w+",
        r"(?:DISTRICT|SUPERIOR|CIRCUIT|MUNICIPAL)\s+COURT",
        r"(?:IN\s+THE\s+MATTER\s+OF|IN\s+RE:?)",
        r"Case\s*(?:No\.?|Number|#|File)\s*:?\s*[\w\-]+",
        r"(?:PLAINTIFF|PETITIONER)\s*(?:v\.?|vs\.?)\s*(?:DEFENDANT|RESPONDENT)",
    ],
    "court_caption": [
        r"\)\s*\n\s*\)\s*(?:Case|File)",  # Caption format with parentheses
        r"Plaintiff,?\s*\n.*?Defendant",
    ],
    "signature_block": [
        r"(?:Respectfully\s+)?[Ss]ubmitted",
        r"(?:DATED|Date[d]?)\s*(?:this|:)",
        r"(?:Attorney|Counsel)\s+for\s+(?:Plaintiff|Defendant|Petitioner|Respondent)",
        r"___+\s*\n.*?(?:Judge|Clerk|Attorney|Notary)",
    ],
}

# Keyword patterns with weights and context requirements
DOCUMENT_PATTERNS = {
    DocumentType.SUMMONS: {
        "primary_keywords": [
            ("summons", 0.9),
            ("you are hereby summoned", 1.0),
            ("you are being sued", 0.95),
            ("you must respond within", 0.95),
            ("failure to respond", 0.8),
        ],
        "supporting_keywords": [
            ("appear", 0.3),
            ("court", 0.2),
            ("answer", 0.3),
            ("days to respond", 0.5),
            ("service of process", 0.6),
        ],
        "context_requirements": ["court", "respond"],
        "category": DocumentCategory.COURT,
    },
    
    DocumentType.COMPLAINT: {
        "primary_keywords": [
            ("complaint", 0.85),
            ("civil complaint", 0.95),
            ("cause of action", 0.9),
            ("wherefore", 0.85),
            ("plaintiff alleges", 0.95),
            ("comes now the plaintiff", 0.95),
        ],
        "supporting_keywords": [
            ("plaintiff", 0.4),
            ("defendant", 0.4),
            ("damages", 0.3),
            ("hereby demands", 0.5),
            ("jurisdiction", 0.4),
        ],
        "context_requirements": ["plaintiff", "defendant"],
        "category": DocumentCategory.COURT,
    },
    
    DocumentType.EVICTION_FILING: {
        "primary_keywords": [
            ("unlawful detainer", 1.0),
            ("eviction action", 0.95),
            ("recovery of premises", 0.9),
            ("forcible entry and detainer", 0.95),
            ("action for possession", 0.9),
        ],
        "supporting_keywords": [
            ("eviction", 0.5),
            ("possession", 0.4),
            ("tenant", 0.3),
            ("landlord", 0.3),
            ("lease", 0.2),
            ("rent", 0.2),
        ],
        "context_requirements": ["court"],
        "category": DocumentCategory.COURT,
    },
    
    DocumentType.JUDGMENT: {
        "primary_keywords": [
            ("judgment is entered", 1.0),
            ("it is hereby ordered and adjudged", 1.0),
            ("judgment for plaintiff", 0.95),
            ("judgment for defendant", 0.95),
            ("default judgment", 0.95),
            ("summary judgment", 0.9),
        ],
        "supporting_keywords": [
            ("judgment", 0.6),
            ("ordered", 0.4),
            ("awarded", 0.5),
            ("adjudged", 0.5),
        ],
        "context_requirements": ["court"],
        "category": DocumentCategory.COURT,
    },
    
    DocumentType.WRIT: {
        "primary_keywords": [
            ("writ of restitution", 1.0),
            ("writ of execution", 0.95),
            ("writ of possession", 0.95),
            ("commanded to", 0.8),
            ("you are hereby commanded", 0.95),
        ],
        "supporting_keywords": [
            ("sheriff", 0.5),
            ("execute", 0.4),
            ("possession", 0.4),
        ],
        "context_requirements": ["court", "command"],
        "category": DocumentCategory.COURT,
    },
    
    DocumentType.COURT_ORDER: {
        "primary_keywords": [
            ("it is ordered", 0.95),
            ("it is hereby ordered", 1.0),
            ("order of court", 0.9),
            ("the court orders", 0.95),
            ("so ordered", 0.8),
        ],
        "supporting_keywords": [
            ("order", 0.4),
            ("court", 0.3),
            ("judge", 0.4),
            ("shall", 0.3),
        ],
        "context_requirements": ["order"],
        "category": DocumentCategory.COURT,
    },
    
    DocumentType.MOTION: {
        "primary_keywords": [
            ("motion to", 0.9),
            ("motion for", 0.9),
            ("moves the court", 0.95),
            ("defendant moves", 0.9),
            ("plaintiff moves", 0.9),
            ("hereby moves", 0.9),
            # Added from MCRO documents
            ("notice of motion", 1.0),
            ("motion to dismiss", 1.0),
            ("motion and motion to dismiss", 1.0),
            ("respectfully move this court", 0.95),
            ("based on their memorandum", 0.8),
            ("motion to dismiss without prejudice", 1.0),
            ("motion to dismiss and expunge", 1.0),
            ("motion to stay", 0.95),
            ("motion to continue", 0.9),
            ("motion to vacate", 0.95),
            ("motion for continuance", 0.9),
            ("please take notice", 0.7),
        ],
        "supporting_keywords": [
            ("motion", 0.5),
            ("court", 0.3),
            ("grant", 0.3),
            ("request", 0.2),
            # Added
            ("memorandum of law", 0.6),
            ("argument of counsel", 0.5),
            ("dismissal", 0.5),
            ("expunge", 0.6),
            ("expungement", 0.6),
            ("without prejudice", 0.5),
            ("presiding judge", 0.4),
            ("sanctions", 0.3),
        ],
        "context_requirements": ["court", "motion"],
        "category": DocumentCategory.COURT,
    },
    
    DocumentType.ANSWER: {
        "primary_keywords": [
            ("answer to complaint", 1.0),
            ("defendant answers", 0.95),
            ("defendant hereby answers", 1.0),
            ("admits", 0.6),
            ("denies", 0.6),
            ("affirmative defense", 0.9),
        ],
        "supporting_keywords": [
            ("answer", 0.4),
            ("defendant", 0.3),
            ("denies each", 0.5),
        ],
        "context_requirements": ["defendant"],
        "category": DocumentCategory.COURT,
    },
    
    DocumentType.AFFIDAVIT: {
        "primary_keywords": [
            ("affidavit", 0.9),
            ("sworn statement", 0.9),
            ("under penalty of perjury", 0.95),
            ("being duly sworn", 0.95),
            ("deposes and says", 0.95),
            ("affiant states", 0.9),
        ],
        "supporting_keywords": [
            ("sworn", 0.4),
            ("notary", 0.5),
            ("subscribed", 0.4),
            ("oath", 0.4),
        ],
        "context_requirements": ["sworn"],
        "category": DocumentCategory.COURT,
    },
    
    # === LANDLORD DOCUMENTS ===
    
    DocumentType.LEASE: {
        "primary_keywords": [
            ("lease agreement", 1.0),
            ("rental agreement", 0.95),
            ("tenancy agreement", 0.95),
            ("residential lease", 0.95),
            ("landlord hereby leases", 0.95),
            ("term of lease", 0.9),
        ],
        "supporting_keywords": [
            ("lease", 0.4),
            ("rent", 0.3),
            ("tenant", 0.3),
            ("landlord", 0.3),
            ("security deposit", 0.4),
            ("premises", 0.3),
            ("monthly", 0.2),
        ],
        "context_requirements": ["tenant", "landlord"],
        "category": DocumentCategory.LANDLORD,
    },
    
    DocumentType.EVICTION_NOTICE: {
        "primary_keywords": [
            ("notice to vacate", 0.95),
            ("eviction notice", 0.95),
            ("notice of termination", 0.9),
            ("you are hereby notified to vacate", 1.0),
            ("terminate your tenancy", 0.9),
        ],
        "supporting_keywords": [
            ("vacate", 0.5),
            ("evict", 0.5),
            ("terminate", 0.4),
            ("days notice", 0.4),
        ],
        "context_requirements": ["vacate"],
        "category": DocumentCategory.LANDLORD,
    },
    
    DocumentType.NOTICE_TO_QUIT: {
        "primary_keywords": [
            ("notice to quit", 1.0),
            ("pay or quit", 0.95),
            ("cure or quit", 0.95),
            ("demand for possession", 0.9),
            ("notice to pay rent or quit", 1.0),
        ],
        "supporting_keywords": [
            ("quit", 0.5),
            ("pay", 0.3),
            ("demand", 0.4),
            ("days", 0.2),
        ],
        "context_requirements": ["quit"],
        "category": DocumentCategory.LANDLORD,
    },
    
    DocumentType.RENT_INCREASE: {
        "primary_keywords": [
            ("rent increase", 0.95),
            ("rent will increase", 0.95),
            ("new rent amount", 0.9),
            ("rent adjustment", 0.85),
            ("increase in rent", 0.9),
        ],
        "supporting_keywords": [
            ("rent", 0.3),
            ("increase", 0.4),
            ("effective", 0.3),
            ("new amount", 0.4),
        ],
        "context_requirements": ["rent", "increase"],
        "category": DocumentCategory.LANDLORD,
    },
    
    DocumentType.LATE_NOTICE: {
        "primary_keywords": [
            ("late rent notice", 0.95),
            ("rent past due", 0.9),
            ("overdue rent", 0.9),
            ("delinquent rent", 0.9),
            ("failure to pay rent", 0.85),
        ],
        "supporting_keywords": [
            ("late", 0.4),
            ("past due", 0.5),
            ("owed", 0.3),
            ("payment", 0.2),
        ],
        "context_requirements": ["rent", "late"],
        "category": DocumentCategory.LANDLORD,
    },
    
    DocumentType.LEASE_VIOLATION: {
        "primary_keywords": [
            ("lease violation", 0.95),
            ("violation notice", 0.9),
            ("breach of lease", 0.95),
            ("in violation of", 0.85),
            ("violating the terms", 0.9),
        ],
        "supporting_keywords": [
            ("violation", 0.5),
            ("breach", 0.5),
            ("cure", 0.4),
            ("comply", 0.3),
        ],
        "context_requirements": ["violation"],
        "category": DocumentCategory.LANDLORD,
    },
    
    DocumentType.ENTRY_NOTICE: {
        "primary_keywords": [
            ("notice of entry", 0.95),
            ("intent to enter", 0.9),
            ("will enter the premises", 0.9),
            ("right to enter", 0.8),
            ("24 hour notice", 0.7),
        ],
        "supporting_keywords": [
            ("entry", 0.4),
            ("enter", 0.3),
            ("inspection", 0.3),
            ("maintenance", 0.3),
        ],
        "context_requirements": ["entry", "premises"],
        "category": DocumentCategory.LANDLORD,
    },
    
    # === FINANCIAL DOCUMENTS ===
    
    DocumentType.RECEIPT: {
        "primary_keywords": [
            ("receipt", 0.8),
            ("payment received", 0.95),
            ("amount paid", 0.9),
            ("thank you for your payment", 0.85),
            ("paid in full", 0.8),
        ],
        "supporting_keywords": [
            ("received", 0.4),
            ("paid", 0.4),
            ("payment", 0.3),
            ("amount", 0.2),
        ],
        "context_requirements": ["paid"],
        "category": DocumentCategory.FINANCIAL,
    },
    
    DocumentType.DEPOSIT_STATEMENT: {
        "primary_keywords": [
            ("security deposit", 0.9),
            ("deposit itemization", 0.95),
            ("deposit deductions", 0.95),
            ("deposit accounting", 0.9),
            ("return of deposit", 0.85),
        ],
        "supporting_keywords": [
            ("deposit", 0.5),
            ("deduction", 0.4),
            ("cleaning", 0.3),
            ("damage", 0.3),
        ],
        "context_requirements": ["deposit"],
        "category": DocumentCategory.FINANCIAL,
    },
    
    # === PROPERTY DOCUMENTS ===
    
    DocumentType.INSPECTION: {
        "primary_keywords": [
            ("inspection report", 0.95),
            ("property inspection", 0.95),
            ("condition report", 0.9),
            ("move-in inspection", 0.95),
            ("move-out inspection", 0.95),
        ],
        "supporting_keywords": [
            ("inspection", 0.5),
            ("condition", 0.4),
            ("walkthrough", 0.5),
            ("checklist", 0.3),
        ],
        "context_requirements": ["inspection"],
        "category": DocumentCategory.PROPERTY,
    },
    
    DocumentType.REPAIR_REQUEST: {
        "primary_keywords": [
            ("repair request", 0.95),
            ("maintenance request", 0.95),
            ("request for repairs", 0.9),
            ("needs repair", 0.8),
            ("please repair", 0.8),
        ],
        "supporting_keywords": [
            ("repair", 0.5),
            ("maintenance", 0.4),
            ("broken", 0.4),
            ("fix", 0.3),
            ("not working", 0.4),
        ],
        "context_requirements": ["repair"],
        "category": DocumentCategory.PROPERTY,
    },
    
    # === COMMUNICATION ===
    
    DocumentType.LETTER: {
        "primary_keywords": [
            ("dear", 0.5),
            ("to whom it may concern", 0.6),
            ("sincerely", 0.4),
            ("regarding your tenancy", 0.7),
        ],
        "supporting_keywords": [
            ("letter", 0.3),
            ("write", 0.2),
            ("inform", 0.2),
        ],
        "context_requirements": [],
        "category": DocumentCategory.COMMUNICATION,
    },
}

# Minnesota-specific legal terms
MN_LEGAL_TERMS = {
    "statutes": [
        ("504B", "Minnesota Tenant Remedies Act"),
        ("504B.135", "Eviction notice requirements"),
        ("504B.161", "Landlord covenants"),
        ("504B.178", "Security deposit rules"),
        ("504B.211", "Eviction proceedings"),
        ("504B.285", "Recovery of possession"),
        ("504B.291", "Expedited eviction"),
        ("504B.321", "Emergency tenant remedies"),
        ("504B.375", "Self-help eviction prohibited"),
        ("504B.441", "Tenant protection from retaliation"),
    ],
    "deadlines": {
        "eviction_answer": 7,  # Days to answer eviction summons
        "nonpayment_notice": 14,  # Days for pay-or-quit
        "lease_violation_notice": 14,  # Days to cure violation
        "month_to_month_termination": 30,  # Days notice required
    },
}

# =============================================================================
# DAKOTA COUNTY SPECIFIC FORMS - First Judicial District
# =============================================================================

DAKOTA_COUNTY_FORMS = {
    # Dakota County Housing Court Forms
    "HOU301": {
        "name": "Summons - Unlawful Detainer",
        "doc_type": DocumentType.SUMMONS,
        "patterns": [
            r"HOU301",
            r"summons.*unlawful\s+detainer",
            r"first\s+judicial\s+district.*dakota",
            r"19HA-CV-\d{2}-\d+",  # Dakota County case number format
        ],
        "deadlines": {"respond": 7},
    },
    "HOU302": {
        "name": "Complaint - Unlawful Detainer (Non-Payment)",
        "doc_type": DocumentType.EVICTION_FILING,
        "patterns": [
            r"HOU302",
            r"complaint.*non-?payment",
            r"unlawful\s+detainer.*rent",
        ],
        "deadlines": {},
    },
    "HOU303": {
        "name": "Complaint - Unlawful Detainer (Lease Violation)",
        "doc_type": DocumentType.EVICTION_FILING,
        "patterns": [
            r"HOU303",
            r"complaint.*lease\s+violation",
            r"breach\s+of\s+covenant",
        ],
        "deadlines": {},
    },
    "HOU304": {
        "name": "Answer - Unlawful Detainer",
        "doc_type": DocumentType.ANSWER,
        "patterns": [
            r"HOU304",
            r"answer.*unlawful\s+detainer",
            r"defendant.*answers",
        ],
        "deadlines": {"file": 7},
    },
    "HOU305": {
        "name": "Affirmative Defenses - Unlawful Detainer",
        "doc_type": DocumentType.ANSWER,
        "patterns": [
            r"HOU305",
            r"affirmative\s+defense",
            r"habitability\s+defense",
            r"retaliation\s+defense",
        ],
        "deadlines": {},
    },
    "HOU306": {
        "name": "Motion to Stay Writ of Recovery",
        "doc_type": DocumentType.MOTION,
        "patterns": [
            r"HOU306",
            r"motion\s+to\s+stay",
            r"stay.*writ\s+of\s+recovery",
        ],
        "deadlines": {},
    },
    "HOU307": {
        "name": "Writ of Recovery of Premises",
        "doc_type": DocumentType.WRIT,
        "patterns": [
            r"HOU307",
            r"writ\s+of\s+recovery",
            r"writ\s+of\s+restitution",
            r"commanded\s+to\s+remove",
        ],
        "deadlines": {"execute": 7},
    },
    "HOU308": {
        "name": "Satisfaction of Judgment",
        "doc_type": DocumentType.JUDGMENT,
        "patterns": [
            r"HOU308",
            r"satisfaction\s+of\s+judgment",
            r"judgment\s+satisfied",
        ],
        "deadlines": {},
    },
}

# Dakota County Court Locations
DAKOTA_COUNTY_COURTS = {
    "hastings": {
        "name": "Dakota County Judicial Center - Hastings",
        "address": "1560 Highway 55, Hastings, MN 55033",
        "phone": "(651) 438-4325",
        "housing_court_day": "Tuesday",
    },
    "burnsville": {
        "name": "Dakota County Northern Service Center",
        "address": "1 Mendota Road W, West St. Paul, MN 55118",
        "phone": "(651) 438-4325",
        "housing_court_day": "Thursday",
    },
}

# Dakota County case number patterns (expanded for MCRO)
DAKOTA_COUNTY_CASE_PATTERNS = [
    r"19HA-CV-\d{2}-\d{4,}",  # Standard Housing: 19HA-CV-24-5678
    r"19AV-CV-\d{2}-\d{4,}",  # Alt Housing/Eviction: 19AV-CV-25-3477
    r"19-CV-\d{2}-\d{4,}",    # General Civil: 19-CV-24-5678  
    r"Court\s*File\s*No\.?\s*:?\s*(19[A-Z]{0,2}-CV-\d{2}-\d+)",  # Court File No. format
    r"Dakota\s+County.*Case\s*(?:No\.?|#)?\s*:?\s*([\w\-]+)",
]

# MCRO (Minnesota Court Records Online) Document Patterns
MCRO_PATTERNS = {
    "file_naming": [
        r"MCRO_\d+[A-Z]{0,2}-CV-\d{2}-\d+",  # MCRO_19AV-CV-25-3477
        r"Filed\s+in\s+District\s+Court",
        r"State\s+of\s+Minnesota",
    ],
    "document_types": {
        # === COMPLAINT PATTERNS (most common MCRO download) ===
        "complaint": {
            "patterns": [
                r"complaint\s+(?:for|and|in)",
                r"civil\s+complaint",
                r"eviction\s+complaint",
                r"complaint\s+for\s+(?:eviction|recovery|unlawful)",
                r"plaintiff[s']?\s+complaint",
                r"comes?\s+now\s+(?:the\s+)?plaintiff",
                r"plaintiff\s+(?:hereby\s+)?(?:complains|alleges|states)",
                r"cause[s]?\s+of\s+action",
                r"wherefore[,]?\s+plaintiff",
                r"recovery\s+of\s+(?:premises|possession)",
                r"unlawful\s+detainer",
                r"holdover\s+tenant",
                r"eviction\s+action",
                r"action\s+for\s+(?:eviction|possession)",
                r"demand[s]?\s+judgment",
                r"judgment\s+(?:in\s+favor|against\s+defendant)",
            ],
            "doc_type": DocumentType.COMPLAINT,
        },
        # === SUMMONS PATTERNS ===
        "summons": {
            "patterns": [
                r"summons",
                r"you\s+are\s+(?:hereby\s+)?summoned",
                r"you\s+are\s+being\s+sued",
                r"you\s+must\s+(?:respond|answer|appear)",
                r"failure\s+to\s+(?:respond|answer|appear)",
                r"served\s+with\s+(?:a\s+)?summons",
                r"service\s+(?:of\s+)?summons",
            ],
            "doc_type": DocumentType.SUMMONS,
        },
        # === EVICTION FILING PATTERNS ===
        "eviction_filing": {
            "patterns": [
                r"action\s+for\s+eviction",
                r"eviction\s+(?:case|action|proceeding)",
                r"unlawful\s+detainer\s+(?:action|complaint)",
                r"forcible\s+(?:entry|detainer)",
                r"writ\s+of\s+(?:restitution|recovery)",
                r"order\s+(?:of|for)\s+eviction",
            ],
            "doc_type": DocumentType.EVICTION_FILING,
        },
        "notice_of_motion": {
            "patterns": [
                r"notice\s+of.*motion",
                r"notice\s+of\s+defendant[s']?\s+.*motion",
            ],
            "doc_type": DocumentType.MOTION,
        },
        "motion_to_dismiss": {
            "patterns": [
                r"motion\s+to\s+dismiss",
                r"dismiss\s+without\s+prejudice",
                r"motion.*dismiss.*expunge",
            ],
            "doc_type": DocumentType.MOTION,
        },
        "memorandum_of_law": {
            "patterns": [
                r"memorandum\s+of\s+law",
                r"memorandum\s+in\s+support",
                r"brief\s+in\s+support",
            ],
            "doc_type": DocumentType.MOTION,  # Associated with motions
        },
        "order": {
            "patterns": [
                r"order\s+(?:granting|denying)",
                r"court\s+order",
                r"it\s+is\s+(?:hereby\s+)?ordered",
            ],
            "doc_type": DocumentType.COURT_ORDER,
        },
        "judgment": {
            "patterns": [
                r"judgment\s+(?:for|against)",
                r"default\s+judgment",
                r"judgment\s+is\s+(?:hereby\s+)?entered",
            ],
            "doc_type": DocumentType.JUDGMENT,
        },
        # === ANSWER PATTERNS ===
        "answer": {
            "patterns": [
                r"answer\s+(?:to\s+(?:the\s+)?)?complaint",
                r"defendant[s']?\s+answer",
                r"defendant\s+(?:hereby\s+)?answers",
                r"affirmative\s+defense[s]?",
                r"defendant\s+admits",
                r"defendant\s+denies",
            ],
            "doc_type": DocumentType.ANSWER,
        },
        # === AFFIDAVIT PATTERNS ===
        "affidavit": {
            "patterns": [
                r"affidavit\s+(?:of|in)",
                r"affidavit\s+of\s+(?:service|mailing)",
                r"being\s+(?:first\s+)?duly\s+sworn",
                r"deposes\s+and\s+(?:says|states)",
                r"under\s+penalty\s+of\s+perjury",
            ],
            "doc_type": DocumentType.AFFIDAVIT,
        },
    },
    "legal_services": {
        "smrls": {
            "name": "Southern Minnesota Regional Legal Services",
            "patterns": [r"SMRLS", r"Southern\s+Minnesota\s+Regional\s+Legal"],
            "phone": "651-222-5863",
        },
        "mid_minnesota": {
            "name": "Mid-Minnesota Legal Aid",
            "patterns": [r"Mid-Minnesota\s+Legal", r"MMLA"],
        },
        "volunteer_lawyers": {
            "name": "Volunteer Lawyers Network",
            "patterns": [r"Volunteer\s+Lawyers", r"VLN"],
        },
    },
}

# Minnesota Judicial Branch standard forms
MN_JUDICIAL_FORMS = {
    "HOU101": {"name": "Tenant Rights Brochure", "doc_type": DocumentType.LETTER},
    "HOU201": {"name": "Notice to Quit - Non-Payment", "doc_type": DocumentType.NOTICE_TO_QUIT},
    "HOU202": {"name": "Notice to Quit - Lease Violation", "doc_type": DocumentType.LEASE_VIOLATION},
    "HOU203": {"name": "Notice of Termination", "doc_type": DocumentType.EVICTION_NOTICE},
    "CIV301": {"name": "Answer Form - General", "doc_type": DocumentType.ANSWER},
    "CIV302": {"name": "Motion Form - General", "doc_type": DocumentType.MOTION},
    "CIV401": {"name": "Affidavit Form", "doc_type": DocumentType.AFFIDAVIT},
}


# =============================================================================
# DOCUMENT RECOGNITION ENGINE
# =============================================================================

class DocumentRecognitionEngine:
    """
    Advanced document recognition using multi-layered analysis.
    
    Analysis Layers:
    1. Structural - Header patterns, formatting, signatures
    2. Keyword - Primary and supporting keywords with weights
    3. Context - Surrounding text analysis for disambiguation
    4. Entity - Parties, dates, amounts extraction
    5. Reasoning - Cross-referencing signals for final classification
    """
    
    def __init__(self):
        self.month_map = {
            'january': 1, 'jan': 1, 'february': 2, 'feb': 2, 
            'march': 3, 'mar': 3, 'april': 4, 'apr': 4,
            'may': 5, 'june': 6, 'jun': 6, 'july': 7, 'jul': 7, 
            'august': 8, 'aug': 8, 'september': 9, 'sep': 9, 'sept': 9,
            'october': 10, 'oct': 10, 'november': 11, 'nov': 11, 
            'december': 12, 'dec': 12
        }
    
    def recognize(self, text: str, filename: str = "") -> RecognitionResult:
        """
        Perform full document recognition.
        
        Args:
            text: Full document text
            filename: Original filename (provides hints)
            
        Returns:
            RecognitionResult with classification, entities, and reasoning
        """
        # Normalize text
        text_lower = text.lower()
        filename_lower = filename.lower()
        
        # Initialize result
        result = RecognitionResult(
            category=DocumentCategory.UNKNOWN,
            doc_type=DocumentType.UNKNOWN,
            confidence=0.0,
            title="Unrecognized Document",
            summary="",
        )
        
        # === LAYER 0: Dakota County Form Detection (Fast Path) ===
        dakota_type, form_code, dakota_confidence = self._detect_dakota_county_form(text, filename)
        if dakota_type and dakota_confidence > 0.90:
            # High-confidence Dakota County form - use fast path
            result.doc_type = dakota_type
            result.category = self._get_category(dakota_type)
            result.confidence = dakota_confidence
            result.reasoning_chain.append(f"Dakota County form detected: {form_code}")
            result.signals.append(RecognitionSignal(
                source="dakota_county",
                indicator=f"form_{form_code}",
                weight=dakota_confidence,
                evidence=form_code,
                reasoning=f"Matched Dakota County form {form_code}"
            ))
            # Still extract entities for completeness
            result.dates = self._extract_dates(text)
            result.parties = self._extract_parties(text)
            result.amounts = self._extract_amounts(text)
            result.case_numbers = self._extract_case_numbers(text)
            result.addresses = self._extract_addresses(text)
            result.title, result.summary = self._generate_title_summary(result, text)
            result.key_terms = self._extract_key_terms(text_lower)
            self._analyze_urgency(result)
            return result
        
        # === LAYER 0.5: MCRO Document Detection (Minnesota Courts) ===
        mcro_result = self._detect_mcro_document(text, filename)
        if mcro_result:
            mcro_type, mcro_confidence, mcro_evidence = mcro_result
            if mcro_confidence > 0.85:
                # High-confidence MCRO detection
                result.doc_type = mcro_type
                result.category = self._get_category(mcro_type)
                result.confidence = mcro_confidence
                result.reasoning_chain.append(f"MCRO document detected: {mcro_type.value}")
                result.signals.append(RecognitionSignal(
                    source="mcro",
                    indicator=f"mcro_{mcro_type.value}",
                    weight=mcro_confidence,
                    evidence=mcro_evidence,
                    reasoning=f"Matched MCRO document pattern: {mcro_evidence}"
                ))
                # Extract entities
                result.dates = self._extract_dates(text)
                result.parties = self._extract_parties(text)
                result.amounts = self._extract_amounts(text)
                result.case_numbers = self._extract_case_numbers(text)
                result.addresses = self._extract_addresses(text)
                result.title, result.summary = self._generate_title_summary(result, text)
                result.key_terms = self._extract_key_terms(text_lower)
                self._analyze_urgency(result)
                return result
        
        # === LAYER 1: Structural Analysis ===
        structural_signals = self._analyze_structure(text)
        result.signals.extend(structural_signals)
        
        # === LAYER 2: Keyword Analysis ===
        keyword_signals, type_scores = self._analyze_keywords(text_lower)
        result.signals.extend(keyword_signals)
        
        # Boost scores if Dakota County form was partially detected
        if dakota_type and dakota_confidence > 0.5:
            if dakota_type in type_scores:
                type_scores[dakota_type] += dakota_confidence
            else:
                type_scores[dakota_type] = dakota_confidence
            result.signals.append(RecognitionSignal(
                source="dakota_county",
                indicator=f"form_hint_{form_code}",
                weight=dakota_confidence,
                evidence=form_code,
                reasoning=f"Partial match for Dakota County form {form_code}"
            ))
        
        # === LAYER 3: Context Analysis ===
        context_signals = self._analyze_context(text_lower, type_scores)
        result.signals.extend(context_signals)
        
        # === LAYER 4: Entity Extraction ===
        result.dates = self._extract_dates(text)
        result.parties = self._extract_parties(text)
        result.amounts = self._extract_amounts(text)
        result.case_numbers = self._extract_case_numbers(text)
        result.addresses = self._extract_addresses(text)
        
        # Add entity signals
        entity_signals = self._generate_entity_signals(result)
        result.signals.extend(entity_signals)
        
        # === LAYER 5: Reasoning & Final Classification ===
        best_type, confidence, reasoning = self._reason_classification(
            type_scores, result.signals, text_lower, filename_lower
        )
        
        result.doc_type = best_type
        result.category = self._get_category(best_type)
        result.confidence = confidence
        result.reasoning_chain = reasoning
        
        # Generate title and summary
        result.title, result.summary = self._generate_title_summary(result, text)
        
        # Extract key terms for law matching
        result.key_terms = self._extract_key_terms(text_lower)
        
        # Analyze urgency
        self._analyze_urgency(result)
        
        return result
    
    def _detect_dakota_county_form(self, text: str, filename: str = "") -> tuple[DocumentType | None, str, float]:
        """
        Detect if document is a Dakota County court form.
        
        Returns:
            Tuple of (doc_type, form_code, confidence) or (None, "", 0.0)
        """
        text_upper = text.upper()
        
        # Check for Dakota County case numbers first
        for pattern in DAKOTA_COUNTY_CASE_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                # Found Dakota County case - now check for specific forms
                for form_code, form_info in DAKOTA_COUNTY_FORMS.items():
                    for form_pattern in form_info["patterns"]:
                        if re.search(form_pattern, text, re.IGNORECASE):
                            return (
                                form_info["doc_type"],
                                form_code,
                                0.95  # High confidence for explicit form match
                            )
        
        # Check for explicit form codes in text or filename
        combined = f"{text_upper} {filename.upper()}"
        for form_code, form_info in DAKOTA_COUNTY_FORMS.items():
            if form_code in combined:
                return (form_info["doc_type"], form_code, 0.98)
        
        # Check MN Judicial Branch forms
        for form_code, form_info in MN_JUDICIAL_FORMS.items():
            if form_code in combined:
                return (form_info["doc_type"], form_code, 0.95)
        
        # Check for First Judicial District / Dakota County indicators
        if re.search(r"first\s+judicial\s+district", text, re.IGNORECASE):
            if re.search(r"dakota\s+county", text, re.IGNORECASE):
                # Dakota County court document - try to infer type
                for form_code, form_info in DAKOTA_COUNTY_FORMS.items():
                    for pattern in form_info["patterns"]:
                        if re.search(pattern, text, re.IGNORECASE):
                            return (form_info["doc_type"], form_code, 0.85)
        
        return (None, "", 0.0)
    
    def _detect_mcro_document(self, text: str, filename: str = "") -> tuple | None:
        """
        Detect MCRO (Minnesota Court Records Online) documents.
        
        These documents have specific patterns from the MN court system.
        MCRO documents are typically downloaded from: https://publicaccess.courts.state.mn.us/
        
        Returns:
            Tuple of (DocumentType, confidence, evidence) or None
        """
        text_lower = text.lower()
        filename_lower = filename.lower()
        
        # Check for MCRO filename pattern (e.g., MCRO_19AV-CV-25-3477.pdf)
        mcro_filename = bool(re.search(r"mcro[_-]?\d*[a-z]{0,2}[-_]?cv[-_]?\d{2}[-_]?\d+", filename_lower))
        
        # Alternative MCRO indicators in filename
        if not mcro_filename:
            mcro_filename = "mcro" in filename_lower or "mncourts" in filename_lower
        
        # Check for Minnesota court markers
        mn_court_markers = [
            (r"state\s+of\s+minnesota", 0.4),
            (r"court\s+file\s+(?:no\.?|number)", 0.5),
            (r"district\s+court", 0.4),
            (r"first\s+judicial\s+district", 0.5),
            (r"second\s+judicial\s+district", 0.5),
            (r"third\s+judicial\s+district", 0.5),
            (r"fourth\s+judicial\s+district", 0.5),  # Hennepin
            (r"fifth\s+judicial\s+district", 0.5),
            (r"sixth\s+judicial\s+district", 0.5),
            (r"seventh\s+judicial\s+district", 0.5),
            (r"eighth\s+judicial\s+district", 0.5),
            (r"ninth\s+judicial\s+district", 0.5),
            (r"tenth\s+judicial\s+district", 0.5),
            (r"dakota\s+county", 0.4),
            (r"hennepin\s+county", 0.4),
            (r"ramsey\s+county", 0.4),
            (r"anoka\s+county", 0.4),
            (r"washington\s+county", 0.4),
            (r"scott\s+county", 0.4),
            (r"carver\s+county", 0.4),
            (r"filed\s+(?:in\s+)?district\s+court", 0.6),
            (r"\d{2}[-]?[a-z]{2}[-]?\d{2}[-]?\d{3,}", 0.5),  # Case number pattern like 27-CV-24-12345
            (r"minnesota\s+(?:rules?\s+of\s+)?(?:civil|court)", 0.4),
        ]
        
        mn_score = 0.0
        mn_evidence = []
        for pattern, weight in mn_court_markers:
            if re.search(pattern, text_lower):
                mn_score += weight
                mn_evidence.append(pattern)
        
        # If MCRO filename, boost the score significantly
        if mcro_filename:
            mn_score += 0.5
            mn_evidence.append("mcro_filename")
        
        # Need some MN court context to proceed
        if mn_score < 0.4:
            return None
        
        # Now check MCRO document types
        best_match = None
        best_confidence = 0.0
        
        for doc_type_name, doc_info in MCRO_PATTERNS.get("document_types", {}).items():
            for pattern in doc_info["patterns"]:
                match = re.search(pattern, text_lower)
                if match:
                    base_confidence = 0.70
                    # Boost for MCRO filename
                    if mcro_filename:
                        base_confidence += 0.15
                    # Boost for MN court markers
                    base_confidence += min(mn_score * 0.08, 0.12)
                    
                    if base_confidence > best_confidence:
                        best_match = (
                            doc_info["doc_type"],
                            min(base_confidence, 0.98),
                            f"{doc_type_name}: {match.group(0)[:50]}"
                        )
                        best_confidence = base_confidence
        
        if best_match:
            return best_match
        
        # If we have MCRO filename or strong MN markers but couldn't detect type
        if mcro_filename or mn_score >= 0.8:
            # Look at filename for hints
            if "motion" in filename_lower:
                return (DocumentType.MOTION, 0.85, "MCRO filename contains 'motion'")
            if "order" in filename_lower:
                return (DocumentType.COURT_ORDER, 0.85, "MCRO filename contains 'order'")
            if "judgment" in filename_lower:
                return (DocumentType.JUDGMENT, 0.85, "MCRO filename contains 'judgment'")
            if "summons" in filename_lower:
                return (DocumentType.SUMMONS, 0.85, "MCRO filename contains 'summons'")
            if "complaint" in filename_lower:
                return (DocumentType.COMPLAINT, 0.85, "MCRO filename contains 'complaint'")
            if "answer" in filename_lower:
                return (DocumentType.ANSWER, 0.85, "MCRO filename contains 'answer'")
            if "affidavit" in filename_lower:
                return (DocumentType.AFFIDAVIT, 0.85, "MCRO filename contains 'affidavit'")
            
            # High confidence MN document but couldn't determine type - try content analysis
            if "plaintiff" in text_lower and ("complaint" in text_lower or "wherefore" in text_lower):
                return (DocumentType.COMPLAINT, 0.80, "MN court doc with complaint indicators")
            if "summon" in text_lower or "you are being sued" in text_lower:
                return (DocumentType.SUMMONS, 0.80, "MN court doc with summons indicators")
            if "ordered" in text_lower and "court" in text_lower:
                return (DocumentType.COURT_ORDER, 0.75, "MN court doc with order indicators")
            
            # Generic court filing fallback
            return (DocumentType.COMPLAINT, 0.65, f"Minnesota court document (score: {mn_score:.2f})")
        
        return None
    
    def _analyze_structure(self, text: str) -> list[RecognitionSignal]:
        """Layer 1: Analyze document structure."""
        signals = []
        
        # Check for court document structure
        for pattern_name, patterns in COURT_STRUCTURE_PATTERNS.items():
            for pattern in patterns:
                match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
                if match:
                    signals.append(RecognitionSignal(
                        source="structure",
                        indicator=f"court_{pattern_name}",
                        weight=0.6,
                        evidence=match.group(0)[:100],
                        reasoning=f"Document has court {pattern_name} structure"
                    ))
        
        # Check for formal letter structure
        if re.search(r'^Dear\s+', text, re.MULTILINE | re.IGNORECASE):
            signals.append(RecognitionSignal(
                source="structure",
                indicator="letter_salutation",
                weight=0.4,
                evidence="Dear...",
                reasoning="Document begins with letter salutation"
            ))
        
        # Check for legal document numbering
        if re.search(r'^\s*\d+\.\s+[A-Z]', text, re.MULTILINE):
            signals.append(RecognitionSignal(
                source="structure",
                indicator="numbered_paragraphs",
                weight=0.5,
                evidence="Numbered paragraphs",
                reasoning="Document uses legal-style numbered paragraphs"
            ))
        
        # Check for signature lines
        if re.search(r'_{3,}\s*$', text, re.MULTILINE):
            signals.append(RecognitionSignal(
                source="structure",
                indicator="signature_line",
                weight=0.3,
                evidence="___________",
                reasoning="Document has signature lines"
            ))
        
        return signals
    
    def _analyze_keywords(self, text_lower: str) -> Tuple[list[RecognitionSignal], dict]:
        """Layer 2: Analyze keywords with weights."""
        signals = []
        type_scores = {doc_type: 0.0 for doc_type in DocumentType}
        
        for doc_type, patterns in DOCUMENT_PATTERNS.items():
            type_score = 0.0
            found_primary = False
            
            # Check primary keywords (high weight)
            for keyword, weight in patterns["primary_keywords"]:
                if keyword in text_lower:
                    found_primary = True
                    type_score += weight
                    signals.append(RecognitionSignal(
                        source="keyword",
                        indicator=f"primary:{keyword}",
                        weight=weight,
                        evidence=self._get_keyword_context(text_lower, keyword),
                        reasoning=f"Primary keyword '{keyword}' strongly indicates {doc_type.value}"
                    ))
            
            # Check supporting keywords (only if primary found or as weak signal)
            for keyword, weight in patterns["supporting_keywords"]:
                if keyword in text_lower:
                    # Lower weight if no primary keyword found
                    actual_weight = weight if found_primary else weight * 0.3
                    type_score += actual_weight
                    
                    if found_primary:  # Only add signal if meaningful
                        signals.append(RecognitionSignal(
                            source="keyword",
                            indicator=f"supporting:{keyword}",
                            weight=actual_weight,
                            evidence=self._get_keyword_context(text_lower, keyword),
                            reasoning=f"Supporting keyword '{keyword}' reinforces {doc_type.value}"
                        ))
            
            type_scores[doc_type] = type_score
        
        return signals, type_scores
    
    def _get_keyword_context(self, text: str, keyword: str, window: int = 50) -> str:
        """Get surrounding context for a keyword."""
        pos = text.find(keyword)
        if pos == -1:
            return keyword
        start = max(0, pos - window)
        end = min(len(text), pos + len(keyword) + window)
        context = text[start:end].replace('\n', ' ').strip()
        return f"...{context}..."
    
    def _analyze_context(self, text_lower: str, type_scores: dict) -> list[RecognitionSignal]:
        """Layer 3: Context analysis for disambiguation."""
        signals = []
        
        # Get top candidates
        top_types = sorted(type_scores.items(), key=lambda x: x[1], reverse=True)[:3]
        
        for doc_type, score in top_types:
            if score <= 0:
                continue
                
            patterns = DOCUMENT_PATTERNS.get(doc_type, {})
            context_reqs = patterns.get("context_requirements", [])
            
            # Check if context requirements are met
            reqs_met = sum(1 for req in context_reqs if req in text_lower)
            if context_reqs:
                context_ratio = reqs_met / len(context_reqs)
                
                if context_ratio >= 0.5:
                    signals.append(RecognitionSignal(
                        source="context",
                        indicator=f"context_match:{doc_type.value}",
                        weight=0.4 * context_ratio,
                        evidence=f"Met {reqs_met}/{len(context_reqs)} context requirements",
                        reasoning=f"Document context supports {doc_type.value} classification"
                    ))
                else:
                    signals.append(RecognitionSignal(
                        source="context",
                        indicator=f"context_mismatch:{doc_type.value}",
                        weight=-0.2,
                        evidence=f"Only met {reqs_met}/{len(context_reqs)} context requirements",
                        reasoning=f"Weak context support for {doc_type.value}"
                    ))
        
        return signals
    
    def _extract_dates(self, text: str) -> list[ExtractedEntity]:
        """Extract dates with context labels."""
        dates = []
        
        # Pattern definitions
        date_patterns = [
            # Month DD, YYYY
            (r'\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{4})\b', 'long'),
            # Month DD YYYY (no comma)
            (r'\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\.?\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{4})\b', 'short_month'),
            # MM/DD/YYYY
            (r'\b(\d{1,2})/(\d{1,2})/(\d{4})\b', 'slash'),
            # MM-DD-YYYY
            (r'\b(\d{1,2})-(\d{1,2})-(\d{4})\b', 'dash'),
            # YYYY-MM-DD (ISO)
            (r'\b(\d{4})-(\d{2})-(\d{2})\b', 'iso'),
        ]
        
        found_dates = set()
        
        for pattern, fmt in date_patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                try:
                    if fmt == 'long':
                        month = self.month_map[match.group(1).lower()]
                        day = int(match.group(2))
                        year = int(match.group(3))
                    elif fmt == 'short_month':
                        month = self.month_map[match.group(1).lower().rstrip('.')]
                        day = int(match.group(2))
                        year = int(match.group(3))
                    elif fmt == 'slash' or fmt == 'dash':
                        month = int(match.group(1))
                        day = int(match.group(2))
                        year = int(match.group(3))
                    else:  # iso
                        year = int(match.group(1))
                        month = int(match.group(2))
                        day = int(match.group(3))
                    
                    # Validate date
                    if not (1 <= month <= 12 and 1 <= day <= 31 and 1900 <= year <= 2100):
                        continue
                    
                    date_str = f"{year:04d}-{month:02d}-{day:02d}"
                    if date_str in found_dates:
                        continue
                    found_dates.add(date_str)
                    
                    # Get context to determine label
                    start = max(0, match.start() - 100)
                    end = min(len(text), match.end() + 50)
                    context = text[start:end].lower()
                    
                    label = self._determine_date_label(context)
                    confidence = 0.9 if fmt in ('long', 'iso') else 0.8
                    
                    dates.append(ExtractedEntity(
                        entity_type="date",
                        value=match.group(0),
                        normalized=date_str,
                        context_label=label,
                        confidence=confidence,
                        source_text=context,
                        position=match.start()
                    ))
                except (ValueError, KeyError):
                    continue
        
        # Sort by position in document
        dates.sort(key=lambda x: x.position)
        return dates
    
    def _determine_date_label(self, context: str) -> str:
        """Determine what a date represents based on context."""
        # High priority labels (specific meanings)
        labels = [
            (["filed", "filing date", "date filed"], "Filing Date"),
            (["hearing", "court date", "appear", "trial"], "Court Hearing Date"),
            (["deadline", "must respond", "response due", "answer by"], "Response Deadline"),
            (["vacate", "move out", "leave", "quit"], "Move-Out Date"),
            (["writ", "execution", "sheriff"], "Enforcement Date"),
            (["judgment", "entered", "awarded"], "Judgment Date"),
            (["lease begin", "start date", "commence", "effective"], "Lease Start Date"),
            (["lease end", "expir", "terminat", "ending"], "Lease End Date"),
            (["rent due", "payment due", "due date"], "Payment Due Date"),
            (["served", "service date", "service of"], "Service Date"),
            (["dated", "this", "signed"], "Document Date"),
            (["notice", "notified"], "Notice Date"),
        ]
        
        for keywords, label in labels:
            if any(kw in context for kw in keywords):
                return label
        
        return "Date Referenced"
    
    def _extract_parties(self, text: str) -> list[ExtractedEntity]:
        """Extract party names with roles."""
        parties = []
        
        # Patterns for party extraction
        party_patterns = [
            # Court case parties
            (r'(?:PLAINTIFF|Plaintiff)[:\s,]*([A-Z][A-Za-z\s,\.]+?)(?:\n|,\s*(?:v\.?|vs\.?))', 'Plaintiff/Landlord'),
            (r'(?:DEFENDANT|Defendant)[:\s,]*([A-Z][A-Za-z\s,\.]+?)(?:\n|$)', 'Defendant/Tenant'),
            (r'(?:PETITIONER|Petitioner)[:\s,]*([A-Z][A-Za-z\s,\.]+?)(?:\n|,)', 'Petitioner'),
            (r'(?:RESPONDENT|Respondent)[:\s,]*([A-Z][A-Za-z\s,\.]+?)(?:\n|$)', 'Respondent'),
            
            # Lease parties
            (r'(?:LANDLORD|Landlord|LESSOR|Lessor)[:\s]+([A-Z][A-Za-z\s,\.]+?)(?:\n|,|;)', 'Landlord'),
            (r'(?:TENANT|Tenant|LESSEE|Lessee|RENTER|Renter)[:\s]+([A-Z][A-Za-z\s,\.]+?)(?:\n|,|;)', 'Tenant'),
            (r'(?:PROPERTY MANAGER|Property Manager|AGENT|Agent)[:\s]+([A-Z][A-Za-z\s,\.]+?)(?:\n|,|;)', 'Property Manager'),
            
            # Attorney
            (r'(?:Attorney for \w+)[:\s]+([A-Z][A-Za-z\s,\.]+?)(?:\n|Bar)', 'Attorney'),
        ]
        
        for pattern, role in party_patterns:
            for match in re.finditer(pattern, text, re.MULTILINE):
                name = match.group(1).strip().rstrip(',.')
                # Clean up name
                name = re.sub(r'\s+', ' ', name)
                
                if len(name) > 2 and len(name) < 80:
                    # Avoid duplicates
                    if not any(p.value == name for p in parties):
                        parties.append(ExtractedEntity(
                            entity_type="party",
                            value=name,
                            context_label=role,
                            confidence=0.85,
                            source_text=match.group(0),
                            position=match.start()
                        ))
        
        return parties
    
    def _extract_amounts(self, text: str) -> list[ExtractedEntity]:
        """Extract monetary amounts with context."""
        amounts = []
        
        # Amount patterns
        amount_patterns = [
            r'\$\s*([\d,]+\.?\d*)',
            r'([\d,]+\.?\d*)\s*(?:dollars?|USD)',
        ]
        
        found_amounts = set()
        
        for pattern in amount_patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                try:
                    amount_str = match.group(1).replace(',', '')
                    amount = float(amount_str)
                    
                    # Skip unrealistic amounts
                    if amount <= 0 or amount > 10000000:
                        continue
                    
                    # Avoid duplicates
                    if amount in found_amounts:
                        continue
                    found_amounts.add(amount)
                    
                    # Get context
                    start = max(0, match.start() - 80)
                    end = min(len(text), match.end() + 40)
                    context = text[start:end].lower()
                    
                    label = self._determine_amount_label(context, amount)
                    
                    amounts.append(ExtractedEntity(
                        entity_type="amount",
                        value=f"${amount:,.2f}",
                        normalized=str(amount),
                        context_label=label,
                        confidence=0.9,
                        source_text=context,
                        position=match.start()
                    ))
                except ValueError:
                    continue
        
        # Sort by amount (largest first, usually most important)
        amounts.sort(key=lambda x: float(x.normalized or 0), reverse=True)
        return amounts
    
    def _determine_amount_label(self, context: str, amount: float) -> str:
        """Determine what an amount represents."""
        labels = [
            (["judgment", "awarded", "damages", "adjudged"], "Judgment Amount"),
            (["rent due", "monthly rent", "rent amount", "rent owed", "past due rent"], "Rent"),
            (["security deposit", "deposit"], "Security Deposit"),
            (["late fee", "late charge", "penalty"], "Late Fee"),
            (["attorney", "legal", "court cost", "filing fee", "attorney fee"], "Legal Costs"),
            (["repair", "damage", "cleaning"], "Damages/Repairs"),
            (["owed", "due", "balance", "arrears", "total due", "amount owed"], "Amount Owed"),
            (["paid", "payment", "received", "amount paid"], "Payment Amount"),
        ]
        
        for keywords, label in labels:
            if any(kw in context for kw in keywords):
                return label
        
        # Heuristic based on amount - be more generous with Rent detection
        if 400 <= amount <= 4000:
            # Check for rent context clues
            if "month" in context or "due" in context or "rent" in context:
                return "Rent"
            return "Amount"
        elif amount > 4000:
            return "Significant Amount"
        elif amount < 200:
            return "Fee/Charge"
        
        return "Amount"
    
    def _extract_case_numbers(self, text: str) -> list[ExtractedEntity]:
        """Extract court case numbers."""
        case_numbers = []
        
        patterns = [
            # Minnesota format: 19AV-CV-25-3477
            (r'\b(\d{2}[A-Z]{2}[-\s]?[A-Z]{2}[-\s]?\d{2,4}[-\s]?\d+)\b', 'MN Format'),
            # General: Case No. 12345
            (r'(?:Case|File)\s*(?:No\.?|Number|#)\s*:?\s*([A-Z0-9\-]+)', 'General'),
            # Civil case: CV-2025-1234
            (r'\b(CV[-\s]?\d{4}[-\s]?\d+)\b', 'Civil'),
        ]
        
        for pattern, fmt in patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                case_num = match.group(1).strip()
                if len(case_num) >= 5:
                    case_numbers.append(ExtractedEntity(
                        entity_type="case_number",
                        value=case_num,
                        context_label=f"Case Number ({fmt})",
                        confidence=0.95,
                        position=match.start()
                    ))
        
        return case_numbers
    
    def _extract_addresses(self, text: str) -> list[ExtractedEntity]:
        """Extract property addresses."""
        addresses = []
        
        # Address pattern - require street type and filter short matches
        pattern = r'\b(\d+\s+[\w\s]+(?:Street|St|Avenue|Ave|Road|Rd|Drive|Dr|Lane|Ln|Court|Ct|Boulevard|Blvd|Way|Circle|Cir)\.?(?:\s*(?:,\s*)?(?:Apt|Unit|Suite|#)\s*[\w\d]+)?)\b'
        
        for match in re.finditer(pattern, text, re.IGNORECASE):
            addr = match.group(1).strip()
            # Must be reasonable length and contain a number at start
            if len(addr) > 15 and addr[0].isdigit():
                # Avoid things that look like dates or phone numbers
                if not re.match(r'^\d{4}\s', addr):  # Skip if starts with 4-digit year
                    # Get context to determine if it's the property address
                    start = max(0, match.start() - 50)
                    context = text[start:match.start()].lower()
                    
                    label = "Address"
                    if "property" in context or "premises" in context:
                        label = "Property Address"
                    elif "landlord" in context or "owner" in context:
                        label = "Landlord Address"
                    elif "tenant" in context:
                        label = "Tenant Address"
                    
                    # Avoid duplicates
                    if not any(a.value == addr for a in addresses):
                        addresses.append(ExtractedEntity(
                            entity_type="address",
                            value=addr,
                            context_label=label,
                            confidence=0.8,
                            position=match.start()
                        ))
        
        return addresses
    
    def _generate_entity_signals(self, result: RecognitionResult) -> list[RecognitionSignal]:
        """Generate signals based on extracted entities."""
        signals = []
        
        # Case number strongly indicates court document
        if result.case_numbers:
            signals.append(RecognitionSignal(
                source="entity",
                indicator="has_case_number",
                weight=0.7,
                evidence=result.case_numbers[0].value,
                reasoning="Document contains court case number"
            ))
        
        # Multiple parties with plaintiff/defendant roles
        plaintiff_found = any('plaintiff' in p.context_label.lower() for p in result.parties)
        defendant_found = any('defendant' in p.context_label.lower() for p in result.parties)
        if plaintiff_found and defendant_found:
            signals.append(RecognitionSignal(
                source="entity",
                indicator="has_court_parties",
                weight=0.6,
                evidence="Plaintiff and Defendant identified",
                reasoning="Document has court case party structure"
            ))
        
        # Deadline dates
        deadline_dates = [d for d in result.dates if 'deadline' in d.context_label.lower()]
        if deadline_dates:
            signals.append(RecognitionSignal(
                source="entity",
                indicator="has_deadline",
                weight=0.5,
                evidence=deadline_dates[0].value,
                reasoning="Document contains response deadline"
            ))
        
        # Judgment amounts
        judgment_amounts = [a for a in result.amounts if 'judgment' in a.context_label.lower()]
        if judgment_amounts:
            signals.append(RecognitionSignal(
                source="entity",
                indicator="has_judgment_amount",
                weight=0.6,
                evidence=judgment_amounts[0].value,
                reasoning="Document contains judgment amount"
            ))
        
        return signals
    
    def _reason_classification(
        self,
        type_scores: dict,
        signals: list[RecognitionSignal],
        text_lower: str,
        filename_lower: str
    ) -> Tuple[DocumentType, float, list[str]]:
        """
        Layer 5: Apply reasoning logic to determine final classification.
        
        This layer cross-references all signals and applies logical rules
        to arrive at the most accurate classification.
        """
        reasoning = []
        
        # Calculate weighted scores from signals
        signal_boost = {doc_type: 0.0 for doc_type in DocumentType}
        
        for signal in signals:
            # Structure signals boost court documents
            if signal.source == "structure" and "court" in signal.indicator:
                for dt in [DocumentType.SUMMONS, DocumentType.COMPLAINT, DocumentType.JUDGMENT, 
                          DocumentType.COURT_ORDER, DocumentType.MOTION, DocumentType.WRIT]:
                    signal_boost[dt] += signal.weight * 0.5
            
            # Entity signals
            if signal.indicator == "has_case_number":
                for dt in [DocumentType.SUMMONS, DocumentType.COMPLAINT, DocumentType.JUDGMENT,
                          DocumentType.COURT_ORDER, DocumentType.MOTION, DocumentType.WRIT,
                          DocumentType.ANSWER, DocumentType.EVICTION_FILING]:
                    signal_boost[dt] += signal.weight
            
            if signal.indicator == "has_court_parties":
                for dt in [DocumentType.COMPLAINT, DocumentType.SUMMONS, DocumentType.ANSWER]:
                    signal_boost[dt] += signal.weight
            
            if signal.indicator == "has_judgment_amount":
                signal_boost[DocumentType.JUDGMENT] += signal.weight
            
            if signal.indicator == "has_deadline":
                signal_boost[DocumentType.SUMMONS] += signal.weight * 0.5
        
        # Combine scores
        final_scores = {}
        for doc_type in DocumentType:
            base_score = type_scores.get(doc_type, 0)
            boost = signal_boost.get(doc_type, 0)
            final_scores[doc_type] = base_score + boost
        
        # Apply filename hints
        filename_hints = {
            'summons': DocumentType.SUMMONS,
            'complaint': DocumentType.COMPLAINT,
            'judgment': DocumentType.JUDGMENT,
            'order': DocumentType.COURT_ORDER,
            'motion': DocumentType.MOTION,
            'writ': DocumentType.WRIT,
            'lease': DocumentType.LEASE,
            'notice': DocumentType.EVICTION_NOTICE,
            'receipt': DocumentType.RECEIPT,
            'inspection': DocumentType.INSPECTION,
        }
        
        for hint, doc_type in filename_hints.items():
            if hint in filename_lower:
                final_scores[doc_type] += 0.5
                reasoning.append(f"Filename suggests {doc_type.value}")
        
        # Get top candidates
        sorted_types = sorted(final_scores.items(), key=lambda x: x[1], reverse=True)
        best_type, best_score = sorted_types[0]
        second_type, second_score = sorted_types[1] if len(sorted_types) > 1 else (DocumentType.UNKNOWN, 0)
        
        # Calculate confidence
        if best_score <= 0:
            confidence = 0.1
            best_type = DocumentType.UNKNOWN
            reasoning.append("No strong classification signals found")
        elif second_score > 0 and second_type is not None:
            # Confidence based on margin between top two
            margin = best_score - second_score
            # Improved confidence calculation - higher baseline for strong matches
            base_confidence = 0.6 if best_score > 3 else 0.5
            confidence = min(0.95, base_confidence + (margin / (best_score + 0.1)) * 0.4)
            reasoning.append(f"Best match: {best_type.value} (score: {best_score:.2f})")
            reasoning.append(f"Second best: {second_type.value} (score: {second_score:.2f})")
            reasoning.append(f"Confidence margin: {margin:.2f}")
        else:
            confidence = min(0.9, 0.5 + best_score * 0.2)
            reasoning.append(f"Clear match: {best_type.value} (score: {best_score:.2f})")
        
        # Add signal summary to reasoning
        strong_signals = [s for s in signals if s.weight >= 0.7]
        if strong_signals:
            reasoning.append(f"Strong signals: {', '.join(s.indicator for s in strong_signals[:3])}")
        
        return best_type, round(confidence, 3), reasoning
    
    def _get_category(self, doc_type: DocumentType) -> DocumentCategory:
        """Get category for a document type."""
        patterns = DOCUMENT_PATTERNS.get(doc_type)
        if patterns:
            return patterns.get("category", DocumentCategory.UNKNOWN)
        return DocumentCategory.UNKNOWN
    
    def _generate_title_summary(self, result: RecognitionResult, text: str) -> Tuple[str, str]:
        """Generate human-readable title and summary."""
        
        # Title templates
        titles = {
            DocumentType.SUMMONS: "Court Summons",
            DocumentType.COMPLAINT: "Civil Complaint",
            DocumentType.EVICTION_FILING: "Eviction Action Filing",
            DocumentType.JUDGMENT: "Court Judgment",
            DocumentType.WRIT: "Writ of Restitution",
            DocumentType.COURT_ORDER: "Court Order",
            DocumentType.MOTION: "Court Motion",
            DocumentType.ANSWER: "Answer to Complaint",
            DocumentType.AFFIDAVIT: "Affidavit",
            DocumentType.LEASE: "Lease Agreement",
            DocumentType.EVICTION_NOTICE: "Eviction Notice",
            DocumentType.NOTICE_TO_QUIT: "Pay or Quit Notice",
            DocumentType.RENT_INCREASE: "Rent Increase Notice",
            DocumentType.LATE_NOTICE: "Late Rent Notice",
            DocumentType.LEASE_VIOLATION: "Lease Violation Notice",
            DocumentType.RECEIPT: "Payment Receipt",
            DocumentType.DEPOSIT_STATEMENT: "Security Deposit Statement",
            DocumentType.INSPECTION: "Inspection Report",
            DocumentType.REPAIR_REQUEST: "Repair Request",
        }
        
        title = titles.get(result.doc_type, "Document")
        
        # Add case number if available
        if result.case_numbers:
            title = f"{title} - Case {result.case_numbers[0].value}"
        
        # Generate summary based on document type
        summaries = {
            DocumentType.SUMMONS: "This is a court summons requiring you to appear in court or respond to a lawsuit. "
                                  "You MUST respond within the deadline specified or a default judgment may be entered against you.",
            
            DocumentType.COMPLAINT: "This is a legal complaint filed against you outlining the claims being made. "
                                    "Review the allegations carefully and consider seeking legal help.",
            
            DocumentType.EVICTION_FILING: "This is an eviction lawsuit filed with the court. The landlord is seeking "
                                          "to remove you from the property through legal process. You have the right to respond.",
            
            DocumentType.JUDGMENT: "This is a court judgment. If entered against you, you may be required to pay money "
                                   "or vacate the property. Review appeal options with an attorney.",
            
            DocumentType.WRIT: "This is a writ of restitution authorizing the sheriff to remove you from the property. "
                              "This typically means you must vacate immediately.",
            
            DocumentType.COURT_ORDER: "This is an order from the court. You are required to comply with its terms.",
            
            DocumentType.LEASE: "This is a rental/lease agreement. Review all terms carefully before signing.",
            
            DocumentType.EVICTION_NOTICE: "This is a notice from your landlord regarding eviction. "
                                          "Review the notice period and your rights under Minnesota law.",
            
            DocumentType.NOTICE_TO_QUIT: "This is a notice requiring you to pay overdue rent or vacate. "
                                         "In Minnesota, you typically have 14 days to pay before eviction can be filed.",
            
            DocumentType.RECEIPT: "This is a payment receipt documenting a rent or deposit payment. "
                                  "Keep this document as proof of payment.",
            
            DocumentType.DEPOSIT_STATEMENT: "This is a security deposit statement showing deductions and balance. "
                                            "Review for accuracy within 21 days of move-out.",
        }
        
        summary = summaries.get(result.doc_type, "Document has been analyzed.")
        
        # Add deadline warning if applicable
        deadline_dates = [d for d in result.dates if 'deadline' in d.context_label.lower()]
        if deadline_dates:
            summary += f" IMPORTANT: Response deadline appears to be {deadline_dates[0].value}."
        
        # Add judgment amount if applicable
        if result.doc_type == DocumentType.JUDGMENT:
            judgment_amounts = [a for a in result.amounts if 'judgment' in a.context_label.lower()]
            if judgment_amounts:
                summary += f" Judgment amount: {judgment_amounts[0].value}."
        
        return title, summary
    
    def _extract_key_terms(self, text_lower: str) -> list[str]:
        """Extract key legal terms for law matching."""
        terms = []
        
        legal_terms = [
            "unlawful detainer", "eviction", "possession", "writ of restitution",
            "default judgment", "summary judgment", "service of process",
            "security deposit", "habitability", "reasonable notice",
            "quiet enjoyment", "lease violation", "breach of lease",
            "tenant rights", "landlord obligations", "constructive eviction",
            "retaliation", "discrimination", "reasonable accommodation",
            "lead paint", "mold", "bedbugs", "repairs",
        ]
        
        for term in legal_terms:
            if term in text_lower:
                terms.append(term.title())
        
        # Check for MN statute references
        for statute_num, statute_name in MN_LEGAL_TERMS["statutes"]:
            if statute_num.lower() in text_lower:
                terms.append(f"MN Stat. {statute_num}")
        
        return terms[:15]  # Limit to top 15
    
    def _analyze_urgency(self, result: RecognitionResult):
        """Analyze document urgency based on content."""
        from datetime import date
        
        today = date.today()
        
        # Check for deadlines
        for d in result.dates:
            if 'deadline' in d.context_label.lower() or 'respond' in d.context_label.lower():
                if d.normalized is None:
                    continue
                try:
                    parts = d.normalized.split('-')
                    deadline = date(int(parts[0]), int(parts[1]), int(parts[2]))
                    days_left = (deadline - today).days
                    
                    result.has_deadline = True
                    result.deadline_date = d.normalized
                    result.days_to_respond = days_left
                    
                    if days_left < 0:
                        result.urgency_level = "critical"
                    elif days_left <= 3:
                        result.urgency_level = "critical"
                    elif days_left <= 7:
                        result.urgency_level = "high"
                    elif days_left <= 14:
                        result.urgency_level = "normal"
                    else:
                        result.urgency_level = "low"
                    break
                except:
                    continue
        
        # Court documents are generally high priority
        if result.category == DocumentCategory.COURT and result.urgency_level == "normal":
            result.urgency_level = "high"
        
        # Writs are always critical
        if result.doc_type == DocumentType.WRIT:
            result.urgency_level = "critical"


# =============================================================================
# SINGLETON & INTEGRATION
# =============================================================================

_recognition_engine: Optional[DocumentRecognitionEngine] = None


def get_recognition_engine() -> DocumentRecognitionEngine:
    """Get or create recognition engine singleton."""
    global _recognition_engine
    if _recognition_engine is None:
        _recognition_engine = DocumentRecognitionEngine()
    return _recognition_engine


def recognize_document(text: str, filename: str = "") -> RecognitionResult:
    """
    Convenience function for document recognition.
    
    Args:
        text: Full document text
        filename: Original filename
        
    Returns:
        RecognitionResult with complete analysis
    """
    engine = get_recognition_engine()
    return engine.recognize(text, filename)
