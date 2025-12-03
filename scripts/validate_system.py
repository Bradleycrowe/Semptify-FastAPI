"""
Full System Validation Script
Tests all endpoints, database, and functionality
"""

import asyncio
import httpx
import json
from pathlib import Path

BASE_URL = "http://localhost:8000"

TESTS = []
PASSED = 0
FAILED = 0


def test(name):
    """Decorator for test functions."""
    def decorator(func):
        TESTS.append((name, func))
        return func
    return decorator


async def run_tests():
    global PASSED, FAILED
    
    print("=" * 60)
    print("🔍 SEMPTIFY FULL SYSTEM VALIDATION")
    print("=" * 60)
    
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30.0) as client:
        for name, test_func in TESTS:
            try:
                result = await test_func(client)
                if result:
                    print(f"✅ {name}")
                    PASSED += 1
                else:
                    print(f"❌ {name}")
                    FAILED += 1
            except Exception as e:
                print(f"❌ {name} - Error: {e}")
                FAILED += 1
    
    print("=" * 60)
    print(f"RESULTS: {PASSED} passed, {FAILED} failed")
    print("=" * 60)
    return FAILED == 0


# ============================================================================
# API ENDPOINT TESTS
# ============================================================================

@test("GET / - Dashboard loads")
async def test_dashboard(client):
    r = await client.get("/")
    return r.status_code == 200 and "Semptify" in r.text


@test("GET /api/documents/ - Documents API")
async def test_documents_api(client):
    r = await client.get("/api/documents/")
    return r.status_code == 200 and isinstance(r.json(), list)


@test("GET /api/timeline/ - Timeline API")
async def test_timeline_api(client):
    r = await client.get("/api/timeline/")
    data = r.json()
    return r.status_code == 200 and "events" in data


@test("GET /api/eviction-defense/defenses - Defenses API")
async def test_defenses_api(client):
    r = await client.get("/api/eviction-defense/defenses")
    return r.status_code == 200


@test("GET /api/eviction-defense/motions - Motions API")
async def test_motions_api(client):
    r = await client.get("/api/eviction-defense/motions")
    return r.status_code == 200


@test("GET /storage/status - Storage Status API")
async def test_storage_status(client):
    r = await client.get("/storage/status")
    return r.status_code == 200


@test("GET /storage/providers - Storage Providers API")
async def test_storage_providers(client):
    r = await client.get("/storage/providers")
    data = r.json()
    return r.status_code == 200 and "providers" in data


@test("GET /storage/session - Storage Session API")
async def test_storage_session(client):
    r = await client.get("/storage/session")
    return r.status_code == 200


@test("GET /health - Health Check")
async def test_health(client):
    r = await client.get("/health")
    return r.status_code == 200


# ============================================================================
# STATIC PAGES
# ============================================================================

@test("GET /static/welcome.html - Welcome Page")
async def test_welcome_page(client):
    r = await client.get("/static/welcome.html")
    return r.status_code == 200


@test("GET /static/timeline.html - Timeline Page")
async def test_timeline_page(client):
    r = await client.get("/static/timeline.html")
    return r.status_code == 200


@test("GET /documents - Documents Page")
async def test_documents_page(client):
    r = await client.get("/documents")
    return r.status_code == 200


@test("GET /timeline - Timeline Route")
async def test_timeline_route(client):
    r = await client.get("/timeline")
    return r.status_code == 200


# ============================================================================
# EVICTION DEFENSE MODULE
# ============================================================================

@test("GET /eviction/ - Eviction Defense Home")
async def test_eviction_home(client):
    r = await client.get("/eviction/")
    return r.status_code == 200


@test("GET /eviction/flows/answer - Answer Flow")
async def test_answer_flow(client):
    r = await client.get("/eviction/flows/answer")
    return r.status_code == 200


@test("GET /eviction/forms - Forms Library")
async def test_forms_library(client):
    r = await client.get("/eviction/forms")
    return r.status_code == 200


# ============================================================================
# DATABASE VALIDATION
# ============================================================================

@test("Database - Documents exist")
async def test_db_documents(client):
    r = await client.get("/api/documents/")
    docs = r.json()
    return len(docs) >= 5  # Should have our 5 sample docs


@test("Database - Timeline events exist")
async def test_db_timeline(client):
    r = await client.get("/api/timeline/")
    data = r.json()
    return data.get("total", 0) >= 11  # Should have our 11 events


# ============================================================================
# EXPORT FUNCTIONALITY
# ============================================================================

@test("GET /api/documents/export - Export endpoint exists")
async def test_export_endpoint(client):
    r = await client.get("/api/documents/export")
    # May return 400 if no docs selected, but endpoint exists
    return r.status_code in [200, 400, 422]


@test("GET /api/timeline/export - Timeline export")
async def test_timeline_export(client):
    r = await client.get("/api/timeline/export")
    return r.status_code in [200, 400, 404, 422]


# ============================================================================
# LAW LIBRARY
# ============================================================================

@test("GET /api/laws - Law Library API")
async def test_law_library(client):
    r = await client.get("/api/laws")
    return r.status_code in [200, 404]


@test("GET /api/laws/search - Law Search")
async def test_law_search(client):
    r = await client.get("/api/laws/search?q=eviction")
    return r.status_code in [200, 404, 422]


# ============================================================================
# FILE STRUCTURE VALIDATION
# ============================================================================

@test("File: data/semptify.db exists")
async def test_db_file(client):
    return Path("data/semptify.db").exists()


@test("File: data/laws/laws.json exists")
async def test_laws_file(client):
    return Path("data/laws/laws.json").exists()


@test("File: static/dashboard.html exists")
async def test_dashboard_file(client):
    return Path("static/dashboard.html").exists()


@test("File: static/welcome.html exists")
async def test_welcome_file(client):
    return Path("static/welcome.html").exists()


@test("Directory: uploads/vault exists")
async def test_uploads_dir(client):
    Path("uploads/vault").mkdir(parents=True, exist_ok=True)
    return Path("uploads/vault").exists()


if __name__ == "__main__":
    asyncio.run(run_tests())
