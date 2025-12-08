"""
Progress Tracker Service
========================

Tracks user progress through their legal journey.
Stores milestones, completed tasks, and overall case readiness.
This data feeds into the emotion engine and action router.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any, Set
from enum import Enum
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class MilestoneCategory(Enum):
    """Categories of milestones"""
    ONBOARDING = "onboarding"
    EVIDENCE_COLLECTION = "evidence_collection"
    DOCUMENT_ANALYSIS = "document_analysis"
    COURT_PREPARATION = "court_preparation"
    LEARNING = "learning"
    LEGAL_FILINGS = "legal_filings"


class MilestoneStatus(Enum):
    """Status of a milestone"""
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    SKIPPED = "skipped"


@dataclass
class Milestone:
    """A single milestone in the user's journey"""
    id: str
    name: str
    description: str
    category: MilestoneCategory
    order: int  # Order within category
    required: bool = True
    prerequisites: List[str] = field(default_factory=list)
    points: int = 10  # Points toward case readiness
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "category": self.category.value,
            "order": self.order,
            "required": self.required,
            "prerequisites": self.prerequisites,
            "points": self.points
        }


@dataclass
class CompletedMilestone:
    """Record of a completed milestone"""
    milestone_id: str
    completed_at: datetime
    notes: Optional[str] = None
    evidence_ids: List[str] = field(default_factory=list)  # Related documents
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "milestone_id": self.milestone_id,
            "completed_at": self.completed_at.isoformat(),
            "notes": self.notes,
            "evidence_ids": self.evidence_ids
        }


@dataclass
class UserProgress:
    """Complete progress state for a user"""
    user_id: str
    case_type: Optional[str] = None
    court_date: Optional[datetime] = None
    journey_started: Optional[datetime] = None
    completed_milestones: Dict[str, CompletedMilestone] = field(default_factory=dict)
    skipped_milestones: Set[str] = field(default_factory=set)
    current_focus: Optional[str] = None
    
    # Stats
    documents_uploaded: int = 0
    violations_found: int = 0
    forms_generated: int = 0
    tasks_completed: int = 0
    streak_days: int = 0
    last_active: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "case_type": self.case_type,
            "court_date": self.court_date.isoformat() if self.court_date else None,
            "journey_started": self.journey_started.isoformat() if self.journey_started else None,
            "completed_milestones": {k: v.to_dict() for k, v in self.completed_milestones.items()},
            "skipped_milestones": list(self.skipped_milestones),
            "current_focus": self.current_focus,
            "documents_uploaded": self.documents_uploaded,
            "violations_found": self.violations_found,
            "forms_generated": self.forms_generated,
            "tasks_completed": self.tasks_completed,
            "streak_days": self.streak_days,
            "last_active": self.last_active.isoformat() if self.last_active else None
        }


class ProgressTracker:
    """
    Tracks user progress through their legal defense journey.
    """
    
    def __init__(self, data_dir: str = "data/progress"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # Define all milestones
        self.milestones = self._define_milestones()
        
        # Current user progress (in-memory cache)
        self._progress_cache: Dict[str, UserProgress] = {}
    
    def _define_milestones(self) -> Dict[str, Milestone]:
        """Define all milestones in the system"""
        milestones = {}
        
        # Onboarding milestones
        milestones["intake_complete"] = Milestone(
            id="intake_complete",
            name="Complete Crisis Intake",
            description="Tell us about your situation",
            category=MilestoneCategory.ONBOARDING,
            order=1,
            points=15
        )
        
        milestones["first_login"] = Milestone(
            id="first_login",
            name="First Login",
            description="Access your dashboard",
            category=MilestoneCategory.ONBOARDING,
            order=2,
            points=5
        )
        
        milestones["tour_complete"] = Milestone(
            id="tour_complete",
            name="Complete Welcome Tour",
            description="Learn how to use Semptify",
            category=MilestoneCategory.ONBOARDING,
            order=3,
            required=False,
            points=10
        )
        
        # Evidence Collection milestones
        milestones["upload_notice"] = Milestone(
            id="upload_notice",
            name="Upload Eviction Notice",
            description="Add your eviction notice for AI analysis",
            category=MilestoneCategory.EVIDENCE_COLLECTION,
            order=1,
            prerequisites=["intake_complete"],
            points=25
        )
        
        milestones["upload_lease"] = Milestone(
            id="upload_lease",
            name="Upload Lease Agreement",
            description="Add your lease for violation detection",
            category=MilestoneCategory.EVIDENCE_COLLECTION,
            order=2,
            points=25
        )
        
        milestones["upload_payment_proof"] = Milestone(
            id="upload_payment_proof",
            name="Upload Payment Records",
            description="Add proof of rent payments",
            category=MilestoneCategory.EVIDENCE_COLLECTION,
            order=3,
            points=20
        )
        
        milestones["upload_maintenance"] = Milestone(
            id="upload_maintenance",
            name="Upload Maintenance Requests",
            description="Add repair requests and communications",
            category=MilestoneCategory.EVIDENCE_COLLECTION,
            order=4,
            required=False,
            points=20
        )
        
        milestones["upload_photos"] = Milestone(
            id="upload_photos",
            name="Document Property Conditions",
            description="Take photos of any issues",
            category=MilestoneCategory.EVIDENCE_COLLECTION,
            order=5,
            required=False,
            points=20
        )
        
        milestones["five_documents"] = Milestone(
            id="five_documents",
            name="Upload 5 Documents",
            description="Build a solid evidence base",
            category=MilestoneCategory.EVIDENCE_COLLECTION,
            order=6,
            required=False,
            points=15
        )
        
        milestones["ten_documents"] = Milestone(
            id="ten_documents",
            name="Upload 10 Documents",
            description="Comprehensive evidence collection",
            category=MilestoneCategory.EVIDENCE_COLLECTION,
            order=7,
            required=False,
            points=25
        )
        
        # Document Analysis milestones
        milestones["first_analysis"] = Milestone(
            id="first_analysis",
            name="First Document Analysis",
            description="Let AI analyze a document",
            category=MilestoneCategory.DOCUMENT_ANALYSIS,
            order=1,
            points=20
        )
        
        milestones["violation_found"] = Milestone(
            id="violation_found",
            name="Find a Violation",
            description="AI detected a legal violation",
            category=MilestoneCategory.DOCUMENT_ANALYSIS,
            order=2,
            required=False,
            points=30
        )
        
        milestones["highlight_evidence"] = Milestone(
            id="highlight_evidence",
            name="Highlight Key Evidence",
            description="Mark important sections in documents",
            category=MilestoneCategory.DOCUMENT_ANALYSIS,
            order=3,
            required=False,
            points=15
        )
        
        # Court Preparation milestones
        milestones["set_court_date"] = Milestone(
            id="set_court_date",
            name="Record Court Date",
            description="Add your hearing date to calendar",
            category=MilestoneCategory.COURT_PREPARATION,
            order=1,
            points=15
        )
        
        milestones["generate_packet"] = Milestone(
            id="generate_packet",
            name="Generate Court Packet",
            description="Create your organized evidence packet",
            category=MilestoneCategory.COURT_PREPARATION,
            order=2,
            prerequisites=["first_analysis"],
            points=30
        )
        
        milestones["review_briefcase"] = Milestone(
            id="review_briefcase",
            name="Review Briefcase",
            description="Check your document organization",
            category=MilestoneCategory.COURT_PREPARATION,
            order=3,
            points=10
        )
        
        milestones["court_ready"] = Milestone(
            id="court_ready",
            name="Court Ready",
            description="All essential documents prepared",
            category=MilestoneCategory.COURT_PREPARATION,
            order=4,
            prerequisites=["upload_notice", "generate_packet"],
            points=50
        )
        
        # Learning milestones
        milestones["read_rights"] = Milestone(
            id="read_rights",
            name="Learn Your Rights",
            description="Review tenant rights information",
            category=MilestoneCategory.LEARNING,
            order=1,
            required=False,
            points=15
        )
        
        milestones["court_basics"] = Milestone(
            id="court_basics",
            name="Court Basics Course",
            description="Learn what to expect in court",
            category=MilestoneCategory.LEARNING,
            order=2,
            required=False,
            points=20
        )
        
        milestones["research_laws"] = Milestone(
            id="research_laws",
            name="Research Relevant Laws",
            description="Study laws that apply to your case",
            category=MilestoneCategory.LEARNING,
            order=3,
            required=False,
            points=20
        )
        
        # Legal Filings milestones
        milestones["generate_answer"] = Milestone(
            id="generate_answer",
            name="Generate Answer Form",
            description="Create your response to the complaint",
            category=MilestoneCategory.LEGAL_FILINGS,
            order=1,
            points=35
        )
        
        milestones["file_answer"] = Milestone(
            id="file_answer",
            name="File Answer with Court",
            description="Submit your answer to the court",
            category=MilestoneCategory.LEGAL_FILINGS,
            order=2,
            prerequisites=["generate_answer"],
            points=50
        )
        
        milestones["file_complaint"] = Milestone(
            id="file_complaint",
            name="File Regulatory Complaint",
            description="Report violations to authorities",
            category=MilestoneCategory.LEGAL_FILINGS,
            order=3,
            required=False,
            points=30
        )
        
        return milestones
    
    def get_progress(self, user_id: str = "default") -> UserProgress:
        """Get progress for a user"""
        if user_id in self._progress_cache:
            return self._progress_cache[user_id]
        
        # Try to load from file
        progress_file = self.data_dir / f"{user_id}.json"
        if progress_file.exists():
            try:
                with open(progress_file) as f:
                    data = json.load(f)
                progress = self._dict_to_progress(data)
                self._progress_cache[user_id] = progress
                return progress
            except Exception as e:
                logger.error(f"Failed to load progress for {user_id}: {e}")
        
        # Create new progress
        progress = UserProgress(
            user_id=user_id,
            journey_started=datetime.now(),
            last_active=datetime.now()
        )
        self._progress_cache[user_id] = progress
        return progress
    
    def _dict_to_progress(self, data: Dict[str, Any]) -> UserProgress:
        """Convert dict to UserProgress"""
        completed = {}
        for k, v in data.get("completed_milestones", {}).items():
            completed[k] = CompletedMilestone(
                milestone_id=v["milestone_id"],
                completed_at=datetime.fromisoformat(v["completed_at"]),
                notes=v.get("notes"),
                evidence_ids=v.get("evidence_ids", [])
            )
        
        return UserProgress(
            user_id=data["user_id"],
            case_type=data.get("case_type"),
            court_date=datetime.fromisoformat(data["court_date"]) if data.get("court_date") else None,
            journey_started=datetime.fromisoformat(data["journey_started"]) if data.get("journey_started") else None,
            completed_milestones=completed,
            skipped_milestones=set(data.get("skipped_milestones", [])),
            current_focus=data.get("current_focus"),
            documents_uploaded=data.get("documents_uploaded", 0),
            violations_found=data.get("violations_found", 0),
            forms_generated=data.get("forms_generated", 0),
            tasks_completed=data.get("tasks_completed", 0),
            streak_days=data.get("streak_days", 0),
            last_active=datetime.fromisoformat(data["last_active"]) if data.get("last_active") else None
        )
    
    def save_progress(self, user_id: str = "default") -> bool:
        """Save progress to file"""
        if user_id not in self._progress_cache:
            return False
        
        progress = self._progress_cache[user_id]
        progress_file = self.data_dir / f"{user_id}.json"
        
        try:
            with open(progress_file, "w") as f:
                json.dump(progress.to_dict(), f, indent=2)
            return True
        except Exception as e:
            logger.error(f"Failed to save progress for {user_id}: {e}")
            return False
    
    def complete_milestone(
        self,
        milestone_id: str,
        user_id: str = "default",
        notes: Optional[str] = None,
        evidence_ids: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Mark a milestone as completed"""
        progress = self.get_progress(user_id)
        milestone = self.milestones.get(milestone_id)
        
        if not milestone:
            return {"success": False, "error": "Milestone not found"}
        
        # Check prerequisites
        for prereq in milestone.prerequisites:
            if prereq not in progress.completed_milestones:
                return {
                    "success": False,
                    "error": f"Prerequisite not met: {prereq}"
                }
        
        # Check if already completed
        if milestone_id in progress.completed_milestones:
            return {
                "success": True,
                "already_completed": True,
                "message": "Milestone was already completed"
            }
        
        # Complete the milestone
        completed = CompletedMilestone(
            milestone_id=milestone_id,
            completed_at=datetime.now(),
            notes=notes,
            evidence_ids=evidence_ids or []
        )
        progress.completed_milestones[milestone_id] = completed
        progress.tasks_completed += 1
        progress.last_active = datetime.now()
        
        # Update streak
        self._update_streak(progress)
        
        # Save
        self.save_progress(user_id)
        
        # Check for unlocked milestones
        unlocked = self._get_unlocked_milestones(progress)
        
        return {
            "success": True,
            "milestone": milestone.to_dict(),
            "points_earned": milestone.points,
            "total_points": self.get_total_points(user_id),
            "case_readiness": self.get_case_readiness(user_id),
            "newly_unlocked": [m.to_dict() for m in unlocked],
            "encouragement": self._get_completion_message(milestone)
        }
    
    def _update_streak(self, progress: UserProgress):
        """Update user's activity streak"""
        if progress.last_active:
            days_since = (datetime.now() - progress.last_active).days
            if days_since <= 1:
                progress.streak_days += 1
            elif days_since > 1:
                progress.streak_days = 1
        else:
            progress.streak_days = 1
    
    def _get_unlocked_milestones(self, progress: UserProgress) -> List[Milestone]:
        """Get milestones that were just unlocked"""
        unlocked = []
        for milestone in self.milestones.values():
            if milestone.id in progress.completed_milestones:
                continue
            if milestone.id in progress.skipped_milestones:
                continue
            
            # Check if prerequisites are now met
            prereqs_met = all(
                p in progress.completed_milestones
                for p in milestone.prerequisites
            )
            if prereqs_met and milestone.prerequisites:
                unlocked.append(milestone)
        
        return unlocked
    
    def _get_completion_message(self, milestone: Milestone) -> str:
        """Get encouraging message for completing a milestone"""
        messages = {
            MilestoneCategory.ONBOARDING: [
                "Great start! You're taking control.",
                "You've begun your journey. Every step matters.",
                "Welcome aboard! Let's build your defense together."
            ],
            MilestoneCategory.EVIDENCE_COLLECTION: [
                "Evidence secured! Your case grows stronger.",
                "Every document is ammunition for your defense.",
                "Nice work! The more evidence, the better your chances."
            ],
            MilestoneCategory.DOCUMENT_ANALYSIS: [
                "Knowledge is power! Now you know what you're working with.",
                "Our AI is on your side. Together we'll find every advantage.",
                "Analysis complete. You're building a real strategy."
            ],
            MilestoneCategory.COURT_PREPARATION: [
                "You're getting ready for battle. This takes courage.",
                "Preparation is half the victory. You're doing it right.",
                "Looking professional and organized impresses judges."
            ],
            MilestoneCategory.LEARNING: [
                "Education arms you with the best weapon: knowledge.",
                "The more you know, the less scary this becomes.",
                "You're becoming an expert on your own rights."
            ],
            MilestoneCategory.LEGAL_FILINGS: [
                "This is a major step! You're officially fighting back.",
                "Filing documents shows you mean business.",
                "The wheels of justice are now turning in your favor."
            ]
        }
        
        import random
        category_messages = messages.get(milestone.category, ["Great progress!"])
        return random.choice(category_messages)
    
    def get_total_points(self, user_id: str = "default") -> int:
        """Get total points earned"""
        progress = self.get_progress(user_id)
        total = 0
        for milestone_id in progress.completed_milestones:
            if milestone_id in self.milestones:
                total += self.milestones[milestone_id].points
        return total
    
    def get_case_readiness(self, user_id: str = "default") -> Dict[str, Any]:
        """Calculate overall case readiness"""
        progress = self.get_progress(user_id)
        
        # Calculate max possible points from required milestones
        max_points = sum(
            m.points for m in self.milestones.values()
            if m.required
        )
        
        # Calculate earned points from required milestones
        earned_points = sum(
            self.milestones[m].points
            for m in progress.completed_milestones
            if m in self.milestones and self.milestones[m].required
        )
        
        readiness_percent = (earned_points / max_points * 100) if max_points > 0 else 0
        
        # Determine readiness level
        if readiness_percent >= 90:
            level = "excellent"
            message = "Your case is in great shape!"
        elif readiness_percent >= 70:
            level = "good"
            message = "Your case is building nicely."
        elif readiness_percent >= 50:
            level = "fair"
            message = "You're making progress. Keep going!"
        elif readiness_percent >= 25:
            level = "developing"
            message = "You've started. Every step helps."
        else:
            level = "early"
            message = "Let's build your defense together."
        
        # Calculate category progress
        category_progress = {}
        for cat in MilestoneCategory:
            cat_milestones = [m for m in self.milestones.values() if m.category == cat]
            completed = [m for m in cat_milestones if m.id in progress.completed_milestones]
            category_progress[cat.value] = {
                "total": len(cat_milestones),
                "completed": len(completed),
                "percent": (len(completed) / len(cat_milestones) * 100) if cat_milestones else 0
            }
        
        return {
            "percent": round(readiness_percent, 1),
            "level": level,
            "message": message,
            "earned_points": earned_points,
            "max_points": max_points,
            "total_points": self.get_total_points(user_id),
            "category_progress": category_progress,
            "documents_uploaded": progress.documents_uploaded,
            "violations_found": progress.violations_found,
            "streak_days": progress.streak_days
        }
    
    def get_next_milestones(self, user_id: str = "default", limit: int = 3) -> List[Dict[str, Any]]:
        """Get the next recommended milestones to complete"""
        progress = self.get_progress(user_id)
        
        available = []
        for milestone in self.milestones.values():
            # Skip completed or skipped
            if milestone.id in progress.completed_milestones:
                continue
            if milestone.id in progress.skipped_milestones:
                continue
            
            # Check prerequisites
            prereqs_met = all(
                p in progress.completed_milestones
                for p in milestone.prerequisites
            )
            if not prereqs_met:
                continue
            
            available.append(milestone)
        
        # Sort by: required first, then by order
        available.sort(key=lambda m: (not m.required, m.order))
        
        return [m.to_dict() for m in available[:limit]]
    
    def get_all_milestones(self, user_id: str = "default") -> Dict[str, Any]:
        """Get all milestones with status for a user"""
        progress = self.get_progress(user_id)
        
        result = {}
        for cat in MilestoneCategory:
            cat_milestones = sorted(
                [m for m in self.milestones.values() if m.category == cat],
                key=lambda m: m.order
            )
            
            result[cat.value] = []
            for milestone in cat_milestones:
                status = MilestoneStatus.NOT_STARTED
                completed_at = None
                
                if milestone.id in progress.completed_milestones:
                    status = MilestoneStatus.COMPLETED
                    completed_at = progress.completed_milestones[milestone.id].completed_at
                elif milestone.id in progress.skipped_milestones:
                    status = MilestoneStatus.SKIPPED
                
                # Check if available (prerequisites met)
                prereqs_met = all(
                    p in progress.completed_milestones
                    for p in milestone.prerequisites
                )
                
                result[cat.value].append({
                    **milestone.to_dict(),
                    "status": status.value,
                    "completed_at": completed_at.isoformat() if completed_at else None,
                    "available": prereqs_met and status == MilestoneStatus.NOT_STARTED
                })
        
        return result
    
    def increment_stat(self, stat: str, user_id: str = "default", amount: int = 1) -> bool:
        """Increment a progress stat"""
        progress = self.get_progress(user_id)
        
        if stat == "documents_uploaded":
            progress.documents_uploaded += amount
            # Check document count milestones
            if progress.documents_uploaded >= 5:
                self.complete_milestone("five_documents", user_id)
            if progress.documents_uploaded >= 10:
                self.complete_milestone("ten_documents", user_id)
        elif stat == "violations_found":
            progress.violations_found += amount
            if progress.violations_found >= 1:
                self.complete_milestone("violation_found", user_id)
        elif stat == "forms_generated":
            progress.forms_generated += amount
        
        progress.last_active = datetime.now()
        self._update_streak(progress)
        return self.save_progress(user_id)


# Singleton instance
progress_tracker = ProgressTracker()
