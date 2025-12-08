"""
Smart Action Router
====================

AI-powered action suggestion system that combines:
- Emotional state (from EmotionEngine)
- Case status and deadlines
- User progress and history
- Legal requirements and timelines

This creates a "human guide" experience that adapts recommendations
based on the user's current emotional capacity and practical needs.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class ActionPriority(Enum):
    """Priority levels for suggested actions"""
    CRITICAL = "critical"      # Must do NOW - legal deadlines, emergencies
    HIGH = "high"              # Should do today
    MEDIUM = "medium"          # Should do this week
    LOW = "low"                # Nice to have
    MAINTENANCE = "maintenance" # Background tasks


class ActionCategory(Enum):
    """Categories of actions"""
    LEGAL_DEADLINE = "legal_deadline"
    EVIDENCE_COLLECTION = "evidence_collection"
    DOCUMENT_PREPARATION = "document_preparation"
    COURT_PREPARATION = "court_preparation"
    COMMUNICATION = "communication"
    SELF_CARE = "self_care"
    LEARNING = "learning"
    ORGANIZATION = "organization"


class EmotionalCapacity(Enum):
    """User's current capacity based on emotional state"""
    MINIMAL = "minimal"      # Can only handle 1 simple thing
    LIMITED = "limited"      # Can handle 2-3 simple things
    MODERATE = "moderate"    # Can handle normal workload
    HIGH = "high"            # Can handle complex tasks
    PEAK = "peak"            # Ready for challenging work


@dataclass
class SuggestedAction:
    """A single suggested action"""
    id: str
    title: str
    description: str
    category: ActionCategory
    priority: ActionPriority
    estimated_minutes: int
    emotional_cost: float  # 0-1, how emotionally draining
    page_url: str
    icon: str
    deadline: Optional[datetime] = None
    prerequisites: List[str] = field(default_factory=list)
    benefits: List[str] = field(default_factory=list)
    encouragement: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "category": self.category.value,
            "priority": self.priority.value,
            "estimated_minutes": self.estimated_minutes,
            "emotional_cost": self.emotional_cost,
            "page_url": self.page_url,
            "icon": self.icon,
            "deadline": self.deadline.isoformat() if self.deadline else None,
            "prerequisites": self.prerequisites,
            "benefits": self.benefits,
            "encouragement": self.encouragement
        }


@dataclass
class ActionPlan:
    """A complete action plan with emotional adaptation"""
    primary_action: SuggestedAction
    secondary_actions: List[SuggestedAction]
    self_care_reminder: Optional[SuggestedAction]
    emotional_capacity: EmotionalCapacity
    total_estimated_time: int
    encouragement_message: str
    mode: str  # crisis, focused, guided, flow, power
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "primary_action": self.primary_action.to_dict(),
            "secondary_actions": [a.to_dict() for a in self.secondary_actions],
            "self_care_reminder": self.self_care_reminder.to_dict() if self.self_care_reminder else None,
            "emotional_capacity": self.emotional_capacity.value,
            "total_estimated_time": self.total_estimated_time,
            "encouragement_message": self.encouragement_message,
            "mode": self.mode
        }


class SmartActionRouter:
    """
    Routes users to the best next action based on their emotional state
    and case requirements.
    """
    
    def __init__(self):
        # Define all possible actions
        self.action_library = self._build_action_library()
        
        # Encouragement messages by mode
        self.encouragements = {
            "crisis": [
                "Right now, only ONE thing matters. Let's focus on that.",
                "You're stronger than you know. Just this one step.",
                "Breathe. We'll handle this together, one piece at a time.",
                "In crisis, simplicity is power. Here's your one focus."
            ],
            "focused": [
                "You're doing great. Let's keep building momentum.",
                "Every step forward is a victory. Here's your next one.",
                "Stay focused on what's in front of you. You've got this.",
                "Small consistent actions lead to big wins."
            ],
            "guided": [
                "Let me help you navigate what comes next.",
                "Here's a clear path forward. No need to figure it all out alone.",
                "We'll work through this step by step together.",
                "You don't have to know everything. I'll guide you."
            ],
            "flow": [
                "You're in a great rhythm! Let's keep it going.",
                "Your momentum is building. Ride this wave.",
                "You're making real progress. Here's how to continue.",
                "This is your zone. Let's maximize it."
            ],
            "power": [
                "You're ready for anything. Let's tackle something big.",
                "Peak performance mode! Time for high-impact work.",
                "Channel this energy into your most important tasks.",
                "You're unstoppable right now. Let's use this."
            ]
        }
        
        # Self-care actions
        self.self_care_actions = [
            SuggestedAction(
                id="breathe",
                title="Take 3 Deep Breaths",
                description="Pause for 30 seconds. Breathe in for 4, hold for 4, out for 4.",
                category=ActionCategory.SELF_CARE,
                priority=ActionPriority.LOW,
                estimated_minutes=1,
                emotional_cost=0.0,
                page_url="#",
                icon="🧘",
                benefits=["Reduces stress", "Improves focus", "Calms nervous system"],
                encouragement="Your wellbeing matters. Take a moment."
            ),
            SuggestedAction(
                id="water",
                title="Drink Some Water",
                description="Hydration helps your brain work better.",
                category=ActionCategory.SELF_CARE,
                priority=ActionPriority.LOW,
                estimated_minutes=1,
                emotional_cost=0.0,
                page_url="#",
                icon="💧",
                benefits=["Improves clarity", "Boosts energy", "Supports focus"],
                encouragement="Small acts of self-care make a big difference."
            ),
            SuggestedAction(
                id="stretch",
                title="Quick Stretch Break",
                description="Stand up, stretch your arms, roll your shoulders.",
                category=ActionCategory.SELF_CARE,
                priority=ActionPriority.LOW,
                estimated_minutes=2,
                emotional_cost=0.0,
                page_url="#",
                icon="🙆",
                benefits=["Releases tension", "Improves circulation", "Refreshes mind"],
                encouragement="Your body carries stress. Give it a moment."
            ),
            SuggestedAction(
                id="celebrate",
                title="Celebrate Your Progress",
                description="Take a moment to acknowledge what you've accomplished.",
                category=ActionCategory.SELF_CARE,
                priority=ActionPriority.LOW,
                estimated_minutes=1,
                emotional_cost=-0.2,  # Actually helps!
                page_url="#",
                icon="🎉",
                benefits=["Boosts confidence", "Builds momentum", "Reduces overwhelm"],
                encouragement="You've done hard things. Honor that."
            )
        ]
    
    def _build_action_library(self) -> Dict[str, SuggestedAction]:
        """Build the library of all possible actions"""
        actions = {}
        
        # Evidence Collection Actions
        actions["upload_lease"] = SuggestedAction(
            id="upload_lease",
            title="Upload Your Lease",
            description="Your lease is the foundation of your case. Let's get it into the system.",
            category=ActionCategory.EVIDENCE_COLLECTION,
            priority=ActionPriority.HIGH,
            estimated_minutes=5,
            emotional_cost=0.2,
            page_url="/static/document_intake.html?type=lease",
            icon="📄",
            benefits=["Enables violation detection", "Required for court", "Protects your rights"],
            encouragement="This is one of the most important documents. You're doing the right thing."
        )
        
        actions["upload_payment_proof"] = SuggestedAction(
            id="upload_payment_proof",
            title="Upload Payment Records",
            description="Bank statements, receipts, money orders - proof you paid.",
            category=ActionCategory.EVIDENCE_COLLECTION,
            priority=ActionPriority.HIGH,
            estimated_minutes=10,
            emotional_cost=0.3,
            page_url="/static/document_intake.html?type=payment",
            icon="💰",
            benefits=["Proves payment history", "Counters false claims", "Strengthens defense"],
            encouragement="Every receipt is evidence. You're building your case."
        )
        
        actions["upload_maintenance_requests"] = SuggestedAction(
            id="upload_maintenance_requests",
            title="Upload Maintenance Requests",
            description="Emails, texts, letters about repairs you requested.",
            category=ActionCategory.EVIDENCE_COLLECTION,
            priority=ActionPriority.MEDIUM,
            estimated_minutes=15,
            emotional_cost=0.4,
            page_url="/static/document_intake.html?type=maintenance",
            icon="🔧",
            benefits=["Shows landlord neglect", "Supports habitability defense", "Documents timeline"],
            encouragement="Documenting maintenance issues is powerful defense."
        )
        
        actions["take_photos"] = SuggestedAction(
            id="take_photos",
            title="Photograph Housing Conditions",
            description="Take photos of any problems with your housing.",
            category=ActionCategory.EVIDENCE_COLLECTION,
            priority=ActionPriority.MEDIUM,
            estimated_minutes=20,
            emotional_cost=0.5,
            page_url="/static/document_intake.html?type=photos",
            icon="📸",
            benefits=["Visual evidence is powerful", "Documents conditions", "Hard to dispute"],
            encouragement="A picture is worth a thousand words in court."
        )
        
        # Document Preparation Actions
        actions["analyze_documents"] = SuggestedAction(
            id="analyze_documents",
            title="Analyze Your Documents",
            description="Let our AI review your documents for violations and issues.",
            category=ActionCategory.DOCUMENT_PREPARATION,
            priority=ActionPriority.HIGH,
            estimated_minutes=5,
            emotional_cost=0.3,
            page_url="/static/recognition.html",
            icon="🔍",
            benefits=["Finds violations automatically", "Identifies key issues", "Saves hours of research"],
            encouragement="Let the system work for you. Knowledge is power."
        )
        
        actions["generate_court_packet"] = SuggestedAction(
            id="generate_court_packet",
            title="Generate Court Packet",
            description="Create a professional, organized packet for court.",
            category=ActionCategory.COURT_PREPARATION,
            priority=ActionPriority.CRITICAL,
            estimated_minutes=10,
            emotional_cost=0.4,
            page_url="/static/court_packet.html",
            icon="📦",
            benefits=["Looks professional", "All evidence organized", "Judge-ready format"],
            encouragement="An organized packet shows the court you're serious."
        )
        
        actions["review_briefcase"] = SuggestedAction(
            id="review_briefcase",
            title="Review Your Briefcase",
            description="Check what documents you have and what you still need.",
            category=ActionCategory.ORGANIZATION,
            priority=ActionPriority.MEDIUM,
            estimated_minutes=10,
            emotional_cost=0.2,
            page_url="/static/briefcase.html",
            icon="💼",
            benefits=["See full picture", "Identify gaps", "Track progress"],
            encouragement="Organization reduces overwhelm. You're being smart."
        )
        
        # Court Preparation Actions
        actions["learn_court_basics"] = SuggestedAction(
            id="learn_court_basics",
            title="Learn Court Basics",
            description="Understand what to expect in housing court.",
            category=ActionCategory.LEARNING,
            priority=ActionPriority.MEDIUM,
            estimated_minutes=15,
            emotional_cost=0.3,
            page_url="/static/court_learning.html",
            icon="📚",
            benefits=["Reduces anxiety", "Prepares you mentally", "Know what to expect"],
            encouragement="Knowledge is your shield. The more you know, the less scary it becomes."
        )
        
        actions["research_laws"] = SuggestedAction(
            id="research_laws",
            title="Research Relevant Laws",
            description="Learn about the laws that protect you.",
            category=ActionCategory.LEARNING,
            priority=ActionPriority.LOW,
            estimated_minutes=20,
            emotional_cost=0.4,
            page_url="/static/law_library.html",
            icon="⚖️",
            benefits=["Understand your rights", "Find defenses", "Speak with authority"],
            encouragement="The law is on your side more than you might think."
        )
        
        actions["set_court_date"] = SuggestedAction(
            id="set_court_date",
            title="Record Your Court Date",
            description="Make sure your court date is in the system.",
            category=ActionCategory.COURT_PREPARATION,
            priority=ActionPriority.CRITICAL,
            estimated_minutes=2,
            emotional_cost=0.2,
            page_url="/static/calendar.html",
            icon="📅",
            benefits=["Never miss a deadline", "Countdown tracking", "Automatic reminders"],
            encouragement="Knowing your deadline is the first step to meeting it."
        )
        
        # Communication Actions
        actions["add_contacts"] = SuggestedAction(
            id="add_contacts",
            title="Add Important Contacts",
            description="Store contact info for landlord, lawyers, agencies.",
            category=ActionCategory.COMMUNICATION,
            priority=ActionPriority.LOW,
            estimated_minutes=5,
            emotional_cost=0.1,
            page_url="/static/contacts.html",
            icon="👥",
            benefits=["Quick access", "Organized info", "Track communications"],
            encouragement="Building your support network is important."
        )
        
        actions["find_legal_aid"] = SuggestedAction(
            id="find_legal_aid",
            title="Find Legal Help",
            description="Locate free legal aid resources in your area.",
            category=ActionCategory.COMMUNICATION,
            priority=ActionPriority.HIGH,
            estimated_minutes=15,
            emotional_cost=0.3,
            page_url="/static/help.html",
            icon="🆘",
            benefits=["Professional guidance", "Free resources", "Expert support"],
            encouragement="You don't have to do this alone. Help exists."
        )
        
        return actions
    
    def assess_emotional_capacity(self, emotional_state: Dict[str, float]) -> EmotionalCapacity:
        """
        Assess user's current emotional capacity based on their state.
        """
        if not emotional_state:
            return EmotionalCapacity.MODERATE
        
        # Calculate key metrics
        overwhelm = emotional_state.get("overwhelm", 0.3)
        clarity = emotional_state.get("clarity", 0.6)
        confidence = emotional_state.get("confidence", 0.5)
        momentum = emotional_state.get("momentum", 0.4)
        intensity = emotional_state.get("intensity", 0.5)
        
        # Crisis check
        if overwhelm > 0.8 or (intensity > 0.8 and clarity < 0.3):
            return EmotionalCapacity.MINIMAL
        
        # Calculate composite score
        capacity_score = (
            (1 - overwhelm) * 0.3 +
            clarity * 0.25 +
            confidence * 0.2 +
            momentum * 0.15 +
            (1 - intensity * 0.5) * 0.1  # Very high intensity can drain
        )
        
        if capacity_score < 0.3:
            return EmotionalCapacity.MINIMAL
        elif capacity_score < 0.45:
            return EmotionalCapacity.LIMITED
        elif capacity_score < 0.6:
            return EmotionalCapacity.MODERATE
        elif capacity_score < 0.75:
            return EmotionalCapacity.HIGH
        else:
            return EmotionalCapacity.PEAK
    
    def get_dashboard_mode(self, emotional_state: Dict[str, float]) -> str:
        """Determine dashboard mode from emotional state"""
        if not emotional_state:
            return "guided"
        
        overwhelm = emotional_state.get("overwhelm", 0.3)
        intensity = emotional_state.get("intensity", 0.5)
        clarity = emotional_state.get("clarity", 0.6)
        confidence = emotional_state.get("confidence", 0.5)
        momentum = emotional_state.get("momentum", 0.4)
        resolve = emotional_state.get("resolve", 0.5)
        
        # Calculate crisis level
        crisis_level = (intensity * 0.3) + (overwhelm * 0.4) + ((1 - clarity) * 0.15) + ((1 - confidence) * 0.15)
        
        # Calculate readiness
        readiness = (clarity + confidence + resolve + momentum) / 4
        
        if crisis_level > 0.7 or overwhelm > 0.8:
            return "crisis"
        elif crisis_level > 0.5:
            return "focused"
        elif readiness < 0.4:
            return "guided"
        elif readiness > 0.7 and momentum > 0.6:
            return "power"
        elif momentum > 0.5 and clarity > 0.6:
            return "flow"
        
        return "guided"
    
    def filter_actions_by_capacity(
        self,
        actions: List[SuggestedAction],
        capacity: EmotionalCapacity
    ) -> List[SuggestedAction]:
        """Filter actions based on emotional capacity"""
        
        # Maximum emotional cost by capacity
        max_cost = {
            EmotionalCapacity.MINIMAL: 0.2,
            EmotionalCapacity.LIMITED: 0.35,
            EmotionalCapacity.MODERATE: 0.5,
            EmotionalCapacity.HIGH: 0.7,
            EmotionalCapacity.PEAK: 1.0
        }
        
        # Maximum time commitment by capacity
        max_time = {
            EmotionalCapacity.MINIMAL: 5,
            EmotionalCapacity.LIMITED: 15,
            EmotionalCapacity.MODERATE: 30,
            EmotionalCapacity.HIGH: 60,
            EmotionalCapacity.PEAK: 120
        }
        
        threshold_cost = max_cost.get(capacity, 0.5)
        threshold_time = max_time.get(capacity, 30)
        
        return [
            a for a in actions
            if a.emotional_cost <= threshold_cost and a.estimated_minutes <= threshold_time
        ]
    
    def prioritize_actions(
        self,
        actions: List[SuggestedAction],
        case_context: Dict[str, Any],
        capacity: EmotionalCapacity
    ) -> List[SuggestedAction]:
        """
        Prioritize actions based on case context and deadlines.
        """
        def priority_score(action: SuggestedAction) -> float:
            score = 0.0
            
            # Priority weight
            priority_weights = {
                ActionPriority.CRITICAL: 100,
                ActionPriority.HIGH: 50,
                ActionPriority.MEDIUM: 20,
                ActionPriority.LOW: 5,
                ActionPriority.MAINTENANCE: 1
            }
            score += priority_weights.get(action.priority, 10)
            
            # Deadline urgency
            if action.deadline:
                days_until = (action.deadline - datetime.now()).days
                if days_until <= 0:
                    score += 200  # Past due!
                elif days_until <= 3:
                    score += 100
                elif days_until <= 7:
                    score += 50
                elif days_until <= 14:
                    score += 25
            
            # Case context modifiers
            if case_context.get("has_court_date"):
                if action.category == ActionCategory.COURT_PREPARATION:
                    score += 30
            
            if not case_context.get("has_lease"):
                if action.id == "upload_lease":
                    score += 40
            
            if case_context.get("maintenance_issues"):
                if action.id == "upload_maintenance_requests":
                    score += 35
            
            # Reduce score if emotional cost is high relative to capacity
            if capacity in [EmotionalCapacity.MINIMAL, EmotionalCapacity.LIMITED]:
                score -= action.emotional_cost * 20
            
            return score
        
        return sorted(actions, key=priority_score, reverse=True)
    
    def generate_action_plan(
        self,
        emotional_state: Dict[str, float],
        case_context: Dict[str, Any]
    ) -> ActionPlan:
        """
        Generate a personalized action plan based on emotional state and case needs.
        """
        # Assess capacity and mode
        capacity = self.assess_emotional_capacity(emotional_state)
        mode = self.get_dashboard_mode(emotional_state)
        
        # Get all relevant actions
        all_actions = list(self.action_library.values())
        
        # Filter by capacity
        suitable_actions = self.filter_actions_by_capacity(all_actions, capacity)
        
        # If nothing suitable, still provide critical items
        if not suitable_actions:
            suitable_actions = [a for a in all_actions if a.priority == ActionPriority.CRITICAL]
            if suitable_actions:
                # Take the lowest emotional cost critical item
                suitable_actions.sort(key=lambda a: a.emotional_cost)
                suitable_actions = suitable_actions[:1]
        
        # Prioritize
        prioritized = self.prioritize_actions(suitable_actions, case_context, capacity)
        
        # Select actions based on capacity
        num_secondary = {
            EmotionalCapacity.MINIMAL: 0,
            EmotionalCapacity.LIMITED: 1,
            EmotionalCapacity.MODERATE: 2,
            EmotionalCapacity.HIGH: 3,
            EmotionalCapacity.PEAK: 5
        }.get(capacity, 2)
        
        primary = prioritized[0] if prioritized else None
        secondary = prioritized[1:num_secondary + 1] if len(prioritized) > 1 else []
        
        # Add self-care reminder if needed
        self_care = None
        if capacity in [EmotionalCapacity.MINIMAL, EmotionalCapacity.LIMITED]:
            # Pick appropriate self-care
            if emotional_state.get("overwhelm", 0) > 0.6:
                self_care = self.self_care_actions[0]  # Breathe
            elif emotional_state.get("momentum", 0) > 0.5:
                self_care = self.self_care_actions[3]  # Celebrate
            else:
                import random
                self_care = random.choice(self.self_care_actions[:3])
        
        # Calculate total time
        total_time = (primary.estimated_minutes if primary else 0) + sum(a.estimated_minutes for a in secondary)
        
        # Get encouragement message
        import random
        encouragement = random.choice(self.encouragements.get(mode, self.encouragements["guided"]))
        
        return ActionPlan(
            primary_action=primary,
            secondary_actions=secondary,
            self_care_reminder=self_care,
            emotional_capacity=capacity,
            total_estimated_time=total_time,
            encouragement_message=encouragement,
            mode=mode
        )
    
    def get_quick_wins(self, case_context: Dict[str, Any]) -> List[SuggestedAction]:
        """
        Get a list of quick win actions (low time, low emotional cost, immediate benefit).
        """
        quick_wins = []
        
        for action in self.action_library.values():
            if action.estimated_minutes <= 5 and action.emotional_cost <= 0.3:
                quick_wins.append(action)
        
        return sorted(quick_wins, key=lambda a: a.estimated_minutes)
    
    def get_actions_by_category(self, category: ActionCategory) -> List[SuggestedAction]:
        """Get all actions in a specific category"""
        return [a for a in self.action_library.values() if a.category == category]


# Singleton instance
action_router = SmartActionRouter()
