"""
Context Data Loop - The Core Processing Engine

This is the BRAIN of Semptify. Everything flows through here.

The Loop:
1. INPUT: Document, event, or user action comes in
2. PROCESS: Extract context, classify, cross-reference with laws
3. INTENSITY: Calculate urgency/priority based on deadlines, severity, patterns
4. OUTPUT: Update user context, trigger UI updates, suggest actions
5. LEARN: Record what happened, what worked, improve predictions

The Intensity Engine determines HOW URGENT something is:
- Eviction notice 3 days before court? CRITICAL (intensity: 100)
- Lease ending in 60 days? MEDIUM (intensity: 40)
- Missing rent receipt from 6 months ago? LOW (intensity: 15)
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Optional, Callable, Any, Dict, List
import hashlib
import json
import logging

from app.core.event_bus import event_bus, EventType as BusEventType, subscribe_async_to_event

logger = logging.getLogger(__name__)


class EventType(str, Enum):
    """Types of events that flow through the loop."""
    DOCUMENT_UPLOADED = "document_uploaded"
    DOCUMENT_ANALYZED = "document_analyzed"
    DEADLINE_APPROACHING = "deadline_approaching"
    DEADLINE_PASSED = "deadline_passed"
    ISSUE_DETECTED = "issue_detected"
    ACTION_TAKEN = "action_taken"
    PHASE_CHANGED = "phase_changed"
    LAW_MATCHED = "law_matched"
    USER_DISMISSED = "user_dismissed"
    PREDICTION_MADE = "prediction_made"
    INTENSITY_SPIKE = "intensity_spike"


class Severity(str, Enum):
    """How serious is this?"""
    CRITICAL = "critical"    # Legal deadline, court date, eviction
    HIGH = "high"            # Needs attention soon
    MEDIUM = "medium"        # Should address
    LOW = "low"              # Nice to know
    INFO = "info"            # Just information


@dataclass
class ContextEvent:
    """A single event in the context data loop."""
    id: str
    type: EventType
    timestamp: datetime
    user_id: str
    data: dict
    intensity: float = 0.0  # 0-100 scale
    severity: Severity = Severity.INFO
    source: str = ""  # What triggered this event
    processed: bool = False
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "type": self.type.value,
            "timestamp": self.timestamp.isoformat(),
            "user_id": self.user_id,
            "data": self.data,
            "intensity": self.intensity,
            "severity": self.severity.value,
            "source": self.source,
            "processed": self.processed,
        }


@dataclass
class UserContext:
    """Complete context for a user - everything we know."""
    user_id: str
    
    # Current state
    phase: str = "active"
    intensity_score: float = 0.0  # Overall urgency 0-100
    
    # Documents and evidence
    documents: list = field(default_factory=list)
    document_types: set = field(default_factory=set)
    
    # Issues and deadlines
    active_issues: list = field(default_factory=list)
    deadlines: list = field(default_factory=list)
    
    # Laws and rights
    applicable_laws: list = field(default_factory=list)
    rights_at_risk: list = field(default_factory=list)
    
    # History
    events: list = field(default_factory=list)
    actions_taken: list = field(default_factory=list)
    
    # Predictions
    predicted_needs: list = field(default_factory=list)
    risk_factors: list = field(default_factory=list)
    
    # Timestamps
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    last_activity: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> dict:
        return {
            "user_id": self.user_id,
            "phase": self.phase,
            "intensity_score": self.intensity_score,
            "documents_count": len(self.documents),
            "document_types": list(self.document_types),
            "active_issues": self.active_issues,
            "deadlines": [
                d if isinstance(d, dict) else {"date": d.isoformat() if hasattr(d, 'isoformat') else str(d)}
                for d in self.deadlines
            ],
            "applicable_laws_count": len(self.applicable_laws),
            "rights_at_risk": self.rights_at_risk,
            "predicted_needs": self.predicted_needs,
            "risk_factors": self.risk_factors,
            "last_activity": self.last_activity.isoformat(),
        }


class IntensityEngine:
    """
    The Intensity Engine - Calculates HOW URGENT everything is.
    
    Intensity is on a 0-100 scale:
    - 0-20: Low priority, informational
    - 21-40: Medium priority, should address soon
    - 41-60: High priority, needs attention
    - 61-80: Urgent, act now
    - 81-100: Critical, emergency situation
    
    Factors that increase intensity:
    - Approaching deadlines
    - Legal consequences (eviction, court)
    - Financial impact
    - Rights violations
    - Pattern of issues
    - Landlord escalation
    """
    
    # Base intensity scores by event/document type
    BASE_INTENSITY = {
        # Documents
        "eviction_notice": 85,
        "notice_to_quit": 80,
        "court_summons": 90,
        "pay_or_quit": 75,
        "lease_violation": 60,
        "rent_increase": 45,
        "lease": 20,
        "rent_receipt": 15,
        "repair_request": 40,
        "photo_evidence": 20,
        "communication": 25,
        
        # Issues
        "eviction_threat": 85,
        "habitability_issue": 55,
        "illegal_lockout": 95,
        "harassment": 65,
        "retaliation": 70,
        "deposit_dispute": 50,
        "rent_dispute": 55,
        "repair_ignored": 45,
        
        # General
        "unknown": 30,
    }
    
    # Deadline multipliers (how much urgency increases as deadline approaches)
    DEADLINE_MULTIPLIERS = {
        "past_due": 1.5,      # Already passed - critical
        "today": 1.4,
        "1_day": 1.35,
        "3_days": 1.25,
        "7_days": 1.15,
        "14_days": 1.05,
        "30_days": 1.0,
        "60_days": 0.8,
        "90_days": 0.6,
    }
    
    def __init__(self):
        self.intensity_history: dict[str, list] = {}  # user_id -> intensity over time
    
    def calculate_intensity(
        self,
        event_type: str,
        context: UserContext,
        deadline: Optional[datetime] = None,
        additional_factors: Optional[dict] = None,
    ) -> tuple[float, Severity, list[str]]:
        """
        Calculate intensity for an event.
        
        Returns: (intensity_score, severity, contributing_factors)
        """
        factors = []
        
        # Start with base intensity
        base = self.BASE_INTENSITY.get(event_type, self.BASE_INTENSITY["unknown"])
        intensity = base
        factors.append(f"Base: {base} ({event_type})")
        
        # Deadline factor
        if deadline:
            deadline_mult, deadline_desc = self._get_deadline_multiplier(deadline)
            intensity *= deadline_mult
            factors.append(f"Deadline ({deadline_desc}): x{deadline_mult}")
        
        # Pattern escalation - multiple issues compound
        if len(context.active_issues) > 1:
            issue_mult = 1 + (len(context.active_issues) * 0.1)
            intensity *= issue_mult
            factors.append(f"Multiple issues ({len(context.active_issues)}): x{issue_mult:.2f}")
        
        # Rights at risk multiplier
        if context.rights_at_risk:
            rights_mult = 1 + (len(context.rights_at_risk) * 0.15)
            intensity *= rights_mult
            factors.append(f"Rights at risk ({len(context.rights_at_risk)}): x{rights_mult:.2f}")
        
        # Phase-based adjustment
        phase_multipliers = {
            "eviction": 1.3,
            "dispute": 1.2,
            "issue_emerging": 1.1,
            "post_tenancy": 1.1,  # Deposit deadlines matter
            "active": 1.0,
            "pre_move_in": 0.9,
        }
        phase_mult = phase_multipliers.get(context.phase, 1.0)
        if phase_mult != 1.0:
            intensity *= phase_mult
            factors.append(f"Phase ({context.phase}): x{phase_mult}")
        
        # Additional custom factors
        if additional_factors:
            for factor_name, factor_value in additional_factors.items():
                if isinstance(factor_value, (int, float)):
                    intensity *= factor_value
                    factors.append(f"{factor_name}: x{factor_value}")
        
        # Cap at 100
        intensity = min(100, intensity)
        
        # Determine severity
        severity = self._intensity_to_severity(intensity)
        
        # Record history
        self._record_intensity(context.user_id, intensity)
        
        return round(intensity, 1), severity, factors
    
    def _get_deadline_multiplier(self, deadline: datetime) -> tuple[float, str]:
        """Get multiplier based on how close the deadline is."""
        now = datetime.now(timezone.utc)
        # Make deadline timezone-aware if it's naive
        if deadline.tzinfo is None:
            deadline = deadline.replace(tzinfo=timezone.utc)
        delta = deadline - now
        days = delta.days

        if days < 0:
            return self.DEADLINE_MULTIPLIERS["past_due"], "PAST DUE"
        elif days == 0:
            return self.DEADLINE_MULTIPLIERS["today"], "TODAY"
        elif days == 1:
            return self.DEADLINE_MULTIPLIERS["1_day"], "1 day"
        elif days <= 3:
            return self.DEADLINE_MULTIPLIERS["3_days"], f"{days} days"
        elif days <= 7:
            return self.DEADLINE_MULTIPLIERS["7_days"], f"{days} days"
        elif days <= 14:
            return self.DEADLINE_MULTIPLIERS["14_days"], f"{days} days"
        elif days <= 30:
            return self.DEADLINE_MULTIPLIERS["30_days"], f"{days} days"
        elif days <= 60:
            return self.DEADLINE_MULTIPLIERS["60_days"], f"{days} days"
        else:
            return self.DEADLINE_MULTIPLIERS["90_days"], f"{days} days"
    
    def _intensity_to_severity(self, intensity: float) -> Severity:
        """Convert intensity score to severity level."""
        if intensity >= 80:
            return Severity.CRITICAL
        elif intensity >= 60:
            return Severity.HIGH
        elif intensity >= 40:
            return Severity.MEDIUM
        elif intensity >= 20:
            return Severity.LOW
        else:
            return Severity.INFO
    
    def _record_intensity(self, user_id: str, intensity: float):
        """Record intensity for trend analysis."""
        if user_id not in self.intensity_history:
            self.intensity_history[user_id] = []
        
        self.intensity_history[user_id].append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "intensity": intensity,
        })

        # Keep last 100 readings
        if len(self.intensity_history[user_id]) > 100:
            self.intensity_history[user_id] = self.intensity_history[user_id][-100:]

    def get_intensity_trend(self, user_id: str) -> dict:
        """Get intensity trend for a user."""
        history = self.intensity_history.get(user_id, [])
        
        if not history:
            return {"trend": "stable", "change": 0, "current": 0}
        
        current = history[-1]["intensity"]
        
        if len(history) < 2:
            return {"trend": "stable", "change": 0, "current": current}
        
        # Compare to average of last 5
        recent = [h["intensity"] for h in history[-5:]]
        avg = sum(recent) / len(recent)
        older = [h["intensity"] for h in history[:-5]] if len(history) > 5 else []
        
        if older:
            old_avg = sum(older) / len(older)
            change = avg - old_avg
            
            if change > 10:
                trend = "escalating"
            elif change < -10:
                trend = "improving"
            else:
                trend = "stable"
        else:
            trend = "stable"
            change = 0
        
        return {
            "trend": trend,
            "change": round(change, 1),
            "current": current,
            "history_count": len(history),
        }
    
    def calculate_overall_intensity(self, context: UserContext) -> float:
        """Calculate overall intensity score for a user's situation."""
        if not context.active_issues and not context.deadlines:
            return 0.0
        
        scores = []
        
        # Score each active issue
        for issue in context.active_issues:
            issue_type = issue.get("type", "unknown") if isinstance(issue, dict) else str(issue)
            score, _, _ = self.calculate_intensity(issue_type, context)
            scores.append(score)
        
        # Score upcoming deadlines
        for deadline in context.deadlines:
            if isinstance(deadline, dict):
                dl_date = deadline.get("date")
                dl_type = deadline.get("type", "deadline")
                if dl_date:
                    if isinstance(dl_date, str):
                        dl_date = datetime.fromisoformat(dl_date.replace("Z", "+00:00"))
                    score, _, _ = self.calculate_intensity(dl_type, context, deadline=dl_date)
                    scores.append(score)
        
        if not scores:
            return 0.0
        
        # Overall is weighted average (highest scores matter more)
        scores.sort(reverse=True)
        weighted_sum = sum(s * (1.0 - i * 0.1) for i, s in enumerate(scores[:5]))
        weight_total = sum(1.0 - i * 0.1 for i in range(min(5, len(scores))))
        
        return round(weighted_sum / weight_total, 1) if weight_total > 0 else 0.0


class ContextDataLoop:
    """
    The Core Processing Loop - Everything flows through here.

    INPUT → PROCESS → INTENSITY → OUTPUT → LEARN
    
    Subscribes to EventBus events and orchestrates responses.
    """

    def __init__(self):
        self.intensity_engine = IntensityEngine()
        self.contexts: dict[str, UserContext] = {}
        self.event_queue: list[ContextEvent] = []
        self.processors: list[Callable] = []
        self.listeners: list[Callable] = []
        
        # Subscribe to EventBus events
        self._setup_event_subscriptions()
    
    def _setup_event_subscriptions(self):
        """Subscribe to EventBus events for orchestration."""
        # Document events
        subscribe_async_to_event(BusEventType.DOCUMENT_ADDED, self._on_document_added)
        subscribe_async_to_event(BusEventType.DOCUMENT_PROCESSED, self._on_document_processed)
        subscribe_async_to_event(BusEventType.DOCUMENT_CLASSIFIED, self._on_document_classified)

        # Data extraction events
        subscribe_async_to_event(BusEventType.EVENTS_EXTRACTED, self._on_events_extracted)

        # Case update events
        subscribe_async_to_event(BusEventType.CASE_INFO_UPDATED, self._on_case_updated)

        logger.info("🔄 ContextDataLoop subscribed to EventBus")

    async def _on_document_added(self, event):
        """Handle new document added to vault."""
        user_id = event.user_id
        if not user_id:
            return
        
        context = self.get_context(user_id)
        context.documents.append({
            "id": event.data.get("resource_id"),
            "type": event.data.get("resource_type"),
            "added_at": event.timestamp.isoformat(),
        })
        
        # Trigger document processing
        logger.info(f"📄 Document added for {user_id}, triggering processing")
        await event_bus.publish(
            BusEventType.UI_REFRESH_NEEDED,
            {"section": "documents"},
            source="context_loop",
            user_id=user_id,
        )
    
    async def _on_document_processed(self, event):
        """Handle document processing complete."""
        user_id = event.user_id
        if not user_id:
            return
        
        context = self.get_context(user_id)
        # Update context with processed info
        logger.info(f"✅ Document processed for {user_id}")

    async def _on_document_classified(self, event):
        """Handle document classified - trigger automatic event extraction."""
        user_id = event.user_id
        if not user_id:
            return
        
        doc_id = event.data.get("document_id")
        doc_type = event.data.get("doc_type", "unknown")
        
        if event.data.get("ready_for_extraction"):
            logger.info(f"🔍 Auto-extracting events from {doc_type} document {doc_id}")
            
            try:
                # Get the document pipeline and event extractor
                from app.services.document_pipeline import get_document_pipeline
                from app.services.event_extractor import get_event_extractor
                
                pipeline = get_document_pipeline()
                extractor = get_event_extractor()
                
                # Get document
                doc = pipeline.get_document(doc_id)
                if doc and doc.full_text:
                    # Extract events
                    events = extractor.extract_events(doc.full_text, doc_type)
                    
                    if events:
                        # Publish extraction event
                        await event_bus.publish(
                            BusEventType.EVENTS_EXTRACTED,
                            {
                                "document_id": doc_id,
                                "count": len(events),
                                "events": [e.to_dict() for e in events],
                                "has_deadlines": any(e.event_type in ["deadline", "court_date", "hearing"] for e in events)
                            },
                            source="context_loop",
                            user_id=user_id,
                        )
                        logger.info(f"📅 Extracted {len(events)} events from document {doc_id}")
            except Exception as e:
                logger.error(f"Failed to auto-extract events: {e}")

    async def _on_events_extracted(self, event):
        """Handle events extracted from document."""
        user_id = event.user_id
        if not user_id:
            return
        
        context = self.get_context(user_id)
        extracted = event.data
        
        # Add to timeline
        if extracted.get("count", 0) > 0:
            logger.info(f"📅 {extracted['count']} events extracted for {user_id}")
            
            # Publish timeline update
            await event_bus.publish(
                BusEventType.TIMELINE_UPDATED,
                {"events_added": extracted["count"]},
                source="context_loop",
                user_id=user_id,
            )
    
    async def _on_case_updated(self, event):
        """Handle case info updated."""
        user_id = event.user_id
        if not user_id:
            return
        
        context = self.get_context(user_id)
        updates = event.data.get("updates", [])
        
        logger.info(f"📋 Case updated for {user_id}: {updates}")
        
        # Check for deadline updates
        if "hearing_date" in updates or "answer_deadline" in updates:
            await self._check_deadlines(user_id, context)
    
    async def _check_deadlines(self, user_id: str, context: UserContext):
        """Check for approaching deadlines and notify."""
        for deadline in context.deadlines:
            if deadline.date:
                days_remaining = (deadline.date - datetime.now(timezone.utc)).days
                if 0 < days_remaining <= 7:
                    await event_bus.publish(
                        BusEventType.DEADLINE_APPROACHING,
                        {
                            "deadline": deadline.name,
                            "date": deadline.date.isoformat(),
                            "days_remaining": days_remaining,
                        },
                        source="context_loop",
                        user_id=user_id,
                    )

    def get_context(self, user_id: str) -> UserContext:
        """Get or create user context."""
        if user_id not in self.contexts:
            self.contexts[user_id] = UserContext(user_id=user_id)
        return self.contexts[user_id]
    
    def register_processor(self, processor: Callable):
        """Register a processor function that handles events."""
        self.processors.append(processor)
    
    def register_listener(self, listener: Callable):
        """Register a listener that's notified of events."""
        self.listeners.append(listener)
    
    # =========================================================================
    # INPUT - Events come in
    # =========================================================================
    
    def emit_event(
        self,
        event_type: EventType,
        user_id: str,
        data: dict,
        source: str = "",
    ) -> ContextEvent:
        """Emit an event into the loop."""
        event_id = hashlib.sha256(
            f"{event_type}{user_id}{datetime.now(timezone.utc).isoformat()}".encode()
        ).hexdigest()[:16]

        context = self.get_context(user_id)

        # Calculate intensity for this event
        event_key = data.get("type", data.get("document_type", event_type.value))
        deadline = data.get("deadline")
        if deadline and isinstance(deadline, str):
            deadline = datetime.fromisoformat(deadline.replace("Z", "+00:00"))
        intensity, severity, factors = self.intensity_engine.calculate_intensity(
            event_key, context, deadline
        )

        event = ContextEvent(
            id=event_id,
            type=event_type,
            timestamp=datetime.now(timezone.utc),
            user_id=user_id,
            data=data,
            intensity=intensity,
            severity=severity,
            source=source,
        )

        # Add to queue
        self.event_queue.append(event)        # Process immediately
        self._process_event(event)
        
        return event
    
    # =========================================================================
    # PROCESS - Handle events
    # =========================================================================
    
    def _process_event(self, event: ContextEvent):
        """Process a single event through the loop."""
        context = self.get_context(event.user_id)
        
        # Update last activity
        context.last_activity = datetime.now(timezone.utc)
        context.updated_at = datetime.now(timezone.utc)

        # Add to event history
        context.events.append(event.to_dict())
        if len(context.events) > 500:
            context.events = context.events[-500:]

        # Handle specific event types
        if event.type == EventType.DOCUMENT_UPLOADED:
            self._handle_document_uploaded(event, context)
        elif event.type == EventType.DOCUMENT_ANALYZED:
            self._handle_document_analyzed(event, context)
        elif event.type == EventType.ISSUE_DETECTED:
            self._handle_issue_detected(event, context)
        elif event.type == EventType.DEADLINE_APPROACHING:
            self._handle_deadline(event, context)
        elif event.type == EventType.ACTION_TAKEN:
            self._handle_action_taken(event, context)
        elif event.type == EventType.LAW_MATCHED:
            self._handle_law_matched(event, context)
        
        # Update overall intensity
        context.intensity_score = self.intensity_engine.calculate_overall_intensity(context)
        
        # Update phase based on intensity and issues
        self._update_phase(context)
        
        # Generate predictions
        self._generate_predictions(context)
        
        # Mark as processed
        event.processed = True
        
        # Notify listeners
        for listener in self.listeners:
            try:
                listener(event, context)
            except Exception as e:
                print(f"Listener error: {e}")
        
        # Run custom processors
        for processor in self.processors:
            try:
                processor(event, context)
            except Exception as e:
                print(f"Processor error: {e}")
    
    def _handle_document_uploaded(self, event: ContextEvent, context: UserContext):
        """Handle document upload event."""
        doc_data = event.data
        doc_type = doc_data.get("type", "unknown")
        
        context.documents.append({
            "id": doc_data.get("id", event.id),
            "type": doc_type,
            "filename": doc_data.get("filename"),
            "uploaded_at": event.timestamp.isoformat(),
            "intensity": event.intensity,
        })
        
        context.document_types.add(doc_type)
    
    def _handle_document_analyzed(self, event: ContextEvent, context: UserContext):
        """Handle document analysis complete."""
        analysis = event.data
        
        # Check for issues in the document
        if analysis.get("issues"):
            for issue in analysis["issues"]:
                if issue not in context.active_issues:
                    context.active_issues.append(issue)
        
        # Check for deadlines
        if analysis.get("deadlines"):
            for deadline in analysis["deadlines"]:
                context.deadlines.append(deadline)
        
        # Check for laws
        if analysis.get("applicable_laws"):
            for law in analysis["applicable_laws"]:
                if law not in context.applicable_laws:
                    context.applicable_laws.append(law)
    
    def _handle_issue_detected(self, event: ContextEvent, context: UserContext):
        """Handle new issue detection."""
        issue = event.data
        
        if issue not in context.active_issues:
            context.active_issues.append(issue)
        
        # Check if this puts rights at risk
        rights_mapping = {
            "eviction_threat": "Right to due process",
            "habitability_issue": "Right to habitable housing",
            "harassment": "Right to quiet enjoyment",
            "retaliation": "Right to assert rights without retaliation",
            "illegal_lockout": "Right to access your home",
            "deposit_dispute": "Right to security deposit return",
        }
        
        issue_type = issue.get("type") if isinstance(issue, dict) else str(issue)
        if issue_type in rights_mapping:
            right = rights_mapping[issue_type]
            if right not in context.rights_at_risk:
                context.rights_at_risk.append(right)
    
    def _handle_deadline(self, event: ContextEvent, context: UserContext):
        """Handle deadline event."""
        deadline = event.data
        
        # Add to deadlines if not already there
        existing = [d for d in context.deadlines if d.get("id") == deadline.get("id")]
        if not existing:
            context.deadlines.append(deadline)
        
        # Sort by date
        context.deadlines.sort(
            key=lambda d: d.get("date", "9999-12-31") if isinstance(d, dict) else str(d)
        )
    
    def _handle_action_taken(self, event: ContextEvent, context: UserContext):
        """Handle user action."""
        action = event.data
        context.actions_taken.append({
            **action,
            "timestamp": event.timestamp.isoformat(),
        })
    
    def _handle_law_matched(self, event: ContextEvent, context: UserContext):
        """Handle law match event."""
        law = event.data
        if law not in context.applicable_laws:
            context.applicable_laws.append(law)
    
    # =========================================================================
    # UPDATE - Adjust state based on events
    # =========================================================================
    
    def _update_phase(self, context: UserContext):
        """Update tenancy phase based on current state."""
        # Phase determination logic
        high_intensity_issues = [
            i for i in context.active_issues
            if isinstance(i, dict) and i.get("type") in ["eviction_threat", "notice_to_quit", "eviction_notice"]
        ]
        
        if high_intensity_issues or context.intensity_score >= 80:
            context.phase = "eviction"
        elif context.intensity_score >= 50 or len(context.active_issues) >= 2:
            context.phase = "dispute"
        elif context.active_issues:
            context.phase = "issue_emerging"
        elif "moved_out" in context.document_types or "deposit_demand" in context.document_types:
            context.phase = "post_tenancy"
        else:
            context.phase = "active"
    
    def _generate_predictions(self, context: UserContext):
        """Generate predictions about what user might need."""
        predictions = []
        
        # Based on document types
        if "lease" in context.document_types and "photo_evidence" not in context.document_types:
            predictions.append({
                "type": "document_needed",
                "item": "move_in_photos",
                "reason": "Protect your security deposit",
                "priority": "medium",
            })
        
        if "repair_request" in context.document_types:
            predictions.append({
                "type": "action_needed",
                "item": "repair_followup",
                "reason": "Follow up in writing creates legal protection",
                "priority": "high",
            })
        
        # Based on phase
        if context.phase == "eviction":
            predictions.append({
                "type": "resource_needed",
                "item": "legal_aid",
                "reason": "Free legal help is available for eviction cases",
                "priority": "critical",
            })
        
        if context.phase == "post_tenancy":
            predictions.append({
                "type": "action_needed",
                "item": "deposit_demand_letter",
                "reason": "Formal demand starts the legal clock",
                "priority": "high",
            })
        
        # Based on deadlines
        for deadline in context.deadlines:
            if isinstance(deadline, dict):
                dl_date = deadline.get("date")
                if dl_date:
                    if isinstance(dl_date, str):
                        try:
                            dl_date = datetime.fromisoformat(dl_date.replace("Z", "+00:00"))
                        except:
                            continue
                    # Make timezone-aware if naive
                    if dl_date.tzinfo is None:
                        dl_date = dl_date.replace(tzinfo=timezone.utc)
                    days_left = (dl_date - datetime.now(timezone.utc)).days
                    if 0 < days_left <= 7:
                        predictions.append({
                            "type": "deadline_warning",
                            "item": deadline.get("type", "deadline"),
                            "reason": f"Due in {days_left} days",
                            "priority": "critical" if days_left <= 3 else "high",
                        })
        
        context.predicted_needs = predictions
    
    # =========================================================================
    # OUTPUT - Get processed state
    # =========================================================================
    
    def get_state(self, user_id: str) -> dict:
        """Get complete processed state for a user."""
        context = self.get_context(user_id)
        trend = self.intensity_engine.get_intensity_trend(user_id)
        
        return {
            "user_id": user_id,
            "context": context.to_dict(),
            "intensity": {
                "current": context.intensity_score,
                "trend": trend,
            },
            "summary": {
                "phase": context.phase,
                "documents": len(context.documents),
                "active_issues": len(context.active_issues),
                "deadlines": len(context.deadlines),
                "laws_applicable": len(context.applicable_laws),
                "rights_at_risk": len(context.rights_at_risk),
            },
            "predictions": context.predicted_needs,
            "next_actions": self._get_recommended_actions(context),
        }
    
    def _get_recommended_actions(self, context: UserContext) -> list:
        """Get recommended next actions based on state."""
        actions = []
        
        # High intensity = urgent actions
        if context.intensity_score >= 80:
            actions.append({
                "action": "seek_legal_help",
                "label": "Get Legal Help Now",
                "reason": "Your situation is urgent",
                "priority": "critical",
            })
        
        # Missing essential documents
        essential = ["lease", "rent_receipt", "photo_evidence"]
        missing = [d for d in essential if d not in context.document_types]
        if missing:
            actions.append({
                "action": "upload_document",
                "label": f"Upload: {missing[0].replace('_', ' ').title()}",
                "reason": "Essential for your protection",
                "priority": "high",
            })
        
        # Active issues need documentation
        if context.active_issues and "photo_evidence" not in context.document_types:
            actions.append({
                "action": "document_issue",
                "label": "Document Current Issues",
                "reason": "Photos and records strengthen your case",
                "priority": "high",
            })
        
        # Predictions become actions
        for pred in context.predicted_needs[:3]:
            actions.append({
                "action": pred.get("item", "take_action"),
                "label": pred.get("item", "").replace("_", " ").title(),
                "reason": pred.get("reason", ""),
                "priority": pred.get("priority", "medium"),
            })
        
        return actions[:5]  # Top 5 actions
    
    def get_intensity_report(self, user_id: str) -> dict:
        """Get detailed intensity report for a user."""
        context = self.get_context(user_id)
        trend = self.intensity_engine.get_intensity_trend(user_id)
        
        # Calculate intensity for each active item
        issue_intensities = []
        for issue in context.active_issues:
            issue_type = issue.get("type", "unknown") if isinstance(issue, dict) else str(issue)
            intensity, severity, factors = self.intensity_engine.calculate_intensity(
                issue_type, context
            )
            issue_intensities.append({
                "item": issue_type,
                "intensity": intensity,
                "severity": severity.value,
                "factors": factors,
            })
        
        return {
            "user_id": user_id,
            "overall_intensity": context.intensity_score,
            "severity": self.intensity_engine._intensity_to_severity(context.intensity_score).value,
            "trend": trend,
            "breakdown": issue_intensities,
            "phase": context.phase,
            "risk_level": self._get_risk_level(context.intensity_score),
        }
    
    def _get_risk_level(self, intensity: float) -> dict:
        """Get risk level description."""
        if intensity >= 80:
            return {
                "level": "critical",
                "color": "red",
                "message": "Immediate action required",
                "icon": "🚨",
            }
        elif intensity >= 60:
            return {
                "level": "high",
                "color": "orange",
                "message": "Urgent attention needed",
                "icon": "⚠️",
            }
        elif intensity >= 40:
            return {
                "level": "elevated",
                "color": "yellow",
                "message": "Active issues to address",
                "icon": "📋",
            }
        elif intensity >= 20:
            return {
                "level": "moderate",
                "color": "blue",
                "message": "Monitor and prepare",
                "icon": "📝",
            }
        else:
            return {
                "level": "low",
                "color": "green",
                "message": "Situation stable",
                "icon": "✓",
            }


# Global instance
context_loop = ContextDataLoop()
intensity_engine = context_loop.intensity_engine
