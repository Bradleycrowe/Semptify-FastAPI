"""
Semptify - FastAPI Application
Tenant rights protection platform.

Core Promise: Help tenants with tools and information to uphold tenant rights,
in court if it goes that far - hopefully it won't.
"""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, Cookie
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, HTMLResponse, RedirectResponse

from app.core.config import get_settings
from app.core.database import init_db, close_db

# Import routers
from app.routers import auth, vault, timeline, calendar, copilot, health, storage, documents, adaptive_ui, context_loop 
from app.routers.intake import router as intake_router
from app.routers.registry import router as registry_router
from app.routers.vault_engine import router as vault_engine_router
from app.routers.law_library import router as law_library_router
from app.routers.eviction_defense import router as eviction_defense_router
from app.routers.zoom_court import router as zoom_court_router
from app.routers.form_data import router as form_data_router
from app.routers.setup import router as setup_router
from app.routers.websocket import router as websocket_router

# Dakota County Eviction Defense Module
try:
    from app.routers.eviction import (
        flows_router as dakota_flows,
        forms_router as dakota_forms,
        case_router as dakota_case,
        learning_router as dakota_learning,
        procedures_router as dakota_procedures,
    )
    DAKOTA_AVAILABLE = True
except ImportError as e:
    logging.getLogger(__name__).warning(f"Dakota County module import failed: {e}")
    DAKOTA_AVAILABLE = False


# =============================================================================
# Logging Setup
# =============================================================================

def setup_logging():
    """Configure logging based on settings."""
    settings = get_settings()
    log_format = (
        '{"time": "%(asctime)s", "level": "%(levelname)s", "message": "%(message)s"}'
        if settings.log_json_format
        else "%(asctime)s - %(levelname)s - %(message)s"
    )
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper()),
        format=log_format,
    )


# =============================================================================
# Lifespan (Startup/Shutdown)
# =============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan handler.
    - Startup: Initialize database, create directories
    - Shutdown: Close database connections
    """
    settings = get_settings()
    logger = logging.getLogger(__name__)
    
    # --- STARTUP ---
    logger.info(f"Starting {settings.app_name} v{settings.app_version}")
    logger.info(f"Security mode: {settings.security_mode}")
    
    # Create runtime directories
    runtime_dirs = [
        "uploads",
        "uploads/vault",
        "logs",
        "security",
        "data",
    ]
    for dir_path in runtime_dirs:
        Path(dir_path).mkdir(parents=True, exist_ok=True)
        logger.debug(f"Ensured directory: {dir_path}")
    
    # Initialize database
    await init_db()
    logger.info("Database initialized")
    
    yield  # Application runs here
    
    # --- SHUTDOWN ---
    logger.info("Shutting down...")
    await close_db()
    logger.info("Database connections closed")


# =============================================================================
# HTML Page Generators for Legal Tools
# =============================================================================

def generate_law_library_html() -> str:
    """Generate law library HTML page."""
    return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Law Library - Semptify</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #064e3b 0%, #065f46 100%);
            color: #fff;
            min-height: 100vh;
        }
        .header {
            background: rgba(0,0,0,0.2);
            padding: 1rem 2rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .logo { font-size: 1.5rem; font-weight: 700; }
        .nav-links { display: flex; gap: 1rem; }
        .nav-links a {
            color: #a7f3d0;
            text-decoration: none;
            padding: 0.5rem 1rem;
            border-radius: 8px;
            transition: all 0.2s;
        }
        .nav-links a:hover { background: rgba(255,255,255,0.1); }
        .container { max-width: 1200px; margin: 0 auto; padding: 2rem; }
        .page-title { font-size: 2.5rem; font-weight: 700; margin-bottom: 0.5rem; }
        .page-subtitle { color: #a7f3d0; margin-bottom: 2rem; }
        .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 1.5rem; }
        .card {
            background: rgba(255,255,255,0.1);
            border-radius: 16px;
            padding: 1.5rem;
            transition: all 0.3s;
            cursor: pointer;
        }
        .card:hover { transform: translateY(-4px); background: rgba(255,255,255,0.15); }
        .card-icon { font-size: 2.5rem; margin-bottom: 1rem; }
        .card-title { font-size: 1.25rem; font-weight: 600; margin-bottom: 0.5rem; }
        .card-desc { color: #a7f3d0; font-size: 0.9rem; }
        .search-box {
            background: rgba(255,255,255,0.1);
            border-radius: 12px;
            padding: 1rem;
            margin-bottom: 2rem;
            display: flex;
            gap: 1rem;
        }
        .search-box input {
            flex: 1;
            background: rgba(255,255,255,0.1);
            border: 1px solid rgba(255,255,255,0.2);
            border-radius: 8px;
            padding: 0.75rem 1rem;
            color: white;
            font-size: 1rem;
        }
        .search-box input::placeholder { color: #a7f3d0; }
        .search-box button {
            background: #10b981;
            color: white;
            border: none;
            padding: 0.75rem 1.5rem;
            border-radius: 8px;
            cursor: pointer;
            font-weight: 600;
        }
        .search-box button:hover { background: #059669; }
        .librarian-chat {
            background: rgba(255,255,255,0.1);
            border-radius: 16px;
            padding: 1.5rem;
            margin-top: 2rem;
        }
        .chat-title { font-size: 1.25rem; margin-bottom: 1rem; display: flex; align-items: center; gap: 0.5rem; }
        .chat-messages {
            background: rgba(0,0,0,0.2);
            border-radius: 12px;
            padding: 1rem;
            height: 300px;
            overflow-y: auto;
            margin-bottom: 1rem;
        }
        .message { margin-bottom: 1rem; padding: 0.75rem; border-radius: 8px; }
        .message.user { background: #10b981; margin-left: 20%; }
        .message.bot { background: rgba(255,255,255,0.1); margin-right: 20%; }
        .chat-input {
            display: flex;
            gap: 0.5rem;
        }
        .chat-input input {
            flex: 1;
            background: rgba(255,255,255,0.1);
            border: 1px solid rgba(255,255,255,0.2);
            border-radius: 8px;
            padding: 0.75rem 1rem;
            color: white;
        }
        .chat-input button {
            background: #10b981;
            color: white;
            border: none;
            padding: 0.75rem 1.5rem;
            border-radius: 8px;
            cursor: pointer;
        }
        #results { margin-top: 2rem; }
        .result-item {
            background: rgba(255,255,255,0.1);
            border-radius: 12px;
            padding: 1rem;
            margin-bottom: 1rem;
        }
        .result-title { font-weight: 600; margin-bottom: 0.5rem; }
        .result-citation { color: #a7f3d0; font-size: 0.9rem; }
    </style>
</head>
<body>
    <header class="header">
        <div class="logo">📚 Semptify Law Library</div>
        <nav class="nav-links">
            <a href="/documents">📄 Documents</a>
            <a href="/timeline">📅 Timeline</a>
            <a href="/eviction-defense">⚖️ Eviction Defense</a>
            <a href="/zoom-court">💻 Zoom Court</a>
        </nav>
    </header>
    <div class="container">
        <h1 class="page-title">Law Library</h1>
        <p class="page-subtitle">Minnesota Tenant Rights & Housing Law Reference</p>
        
        <div class="search-box">
            <input type="text" id="search-input" placeholder="Search statutes, case law, rights...">
            <button onclick="searchLaw()">🔍 Search</button>
        </div>
        
        <div class="grid">
            <div class="card" onclick="browseCategory('tenant_rights')">
                <div class="card-icon">🏠</div>
                <div class="card-title">Tenant Rights</div>
                <div class="card-desc">Your fundamental rights as a tenant in Minnesota</div>
            </div>
            <div class="card" onclick="browseCategory('eviction')">
                <div class="card-icon">⚖️</div>
                <div class="card-title">Eviction Procedures</div>
                <div class="card-desc">Legal requirements for eviction in MN</div>
            </div>
            <div class="card" onclick="browseCategory('security_deposits')">
                <div class="card-icon">💰</div>
                <div class="card-title">Security Deposits</div>
                <div class="card-desc">Deposit limits, return requirements, deductions</div>
            </div>
            <div class="card" onclick="browseCategory('habitability')">
                <div class="card-icon">🔧</div>
                <div class="card-title">Habitability</div>
                <div class="card-desc">Landlord's duty to maintain livable conditions</div>
            </div>
            <div class="card" onclick="browseCategory('retaliation')">
                <div class="card-icon">🛡️</div>
                <div class="card-title">Retaliation Protection</div>
                <div class="card-desc">Protection against landlord retaliation</div>
            </div>
            <div class="card" onclick="browseCategory('discrimination')">
                <div class="card-icon">👥</div>
                <div class="card-title">Fair Housing</div>
                <div class="card-desc">Anti-discrimination protections</div>
            </div>
        </div>
        
        <div id="results"></div>
        
        <div class="librarian-chat">
            <div class="chat-title">🤖 AI Legal Librarian</div>
            <div class="chat-messages" id="chat-messages">
                <div class="message bot">Hello! I'm your AI legal librarian. I can help you find relevant statutes, case law, and understand your tenant rights. What would you like to know?</div>
            </div>
            <div class="chat-input">
                <input type="text" id="chat-input" placeholder="Ask about tenant rights, eviction, security deposits...">
                <button onclick="askLibrarian()">Send</button>
            </div>
        </div>
    </div>
    <script>
        async function searchLaw() {
            const query = document.getElementById('search-input').value;
            if (!query) return;
            const res = await fetch('/api/law-library/statutes?search=' + encodeURIComponent(query));
            const data = await res.json();
            displayResults(data);
        }
        
        async function browseCategory(cat) {
            const res = await fetch('/api/law-library/statutes?category=' + cat);
            const data = await res.json();
            displayResults(data);
        }
        
        function displayResults(data) {
            const container = document.getElementById('results');
            if (!data.length) {
                container.innerHTML = '<p style="text-align:center; color:#a7f3d0;">No results found</p>';
                return;
            }
            container.innerHTML = data.map(s => `
                <div class="result-item">
                    <div class="result-title">${s.title}</div>
                    <div class="result-citation">${s.citation}</div>
                    <p style="margin-top:0.5rem">${s.summary}</p>
                </div>
            `).join('');
        }
        
        async function askLibrarian() {
            const input = document.getElementById('chat-input');
            const messages = document.getElementById('chat-messages');
            const question = input.value.trim();
            if (!question) return;
            
            messages.innerHTML += '<div class="message user">' + question + '</div>';
            input.value = '';
            
            try {
                const res = await fetch('/api/law-library/librarian/ask', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ question })
                });
                const data = await res.json();
                messages.innerHTML += '<div class="message bot">' + data.answer + '</div>';
            } catch (e) {
                messages.innerHTML += '<div class="message bot">I apologize, I encountered an error. Please try again.</div>';
            }
            messages.scrollTop = messages.scrollHeight;
        }
        
        document.getElementById('chat-input').addEventListener('keypress', e => {
            if (e.key === 'Enter') askLibrarian();
        });
        document.getElementById('search-input').addEventListener('keypress', e => {
            if (e.key === 'Enter') searchLaw();
        });
    </script>
</body>
</html>"""


def generate_eviction_defense_html() -> str:
    """Generate eviction defense toolkit HTML page."""
    return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Eviction Defense - Semptify</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #7f1d1d 0%, #991b1b 100%);
            color: #fff;
            min-height: 100vh;
        }
        .header {
            background: rgba(0,0,0,0.2);
            padding: 1rem 2rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .logo { font-size: 1.5rem; font-weight: 700; }
        .nav-links { display: flex; gap: 1rem; }
        .nav-links a {
            color: #fecaca;
            text-decoration: none;
            padding: 0.5rem 1rem;
            border-radius: 8px;
            transition: all 0.2s;
        }
        .nav-links a:hover { background: rgba(255,255,255,0.1); }
        .container { max-width: 1200px; margin: 0 auto; padding: 2rem; }
        .page-title { font-size: 2.5rem; font-weight: 700; margin-bottom: 0.5rem; }
        .page-subtitle { color: #fecaca; margin-bottom: 2rem; }
        .tabs {
            display: flex;
            gap: 0.5rem;
            margin-bottom: 2rem;
            flex-wrap: wrap;
        }
        .tab {
            background: rgba(255,255,255,0.1);
            border: none;
            color: white;
            padding: 0.75rem 1.5rem;
            border-radius: 8px;
            cursor: pointer;
            font-size: 0.9rem;
            transition: all 0.2s;
        }
        .tab:hover, .tab.active { background: #ef4444; }
        .content-panel { display: none; }
        .content-panel.active { display: block; }
        .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(350px, 1fr)); gap: 1.5rem; }
        .card {
            background: rgba(255,255,255,0.1);
            border-radius: 16px;
            padding: 1.5rem;
            transition: all 0.3s;
        }
        .card:hover { transform: translateY(-4px); background: rgba(255,255,255,0.15); }
        .card-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem; }
        .card-title { font-size: 1.1rem; font-weight: 600; }
        .card-badge {
            background: #ef4444;
            padding: 0.25rem 0.75rem;
            border-radius: 20px;
            font-size: 0.75rem;
        }
        .card-desc { color: #fecaca; font-size: 0.9rem; margin-bottom: 1rem; }
        .card-btn {
            background: #ef4444;
            color: white;
            border: none;
            padding: 0.5rem 1rem;
            border-radius: 6px;
            cursor: pointer;
            font-size: 0.875rem;
            width: 100%;
        }
        .card-btn:hover { background: #dc2626; }
        .timeline {
            background: rgba(255,255,255,0.1);
            border-radius: 16px;
            padding: 1.5rem;
        }
        .timeline-item {
            display: flex;
            gap: 1rem;
            margin-bottom: 1.5rem;
            position: relative;
        }
        .timeline-item::before {
            content: '';
            position: absolute;
            left: 15px;
            top: 30px;
            bottom: -20px;
            width: 2px;
            background: rgba(255,255,255,0.2);
        }
        .timeline-item:last-child::before { display: none; }
        .timeline-dot {
            width: 32px;
            height: 32px;
            background: #ef4444;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: 600;
            flex-shrink: 0;
        }
        .timeline-content { flex: 1; }
        .timeline-title { font-weight: 600; margin-bottom: 0.25rem; }
        .timeline-desc { color: #fecaca; font-size: 0.9rem; }
        .stats-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 1rem; margin-bottom: 2rem; }
        .stat-card {
            background: rgba(255,255,255,0.1);
            border-radius: 12px;
            padding: 1.25rem;
            text-align: center;
        }
        .stat-value { font-size: 2rem; font-weight: 700; }
        .stat-label { color: #fecaca; font-size: 0.85rem; }
        #motion-modal {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(0,0,0,0.8);
            z-index: 1000;
            align-items: center;
            justify-content: center;
        }
        .modal-content {
            background: #1f2937;
            border-radius: 16px;
            padding: 2rem;
            max-width: 800px;
            max-height: 80vh;
            overflow-y: auto;
            margin: 2rem;
        }
        .modal-close {
            float: right;
            background: none;
            border: none;
            color: white;
            font-size: 1.5rem;
            cursor: pointer;
        }
        .template-text {
            background: rgba(0,0,0,0.3);
            padding: 1rem;
            border-radius: 8px;
            font-family: monospace;
            white-space: pre-wrap;
            font-size: 0.85rem;
            margin-top: 1rem;
        }
        @media (max-width: 768px) {
            .stats-grid { grid-template-columns: repeat(2, 1fr); }
        }
    </style>
</head>
<body>
    <header class="header">
        <div class="logo">⚖️ Eviction Defense Toolkit</div>
        <nav class="nav-links">
            <a href="/documents">📄 Documents</a>
            <a href="/timeline">📅 Timeline</a>
            <a href="/law-library">📚 Law Library</a>
            <a href="/zoom-court">💻 Zoom Court</a>
        </nav>
    </header>
    <div class="container">
        <h1 class="page-title">Dakota County Eviction Defense</h1>
        <p class="page-subtitle">Complete toolkit for defending against eviction in Dakota County, MN</p>
        
        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-value" id="stat-motions">6</div>
                <div class="stat-label">Motion Templates</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" id="stat-forms">8</div>
                <div class="stat-label">Court Forms</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" id="stat-defenses">12</div>
                <div class="stat-label">Defense Strategies</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" id="stat-counterclaims">5</div>
                <div class="stat-label">Counterclaim Types</div>
            </div>
        </div>
        
        <div class="tabs">
            <button class="tab active" onclick="showPanel('motions')">📋 Motions</button>
            <button class="tab" onclick="showPanel('forms')">📝 Forms</button>
            <button class="tab" onclick="showPanel('procedures')">📚 Procedures</button>
            <button class="tab" onclick="showPanel('defenses')">🛡️ Defenses</button>
            <button class="tab" onclick="showPanel('counterclaims')">⚔️ Counterclaims</button>
            <button class="tab" onclick="showPanel('timeline')">📅 Case Timeline</button>
        </div>
        
        <div id="motions" class="content-panel active">
            <div class="grid" id="motions-grid">Loading motions...</div>
        </div>
        
        <div id="forms" class="content-panel">
            <div class="grid" id="forms-grid">Loading forms...</div>
        </div>
        
        <div id="procedures" class="content-panel">
            <div class="timeline" id="procedures-list">Loading procedures...</div>
        </div>
        
        <div id="defenses" class="content-panel">
            <div class="grid" id="defenses-grid">Loading defenses...</div>
        </div>
        
        <div id="counterclaims" class="content-panel">
            <div class="grid" id="counterclaims-grid">Loading counterclaims...</div>
        </div>
        
        <div id="timeline" class="content-panel">
            <div class="timeline" id="case-timeline">Loading timeline...</div>
        </div>
    </div>
    
    <div id="motion-modal">
        <div class="modal-content">
            <button class="modal-close" onclick="closeModal()">×</button>
            <div id="modal-body"></div>
        </div>
    </div>
    
    <script>
        async function loadData() {
            // Load motions
            const motions = await fetch('/api/eviction-defense/motions').then(r => r.json());
            document.getElementById('motions-grid').innerHTML = motions.map(m => `
                <div class="card">
                    <div class="card-header">
                        <div class="card-title">${m.title}</div>
                        <span class="card-badge">${m.success_rate || 'Standard'}</span>
                    </div>
                    <div class="card-desc">${m.description}</div>
                    <button class="card-btn" onclick="showMotion('${m.id}')">View Template</button>
                </div>
            `).join('');
            
            // Load forms
            const forms = await fetch('/api/eviction-defense/forms').then(r => r.json());
            document.getElementById('forms-grid').innerHTML = forms.map(f => `
                <div class="card">
                    <div class="card-header">
                        <div class="card-title">${f.name}</div>
                        <span class="card-badge">${f.court}</span>
                    </div>
                    <div class="card-desc">${f.description}</div>
                    <button class="card-btn" onclick="showForm('${f.id}')">View Form</button>
                </div>
            `).join('');
            
            // Load defenses
            const defenses = await fetch('/api/eviction-defense/defenses').then(r => r.json());
            document.getElementById('defenses-grid').innerHTML = defenses.map(d => `
                <div class="card">
                    <div class="card-header">
                        <div class="card-title">${d.name}</div>
                    </div>
                    <div class="card-desc">${d.description}</div>
                    <p style="margin-top:0.5rem;font-size:0.85rem;"><strong>Legal Basis:</strong> ${d.legal_basis}</p>
                </div>
            `).join('');
            
            // Load counterclaims
            const claims = await fetch('/api/eviction-defense/counterclaims').then(r => r.json());
            document.getElementById('counterclaims-grid').innerHTML = claims.map(c => `
                <div class="card">
                    <div class="card-header">
                        <div class="card-title">${c.title}</div>
                    </div>
                    <div class="card-desc">${c.description}</div>
                    <button class="card-btn" onclick="showCounterclaim('${c.id}')">Learn More</button>
                </div>
            `).join('');
            
            // Load procedures
            const procedures = await fetch('/api/eviction-defense/procedures').then(r => r.json());
            document.getElementById('procedures-list').innerHTML = procedures.map((p, i) => `
                <div class="timeline-item">
                    <div class="timeline-dot">${i + 1}</div>
                    <div class="timeline-content">
                        <div class="timeline-title">${p.title}</div>
                        <div class="timeline-desc">${p.description}</div>
                    </div>
                </div>
            `).join('');
        }
        
        function showPanel(panel) {
            document.querySelectorAll('.content-panel').forEach(p => p.classList.remove('active'));
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            document.getElementById(panel).classList.add('active');
            event.target.classList.add('active');
        }
        
        async function showMotion(id) {
            const motions = await fetch('/api/eviction-defense/motions').then(r => r.json());
            const motion = motions.find(m => m.id === id);
            if (motion) {
                document.getElementById('modal-body').innerHTML = `
                    <h2 style="margin-bottom:1rem">${motion.title}</h2>
                    <p style="color:#fecaca;margin-bottom:1rem">${motion.description}</p>
                    <h3 style="margin:1rem 0 0.5rem">When to Use:</h3>
                    <ul style="margin-left:1.5rem;color:#fecaca">${motion.when_to_use.map(w => '<li>' + w + '</li>').join('')}</ul>
                    <h3 style="margin:1rem 0 0.5rem">Legal Basis:</h3>
                    <ul style="margin-left:1.5rem;color:#fecaca">${motion.legal_basis.map(l => '<li>' + l + '</li>').join('')}</ul>
                    <h3 style="margin:1rem 0 0.5rem">Template:</h3>
                    <div class="template-text">${motion.template_text}</div>
                `;
                document.getElementById('motion-modal').style.display = 'flex';
            }
        }
        
        async function showForm(id) {
            const forms = await fetch('/api/eviction-defense/forms').then(r => r.json());
            const form = forms.find(f => f.id === id);
            if (form) {
                document.getElementById('modal-body').innerHTML = `
                    <h2 style="margin-bottom:1rem">${form.name}</h2>
                    <p style="color:#fecaca;margin-bottom:1rem">${form.description}</p>
                    <p><strong>Court:</strong> ${form.court}</p>
                    <p><strong>Filing Fee:</strong> ${form.filing_fee || 'Varies'}</p>
                    <h3 style="margin:1rem 0 0.5rem">Instructions:</h3>
                    <ol style="margin-left:1.5rem;color:#fecaca">${form.instructions.map(i => '<li>' + i + '</li>').join('')}</ol>
                `;
                document.getElementById('motion-modal').style.display = 'flex';
            }
        }
        
        async function showCounterclaim(id) {
            const claims = await fetch('/api/eviction-defense/counterclaims').then(r => r.json());
            const claim = claims.find(c => c.id === id);
            if (claim) {
                document.getElementById('modal-body').innerHTML = `
                    <h2 style="margin-bottom:1rem">${claim.title}</h2>
                    <p style="color:#fecaca;margin-bottom:1rem">${claim.description}</p>
                    <h3 style="margin:1rem 0 0.5rem">Requirements:</h3>
                    <ul style="margin-left:1.5rem;color:#fecaca">${claim.requirements.map(r => '<li>' + r + '</li>').join('')}</ul>
                    <h3 style="margin:1rem 0 0.5rem">Potential Damages:</h3>
                    <ul style="margin-left:1.5rem;color:#fecaca">${claim.potential_damages.map(d => '<li>' + d + '</li>').join('')}</ul>
                `;
                document.getElementById('motion-modal').style.display = 'flex';
            }
        }
        
        function closeModal() {
            document.getElementById('motion-modal').style.display = 'none';
        }
        
        document.getElementById('motion-modal').addEventListener('click', e => {
            if (e.target.id === 'motion-modal') closeModal();
        });
        
        loadData();
    </script>
</body>
</html>"""


def generate_zoom_court_html() -> str:
    """Generate zoom court helper HTML page."""
    return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Zoom Court Helper - Semptify</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #0c4a6e 0%, #075985 100%);
            color: #fff;
            min-height: 100vh;
        }
        .header {
            background: rgba(0,0,0,0.2);
            padding: 1rem 2rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .logo { font-size: 1.5rem; font-weight: 700; }
        .nav-links { display: flex; gap: 1rem; }
        .nav-links a {
            color: #bae6fd;
            text-decoration: none;
            padding: 0.5rem 1rem;
            border-radius: 8px;
            transition: all 0.2s;
        }
        .nav-links a:hover { background: rgba(255,255,255,0.1); }
        .container { max-width: 1200px; margin: 0 auto; padding: 2rem; }
        .page-title { font-size: 2.5rem; font-weight: 700; margin-bottom: 0.5rem; }
        .page-subtitle { color: #bae6fd; margin-bottom: 2rem; }
        .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 1.5rem; }
        .card {
            background: rgba(255,255,255,0.1);
            border-radius: 16px;
            padding: 1.5rem;
            transition: all 0.3s;
        }
        .card:hover { transform: translateY(-4px); background: rgba(255,255,255,0.15); }
        .card-icon { font-size: 2.5rem; margin-bottom: 1rem; }
        .card-title { font-size: 1.25rem; font-weight: 600; margin-bottom: 0.5rem; }
        .card-desc { color: #bae6fd; font-size: 0.9rem; }
        .checklist {
            background: rgba(255,255,255,0.1);
            border-radius: 16px;
            padding: 1.5rem;
            margin-top: 2rem;
        }
        .checklist-title { font-size: 1.25rem; margin-bottom: 1rem; }
        .check-item {
            display: flex;
            align-items: center;
            gap: 0.75rem;
            padding: 0.75rem;
            background: rgba(0,0,0,0.2);
            border-radius: 8px;
            margin-bottom: 0.5rem;
            cursor: pointer;
        }
        .check-item:hover { background: rgba(0,0,0,0.3); }
        .check-item input { width: 20px; height: 20px; }
        .check-item.critical { border-left: 4px solid #f59e0b; }
        .check-item label { flex: 1; cursor: pointer; }
        .check-item .fix { font-size: 0.85rem; color: #bae6fd; margin-top: 0.25rem; }
        .tips-section {
            background: rgba(255,255,255,0.1);
            border-radius: 16px;
            padding: 1.5rem;
            margin-top: 2rem;
        }
        .tips-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 1rem; }
        .tip-category { margin-bottom: 1rem; }
        .tip-category h3 { font-size: 1rem; margin-bottom: 0.5rem; color: #0ea5e9; }
        .tip-list { list-style: none; }
        .tip-list li { padding: 0.5rem 0; border-bottom: 1px solid rgba(255,255,255,0.1); font-size: 0.9rem; }
        .etiquette {
            background: rgba(255,255,255,0.1);
            border-radius: 16px;
            padding: 1.5rem;
            margin-top: 2rem;
        }
        .rule-item {
            display: flex;
            gap: 1rem;
            padding: 1rem;
            background: rgba(0,0,0,0.2);
            border-radius: 8px;
            margin-bottom: 0.75rem;
        }
        .rule-icon { font-size: 1.5rem; }
        .rule-content { flex: 1; }
        .rule-title { font-weight: 600; margin-bottom: 0.25rem; }
        .rule-desc { color: #bae6fd; font-size: 0.9rem; }
        .phrases-section {
            background: rgba(255,255,255,0.1);
            border-radius: 16px;
            padding: 1.5rem;
            margin-top: 2rem;
        }
        .phrase-category { margin-bottom: 1.5rem; }
        .phrase-category h3 { margin-bottom: 0.75rem; color: #0ea5e9; }
        .phrase-item {
            display: flex;
            gap: 1rem;
            padding: 0.75rem;
            background: rgba(0,0,0,0.2);
            border-radius: 8px;
            margin-bottom: 0.5rem;
        }
        .phrase-situation { color: #bae6fd; min-width: 200px; }
        .phrase-text { font-style: italic; }
        @media (max-width: 768px) {
            .tips-grid { grid-template-columns: 1fr; }
        }
    </style>
</head>
<body>
    <header class="header">
        <div class="logo">💻 Zoom Court Helper</div>
        <nav class="nav-links">
            <a href="/documents">📄 Documents</a>
            <a href="/timeline">📅 Timeline</a>
            <a href="/law-library">📚 Law Library</a>
            <a href="/eviction-defense">⚖️ Eviction Defense</a>
        </nav>
    </header>
    <div class="container">
        <h1 class="page-title">Zoom Court Helper</h1>
        <p class="page-subtitle">Prepare for your virtual court hearing with confidence</p>
        
        <div class="grid">
            <div class="card" onclick="scrollTo('checklist')">
                <div class="card-icon">✅</div>
                <div class="card-title">Tech Checklist</div>
                <div class="card-desc">Ensure your technology is ready for court</div>
            </div>
            <div class="card" onclick="scrollTo('etiquette')">
                <div class="card-icon">🎩</div>
                <div class="card-title">Court Etiquette</div>
                <div class="card-desc">Proper behavior for virtual hearings</div>
            </div>
            <div class="card" onclick="scrollTo('phrases')">
                <div class="card-icon">🗣️</div>
                <div class="card-title">What to Say</div>
                <div class="card-desc">Phrases to use when addressing the court</div>
            </div>
            <div class="card" onclick="scrollTo('tips')">
                <div class="card-icon">💡</div>
                <div class="card-title">Quick Tips</div>
                <div class="card-desc">Essential tips for before, during, and after</div>
            </div>
        </div>
        
        <div class="checklist" id="checklist">
            <h2 class="checklist-title">📋 Technology Checklist</h2>
            <div id="tech-checklist">Loading checklist...</div>
        </div>
        
        <div class="etiquette" id="etiquette">
            <h2 class="checklist-title">🎩 Court Etiquette Rules</h2>
            <div id="etiquette-rules">Loading etiquette rules...</div>
        </div>
        
        <div class="phrases-section" id="phrases">
            <h2 class="checklist-title">🗣️ Helpful Phrases</h2>
            <div id="phrases-list">Loading phrases...</div>
        </div>
        
        <div class="tips-section" id="tips">
            <h2 class="checklist-title">💡 Quick Tips</h2>
            <div class="tips-grid" id="quick-tips">Loading tips...</div>
        </div>
    </div>
    
    <script>
        async function loadData() {
            // Load tech checklist
            const checklist = await fetch('/api/zoom-court/tech-checklist').then(r => r.json());
            document.getElementById('tech-checklist').innerHTML = checklist.map(item => `
                <div class="check-item ${item.critical ? 'critical' : ''}">
                    <input type="checkbox" id="check-${item.item.replace(/\\s/g, '-')}">
                    <label for="check-${item.item.replace(/\\s/g, '-')}">
                        <strong>${item.item}</strong>
                        <div class="fix">${item.description} — Fix: ${item.how_to_fix}</div>
                    </label>
                </div>
            `).join('');
            
            // Load etiquette
            const etiquette = await fetch('/api/zoom-court/etiquette').then(r => r.json());
            document.getElementById('etiquette-rules').innerHTML = etiquette.map(rule => `
                <div class="rule-item">
                    <div class="rule-icon">📌</div>
                    <div class="rule-content">
                        <div class="rule-title">${rule.rule}</div>
                        <div class="rule-desc">${rule.explanation}</div>
                    </div>
                </div>
            `).join('');
            
            // Load phrases
            const phrases = await fetch('/api/zoom-court/phrases-to-use').then(r => r.json());
            let phrasesHtml = '';
            for (const [category, items] of Object.entries(phrases)) {
                phrasesHtml += `<div class="phrase-category"><h3>${category.replace(/_/g, ' ').toUpperCase()}</h3>`;
                phrasesHtml += items.map(p => `
                    <div class="phrase-item">
                        <div class="phrase-situation">${p.situation}</div>
                        <div class="phrase-text">"${p.phrase}"</div>
                    </div>
                `).join('');
                phrasesHtml += '</div>';
            }
            document.getElementById('phrases-list').innerHTML = phrasesHtml;
            
            // Load quick tips
            const tips = await fetch('/api/zoom-court/quick-tips').then(r => r.json());
            let tipsHtml = '';
            for (const [category, items] of Object.entries(tips)) {
                tipsHtml += `<div class="tip-category"><h3>${category.replace(/_/g, ' ')}</h3><ul class="tip-list">`;
                tipsHtml += items.map(t => `<li>${t}</li>`).join('');
                tipsHtml += '</ul></div>';
            }
            document.getElementById('quick-tips').innerHTML = tipsHtml;
        }
        
        function scrollTo(id) {
            document.getElementById(id).scrollIntoView({ behavior: 'smooth' });
        }
        
        loadData();
    </script>
</body>
</html>"""


# =============================================================================
# Create FastAPI App
# =============================================================================

def create_app() -> FastAPI:
    """
    Application factory.
    Creates and configures the FastAPI application.
    """
    settings = get_settings()
    setup_logging()

    # OpenAPI tags for documentation organization
    tags_metadata = [
        {
            "name": "Health",
            "description": "Health checks, readiness probes, and metrics endpoints.",
        },
        {
            "name": "Authentication",
            "description": "User authentication status and role management.",
        },
        {
            "name": "Storage Auth",
            "description": "OAuth2 flows for Google Drive, Dropbox, and OneDrive.",
        },
        {
            "name": "Document Vault",
            "description": "Secure document upload, certification, and retrieval.",
        },
        {
            "name": "Documents",
            "description": "Document processing, analysis, and classification.",
        },
        {
            "name": "Timeline",
            "description": "Chronological event tracking for evidence building.",
        },
        {
            "name": "Calendar",
            "description": "Deadline and appointment management.",
        },
        {
            "name": "Copilot",
            "description": "AI-powered tenant rights assistant.",
        },
        {
            "name": "Context Loop",
            "description": "Event processing and intensity engine.",
        },
        {
            "name": "Adaptive UI",
            "description": "Dynamic UI configuration based on user context.",
        },
        {
            "name": "Document Registry",
            "description": "Tamper-proof document management with chain of custody and forgery detection.",
        },
        {
            "name": "Eviction Case",
            "description": "Unified case builder - pulls from all Semptify data for court-ready packages.",
        },
        {
            "name": "Court Learning",
            "description": "Bidirectional learning - record outcomes, query patterns, get data-driven strategies.",
        },
        {
            "name": "Dakota Procedures",
            "description": "Court rules, motions, objections, counterclaims, and step-by-step procedures.",
        },
        {
            "name": "Eviction Defense",
            "description": "Dakota County eviction answer forms and motions.",
        },
        {
            "name": "Law Library",
            "description": "Legal research with AI librarian, statutes, case law, and deadline calculator.",
        },
        {
            "name": "Eviction Defense Toolkit",
            "description": "Complete eviction defense with motions, forms, procedures, counterclaims, and trial prep.",
        },
        {
            "name": "Zoom Courtroom",
            "description": "Virtual courtroom preparation, tech checklist, etiquette, and hearing guides.",
        },
    ]

    app = FastAPI(
        title=settings.app_name,
        description=settings.app_description,
        version=settings.app_version,
        lifespan=lifespan,
        docs_url="/api/docs" if settings.enable_docs else None,
        redoc_url="/api/redoc" if settings.enable_docs else None,
        openapi_url="/api/openapi.json" if settings.enable_docs else None,
        openapi_tags=tags_metadata,
        contact={
            "name": "Semptify Support",
            "url": "https://github.com/Semptify/Semptify-FastAPI",
        },
        license_info={
            "name": "MIT License",
            "url": "https://opensource.org/licenses/MIT",
        },
    )    # =========================================================================
    # Middleware
    # =========================================================================
    
    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Request ID middleware
    @app.middleware("http")
    async def add_request_id(request: Request, call_next):
        import uuid
        request_id = request.headers.get("X-Request-Id", str(uuid.uuid4()))
        response = await call_next(request)
        response.headers["X-Request-Id"] = request_id
        return response
    
    # =========================================================================
    # Exception Handlers
    # =========================================================================
    
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger = logging.getLogger(__name__)
        logger.error(f"Unhandled exception: {exc}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"},
        )
    
    # =========================================================================
    # Register Routers
    # =========================================================================
    
    # Health & metrics (no prefix)
    app.include_router(health.router, tags=["Health"])

    # Storage OAuth (handles authentication)
    app.include_router(storage.router, tags=["Storage Auth"])

    # API routes
    app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
    app.include_router(vault.router, prefix="/api/vault", tags=["Document Vault"])
    app.include_router(timeline.router, prefix="/api/timeline", tags=["Timeline"])
    app.include_router(calendar.router, prefix="/api/calendar", tags=["Calendar"])
    app.include_router(copilot.router, prefix="/api/copilot", tags=["AI Copilot"])
    app.include_router(documents.router, tags=["Documents"])  # Fresh document processing API
    app.include_router(adaptive_ui.router, tags=["Adaptive UI"])  # Self-building interface
    app.include_router(context_loop.router, tags=["Context Loop"])  # Core processing engine
    app.include_router(intake_router, tags=["Document Intake"])  # Document intake & extraction
    app.include_router(registry_router, tags=["Document Registry"])  # Tamper-proof chain of custody
    app.include_router(vault_engine_router, tags=["Vault Engine"])  # Centralized access control
    app.include_router(form_data_router, prefix="/api/form-data", tags=["Form Data Hub"])  # Central data integration
    app.include_router(setup_router, prefix="/api/setup", tags=["Setup Wizard"])  # Initial setup wizard
    app.include_router(websocket_router, prefix="/ws", tags=["WebSocket Events"])  # Real-time events

    # Dakota County Eviction Defense Module
    if DAKOTA_AVAILABLE:
        app.include_router(dakota_case, prefix="/eviction", tags=["Eviction Case"])
        app.include_router(dakota_learning, prefix="/eviction/learn", tags=["Court Learning"])
        app.include_router(dakota_procedures, tags=["Dakota Procedures"])
        app.include_router(dakota_flows, prefix="/eviction", tags=["Eviction Defense"])
        app.include_router(dakota_forms, prefix="/eviction/forms", tags=["Court Forms"])
        logging.getLogger(__name__).info("✅ Dakota County Eviction Defense module loaded")
    else:
        logging.getLogger(__name__).warning("⚠️ Dakota County module not available")

    # New Legal Defense Modules
    app.include_router(law_library_router, tags=["Law Library"])
    app.include_router(eviction_defense_router, tags=["Eviction Defense Toolkit"])
    app.include_router(zoom_court_router, tags=["Zoom Courtroom"])
    logging.getLogger(__name__).info("✅ Legal Defense modules loaded (Law Library, Eviction Defense, Zoom Court)")

    # app.include_router(complaints.router, prefix="/api/complaints", tags=["Complaints"])
    # app.include_router(ledger.router, prefix="/api/ledger", tags=["Rent Ledger"])
    # app.include_router(admin.router, prefix="/api/admin", tags=["Admin"])
    
    # =========================================================================
    # Static Files (for any frontend assets)
    # =========================================================================
    
    static_path = Path("static")
    if static_path.exists():
        app.mount("/static", StaticFiles(directory="static"), name="static")
    
    # =========================================================================
    # Root endpoint - Serve SPA
    # =========================================================================

    @app.get("/", response_class=HTMLResponse)
    async def root():
        """Serve the unified dashboard - main user-facing page."""
        dashboard_path = Path("static/dashboard.html")
        if dashboard_path.exists():
            return HTMLResponse(content=dashboard_path.read_text(encoding="utf-8"))
        # Fallback to documents page
        documents_path = Path("static/documents.html")
        if documents_path.exists():
            return HTMLResponse(content=documents_path.read_text(encoding="utf-8"))
        # Fallback JSON response if no frontend
        return JSONResponse(content={
            "name": settings.app_name,
            "version": settings.app_version,
            "description": settings.app_description,
            "docs": "/api/docs" if settings.debug else "disabled",
        })

    @app.get("/dev/elbow", response_class=HTMLResponse)
    async def elbow_dev():
        """
        Elbow UI - Development mode only.
        The experimental Elbow interface for legal flow assistance.
        """
        if not settings.debug:
            return HTMLResponse(
                content="<h1>404 - Not Found</h1><p>This page is only available in development mode.</p>",
                status_code=404
            )
        index_path = Path("static/index.html")
        if index_path.exists():
            return HTMLResponse(content=index_path.read_text(encoding="utf-8"))
        return JSONResponse(content={"error": "Elbow UI not found"}, status_code=404)    # =========================================================================
    # Vault UI Page (after OAuth redirect)
    # =========================================================================

    @app.get("/vault", response_class=HTMLResponse)
    async def vault_page(request: Request):
        """
        Vault UI page - where users land after OAuth authentication.
        Shows their connected storage and vault documents.
        """
        session_id = request.cookies.get("semptify_session")
        if not session_id:
            return RedirectResponse(url="/", status_code=302)
        
        return HTMLResponse(content=f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Document Vault - {settings.app_name}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            color: #fff;
            min-height: 100vh;
            padding: 2rem;
        }}
        .container {{ max-width: 900px; margin: 0 auto; }}
        header {{ 
            display: flex; 
            justify-content: space-between; 
            align-items: center;
            margin-bottom: 2rem;
            padding-bottom: 1rem;
            border-bottom: 1px solid rgba(255,255,255,0.1);
        }}
        h1 {{ font-size: 1.5rem; font-weight: 600; }}
        .status {{ 
            background: #10b981; 
            padding: 0.5rem 1rem; 
            border-radius: 2rem;
            font-size: 0.875rem;
        }}
        .card {{
            background: rgba(255,255,255,0.05);
            border: 1px solid rgba(255,255,255,0.1);
            border-radius: 1rem;
            padding: 1.5rem;
            margin-bottom: 1.5rem;
        }}
        .card h2 {{ font-size: 1.125rem; margin-bottom: 1rem; color: #94a3b8; }}
        .upload-zone {{
            border: 2px dashed rgba(255,255,255,0.2);
            border-radius: 0.75rem;
            padding: 3rem;
            text-align: center;
            cursor: pointer;
            transition: all 0.2s;
        }}
        .upload-zone:hover {{ border-color: #3b82f6; background: rgba(59,130,246,0.1); }}
        .upload-zone input {{ display: none; }}
        .upload-icon {{ font-size: 3rem; margin-bottom: 1rem; }}
        .btn {{
            background: #3b82f6;
            color: white;
            padding: 0.75rem 1.5rem;
            border: none;
            border-radius: 0.5rem;
            cursor: pointer;
            font-size: 1rem;
            transition: all 0.2s;
        }}
        .btn:hover {{ background: #2563eb; }}
        .documents {{ display: grid; gap: 1rem; }}
        .doc-item {{
            display: flex;
            align-items: center;
            gap: 1rem;
            padding: 1rem;
            background: rgba(255,255,255,0.03);
            border-radius: 0.5rem;
        }}
        .doc-icon {{ font-size: 2rem; }}
        .doc-info {{ flex: 1; }}
        .doc-name {{ font-weight: 500; }}
        .doc-meta {{ font-size: 0.875rem; color: #64748b; }}
        #message {{ 
            padding: 1rem; 
            border-radius: 0.5rem; 
            margin-bottom: 1rem;
            display: none;
        }}
        .success {{ background: rgba(16, 185, 129, 0.2); border: 1px solid #10b981; }}
        .error {{ background: rgba(239, 68, 68, 0.2); border: 1px solid #ef4444; }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>📁 Document Vault</h1>
            <span class="status" id="provider-status">Loading...</span>
        </header>

        <div id="message"></div>

        <div class="card">
            <h2>Upload Documents</h2>
            <div class="upload-zone" id="upload-zone">
                <div class="upload-icon">📤</div>
                <p>Drag & drop files here or click to browse</p>
                <p style="color: #64748b; margin-top: 0.5rem; font-size: 0.875rem;">
                    Documents are stored securely in YOUR cloud storage
                </p>
                <input type="file" id="file-input" multiple accept=".pdf,.doc,.docx,.jpg,.jpeg,.png,.txt">
            </div>
        </div>

        <div class="card">
            <h2>Your Documents</h2>
            <div class="documents" id="documents-list">
                <p style="color: #64748b; text-align: center; padding: 2rem;">
                    Loading documents...
                </p>
            </div>
        </div>
    </div>

    <script>
        // Check session and get storage status
        async function init() {{
            try {{
                const status = await fetch('/storage/status', {{ credentials: 'include' }});
                const data = await status.json();
                
                if (data.authenticated) {{
                    document.getElementById('provider-status').textContent = 
                        '✓ Connected: ' + data.provider;
                    loadDocuments(data.access_token);
                }} else {{
                    document.getElementById('provider-status').textContent = 'Not connected';
                    document.getElementById('provider-status').style.background = '#ef4444';
                }}
            }} catch (e) {{
                showMessage('Failed to load status', 'error');
            }}
        }}

        async function loadDocuments(accessToken) {{
            try {{
                const res = await fetch('/api/vault/?access_token=' + accessToken, {{ 
                    credentials: 'include' 
                }});
                const data = await res.json();
                
                const list = document.getElementById('documents-list');
                if (data.documents && data.documents.length > 0) {{
                    list.innerHTML = data.documents.map(doc => `
                        <div class="doc-item">
                            <span class="doc-icon">${{getIcon(doc.mime_type)}}</span>
                            <div class="doc-info">
                                <div class="doc-name">${{doc.original_filename}}</div>
                                <div class="doc-meta">
                                    ${{formatSize(doc.file_size)}} · 
                                    ${{new Date(doc.uploaded_at).toLocaleDateString()}}
                                </div>
                            </div>
                            <button class="btn" onclick="downloadDoc('${{doc.id}}', '${{accessToken}}')">
                                Download
                            </button>
                        </div>
                    `).join('');
                }} else {{
                    list.innerHTML = '<p style="color: #64748b; text-align: center; padding: 2rem;">No documents yet. Upload your first document above!</p>';
                }}
            }} catch (e) {{
                document.getElementById('documents-list').innerHTML = 
                    '<p style="color: #ef4444;">Failed to load documents</p>';
            }}
        }}

        function getIcon(mime) {{
            if (mime.includes('pdf')) return '📄';
            if (mime.includes('image')) return '🖼️';
            if (mime.includes('word') || mime.includes('doc')) return '📝';
            return '📎';
        }}

        function formatSize(bytes) {{
            if (bytes < 1024) return bytes + ' B';
            if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
            return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
        }}

        function showMessage(text, type) {{
            const el = document.getElementById('message');
            el.textContent = text;
            el.className = type;
            el.style.display = 'block';
            setTimeout(() => el.style.display = 'none', 5000);
        }}

        async function downloadDoc(id, token) {{
            window.open('/api/vault/' + id + '/download?access_token=' + token, '_blank');
        }}

        // File upload handling
        const uploadZone = document.getElementById('upload-zone');
        const fileInput = document.getElementById('file-input');

        uploadZone.addEventListener('click', () => fileInput.click());
        uploadZone.addEventListener('dragover', (e) => {{
            e.preventDefault();
            uploadZone.style.borderColor = '#3b82f6';
        }});
        uploadZone.addEventListener('dragleave', () => {{
            uploadZone.style.borderColor = 'rgba(255,255,255,0.2)';
        }});
        uploadZone.addEventListener('drop', async (e) => {{
            e.preventDefault();
            uploadZone.style.borderColor = 'rgba(255,255,255,0.2)';
            await handleFiles(e.dataTransfer.files);
        }});
        fileInput.addEventListener('change', async () => {{
            await handleFiles(fileInput.files);
        }});

        async function handleFiles(files) {{
            const status = await fetch('/storage/status', {{ credentials: 'include' }});
            const data = await status.json();
            
            if (!data.authenticated) {{
                showMessage('Please connect your storage first', 'error');
                return;
            }}

            for (const file of files) {{
                const formData = new FormData();
                formData.append('file', file);
                formData.append('access_token', data.access_token);

                try {{
                    const res = await fetch('/api/vault/upload', {{
                        method: 'POST',
                        body: formData,
                        credentials: 'include'
                    }});
                    
                    if (res.ok) {{
                        showMessage('Uploaded: ' + file.name, 'success');
                        loadDocuments(data.access_token);
                    }} else {{
                        const err = await res.json();
                        showMessage('Failed: ' + (err.detail || 'Unknown error'), 'error');
                    }}
                }} catch (e) {{
                    showMessage('Upload failed: ' + e.message, 'error');
                }}
            }}
        }}

        // Init on load
        init();
    </script>
</body>
</html>
        """)

    # =========================================================================
    # Timeline Page
    # =========================================================================

    @app.get("/timeline", response_class=HTMLResponse)
    async def timeline_page():
        """Serve the timeline viewer page."""
        timeline_path = Path("static/timeline.html")
        if timeline_path.exists():
            return HTMLResponse(content=timeline_path.read_text(encoding="utf-8"))
        return HTMLResponse(
            content="<h1>Timeline viewer not found</h1>",
            status_code=404
        )

    # =========================================================================
    # Documents Page
    # =========================================================================

    @app.get("/documents", response_class=HTMLResponse)
    async def documents_page():
        """Serve the document intake page."""
        documents_path = Path("static/documents.html")
        if documents_path.exists():
            return HTMLResponse(content=documents_path.read_text(encoding="utf-8"))
        return HTMLResponse(
            content="<h1>Documents page not found</h1>",
            status_code=404
        )

    # =========================================================================
    # Law Library Page
    # =========================================================================

    @app.get("/law-library", response_class=HTMLResponse)
    async def law_library_page():
        """Serve the law library page."""
        return HTMLResponse(content=generate_law_library_html())

    # =========================================================================
    # Eviction Defense Page
    # =========================================================================

    @app.get("/eviction-defense", response_class=HTMLResponse)
    async def eviction_defense_page():
        """Serve the eviction defense toolkit page."""
        return HTMLResponse(content=generate_eviction_defense_html())

    # =========================================================================
    # Zoom Court Page
    # =========================================================================

    @app.get("/zoom-court", response_class=HTMLResponse)
    async def zoom_court_page():
        """Serve the zoom court helper page."""
        return HTMLResponse(content=generate_zoom_court_html())

    return app
# Create the app instance
app = create_app()


# =============================================================================
# Development Server
# =============================================================================

if __name__ == "__main__":
    import uvicorn
    
    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )
