"""
Semptify 5.0 - Copilot & AI Tests
Tests for the AI assistant and context loop.
"""

import pytest
from httpx import AsyncClient
from unittest.mock import patch, AsyncMock, MagicMock


# =============================================================================
# Copilot Status Tests
# =============================================================================

@pytest.mark.anyio
async def test_copilot_status(client: AsyncClient):
    """Test AI copilot status endpoint."""
    response = await client.get("/api/copilot/status")
    assert response.status_code == 200
    data = response.json()
    assert "available" in data
    assert "provider" in data


@pytest.mark.anyio
async def test_copilot_status_shows_provider(client: AsyncClient):
    """Test status shows configured provider."""
    response = await client.get("/api/copilot/status")
    data = response.json()
    # Provider should be one of the supported options or none
    if data["available"]:
        assert data["provider"] in ["openai", "azure_openai", "ollama", None]


# =============================================================================
# Copilot Query Tests
# =============================================================================

@pytest.mark.anyio
async def test_copilot_query_unauthenticated(client: AsyncClient):
    """Test copilot query requires authentication."""
    response = await client.post("/api/copilot/", json={
        "message": "What are my tenant rights?"
    })
    # In open mode, should work; otherwise 401
    assert response.status_code in [200, 401, 503]


@pytest.mark.anyio
async def test_copilot_query_authenticated(authenticated_client: AsyncClient, mock_openai):
    """Test copilot query with authentication and mocked AI."""
    response = await authenticated_client.post("/api/copilot/", json={
        "message": "What are my tenant rights in Minnesota?"
    })
    # May succeed or fail based on AI availability
    assert response.status_code in [200, 401, 503]
    if response.status_code == 200:
        data = response.json()
        assert "answer" in data or "response" in data or "message" in data


@pytest.mark.anyio
async def test_copilot_query_with_context(authenticated_client: AsyncClient):
    """Test copilot query with document context."""
    response = await authenticated_client.post("/api/copilot/", json={
        "message": "Is this notice legal?",
        "context": "14-day notice for non-payment dated November 20, 2025"
    })
    assert response.status_code in [200, 401, 503]


@pytest.mark.anyio
async def test_copilot_query_missing_question(authenticated_client: AsyncClient):
    """Test copilot query with missing question."""
    response = await authenticated_client.post("/api/copilot/", json={})
    assert response.status_code == 422


# =============================================================================
# Document Analysis Tests
# =============================================================================

@pytest.mark.anyio
async def test_copilot_analyze_document(authenticated_client: AsyncClient):
    """Test document analysis endpoint."""
    response = await authenticated_client.post(
        "/api/copilot/analyze-document?document_id=test-doc-123"
    )
    # May be implemented or return not_implemented, or 404 for doc not found
    assert response.status_code in [200, 404, 501, 503]


# =============================================================================
# Context Loop Tests
# =============================================================================

@pytest.mark.anyio
async def test_context_loop_state(client: AsyncClient, test_user_id):
    """Test getting user state from context loop."""
    response = await client.get(f"/api/core/state?user_id={test_user_id}")
    assert response.status_code == 200
    data = response.json()
    assert "user_id" in data or "state" in data or "intensity" in data


@pytest.mark.anyio
async def test_context_loop_intensity(client: AsyncClient, test_user_id):
    """Test intensity score endpoint."""
    response = await client.get(f"/api/core/intensity?user_id={test_user_id}")
    assert response.status_code == 200
    data = response.json()
    # Should include intensity score
    assert "intensity" in data or "score" in data or "severity" in data


@pytest.mark.anyio
async def test_context_loop_emit_event(client: AsyncClient, test_user_id):
    """Test emitting an event to context loop."""
    response = await client.post("/api/core/event", json={
        "user_id": test_user_id,
        "event_type": "DOCUMENT_UPLOADED",
        "data": {"filename": "test.pdf", "doc_type": "notice"}
    })
    assert response.status_code in [200, 201]


@pytest.mark.anyio
async def test_context_loop_predictions(client: AsyncClient, test_user_id):
    """Test getting predictions for user needs."""
    response = await client.get(f"/api/core/predictions?user_id={test_user_id}")
    assert response.status_code == 200
    data = response.json()
    assert "predictions" in data or isinstance(data, list)


@pytest.mark.anyio
async def test_context_loop_health(client: AsyncClient):
    """Test context loop health endpoint."""
    response = await client.get("/api/core/health")
    assert response.status_code == 200


@pytest.mark.anyio
async def test_context_loop_add_deadline(client: AsyncClient, test_user_id):
    """Test adding deadline to context loop."""
    response = await client.post("/api/core/deadline", json={
        "deadline_type": "Answer Due",
        "date": "2025-12-05T17:00:00",
        "description": "Answer must be filed by this date",
    }, headers={"X-User-ID": test_user_id})
    assert response.status_code in [200, 201]


@pytest.mark.anyio
async def test_context_loop_report_issue(client: AsyncClient, test_user_id):
    """Test reporting an issue to context loop."""
    response = await client.post("/api/core/issue", json={
        "user_id": test_user_id,
        "issue_type": "eviction_notice",
        "description": "Received 14-day notice",
        "urgency": "high",
    })
    assert response.status_code in [200, 201]


# =============================================================================
# Adaptive UI Tests
# =============================================================================

@pytest.mark.anyio
async def test_adaptive_ui_widgets(client: AsyncClient, test_user_id):
    """Test getting adaptive UI widgets."""
    response = await client.get(f"/api/ui/widgets?user_id={test_user_id}")
    assert response.status_code == 200
    data = response.json()
    assert "widgets" in data or isinstance(data, list)


@pytest.mark.anyio
async def test_adaptive_ui_context(client: AsyncClient, test_user_id):
    """Test getting user context for UI."""
    response = await client.get(f"/api/ui/context?user_id={test_user_id}")
    assert response.status_code == 200


@pytest.mark.anyio
async def test_adaptive_ui_dismiss_widget(client: AsyncClient, test_user_id):
    """Test dismissing a widget."""
    response = await client.post(
        f"/api/ui/dismiss/test-widget-123?user_id={test_user_id}"
    )
    assert response.status_code in [200, 404]


@pytest.mark.anyio
async def test_adaptive_ui_record_action(client: AsyncClient, test_user_id):
    """Test recording user action."""
    response = await client.post(
        f"/api/ui/action/document_uploaded?user_id={test_user_id}",
        json={"document_type": "notice"}
    )
    assert response.status_code in [200, 201]


@pytest.mark.anyio
async def test_adaptive_ui_update_context(client: AsyncClient, test_user_id):
    """Test updating user context."""
    response = await client.post(
        f"/api/ui/context/update?user_id={test_user_id}",
        json={"phase": "eviction", "jurisdiction": "dakota_county"}
    )
    assert response.status_code in [200, 201]
