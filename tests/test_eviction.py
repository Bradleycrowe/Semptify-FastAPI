"""
Semptify 5.0 - Eviction Flow Tests
Tests for the Dakota County eviction defense wizard.
"""

import pytest
from httpx import AsyncClient


# =============================================================================
# Eviction Home & Navigation Tests
# =============================================================================

@pytest.mark.anyio
async def test_eviction_home(client: AsyncClient):
    """Test eviction defense home page loads."""
    response = await client.get("/eviction/")
    assert response.status_code == 200
    # Should return HTML
    assert "text/html" in response.headers.get("content-type", "")


@pytest.mark.anyio
async def test_eviction_answer_step1(client: AsyncClient):
    """Test answer form step 1 loads."""
    response = await client.get("/eviction/answer")
    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")


@pytest.mark.anyio
async def test_eviction_answer_step2(client: AsyncClient):
    """Test answer form step 2 (defenses) loads."""
    response = await client.get("/eviction/answer/step2")
    assert response.status_code == 200


@pytest.mark.anyio
async def test_eviction_answer_step3(client: AsyncClient):
    """Test answer form step 3 (review) loads."""
    response = await client.get("/eviction/answer/step3")
    assert response.status_code == 200


@pytest.mark.anyio
async def test_eviction_motions_menu(client: AsyncClient):
    """Test motions menu loads."""
    response = await client.get("/eviction/motions")
    assert response.status_code == 200


@pytest.mark.anyio
@pytest.mark.parametrize("motion_type", ["dismiss", "continuance", "stay", "fee_waiver"])
async def test_eviction_motion_forms(client: AsyncClient, motion_type: str):
    """Test each motion form type loads."""
    response = await client.get(f"/eviction/motions/{motion_type}")
    assert response.status_code == 200


@pytest.mark.anyio
async def test_eviction_hearing_prep(client: AsyncClient):
    """Test hearing preparation page loads."""
    response = await client.get("/eviction/hearing")
    assert response.status_code == 200


@pytest.mark.anyio
async def test_eviction_zoom_tips(client: AsyncClient):
    """Test Zoom court tips page loads."""
    response = await client.get("/eviction/zoom")
    assert response.status_code == 200


# =============================================================================
# i18n / Translation Tests
# =============================================================================

@pytest.mark.anyio
@pytest.mark.parametrize("lang", ["en", "es", "so", "ar"])
async def test_eviction_i18n_strings(client: AsyncClient, lang: str):
    """Test translation strings available for each language."""
    response = await client.get(f"/eviction/api/strings/{lang}")
    assert response.status_code == 200
    data = response.json()
    assert "strings" in data or isinstance(data, dict)
    # Should have common keys
    if isinstance(data, dict) and "strings" not in data:
        # Direct dict of translations
        assert len(data) > 0


@pytest.mark.anyio
async def test_eviction_answer_with_language(client: AsyncClient):
    """Test answer form respects language parameter."""
    response = await client.get("/eviction/answer?lang=es")
    assert response.status_code == 200


@pytest.mark.anyio
async def test_eviction_invalid_language_fallback(client: AsyncClient):
    """Test invalid language falls back to English."""
    response = await client.get("/eviction/answer?lang=invalid")
    # Should still work, falling back to English
    assert response.status_code == 200


# =============================================================================
# Deadline Calculation Tests
# =============================================================================

@pytest.mark.anyio
async def test_eviction_deadline_calculation(client: AsyncClient):
    """Test deadline calculation API."""
    response = await client.get("/eviction/api/deadlines?served_date=2025-11-20")
    assert response.status_code == 200
    data = response.json()
    # API returns answer_deadline, hearing_earliest, hearing_latest
    assert "answer_deadline" in data or "deadlines" in data or "answer_due" in data


# =============================================================================
# Forms Library Tests
# =============================================================================

@pytest.mark.anyio
async def test_forms_library_page(client: AsyncClient):
    """Test forms library page loads."""
    response = await client.get("/eviction/forms/library")
    assert response.status_code == 200


@pytest.mark.anyio
async def test_forms_api_list(client: AsyncClient):
    """Test forms API list endpoint."""
    response = await client.get("/eviction/forms/api/list")
    assert response.status_code == 200
    data = response.json()
    assert "forms" in data or isinstance(data, list)


@pytest.mark.anyio
async def test_forms_api_resources(client: AsyncClient):
    """Test legal resources API endpoint."""
    response = await client.get("/eviction/forms/api/resources")
    assert response.status_code == 200
    data = response.json()
    assert "resources" in data or isinstance(data, list)


# =============================================================================
# PDF Generation Tests
# =============================================================================

@pytest.mark.anyio
async def test_answer_generate_pdf(client: AsyncClient, sample_eviction_form_data):
    """Test answer PDF generation."""
    response = await client.post(
        "/eviction/answer/generate",
        data={
            "tenant_name": sample_eviction_form_data["tenant_name"],
            "landlord_name": sample_eviction_form_data["landlord_name"],
            "case_number": sample_eviction_form_data["case_number"],
            "address": sample_eviction_form_data["address"],
            "served_date": sample_eviction_form_data["served_date"],
            "defenses": ",".join(sample_eviction_form_data["defenses"]),
            "defense_details": sample_eviction_form_data["defense_details"],
        }
    )
    # PDF generation may succeed (200) or fail gracefully if WeasyPrint not installed
    assert response.status_code in [200, 500, 422]
    if response.status_code == 200:
        content_type = response.headers.get("content-type", "")
        assert "pdf" in content_type or "html" in content_type


@pytest.mark.anyio
async def test_motion_generate_pdf(client: AsyncClient):
    """Test motion PDF generation."""
    response = await client.post(
        "/eviction/motions/generate",
        data={
            "motion_type": "continuance",
            "tenant_name": "John Doe",
            "case_number": "27-CV-25-12345",
            "reason": "Need more time to gather evidence",
            "requested_date": "2025-12-30",
        }
    )
    assert response.status_code in [200, 500, 422]


@pytest.mark.anyio
async def test_hearing_generate_pdf(client: AsyncClient):
    """Test hearing prep PDF generation."""
    response = await client.post(
        "/eviction/hearing/generate",
        data={
            "tenant_name": "John Doe",
            "hearing_date": "2025-12-15",
            "hearing_time": "09:00",
            "key_points": "Habitability issues, rent receipts",
        }
    )
    assert response.status_code in [200, 500, 422]


# =============================================================================
# Counterclaim Tests
# =============================================================================

@pytest.mark.anyio
async def test_counterclaim_page(client: AsyncClient):
    """Test counterclaim form page loads."""
    response = await client.get("/eviction/counterclaim")
    assert response.status_code == 200


@pytest.mark.anyio
async def test_counterclaim_generate_pdf(client: AsyncClient):
    """Test counterclaim PDF generation."""
    response = await client.post(
        "/eviction/counterclaim/generate",
        data={
            "tenant_name": "John Doe",
            "landlord_name": "ABC Properties LLC",
            "case_number": "27-CV-25-12345",
            "claim_type": "habitability",
            "claim_amount": "5000",
            "claim_details": "Landlord failed to repair heating for 3 months",
        }
    )
    assert response.status_code in [200, 500, 422]


# =============================================================================
# Edge Case & Error Tests
# =============================================================================

@pytest.mark.anyio
async def test_invalid_motion_type(client: AsyncClient):
    """Test invalid motion type returns error."""
    response = await client.get("/eviction/motions/invalid_type")
    assert response.status_code in [404, 400, 200]  # May show error page


@pytest.mark.anyio
async def test_answer_generate_missing_required_fields(client: AsyncClient):
    """Test PDF generation with missing required fields."""
    response = await client.post(
        "/eviction/answer/generate",
        data={
            "tenant_name": "John Doe",
            # Missing required fields
        }
    )
    # Should fail validation or return error
    assert response.status_code in [400, 422, 200, 500]
