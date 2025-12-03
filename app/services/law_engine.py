"""
Semptify 5.0 - Law Cross-Reference Engine
Generic tenant law framework that grows with usage.
"""

import json
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional, List, Dict
import logging

from app.core.event_bus import event_bus, EventType

logger = logging.getLogger(__name__)


class LawCategory(str, Enum):
    """Categories of tenant law."""
    LEASE_TERMS = "lease_terms"
    RENT_PAYMENT = "rent_payment"
    SECURITY_DEPOSIT = "security_deposit"
    HABITABILITY = "habitability"
    REPAIRS = "repairs"
    EVICTION = "eviction"
    NOTICE_REQUIREMENTS = "notice_requirements"
    DISCRIMINATION = "discrimination"
    PRIVACY = "privacy"
    RETALIATION = "retaliation"
    LEASE_TERMINATION = "lease_termination"
    SUBLETTING = "subletting"
    UTILITIES = "utilities"
    ENTRY_ACCESS = "entry_access"
    OTHER = "other"


@dataclass
class LawReference:
    """A reference to applicable law."""
    id: str
    category: LawCategory
    title: str
    summary: str
    jurisdiction: str  # "federal", "minnesota", "dakota_county", or "general"
    statute_citation: Optional[str] = None
    key_points: Optional[list[str]] = None
    tenant_rights: Optional[list[str]] = None
    landlord_obligations: Optional[list[str]] = None
    time_limits: Optional[dict] = None  # {"action": "days"}
    keywords: Optional[list[str]] = None  # For matching documents
    
    def to_dict(self) -> dict:
        data = asdict(self)
        data["category"] = self.category.value
        return data
    
    @classmethod
    def from_dict(cls, data: dict) -> "LawReference":
        if data.get("category"):
            data["category"] = LawCategory(data["category"])
        return cls(**data)


@dataclass 
class CrossReference:
    """A match between a document and applicable law."""
    doc_id: str
    law_id: str
    relevance_score: float  # 0.0 - 1.0
    matched_keywords: list[str]
    explanation: str
    created_at: datetime


class LawEngine:
    """
    Law cross-reference engine.
    - Stores law references
    - Matches documents to applicable laws
    - Learns from user confirmations
    """

    def __init__(self, data_dir: str = "data/laws"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        self._laws: dict[str, LawReference] = {}
        self._cross_refs: list[CrossReference] = []
        
        self._load_data()
        self._seed_base_laws()

    def _load_data(self):
        """Load laws and cross-references from disk."""
        laws_file = self.data_dir / "laws.json"
        if laws_file.exists():
            try:
                with open(laws_file) as f:
                    data = json.load(f)
                    for law_id, law_data in data.items():
                        self._laws[law_id] = LawReference.from_dict(law_data)
            except Exception:
                pass

    def _save_data(self):
        """Save laws to disk."""
        laws_file = self.data_dir / "laws.json"
        data = {law_id: law.to_dict() for law_id, law in self._laws.items()}
        with open(laws_file, "w") as f:
            json.dump(data, f, indent=2)

    def _seed_base_laws(self):
        """Seed the engine with base tenant law knowledge."""
        if self._laws:
            return  # Already seeded
        
        base_laws = [
            LawReference(
                id="security_deposit_general",
                category=LawCategory.SECURITY_DEPOSIT,
                title="Security Deposit Limits and Return",
                summary="Landlords must return security deposits within a specified time after move-out, minus documented deductions.",
                jurisdiction="general",
                key_points=[
                    "Deposit must be returned within statutory timeframe",
                    "Deductions must be itemized in writing",
                    "Landlord must provide receipts for repairs",
                    "Tenant may sue for wrongful withholding"
                ],
                tenant_rights=[
                    "Right to itemized statement of deductions",
                    "Right to return of deposit within time limit",
                    "Right to sue for wrongful retention"
                ],
                landlord_obligations=[
                    "Return deposit within statutory period",
                    "Provide written itemized statement",
                    "Document damage beyond normal wear"
                ],
                keywords=["security deposit", "deposit return", "damage deduction", "move out", "move-out inspection"]
            ),
            LawReference(
                id="habitability_general",
                category=LawCategory.HABITABILITY,
                title="Implied Warranty of Habitability",
                summary="Landlords must maintain rental property in habitable condition with working essential services.",
                jurisdiction="general",
                key_points=[
                    "Heat, water, electricity must work",
                    "No serious health or safety hazards",
                    "Structural integrity maintained",
                    "Tenant may withhold rent or repair-and-deduct"
                ],
                tenant_rights=[
                    "Right to habitable living conditions",
                    "Right to repair and deduct (with notice)",
                    "Right to withhold rent for serious violations",
                    "Right to terminate lease for uninhabitable conditions"
                ],
                landlord_obligations=[
                    "Maintain essential services",
                    "Make timely repairs",
                    "Address health and safety issues"
                ],
                keywords=["habitability", "repairs", "maintenance", "heat", "water", "plumbing", "electrical", "mold", "pest", "infestation"]
            ),
            LawReference(
                id="eviction_notice_general",
                category=LawCategory.EVICTION,
                title="Eviction Notice Requirements",
                summary="Landlords must follow proper legal procedures and provide adequate notice before eviction.",
                jurisdiction="general",
                key_points=[
                    "Written notice required before filing",
                    "Notice period varies by reason",
                    "Self-help eviction is illegal",
                    "Tenant has right to contest in court"
                ],
                tenant_rights=[
                    "Right to proper written notice",
                    "Right to cure violations if applicable",
                    "Right to court hearing",
                    "Protection from illegal lockouts"
                ],
                landlord_obligations=[
                    "Provide proper written notice",
                    "Allow cure period where required",
                    "File in court - no self-help",
                    "Follow legal process for removal"
                ],
                time_limits={
                    "nonpayment_notice": "3-14 days typically",
                    "lease_violation_cure": "varies by jurisdiction",
                    "no_cause_notice": "30-60 days typically"
                },
                keywords=["eviction", "notice to quit", "pay or quit", "vacate", "termination", "unlawful detainer"]
            ),
            LawReference(
                id="retaliation_general",
                category=LawCategory.RETALIATION,
                title="Protection Against Retaliation",
                summary="Landlords cannot retaliate against tenants for exercising legal rights.",
                jurisdiction="general",
                key_points=[
                    "Protected activities include complaints to authorities",
                    "Retaliation presumed if action within 90 days",
                    "Tenant may have defense to eviction",
                    "May recover damages for retaliation"
                ],
                tenant_rights=[
                    "Right to complain about conditions",
                    "Right to contact housing authorities",
                    "Right to join tenant organizations",
                    "Right to assert legal rights"
                ],
                keywords=["retaliation", "retaliatory eviction", "complaint", "housing authority", "code enforcement"]
            ),
            LawReference(
                id="entry_access_general",
                category=LawCategory.ENTRY_ACCESS,
                title="Landlord Entry and Access",
                summary="Landlords must provide reasonable notice before entering rental unit.",
                jurisdiction="general",
                key_points=[
                    "24-48 hours notice typically required",
                    "Entry only for legitimate purposes",
                    "Emergency entry exception",
                    "Tenant may refuse unreasonable entry"
                ],
                tenant_rights=[
                    "Right to advance notice of entry",
                    "Right to quiet enjoyment",
                    "Right to refuse entry without notice"
                ],
                landlord_obligations=[
                    "Provide reasonable advance notice",
                    "Enter only at reasonable times",
                    "Limit entry to legitimate purposes"
                ],
                time_limits={
                    "notice_for_entry": "24-48 hours typical"
                },
                keywords=["entry", "access", "notice", "privacy", "inspection", "showing", "landlord entry"]
            ),
            LawReference(
                id="rent_increase_general",
                category=LawCategory.RENT_PAYMENT,
                title="Rent Increase Requirements",
                summary="Rent increases must follow proper notice procedures and lease terms.",
                jurisdiction="general",
                key_points=[
                    "Cannot increase during lease term without clause",
                    "Written notice required for increase",
                    "Notice period varies by jurisdiction",
                    "No rent control in most areas"
                ],
                tenant_rights=[
                    "Right to notice of rent increase",
                    "Right to refuse increase and terminate",
                    "Protection from increase during lease"
                ],
                time_limits={
                    "rent_increase_notice": "30-60 days typical"
                },
                keywords=["rent increase", "rent raise", "rent hike", "rent change"]
            ),
            LawReference(
                id="lease_termination_general",
                category=LawCategory.LEASE_TERMINATION,
                title="Lease Termination and Renewal",
                summary="Rules for ending tenancy and lease renewal/non-renewal.",
                jurisdiction="general",
                key_points=[
                    "Written notice required to end month-to-month",
                    "Fixed-term leases end on their own date",
                    "Early termination may require cause or penalty",
                    "Some jurisdictions require renewal notice"
                ],
                tenant_rights=[
                    "Right to notice of non-renewal",
                    "Right to terminate with proper notice",
                    "Protection from mid-lease termination without cause"
                ],
                time_limits={
                    "month_to_month_notice": "30 days typical",
                    "non_renewal_notice": "varies"
                },
                keywords=["termination", "end lease", "move out", "non-renewal", "renewal", "month-to-month"]
            )
        ]
        
        for law in base_laws:
            self._laws[law.id] = law
        
        self._save_data()

    def add_law(self, law: LawReference) -> None:
        """Add a new law reference."""
        self._laws[law.id] = law
        self._save_data()

    def get_law(self, law_id: str) -> Optional[LawReference]:
        """Get a law by ID."""
        return self._laws.get(law_id)

    def get_laws_by_category(self, category: LawCategory) -> list[LawReference]:
        """Get all laws in a category."""
        return [law for law in self._laws.values() if law.category == category]

    def get_all_laws(self) -> list[LawReference]:
        """Get all laws."""
        return list(self._laws.values())

    def match_document(
        self,
        doc_type: str,
        doc_text: str,
        doc_terms: list[str]
    ) -> list[tuple[LawReference, float, list[str]]]:
        """
        Match a document to applicable laws.
        Returns list of (law, relevance_score, matched_keywords).
        """
        matches = []
        doc_text_lower = doc_text.lower()
        doc_terms_lower = [t.lower() for t in doc_terms]
        
        for law in self._laws.values():
            if not law.keywords:
                continue
            
            matched_keywords = []
            for keyword in law.keywords:
                keyword_lower = keyword.lower()
                if keyword_lower in doc_text_lower:
                    matched_keywords.append(keyword)
                elif any(keyword_lower in term for term in doc_terms_lower):
                    matched_keywords.append(keyword)
            
            if matched_keywords:
                # Calculate relevance score
                score = len(matched_keywords) / len(law.keywords)
                score = min(1.0, score * 1.2)  # Boost but cap at 1.0
                matches.append((law, score, matched_keywords))
        
        # Sort by relevance
        matches.sort(key=lambda x: x[1], reverse=True)
        return matches

    def get_applicable_laws(
        self,
        doc_type: str,
        doc_text: str,
        doc_terms: list[str],
        min_score: float = 0.3
    ) -> list[dict]:
        """
        Get applicable laws for a document with explanations.
        Returns list of dicts with law info and match details.
        """
        matches = self.match_document(doc_type, doc_text, doc_terms)
        
        results = []
        for law, score, keywords in matches:
            if score >= min_score:
                results.append({
                    "law_id": law.id,
                    "category": law.category.value,
                    "title": law.title,
                    "summary": law.summary,
                    "jurisdiction": law.jurisdiction,
                    "relevance_score": round(score, 2),
                    "matched_keywords": keywords,
                    "tenant_rights": law.tenant_rights,
                    "time_limits": law.time_limits
                })
        
        return results

    def get_rights_summary(self, user_id: str, documents: list) -> dict:
        """
        Generate a summary of tenant rights based on their documents.
        """
        all_categories = set()
        all_rights = []
        all_deadlines = []
        
        for doc in documents:
            doc_text = doc.full_text or ""
            doc_terms = doc.key_terms or []
            doc_type = doc.doc_type.value if doc.doc_type else "unknown"
            
            applicable = self.get_applicable_laws(doc_type, doc_text, doc_terms)
            
            for law_info in applicable:
                all_categories.add(law_info["category"])
                
                if law_info.get("tenant_rights"):
                    for right in law_info["tenant_rights"]:
                        if right not in all_rights:
                            all_rights.append(right)
                
                if law_info.get("time_limits"):
                    for action, timeframe in law_info["time_limits"].items():
                        all_deadlines.append({
                            "action": action.replace("_", " ").title(),
                            "timeframe": timeframe,
                            "from_law": law_info["title"]
                        })
        
        return {
            "categories_involved": list(all_categories),
            "your_rights": all_rights[:10],  # Top 10 most relevant
            "important_deadlines": all_deadlines,
            "documents_analyzed": len(documents)
        }

    async def find_violations(
        self,
        case_data: dict,
        user_id: str = None
    ) -> List[Dict]:
        """
        Analyze case data for potential landlord violations.
        Publishes VIOLATION_FOUND events for each violation.
        
        Args:
            case_data: Case information including dates, amounts, notices
            user_id: User ID for event publishing
        
        Returns:
            List of violations found with law references
        """
        violations = []
        
        # Check notice requirements
        notice_date = case_data.get("notice_date")
        notice_type = case_data.get("notice_type")
        hearing_date = case_data.get("hearing_date")
        
        if notice_date and hearing_date:
            # Check if proper notice period was given
            from datetime import datetime
            try:
                notice = datetime.fromisoformat(notice_date)
                hearing = datetime.fromisoformat(hearing_date)
                days_notice = (hearing - notice).days
                
                required_days = 14  # Default for eviction
                if notice_type == "30-day":
                    required_days = 30
                elif notice_type == "7-day":
                    required_days = 7
                
                if days_notice < required_days:
                    violation = {
                        "id": "insufficient_notice",
                        "type": "notice_requirement",
                        "title": "Insufficient Notice Period",
                        "description": f"Only {days_notice} days notice given, {required_days} days required",
                        "law_ref": "MN Stat. 504B.135",
                        "severity": "high",
                        "defense_code": "IMPROPER_NOTICE"
                    }
                    violations.append(violation)
                    
                    # Publish event
                    if user_id:
                        try:
                            await event_bus.publish(
                                EventType.VIOLATION_FOUND,
                                {"violation": violation["title"], "law_ref": violation["law_ref"]},
                                source="law_engine",
                                user_id=user_id,
                            )
                        except Exception:
                            pass
            except Exception:
                pass
        
        # Check for habitability issues mentioned
        issues = case_data.get("habitability_issues", [])
        if issues:
            violation = {
                "id": "habitability",
                "type": "habitability",
                "title": "Habitability Violations",
                "description": f"Reported issues: {', '.join(issues)}",
                "law_ref": "MN Stat. 504B.161",
                "severity": "medium",
                "defense_code": "HABITABILITY"
            }
            violations.append(violation)
            
            if user_id:
                try:
                    await event_bus.publish(
                        EventType.VIOLATION_FOUND,
                        {"violation": violation["title"], "law_ref": violation["law_ref"]},
                        source="law_engine",
                        user_id=user_id,
                    )
                except Exception:
                    pass
        
        # Check rent calculation
        rent_claimed = case_data.get("rent_claimed", 0)
        actual_rent = case_data.get("monthly_rent", 0)
        if rent_claimed and actual_rent and rent_claimed > actual_rent * 3:
            violation = {
                "id": "excessive_damages",
                "type": "damages",
                "title": "Excessive Damages Claimed",
                "description": f"Claimed ${rent_claimed} exceeds reasonable amount",
                "law_ref": "MN Stat. 504B.291",
                "severity": "medium",
                "defense_code": "EXCESSIVE_DAMAGES"
            }
            violations.append(violation)
        
        logger.info(f"Found {len(violations)} potential violations")
        return violations
    
    def get_defense_strategies(self, violations: List[Dict]) -> List[Dict]:
        """
        Get recommended defense strategies based on violations found.
        """
        strategies = []
        
        for v in violations:
            defense_code = v.get("defense_code")
            if defense_code == "IMPROPER_NOTICE":
                strategies.append({
                    "code": "IMPROPER_NOTICE",
                    "title": "Challenge Notice Validity",
                    "description": "The notice period provided was insufficient under Minnesota law",
                    "strength": "strong",
                    "evidence_needed": ["Notice document", "Calendar showing dates"],
                    "forms_to_file": ["Answer with Affirmative Defense", "Motion to Dismiss"],
                })
            elif defense_code == "HABITABILITY":
                strategies.append({
                    "code": "HABITABILITY",
                    "title": "Habitability Defense",
                    "description": "Landlord failed to maintain habitable conditions",
                    "strength": "strong",
                    "evidence_needed": ["Photos of conditions", "Repair requests", "Communication records"],
                    "forms_to_file": ["Answer with Counterclaim", "Motion for Rent Escrow"],
                })
            elif defense_code == "EXCESSIVE_DAMAGES":
                strategies.append({
                    "code": "EXCESSIVE_DAMAGES",
                    "title": "Challenge Damages Amount",
                    "description": "Damages claimed exceed actual losses",
                    "strength": "medium",
                    "evidence_needed": ["Rent receipts", "Lease showing rent amount"],
                    "forms_to_file": ["Answer disputing damages"],
                })
        
        return strategies


# Singleton instance
_law_engine: Optional[LawEngine] = None


def get_law_engine() -> LawEngine:
    """Get or create law engine instance."""
    global _law_engine
    if _law_engine is None:
        _law_engine = LawEngine()
    return _law_engine
