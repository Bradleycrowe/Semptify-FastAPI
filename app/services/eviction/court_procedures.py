"""
Court Procedures, Rules, Motions & Objection Handlers for Dakota County Eviction Defense.

Minnesota Rules of Civil Procedure (expedited eviction actions) plus
Dakota County local rules and common objection/response patterns.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
from datetime import datetime, timedelta


# =============================================================================
# ENUMS - Motion Types, Objection Types, Procedure Phases
# =============================================================================

class MotionType(str, Enum):
    """Common motions in eviction defense."""
    DISMISS_IMPROPER_SERVICE = "dismiss_improper_service"
    DISMISS_DEFECTIVE_NOTICE = "dismiss_defective_notice"
    DISMISS_WRONG_VENUE = "dismiss_wrong_venue"
    DISMISS_LACK_STANDING = "dismiss_lack_standing"
    CONTINUANCE = "continuance"
    STAY_OF_EXECUTION = "stay_of_execution"
    MOTION_TO_COMPEL = "motion_to_compel"
    MOTION_FOR_DISCOVERY = "motion_for_discovery"
    MOTION_TO_QUASH = "motion_to_quash"
    MOTION_IN_LIMINE = "motion_in_limine"
    EXPUNGEMENT = "expungement"
    REDEMPTION = "redemption"


class ObjectionType(str, Enum):
    """Common objections raised by landlords and how to counter them."""
    HEARSAY = "hearsay"
    RELEVANCE = "relevance"
    FOUNDATION = "foundation"
    BEST_EVIDENCE = "best_evidence"
    LEADING_QUESTION = "leading_question"
    SPECULATION = "speculation"
    ARGUMENTATIVE = "argumentative"
    ASKED_AND_ANSWERED = "asked_and_answered"
    BEYOND_SCOPE = "beyond_scope"
    IMPROPER_CHARACTER = "improper_character"
    PAROL_EVIDENCE = "parol_evidence"


class ProcedurePhase(str, Enum):
    """Phases of an eviction proceeding."""
    PRE_FILING = "pre_filing"
    SUMMONS_SERVICE = "summons_service"
    ANSWER_PERIOD = "answer_period"
    DISCOVERY = "discovery"
    PRE_HEARING_MOTIONS = "pre_hearing_motions"
    HEARING = "hearing"
    POST_HEARING = "post_hearing"
    APPEAL = "appeal"
    EXECUTION = "execution"


class DefenseCategory(str, Enum):
    """Categories of eviction defenses under Minnesota law."""
    PROCEDURAL = "procedural"
    HABITABILITY = "habitability"
    RETALIATION = "retaliation"
    DISCRIMINATION = "discrimination"
    RENT_ESCROW = "rent_escrow"
    LEASE_VIOLATION = "lease_violation"
    PAYMENT = "payment"
    WAIVER = "waiver"
    ESTOPPEL = "estoppel"


# =============================================================================
# DATA CLASSES - Structured Court Data
# =============================================================================

@dataclass
class MinnesotaEvictionRule:
    """A specific rule governing Minnesota eviction proceedings."""
    rule_id: str
    title: str
    statute: str
    summary: str
    deadline_days: Optional[int] = None
    applies_to: list[ProcedurePhase] = field(default_factory=list)
    tenant_action: Optional[str] = None
    landlord_obligation: Optional[str] = None
    consequence_if_violated: Optional[str] = None


@dataclass
class MotionTemplate:
    """Template for generating court motions."""
    motion_type: MotionType
    title: str
    legal_basis: list[str]
    required_facts: list[str]
    template_text: str
    supporting_evidence: list[str]
    success_factors: list[str]
    common_responses: list[str]


@dataclass
class ObjectionResponse:
    """How to respond when landlord raises an objection."""
    objection_type: ObjectionType
    definition: str
    when_valid: str
    how_to_overcome: list[str]
    example_response: str
    supporting_rule: str


@dataclass
class ProcedureStep:
    """A step in the eviction court procedure."""
    phase: ProcedurePhase
    step_number: int
    title: str
    description: str
    deadline: Optional[str] = None
    tenant_tasks: list[str] = field(default_factory=list)
    documents_needed: list[str] = field(default_factory=list)
    tips: list[str] = field(default_factory=list)


@dataclass
class CounterclaimType:
    """Types of counterclaims available to tenants."""
    code: str
    title: str
    legal_basis: str
    elements_to_prove: list[str]
    damages_available: list[str]
    evidence_needed: list[str]
    statute_of_limitations: str


# =============================================================================
# COURT PROCEDURES ENGINE
# =============================================================================

class CourtProceduresEngine:
    """
    Comprehensive engine for Minnesota eviction court procedures,
    motions, objections, and counterclaims.
    """

    def __init__(self):
        self._rules = self._load_mn_eviction_rules()
        self._motions = self._load_motion_templates()
        self._objections = self._load_objection_responses()
        self._procedures = self._load_procedure_steps()
        self._counterclaims = self._load_counterclaim_types()
        self._defenses = self._load_defense_strategies()

    # -------------------------------------------------------------------------
    # MINNESOTA EVICTION RULES
    # -------------------------------------------------------------------------

    def _load_mn_eviction_rules(self) -> dict[str, MinnesotaEvictionRule]:
        """Load Minnesota eviction rules and statutes."""
        rules = {}

        # Notice Requirements
        rules["notice_14_day"] = MinnesotaEvictionRule(
            rule_id="notice_14_day",
            title="14-Day Notice to Quit (Non-Payment)",
            statute="Minn. Stat. § 504B.135",
            summary="Landlord must give tenant 14 days written notice before filing eviction for non-payment of rent.",
            deadline_days=14,
            applies_to=[ProcedurePhase.PRE_FILING],
            tenant_action="Pay rent in full within 14 days to cure the default",
            landlord_obligation="Provide written notice specifying amount due and deadline",
            consequence_if_violated="Case may be dismissed for improper notice"
        )

        rules["notice_lease_violation"] = MinnesotaEvictionRule(
            rule_id="notice_lease_violation",
            title="Notice for Lease Violation",
            statute="Minn. Stat. § 504B.285",
            summary="For non-rent lease violations, notice period depends on lease terms and violation type.",
            deadline_days=None,
            applies_to=[ProcedurePhase.PRE_FILING],
            tenant_action="Cure the violation if curable within notice period",
            landlord_obligation="Specify the exact violation and give reasonable time to cure if curable",
            consequence_if_violated="Case may be dismissed; tenant may have affirmative defense"
        )

        rules["service_requirements"] = MinnesotaEvictionRule(
            rule_id="service_requirements",
            title="Service of Summons Requirements",
            statute="Minn. Stat. § 504B.331",
            summary="Summons must be served at least 7 days before the hearing date.",
            deadline_days=7,
            applies_to=[ProcedurePhase.SUMMONS_SERVICE],
            tenant_action="Verify proper service; challenge if defective",
            landlord_obligation="Serve via personal service, substituted service, or posting with mailing",
            consequence_if_violated="Case must be dismissed; landlord must re-serve"
        )

        rules["answer_deadline"] = MinnesotaEvictionRule(
            rule_id="answer_deadline",
            title="Answer Deadline",
            statute="Minn. R. Civ. P. 5.04",
            summary="Tenant should file Answer before hearing; can present defenses at hearing if no written answer.",
            deadline_days=None,
            applies_to=[ProcedurePhase.ANSWER_PERIOD],
            tenant_action="File written Answer with counterclaims before hearing for strongest defense",
            landlord_obligation="N/A",
            consequence_if_violated="Tenant may still defend at hearing but loses some procedural advantages"
        )

        rules["writ_of_recovery"] = MinnesotaEvictionRule(
            rule_id="writ_of_recovery",
            title="Writ of Recovery Execution",
            statute="Minn. Stat. § 504B.365",
            summary="After judgment, landlord must wait 24 hours (or 7 days if tenant requests) before executing writ.",
            deadline_days=7,
            applies_to=[ProcedurePhase.EXECUTION],
            tenant_action="Request 7-day stay; move out or appeal within that time",
            landlord_obligation="Cannot execute writ during stay period",
            consequence_if_violated="Wrongful eviction; tenant may sue for damages"
        )

        rules["rent_escrow"] = MinnesotaEvictionRule(
            rule_id="rent_escrow",
            title="Rent Escrow Action",
            statute="Minn. Stat. § 504B.385",
            summary="Tenant may deposit rent with court if landlord fails to maintain premises.",
            deadline_days=None,
            applies_to=[ProcedurePhase.PRE_FILING, ProcedurePhase.HEARING],
            tenant_action="File rent escrow petition; deposit rent with court",
            landlord_obligation="Make repairs or rent is released to tenant/applied to repairs",
            consequence_if_violated="N/A - this is a tenant remedy"
        )

        rules["expungement"] = MinnesotaEvictionRule(
            rule_id="expungement",
            title="Eviction Record Expungement",
            statute="Minn. Stat. § 484.014",
            summary="Court records may be expunged if case dismissed, tenant prevails, or certain conditions met.",
            deadline_days=None,
            applies_to=[ProcedurePhase.POST_HEARING],
            tenant_action="File motion for expungement; demonstrate grounds",
            landlord_obligation="N/A",
            consequence_if_violated="N/A"
        )

        rules["retaliation_protection"] = MinnesotaEvictionRule(
            rule_id="retaliation_protection",
            title="Retaliation Protection",
            statute="Minn. Stat. § 504B.441",
            summary="Landlord cannot evict in retaliation for tenant exercising legal rights.",
            deadline_days=90,
            applies_to=[ProcedurePhase.HEARING],
            tenant_action="Raise retaliation defense if eviction follows protected activity within 90 days",
            landlord_obligation="Must have legitimate, non-retaliatory reason for eviction",
            consequence_if_violated="Case dismissed; tenant may recover damages"
        )

        return rules

    # -------------------------------------------------------------------------
    # MOTION TEMPLATES
    # -------------------------------------------------------------------------

    def _load_motion_templates(self) -> dict[MotionType, MotionTemplate]:
        """Load motion templates for common defense motions."""
        motions = {}

        motions[MotionType.DISMISS_IMPROPER_SERVICE] = MotionTemplate(
            motion_type=MotionType.DISMISS_IMPROPER_SERVICE,
            title="Motion to Dismiss for Improper Service",
            legal_basis=[
                "Minn. Stat. § 504B.331",
                "Minn. R. Civ. P. 4.03",
                "Due Process Clause, U.S. Const. Amend. XIV"
            ],
            required_facts=[
                "Date and method of attempted service",
                "Why service was defective (wrong person, insufficient time, improper posting)",
                "Tenant's actual knowledge (or lack thereof) of the hearing"
            ],
            template_text="""MOTION TO DISMISS FOR IMPROPER SERVICE

Defendant respectfully moves this Court to dismiss the above-captioned action for the following reasons:

1. Plaintiff failed to properly serve Defendant with the Summons and Complaint as required by Minn. Stat. § 504B.331.

2. Specifically, [DESCRIBE SERVICE DEFECT: e.g., "service was made fewer than 7 days before the scheduled hearing," "service was made by posting without proper mailing," "service was made to a person not authorized to accept service"].

3. Proper service is a jurisdictional prerequisite. Without valid service, this Court lacks personal jurisdiction over Defendant.

4. Defendant was thereby denied due process of law.

WHEREFORE, Defendant requests that this action be dismissed without prejudice.""",
            supporting_evidence=[
                "Affidavit of Service (showing defect)",
                "Calendar showing fewer than 7 days",
                "Testimony about who received service"
            ],
            success_factors=[
                "Clear documentation of service defect",
                "Raise at earliest opportunity",
                "Landlord cannot cure defect mid-hearing"
            ],
            common_responses=[
                "Landlord may claim substantial compliance",
                "Landlord may request continuance to re-serve"
            ]
        )

        motions[MotionType.DISMISS_DEFECTIVE_NOTICE] = MotionTemplate(
            motion_type=MotionType.DISMISS_DEFECTIVE_NOTICE,
            title="Motion to Dismiss for Defective Notice",
            legal_basis=[
                "Minn. Stat. § 504B.135 (14-day notice)",
                "Minn. Stat. § 504B.285 (lease termination)",
                "Lease agreement terms"
            ],
            required_facts=[
                "Date notice was given (or not given)",
                "Content of notice (or deficiencies)",
                "Whether notice complied with statute and lease"
            ],
            template_text="""MOTION TO DISMISS FOR DEFECTIVE NOTICE

Defendant respectfully moves this Court to dismiss this action because Plaintiff failed to provide legally sufficient notice:

1. Minnesota law requires [14 days written notice for non-payment / proper notice for lease violations].

2. Plaintiff's notice was defective because [DESCRIBE DEFECT: e.g., "no notice was provided," "notice was only 10 days," "notice did not specify the amount due," "notice did not identify the specific lease violation"].

3. Compliance with notice requirements is a condition precedent to an eviction action.

4. Because Plaintiff failed to comply, this action is premature and must be dismissed.

WHEREFORE, Defendant requests dismissal without prejudice.""",
            supporting_evidence=[
                "Copy of defective notice (or absence of notice)",
                "Lease agreement showing notice requirements",
                "Timeline showing insufficient notice period"
            ],
            success_factors=[
                "Specific identification of defect",
                "Landlord cannot cure notice defect at hearing",
                "Even one-day shortage is grounds for dismissal"
            ],
            common_responses=[
                "Landlord may claim tenant had actual notice",
                "Landlord may argue substantial compliance"
            ]
        )

        motions[MotionType.CONTINUANCE] = MotionTemplate(
            motion_type=MotionType.CONTINUANCE,
            title="Motion for Continuance",
            legal_basis=[
                "Minn. R. Civ. P. 6.02",
                "Due Process - right to prepare defense",
                "Court's inherent authority"
            ],
            required_facts=[
                "Reason continuance is needed",
                "How much time is requested",
                "Prejudice to tenant without continuance"
            ],
            template_text="""MOTION FOR CONTINUANCE

Defendant respectfully requests a continuance of the hearing scheduled for [DATE] for the following reasons:

1. Defendant needs additional time to [REASON: e.g., "obtain legal representation," "gather evidence," "arrange for witnesses," "obtain documents from landlord"].

2. Defendant requests a continuance of [NUMBER] days.

3. Without this continuance, Defendant will be unable to adequately prepare a defense, resulting in a denial of due process.

4. Defendant is not seeking delay for improper purposes and will be prepared to proceed on the new date.

5. [If applicable: Defendant is current on rent / willing to pay rent into court during continuance.]

WHEREFORE, Defendant requests that this hearing be continued to [DATE or "a date convenient to the Court"].""",
            supporting_evidence=[
                "Documentation of need (medical records, work schedule, etc.)",
                "Proof of diligent efforts to prepare",
                "Rent payment or offer to escrow"
            ],
            success_factors=[
                "Request as early as possible",
                "Offer to pay rent into escrow",
                "Show specific reason, not just 'need more time'"
            ],
            common_responses=[
                "Landlord will argue delay causes economic harm",
                "Court may grant short continuance with conditions"
            ]
        )

        motions[MotionType.STAY_OF_EXECUTION] = MotionTemplate(
            motion_type=MotionType.STAY_OF_EXECUTION,
            title="Motion for Stay of Execution of Writ",
            legal_basis=[
                "Minn. Stat. § 504B.365",
                "Court's equitable authority",
                "Hardship considerations"
            ],
            required_facts=[
                "Judgment has been entered against tenant",
                "Specific hardship requiring additional time",
                "Plan for vacating or appealing"
            ],
            template_text="""MOTION FOR STAY OF EXECUTION

Defendant requests that the Court stay execution of the Writ of Recovery for [7 days / additional time]:

1. A judgment for possession has been entered against Defendant.

2. Defendant requires additional time because [HARDSHIP: e.g., "Defendant has minor children and needs time to arrange alternative housing," "Defendant is elderly/disabled and requires assistance to move," "Defendant is appealing this judgment"].

3. Minnesota law provides that a tenant may request up to 7 days before the writ is executed.

4. [If appealing: Defendant has filed / intends to file a notice of appeal and posts this request in conjunction therewith.]

5. A stay will not substantially prejudice Plaintiff, who will receive possession upon expiration of the stay.

WHEREFORE, Defendant requests a stay of execution for [TIME PERIOD].""",
            supporting_evidence=[
                "Documentation of hardship",
                "Proof of efforts to find new housing",
                "Notice of appeal (if applicable)"
            ],
            success_factors=[
                "Request within 24 hours of judgment",
                "Demonstrate specific hardship",
                "Have a concrete plan"
            ],
            common_responses=[
                "Landlord will argue tenant had time to prepare",
                "Court will likely grant 7-day statutory stay"
            ]
        )

        motions[MotionType.EXPUNGEMENT] = MotionTemplate(
            motion_type=MotionType.EXPUNGEMENT,
            title="Motion for Expungement of Eviction Record",
            legal_basis=[
                "Minn. Stat. § 484.014",
                "Court's inherent authority",
                "Privacy interests"
            ],
            required_facts=[
                "Case outcome (dismissal, tenant prevailed, or other grounds)",
                "Why expungement is appropriate",
                "Harm from continued public record"
            ],
            template_text="""MOTION FOR EXPUNGEMENT

Defendant respectfully moves for expungement of the court records in this matter:

1. This eviction action was [resolved by: dismissal / judgment in favor of Defendant / settlement with no finding of wrongdoing].

2. Under Minn. Stat. § 484.014, expungement is appropriate when [GROUNDS: e.g., "the case was dismissed," "judgment was entered in favor of the tenant," "the parties have agreed to expungement"].

3. The continued existence of this record on Defendant's public record causes harm because [HARM: e.g., "it appears in tenant screening reports," "it prevents Defendant from obtaining housing," "the underlying dispute has been resolved"].

4. Expungement serves the interests of justice because [REASON].

WHEREFORE, Defendant requests that the Court order expungement of all records in this matter.""",
            supporting_evidence=[
                "Case disposition showing grounds for expungement",
                "Evidence of harm from record",
                "Settlement agreement (if applicable)"
            ],
            success_factors=[
                "Clear grounds under statute",
                "Demonstrate concrete harm",
                "No outstanding judgment against tenant"
            ],
            common_responses=[
                "Landlord may argue public interest in records",
                "Court has discretion even when grounds exist"
            ]
        )

        return motions

    # -------------------------------------------------------------------------
    # OBJECTION RESPONSES
    # -------------------------------------------------------------------------

    def _load_objection_responses(self) -> dict[ObjectionType, ObjectionResponse]:
        """Load responses to common landlord objections."""
        objections = {}

        objections[ObjectionType.HEARSAY] = ObjectionResponse(
            objection_type=ObjectionType.HEARSAY,
            definition="An out-of-court statement offered to prove the truth of the matter asserted.",
            when_valid="When tenant tries to introduce what someone else said as proof of what they said.",
            how_to_overcome=[
                "Not offered for truth - offered to show effect on listener or notice",
                "Statement by party-opponent (landlord's own words)",
                "Present sense impression or excited utterance",
                "Business records exception (with proper foundation)",
                "Statement against interest"
            ],
            example_response="Your Honor, this is not hearsay. I'm not offering this to prove [X is true], but to show that I was on notice of the condition. Alternatively, this is a statement by the landlord, a party-opponent, which is excluded from hearsay under Rule 801(d)(2).",
            supporting_rule="Minn. R. Evid. 801, 803, 804"
        )

        objections[ObjectionType.RELEVANCE] = ObjectionResponse(
            objection_type=ObjectionType.RELEVANCE,
            definition="Evidence must have a tendency to make a fact of consequence more or less probable.",
            when_valid="When evidence has no connection to the issues in the case.",
            how_to_overcome=[
                "Explain the logical connection to an issue in the case",
                "Connect to an element of defense or counterclaim",
                "Show it affects credibility of a witness",
                "Demonstrate it provides context"
            ],
            example_response="Your Honor, this evidence is relevant because it goes directly to my defense of [habitability/retaliation/etc.]. It shows that [explain connection]. The landlord's [action/inaction] is directly at issue here.",
            supporting_rule="Minn. R. Evid. 401, 402"
        )

        objections[ObjectionType.FOUNDATION] = ObjectionResponse(
            objection_type=ObjectionType.FOUNDATION,
            definition="Evidence must be authenticated or have a proper basis before being admitted.",
            when_valid="When evidence is introduced without showing it is what it claims to be.",
            how_to_overcome=[
                "Testify to personal knowledge of the document/photo",
                "Identify when and where you created/received it",
                "For photos: state when taken, what it depicts, that it accurately shows the condition",
                "For documents: identify your signature or the landlord's"
            ],
            example_response="Your Honor, I can lay foundation. I took this photo on [date] at [location]. It accurately depicts the condition of [describe]. I recognize this document because I received it from the landlord on [date].",
            supporting_rule="Minn. R. Evid. 901, 902"
        )

        objections[ObjectionType.BEST_EVIDENCE] = ObjectionResponse(
            objection_type=ObjectionType.BEST_EVIDENCE,
            definition="To prove the contents of a writing, the original is generally required.",
            when_valid="When proving what a document says without producing the original.",
            how_to_overcome=[
                "Produce the original document",
                "Explain why original is unavailable (lost, destroyed, in opponent's possession)",
                "Show copy is accurate and reliable",
                "For electronic records: print is admissible as original"
            ],
            example_response="Your Honor, I have the original here. [Or] The original is in the landlord's possession and they have not produced it despite my request. This copy accurately reflects the original.",
            supporting_rule="Minn. R. Evid. 1001-1004"
        )

        objections[ObjectionType.LEADING_QUESTION] = ObjectionResponse(
            objection_type=ObjectionType.LEADING_QUESTION,
            definition="A question that suggests the answer within it.",
            when_valid="On direct examination of your own witness (but allowed on cross).",
            how_to_overcome=[
                "Rephrase as open-ended question",
                "Ask 'what,' 'when,' 'where,' 'how' instead",
                "Note: leading is allowed on cross-examination of adverse party"
            ],
            example_response="I'll rephrase, Your Honor. [Instead of 'The apartment had mold, didn't it?' ask 'What conditions did you observe in the apartment?']",
            supporting_rule="Minn. R. Evid. 611(c)"
        )

        objections[ObjectionType.SPECULATION] = ObjectionResponse(
            objection_type=ObjectionType.SPECULATION,
            definition="Witness is guessing rather than testifying to personal knowledge.",
            when_valid="When witness testifies to something they don't actually know.",
            how_to_overcome=[
                "Clarify the basis for your knowledge",
                "Testify only to what you personally observed",
                "If making an inference, explain the facts supporting it"
            ],
            example_response="Your Honor, I'm not speculating. I personally observed [X]. Based on what I saw, heard, and experienced, I know [Y].",
            supporting_rule="Minn. R. Evid. 602"
        )

        objections[ObjectionType.PAROL_EVIDENCE] = ObjectionResponse(
            objection_type=ObjectionType.PAROL_EVIDENCE,
            definition="Prior or contemporaneous oral agreements cannot contradict a written contract.",
            when_valid="When tenant tries to contradict clear lease terms with oral statements.",
            how_to_overcome=[
                "Not contradicting, but explaining ambiguous term",
                "Evidence of fraud, mistake, or duress",
                "Subsequent modification (oral modification may be allowed)",
                "Collateral agreement on separate matter",
                "Evidence of implied warranty of habitability (cannot be waived)"
            ],
            example_response="Your Honor, I'm not trying to contradict the lease. I'm showing that the landlord's oral representation was fraudulent, OR that this evidence relates to the implied warranty of habitability which cannot be waived by lease terms.",
            supporting_rule="Common law; Minn. Stat. § 504B.161 (habitability cannot be waived)"
        )

        return objections

    # -------------------------------------------------------------------------
    # PROCEDURE STEPS
    # -------------------------------------------------------------------------

    def _load_procedure_steps(self) -> list[ProcedureStep]:
        """Load step-by-step eviction procedure guide."""
        steps = []

        # Pre-Filing Phase
        steps.append(ProcedureStep(
            phase=ProcedurePhase.PRE_FILING,
            step_number=1,
            title="Notice Period",
            description="Landlord must provide proper written notice before filing eviction. For non-payment, this is 14 days.",
            deadline="14 days (non-payment) or per lease (other violations)",
            tenant_tasks=[
                "Review notice carefully for defects",
                "Note the date you received it",
                "Check if amount claimed is accurate",
                "Consider paying to cure if possible",
                "Document any landlord violations"
            ],
            documents_needed=[
                "Copy of notice received",
                "Lease agreement",
                "Rent payment records",
                "Photos of any habitability issues"
            ],
            tips=[
                "Defective notice = grounds for dismissal",
                "14 days means 14 FULL days, not including service day",
                "Even if you owe rent, you may have defenses"
            ]
        ))

        # Service Phase
        steps.append(ProcedureStep(
            phase=ProcedurePhase.SUMMONS_SERVICE,
            step_number=2,
            title="Service of Summons",
            description="Landlord must serve you with Summons and Complaint at least 7 days before hearing.",
            deadline="At least 7 days before hearing",
            tenant_tasks=[
                "Note exact date and method of service",
                "Check if 7 full days before hearing",
                "Verify your name and address are correct",
                "Read the Complaint carefully"
            ],
            documents_needed=[
                "Summons and Complaint",
                "Note of when/how served"
            ],
            tips=[
                "Improper service = case dismissed",
                "Posting service requires mailing too",
                "Service on wrong person may be defective"
            ]
        ))

        # Answer Phase
        steps.append(ProcedureStep(
            phase=ProcedurePhase.ANSWER_PERIOD,
            step_number=3,
            title="File Your Answer",
            description="File written Answer with defenses and counterclaims before hearing.",
            deadline="Before hearing (no strict deadline, but earlier is better)",
            tenant_tasks=[
                "Complete Answer form",
                "List all defenses",
                "Include counterclaims if applicable",
                "File with court clerk",
                "Serve copy on landlord"
            ],
            documents_needed=[
                "Answer & Counterclaim form",
                "Evidence supporting defenses",
                "Filing fee (or fee waiver if qualified)"
            ],
            tips=[
                "You can defend at hearing without written Answer, but it's stronger with one",
                "Counterclaims can offset rent owed",
                "Fee waiver available for low-income tenants"
            ]
        ))

        # Hearing Phase
        steps.append(ProcedureStep(
            phase=ProcedurePhase.HEARING,
            step_number=4,
            title="The Hearing",
            description="Present your case to the judge. Landlord goes first, then you present defenses.",
            deadline="Appear on scheduled date and time",
            tenant_tasks=[
                "Arrive 15 minutes early",
                "Bring all documents and evidence",
                "Dress appropriately",
                "Be respectful to the judge",
                "Present your defenses clearly"
            ],
            documents_needed=[
                "All evidence (photos, receipts, communications)",
                "Witness list",
                "Copies for court and landlord",
                "Your Answer (if filed)"
            ],
            tips=[
                "Listen carefully - don't interrupt",
                "Address the judge as 'Your Honor'",
                "Stick to relevant facts",
                "Object to improper evidence",
                "Ask for clarification if confused"
            ]
        ))

        # Post-Hearing Phase
        steps.append(ProcedureStep(
            phase=ProcedurePhase.POST_HEARING,
            step_number=5,
            title="After the Hearing",
            description="Judge issues decision. If you lose, you have limited time to appeal or vacate.",
            deadline="24 hours to request 7-day stay; 15 days to appeal",
            tenant_tasks=[
                "Request 7-day stay if you lose",
                "Consider appeal if grounds exist",
                "Begin moving if staying not viable",
                "Request expungement if you win or case dismissed"
            ],
            documents_needed=[
                "Court order/judgment",
                "Notice of appeal (if appealing)",
                "Motion for expungement (if applicable)"
            ],
            tips=[
                "7-day stay is almost always granted - ask for it",
                "Appeal must be filed within 15 days",
                "Expungement protects your rental history"
            ]
        ))

        return steps

    # -------------------------------------------------------------------------
    # COUNTERCLAIM TYPES
    # -------------------------------------------------------------------------

    def _load_counterclaim_types(self) -> dict[str, CounterclaimType]:
        """Load available counterclaim types."""
        counterclaims = {}

        counterclaims["breach_habitability"] = CounterclaimType(
            code="breach_habitability",
            title="Breach of Implied Warranty of Habitability",
            legal_basis="Minn. Stat. § 504B.161",
            elements_to_prove=[
                "Landlord had duty to maintain habitable premises",
                "Premises had defects affecting habitability",
                "Tenant notified landlord of defects",
                "Landlord failed to repair in reasonable time",
                "Tenant suffered damages"
            ],
            damages_available=[
                "Rent abatement (reduction for diminished value)",
                "Cost of repairs tenant made",
                "Moving expenses if forced to leave",
                "Storage costs",
                "Consequential damages"
            ],
            evidence_needed=[
                "Photos/videos of conditions",
                "Written complaints to landlord",
                "Repair requests",
                "Inspector reports",
                "Medical records if health affected",
                "Receipts for repairs made"
            ],
            statute_of_limitations="6 years for contract claims"
        )

        counterclaims["retaliation"] = CounterclaimType(
            code="retaliation",
            title="Retaliatory Eviction",
            legal_basis="Minn. Stat. § 504B.441",
            elements_to_prove=[
                "Tenant engaged in protected activity",
                "Landlord took adverse action within 90 days",
                "Causal connection between activity and eviction",
                "Landlord's stated reason is pretextual"
            ],
            damages_available=[
                "Dismissal of eviction",
                "Actual damages",
                "Civil penalty up to $500",
                "Attorney fees"
            ],
            evidence_needed=[
                "Documentation of protected activity (complaint, organizing, etc.)",
                "Timeline showing proximity",
                "Landlord's knowledge of protected activity",
                "Evidence landlord's reason is pretextual"
            ],
            statute_of_limitations="90-day presumption period"
        )

        counterclaims["security_deposit"] = CounterclaimType(
            code="security_deposit",
            title="Security Deposit Violations",
            legal_basis="Minn. Stat. § 504B.178",
            elements_to_prove=[
                "Tenant paid security deposit",
                "Tenancy ended",
                "Landlord failed to return deposit within 21 days",
                "Or landlord made improper deductions"
            ],
            damages_available=[
                "Return of deposit",
                "Bad faith penalty (up to $500 in punitive damages)",
                "Interest on deposit"
            ],
            evidence_needed=[
                "Receipt for deposit",
                "Move-out inspection",
                "Photos of unit condition",
                "Landlord's itemization (or lack thereof)"
            ],
            statute_of_limitations="6 years"
        )

        counterclaims["lockout"] = CounterclaimType(
            code="lockout",
            title="Illegal Lockout / Self-Help Eviction",
            legal_basis="Minn. Stat. § 504B.375",
            elements_to_prove=[
                "Landlord locked out tenant",
                "Or removed tenant's property",
                "Or shut off utilities",
                "Without court order"
            ],
            damages_available=[
                "Actual damages",
                "Up to $500 civil penalty per violation",
                "Restoration of possession",
                "Attorney fees"
            ],
            evidence_needed=[
                "Photos of changed locks",
                "Utility shutoff records",
                "Photos of removed property",
                "Police report",
                "Witness statements"
            ],
            statute_of_limitations="6 years"
        )

        counterclaims["housing_code"] = CounterclaimType(
            code="housing_code",
            title="Housing Code Violations",
            legal_basis="Minn. Stat. § 504B.395; Local housing codes",
            elements_to_prove=[
                "Premises violated housing codes",
                "Tenant notified landlord",
                "Landlord failed to correct",
                "Tenant suffered damages"
            ],
            damages_available=[
                "Rent abatement",
                "Cost of alternative housing",
                "Medical expenses",
                "Moving costs"
            ],
            evidence_needed=[
                "City inspection reports",
                "Photos of violations",
                "Repair requests",
                "Medical records"
            ],
            statute_of_limitations="6 years"
        )

        return counterclaims

    # -------------------------------------------------------------------------
    # DEFENSE STRATEGIES
    # -------------------------------------------------------------------------

    def _load_defense_strategies(self) -> dict[DefenseCategory, dict]:
        """Load defense strategies by category."""
        defenses = {}

        defenses[DefenseCategory.PROCEDURAL] = {
            "name": "Procedural Defenses",
            "description": "Attack the landlord's process, not the substance",
            "defenses": [
                {
                    "code": "improper_notice",
                    "title": "Improper or Insufficient Notice",
                    "how_to_raise": "Motion to Dismiss or affirmative defense",
                    "what_to_show": "Notice was not given, too short, or defective in content"
                },
                {
                    "code": "improper_service",
                    "title": "Improper Service of Summons",
                    "how_to_raise": "Motion to Dismiss",
                    "what_to_show": "Service was not made properly or with enough time"
                },
                {
                    "code": "wrong_venue",
                    "title": "Wrong Venue",
                    "how_to_raise": "Motion to Dismiss or Transfer",
                    "what_to_show": "Case filed in wrong county"
                },
                {
                    "code": "lack_standing",
                    "title": "Lack of Standing",
                    "how_to_raise": "Motion to Dismiss",
                    "what_to_show": "Plaintiff is not the owner or authorized agent"
                }
            ]
        }

        defenses[DefenseCategory.HABITABILITY] = {
            "name": "Habitability Defenses",
            "description": "Landlord failed to maintain habitable premises",
            "defenses": [
                {
                    "code": "warranty_habitability",
                    "title": "Breach of Implied Warranty of Habitability",
                    "how_to_raise": "Affirmative defense and counterclaim",
                    "what_to_show": "Serious defects affecting health/safety; landlord knew; failed to repair"
                },
                {
                    "code": "rent_escrow",
                    "title": "Rent Escrow",
                    "how_to_raise": "File rent escrow petition",
                    "what_to_show": "Deposit rent with court due to landlord's failure to repair"
                }
            ]
        }

        defenses[DefenseCategory.RETALIATION] = {
            "name": "Retaliation Defense",
            "description": "Eviction is punishment for exercising legal rights",
            "defenses": [
                {
                    "code": "retaliation_complaint",
                    "title": "Retaliation for Complaint",
                    "how_to_raise": "Affirmative defense",
                    "what_to_show": "Filed complaint with city/reported code violations within 90 days before eviction"
                },
                {
                    "code": "retaliation_organizing",
                    "title": "Retaliation for Organizing",
                    "how_to_raise": "Affirmative defense",
                    "what_to_show": "Joined tenant organization or advocated for tenant rights"
                },
                {
                    "code": "retaliation_legal_action",
                    "title": "Retaliation for Legal Action",
                    "how_to_raise": "Affirmative defense",
                    "what_to_show": "Took legal action against landlord (rent escrow, etc.)"
                }
            ]
        }

        defenses[DefenseCategory.PAYMENT] = {
            "name": "Payment Defenses",
            "description": "Tenant paid or doesn't owe claimed amount",
            "defenses": [
                {
                    "code": "payment_made",
                    "title": "Payment Made",
                    "how_to_raise": "Deny amount owed; produce receipts",
                    "what_to_show": "Tenant paid rent; landlord's records are wrong"
                },
                {
                    "code": "waiver",
                    "title": "Waiver by Accepting Rent",
                    "how_to_raise": "Affirmative defense",
                    "what_to_show": "Landlord accepted rent after alleged breach"
                },
                {
                    "code": "accord_satisfaction",
                    "title": "Accord and Satisfaction",
                    "how_to_raise": "Affirmative defense",
                    "what_to_show": "Parties agreed to different amount; landlord accepted"
                }
            ]
        }

        return defenses

    # -------------------------------------------------------------------------
    # PUBLIC API METHODS
    # -------------------------------------------------------------------------

    def get_rule(self, rule_id: str) -> Optional[MinnesotaEvictionRule]:
        """Get a specific rule by ID."""
        return self._rules.get(rule_id)

    def get_all_rules(self) -> list[MinnesotaEvictionRule]:
        """Get all eviction rules."""
        return list(self._rules.values())

    def get_rules_by_phase(self, phase: ProcedurePhase) -> list[MinnesotaEvictionRule]:
        """Get rules applicable to a specific phase."""
        return [r for r in self._rules.values() if phase in r.applies_to]

    def get_motion_template(self, motion_type: MotionType) -> Optional[MotionTemplate]:
        """Get a motion template."""
        return self._motions.get(motion_type)

    def get_all_motions(self) -> list[MotionTemplate]:
        """Get all motion templates."""
        return list(self._motions.values())

    def get_objection_response(self, objection_type: ObjectionType) -> Optional[ObjectionResponse]:
        """Get response for an objection type."""
        return self._objections.get(objection_type)

    def get_all_objection_responses(self) -> list[ObjectionResponse]:
        """Get all objection responses."""
        return list(self._objections.values())

    def get_procedure_steps(self, phase: Optional[ProcedurePhase] = None) -> list[ProcedureStep]:
        """Get procedure steps, optionally filtered by phase."""
        if phase:
            return [s for s in self._procedures if s.phase == phase]
        return self._procedures

    def get_counterclaim_types(self) -> list[CounterclaimType]:
        """Get all counterclaim types."""
        return list(self._counterclaims.values())

    def get_counterclaim(self, code: str) -> Optional[CounterclaimType]:
        """Get specific counterclaim type."""
        return self._counterclaims.get(code)

    def get_defense_strategies(self, category: Optional[DefenseCategory] = None) -> dict:
        """Get defense strategies, optionally filtered by category."""
        if category:
            return self._defenses.get(category, {})
        return self._defenses

    def generate_motion(
        self,
        motion_type: MotionType,
        tenant_name: str,
        case_number: str,
        facts: dict
    ) -> str:
        """Generate a motion document with tenant's specific facts."""
        template = self._motions.get(motion_type)
        if not template:
            return f"Motion type {motion_type} not found"

        # Build the motion header
        motion = f"""STATE OF MINNESOTA                    DISTRICT COURT
COUNTY OF DAKOTA                      FIRST JUDICIAL DISTRICT

{facts.get('landlord_name', '[LANDLORD NAME]')},
    Plaintiff,                        Case No.: {case_number}

vs.

{tenant_name},
    Defendant.

================================================================================
{template.title.upper()}
================================================================================

{template.template_text}

Dated: {datetime.now().strftime('%B %d, %Y')}

                                    Respectfully submitted,

                                    _______________________________
                                    {tenant_name}
                                    Defendant, Pro Se
                                    {facts.get('tenant_address', '[ADDRESS]')}
                                    {facts.get('tenant_phone', '[PHONE]')}

================================================================================
LEGAL BASIS
================================================================================
"""
        for basis in template.legal_basis:
            motion += f"• {basis}\n"

        motion += """
================================================================================
CERTIFICATE OF SERVICE
================================================================================
I certify that on the date below, I served a copy of this Motion on all parties
by [mail/email/hand delivery] to:

{landlord_attorney}
{landlord_address}

Dated: _______________          _______________________________
                                {tenant_name}
"""

        return motion

    def get_hearing_checklist(self) -> dict:
        """Get a comprehensive hearing preparation checklist."""
        return {
            "before_hearing": [
                "Review all documents",
                "Organize evidence in order you'll present it",
                "Make 3 copies of everything (you, court, landlord)",
                "Write out key points you want to make",
                "Prepare questions for landlord's witnesses",
                "Know your defenses and the law supporting them",
                "Plan transportation - arrive 15 min early",
                "Dress professionally"
            ],
            "bring_to_court": [
                "Photo ID",
                "All evidence (photos, receipts, communications)",
                "Lease agreement",
                "Rent payment records",
                "Written Answer (if filed)",
                "Motions (if any)",
                "Witness contact info",
                "Notepad and pen",
                "Calculator (for rent calculations)"
            ],
            "during_hearing": [
                "Stand when judge enters",
                "Address judge as 'Your Honor'",
                "Don't interrupt anyone",
                "Listen carefully to questions",
                "Answer only what's asked",
                "Object to improper evidence",
                "Take notes",
                "Ask to clarify anything you don't understand",
                "Stay calm - don't argue with landlord"
            ],
            "what_to_say": [
                "State your defenses clearly",
                "Tie evidence to specific defenses",
                "Use dates and specifics",
                "If you don't know, say 'I don't know'",
                "Don't guess or speculate",
                "End with a clear request (dismissal, counterclaim damages, etc.)"
            ],
            "after_hearing": [
                "Request stay of execution if you lose",
                "Ask about appeal process",
                "Get copy of any orders",
                "Note deadline for any required actions",
                "Consider expungement if eligible"
            ]
        }


# =============================================================================
# SINGLETON INSTANCE
# =============================================================================

_procedures_engine: Optional[CourtProceduresEngine] = None


def get_procedures_engine() -> CourtProceduresEngine:
    """Get or create the procedures engine singleton."""
    global _procedures_engine
    if _procedures_engine is None:
        _procedures_engine = CourtProceduresEngine()
    return _procedures_engine
