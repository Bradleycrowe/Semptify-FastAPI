"""
Health & Metrics Router
Observability endpoints for monitoring and system dashboard.

Endpoints:
- /healthz - Basic liveness check (is the process running?)
- /livez - Kubernetes liveness probe (same as healthz)
- /readyz - Readiness check (is the app ready to serve traffic?)
- /metrics - Prometheus metrics
- /metrics/json - JSON metrics
"""

import time
import asyncio
from datetime import datetime, timezone
from pathlib import Path
import json

from fastapi import APIRouter, Depends, Request
from fastapi.responses import PlainTextResponse, JSONResponse, HTMLResponse

from app.core.config import Settings, get_settings
from app.core.security import get_metrics, incr_metric, record_request_latency


router = APIRouter()

# Track startup time for uptime calculation
_start_time = time.time()


@router.get("/healthz")
async def health_check():
    """
    Liveness probe - is the app process running?
    Returns 200 if the process is alive.
    Use for Kubernetes livenessProbe.
    """
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}


@router.get("/livez")
async def liveness_check():
    """
    Kubernetes liveness probe alias.
    Returns 200 if the process is alive.
    """
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}


@router.get("/health")
async def health_alias():
    """Alias for /healthz for compatibility."""
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}


@router.get("/readyz")
async def readiness_check(settings: Settings = Depends(get_settings)):
    """
    Readiness check - is the app ready to serve traffic?
    Checks: database connectivity, required directories, AI provider.
    Use for Kubernetes readinessProbe.
    """
    checks = {}
    details = {}
    start = time.perf_counter()

    # Check runtime directories are writable
    for dir_name in ["uploads", "uploads/vault", "logs", "security", "data"]:
        dir_path = Path(dir_name)
        exists = dir_path.exists() and dir_path.is_dir()
        
        # Test writability
        writable = False
        if exists:
            try:
                test_file = dir_path / ".write_test"
                test_file.write_text("test")
                test_file.unlink()
                writable = True
            except Exception:
                pass
        
        key = f"dir_{dir_name.replace('/', '_')}"
        checks[key] = exists and writable
        details[key] = {"exists": exists, "writable": writable}

    # Check security files loadable
    for filename in ["users.json", "admin_tokens.json"]:
        file_path = Path("security") / filename
        if file_path.exists():
            try:
                with open(file_path) as f:
                    json.load(f)
                checks[f"security_{filename.replace('.', '_')}"] = True
            except Exception as e:
                checks[f"security_{filename.replace('.', '_')}"] = False
                details[f"security_{filename.replace('.', '_')}_error"] = str(e)
        else:
            checks[f"security_{filename.replace('.', '_')}"] = "not_created"

    # Check database connectivity with timeout
    try:
        from app.core.database import get_db_session
        from sqlalchemy import text
        db_start = time.perf_counter()
        async with get_db_session() as session:
            await asyncio.wait_for(
                session.execute(text("SELECT 1")),
                timeout=5.0
            )
        checks["database"] = True
        details["database_latency_ms"] = round((time.perf_counter() - db_start) * 1000, 2)
    except asyncio.TimeoutError:
        checks["database"] = False
        details["database_error"] = "Connection timeout (5s)"
    except Exception as e:
        checks["database"] = False
        details["database_error"] = str(e)

    # Check AI provider availability
    ai_provider = settings.ai_provider
    if ai_provider and ai_provider != "none":
        checks["ai_provider"] = ai_provider
        # Check if API key is configured
        if ai_provider == "anthropic" and settings.anthropic_api_key:
            details["ai_configured"] = True
        elif ai_provider == "openai" and settings.openai_api_key:
            details["ai_configured"] = True
        elif ai_provider == "azure" and settings.azure_openai_api_key:
            details["ai_configured"] = True
        elif ai_provider == "groq" and settings.groq_api_key:
            details["ai_configured"] = True
        elif ai_provider == "ollama":
            details["ai_configured"] = True  # Ollama doesn't need API key
        else:
            details["ai_configured"] = False

    # Calculate total check time
    details["check_duration_ms"] = round((time.perf_counter() - start) * 1000, 2)
    
    # Overall status
    critical_checks = ["dir_uploads", "dir_uploads_vault", "dir_security", "database"]
    all_critical_ok = all(checks.get(k, False) is True for k in critical_checks)

    # Return 503 if not ready (for load balancer integration)
    status_code = 200 if all_critical_ok else 503
    
    return JSONResponse(
        status_code=status_code,
        content={
            "status": "ready" if all_critical_ok else "degraded",
            "checks": checks,
            "details": details,
            "uptime_seconds": round(time.time() - _start_time, 2),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    )


@router.get("/metrics", response_class=PlainTextResponse)
async def metrics(settings: Settings = Depends(get_settings)):
    """
    Prometheus-compatible metrics endpoint.
    Returns metrics in Prometheus text format or JSON.
    """
    if not settings.enable_metrics:
        return PlainTextResponse("Metrics disabled", status_code=404)

    # Get metrics from security module
    all_metrics = get_metrics()
    uptime = all_metrics.get("uptime_seconds", time.time() - _start_time)
    latency = all_metrics.get("latency", {})

    # Build Prometheus text format
    metrics_lines = [
        "# HELP semptify_uptime_seconds Time since application start",
        "# TYPE semptify_uptime_seconds gauge",
        f"semptify_uptime_seconds {uptime:.2f}",
        "",
        "# HELP semptify_info Application information",
        "# TYPE semptify_info gauge",
        f'semptify_info{{version="{settings.app_version}",security_mode="{settings.security_mode}"}} 1',
        "",
        "# HELP semptify_requests_total Total requests",
        "# TYPE semptify_requests_total counter",
        f'semptify_requests_total {all_metrics.get("requests_total", 0)}',
        "",
        "# HELP semptify_admin_requests_total Admin requests",
        "# TYPE semptify_admin_requests_total counter",
        f'semptify_admin_requests_total {all_metrics.get("admin_requests_total", 0)}',
        "",
        "# HELP semptify_errors_total Total errors",
        "# TYPE semptify_errors_total counter",
        f'semptify_errors_total {all_metrics.get("errors_total", 0)}',
        "",
        "# HELP semptify_rate_limited_total Rate limited requests",
        "# TYPE semptify_rate_limited_total counter",
        f'semptify_rate_limited_total {all_metrics.get("rate_limited_total", 0)}',
        "",
        "# HELP semptify_breakglass_used_total Breakglass tokens used",
        "# TYPE semptify_breakglass_used_total counter",
        f'semptify_breakglass_used_total {all_metrics.get("breakglass_used_total", 0)}',
        "",
        "# HELP semptify_user_registrations_total User registrations",
        "# TYPE semptify_user_registrations_total counter",
        f'semptify_user_registrations_total {all_metrics.get("user_registrations_total", 0)}',
    ]

    # Add latency metrics if available
    if latency:
        metrics_lines.extend([
            "",
            "# HELP semptify_request_latency_ms Request latency in milliseconds",
            "# TYPE semptify_request_latency_ms summary",
            f'semptify_request_latency_ms{{quantile="0.5"}} {latency.get("p50_ms", 0):.2f}',
            f'semptify_request_latency_ms{{quantile="0.95"}} {latency.get("p95_ms", 0):.2f}',
            f'semptify_request_latency_ms{{quantile="0.99"}} {latency.get("p99_ms", 0):.2f}',
        ])

    return PlainTextResponse("\n".join(metrics_lines), media_type="text/plain")


@router.get("/metrics/json")
async def metrics_json(settings: Settings = Depends(get_settings)):
    """
    JSON metrics endpoint for non-Prometheus consumers.
    """
    if not settings.enable_metrics:
        return {"error": "Metrics disabled"}

    all_metrics = get_metrics()
    all_metrics["app_version"] = settings.app_version
    all_metrics["security_mode"] = settings.security_mode

    return all_metrics


@router.get("/system-dashboard", response_class=HTMLResponse)
async def system_dashboard():
    """Visual system dashboard showing all capabilities."""
    html = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Semptify - System Dashboard</title>
    <style>
        :root {
            --primary: #4F46E5;
            --success: #10B981;
            --warning: #F59E0B;
            --danger: #EF4444;
            --bg: #0F172A;
            --card-bg: #1E293B;
            --text: #F8FAFC;
            --text-muted: #94A3B8;
        }
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: var(--bg);
            color: var(--text);
            min-height: 100vh;
            padding: 2rem;
        }
        h1 {
            text-align: center;
            font-size: 2.5rem;
            margin-bottom: 0.5rem;
            background: linear-gradient(135deg, var(--primary), #818CF8);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        .subtitle {
            text-align: center;
            color: var(--text-muted);
            margin-bottom: 2rem;
        }
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 1.5rem;
            max-width: 1400px;
            margin: 0 auto;
        }
        .card {
            background: var(--card-bg);
            border-radius: 12px;
            padding: 1.5rem;
            border: 1px solid rgba(255,255,255,0.1);
        }
        .card h2 {
            display: flex;
            align-items: center;
            gap: 0.5rem;
            margin-bottom: 1rem;
            font-size: 1.25rem;
        }
        .card h2 span { font-size: 1.5rem; }
        .endpoint-list { list-style: none; }
        .endpoint-list li {
            padding: 0.75rem;
            background: rgba(0,0,0,0.2);
            border-radius: 8px;
            margin-bottom: 0.5rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .endpoint-list .method {
            font-size: 0.7rem;
            font-weight: bold;
            padding: 0.25rem 0.5rem;
            border-radius: 4px;
            margin-right: 0.5rem;
        }
        .method-get { background: var(--success); color: white; }
        .method-post { background: var(--primary); color: white; }
        .endpoint-path {
            font-family: monospace;
            font-size: 0.85rem;
            color: #A5B4FC;
        }
        .status {
            display: inline-block;
            width: 10px;
            height: 10px;
            border-radius: 50%;
            margin-left: 0.5rem;
        }
        .status-ok { background: var(--success); }
        .status-pending { background: var(--warning); }
        .quick-links {
            display: flex;
            flex-wrap: wrap;
            gap: 0.5rem;
            margin-top: 1rem;
        }
        .quick-links a {
            padding: 0.5rem 1rem;
            background: var(--primary);
            color: white;
            text-decoration: none;
            border-radius: 6px;
            font-size: 0.85rem;
            transition: opacity 0.2s;
        }
        .quick-links a:hover { opacity: 0.8; }
        .status-banner {
            text-align: center;
            padding: 1rem;
            background: linear-gradient(135deg, rgba(16,185,129,0.2), rgba(79,70,229,0.2));
            border-radius: 12px;
            margin-bottom: 2rem;
            border: 1px solid var(--success);
        }
        .status-banner .big { font-size: 2rem; margin-bottom: 0.5rem; }
        #live-status { color: var(--success); font-weight: bold; }
        .feature-tag {
            display: inline-block;
            padding: 0.2rem 0.5rem;
            font-size: 0.7rem;
            background: rgba(79,70,229,0.3);
            border-radius: 4px;
            margin-left: 0.5rem;
        }
    </style>
</head>
<body>
    <h1>⚖️ Semptify</h1>
    <p class="subtitle">Eviction Defense Intelligence Platform</p>
    
    <div class="status-banner">
        <div class="big">✅</div>
        <div>System Status: <span id="live-status">All Systems Operational</span></div>
        <div style="color: var(--text-muted); font-size: 0.85rem; margin-top: 0.5rem;">
            Last checked: <span id="last-check">--</span>
        </div>
    </div>

    <div class="grid">
        <!-- Core System -->
        <div class="card">
            <h2><span>🏥</span> System Health</h2>
            <ul class="endpoint-list">
                <li>
                    <span><span class="method method-get">GET</span><span class="endpoint-path">/health</span></span>
                    <span class="status status-ok"></span>
                </li>
                <li>
                    <span><span class="method method-get">GET</span><span class="endpoint-path">/readyz</span></span>
                    <span class="status status-ok"></span>
                </li>
                <li>
                    <span><span class="method method-get">GET</span><span class="endpoint-path">/metrics</span></span>
                    <span class="status status-ok"></span>
                </li>
            </ul>
            <div class="quick-links">
                <a href="/health" target="_blank">Health</a>
                <a href="/readyz" target="_blank">Readiness</a>
                <a href="/api/docs" target="_blank">API Docs</a>
            </div>
        </div>

        <!-- Defense Analysis -->
        <div class="card">
            <h2><span>🛡️</span> Defense Analysis Engine</h2>
            <ul class="endpoint-list">
                <li>
                    <span><span class="method method-get">GET</span><span class="endpoint-path">/api/eviction/defenses</span></span>
                    <span class="feature-tag">AI-Powered</span>
                </li>
                <li>
                    <span><span class="method method-get">GET</span><span class="endpoint-path">/api/eviction/defense-analysis</span></span>
                    <span class="feature-tag">Smart</span>
                </li>
                <li>
                    <span><span class="method method-get">GET</span><span class="endpoint-path">/api/eviction/timeline</span></span>
                    <span class="feature-tag">45+ Events</span>
                </li>
            </ul>
            <div class="quick-links">
                <a href="/api/eviction/defenses" target="_blank">View Defenses</a>
                <a href="/api/eviction/timeline" target="_blank">Timeline</a>
            </div>
        </div>

        <!-- Document Management -->
        <div class="card">
            <h2><span>📄</span> Document Pipeline</h2>
            <ul class="endpoint-list">
                <li>
                    <span><span class="method method-get">GET</span><span class="endpoint-path">/api/documents</span></span>
                    <span class="status status-ok"></span>
                </li>
                <li>
                    <span><span class="method method-post">POST</span><span class="endpoint-path">/api/documents/upload</span></span>
                    <span class="feature-tag">OCR</span>
                </li>
                <li>
                    <span><span class="method method-get">GET</span><span class="endpoint-path">/api/documents/{id}/analysis</span></span>
                    <span class="feature-tag">AI</span>
                </li>
            </ul>
            <div class="quick-links">
                <a href="/api/documents" target="_blank">Documents</a>
            </div>
        </div>

        <!-- Court Forms -->
        <div class="card">
            <h2><span>📋</span> Court Form Generator</h2>
            <ul class="endpoint-list">
                <li>
                    <span><span class="method method-get">GET</span><span class="endpoint-path">/api/forms/library</span></span>
                    <span class="status status-ok"></span>
                </li>
                <li>
                    <span><span class="method method-get">GET</span><span class="endpoint-path">/api/autofill/answer</span></span>
                    <span class="feature-tag">Auto-Fill</span>
                </li>
                <li>
                    <span><span class="method method-post">POST</span><span class="endpoint-path">/api/generate/answer</span></span>
                    <span class="feature-tag">PDF</span>
                </li>
                <li>
                    <span><span class="method method-get">GET</span><span class="endpoint-path">/api/quick-generate/{type}</span></span>
                    <span class="feature-tag">Quick</span>
                </li>
            </ul>
            <div class="quick-links">
                <a href="/api/forms/library" target="_blank">Form Library</a>
                <a href="/api/autofill/answer" target="_blank">Auto-Fill Answer</a>
            </div>
        </div>

        <!-- Zoom Court -->
        <div class="card">
            <h2><span>🎥</span> Zoom Court Preparation</h2>
            <ul class="endpoint-list">
                <li>
                    <span><span class="method method-get">GET</span><span class="endpoint-path">/api/zoom-court/quick-tips</span></span>
                    <span class="status status-ok"></span>
                </li>
                <li>
                    <span><span class="method method-get">GET</span><span class="endpoint-path">/api/zoom-court/my-hearing-prep</span></span>
                    <span class="feature-tag">Personal</span>
                </li>
                <li>
                    <span><span class="method method-get">GET</span><span class="endpoint-path">/api/zoom-court/countdown</span></span>
                    <span class="feature-tag">Timer</span>
                </li>
                <li>
                    <span><span class="method method-get">GET</span><span class="endpoint-path">/api/zoom-court/day-of-checklist</span></span>
                    <span class="feature-tag">Checklist</span>
                </li>
            </ul>
            <div class="quick-links">
                <a href="/api/zoom-court/quick-tips" target="_blank">Quick Tips</a>
                <a href="/api/zoom-court/countdown" target="_blank">Countdown</a>
            </div>
        </div>

        <!-- AI Copilot -->
        <div class="card">
            <h2><span>🤖</span> AI Legal Copilot</h2>
            <ul class="endpoint-list">
                <li>
                    <span><span class="method method-post">POST</span><span class="endpoint-path">/api/copilot/analyze</span></span>
                    <span class="feature-tag">Azure AI</span>
                </li>
                <li>
                    <span><span class="method method-post">POST</span><span class="endpoint-path">/api/copilot/chat</span></span>
                    <span class="feature-tag">Interactive</span>
                </li>
                <li>
                    <span><span class="method method-get">GET</span><span class="endpoint-path">/api/copilot/suggestions</span></span>
                    <span class="feature-tag">Smart</span>
                </li>
            </ul>
            <div class="quick-links">
                <a href="/api/copilot/analyze?query=test" target="_blank">Test Copilot</a>
            </div>
        </div>

        <!-- Context Loop -->
        <div class="card">
            <h2><span>🔄</span> Context Intelligence</h2>
            <ul class="endpoint-list">
                <li>
                    <span><span class="method method-get">GET</span><span class="endpoint-path">/api/context/status</span></span>
                    <span class="status status-ok"></span>
                </li>
                <li>
                    <span><span class="method method-post">POST</span><span class="endpoint-path">/api/context/refresh</span></span>
                    <span class="feature-tag">Real-time</span>
                </li>
            </ul>
            <div class="quick-links">
                <a href="/api/context/status" target="_blank">Context Status</a>
            </div>
        </div>

        <!-- Storage -->
        <div class="card">
            <h2><span>☁️</span> Cloud Storage</h2>
            <ul class="endpoint-list">
                <li>
                    <span><span class="method method-get">GET</span><span class="endpoint-path">/api/storage/providers</span></span>
                    <span class="status status-ok"></span>
                </li>
                <li>
                    <span><span class="method method-post">POST</span><span class="endpoint-path">/api/storage/connect</span></span>
                    <span class="feature-tag">OAuth</span>
                </li>
            </ul>
            <div class="quick-links">
                <a href="/api/storage/providers" target="_blank">Providers</a>
            </div>
        </div>
    </div>

    <div style="text-align: center; margin-top: 2rem; color: var(--text-muted);">
        <p>📚 <a href="/api/docs" style="color: var(--primary);">Full API Documentation</a></p>
        <p style="margin-top: 0.5rem; font-size: 0.8rem;">
            Semptify v1.0 - Making Justice Accessible
        </p>
    </div>

    <script>
        // Update timestamp
        document.getElementById('last-check').textContent = new Date().toLocaleTimeString();
        
        // Live health check
        async function checkHealth() {
            try {
                const res = await fetch('/health');
                if (res.ok) {
                    document.getElementById('live-status').textContent = 'All Systems Operational';
                    document.getElementById('live-status').style.color = '#10B981';
                } else {
                    document.getElementById('live-status').textContent = 'Degraded';
                    document.getElementById('live-status').style.color = '#F59E0B';
                }
            } catch {
                document.getElementById('live-status').textContent = 'Offline';
                document.getElementById('live-status').style.color = '#EF4444';
            }
            document.getElementById('last-check').textContent = new Date().toLocaleTimeString();
        }
        
        // Check every 30 seconds
        setInterval(checkHealth, 30000);
        checkHealth();
    </script>
</body>
</html>
    """
    return HTMLResponse(content=html)


@router.get("/api-summary")
async def api_summary():
    """
    JSON summary of all API capabilities for programmatic access.
    """
    return {
        "name": "Semptify Eviction Defense Platform",
        "version": "1.0.0",
        "description": "AI-powered eviction defense intelligence system",
        "modules": {
            "defense_analysis": {
                "status": "active",
                "endpoints": [
                    {"method": "GET", "path": "/api/eviction/defenses", "description": "List applicable defenses"},
                    {"method": "GET", "path": "/api/eviction/defense-analysis", "description": "Full defense analysis"},
                    {"method": "GET", "path": "/api/eviction/timeline", "description": "Case timeline events"}
                ]
            },
            "document_pipeline": {
                "status": "active",
                "endpoints": [
                    {"method": "GET", "path": "/api/documents", "description": "List uploaded documents"},
                    {"method": "POST", "path": "/api/documents/upload", "description": "Upload document with OCR"},
                    {"method": "GET", "path": "/api/documents/{id}/analysis", "description": "Document AI analysis"}
                ]
            },
            "court_forms": {
                "status": "active",
                "endpoints": [
                    {"method": "GET", "path": "/api/forms/library", "description": "Available court forms"},
                    {"method": "GET", "path": "/api/autofill/answer", "description": "Auto-fill Answer form"},
                    {"method": "POST", "path": "/api/generate/answer", "description": "Generate Answer PDF"},
                    {"method": "GET", "path": "/api/quick-generate/{type}", "description": "Quick form generation"}
                ]
            },
            "zoom_court": {
                "status": "active",
                "endpoints": [
                    {"method": "GET", "path": "/api/zoom-court/quick-tips", "description": "Zoom hearing tips"},
                    {"method": "GET", "path": "/api/zoom-court/my-hearing-prep", "description": "Personalized prep"},
                    {"method": "GET", "path": "/api/zoom-court/countdown", "description": "Hearing countdown"},
                    {"method": "GET", "path": "/api/zoom-court/day-of-checklist", "description": "Day-of checklist"}
                ]
            },
            "ai_copilot": {
                "status": "active",
                "endpoints": [
                    {"method": "POST", "path": "/api/copilot/analyze", "description": "AI document analysis"},
                    {"method": "POST", "path": "/api/copilot/chat", "description": "Interactive legal chat"},
                    {"method": "GET", "path": "/api/copilot/suggestions", "description": "Smart suggestions"}
                ]
            },
            "context_loop": {
                "status": "active",
                "endpoints": [
                    {"method": "GET", "path": "/api/context/status", "description": "Context state"},
                    {"method": "POST", "path": "/api/context/refresh", "description": "Refresh context"}
                ]
            },
            "storage": {
                "status": "active",
                "endpoints": [
                    {"method": "GET", "path": "/api/storage/providers", "description": "Available providers"},
                    {"method": "POST", "path": "/api/storage/connect", "description": "Connect storage"}
                ]
            }
        },
        "documentation": {
            "swagger_ui": "/api/docs",
            "openapi": "/api/openapi.json",
            "tenant_dashboard": "/dashboard",
            "system_dashboard": "/system-dashboard"
        },
        "timestamp": datetime.now(timezone.utc).isoformat()
    }