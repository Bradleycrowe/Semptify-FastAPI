"""
Event Bus - Central Nervous System for Semptify
Enables bi-directional communication between all modules.
"""

import asyncio
from typing import Any, Callable, Dict, List, Optional
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum
import logging
import json

logger = logging.getLogger(__name__)


class EventType(str, Enum):
    """All event types in the system"""
    # Document events
    DOCUMENT_ADDED = "document_added"
    DOCUMENT_UPDATED = "document_updated"
    DOCUMENT_DELETED = "document_deleted"
    DOCUMENT_PROCESSED = "document_processed"
    DOCUMENT_CLASSIFIED = "document_classified"

    # Data extraction events
    EVENTS_EXTRACTED = "events_extracted"
    DATES_EXTRACTED = "dates_extracted"
    AMOUNTS_EXTRACTED = "amounts_extracted"
    PARTIES_EXTRACTED = "parties_extracted"
    
    # Form data events
    FORM_DATA_UPDATED = "form_data_updated"
    CASE_INFO_UPDATED = "case_info_updated"
    PROFILE_UPDATED = "profile_updated"
    
    # Timeline events
    TIMELINE_UPDATED = "timeline_updated"
    TIMELINE_EVENT_ADDED = "timeline_event_added"
    
    # Calendar events
    DEADLINE_ADDED = "deadline_added"
    DEADLINE_APPROACHING = "deadline_approaching"
    HEARING_SCHEDULED = "hearing_scheduled"
    
    # Defense events
    VIOLATION_FOUND = "violation_found"
    DEFENSE_GENERATED = "defense_generated"
    STRATEGY_RECOMMENDED = "strategy_recommended"
    FORM_GENERATED = "form_generated"

    # AI events
    AI_ANALYSIS_COMPLETE = "ai_analysis_complete"
    AI_SUGGESTION_READY = "ai_suggestion_ready"
    
    # System events
    SETUP_COMPLETE = "setup_complete"
    USER_ACTION = "user_action"
    ERROR_OCCURRED = "error_occurred"
    
    # UI events
    UI_REFRESH_NEEDED = "ui_refresh_needed"
    NOTIFICATION = "notification"


@dataclass
class Event:
    """Event data structure"""
    type: EventType
    data: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.now)
    source: str = "system"
    user_id: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type.value,
            "data": self.data,
            "timestamp": self.timestamp.isoformat(),
            "source": self.source,
            "user_id": self.user_id,
        }
    
    def to_json(self) -> str:
        return json.dumps(self.to_dict())


class EventBus:
    """
    Central event bus for Semptify.
    Singleton pattern - one bus for entire application.
    """
    _instance: Optional["EventBus"] = None
    _initialized: bool = False
    
    def __new__(cls) -> "EventBus":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._subscribers: Dict[EventType, List[Callable]] = {}
        self._async_subscribers: Dict[EventType, List[Callable]] = {}
        self._websocket_connections: Dict[str, List[Any]] = {}  # user_id -> websockets
        self._event_history: List[Event] = []
        self._max_history = 1000
        self._initialized = True
        
        logger.info("🚌 EventBus initialized")
    
    def subscribe(self, event_type: EventType, callback: Callable) -> None:
        """Subscribe a sync callback to an event type"""
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(callback)
        logger.debug(f"Subscribed to {event_type.value}: {callback.__name__}")
    
    def subscribe_async(self, event_type: EventType, callback: Callable) -> None:
        """Subscribe an async callback to an event type"""
        if event_type not in self._async_subscribers:
            self._async_subscribers[event_type] = []
        self._async_subscribers[event_type].append(callback)
        logger.debug(f"Async subscribed to {event_type.value}: {callback.__name__}")
    
    def unsubscribe(self, event_type: EventType, callback: Callable) -> None:
        """Unsubscribe a callback from an event type"""
        if event_type in self._subscribers:
            self._subscribers[event_type] = [
                cb for cb in self._subscribers[event_type] if cb != callback
            ]
        if event_type in self._async_subscribers:
            self._async_subscribers[event_type] = [
                cb for cb in self._async_subscribers[event_type] if cb != callback
            ]
    
    async def publish(
        self,
        event_type: EventType,
        data: Dict[str, Any],
        source: str = "system",
        user_id: Optional[str] = None,
    ) -> Event:
        """
        Publish an event to all subscribers.
        Returns the created event.
        """
        event = Event(
            type=event_type,
            data=data,
            source=source,
            user_id=user_id,
        )
        
        # Store in history
        self._event_history.append(event)
        if len(self._event_history) > self._max_history:
            self._event_history = self._event_history[-self._max_history:]
        
        logger.info(f"📢 Event: {event_type.value} from {source}")
        
        # Call sync subscribers
        if event_type in self._subscribers:
            for callback in self._subscribers[event_type]:
                try:
                    callback(event)
                except Exception as e:
                    logger.error(f"Error in sync subscriber {callback.__name__}: {e}")
        
        # Call async subscribers
        if event_type in self._async_subscribers:
            for callback in self._async_subscribers[event_type]:
                try:
                    await callback(event)
                except Exception as e:
                    logger.error(f"Error in async subscriber {callback.__name__}: {e}")
        
        # Push to WebSocket connections
        await self._push_to_websockets(event, user_id)
        
        return event
    
    def publish_sync(
        self,
        event_type: EventType,
        data: Dict[str, Any],
        source: str = "system",
        user_id: Optional[str] = None,
    ) -> Event:
        """Synchronous publish - schedules async work"""
        event = Event(
            type=event_type,
            data=data,
            source=source,
            user_id=user_id,
        )
        
        self._event_history.append(event)
        if len(self._event_history) > self._max_history:
            self._event_history = self._event_history[-self._max_history:]
        
        # Call sync subscribers only
        if event_type in self._subscribers:
            for callback in self._subscribers[event_type]:
                try:
                    callback(event)
                except Exception as e:
                    logger.error(f"Error in sync subscriber: {e}")
        
        # Schedule async work
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(self._process_async_subscribers(event, user_id))
        except RuntimeError:
            pass  # No event loop, skip async
        
        return event
    
    async def _process_async_subscribers(self, event: Event, user_id: Optional[str]):
        """Process async subscribers and websockets"""
        if event.type in self._async_subscribers:
            for callback in self._async_subscribers[event.type]:
                try:
                    await callback(event)
                except Exception as e:
                    logger.error(f"Error in async subscriber: {e}")
        
        await self._push_to_websockets(event, user_id)
    
    async def _push_to_websockets(self, event: Event, user_id: Optional[str]):
        """Push event to connected WebSocket clients"""
        message = event.to_json()
        
        # Push to specific user if user_id provided
        if user_id and user_id in self._websocket_connections:
            for ws in self._websocket_connections[user_id]:
                try:
                    await ws.send_text(message)
                except Exception as e:
                    logger.error(f"WebSocket send error: {e}")
        
        # Also push to broadcast connections (user_id = "broadcast")
        if "broadcast" in self._websocket_connections:
            for ws in self._websocket_connections["broadcast"]:
                try:
                    await ws.send_text(message)
                except Exception as e:
                    logger.error(f"WebSocket broadcast error: {e}")
    
    def register_websocket(self, websocket: Any, user_id: str = "broadcast") -> None:
        """Register a WebSocket connection"""
        if user_id not in self._websocket_connections:
            self._websocket_connections[user_id] = []
        self._websocket_connections[user_id].append(websocket)
        logger.info(f"🔌 WebSocket registered for {user_id}")
    
    def unregister_websocket(self, websocket: Any, user_id: str = "broadcast") -> None:
        """Unregister a WebSocket connection"""
        if user_id in self._websocket_connections:
            self._websocket_connections[user_id] = [
                ws for ws in self._websocket_connections[user_id] if ws != websocket
            ]
    
    def get_history(
        self,
        event_type: Optional[EventType] = None,
        user_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[Event]:
        """Get recent events from history"""
        events = self._event_history
        
        if event_type:
            events = [e for e in events if e.type == event_type]
        
        if user_id:
            events = [e for e in events if e.user_id == user_id]
        
        return events[-limit:]
    
    def clear_history(self) -> None:
        """Clear event history"""
        self._event_history = []


# Global singleton instance
event_bus = EventBus()


# Convenience functions
async def publish_event(
    event_type: EventType,
    data: Dict[str, Any],
    source: str = "system",
    user_id: Optional[str] = None,
) -> Event:
    """Publish an event to the bus"""
    return await event_bus.publish(event_type, data, source, user_id)


def subscribe_to_event(event_type: EventType, callback: Callable) -> None:
    """Subscribe to an event type"""
    event_bus.subscribe(event_type, callback)


def subscribe_async_to_event(event_type: EventType, callback: Callable) -> None:
    """Subscribe async to an event type"""
    event_bus.subscribe_async(event_type, callback)


# Pre-built notification helpers
async def notify_document_added(doc_id: str, filename: str, user_id: str):
    """Notify that a document was added"""
    await publish_event(
        EventType.DOCUMENT_ADDED,
        {"doc_id": doc_id, "filename": filename},
        source="vault",
        user_id=user_id,
    )


async def notify_timeline_updated(events_count: int, user_id: str):
    """Notify that timeline was updated"""
    await publish_event(
        EventType.TIMELINE_UPDATED,
        {"events_count": events_count},
        source="timeline",
        user_id=user_id,
    )


async def notify_deadline_approaching(deadline: str, days_remaining: int, user_id: str):
    """Notify about approaching deadline"""
    await publish_event(
        EventType.DEADLINE_APPROACHING,
        {"deadline": deadline, "days_remaining": days_remaining},
        source="calendar",
        user_id=user_id,
    )


async def notify_violation_found(violation: str, law_ref: str, user_id: str):
    """Notify that a violation was found"""
    await publish_event(
        EventType.VIOLATION_FOUND,
        {"violation": violation, "law_ref": law_ref},
        source="defense",
        user_id=user_id,
    )


async def send_notification(title: str, message: str, level: str = "info", user_id: Optional[str] = None):
    """Send a UI notification"""
    await publish_event(
        EventType.NOTIFICATION,
        {"title": title, "message": message, "level": level},
        source="system",
        user_id=user_id,
    )
