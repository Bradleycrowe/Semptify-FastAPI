"""
Semptify SDK - Timeline Client

Handles timeline events, statute of limitations, and deadline tracking.
"""

from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from datetime import datetime, date

from .base import BaseClient


@dataclass
class TimelineEvent:
    """Timeline event information."""
    id: str
    event_type: str
    title: str
    description: Optional[str] = None
    event_date: Optional[date] = None
    importance: str = "normal"
    source: Optional[str] = None
    document_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass 
class Deadline:
    """Deadline information."""
    id: str
    title: str
    deadline_date: date
    deadline_type: str
    status: str = "pending"
    priority: str = "normal"
    description: Optional[str] = None
    days_remaining: Optional[int] = None
    statute_info: Optional[Dict[str, Any]] = None


@dataclass
class StatuteInfo:
    """Statute of limitations information."""
    statute_name: str
    jurisdiction: str
    limitation_period: str
    limitation_days: int
    start_date: Optional[date] = None
    deadline_date: Optional[date] = None
    days_remaining: Optional[int] = None
    tolling_info: Optional[Dict[str, Any]] = None


class TimelineClient(BaseClient):
    """Client for timeline and deadline operations."""
    
    def add_event(
        self,
        event_type: str,
        title: str,
        event_date: date,
        description: Optional[str] = None,
        importance: str = "normal",
        document_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> TimelineEvent:
        """
        Add a new event to the timeline.
        
        Args:
            event_type: Type of event (e.g., "notice_received", "payment_due")
            title: Event title
            event_date: Date of the event
            description: Event description
            importance: Importance level (low, normal, high, critical)
            document_id: Associated document ID
            metadata: Additional event metadata
            
        Returns:
            Created timeline event
        """
        data = {
            "event_type": event_type,
            "title": title,
            "event_date": event_date.isoformat(),
            "importance": importance,
        }
        
        if description:
            data["description"] = description
        if document_id:
            data["document_id"] = document_id
        if metadata:
            data["metadata"] = metadata
        
        response = self.post("/api/timeline/events", json=data)
        
        return TimelineEvent(
            id=response.get("id", ""),
            event_type=response.get("event_type", event_type),
            title=response.get("title", title),
            description=response.get("description"),
            event_date=date.fromisoformat(response["event_date"]) if response.get("event_date") else event_date,
            importance=response.get("importance", importance),
            document_id=response.get("document_id"),
            metadata=response.get("metadata"),
        )
    
    def get_events(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        event_type: Optional[str] = None,
        limit: int = 100,
    ) -> List[TimelineEvent]:
        """
        Get timeline events.
        
        Args:
            start_date: Filter events from this date
            end_date: Filter events until this date
            event_type: Filter by event type
            limit: Maximum events to return
            
        Returns:
            List of timeline events
        """
        params = {"limit": limit}
        if start_date:
            params["start_date"] = start_date.isoformat()
        if end_date:
            params["end_date"] = end_date.isoformat()
        if event_type:
            params["event_type"] = event_type
        
        response = self.get("/api/timeline/events", params=params)
        events = response if isinstance(response, list) else response.get("events", [])
        
        return [
            TimelineEvent(
                id=evt.get("id", ""),
                event_type=evt.get("event_type", ""),
                title=evt.get("title", ""),
                description=evt.get("description"),
                event_date=date.fromisoformat(evt["event_date"]) if evt.get("event_date") else None,
                importance=evt.get("importance", "normal"),
                document_id=evt.get("document_id"),
                metadata=evt.get("metadata"),
            )
            for evt in events
        ]
    
    def get_deadlines(
        self,
        status: Optional[str] = None,
        priority: Optional[str] = None,
        days_ahead: int = 30,
    ) -> List[Deadline]:
        """
        Get upcoming deadlines.
        
        Args:
            status: Filter by status (pending, completed, missed)
            priority: Filter by priority
            days_ahead: Number of days to look ahead
            
        Returns:
            List of deadlines
        """
        params = {"days_ahead": days_ahead}
        if status:
            params["status"] = status
        if priority:
            params["priority"] = priority
        
        response = self.get("/api/timeline/deadlines", params=params)
        deadlines = response if isinstance(response, list) else response.get("deadlines", [])
        
        return [
            Deadline(
                id=dl.get("id", ""),
                title=dl.get("title", ""),
                deadline_date=date.fromisoformat(dl["deadline_date"]) if dl.get("deadline_date") else date.today(),
                deadline_type=dl.get("deadline_type", ""),
                status=dl.get("status", "pending"),
                priority=dl.get("priority", "normal"),
                description=dl.get("description"),
                days_remaining=dl.get("days_remaining"),
                statute_info=dl.get("statute_info"),
            )
            for dl in deadlines
        ]
    
    def calculate_statute(
        self,
        violation_type: str,
        jurisdiction: str,
        incident_date: date,
        discovered_date: Optional[date] = None,
    ) -> StatuteInfo:
        """
        Calculate statute of limitations for a specific violation.
        
        Args:
            violation_type: Type of violation (e.g., "habitability", "retaliation")
            jurisdiction: Jurisdiction (e.g., "california")
            incident_date: Date the violation occurred
            discovered_date: Date the violation was discovered (for discovery rule)
            
        Returns:
            Statute of limitations information
        """
        data = {
            "violation_type": violation_type,
            "jurisdiction": jurisdiction,
            "incident_date": incident_date.isoformat(),
        }
        if discovered_date:
            data["discovered_date"] = discovered_date.isoformat()
        
        response = self.post("/api/timeline/statute/calculate", json=data)
        
        return StatuteInfo(
            statute_name=response.get("statute_name", ""),
            jurisdiction=response.get("jurisdiction", jurisdiction),
            limitation_period=response.get("limitation_period", ""),
            limitation_days=response.get("limitation_days", 0),
            start_date=date.fromisoformat(response["start_date"]) if response.get("start_date") else incident_date,
            deadline_date=date.fromisoformat(response["deadline_date"]) if response.get("deadline_date") else None,
            days_remaining=response.get("days_remaining"),
            tolling_info=response.get("tolling_info"),
        )
    
    def get_statute_deadlines(
        self,
        jurisdiction: Optional[str] = None,
    ) -> List[StatuteInfo]:
        """
        Get all statute of limitations deadlines.
        
        Args:
            jurisdiction: Filter by jurisdiction
            
        Returns:
            List of statute deadline information
        """
        params = {}
        if jurisdiction:
            params["jurisdiction"] = jurisdiction
        
        response = self.get("/api/timeline/statute/deadlines", params=params)
        statutes = response if isinstance(response, list) else response.get("statutes", [])
        
        return [
            StatuteInfo(
                statute_name=s.get("statute_name", ""),
                jurisdiction=s.get("jurisdiction", ""),
                limitation_period=s.get("limitation_period", ""),
                limitation_days=s.get("limitation_days", 0),
                start_date=date.fromisoformat(s["start_date"]) if s.get("start_date") else None,
                deadline_date=date.fromisoformat(s["deadline_date"]) if s.get("deadline_date") else None,
                days_remaining=s.get("days_remaining"),
                tolling_info=s.get("tolling_info"),
            )
            for s in statutes
        ]
    
    def get_timeline_summary(self) -> Dict[str, Any]:
        """
        Get a summary of the timeline with key events and deadlines.
        
        Returns:
            Timeline summary with statistics and highlights
        """
        return self.get("/api/timeline/summary")
    
    def delete_event(self, event_id: str) -> bool:
        """
        Delete a timeline event.
        
        Args:
            event_id: The event ID
            
        Returns:
            True if deleted successfully
        """
        self.delete(f"/api/timeline/events/{event_id}")
        return True
