"""
Document Intake, Data Extraction & Analysis Engine

This is the INTAKE PIPELINE for Semptify. When a document comes in:
1. INTAKE: Receive, validate, hash, store
2. EXTRACT: OCR, parse structure, pull key data
3. ANALYZE: Classify, detect issues, cross-reference laws
4. ENRICH: Add context, link to timeline, suggest actions

Supports:
- Leases, notices, letters, receipts, photos, court filings
- Multiple formats: PDF, images, Word docs, text
- Multiple languages (English primary, with Spanish/Somali/Arabic detection)
"""

import hashlib
import json
import re
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta
from enum import Enum
from pathlib import Path
from typing import Optional, Any
from uuid import uuid4


# =============================================================================
# ENUMS & TYPES
# =============================================================================

class DocumentType(str, Enum):
    """Types of documents in tenant defense."""
    LEASE = "lease"
    LEASE_AMENDMENT = "lease_amendment"
    EVICTION_NOTICE = "eviction_notice"
    NOTICE_TO_QUIT = "notice_to_quit"
    RENT_INCREASE_NOTICE = "rent_increase_notice"
    LATE_FEE_NOTICE = "late_fee_notice"
    REPAIR_REQUEST = "repair_request"
    REPAIR_RESPONSE = "repair_response"
    INSPECTION_REPORT = "inspection_report"
    RECEIPT = "receipt"
    PAYMENT_RECORD = "payment_record"
    BANK_STATEMENT = "bank_statement"
    PHOTO_EVIDENCE = "photo_evidence"
    VIDEO_EVIDENCE = "video_evidence"
    EMAIL_COMMUNICATION = "email_communication"
    TEXT_MESSAGE = "text_message"
    LETTER = "letter"
    COURT_SUMMONS = "court_summons"
    COURT_COMPLAINT = "court_complaint"
    COURT_FILING = "court_filing"
    COURT_ORDER = "court_order"
    AFFIDAVIT = "affidavit"
    MOTION = "motion"
    UTILITY_BILL = "utility_bill"
    MOVE_IN_CHECKLIST = "move_in_checklist"
    MOVE_OUT_CHECKLIST = "move_out_checklist"
    SECURITY_DEPOSIT_RECEIPT = "security_deposit_receipt"
    SECURITY_DEPOSIT_ITEMIZATION = "security_deposit_itemization"
    OTHER = "other"


class IntakeStatus(str, Enum):
    """Document intake processing status."""
    RECEIVED = "received"           # Just uploaded
    VALIDATING = "validating"       # Checking file integrity
    EXTRACTING = "extracting"       # OCR/text extraction
    ANALYZING = "analyzing"         # AI analysis
    ENRICHING = "enriching"         # Adding context
    COMPLETE = "complete"           # Fully processed
    FAILED = "failed"               # Processing failed
    NEEDS_REVIEW = "needs_review"   # Human review needed


class IssueSeverity(str, Enum):
    """Severity of detected issues."""
    CRITICAL = "critical"   # Immediate action needed (eviction, court date)
    HIGH = "high"           # Urgent (deadline approaching, violation)
    MEDIUM = "medium"       # Important (potential issue, follow up)
    LOW = "low"             # Informational (note for record)
    INFO = "info"           # Just information


class LanguageCode(str, Enum):
    """Supported languages."""
    ENGLISH = "en"
    SPANISH = "es"
    SOMALI = "so"
    ARABIC = "ar"
    UNKNOWN = "unknown"


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class ExtractedDate:
    """A date extracted from a document."""
    date: datetime
    label: str              # What this date represents
    confidence: float       # 0.0-1.0
    source_text: str        # Original text it was extracted from
    is_deadline: bool = False
    days_until: Optional[int] = None  # Days from today (negative if past)

    def to_dict(self) -> dict:
        return {
            "date": self.date.isoformat(),
            "label": self.label,
            "confidence": self.confidence,
            "source_text": self.source_text,
            "is_deadline": self.is_deadline,
            "days_until": self.days_until,
        }


@dataclass
class ExtractedParty:
    """A party (person/entity) extracted from a document."""
    name: str
    role: str               # landlord, tenant, agent, attorney, court
    address: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    confidence: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ExtractedAmount:
    """A monetary amount extracted from a document."""
    amount: float
    label: str              # rent, deposit, fee, damages, etc.
    currency: str = "USD"
    period: Optional[str] = None  # monthly, one-time, etc.
    confidence: float = 0.0
    source_text: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ExtractedClause:
    """A significant clause or term extracted from a document."""
    clause_type: str        # late_fee, notice_period, pet_policy, etc.
    text: str               # The actual clause text
    summary: str            # Plain English summary
    is_problematic: bool = False  # Potentially illegal/unfair
    issue_description: Optional[str] = None
    legal_reference: Optional[str] = None
    confidence: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class DetectedIssue:
    """An issue or concern detected in the document."""
    issue_id: str
    severity: IssueSeverity
    title: str
    description: str
    affected_text: Optional[str] = None
    legal_basis: Optional[str] = None
    recommended_action: Optional[str] = None
    deadline: Optional[datetime] = None
    related_laws: list = field(default_factory=list)

    def to_dict(self) -> dict:
        data = asdict(self)
        data["severity"] = self.severity.value
        if self.deadline:
            data["deadline"] = self.deadline.isoformat()
        return data


@dataclass
class ExtractionResult:
    """Complete extraction result from a document."""
    doc_type: DocumentType
    doc_type_confidence: float
    language: LanguageCode
    
    # Raw extraction
    full_text: str
    page_count: int
    word_count: int
    
    # Structured extractions
    dates: list[ExtractedDate] = field(default_factory=list)
    parties: list[ExtractedParty] = field(default_factory=list)
    amounts: list[ExtractedAmount] = field(default_factory=list)
    clauses: list[ExtractedClause] = field(default_factory=list)
    
    # Analysis
    issues: list[DetectedIssue] = field(default_factory=list)
    summary: str = ""
    key_points: list[str] = field(default_factory=list)
    
    # Metadata
    extracted_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    extraction_method: str = ""  # ocr, text_parse, ai_extraction
    raw_ai_response: Optional[dict] = None

    def to_dict(self) -> dict:
        return {
            "doc_type": self.doc_type.value,
            "doc_type_confidence": self.doc_type_confidence,
            "language": self.language.value,
            "full_text": self.full_text[:1000] + "..." if len(self.full_text) > 1000 else self.full_text,
            "page_count": self.page_count,
            "word_count": self.word_count,
            "dates": [d.to_dict() for d in self.dates],
            "parties": [p.to_dict() for p in self.parties],
            "amounts": [a.to_dict() for a in self.amounts],
            "clauses": [c.to_dict() for c in self.clauses],
            "issues": [i.to_dict() for i in self.issues],
            "summary": self.summary,
            "key_points": self.key_points,
            "extracted_at": self.extracted_at.isoformat(),
            "extraction_method": self.extraction_method,
        }


@dataclass
class IntakeDocument:
    """A document in the intake pipeline."""
    id: str
    user_id: str
    filename: str
    file_hash: str
    file_size: int
    mime_type: str
    
    # Processing state
    status: IntakeStatus
    status_message: str = ""
    progress_percent: int = 0
    
    # Extraction results
    extraction: Optional[ExtractionResult] = None
    
    # Cross-references
    linked_timeline_events: list[str] = field(default_factory=list)
    linked_calendar_events: list[str] = field(default_factory=list)
    matched_laws: list[str] = field(default_factory=list)
    
    # Timestamps
    uploaded_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    processed_at: Optional[datetime] = None
    
    # Storage - documents are in vault
    vault_id: Optional[str] = None  # Reference to document in vault
    storage_path: Optional[str] = None
    storage_provider: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "filename": self.filename,
            "file_hash": self.file_hash,
            "file_size": self.file_size,
            "mime_type": self.mime_type,
            "status": self.status.value,
            "status_message": self.status_message,
            "progress_percent": self.progress_percent,
            "extraction": self.extraction.to_dict() if self.extraction else None,
            "linked_timeline_events": self.linked_timeline_events,
            "linked_calendar_events": self.linked_calendar_events,
            "matched_laws": self.matched_laws,
            "uploaded_at": self.uploaded_at.isoformat(),
            "processed_at": self.processed_at.isoformat() if self.processed_at else None,
            "vault_id": self.vault_id,
            "storage_path": self.storage_path,
            "storage_provider": self.storage_provider,
        }


# =============================================================================
# DOCUMENT CLASSIFIER
# =============================================================================

class DocumentClassifier:
    """Classify documents by type based on content analysis."""

    # Keywords and patterns for document classification
    CLASSIFICATION_PATTERNS = {
        DocumentType.EVICTION_NOTICE: {
            "keywords": ["eviction", "evict", "unlawful detainer", "notice to quit", 
                        "vacate", "terminate tenancy", "possession"],
            "weight": 10,
        },
        DocumentType.COURT_SUMMONS: {
            "keywords": ["summons", "court date", "appear in court", "hearing",
                        "district court", "housing court", "you are hereby summoned"],
            "weight": 10,
        },
        DocumentType.LEASE: {
            "keywords": ["lease agreement", "rental agreement", "tenancy agreement",
                        "landlord and tenant", "term of lease", "security deposit",
                        "monthly rent"],
            "weight": 8,
        },
        DocumentType.NOTICE_TO_QUIT: {
            "keywords": ["notice to quit", "14 day notice", "30 day notice",
                        "terminate your tenancy", "demand for possession"],
            "weight": 9,
        },
        DocumentType.RENT_INCREASE_NOTICE: {
            "keywords": ["rent increase", "new rent amount", "rent will increase",
                        "effective date", "increased to"],
            "weight": 7,
        },
        DocumentType.REPAIR_REQUEST: {
            "keywords": ["repair request", "maintenance request", "needs repair",
                        "broken", "not working", "please fix"],
            "weight": 6,
        },
        DocumentType.INSPECTION_REPORT: {
            "keywords": ["inspection", "property condition", "move-in inspection",
                        "move-out inspection", "condition report"],
            "weight": 6,
        },
        DocumentType.RECEIPT: {
            "keywords": ["receipt", "payment received", "amount paid",
                        "thank you for your payment"],
            "weight": 5,
        },
        DocumentType.SECURITY_DEPOSIT_ITEMIZATION: {
            "keywords": ["security deposit", "itemization", "deductions",
                        "deposit return", "damage charges", "cleaning fee"],
            "weight": 7,
        },
    }

    @classmethod
    def classify(cls, text: str, filename: str = "") -> tuple[DocumentType, float]:
        """
        Classify a document based on its text content.
        Returns (DocumentType, confidence_score).
        """
        text_lower = text.lower()
        filename_lower = filename.lower()
        
        scores: dict[DocumentType, float] = {}
        
        for doc_type, pattern in cls.CLASSIFICATION_PATTERNS.items():
            score = 0.0
            keyword_count = 0
            
            for keyword in pattern["keywords"]:
                if keyword in text_lower:
                    keyword_count += 1
                    score += pattern["weight"]
                if keyword in filename_lower:
                    score += pattern["weight"] * 0.5
            
            # Normalize by keyword count
            if keyword_count > 0:
                score = score * (1 + keyword_count * 0.1)
            
            scores[doc_type] = score
        
        # Find best match
        if scores:
            best_type = max(scores, key=scores.get)
            best_score = scores[best_type]
            
            # Normalize confidence to 0-1
            confidence = min(best_score / 50.0, 1.0)
            
            if confidence > 0.2:
                return best_type, confidence
        
        # Fallback based on filename
        if "lease" in filename_lower:
            return DocumentType.LEASE, 0.5
        if "notice" in filename_lower:
            return DocumentType.EVICTION_NOTICE, 0.4
        if "receipt" in filename_lower:
            return DocumentType.RECEIPT, 0.5
        if any(ext in filename_lower for ext in [".jpg", ".jpeg", ".png", ".gif"]):
            return DocumentType.PHOTO_EVIDENCE, 0.7
        
        return DocumentType.OTHER, 0.1


# =============================================================================
# DATA EXTRACTOR
# =============================================================================

class DataExtractor:
    """Extract structured data from document text."""

    # Date patterns
    DATE_PATTERNS = [
        # MM/DD/YYYY or MM-DD-YYYY
        (r'\b(\d{1,2})[/-](\d{1,2})[/-](\d{4})\b', "%m/%d/%Y"),
        # Month DD, YYYY
        (r'\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2}),?\s+(\d{4})\b', "Month DD, YYYY"),
        # DD Month YYYY
        (r'\b(\d{1,2})\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})\b', "DD Month YYYY"),
        # YYYY-MM-DD (ISO)
        (r'\b(\d{4})-(\d{2})-(\d{2})\b', "%Y-%m-%d"),
    ]

    # Money patterns
    MONEY_PATTERNS = [
        r'\$\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)',  # $1,234.56
        r'(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)\s*(?:dollars?|USD)',  # 1234.56 dollars
    ]

    # Phone patterns
    PHONE_PATTERNS = [
        r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}',  # (555) 123-4567
    ]

    # Email patterns
    EMAIL_PATTERN = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'

    # Address patterns (simplified)
    ADDRESS_PATTERN = r'\d+\s+[\w\s]+(?:Street|St|Avenue|Ave|Road|Rd|Drive|Dr|Lane|Ln|Court|Ct|Boulevard|Blvd)\.?(?:\s*(?:Apt|Unit|Suite|#)\s*\w+)?'

    MONTH_MAP = {
        'january': 1, 'february': 2, 'march': 3, 'april': 4,
        'may': 5, 'june': 6, 'july': 7, 'august': 8,
        'september': 9, 'october': 10, 'november': 11, 'december': 12
    }

    @classmethod
    def extract_dates(cls, text: str) -> list[ExtractedDate]:
        """Extract all dates from text."""
        dates = []
        today = datetime.now(timezone.utc).date()
        
        # Pattern 1: MM/DD/YYYY or MM-DD-YYYY
        for match in re.finditer(r'\b(\d{1,2})[/-](\d{1,2})[/-](\d{4})\b', text):
            try:
                month, day, year = int(match.group(1)), int(match.group(2)), int(match.group(3))
                dt = datetime(year, month, day, tzinfo=timezone.utc)
                
                # Determine label from context
                context = text[max(0, match.start()-50):match.end()+50].lower()
                label = cls._determine_date_label(context)
                is_deadline = cls._is_deadline(context)
                
                days_until = (dt.date() - today).days
                
                dates.append(ExtractedDate(
                    date=dt,
                    label=label,
                    confidence=0.8,
                    source_text=match.group(0),
                    is_deadline=is_deadline,
                    days_until=days_until,
                ))
            except ValueError:
                continue
        
        # Pattern 2: Month DD, YYYY
        for match in re.finditer(
            r'\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2}),?\s+(\d{4})\b',
            text, re.IGNORECASE
        ):
            try:
                month = cls.MONTH_MAP[match.group(1).lower()]
                day, year = int(match.group(2)), int(match.group(3))
                dt = datetime(year, month, day, tzinfo=timezone.utc)
                
                context = text[max(0, match.start()-50):match.end()+50].lower()
                label = cls._determine_date_label(context)
                is_deadline = cls._is_deadline(context)
                days_until = (dt.date() - today).days
                
                dates.append(ExtractedDate(
                    date=dt,
                    label=label,
                    confidence=0.9,
                    source_text=match.group(0),
                    is_deadline=is_deadline,
                    days_until=days_until,
                ))
            except (ValueError, KeyError):
                continue
        
        return dates

    @classmethod
    def _determine_date_label(cls, context: str) -> str:
        """Determine what a date represents based on surrounding context."""
        labels = {
            "hearing": ["hearing", "court date", "appear", "trial"],
            "deadline": ["deadline", "must", "by", "before", "due"],
            "move_out": ["vacate", "move out", "leave", "quit"],
            "lease_start": ["commence", "begin", "start date", "effective"],
            "lease_end": ["expir", "terminat", "end date", "ending"],
            "payment_due": ["rent due", "payment due", "pay by"],
            "notice_date": ["dated", "notice date", "issued"],
            "service_date": ["served", "service date"],
        }
        
        for label, keywords in labels.items():
            if any(kw in context for kw in keywords):
                return label
        
        return "date_mentioned"

    @classmethod
    def _is_deadline(cls, context: str) -> bool:
        """Determine if a date represents a deadline."""
        deadline_words = ["must", "deadline", "by", "before", "no later than",
                         "due", "hearing", "court", "appear", "vacate"]
        return any(word in context for word in deadline_words)

    @classmethod
    def extract_amounts(cls, text: str) -> list[ExtractedAmount]:
        """Extract monetary amounts from text."""
        amounts = []
        
        for pattern in cls.MONEY_PATTERNS:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                amount_str = match.group(1).replace(',', '')
                try:
                    amount = float(amount_str)
                    
                    # Get context to determine label
                    start = max(0, match.start() - 100)
                    end = min(len(text), match.end() + 50)
                    context = text[start:end].lower()
                    
                    label = cls._determine_amount_label(context, amount)
                    period = cls._determine_period(context)
                    
                    amounts.append(ExtractedAmount(
                        amount=amount,
                        label=label,
                        currency="USD",
                        period=period,
                        confidence=0.8,
                        source_text=text[match.start():match.end()],
                    ))
                except ValueError:
                    continue
        
        return amounts

    @classmethod
    def _determine_amount_label(cls, context: str, amount: float) -> str:
        """Determine what an amount represents."""
        labels = {
            "rent": ["rent", "monthly rent", "rent amount"],
            "security_deposit": ["security deposit", "deposit"],
            "late_fee": ["late fee", "late charge", "penalty"],
            "application_fee": ["application fee", "application"],
            "pet_deposit": ["pet deposit", "pet fee"],
            "utilities": ["utilities", "electric", "gas", "water"],
            "damages": ["damage", "repair cost", "cleaning"],
            "court_costs": ["court cost", "filing fee"],
            "attorney_fees": ["attorney fee", "legal fee"],
        }
        
        for label, keywords in labels.items():
            if any(kw in context for kw in keywords):
                return label
        
        # Heuristic based on amount
        if 500 <= amount <= 3000:
            return "likely_rent"
        elif amount < 100:
            return "likely_fee"
        
        return "amount_mentioned"

    @classmethod
    def _determine_period(cls, context: str) -> Optional[str]:
        """Determine payment period from context."""
        if "month" in context or "per month" in context:
            return "monthly"
        if "week" in context:
            return "weekly"
        if "year" in context or "annual" in context:
            return "yearly"
        if "one-time" in context or "one time" in context:
            return "one_time"
        return None

    @classmethod
    def extract_parties(cls, text: str, doc_type: DocumentType) -> list[ExtractedParty]:
        """Extract parties (landlord, tenant, etc.) from text."""
        parties = []
        
        # Look for labeled parties
        party_patterns = [
            (r"(?:landlord|lessor|property owner)[:\s]+([A-Z][a-zA-Z\s]+?)(?:\n|,|$)", "landlord"),
            (r"(?:tenant|lessee|renter)[:\s]+([A-Z][a-zA-Z\s]+?)(?:\n|,|$)", "tenant"),
            (r"(?:property manager|manager|agent)[:\s]+([A-Z][a-zA-Z\s]+?)(?:\n|,|$)", "property_manager"),
            (r"(?:plaintiff)[:\s]+([A-Z][a-zA-Z\s]+?)(?:\n|,|$)", "plaintiff"),
            (r"(?:defendant)[:\s]+([A-Z][a-zA-Z\s]+?)(?:\n|,|$)", "defendant"),
        ]
        
        for pattern, role in party_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                name = match.strip()
                if len(name) > 2 and len(name) < 100:
                    parties.append(ExtractedParty(
                        name=name,
                        role=role,
                        confidence=0.7,
                    ))
        
        # Extract emails
        emails = re.findall(cls.EMAIL_PATTERN, text)
        for email in emails:
            # Try to find associated name
            parties.append(ExtractedParty(
                name="",
                role="contact",
                email=email,
                confidence=0.6,
            ))
        
        # Extract phone numbers
        phones = re.findall(cls.PHONE_PATTERNS[0], text)
        for phone in phones:
            parties.append(ExtractedParty(
                name="",
                role="contact",
                phone=phone,
                confidence=0.5,
            ))
        
        return parties

    @classmethod
    def extract_addresses(cls, text: str) -> list[str]:
        """Extract addresses from text."""
        addresses = re.findall(cls.ADDRESS_PATTERN, text, re.IGNORECASE)
        return [addr.strip() for addr in addresses if len(addr) > 10]


# =============================================================================
# ISSUE DETECTOR
# =============================================================================

class IssueDetector:
    """Detect potential issues and concerns in documents."""

    # Issue patterns for Minnesota tenant law
    ISSUE_PATTERNS = {
        "improper_notice_period": {
            "patterns": [
                r"(\d+)\s*day\s*notice",
                r"notice\s*(?:of|to)\s*(\d+)\s*days?",
            ],
            "check": lambda match, text: int(match.group(1)) < 14 if "non-payment" in text.lower() or "rent" in text.lower() else int(match.group(1)) < 30,
            "title": "Potentially Insufficient Notice Period",
            "description": "The notice period may be shorter than required by Minnesota law. Non-payment requires 14 days; other lease violations may require different periods.",
            "severity": IssueSeverity.HIGH,
            "legal_basis": "Minn. Stat. § 504B.135",
        },
        "illegal_late_fee": {
            "patterns": [
                r"late\s*fee[:\s]*\$?\s*(\d+)",
                r"\$\s*(\d+)\s*late\s*(?:fee|charge)",
            ],
            "check": lambda match, text: float(match.group(1)) > 100 or "percent" in text.lower(),
            "title": "Potentially Excessive Late Fee",
            "description": "Late fees must be reasonable. Excessive late fees may be unenforceable.",
            "severity": IssueSeverity.MEDIUM,
            "legal_basis": "Common law - unconscionability",
        },
        "lockout_threat": {
            "patterns": [
                r"change\s*(?:the\s*)?locks",
                r"lock\s*(?:you\s*)?out",
                r"shut\s*off\s*(?:your\s*)?utilities",
                r"remove\s*(?:your\s*)?belongings",
            ],
            "check": lambda match, text: True,
            "title": "Illegal Self-Help Eviction Threatened",
            "description": "Landlords cannot change locks, shut off utilities, or remove belongings without a court order. This is an illegal self-help eviction.",
            "severity": IssueSeverity.CRITICAL,
            "legal_basis": "Minn. Stat. § 504B.375",
        },
        "retaliation_indicator": {
            "patterns": [
                r"(?:since|after|because)\s*(?:you|your)\s*(?:complained|reported|called|contacted)",
                r"(?:complaint|report)\s*(?:to|with)\s*(?:city|county|health|inspector)",
            ],
            "check": lambda match, text: True,
            "title": "Possible Retaliatory Action",
            "description": "This action may be retaliation for exercising tenant rights. Retaliatory evictions are prohibited.",
            "severity": IssueSeverity.HIGH,
            "legal_basis": "Minn. Stat. § 504B.441",
        },
        "waiver_of_rights": {
            "patterns": [
                r"waive\s*(?:your|any|all)\s*(?:right|claim)",
                r"give\s*up\s*(?:your|any|all)\s*(?:right|claim)",
                r"cannot\s*(?:sue|take\s*legal\s*action)",
            ],
            "check": lambda match, text: True,
            "title": "Potentially Unenforceable Waiver",
            "description": "Tenants cannot waive certain statutory rights. Such clauses may be void.",
            "severity": IssueSeverity.MEDIUM,
            "legal_basis": "Minn. Stat. § 504B.161",
        },
        "habitability_issue": {
            "patterns": [
                r"mold",
                r"no\s*(?:heat|hot\s*water|running\s*water)",
                r"pest|rodent|cockroach|bed\s*bug",
                r"broken\s*(?:window|door|lock|stair|railing)",
                r"(?:leak|leaking)\s*(?:roof|ceiling|pipe|water)",
                r"electrical\s*(?:hazard|problem|issue)",
                r"(?:no|broken)\s*(?:smoke|carbon\s*monoxide)\s*(?:detector|alarm)",
            ],
            "check": lambda match, text: True,
            "title": "Habitability Concern Detected",
            "description": "This document mentions conditions that may affect habitability. Landlords must maintain habitable premises.",
            "severity": IssueSeverity.HIGH,
            "legal_basis": "Minn. Stat. § 504B.161",
        },
        "improper_security_deposit": {
            "patterns": [
                r"deposit[:\s]*\$?\s*(\d{1,3}(?:,\d{3})*)",
            ],
            "check": lambda match, text: float(match.group(1).replace(',', '')) > 5000,  # Unusually high
            "title": "Security Deposit Amount to Review",
            "description": "Verify security deposit amount is reasonable. While Minnesota has no statutory cap, excessive deposits may indicate other issues.",
            "severity": IssueSeverity.LOW,
            "legal_basis": "Minn. Stat. § 504B.178",
        },
        "deadline_imminent": {
            "patterns": [],  # Checked via date extraction
            "check": lambda dates: any(d.is_deadline and d.days_until is not None and 0 <= d.days_until <= 7 for d in dates),
            "title": "Deadline Within 7 Days",
            "description": "There is a deadline approaching within the next 7 days. Immediate action may be required.",
            "severity": IssueSeverity.CRITICAL,
        },
        "deadline_missed": {
            "patterns": [],  # Checked via date extraction
            "check": lambda dates: any(d.is_deadline and d.days_until is not None and d.days_until < 0 for d in dates),
            "title": "Deadline May Have Passed",
            "description": "A deadline mentioned in this document appears to have passed. Review whether this affects your case.",
            "severity": IssueSeverity.HIGH,
        },
    }

    @classmethod
    def detect_issues(
        cls,
        text: str,
        doc_type: DocumentType,
        dates: list[ExtractedDate],
        amounts: list[ExtractedAmount],
    ) -> list[DetectedIssue]:
        """Detect all issues in a document."""
        issues = []
        
        for issue_key, issue_def in cls.ISSUE_PATTERNS.items():
            # Skip date-based checks here (handled separately)
            if issue_key in ["deadline_imminent", "deadline_missed"]:
                continue
            
            for pattern in issue_def["patterns"]:
                for match in re.finditer(pattern, text, re.IGNORECASE):
                    if issue_def["check"](match, text):
                        issues.append(DetectedIssue(
                            issue_id=f"{issue_key}_{uuid4().hex[:8]}",
                            severity=issue_def["severity"],
                            title=issue_def["title"],
                            description=issue_def["description"],
                            affected_text=text[max(0, match.start()-20):match.end()+20],
                            legal_basis=issue_def.get("legal_basis"),
                            related_laws=[issue_def.get("legal_basis")] if issue_def.get("legal_basis") else [],
                        ))
                        break  # One issue per pattern type
        
        # Check date-based issues
        if dates:
            if cls.ISSUE_PATTERNS["deadline_imminent"]["check"](dates):
                imminent_dates = [d for d in dates if d.is_deadline and d.days_until is not None and 0 <= d.days_until <= 7]
                for d in imminent_dates:
                    issues.append(DetectedIssue(
                        issue_id=f"deadline_imminent_{uuid4().hex[:8]}",
                        severity=IssueSeverity.CRITICAL,
                        title=f"Deadline in {d.days_until} days: {d.label}",
                        description=f"The {d.label} deadline on {d.date.strftime('%B %d, %Y')} is approaching. Take action immediately.",
                        deadline=d.date,
                        recommended_action="Review requirements and take necessary action before deadline.",
                    ))
            
            if cls.ISSUE_PATTERNS["deadline_missed"]["check"](dates):
                missed_dates = [d for d in dates if d.is_deadline and d.days_until is not None and d.days_until < 0]
                for d in missed_dates:
                    issues.append(DetectedIssue(
                        issue_id=f"deadline_missed_{uuid4().hex[:8]}",
                        severity=IssueSeverity.HIGH,
                        title=f"Deadline may have passed: {d.label}",
                        description=f"The {d.label} deadline of {d.date.strftime('%B %d, %Y')} appears to have passed ({abs(d.days_until)} days ago). Check if this affects your case.",
                        deadline=d.date,
                        recommended_action="Consult with legal aid to understand your options.",
                    ))
        
        return issues


# =============================================================================
# DOCUMENT ANALYZER
# =============================================================================

class DocumentAnalyzer:
    """High-level document analysis combining all extractors."""

    @classmethod
    def generate_summary(cls, text: str, doc_type: DocumentType, issues: list[DetectedIssue]) -> str:
        """Generate a plain-English summary of the document."""
        summaries = {
            DocumentType.EVICTION_NOTICE: "This is an eviction notice from your landlord.",
            DocumentType.COURT_SUMMONS: "This is a court summons requiring you to appear in court.",
            DocumentType.LEASE: "This is a lease/rental agreement document.",
            DocumentType.NOTICE_TO_QUIT: "This is a notice requiring you to vacate the premises.",
            DocumentType.RENT_INCREASE_NOTICE: "This is a notice of rent increase.",
            DocumentType.REPAIR_REQUEST: "This is a repair/maintenance request.",
            DocumentType.RECEIPT: "This is a payment receipt.",
            DocumentType.SECURITY_DEPOSIT_ITEMIZATION: "This is a security deposit itemization showing deductions.",
        }
        
        base_summary = summaries.get(doc_type, "This document has been analyzed.")
        
        if issues:
            critical = [i for i in issues if i.severity == IssueSeverity.CRITICAL]
            if critical:
                base_summary += f" ⚠️ {len(critical)} CRITICAL issue(s) detected requiring immediate attention."
        
        return base_summary

    @classmethod
    def generate_key_points(
        cls,
        doc_type: DocumentType,
        dates: list[ExtractedDate],
        amounts: list[ExtractedAmount],
        issues: list[DetectedIssue],
    ) -> list[str]:
        """Generate key points from extracted data."""
        points = []
        
        # Deadline points
        deadlines = [d for d in dates if d.is_deadline]
        for d in deadlines:
            if d.days_until is not None:
                if d.days_until >= 0:
                    points.append(f"📅 {d.label.replace('_', ' ').title()}: {d.date.strftime('%B %d, %Y')} ({d.days_until} days away)")
                else:
                    points.append(f"⚠️ {d.label.replace('_', ' ').title()}: {d.date.strftime('%B %d, %Y')} ({abs(d.days_until)} days ago)")
        
        # Amount points
        for a in amounts:
            if a.label in ["rent", "likely_rent"]:
                points.append(f"💰 Rent amount: ${a.amount:,.2f}" + (f" ({a.period})" if a.period else ""))
            elif a.label == "security_deposit":
                points.append(f"💰 Security deposit: ${a.amount:,.2f}")
            elif a.label in ["late_fee", "damages"]:
                points.append(f"⚠️ {a.label.replace('_', ' ').title()}: ${a.amount:,.2f}")
        
        # Issue points
        for issue in issues:
            if issue.severity in [IssueSeverity.CRITICAL, IssueSeverity.HIGH]:
                points.append(f"🚨 {issue.title}")
        
        return points[:10]  # Limit to top 10 points


# =============================================================================
# INTAKE ENGINE (MAIN CLASS)
# =============================================================================

class DocumentIntakeEngine:
    """
    Main engine for document intake, extraction, and analysis.
    
    Usage:
        engine = DocumentIntakeEngine()
        doc = await engine.intake_document(user_id, file_bytes, filename, mime_type)
        result = await engine.process_document(doc.id)
    """

    def __init__(self, storage_dir: str = "data/intake"):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        
        self._documents: dict[str, IntakeDocument] = {}
        self._load_documents()

    def _load_documents(self):
        """Load documents from storage."""
        docs_file = self.storage_dir / "documents.json"
        if docs_file.exists():
            try:
                with open(docs_file) as f:
                    data = json.load(f)
                    for doc_id, doc_data in data.items():
                        # Reconstruct IntakeDocument
                        doc_data["status"] = IntakeStatus(doc_data["status"])
                        doc_data["uploaded_at"] = datetime.fromisoformat(doc_data["uploaded_at"])
                        if doc_data.get("processed_at"):
                            doc_data["processed_at"] = datetime.fromisoformat(doc_data["processed_at"])
                        # Skip extraction reconstruction for simplicity
                        doc_data["extraction"] = None
                        self._documents[doc_id] = IntakeDocument(**doc_data)
            except Exception:
                pass

    def _save_documents(self):
        """Save documents to storage."""
        docs_file = self.storage_dir / "documents.json"
        data = {doc_id: doc.to_dict() for doc_id, doc in self._documents.items()}
        with open(docs_file, "w") as f:
            json.dump(data, f, indent=2, default=str)

    async def intake_document(
        self,
        user_id: str,
        file_content: bytes,
        filename: str,
        mime_type: str,
        vault_id: Optional[str] = None,
    ) -> IntakeDocument:
        """
        Intake a new document.
        
        Documents should already be in the vault - this creates a processing record.
        
        Args:
            user_id: The user uploading the document
            file_content: Raw file bytes
            filename: Original filename
            mime_type: MIME type of the file
            vault_id: Reference to document in vault (if already stored there)
        
        Returns:
            IntakeDocument with status RECEIVED
        """
        # Generate hash
        file_hash = hashlib.sha256(file_content).hexdigest()
        
        # Check for duplicate
        for existing in self._documents.values():
            if existing.user_id == user_id and existing.file_hash == file_hash:
                return existing
        
        # Create document record
        doc_id = f"doc_{uuid4().hex[:12]}"
        
        doc = IntakeDocument(
            id=doc_id,
            user_id=user_id,
            filename=filename,
            file_hash=file_hash,
            file_size=len(file_content),
            mime_type=mime_type,
            status=IntakeStatus.RECEIVED,
            status_message="Document received, awaiting processing",
            progress_percent=10,
            vault_id=vault_id,  # Link to vault
        )
        
        # Store raw file locally for processing (even if in vault)
        # This is a working copy - vault is the source of truth
        user_dir = self.storage_dir / user_id
        user_dir.mkdir(exist_ok=True)
        file_path = user_dir / f"{doc_id}_{filename}"
        file_path.write_bytes(file_content)
        doc.storage_path = str(file_path)
        
        self._documents[doc_id] = doc
        self._save_documents()
        
        return doc


    async def process_document(self, doc_id: str) -> IntakeDocument:
        """
        Process a document through the full pipeline.
        
        Args:
            doc_id: Document ID to process
        
        Returns:
            Updated IntakeDocument with extraction results
        """
        doc = self._documents.get(doc_id)
        if not doc:
            raise ValueError(f"Document {doc_id} not found")
        
        try:
            # Stage 1: Validation
            doc.status = IntakeStatus.VALIDATING
            doc.status_message = "Validating document..."
            doc.progress_percent = 20
            
            # Read file content
            if not doc.storage_path or not Path(doc.storage_path).exists():
                raise ValueError("Document file not found")
            
            file_content = Path(doc.storage_path).read_bytes()
            
            # Stage 2: Extraction
            doc.status = IntakeStatus.EXTRACTING
            doc.status_message = "Extracting text..."
            doc.progress_percent = 40
            
            # Extract text (simplified - real implementation would use OCR)
            text = await self._extract_text(file_content, doc.mime_type, doc.filename)
            
            # Stage 3: Analysis
            doc.status = IntakeStatus.ANALYZING
            doc.status_message = "Analyzing content..."
            doc.progress_percent = 60
            
            # Classify document
            doc_type, type_confidence = DocumentClassifier.classify(text, doc.filename)
            
            # Detect language (simplified)
            language = self._detect_language(text)
            
            # Extract structured data
            dates = DataExtractor.extract_dates(text)
            amounts = DataExtractor.extract_amounts(text)
            parties = DataExtractor.extract_parties(text, doc_type)
            
            # Detect issues
            issues = IssueDetector.detect_issues(text, doc_type, dates, amounts)
            
            # Generate summary and key points
            summary = DocumentAnalyzer.generate_summary(text, doc_type, issues)
            key_points = DocumentAnalyzer.generate_key_points(doc_type, dates, amounts, issues)
            
            # Stage 4: Enrichment
            doc.status = IntakeStatus.ENRICHING
            doc.status_message = "Enriching with context..."
            doc.progress_percent = 80
            
            # Build extraction result
            extraction = ExtractionResult(
                doc_type=doc_type,
                doc_type_confidence=type_confidence,
                language=language,
                full_text=text,
                page_count=1,  # Simplified
                word_count=len(text.split()),
                dates=dates,
                parties=parties,
                amounts=amounts,
                clauses=[],  # Would require more sophisticated analysis
                issues=issues,
                summary=summary,
                key_points=key_points,
                extraction_method="text_parse",
            )
            
            doc.extraction = extraction
            
            # Complete
            doc.status = IntakeStatus.COMPLETE
            doc.status_message = "Processing complete"
            doc.progress_percent = 100
            doc.processed_at = datetime.now(timezone.utc)
            
            self._save_documents()
            
        except Exception as e:
            doc.status = IntakeStatus.FAILED
            doc.status_message = f"Processing failed: {str(e)}"
            doc.progress_percent = 0
            self._save_documents()
            raise
        
        return doc

    async def _extract_text(self, content: bytes, mime_type: str, filename: str) -> str:
        """Extract text from document content using robust multi-method extraction."""
        # For text files
        if mime_type.startswith("text/") or filename.endswith(".txt"):
            try:
                return content.decode("utf-8")
            except UnicodeDecodeError:
                return content.decode("latin-1")

        # For PDFs - use the PDF extractor service
        if mime_type == "application/pdf" or filename.lower().endswith(".pdf"):
            try:
                from app.services.pdf_extractor import get_pdf_extractor
                from app.core.config import get_settings
                
                extractor = get_pdf_extractor()
                settings = get_settings()
                
                # Try extraction with OCR fallback if Azure is configured
                if settings.azure_ai_key1:
                    result = extractor.extract_with_ocr(
                        content,
                        azure_endpoint=settings.azure_ai_endpoint,
                        azure_key=settings.azure_ai_key1
                    )
                else:
                    result = extractor.extract(content)
                
                if result.text.strip():
                    return result.text
                else:
                    return f"[PDF: {filename} - {result.page_count} pages, extraction method: {result.method_used}]"
                    
            except Exception as e:
                # Fallback to basic extraction
                try:
                    import PyPDF2
                    import io
                    reader = PyPDF2.PdfReader(io.BytesIO(content))
                    texts = [page.extract_text() or "" for page in reader.pages]
                    return "\n\n".join(texts)
                except:
                    pass
                return f"[PDF document: {filename} - extraction failed: {e}]"

        # For images - use Azure OCR if available
        if mime_type.startswith("image/"):
            try:
                from app.core.config import get_settings
                settings = get_settings()
                
                if settings.azure_ai_key1:
                    # Use Azure Document Intelligence for image OCR
                    from app.services.azure_ai import get_azure_ai
                    azure = get_azure_ai()
                    result = await azure._extract_with_doc_intelligence(content, mime_type)
                    text = azure._get_text_from_result(result)
                    if text.strip():
                        return text
            except Exception as e:
                pass
            return f"[Image: {filename} - OCR not available or failed]"

        # Try generic decode
        try:
            return content.decode("utf-8")
        except:
            return f"[Binary document: {filename}]"

    def _detect_language(self, text: str) -> LanguageCode:
        """Simple language detection based on common words."""
        text_lower = text.lower()
        
        # Spanish indicators
        spanish_words = ["el", "la", "de", "que", "en", "los", "del", "por", "con", "para"]
        spanish_count = sum(1 for w in spanish_words if f" {w} " in f" {text_lower} ")
        
        # Somali indicators
        somali_words = ["waa", "oo", "iyo", "ka", "ku", "ayaa", "ah", "uu", "la"]
        somali_count = sum(1 for w in somali_words if f" {w} " in f" {text_lower} ")
        
        # Arabic check (presence of Arabic characters)
        arabic_chars = sum(1 for c in text if '\u0600' <= c <= '\u06FF')
        
        if arabic_chars > len(text) * 0.1:
            return LanguageCode.ARABIC
        if somali_count > 5:
            return LanguageCode.SOMALI
        if spanish_count > 5:
            return LanguageCode.SPANISH
        
        return LanguageCode.ENGLISH

    def get_document(self, doc_id: str) -> Optional[IntakeDocument]:
        """Get a document by ID."""
        return self._documents.get(doc_id)

    def get_user_documents(self, user_id: str) -> list[IntakeDocument]:
        """Get all documents for a user."""
        return [d for d in self._documents.values() if d.user_id == user_id]

    def get_processing_status(self, doc_id: str) -> dict:
        """Get current processing status for a document."""
        doc = self._documents.get(doc_id)
        if not doc:
            return {"error": "Document not found"}
        
        return {
            "id": doc.id,
            "status": doc.status.value,
            "status_message": doc.status_message,
            "progress_percent": doc.progress_percent,
        }


# =============================================================================
# SINGLETON INSTANCE
# =============================================================================

_intake_engine: Optional[DocumentIntakeEngine] = None


def get_intake_engine() -> DocumentIntakeEngine:
    """Get or create the intake engine singleton."""
    global _intake_engine
    if _intake_engine is None:
        _intake_engine = DocumentIntakeEngine()
    return _intake_engine


# Alias for unified import pattern
get_document_intake = get_intake_engine
