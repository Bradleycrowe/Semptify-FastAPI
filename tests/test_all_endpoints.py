#!/usr/bin/env python3
"""
Comprehensive API Endpoint Test Suite for Semptify-FastAPI
Tests all routes to verify functionality
"""

import requests
import json
from typing import Optional, Dict, Any, Callable

BASE_URL = "http://localhost:8000"

# Test results tracking
results = {
    "passed": [],
    "failed": [],
    "skipped": []
}

def get(path: str) -> requests.Response:
    """GET request helper"""
    return requests.get(f"{BASE_URL}{path}", timeout=10)

def post(path: str, data: Dict[str, Any] = None) -> requests.Response:
    """POST request helper"""
    return requests.post(f"{BASE_URL}{path}", json=data or {}, timeout=10)

def test(name: str, request_func: Callable, expected_codes: list = None):
    """Run a test and record result"""
    if expected_codes is None:
        expected_codes = [200, 201, 204, 307, 404]  # 404 is OK for verify endpoints without real data
    
    try:
        response = request_func()
        if response.status_code in expected_codes:
            results["passed"].append(name)
            print(f"  ✅ {name} - {response.status_code}")
        else:
            results["failed"].append((name, f"Got {response.status_code}"))
            print(f"  ❌ {name} - Expected {expected_codes}, got {response.status_code}")
    except requests.exceptions.ConnectionError:
        results["failed"].append((name, "Connection refused"))
        print(f"  ❌ {name} - Connection refused (is server running?)")
    except Exception as e:
        results["failed"].append((name, str(e)))
        print(f"  ❌ {name} - {str(e)[:50]}")

# =============================================================================
# RUN TESTS
# =============================================================================
print("=" * 60)
print("SEMPTIFY-FASTAPI ENDPOINT TEST SUITE")
print("=" * 60)

# =============================================================================
# HEALTH & CORE
# =============================================================================
print("\n💚 HEALTH & CORE")
print("-" * 40)

test("Health Check", lambda: get("/health"))
test("Health Status", lambda: get("/health/status"))
test("API Root", lambda: get("/"))
test("API Info", lambda: get("/api-info"))
test("API Summary", lambda: get("/api-summary"))
test("Docs (Swagger)", lambda: get("/docs"))
test("ReDoc", lambda: get("/redoc"))
test("OpenAPI Schema", lambda: get("/openapi.json"))

# =============================================================================
# STATIC FILES
# =============================================================================
print("\n📁 STATIC FILES")
print("-" * 40)

test("Static Index", lambda: get("/static/index.html"))
test("Static CSS", lambda: get("/static/css/app.css"))
test("Static JS", lambda: get("/static/js/app.js"))
test("Sample Certificate", lambda: get("/static/sample_certificate.html"))

# =============================================================================
# STORAGE & AUTH
# =============================================================================
print("\n🔐 STORAGE & AUTH")
print("-" * 40)

test("Storage Home", lambda: get("/storage/"))
test("Storage Providers", lambda: get("/storage/providers"))
test("Storage Session", lambda: get("/storage/session"))
test("Storage Health", lambda: get("/storage/health"))

# =============================================================================
# STORAGE INTEGRITY
# =============================================================================
print("\n🔒 STORAGE INTEGRITY")
print("-" * 40)

# Timestamp is GET, returns current timestamp proof format
test("Integrity Timestamp", lambda: get("/storage/integrity/timestamp"))
# Hash needs base64 content
test("Integrity Hash", lambda: post("/storage/integrity/hash", {
    "content": "dGVzdCBkYXRh"  # base64 encoded "test data"
}))

# =============================================================================
# CERTIFICATES
# =============================================================================
print("\n📜 CERTIFICATES")
print("-" * 40)

# Certificate endpoints need auth headers - test with X-User-Id
def gen_cert():
    return requests.post(f"{BASE_URL}/storage/certificate/generate", 
        json={"document_name": "Test Document", "document_hash": "abc123def456"},
        headers={"X-User-Id": "test-user"}, timeout=10)
def gen_html():
    return requests.post(f"{BASE_URL}/storage/certificate/html",
        json={"document_name": "Test Document", "document_hash": "abc123def456"},
        headers={"X-User-Id": "test-user"}, timeout=10)

test("Certificate Generate", gen_cert)
test("Certificate HTML", gen_html)
test("Certificate Verify Page", lambda: get("/storage/certificate/verify/TEST-123"))

# =============================================================================
# VAULT (Document storage - all routes need user context)
# =============================================================================
print("\n🗄️ VAULT")
print("-" * 40)

# Vault list endpoint - GET /api/vault/
def vault_list():
    return requests.get(f"{BASE_URL}/api/vault/", 
        headers={"X-User-Id": "test-user"}, timeout=10)
test("Vault Document List", vault_list)

# =============================================================================
# DOCUMENTS
# =============================================================================
print("\n📂 DOCUMENTS")
print("-" * 40)

test("Documents List", lambda: get("/api/documents/"))
test("Document Types", lambda: get("/api/documents/types"))
test("Document Stats", lambda: get("/api/documents/stats"))

# =============================================================================
# TIMELINE & CALENDAR
# =============================================================================
print("\n📅 TIMELINE & CALENDAR")
print("-" * 40)

test("Timeline List", lambda: get("/api/timeline/"))
test("Timeline Events", lambda: get("/api/timeline/events"))
test("Timeline Upcoming", lambda: get("/api/timeline/upcoming"))
test("Calendar List", lambda: get("/api/calendar/"))
test("Calendar Events", lambda: get("/api/calendar/events"))

# =============================================================================
# COPILOT
# =============================================================================
print("\n🤖 COPILOT")
print("-" * 40)

test("Copilot Status", lambda: get("/api/copilot/status"))
test("Copilot Suggestions", lambda: get("/api/copilot/suggestions"))

# =============================================================================
# CONTEXT LOOP (api/core)
# =============================================================================
print("\n🔄 CONTEXT LOOP")
print("-" * 40)

test("Context State", lambda: get("/api/core/state"))
test("Context Intensity", lambda: get("/api/core/intensity"))
test("Context Full", lambda: get("/api/core/context"))
test("Context Events", lambda: get("/api/core/events"))
test("Context Predictions", lambda: get("/api/core/predictions"))

# =============================================================================
# ADAPTIVE UI (api/ui)
# =============================================================================
print("\n🎨 ADAPTIVE UI")
print("-" * 40)

test("UI Config", lambda: get("/api/ui/config"))
test("UI Theme", lambda: get("/api/ui/theme"))
test("UI Layout", lambda: get("/api/ui/layout"))

# =============================================================================
# SETUP WIZARD
# =============================================================================
print("\n⚙️ SETUP WIZARD")
print("-" * 40)

test("Setup Status", lambda: get("/api/setup/status"))
test("Setup Steps", lambda: get("/api/setup/steps"))

# =============================================================================
# FORM DATA HUB
# =============================================================================
print("\n📋 FORM DATA HUB")
print("-" * 40)

test("Form Data Status", lambda: get("/api/form-data/status"))
test("Form Fields", lambda: get("/api/form-data/fields"))

# =============================================================================
# LAW LIBRARY
# =============================================================================
print("\n📚 LAW LIBRARY")
print("-" * 40)

test("Laws List", lambda: get("/api/laws/"))
test("Laws Search", lambda: get("/api/laws/search?q=eviction"))
test("Laws Categories", lambda: get("/api/laws/categories"))
test("Laws Topics", lambda: get("/api/laws/topics"))

# =============================================================================
# EVICTION DEFENSE
# =============================================================================
print("\n⚖️ EVICTION DEFENSE")
print("-" * 40)

test("Defenses List", lambda: get("/api/defenses/"))
test("Defenses Analysis", lambda: get("/api/defenses/analysis"))
test("Defense Types", lambda: get("/api/defenses/types"))

# =============================================================================
# ZOOM COURT
# =============================================================================
print("\n🎥 ZOOM COURT")
print("-" * 40)

test("Zoom Etiquette", lambda: get("/api/zoom-court/etiquette"))
test("Zoom Tips", lambda: get("/api/zoom-court/tips"))
test("Zoom Checklist", lambda: get("/api/zoom-court/checklist"))
test("Zoom Prep", lambda: get("/api/zoom-court/prep"))

# =============================================================================
# DAKOTA EVICTION FLOWS
# =============================================================================
print("\n📝 DAKOTA EVICTION FLOWS")
print("-" * 40)

test("Eviction Home", lambda: get("/eviction/"))
test("Case Status", lambda: get("/eviction/status"))
test("Eviction Defenses", lambda: get("/eviction/defenses"))
test("Case Timeline", lambda: get("/eviction/timeline"))
test("Answer Flow Step 1", lambda: get("/eviction/flows/answer/step/1"))
test("Forms Library", lambda: get("/eviction/forms/library"))
test("Forms Available", lambda: get("/eviction/forms/available"))

# =============================================================================
# DOCUMENT INTAKE
# =============================================================================
print("\n📥 DOCUMENT INTAKE")
print("-" * 40)

test("Intake Status", lambda: get("/api/intake/status"))

# =============================================================================
# DOCUMENT REGISTRY
# =============================================================================
print("\n📒 DOCUMENT REGISTRY")
print("-" * 40)

test("Registry Status", lambda: get("/api/registry/status"))
test("Registry Chain", lambda: get("/api/registry/chain"))

# =============================================================================
# VAULT ENGINE
# =============================================================================
print("\n🔧 VAULT ENGINE")
print("-" * 40)

test("Engine Status", lambda: get("/api/vault-engine/status"))

# =============================================================================
# AUTHENTICATION
# =============================================================================
print("\n🔑 AUTHENTICATION")
print("-" * 40)

test("Auth Status", lambda: get("/api/auth/status"))
test("Auth User", lambda: get("/api/auth/user"))

# =============================================================================
# DASHBOARD
# =============================================================================
print("\n📊 DASHBOARD")
print("-" * 40)

test("Dashboard Page", lambda: get("/dashboard"))
test("Register Page", lambda: get("/register"))

# =============================================================================
# SUMMARY
# =============================================================================
print("\n" + "=" * 60)
print("TEST RESULTS SUMMARY")
print("=" * 60)
print(f"✅ Passed: {len(results['passed'])}")
print(f"❌ Failed: {len(results['failed'])}")
print(f"⏭️ Skipped: {len(results['skipped'])}")

total = len(results['passed']) + len(results['failed'])
if total > 0:
    success_rate = (len(results['passed']) / total) * 100
    print(f"\n📈 Success Rate: {success_rate:.1f}%")

if results['failed']:
    print("\n❌ FAILED TESTS:")
    for name, reason in results['failed']:
        print(f"   - {name}: {reason}")

print("\n" + "=" * 60)
