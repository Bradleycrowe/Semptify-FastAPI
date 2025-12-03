"""
Eviction Case Builder - The Integration Layer

This service connects ALL of Semptify's data sources to generate
court-ready eviction defense packages.

Data Flow:
    User Profile → Tenant Info
    Vault Documents → Evidence + Extracted Fields
    Timeline Events → Chronological Narrative
    Calendar → Court Dates & Deadlines
    Rent Ledger → Payment History
    AI Analysis → Suggested Defenses

Output:
    Pre-filled court forms (Dakota County specific)
    Evidence packet with exhibit labels
    Timeline summary for court
    Compliance validation for MN court rules
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.models.models import (
    User, Document, TimelineEvent, CalendarEvent, RentPayment
)


# =============================================================================
# Minnesota Court Compliance Rules
# =============================================================================

class MNCourtRules:
    """
    Minnesota Housing Court Rules - Dakota County
    These are the rules that MUST be followed for valid filings.
    """
    
    # Answer deadline: Must be filed before hearing or within 
    # time specified in summons (typically 7-14 days)
    ANSWER_DEADLINE_DAYS = 7
    
    # Service requirements
    SERVICE_METHODS = ["personal", "substitute", "mail", "posting"]
    REQUIRED_SERVICE_PROOF = True
    
    # Counterclaim requirements
    MAX_COUNTERCLAIM_AMOUNT = 15000  # Small claims limit
    COUNTERCLAIM_FILING_FEE = 75  # As of 2024
    
    # Document requirements
    REQUIRED_COPIES = 3  # Original + 2 copies
    ALLOWED_FORMATS = ["pdf", "jpg", "png", "doc", "docx"]
    MAX_FILE_SIZE_MB = 25
    
    # Hearing requirements
    ZOOM_APPEARANCE_ALLOWED = True
    IN_PERSON_REQUIRED_FOR = ["jury_trial", "contempt"]
    
    # Fee waiver (IFP - In Forma Pauperis)
    IFP_INCOME_THRESHOLD_PERCENT = 125  # % of federal poverty guidelines
    
    # Dakota County specific
    DAKOTA_COUNTY_CODE = "19"
    COURT_ADDRESS = "1560 Highway 55, Hastings, MN 55033"
    EFILING_URL = "https://minnesota.tylerhost.net/ofsweb"
    GUIDE_AND_FILE_URL = "https://www.mncourts.gov/Help-Topics/Guide-and-File.aspx"


class ComplianceStatus(str, Enum):
    """Compliance check status."""
    COMPLIANT = "compliant"
    WARNING = "warning"
    ERROR = "error"
    MISSING = "missing"


@dataclass
class ComplianceCheck:
    """Result of a single compliance check."""
    rule: str
    status: ComplianceStatus
    message: str
    fix_action: Optional[str] = None
    deadline: Optional[datetime] = None


@dataclass
class ComplianceReport:
    """Full compliance report for a case."""
    overall_status: ComplianceStatus
    checks: list[ComplianceCheck] = field(default_factory=list)
    blocking_issues: int = 0
    warnings: int = 0
    ready_to_file: bool = False
    
    def to_dict(self) -> dict:
        return {
            "overall_status": self.overall_status.value,
            "checks": [
                {
                    "rule": c.rule,
                    "status": c.status.value,
                    "message": c.message,
                    "fix_action": c.fix_action,
                    "deadline": c.deadline.isoformat() if c.deadline else None,
                }
                for c in self.checks
            ],
            "blocking_issues": self.blocking_issues,
            "warnings": self.warnings,
            "ready_to_file": self.ready_to_file,
        }


# =============================================================================
# Case Data Structures
# =============================================================================

@dataclass
class ExtractedTenantInfo:
    """Tenant information extracted from Semptify data."""
    full_name: str
    address: str
    city: str
    state: str
    zip_code: str
    phone: Optional[str] = None
    email: Optional[str] = None
    
    # From lease
    lease_start: Optional[datetime] = None
    lease_end: Optional[datetime] = None
    monthly_rent: Optional[int] = None  # cents
    security_deposit: Optional[int] = None  # cents


@dataclass
class ExtractedLandlordInfo:
    """Landlord information extracted from documents."""
    name: str
    address: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    agent_name: Optional[str] = None  # Property manager


@dataclass
class EvictionNoticeInfo:
    """Information extracted from the eviction notice."""
    notice_type: str  # nonpayment, lease_violation, holdover, etc.
    date_served: Optional[datetime] = None
    service_method: Optional[str] = None
    amount_claimed: Optional[int] = None  # cents
    court_date: Optional[datetime] = None
    case_number: Optional[str] = None
    response_deadline: Optional[datetime] = None


@dataclass
class EvidenceItem:
    """A piece of evidence for the case."""
    document_id: str
    filename: str
    document_type: str
    description: str
    date_created: Optional[datetime] = None
    exhibit_label: Optional[str] = None  # A, B, C, etc.
    relevance: str = ""  # Why this matters


@dataclass
class TimelineEntry:
    """A timeline entry for court narrative."""
    date: datetime
    event_type: str
    title: str
    description: str
    has_evidence: bool = False
    evidence_ids: list[str] = field(default_factory=list)


@dataclass 
class Defense:
    """A legal defense that may apply."""
    code: str
    name: str
    description: str
    applicable: bool = False
    strength: str = "unknown"  # strong, moderate, weak
    evidence_ids: list[str] = field(default_factory=list)
    notes: str = ""


@dataclass
class EvictionCase:
    """Complete eviction case data assembled from Semptify."""
    user_id: str
    case_number: Optional[str] = None
    
    # Parties
    tenant: Optional[ExtractedTenantInfo] = None
    landlord: Optional[ExtractedLandlordInfo] = None
    
    # The eviction
    notice: Optional[EvictionNoticeInfo] = None
    
    # Evidence and timeline
    evidence: list[EvidenceItem] = field(default_factory=list)
    timeline: list[TimelineEntry] = field(default_factory=list)
    
    # Legal analysis
    defenses: list[Defense] = field(default_factory=list)
    counterclaims: list[dict] = field(default_factory=list)
    
    # Payment history
    rent_history: list[dict] = field(default_factory=list)
    total_paid: int = 0  # cents
    total_owed: int = 0  # cents
    
    # Compliance
    compliance: Optional[ComplianceReport] = None
    
    # Metadata
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    language: str = "en"
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "user_id": self.user_id,
            "case_number": self.case_number,
            "tenant": {
                "full_name": self.tenant.full_name if self.tenant else "",
                "address": self.tenant.address if self.tenant else "",
                "city": self.tenant.city if self.tenant else "",
                "state": self.tenant.state if self.tenant else "MN",
                "zip_code": self.tenant.zip_code if self.tenant else "",
                "phone": self.tenant.phone if self.tenant else "",
                "email": self.tenant.email if self.tenant else "",
                "monthly_rent": self.tenant.monthly_rent if self.tenant else 0,
            } if self.tenant else None,
            "landlord": {
                "name": self.landlord.name if self.landlord else "",
                "address": self.landlord.address if self.landlord else "",
            } if self.landlord else None,
            "notice": {
                "type": self.notice.notice_type if self.notice else "",
                "date_served": self.notice.date_served.isoformat() if self.notice and self.notice.date_served else None,
                "court_date": self.notice.court_date.isoformat() if self.notice and self.notice.court_date else None,
                "case_number": self.notice.case_number if self.notice else None,
                "amount_claimed": self.notice.amount_claimed if self.notice else 0,
            } if self.notice else None,
            "evidence_count": len(self.evidence),
            "timeline_count": len(self.timeline),
            "defenses": [
                {"code": d.code, "name": d.name, "applicable": d.applicable, "strength": d.strength}
                for d in self.defenses if d.applicable
            ],
            "rent_history_summary": {
                "total_paid": self.total_paid,
                "total_owed": self.total_owed,
                "payments_count": len(self.rent_history),
            },
            "compliance": self.compliance.to_dict() if self.compliance else None,
            "language": self.language,
            "created_at": self.created_at.isoformat(),
        }


# =============================================================================
# Minnesota Eviction Defenses
# =============================================================================

MINNESOTA_DEFENSES = [
    Defense(
        code="improper_notice",
        name="Improper Notice",
        description="The eviction notice did not comply with Minnesota law requirements",
    ),
    Defense(
        code="improper_service",
        name="Improper Service",
        description="The notice or summons was not properly served",
    ),
    Defense(
        code="retaliation",
        name="Retaliatory Eviction",
        description="Eviction is retaliation for exercising tenant rights (Minn. Stat. § 504B.441)",
    ),
    Defense(
        code="discrimination",
        name="Discrimination",
        description="Eviction based on protected class status",
    ),
    Defense(
        code="habitability",
        name="Breach of Habitability",
        description="Landlord failed to maintain habitable conditions (Minn. Stat. § 504B.161)",
    ),
    Defense(
        code="rent_paid",
        name="Rent Was Paid",
        description="All rent claimed was actually paid",
    ),
    Defense(
        code="rent_escrow",
        name="Rent Escrow",
        description="Rent withheld or escrowed due to habitability issues",
    ),
    Defense(
        code="waiver",
        name="Waiver",
        description="Landlord waived right to evict by accepting rent or other conduct",
    ),
    Defense(
        code="lease_violation_cured",
        name="Violation Cured",
        description="The alleged lease violation has been corrected",
    ),
    Defense(
        code="emergency_assistance",
        name="Emergency Assistance Pending",
        description="Emergency rental assistance application is pending",
    ),
]


# =============================================================================
# Case Builder Service
# =============================================================================

class EvictionCaseBuilder:
    """
    Builds an eviction defense case from Semptify data.
    
    This is THE integration point that connects:
    - User profile
    - Document vault
    - Timeline events
    - Calendar deadlines
    - Rent ledger
    - AI document analysis
    
    Into a court-ready eviction defense package.
    """
    
    def __init__(self):
        self.defenses = [Defense(**d.__dict__) for d in MINNESOTA_DEFENSES]
    
    async def build_case(self, user_id: str, language: str = "en") -> EvictionCase:
        """
        Build a complete eviction case from all Semptify data sources.
        
        Args:
            user_id: The user's Semptify ID
            language: Preferred language (en, es, so, ar)
            
        Returns:
            EvictionCase with all data assembled
        """
        case = EvictionCase(user_id=user_id, language=language)
        
        async with get_db_session() as session:
            # 1. Get user profile
            user = await self._get_user(session, user_id)
            if user:
                case.tenant = await self._extract_tenant_info(session, user)
            
            # 2. Get all documents and extract info
            documents = await self._get_documents(session, user_id)
            case.evidence = self._build_evidence_list(documents)
            case.landlord = self._extract_landlord_info(documents)
            case.notice = self._extract_notice_info(documents)
            
            # 3. Get timeline events
            events = await self._get_timeline_events(session, user_id)
            case.timeline = self._build_timeline(events, documents)
            
            # 4. Get calendar events (court dates)
            calendar = await self._get_calendar_events(session, user_id)
            self._update_from_calendar(case, calendar)
            
            # 5. Get rent payment history
            payments = await self._get_rent_payments(session, user_id)
            case.rent_history = self._build_rent_history(payments)
            case.total_paid = sum(p.amount for p in payments if p.status == "paid")
            case.total_owed = sum(p.amount for p in payments if p.status in ["late", "missed"])
            
            # 6. Analyze applicable defenses
            case.defenses = self._analyze_defenses(case)
            
            # 7. Run compliance check
            case.compliance = self._check_compliance(case)
        
        return case
    
    async def _get_user(self, session: AsyncSession, user_id: str) -> Optional[User]:
        """Get user from database."""
        result = await session.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()
    
    async def _extract_tenant_info(
        self, session: AsyncSession, user: User
    ) -> ExtractedTenantInfo:
        """Extract tenant info from user profile and documents."""
        # Start with what we know from user profile
        tenant = ExtractedTenantInfo(
            full_name=user.display_name or "",
            address="",
            city="",
            state="MN",
            zip_code="",
            email=user.email,
        )
        
        # TODO: Enhance with lease document extraction
        # Look for lease documents and extract address, rent amount, etc.
        
        return tenant
    
    async def _get_documents(
        self, session: AsyncSession, user_id: str
    ) -> list[Document]:
        """Get all documents for user."""
        result = await session.execute(
            select(Document)
            .where(Document.user_id == user_id)
            .order_by(Document.uploaded_at.desc())
        )
        return list(result.scalars().all())
    
    def _build_evidence_list(self, documents: list[Document]) -> list[EvidenceItem]:
        """Build evidence list with exhibit labels."""
        evidence = []
        exhibit_num = 0
        
        for doc in documents:
            exhibit_num += 1
            exhibit_label = chr(64 + exhibit_num) if exhibit_num <= 26 else f"AA{exhibit_num - 26}"
            
            evidence.append(EvidenceItem(
                document_id=doc.id,
                filename=doc.original_filename,
                document_type=doc.document_type or "unknown",
                description=doc.description or "",
                date_created=doc.uploaded_at,
                exhibit_label=f"Exhibit {exhibit_label}",
                relevance=self._determine_relevance(doc),
            ))
        
        return evidence
    
    def _determine_relevance(self, doc: Document) -> str:
        """Determine why a document is relevant to the case."""
        doc_type = (doc.document_type or "").lower()
        
        relevance_map = {
            "lease": "Establishes terms of tenancy agreement",
            "eviction_notice": "The notice being challenged",
            "rent_receipt": "Proof of rent payment",
            "photo": "Photographic evidence of conditions",
            "communication": "Communication with landlord",
            "repair_request": "Evidence of maintenance issues reported",
            "bank_statement": "Financial records showing payments",
        }
        
        return relevance_map.get(doc_type, "Supporting evidence")
    
    def _extract_landlord_info(self, documents: list[Document]) -> Optional[ExtractedLandlordInfo]:
        """Extract landlord info from documents."""
        # TODO: Use AI extraction from lease documents
        # For now, return placeholder
        return ExtractedLandlordInfo(name="")
    
    def _extract_notice_info(self, documents: list[Document]) -> Optional[EvictionNoticeInfo]:
        """Extract eviction notice info from documents."""
        # Look for eviction notice documents
        for doc in documents:
            if doc.document_type and "eviction" in doc.document_type.lower():
                # TODO: Use AI extraction
                return EvictionNoticeInfo(
                    notice_type="nonpayment",  # Would be extracted
                    date_served=doc.uploaded_at,
                )
        return None
    
    async def _get_timeline_events(
        self, session: AsyncSession, user_id: str
    ) -> list[TimelineEvent]:
        """Get timeline events for user."""
        result = await session.execute(
            select(TimelineEvent)
            .where(TimelineEvent.user_id == user_id)
            .order_by(TimelineEvent.event_date.asc())
        )
        return list(result.scalars().all())
    
    def _build_timeline(
        self, events: list[TimelineEvent], documents: list[Document]
    ) -> list[TimelineEntry]:
        """Build timeline for court narrative."""
        timeline = []
        doc_map = {d.id: d for d in documents}
        
        for event in events:
            has_evidence = event.document_id is not None
            evidence_ids = [event.document_id] if event.document_id else []
            
            timeline.append(TimelineEntry(
                date=event.event_date,
                event_type=event.event_type,
                title=event.title,
                description=event.description or "",
                has_evidence=has_evidence,
                evidence_ids=evidence_ids,
            ))
        
        return timeline
    
    async def _get_calendar_events(
        self, session: AsyncSession, user_id: str
    ) -> list[CalendarEvent]:
        """Get calendar events for user."""
        result = await session.execute(
            select(CalendarEvent)
            .where(CalendarEvent.user_id == user_id)
            .order_by(CalendarEvent.start_datetime.asc())
        )
        return list(result.scalars().all())
    
    def _update_from_calendar(
        self, case: EvictionCase, calendar: list[CalendarEvent]
    ) -> None:
        """Update case with calendar information."""
        for event in calendar:
            if event.event_type == "hearing":
                if case.notice:
                    case.notice.court_date = event.start_datetime
                else:
                    case.notice = EvictionNoticeInfo(
                        notice_type="unknown",
                        court_date=event.start_datetime,
                    )
    
    async def _get_rent_payments(
        self, session: AsyncSession, user_id: str
    ) -> list[RentPayment]:
        """Get rent payment history."""
        result = await session.execute(
            select(RentPayment)
            .where(RentPayment.user_id == user_id)
            .order_by(RentPayment.payment_date.desc())
        )
        return list(result.scalars().all())
    
    def _build_rent_history(self, payments: list[RentPayment]) -> list[dict]:
        """Build rent history summary."""
        return [
            {
                "date": p.payment_date.isoformat(),
                "amount": p.amount,
                "status": p.status,
                "method": p.payment_method,
                "confirmation": p.confirmation_number,
            }
            for p in payments
        ]
    
    def _analyze_defenses(self, case: EvictionCase) -> list[Defense]:
        """Analyze which defenses may apply based on case data."""
        defenses = [Defense(**d.__dict__) for d in MINNESOTA_DEFENSES]
        
        for defense in defenses:
            if defense.code == "rent_paid":
                # Check if rent history shows payments
                if case.total_paid > 0:
                    defense.applicable = True
                    defense.strength = "moderate"
                    defense.notes = f"Records show ${case.total_paid / 100:.2f} in payments"
            
            elif defense.code == "habitability":
                # Check for maintenance-related documents or timeline events
                has_maintenance = any(
                    e.event_type in ["maintenance", "repair_request"]
                    for e in case.timeline
                )
                has_photos = any(
                    e.document_type == "photo"
                    for e in case.evidence
                )
                if has_maintenance or has_photos:
                    defense.applicable = True
                    defense.strength = "moderate" if has_photos else "weak"
                    defense.notes = "Evidence of habitability issues found"
            
            elif defense.code == "improper_notice":
                # Would analyze notice details
                pass
            
            elif defense.code == "retaliation":
                # Check timeline for complaints before eviction
                pass
        
        return defenses
    
    def _check_compliance(self, case: EvictionCase) -> ComplianceReport:
        """Check case for Minnesota court compliance."""
        checks = []
        blocking = 0
        warnings = 0
        
        # Check 1: Tenant info complete
        if not case.tenant or not case.tenant.full_name:
            checks.append(ComplianceCheck(
                rule="tenant_name_required",
                status=ComplianceStatus.ERROR,
                message="Tenant name is required for court forms",
                fix_action="Enter your full legal name in your profile",
            ))
            blocking += 1
        else:
            checks.append(ComplianceCheck(
                rule="tenant_name_required",
                status=ComplianceStatus.COMPLIANT,
                message="Tenant name is provided",
            ))
        
        # Check 2: Address required
        if not case.tenant or not case.tenant.address:
            checks.append(ComplianceCheck(
                rule="address_required",
                status=ComplianceStatus.ERROR,
                message="Property address is required",
                fix_action="Upload your lease to extract address, or enter manually",
            ))
            blocking += 1
        else:
            checks.append(ComplianceCheck(
                rule="address_required",
                status=ComplianceStatus.COMPLIANT,
                message="Property address is provided",
            ))
        
        # Check 3: Court date known
        if not case.notice or not case.notice.court_date:
            checks.append(ComplianceCheck(
                rule="court_date_required",
                status=ComplianceStatus.WARNING,
                message="Court date not found - check your summons",
                fix_action="Add court date to your calendar",
            ))
            warnings += 1
        else:
            # Check if deadline is approaching
            days_until = (case.notice.court_date - datetime.now(timezone.utc)).days
            if days_until < 0:
                checks.append(ComplianceCheck(
                    rule="court_date_required",
                    status=ComplianceStatus.ERROR,
                    message="Court date has passed!",
                    deadline=case.notice.court_date,
                ))
                blocking += 1
            elif days_until <= 3:
                checks.append(ComplianceCheck(
                    rule="court_date_required",
                    status=ComplianceStatus.WARNING,
                    message=f"Court date is in {days_until} days - file immediately!",
                    deadline=case.notice.court_date,
                ))
                warnings += 1
            else:
                checks.append(ComplianceCheck(
                    rule="court_date_required",
                    status=ComplianceStatus.COMPLIANT,
                    message=f"Court date: {case.notice.court_date.strftime('%B %d, %Y')}",
                    deadline=case.notice.court_date,
                ))
        
        # Check 4: Evidence available
        if len(case.evidence) == 0:
            checks.append(ComplianceCheck(
                rule="evidence_recommended",
                status=ComplianceStatus.WARNING,
                message="No evidence documents uploaded - your case will be stronger with documentation",
                fix_action="Upload relevant documents to your vault",
            ))
            warnings += 1
        else:
            checks.append(ComplianceCheck(
                rule="evidence_recommended",
                status=ComplianceStatus.COMPLIANT,
                message=f"{len(case.evidence)} evidence documents available",
            ))
        
        # Check 5: Landlord name
        if not case.landlord or not case.landlord.name:
            checks.append(ComplianceCheck(
                rule="landlord_name_required",
                status=ComplianceStatus.ERROR,
                message="Landlord/Plaintiff name is required for Answer form",
                fix_action="Check your summons or lease for landlord name",
            ))
            blocking += 1
        else:
            checks.append(ComplianceCheck(
                rule="landlord_name_required",
                status=ComplianceStatus.COMPLIANT,
                message="Landlord name is provided",
            ))
        
        # Check 6: Case number (if summons received)
        if case.notice and case.notice.court_date and not case.case_number:
            checks.append(ComplianceCheck(
                rule="case_number_required",
                status=ComplianceStatus.WARNING,
                message="Case number not found - check your summons",
                fix_action="Enter case number from court summons",
            ))
            warnings += 1
        
        # Determine overall status
        if blocking > 0:
            overall = ComplianceStatus.ERROR
        elif warnings > 0:
            overall = ComplianceStatus.WARNING
        else:
            overall = ComplianceStatus.COMPLIANT
        
        return ComplianceReport(
            overall_status=overall,
            checks=checks,
            blocking_issues=blocking,
            warnings=warnings,
            ready_to_file=blocking == 0,
        )


# =============================================================================
# Form Field Mapping - Dakota County Answer Form
# =============================================================================

DAKOTA_COUNTY_FORM_FIELDS = {
    # Maps Semptify data to PDF form field names
    # These will need to be updated based on actual form field inspection
    "case_number": "CaseNumber",
    "tenant_name": "DefendantName",
    "tenant_address": "DefendantAddress",
    "tenant_city_state_zip": "DefendantCityStateZip",
    "tenant_phone": "DefendantPhone",
    "landlord_name": "PlaintiffName",
    "landlord_address": "PlaintiffAddress",
    "court_date": "HearingDate",
    "answer_date": "AnswerDate",
    
    # Answer checkboxes
    "deny_all": "DenyAllAllegations",
    "deny_amount": "DenyAmountOwed",
    "defense_improper_notice": "DefenseImproperNotice",
    "defense_habitability": "DefenseHabitability",
    "defense_retaliation": "DefenseRetaliation",
    "defense_discrimination": "DefenseDiscrimination",
    "defense_rent_paid": "DefenseRentPaid",
    
    # Counterclaim fields
    "counterclaim_amount": "CounterclaimAmount",
    "counterclaim_description": "CounterclaimFacts",
}


async def get_case_builder() -> EvictionCaseBuilder:
    """Get case builder instance."""
    return EvictionCaseBuilder()
