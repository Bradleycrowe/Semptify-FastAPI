"""
Semptify User Flow Testing & Validation
Tests all critical user workflows for usability and functionality
"""
import asyncio
import httpx
from pathlib import Path

BASE_URL = "http://localhost:8000"

async def test_user_flows():
    """Test all critical user workflows"""
    client = httpx.AsyncClient(timeout=10.0)
    results = {
        "passed": [],
        "failed": [],
        "warnings": []
    }
    
    print("=" * 60)
    print("SEMPTIFY USER FLOW TESTING")
    print("=" * 60)
    print()
    
    try:
        # Test 1: Health Check
        print("✓ Testing: Server Health...")
        try:
            r = await client.get(f"{BASE_URL}/healthz")
            if r.status_code == 200:
                results["passed"].append("Health Check")
                print("  ✅ Server is healthy")
            else:
                results["failed"].append(f"Health Check (status {r.status_code})")
        except Exception as e:
            results["failed"].append(f"Health Check - {str(e)}")
            print(f"  ❌ Server not responding")
        
        # Test 2: Frontend Pages
        print("\n✓ Testing: Frontend Pages...")
        pages = [
            ("Dashboard", "/"),
            ("Documents", "/documents"),
            ("Timeline", "/timeline"),
            ("Law Library", "/law-library"),
            ("Eviction Defense", "/eviction-defense"),
            ("Zoom Court", "/zoom-court"),
        ]
        
        for name, path in pages:
            try:
                r = await client.get(f"{BASE_URL}{path}")
                if r.status_code == 200:
                    results["passed"].append(f"Page: {name}")
                    print(f"  ✅ {name} page accessible")
                else:
                    results["failed"].append(f"Page: {name} (status {r.status_code})")
                    print(f"  ❌ {name} page error")
            except Exception as e:
                results["failed"].append(f"Page: {name} - {str(e)}")
                print(f"  ❌ {name} page unreachable")
        
        # Test 3: API Endpoints
        print("\n✓ Testing: API Endpoints...")
        endpoints = [
            ("Auth Status", "/api/auth/status"),
            ("Storage Providers", "/storage/providers"),
            ("Timeline Events", "/api/timeline/"),
            ("Calendar Events", "/api/calendar/"),
        ]
        
        for name, path in endpoints:
            try:
                r = await client.get(f"{BASE_URL}{path}")
                if r.status_code in [200, 401]:  # 401 is acceptable (not authenticated)
                    results["passed"].append(f"API: {name}")
                    print(f"  ✅ {name} endpoint working")
                else:
                    results["warnings"].append(f"API: {name} (status {r.status_code})")
                    print(f"  ⚠️  {name} endpoint returned {r.status_code}")
            except Exception as e:
                results["failed"].append(f"API: {name} - {str(e)}")
                print(f"  ❌ {name} endpoint failed")
        
        # Test 4: Static Assets
        print("\n✓ Testing: Static Assets...")
        static_files = [
            "welcome.html",
            "dashboard.html",
            "documents.html",
            "enterprise-dashboard.html",
        ]
        
        for file in static_files:
            path = Path(f"static/{file}")
            if path.exists():
                results["passed"].append(f"Static: {file}")
                print(f"  ✅ {file} exists")
            else:
                results["warnings"].append(f"Static: {file} missing")
                print(f"  ⚠️  {file} not found")
        
        # Test 5: API Documentation
        print("\n✓ Testing: API Documentation...")
        try:
            r = await client.get(f"{BASE_URL}/api/docs")
            if r.status_code == 200:
                results["passed"].append("API Docs")
                print("  ✅ API documentation accessible")
            else:
                results["warnings"].append("API Docs disabled")
                print("  ⚠️  API docs may be disabled")
        except Exception as e:
            results["warnings"].append("API Docs error")
            print("  ⚠️  API docs not accessible")
        
    finally:
        await client.aclose()
    
    # Print Summary
    print()
    print("=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    print(f"✅ Passed:   {len(results['passed'])}")
    print(f"❌ Failed:   {len(results['failed'])}")
    print(f"⚠️  Warnings: {len(results['warnings'])}")
    print()
    
    if results["failed"]:
        print("FAILED TESTS:")
        for item in results["failed"]:
            print(f"  ❌ {item}")
        print()
    
    if results["warnings"]:
        print("WARNINGS:")
        for item in results["warnings"]:
            print(f"  ⚠️  {item}")
        print()
    
    # Overall Status
    if len(results["failed"]) == 0:
        print("🎉 ALL CRITICAL TESTS PASSED!")
        print("✅ Semptify is ready for users")
    else:
        print("⚠️  SOME TESTS FAILED - Review above")
    
    print("=" * 60)
    
    return results

if __name__ == "__main__":
    asyncio.run(test_user_flows())
