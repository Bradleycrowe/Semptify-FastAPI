"""
WebSocket Router for Real-Time Events
Pushes events to browser for live UI updates.
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from typing import Optional
import logging
import json

from app.core.event_bus import event_bus, EventType

logger = logging.getLogger(__name__)
router = APIRouter()


@router.websocket("/events")
async def websocket_events(
    websocket: WebSocket,
    user_id: Optional[str] = Query(default="broadcast"),
):
    """
    WebSocket endpoint for real-time events.
    
    Connect: ws://localhost:8000/ws/events?user_id=xxx
    
    Receives all events published to the EventBus.
    """
    await websocket.accept()
    logger.info(f"🔌 WebSocket connected: {user_id}")
    
    # Register with event bus
    event_bus.register_websocket(websocket, user_id)
    
    try:
        # Send welcome message
        await websocket.send_json({
            "type": "connected",
            "message": "Connected to Semptify Event Stream",
            "user_id": user_id,
        })
        
        # Keep connection alive and handle incoming messages
        while True:
            try:
                # Receive messages from client (for ping/pong and commands)
                data = await websocket.receive_text()
                message = json.loads(data)
                
                if message.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})
                
                elif message.get("type") == "subscribe":
                    # Client can subscribe to specific event types
                    event_types = message.get("events", [])
                    await websocket.send_json({
                        "type": "subscribed",
                        "events": event_types,
                    })
                
                elif message.get("type") == "get_history":
                    # Client requests recent events
                    event_type = message.get("event_type")
                    limit = message.get("limit", 50)
                    
                    history = event_bus.get_history(
                        event_type=EventType(event_type) if event_type else None,
                        user_id=user_id if user_id != "broadcast" else None,
                        limit=limit,
                    )
                    
                    await websocket.send_json({
                        "type": "history",
                        "events": [e.to_dict() for e in history],
                    })
                    
            except json.JSONDecodeError:
                await websocket.send_json({
                    "type": "error",
                    "message": "Invalid JSON",
                })
                
    except WebSocketDisconnect:
        logger.info(f"🔌 WebSocket disconnected: {user_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        # Unregister from event bus
        event_bus.unregister_websocket(websocket, user_id)


@router.get("/status")
async def get_websocket_status():
    """Get WebSocket connection status"""
    return {
        "status": "active",
        "event_types": [e.value for e in EventType],
        "connect_url": "/ws/events",
        "usage": "Connect via WebSocket to receive real-time events",
    }
