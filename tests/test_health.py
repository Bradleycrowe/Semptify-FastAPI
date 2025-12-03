"""
Semptify 5.0 - Health & Monitoring Tests
Tests for health checks, readiness, and metrics.
"""

import pytest
from httpx import AsyncClient


# =============================================================================
# Health Check Tests
# =============================================================================

@pytest.mark.anyio
async def test_healthz(client: AsyncClient):
    """Test basic health check endpoint."""
    response = await client.get("/healthz")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "timestamp" in data


@pytest.mark.anyio
async def test_health_alias(client: AsyncClient):
    """Test /health alias endpoint."""
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


@pytest.mark.anyio
async def test_healthz_response_format(client: AsyncClient):
    """Test health check response has expected format."""
    response = await client.get("/healthz")
    data = response.json()
    
    # Should have status and timestamp
    assert "status" in data
    assert "timestamp" in data
    
    # Timestamp should be ISO format
    import re
    iso_pattern = r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}'
    assert re.match(iso_pattern, data["timestamp"])


# =============================================================================
# Readiness Check Tests
# =============================================================================

@pytest.mark.anyio
async def test_readyz(client: AsyncClient):
    """Test readiness check endpoint."""
    response = await client.get("/readyz")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert data["status"] in ["ready", "degraded"]
    assert "checks" in data


@pytest.mark.anyio
async def test_readyz_checks_structure(client: AsyncClient):
    """Test readiness check returns expected checks."""
    response = await client.get("/readyz")
    data = response.json()
    
    # Should have checks dict
    assert "checks" in data
    checks = data["checks"]
    
    # Should check critical directories
    expected_dirs = ["dir_uploads", "dir_security", "dir_data"]
    for expected in expected_dirs:
        assert expected in checks or any(expected in k for k in checks.keys())


@pytest.mark.anyio
async def test_readyz_includes_database(client: AsyncClient):
    """Test readiness check includes database check."""
    response = await client.get("/readyz")
    data = response.json()
    
    # Should have database check
    assert "database" in data["checks"]


@pytest.mark.anyio
async def test_readyz_details(client: AsyncClient):
    """Test readiness check includes details."""
    response = await client.get("/readyz")
    data = response.json()
    
    # May include details
    if "details" in data:
        assert isinstance(data["details"], dict)


# =============================================================================
# Metrics Tests
# =============================================================================

@pytest.mark.anyio
async def test_metrics_prometheus(client: AsyncClient):
    """Test Prometheus metrics endpoint."""
    response = await client.get("/metrics")
    # May return 404 if disabled, or text if enabled
    assert response.status_code in [200, 404]
    
    if response.status_code == 200:
        content = response.text
        # Should be Prometheus format
        assert "semptify_" in content or "# HELP" in content or "Metrics disabled" in content


@pytest.mark.anyio
async def test_metrics_json(client: AsyncClient):
    """Test JSON metrics endpoint."""
    response = await client.get("/metrics/json")
    assert response.status_code == 200
    data = response.json()
    
    # Should have metrics data or error
    assert isinstance(data, dict)
    if "error" not in data:
        assert "app_version" in data or "uptime_seconds" in data or "requests_total" in data


@pytest.mark.anyio
async def test_metrics_contains_expected_fields(client: AsyncClient):
    """Test metrics contains expected fields."""
    response = await client.get("/metrics")
    
    if response.status_code == 200:
        content = response.text
        # Check for expected metric names if enabled
        if "semptify_" in content:
            expected_metrics = [
                "semptify_uptime_seconds",
                "semptify_requests_total",
            ]
            for metric in expected_metrics:
                assert metric in content, f"Missing metric: {metric}"


# =============================================================================
# Error Response Tests
# =============================================================================

@pytest.mark.anyio
async def test_404_error(client: AsyncClient):
    """Test 404 response for non-existent endpoint."""
    response = await client.get("/nonexistent-endpoint-xyz")
    assert response.status_code == 404


@pytest.mark.anyio
async def test_method_not_allowed(client: AsyncClient):
    """Test 405 for wrong HTTP method."""
    # POST to GET-only endpoint
    response = await client.post("/healthz", json={})
    assert response.status_code in [405, 422]


# =============================================================================
# Performance Tests
# =============================================================================

@pytest.mark.anyio
async def test_health_check_fast(client: AsyncClient):
    """Test health check responds quickly."""
    import time
    
    start = time.time()
    response = await client.get("/healthz")
    elapsed = time.time() - start
    
    assert response.status_code == 200
    assert elapsed < 1.0, f"Health check too slow: {elapsed:.2f}s"


@pytest.mark.anyio
async def test_multiple_health_checks(client: AsyncClient):
    """Test multiple health checks in succession."""
    for _ in range(5):
        response = await client.get("/healthz")
        assert response.status_code == 200
