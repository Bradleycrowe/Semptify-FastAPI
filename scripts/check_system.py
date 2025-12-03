#!/usr/bin/env python3
"""Quick system validation using stdlib only."""

import json
import sys
from pathlib import Path
from urllib.request import urlopen
from urllib.error import HTTPError

BASE = "http://localhost:8000"
results = []

def check(name, path):
    try:
        with urlopen(f"{BASE}{path}", timeout=5) as r:
            if r.status == 200:
                print(f"✅ {path} - {name}")
                results.append(True)
            else:
                print(f"❌ {path} - {name} ({r.status})")
                results.append(False)
    except HTTPError as e:
        print(f"❌ {path} - {name} ({e.code})")
        results.append(False)
    except Exception as e:
        print(f"❌ {path} - {name} ({e})")
        results.append(False)

print("=" * 60)
print("SEMPTIFY QUICK VALIDATION")
print("=" * 60)

print("\n📄 Pages:")
check("Home", "/")
check("Documents", "/documents")
check("Timeline", "/timeline")
check("Eviction Defense", "/eviction-defense")

print("\n⚖️ Eviction Flows:")
check("Eviction Home", "/eviction/")
check("Answer Flow", "/eviction/answer")
check("Counterclaim", "/eviction/counterclaim")
check("Motions", "/eviction/motions")
check("Hearing Prep", "/eviction/hearing")
check("Zoom Helper", "/eviction/zoom")
check("Forms Library", "/eviction/forms/library")

print("\n🔌 APIs:")
check("Documents API", "/api/documents/")
check("Timeline API", "/api/timeline/")
check("Defenses", "/api/eviction-defense/defenses")
check("Motions", "/api/eviction-defense/motions")
check("Counterclaims", "/api/eviction-defense/counterclaims")
check("Forms", "/api/eviction-defense/forms")
check("Laws", "/api/documents/laws/")
check("Calendar", "/api/calendar/")

print("\n☁️ Storage:")
check("Status", "/storage/status")
check("Providers", "/storage/providers")
check("Session", "/storage/session")

print("\n💚 Health:")
check("Health", "/health")

print("\n📁 Static:")
check("Welcome", "/static/welcome.html")
check("Dashboard", "/static/dashboard.html")
check("Timeline HTML", "/static/timeline.html")

print("\n" + "=" * 60)
passed = sum(results)
total = len(results)
print(f"RESULTS: {passed}/{total} passed")
print("=" * 60)

if passed == total:
    print("\n🎉 ALL SYSTEMS GO!")
else:
    print(f"\n⚠️ {total - passed} tests failed")
