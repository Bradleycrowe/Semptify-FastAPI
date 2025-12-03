"""
Semptify 5.0 - Timeline & Calendar Tests
Tests for timeline events and calendar management.
"""

import pytest
from httpx import AsyncClient
from datetime import datetime, timedelta


# =============================================================================
# Timeline Tests
# =============================================================================

@pytest.mark.anyio
async def test_timeline_create_event(client: AsyncClient, sample_timeline_event):
    """Test creating a timeline event."""
    response = await client.post("/api/timeline/", json=sample_timeline_event)
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == sample_timeline_event["title"]
    assert data["event_type"] == sample_timeline_event["event_type"]
    assert data["is_evidence"] == sample_timeline_event["is_evidence"]
    assert "id" in data


@pytest.mark.anyio
async def test_timeline_list_events(client: AsyncClient, sample_timeline_event):
    """Test listing timeline events."""
    # Create an event first
    await client.post("/api/timeline/", json=sample_timeline_event)
    
    response = await client.get("/api/timeline/")
    assert response.status_code == 200
    data = response.json()
    assert "events" in data
    assert "total" in data
    assert data["total"] >= 1


@pytest.mark.anyio
async def test_timeline_get_single_event(client: AsyncClient, sample_timeline_event):
    """Test getting a single timeline event."""
    # Create an event
    create_response = await client.post("/api/timeline/", json=sample_timeline_event)
    event_id = create_response.json()["id"]
    
    response = await client.get(f"/api/timeline/{event_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == event_id


@pytest.mark.anyio
async def test_timeline_update_event(client: AsyncClient, sample_timeline_event):
    """Test updating a timeline event."""
    # Create an event
    create_response = await client.post("/api/timeline/", json=sample_timeline_event)
    event_id = create_response.json()["id"]
    
    # Update it
    response = await client.patch(
        f"/api/timeline/{event_id}",
        json={"title": "Updated Title", "is_evidence": False}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Updated Title"
    assert data["is_evidence"] is False


@pytest.mark.anyio
async def test_timeline_delete_event(client: AsyncClient, sample_timeline_event):
    """Test deleting a timeline event."""
    # Create an event
    create_response = await client.post("/api/timeline/", json=sample_timeline_event)
    event_id = create_response.json()["id"]
    
    # Delete it
    response = await client.delete(f"/api/timeline/{event_id}")
    assert response.status_code in [200, 204]
    
    # Verify deleted
    get_response = await client.get(f"/api/timeline/{event_id}")
    assert get_response.status_code == 404


@pytest.mark.anyio
async def test_timeline_filter_by_type(client: AsyncClient):
    """Test filtering timeline events by type."""
    # Create events of different types
    await client.post("/api/timeline/", json={
        "event_type": "notice",
        "title": "Notice Event",
        "event_date": "2025-11-25T10:00:00",
    })
    await client.post("/api/timeline/", json={
        "event_type": "payment",
        "title": "Payment Event",
        "event_date": "2025-11-26T10:00:00",
    })
    
    # Filter by type
    response = await client.get("/api/timeline/?event_type=notice")
    assert response.status_code == 200
    data = response.json()
    for event in data["events"]:
        assert event["event_type"] == "notice"


@pytest.mark.anyio
async def test_timeline_types_summary(client: AsyncClient, sample_timeline_event):
    """Test timeline types summary endpoint."""
    await client.post("/api/timeline/", json=sample_timeline_event)
    
    response = await client.get("/api/timeline/types/summary")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, dict)


@pytest.mark.anyio
@pytest.mark.parametrize("event_type", ["notice", "payment", "maintenance", "communication", "court", "other"])
async def test_timeline_all_event_types(client: AsyncClient, event_type):
    """Test creating events of all supported types."""
    response = await client.post("/api/timeline/", json={
        "event_type": event_type,
        "title": f"Test {event_type} event",
        "event_date": "2025-11-25T10:00:00",
    })
    assert response.status_code == 201


# =============================================================================
# Calendar Tests
# =============================================================================

@pytest.mark.anyio
async def test_calendar_create_event(client: AsyncClient, sample_calendar_event):
    """Test creating a calendar event."""
    response = await client.post("/api/calendar/", json=sample_calendar_event)
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == sample_calendar_event["title"]
    assert data["event_type"] == sample_calendar_event["event_type"]
    assert data["is_critical"] == sample_calendar_event["is_critical"]
    assert "id" in data


@pytest.mark.anyio
async def test_calendar_list_events(client: AsyncClient, sample_calendar_event):
    """Test listing calendar events."""
    await client.post("/api/calendar/", json=sample_calendar_event)
    
    response = await client.get("/api/calendar/")
    assert response.status_code == 200
    data = response.json()
    assert "events" in data
    assert "total" in data


@pytest.mark.anyio
async def test_calendar_upcoming(client: AsyncClient):
    """Test upcoming deadlines endpoint."""
    # Create future events
    future_date = (datetime.now() + timedelta(days=10)).isoformat()
    await client.post("/api/calendar/", json={
        "title": "Future Hearing",
        "start_datetime": future_date,
        "event_type": "hearing",
        "is_critical": True,
    })
    
    response = await client.get("/api/calendar/upcoming?days=30")
    assert response.status_code == 200
    data = response.json()
    assert "critical" in data or "upcoming" in data


@pytest.mark.anyio
async def test_calendar_get_single_event(client: AsyncClient, sample_calendar_event):
    """Test getting a single calendar event."""
    create_response = await client.post("/api/calendar/", json=sample_calendar_event)
    event_id = create_response.json()["id"]
    
    response = await client.get(f"/api/calendar/{event_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == event_id


@pytest.mark.anyio
async def test_calendar_update_event(client: AsyncClient, sample_calendar_event):
    """Test updating a calendar event."""
    create_response = await client.post("/api/calendar/", json=sample_calendar_event)
    event_id = create_response.json()["id"]
    
    response = await client.patch(
        f"/api/calendar/{event_id}",
        json={"title": "Updated Hearing", "is_critical": False}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Updated Hearing"


@pytest.mark.anyio
async def test_calendar_delete_event(client: AsyncClient, sample_calendar_event):
    """Test deleting a calendar event."""
    create_response = await client.post("/api/calendar/", json=sample_calendar_event)
    event_id = create_response.json()["id"]
    
    response = await client.delete(f"/api/calendar/{event_id}")
    assert response.status_code in [200, 204]


@pytest.mark.anyio
@pytest.mark.parametrize("event_type", ["deadline", "hearing", "reminder", "appointment", "rent_due"])
async def test_calendar_all_event_types(client: AsyncClient, event_type):
    """Test creating calendar events of all types."""
    response = await client.post("/api/calendar/", json={
        "title": f"Test {event_type}",
        "start_datetime": "2025-12-15T09:00:00",
        "event_type": event_type,
    })
    assert response.status_code == 201


@pytest.mark.anyio
async def test_calendar_date_range_filter(client: AsyncClient):
    """Test filtering calendar events by date range."""
    # Create events
    await client.post("/api/calendar/", json={
        "title": "December Event",
        "start_datetime": "2025-12-15T09:00:00",
        "event_type": "deadline",
    })
    
    response = await client.get(
        "/api/calendar/?start_date=2025-12-01&end_date=2025-12-31"
    )
    assert response.status_code == 200


# =============================================================================
# Error Case Tests
# =============================================================================

@pytest.mark.anyio
async def test_timeline_invalid_event_type(client: AsyncClient):
    """Test creating timeline event with invalid type."""
    response = await client.post("/api/timeline/", json={
        "event_type": "invalid_type",
        "title": "Test Event",
        "event_date": "2025-11-25T10:00:00",
    })
    assert response.status_code == 422  # Validation error


@pytest.mark.anyio
async def test_timeline_missing_required_fields(client: AsyncClient):
    """Test creating timeline event with missing fields."""
    response = await client.post("/api/timeline/", json={
        "event_type": "notice",
        # Missing title and event_date
    })
    assert response.status_code == 422


@pytest.mark.anyio
async def test_calendar_invalid_datetime(client: AsyncClient):
    """Test creating calendar event with invalid datetime."""
    response = await client.post("/api/calendar/", json={
        "title": "Test Event",
        "start_datetime": "not-a-datetime",
        "event_type": "deadline",
    })
    assert response.status_code == 422


@pytest.mark.anyio
async def test_get_nonexistent_timeline_event(client: AsyncClient):
    """Test getting a non-existent timeline event."""
    response = await client.get("/api/timeline/nonexistent-id")
    assert response.status_code == 404


@pytest.mark.anyio
async def test_get_nonexistent_calendar_event(client: AsyncClient):
    """Test getting a non-existent calendar event."""
    response = await client.get("/api/calendar/nonexistent-id")
    assert response.status_code == 404
