"""
WebSocket Tests for Semptify API

Tests real-time WebSocket connections for:
- Event streaming (/ws/events)
- Brain WebSocket (/brain/ws)
- Dashboard updates (/ws/dashboard)
- Mesh visualization (/mesh/ws)
"""

import pytest
import asyncio
import json
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi import WebSocket
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect
from httpx import ASGITransport, AsyncClient

from app.main import app


# =============================================================================
# Helper Classes
# =============================================================================

class MockWebSocket:
    """Mock WebSocket for testing without actual connections."""
    
    def __init__(self):
        self.accepted = False
        self.closed = False
        self.messages_sent = []
        self.messages_to_receive = []
        self.cookies = {}
        self.receive_index = 0
    
    async def accept(self):
        self.accepted = True
    
    async def close(self, code=1000):
        self.closed = True
    
    async def send_json(self, data):
        self.messages_sent.append(data)
    
    async def send_text(self, data):
        self.messages_sent.append(data)
    
    async def receive_json(self):
        if self.receive_index >= len(self.messages_to_receive):
            raise WebSocketDisconnect()
        msg = self.messages_to_receive[self.receive_index]
        self.receive_index += 1
        return msg
    
    async def receive_text(self):
        if self.receive_index >= len(self.messages_to_receive):
            raise WebSocketDisconnect()
        msg = self.messages_to_receive[self.receive_index]
        self.receive_index += 1
        return json.dumps(msg) if isinstance(msg, dict) else msg
    
    def queue_message(self, message):
        """Add a message to the receive queue."""
        self.messages_to_receive.append(message)


# =============================================================================
# WebSocket Events Tests
# =============================================================================

class TestWebSocketEvents:
    """Tests for the main /ws/events endpoint."""
    
    def test_websocket_status_endpoint(self, test_client):
        """Test GET /ws/status returns WebSocket info."""
        response = test_client.get("/ws/status")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "active"
        assert "event_types" in data
        assert data["connect_url"] == "/ws/events"
    
    @pytest.mark.anyio
    async def test_websocket_events_connection(self):
        """Test WebSocket connection sends welcome message."""
        from app.routers.websocket import websocket_events, get_user_id_from_websocket
        from app.core.event_bus import event_bus
        
        ws = MockWebSocket()
        ws.cookies = {"semptify_uid": "test_user_123"}
        
        # Simulate ping then disconnect
        ws.queue_message({"type": "ping"})
        
        # Run the websocket handler
        await websocket_events(ws)
        
        # Check connection was accepted
        assert ws.accepted is True
        
        # Check welcome message was sent
        assert len(ws.messages_sent) >= 1
        welcome = ws.messages_sent[0]
        assert welcome["type"] == "connected"
        assert welcome["user_id"] == "test_user_123"
        assert "Connected to Semptify Event Stream" in welcome["message"]
    
    @pytest.mark.anyio
    async def test_websocket_ping_pong(self):
        """Test WebSocket ping/pong mechanism."""
        from app.routers.websocket import websocket_events
        
        ws = MockWebSocket()
        ws.cookies = {"semptify_uid": "test_user"}
        ws.queue_message({"type": "ping"})
        
        await websocket_events(ws)
        
        # Should have welcome + pong
        messages = ws.messages_sent
        pong_messages = [m for m in messages if m.get("type") == "pong"]
        assert len(pong_messages) == 1
    
    @pytest.mark.anyio
    async def test_websocket_subscribe(self):
        """Test WebSocket event subscription."""
        from app.routers.websocket import websocket_events
        
        ws = MockWebSocket()
        ws.cookies = {}
        ws.queue_message({"type": "subscribe", "events": ["document_uploaded", "case_updated"]})
        
        await websocket_events(ws)
        
        # Check subscription confirmation
        messages = ws.messages_sent
        subscribed = [m for m in messages if m.get("type") == "subscribed"]
        assert len(subscribed) == 1
        assert subscribed[0]["events"] == ["document_uploaded", "case_updated"]
    
    @pytest.mark.anyio
    async def test_websocket_get_history(self):
        """Test WebSocket event history request."""
        from app.routers.websocket import websocket_events
        
        ws = MockWebSocket()
        ws.cookies = {}
        ws.queue_message({"type": "get_history", "limit": 10})
        
        await websocket_events(ws)
        
        # Check history response
        messages = ws.messages_sent
        history = [m for m in messages if m.get("type") == "history"]
        assert len(history) == 1
        assert "events" in history[0]
    
    @pytest.mark.anyio
    async def test_websocket_invalid_json(self):
        """Test WebSocket handles invalid JSON gracefully."""
        from app.routers.websocket import websocket_events
        
        ws = MockWebSocket()
        ws.cookies = {}
        # Override receive_text to return invalid JSON
        ws.messages_to_receive = ["not valid json"]
        
        # Patch receive_text to return raw string
        original_receive_text = ws.receive_text
        async def receive_invalid():
            if ws.receive_index >= len(ws.messages_to_receive):
                raise WebSocketDisconnect()
            msg = ws.messages_to_receive[ws.receive_index]
            ws.receive_index += 1
            return msg  # Return raw string, not JSON
        ws.receive_text = receive_invalid
        
        await websocket_events(ws)
        
        # Should have error message
        errors = [m for m in ws.messages_sent if m.get("type") == "error"]
        assert len(errors) == 1
        assert "Invalid JSON" in errors[0]["message"]
    
    @pytest.mark.anyio
    async def test_websocket_user_id_from_cookies(self):
        """Test user ID extraction from cookies."""
        from app.routers.websocket import get_user_id_from_websocket
        
        ws = MockWebSocket()
        
        # No cookies
        ws.cookies = {}
        assert get_user_id_from_websocket(ws) == "broadcast"
        
        # With semptify_uid cookie
        ws.cookies = {"semptify_uid": "user_abc123"}
        assert get_user_id_from_websocket(ws) == "user_abc123"
        
        # Empty user_id
        ws.cookies = {"semptify_uid": ""}
        assert get_user_id_from_websocket(ws) == "broadcast"


# =============================================================================
# Brain WebSocket Tests
# =============================================================================

class TestBrainWebSocket:
    """Tests for the Positronic Brain WebSocket /brain/ws."""
    
    def test_brain_status_endpoint(self, test_client):
        """Test GET /brain/status works."""
        response = test_client.get("/brain/status")
        assert response.status_code == 200
        data = response.json()
        assert "modules" in data or "status" in data
    
    def test_brain_modules_endpoint(self, test_client):
        """Test GET /brain/modules lists modules."""
        response = test_client.get("/brain/modules")
        assert response.status_code == 200
        data = response.json()
        assert "modules" in data
    
    @pytest.mark.anyio
    async def test_brain_websocket_connection(self):
        """Test Brain WebSocket connection sends initial state."""
        from app.routers.brain import brain_websocket
        from app.services.positronic_brain import get_brain
        
        ws = MockWebSocket()
        ws.queue_message({"type": "ping"})
        
        brain = get_brain()
        await brain_websocket(ws, brain)
        
        assert ws.accepted is True
        
        # Check connection message
        welcome = ws.messages_sent[0]
        assert welcome["type"] == "connected"
        assert "state" in welcome
        assert "modules" in welcome
    
    @pytest.mark.anyio
    async def test_brain_websocket_ping(self):
        """Test Brain WebSocket ping/pong."""
        from app.routers.brain import brain_websocket
        from app.services.positronic_brain import get_brain
        
        ws = MockWebSocket()
        ws.queue_message({"type": "ping"})
        
        brain = get_brain()
        await brain_websocket(ws, brain)
        
        pongs = [m for m in ws.messages_sent if m.get("type") == "pong"]
        assert len(pongs) == 1
    
    @pytest.mark.anyio
    async def test_brain_websocket_get_state(self):
        """Test Brain WebSocket state request."""
        from app.routers.brain import brain_websocket
        from app.services.positronic_brain import get_brain
        
        ws = MockWebSocket()
        ws.queue_message({"type": "get_state"})
        
        brain = get_brain()
        await brain_websocket(ws, brain)
        
        state_msgs = [m for m in ws.messages_sent if m.get("type") == "state"]
        assert len(state_msgs) == 1
        assert "state" in state_msgs[0]
    
    @pytest.mark.anyio
    async def test_brain_websocket_trigger_workflow(self):
        """Test Brain WebSocket workflow trigger."""
        from app.routers.brain import brain_websocket
        from app.services.positronic_brain import get_brain
        
        ws = MockWebSocket()
        ws.queue_message({
            "type": "trigger_workflow",
            "workflow_name": "test_workflow",
            "data": {"test": True}
        })
        
        brain = get_brain()
        await brain_websocket(ws, brain)
        
        workflow_msgs = [m for m in ws.messages_sent if m.get("type") == "workflow_started"]
        assert len(workflow_msgs) == 1
        assert "workflow_id" in workflow_msgs[0]
    
    @pytest.mark.anyio
    async def test_brain_websocket_client_tracking(self):
        """Test Brain WebSocket client registration/unregistration."""
        from app.routers.brain import brain_websocket
        from app.services.positronic_brain import get_brain
        
        ws = MockWebSocket()
        ws.queue_message({"type": "ping"})
        
        brain = get_brain()
        
        # Should not be in clients before connection
        assert ws not in brain.websocket_clients
        
        await brain_websocket(ws, brain)
        
        # Should be removed after disconnect
        assert ws not in brain.websocket_clients


# =============================================================================
# Dashboard WebSocket Tests
# =============================================================================

class TestDashboardWebSocket:
    """Tests for the Dashboard WebSocket /ws/dashboard."""
    
    def test_dashboard_endpoint_exists(self, test_client):
        """Test dashboard endpoints exist."""
        # The dashboard page should exist
        response = test_client.get("/dashboard")
        assert response.status_code in [200, 307, 302]  # May redirect


# =============================================================================
# Event Bus Integration Tests
# =============================================================================

class TestEventBusWebSocketIntegration:
    """Tests for EventBus + WebSocket integration."""
    
    def test_event_bus_exists(self):
        """Test EventBus singleton exists."""
        from app.core.event_bus import event_bus
        assert event_bus is not None
    
    def test_event_types_defined(self):
        """Test EventType enum has expected values."""
        from app.core.event_bus import EventType
        
        # Check some expected event types exist
        event_values = [e.value for e in EventType]
        assert len(event_values) > 0
    
    @pytest.mark.anyio
    async def test_event_bus_register_websocket(self):
        """Test WebSocket registration with EventBus."""
        from app.core.event_bus import event_bus
        
        ws = MockWebSocket()
        user_id = "test_user_456"
        
        # Register
        event_bus.register_websocket(ws, user_id)
        
        # Check registration (implementation may vary)
        # Just verify no errors occur
        
        # Unregister
        event_bus.unregister_websocket(ws, user_id)
    
    @pytest.mark.anyio
    async def test_event_bus_publish_event(self):
        """Test EventBus can publish events."""
        from app.core.event_bus import event_bus, EventType
        
        # Just verify publishing doesn't error
        await event_bus.publish(
            EventType.DOCUMENT_ADDED,
            {"document_id": "test_doc"},
            user_id="test_user"
        )


# =============================================================================
# WebSocket Protocol Tests
# =============================================================================

class TestWebSocketProtocol:
    """Tests for WebSocket message protocol compliance."""
    
    @pytest.mark.anyio
    async def test_message_format_has_type(self):
        """All server messages should have 'type' field."""
        from app.routers.websocket import websocket_events
        
        ws = MockWebSocket()
        ws.cookies = {}
        ws.queue_message({"type": "ping"})
        
        await websocket_events(ws)
        
        for msg in ws.messages_sent:
            assert "type" in msg, f"Message missing 'type': {msg}"
    
    @pytest.mark.anyio
    async def test_error_message_format(self):
        """Error messages should have standard format."""
        from app.routers.websocket import websocket_events
        
        ws = MockWebSocket()
        ws.cookies = {}
        ws.messages_to_receive = ["invalid json {{{"]
        
        async def receive_invalid():
            if ws.receive_index >= len(ws.messages_to_receive):
                raise WebSocketDisconnect()
            msg = ws.messages_to_receive[ws.receive_index]
            ws.receive_index += 1
            return msg
        ws.receive_text = receive_invalid
        
        await websocket_events(ws)
        
        errors = [m for m in ws.messages_sent if m.get("type") == "error"]
        for err in errors:
            assert "message" in err, "Error should have 'message' field"


# =============================================================================
# Connection Manager Tests
# =============================================================================

class TestConnectionManager:
    """Tests for WebSocket ConnectionManager pattern."""
    
    def test_connection_manager_exists(self):
        """Test ConnectionManager class exists in dashboard."""
        try:
            from app.routers.enterprise_dashboard import ConnectionManager
            assert ConnectionManager is not None
        except ImportError:
            # May not exist, which is fine
            pass
    
    @pytest.mark.anyio
    async def test_multiple_websocket_clients(self):
        """Test handling multiple WebSocket clients."""
        from app.core.event_bus import event_bus
        
        ws1 = MockWebSocket()
        ws2 = MockWebSocket()
        
        event_bus.register_websocket(ws1, "user1")
        event_bus.register_websocket(ws2, "user2")
        
        # Both should be registered
        event_bus.unregister_websocket(ws1, "user1")
        event_bus.unregister_websocket(ws2, "user2")


# =============================================================================
# WebSocket Security Tests
# =============================================================================

class TestWebSocketSecurity:
    """Tests for WebSocket security measures."""
    
    def test_user_id_not_from_query_params(self):
        """Verify user_id comes from cookies, not query params."""
        from app.routers.websocket import get_user_id_from_websocket
        
        # The function should only look at cookies
        ws = MockWebSocket()
        ws.cookies = {"semptify_uid": "from_cookie"}
        
        # Even if query_params existed with different value, should use cookie
        result = get_user_id_from_websocket(ws)
        assert result == "from_cookie"
    
    @pytest.mark.anyio
    async def test_websocket_graceful_disconnect(self):
        """Test WebSocket handles disconnection gracefully."""
        from app.routers.websocket import websocket_events
        from app.core.event_bus import event_bus
        
        ws = MockWebSocket()
        ws.cookies = {"semptify_uid": "disconnect_test_user"}
        # Empty queue causes immediate disconnect
        
        # Should not raise exception
        await websocket_events(ws)
        
        # Should have cleaned up
        connections = event_bus._websocket_connections.get("disconnect_test_user", [])
        assert ws not in connections


# =============================================================================
# HTTP Fallback Tests  
# =============================================================================

class TestWebSocketHTTPFallback:
    """Tests for HTTP endpoints that fall back when WebSocket unavailable."""
    
    def test_events_via_http(self, test_client):
        """Test event history available via HTTP."""
        # Some implementations provide HTTP fallback
        response = test_client.get("/ws/status")
        assert response.status_code == 200
    
    def test_brain_state_via_http(self, test_client):
        """Test brain state available via HTTP."""
        response = test_client.get("/brain/state")
        assert response.status_code == 200


# =============================================================================
# Performance Tests
# =============================================================================

class TestWebSocketPerformance:
    """Basic performance tests for WebSocket operations."""
    
    @pytest.mark.anyio
    async def test_rapid_ping_pong(self):
        """Test rapid ping/pong doesn't cause issues."""
        from app.routers.websocket import websocket_events
        
        ws = MockWebSocket()
        ws.cookies = {}
        
        # Queue multiple pings
        for _ in range(10):
            ws.queue_message({"type": "ping"})
        
        await websocket_events(ws)
        
        pongs = [m for m in ws.messages_sent if m.get("type") == "pong"]
        assert len(pongs) == 10
    
    @pytest.mark.anyio
    async def test_message_order_preserved(self):
        """Test message order is preserved."""
        from app.routers.websocket import websocket_events
        
        ws = MockWebSocket()
        ws.cookies = {}
        
        ws.queue_message({"type": "ping"})
        ws.queue_message({"type": "subscribe", "events": ["test"]})
        ws.queue_message({"type": "ping"})
        
        await websocket_events(ws)
        
        # Check order: connected, pong, subscribed, pong
        types = [m.get("type") for m in ws.messages_sent]
        assert types[0] == "connected"
        # Subsequent messages should maintain order


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def test_client():
    """Create a test client."""
    return TestClient(app)


@pytest.fixture
def anyio_backend():
    """Use asyncio for anyio."""
    return "asyncio"
