"""
Adaptive UI Engine - Self-Building Interface Based on User Needs

This is the brain that figures out what the user needs and builds
the interface dynamically. It learns from:
- Documents they upload
- Issues detected
- Actions they take
- What helped other tenants in similar situations

The GUI literally builds itself based on what's relevant to THIS tenant.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional
import json


class WidgetType(str, Enum):
    """Types of UI widgets that can be dynamically added."""
    ALERT = "alert"              # Urgent: deadline, violation detected
    ACTION_CARD = "action_card"  # Suggested action to take
    INFO_PANEL = "info_panel"    # Information/education
    CHECKLIST = "checklist"      # Steps to complete
    TIMELINE = "timeline"        # Events visualization
    DOCUMENT_REQUEST = "doc_request"  # "We need this document"
    CALCULATOR = "calculator"    # Rent calc, deposit calc, etc.
    LETTER_BUILDER = "letter"    # Generate a letter to landlord
    PROGRESS_TRACKER = "progress"  # How far along in a process
    RESOURCE_LINK = "resource"   # External helpful resource
    WARNING = "warning"          # Something to watch out for


class Priority(str, Enum):
    """How urgently this widget should be shown."""
    CRITICAL = "critical"   # Red, top of screen, can't miss it
    HIGH = "high"           # Orange, prominent
    MEDIUM = "medium"       # Normal visibility
    LOW = "low"             # Available but not prominent
    BACKGROUND = "background"  # There if they look for it


class TenancyPhase(str, Enum):
    """What phase of tenancy the user appears to be in."""
    PRE_MOVE_IN = "pre_move_in"       # Signing lease, before moving
    ACTIVE_TENANCY = "active"          # Living there, normal
    ISSUE_EMERGING = "issue_emerging"  # Problems starting
    DISPUTE_ACTIVE = "dispute"         # Active conflict
    EVICTION_THREAT = "eviction"       # Eviction situation
    MOVE_OUT = "move_out"              # Planning to leave
    POST_TENANCY = "post_tenancy"      # After moving out (deposit return)


@dataclass
class UIWidget:
    """A single UI widget to display."""
    id: str
    type: WidgetType
    title: str
    content: dict  # Widget-specific content
    priority: Priority = Priority.MEDIUM
    reason: str = ""  # Why we're showing this
    actions: list = field(default_factory=list)  # Buttons/actions available
    dismissible: bool = True
    created_at: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "type": self.type.value,
            "title": self.title,
            "content": self.content,
            "priority": self.priority.value,
            "reason": self.reason,
            "actions": self.actions,
            "dismissible": self.dismissible,
            "created_at": self.created_at.isoformat(),
        }


@dataclass 
class UserContext:
    """Everything we know about this user's situation."""
    user_id: str
    phase: TenancyPhase = TenancyPhase.ACTIVE_TENANCY
    documents: list = field(default_factory=list)  # Document types they have
    issues_detected: list = field(default_factory=list)  # Problems we've found
    actions_taken: list = field(default_factory=list)  # What they've done
    deadlines: list = field(default_factory=list)  # Upcoming deadlines
    jurisdiction: str = ""  # State/city for law lookup
    lease_start: Optional[datetime] = None
    lease_end: Optional[datetime] = None
    rent_amount: Optional[float] = None
    deposit_amount: Optional[float] = None
    landlord_type: str = ""  # individual, company, property_manager
    
    def to_dict(self) -> dict:
        # Process deadlines - they can be strings, datetimes, or dicts
        deadlines_list = []
        for d in self.deadlines:
            if isinstance(d, str):
                deadlines_list.append(d)
            elif isinstance(d, dict):
                deadlines_list.append(d)
            elif hasattr(d, 'isoformat'):
                deadlines_list.append(d.isoformat())
            else:
                deadlines_list.append(str(d))
        
        return {
            "user_id": self.user_id,
            "phase": self.phase.value,
            "documents": self.documents,
            "issues_detected": self.issues_detected,
            "actions_taken": self.actions_taken,
            "deadlines": deadlines_list,
            "jurisdiction": self.jurisdiction,
        }


class AdaptiveUIEngine:
    """
    The brain that builds the UI based on user needs.
    
    This isn't magic - it's pattern matching based on:
    1. What documents they have (tells us their situation)
    2. What issues are detected (tells us their problems)
    3. What phase they're in (tells us what's coming next)
    4. What's worked for similar situations (learning)
    """
    
    def __init__(self):
        # In-memory storage for now
        self.user_contexts: dict[str, UserContext] = {}
        self.dismissed_widgets: dict[str, set] = {}  # user_id -> set of widget_ids
        
        # Patterns: document_type -> likely issues/needs
        self.document_patterns = {
            "lease": ["review_lease_terms", "know_your_rights"],
            "rent_receipt": ["track_payments", "build_payment_history"],
            "repair_request": ["habitability_issue", "document_conditions"],
            "notice_to_quit": ["eviction_threat", "know_eviction_rights", "seek_legal_help"],
            "eviction_notice": ["eviction_active", "urgent_legal_help", "tenant_defense"],
            "security_deposit": ["deposit_tracking", "move_out_checklist"],
            "photo_evidence": ["document_conditions", "build_evidence"],
            "communication": ["paper_trail", "document_harassment"],
            "violation_notice": ["code_violation", "landlord_responsibility"],
            "rent_increase": ["rent_increase_rights", "check_legality"],
        }
        
        # Phase transitions: what triggers moving to a new phase
        self.phase_triggers = {
            TenancyPhase.ISSUE_EMERGING: ["repair_request", "complaint", "late_payment"],
            TenancyPhase.DISPUTE_ACTIVE: ["dispute_letter", "withheld_rent", "formal_complaint"],
            TenancyPhase.EVICTION_THREAT: ["notice_to_quit", "eviction_notice", "pay_or_quit"],
            TenancyPhase.MOVE_OUT: ["move_out_notice", "lease_end_approaching"],
            TenancyPhase.POST_TENANCY: ["moved_out", "deposit_demand"],
        }
    
    def get_or_create_context(self, user_id: str) -> UserContext:
        """Get user context or create a new one."""
        if user_id not in self.user_contexts:
            self.user_contexts[user_id] = UserContext(user_id=user_id)
        return self.user_contexts[user_id]
    
    def update_context_from_document(self, user_id: str, doc_type: str, doc_data: dict):
        """
        Update user context based on a new document.
        This is where we learn about their situation.
        """
        ctx = self.get_or_create_context(user_id)
        
        if doc_type not in ctx.documents:
            ctx.documents.append(doc_type)
        
        # Check for phase transitions
        for phase, triggers in self.phase_triggers.items():
            if doc_type in triggers and ctx.phase.value < phase.value:
                ctx.phase = phase
        
        # Extract useful data from document
        if doc_type == "lease":
            if "rent_amount" in doc_data:
                ctx.rent_amount = doc_data["rent_amount"]
            if "deposit_amount" in doc_data:
                ctx.deposit_amount = doc_data["deposit_amount"]
            if "start_date" in doc_data:
                ctx.lease_start = doc_data["start_date"]
            if "end_date" in doc_data:
                ctx.lease_end = doc_data["end_date"]
        
        return ctx
    
    def detect_issues(self, ctx: UserContext) -> list[str]:
        """Analyze context and detect potential issues."""
        issues = []
        
        # Check for document-based issues
        for doc_type in ctx.documents:
            if doc_type in self.document_patterns:
                for pattern in self.document_patterns[doc_type]:
                    if pattern not in issues:
                        issues.append(pattern)
        
        # Check for timeline-based issues
        if ctx.lease_end:
            days_to_end = (ctx.lease_end - datetime.now(timezone.utc)).days
            if 0 < days_to_end <= 30:
                issues.append("lease_ending_soon")
            elif days_to_end <= 60:
                issues.append("lease_end_approaching")

        return issues

    def build_ui(self, user_id: str) -> list[dict]:
        """
        Build the adaptive UI for this user.
        Returns a list of widgets in priority order.
        """
        ctx = self.get_or_create_context(user_id)
        dismissed = self.dismissed_widgets.get(user_id, set())

        widgets = []        # Always show: Welcome/status widget
        widgets.append(self._build_status_widget(ctx))
        
        # Phase-specific widgets
        phase_widgets = self._build_phase_widgets(ctx)
        widgets.extend(phase_widgets)
        
        # Issue-specific widgets
        issues = self.detect_issues(ctx)
        for issue in issues:
            issue_widget = self._build_issue_widget(issue, ctx)
            if issue_widget:
                widgets.append(issue_widget)
        
        # Prediction widgets - what they might need next
        predictions = self._predict_next_needs(ctx)
        for pred in predictions:
            widgets.append(pred)
        
        # Missing document suggestions
        missing = self._suggest_missing_documents(ctx)
        if missing:
            widgets.append(missing)
        
        # Filter out dismissed widgets
        widgets = [w for w in widgets if w.id not in dismissed]
        
        # Sort by priority
        priority_order = {
            Priority.CRITICAL: 0,
            Priority.HIGH: 1,
            Priority.MEDIUM: 2,
            Priority.LOW: 3,
            Priority.BACKGROUND: 4,
        }
        widgets.sort(key=lambda w: priority_order.get(w.priority, 5))
        
        return [w.to_dict() for w in widgets]
    
    def _build_status_widget(self, ctx: UserContext) -> UIWidget:
        """Build the main status widget."""
        phase_messages = {
            TenancyPhase.PRE_MOVE_IN: "Getting ready to move in",
            TenancyPhase.ACTIVE_TENANCY: "Your tenancy is active",
            TenancyPhase.ISSUE_EMERGING: "We've detected some issues to address",
            TenancyPhase.DISPUTE_ACTIVE: "You're in an active dispute",
            TenancyPhase.EVICTION_THREAT: "Eviction situation detected",
            TenancyPhase.MOVE_OUT: "Preparing to move out",
            TenancyPhase.POST_TENANCY: "Post-tenancy: deposit recovery phase",
        }
        
        phase_colors = {
            TenancyPhase.PRE_MOVE_IN: "blue",
            TenancyPhase.ACTIVE_TENANCY: "green",
            TenancyPhase.ISSUE_EMERGING: "yellow",
            TenancyPhase.DISPUTE_ACTIVE: "orange",
            TenancyPhase.EVICTION_THREAT: "red",
            TenancyPhase.MOVE_OUT: "purple",
            TenancyPhase.POST_TENANCY: "blue",
        }
        
        return UIWidget(
            id="status_main",
            type=WidgetType.INFO_PANEL,
            title="Your Tenancy Status",
            content={
                "message": phase_messages.get(ctx.phase, "Welcome to Semptify"),
                "color": phase_colors.get(ctx.phase, "blue"),
                "documents_count": len(ctx.documents),
                "phase": ctx.phase.value,
            },
            priority=Priority.MEDIUM,
            dismissible=False,
        )
    
    def _build_phase_widgets(self, ctx: UserContext) -> list[UIWidget]:
        """Build widgets specific to the user's tenancy phase."""
        widgets = []
        
        if ctx.phase == TenancyPhase.EVICTION_THREAT:
            widgets.append(UIWidget(
                id="eviction_alert",
                type=WidgetType.ALERT,
                title="⚠️ Eviction Notice Detected",
                content={
                    "message": "This is serious but you have rights. Let's make sure you know them.",
                    "steps": [
                        "Don't panic - you have legal protections",
                        "Check the notice for required information",
                        "Note all deadlines carefully",
                        "Consider seeking legal help immediately",
                    ],
                },
                priority=Priority.CRITICAL,
                reason="You uploaded an eviction-related document",
                actions=[
                    {"label": "Know Your Eviction Rights", "action": "show_eviction_rights"},
                    {"label": "Find Legal Help", "action": "find_legal_aid"},
                    {"label": "Check Notice Validity", "action": "validate_notice"},
                ],
                dismissible=False,
            ))
        
        elif ctx.phase == TenancyPhase.ISSUE_EMERGING:
            widgets.append(UIWidget(
                id="issue_guidance",
                type=WidgetType.ACTION_CARD,
                title="Document Everything",
                content={
                    "message": "You're dealing with some issues. The most important thing: document everything.",
                    "tips": [
                        "Keep all written communication",
                        "Take dated photos of any problems",
                        "Follow up verbal conversations in writing",
                        "Keep copies of everything you send",
                    ],
                },
                priority=Priority.HIGH,
                reason="Issues detected in your tenancy",
                actions=[
                    {"label": "Upload Evidence", "action": "upload_document"},
                    {"label": "Write to Landlord", "action": "letter_builder"},
                ],
            ))
        
        elif ctx.phase == TenancyPhase.POST_TENANCY:
            widgets.append(UIWidget(
                id="deposit_recovery",
                type=WidgetType.CHECKLIST,
                title="Security Deposit Recovery",
                content={
                    "message": "Let's get your deposit back.",
                    "items": [
                        {"text": "Move-out photos taken", "checked": "photo_evidence" in ctx.documents},
                        {"text": "Forwarding address provided", "checked": False},
                        {"text": "Deposit demand letter sent", "checked": "deposit_demand" in ctx.documents},
                        {"text": "21-day deadline tracked", "checked": False},
                    ],
                },
                priority=Priority.HIGH,
                reason="You've moved out - deposit recovery is your priority",
                actions=[
                    {"label": "Generate Demand Letter", "action": "deposit_demand_letter"},
                    {"label": "Calculate What's Owed", "action": "deposit_calculator"},
                ],
            ))
        
        return widgets
    
    def _build_issue_widget(self, issue: str, ctx: UserContext) -> Optional[UIWidget]:
        """Build a widget for a specific detected issue."""
        issue_configs = {
            "habitability_issue": {
                "type": WidgetType.ACTION_CARD,
                "title": "Habitability Issue Detected",
                "content": {
                    "message": "Your landlord is legally required to maintain habitable conditions.",
                    "your_rights": [
                        "Right to safe, livable housing",
                        "Right to working utilities",
                        "Right to proper repairs",
                    ],
                },
                "priority": Priority.HIGH,
                "actions": [
                    {"label": "Learn About Habitability", "action": "show_habitability_rights"},
                    {"label": "Document the Issue", "action": "upload_document"},
                    {"label": "Write Repair Request", "action": "repair_letter"},
                ],
            },
            "eviction_threat": {
                "type": WidgetType.ALERT,
                "title": "Potential Eviction Situation",
                "content": {
                    "message": "We see signs of an eviction situation. Know your rights.",
                },
                "priority": Priority.CRITICAL,
                "actions": [
                    {"label": "Eviction Rights", "action": "show_eviction_rights"},
                    {"label": "Find Legal Aid", "action": "find_legal_aid"},
                ],
            },
            "rent_increase_rights": {
                "type": WidgetType.INFO_PANEL,
                "title": "Rent Increase Notice",
                "content": {
                    "message": "Rent increases must follow specific rules.",
                    "check_points": [
                        "Is proper notice given? (usually 30-60 days)",
                        "Is the increase allowed by your lease?",
                        "Is rent control applicable in your area?",
                    ],
                },
                "priority": Priority.HIGH,
                "actions": [
                    {"label": "Check Rent Laws", "action": "show_rent_laws"},
                    {"label": "Calculate Impact", "action": "rent_calculator"},
                ],
            },
        }
        
        config = issue_configs.get(issue)
        if not config:
            return None
        
        return UIWidget(
            id=f"issue_{issue}",
            type=config["type"],
            title=config["title"],
            content=config["content"],
            priority=config["priority"],
            reason=f"Detected from your documents",
            actions=config.get("actions", []),
        )
    
    def _predict_next_needs(self, ctx: UserContext) -> list[UIWidget]:
        """
        Predict what the user might need next based on patterns.
        This is where Semptify gets smart.
        """
        predictions = []
        
        # If they have a lease but no move-in photos
        if "lease" in ctx.documents and "photo_evidence" not in ctx.documents:
            predictions.append(UIWidget(
                id="predict_photos",
                type=WidgetType.ACTION_CARD,
                title="📸 Take Move-In Photos",
                content={
                    "message": "Protect your security deposit by documenting the condition now.",
                    "why": "Move-in photos are your best defense against unfair deposit deductions.",
                },
                priority=Priority.MEDIUM,
                reason="You have a lease but no photos documented",
                actions=[
                    {"label": "Upload Photos", "action": "upload_document"},
                    {"label": "Photo Checklist", "action": "photo_checklist"},
                ],
            ))
        
        # If they have repair requests but no follow-up
        if "repair_request" in ctx.documents and "repair_followup" not in ctx.documents:
            predictions.append(UIWidget(
                id="predict_repair_followup",
                type=WidgetType.ACTION_CARD,
                title="Follow Up on Repairs",
                content={
                    "message": "Your repair request needs follow-up documentation.",
                    "why": "Written follow-ups create a paper trail and legal protection.",
                },
                priority=Priority.MEDIUM,
                reason="You submitted a repair request",
                actions=[
                    {"label": "Write Follow-Up", "action": "repair_followup_letter"},
                    {"label": "Document Current State", "action": "upload_document"},
                ],
            ))
        
        # New user with no documents
        if not ctx.documents:
            predictions.append(UIWidget(
                id="predict_start",
                type=WidgetType.ACTION_CARD,
                title="Let's Get Started",
                content={
                    "message": "Upload your first document and Semptify will start building your case.",
                    "suggestions": [
                        "Your lease agreement",
                        "Rent receipts",
                        "Photos of current conditions",
                        "Any communication with landlord",
                    ],
                },
                priority=Priority.HIGH,
                reason="Let's understand your situation",
                actions=[
                    {"label": "Upload Document", "action": "upload_document"},
                ],
            ))
        
        return predictions
    
    def _suggest_missing_documents(self, ctx: UserContext) -> Optional[UIWidget]:
        """Suggest documents they should have but don't."""
        essential = ["lease", "rent_receipt", "photo_evidence"]
        missing = [doc for doc in essential if doc not in ctx.documents]
        
        if not missing:
            return None
        
        doc_names = {
            "lease": "Lease Agreement",
            "rent_receipt": "Rent Payment Records",
            "photo_evidence": "Move-in/Current Condition Photos",
        }
        
        return UIWidget(
            id="missing_docs",
            type=WidgetType.DOCUMENT_REQUEST,
            title="Strengthen Your Case",
            content={
                "message": "These documents will help protect you:",
                "missing": [doc_names.get(d, d) for d in missing],
            },
            priority=Priority.LOW,
            reason="Essential documents for tenant protection",
            actions=[
                {"label": "Upload Documents", "action": "upload_document"},
            ],
        )
    
    def dismiss_widget(self, user_id: str, widget_id: str):
        """Mark a widget as dismissed for this user."""
        if user_id not in self.dismissed_widgets:
            self.dismissed_widgets[user_id] = set()
        self.dismissed_widgets[user_id].add(widget_id)
    
    def record_action(self, user_id: str, action: str):
        """Record that a user took an action."""
        ctx = self.get_or_create_context(user_id)
        ctx.actions_taken.append({
            "action": action,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })


# Global instance
adaptive_ui = AdaptiveUIEngine()


# =============================================================================
# Context Loop Integration
# =============================================================================

def sync_from_context_loop(user_id: str):
    """
    Sync adaptive UI context from the context loop.
    This ensures both systems have the same view of the user.
    """
    try:
        from app.services.context_loop import context_loop
        
        loop_ctx = context_loop.get_context(user_id)
        ui_ctx = adaptive_ui.get_or_create_context(user_id)
        
        # Sync documents
        ui_ctx.documents = list(loop_ctx.document_types)
        
        # Sync phase
        phase_map = {
            "active": TenancyPhase.ACTIVE_TENANCY,
            "issue_emerging": TenancyPhase.ISSUE_EMERGING,
            "dispute": TenancyPhase.DISPUTE_ACTIVE,
            "eviction": TenancyPhase.EVICTION_THREAT,
            "post_tenancy": TenancyPhase.POST_TENANCY,
            "pre_move_in": TenancyPhase.PRE_MOVE_IN,
            "move_out": TenancyPhase.MOVE_OUT,
        }
        if loop_ctx.phase in phase_map:
            ui_ctx.phase = phase_map[loop_ctx.phase]
        
        # Sync issues
        ui_ctx.issues_detected = [
            i.get("type") if isinstance(i, dict) else str(i)
            for i in loop_ctx.active_issues
        ]
        
        # Sync deadlines
        ui_ctx.deadlines = loop_ctx.deadlines
        
        return True
    except ImportError:
        return False
    except Exception as e:
        print(f"Context sync error: {e}")
        return False


def build_ui_with_intensity(user_id: str) -> dict:
    """
    Build UI with intensity information from context loop.
    Returns widgets plus intensity data.
    """
    # Sync first
    sync_from_context_loop(user_id)
    
    # Get widgets
    widgets = adaptive_ui.build_ui(user_id)
    
    # Get intensity from context loop
    try:
        from app.services.context_loop import context_loop
        intensity_report = context_loop.get_intensity_report(user_id)
    except ImportError:
        intensity_report = {"overall_intensity": 0, "severity": "info"}
    
    return {
        "user_id": user_id,
        "widgets": widgets,
        "intensity": intensity_report,
    }

