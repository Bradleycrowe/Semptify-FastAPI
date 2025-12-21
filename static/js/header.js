/**
 * Semptify Site-Wide Header Component
 * Include this script on any page to add the standard header with navigation
 * Usage: <script src="/static/js/header.js"></script>
 * 
 * NOTE: This header is DISABLED on pages using shared-nav.js
 * The shared nav component provides navigation for app pages.
 * This header is only for public/landing pages without the sidebar.
 */

(function() {
    // Skip if shared nav is present (app pages use sidebar navigation)
    if (document.getElementById('semptify-nav') || document.body.classList.contains('has-nav')) {
        console.log('Header skipped - using shared nav component');
        return;
    }

    // Header HTML template
    const headerHTML = `
    <header class="semptify-header">
        <div class="header-container">
            <a href="/static/welcome.html" class="header-logo">
                <img src="/static/logo.png" alt="Semptify">
            </a>
            <nav class="header-nav">
                <a href="/static/welcome.html">Home</a>
                <a href="/static/dashboard.html">Dashboard</a>
                <a href="/static/document_intake.html">Documents</a>
                <a href="/static/crisis_intake.html">Crisis Help</a>
            </nav>
        </div>
    </header>
    `;

    // Header CSS styles - dark theme to match app
    const headerCSS = `
    <style id="semptify-header-styles">
        .semptify-header {
            background: linear-gradient(135deg, #1e3a5f 0%, #0f172a 100%);
            border-bottom: 1px solid #334155;
            padding: 1rem 1.5rem;
            position: sticky;
            top: 0;
            z-index: 1000;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        }
        
        .header-container {
            max-width: 1200px;
            margin: 0 auto;
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 1rem;
        }
        
        .header-logo {
            display: flex;
            align-items: center;
            text-decoration: none;
        }
        
        .header-logo img {
            height: 50px;
            width: auto;
            object-fit: contain;
        }
        
        .header-nav {
            display: flex;
            gap: 1.5rem;
            align-items: center;
            flex-wrap: wrap;
            justify-content: center;
        }
        
        .header-nav a {
            color: #f1f5f9;
            text-decoration: none;
            font-size: 0.9rem;
            font-weight: 500;
            padding: 0.5rem 0.75rem;
            border-radius: 4px;
            transition: all 0.2s;
        }
        
        .header-nav a:hover {
            background: rgba(59, 130, 246, 0.2);
            color: #3b82f6;
        }
        
        .header-nav a.active {
            background: #3b82f6;
            color: white;
        }
        
        /* Mobile responsive */
        @media (max-width: 600px) {
            .header-container {
                flex-direction: column;
                gap: 0.75rem;
            }
            
            .header-logo img {
                height: 40px;
            }
            
            .header-nav {
                gap: 0.5rem;
            }
            
            .header-nav a {
                font-size: 0.8rem;
                padding: 0.375rem 0.5rem;
            }
        }
    </style>
    `;

    // Insert header when DOM is ready
    function insertHeader() {
        // Don't add if header already exists
        if (document.querySelector('.semptify-header')) return;
        
        // Add styles to head if not already present
        if (!document.getElementById('semptify-header-styles')) {
            document.head.insertAdjacentHTML('beforeend', headerCSS);
        }
        
        // Add header at the start of body
        document.body.insertAdjacentHTML('afterbegin', headerHTML);
        
        // Highlight current page in nav
        const currentPath = window.location.pathname;
        document.querySelectorAll('.header-nav a').forEach(link => {
            if (currentPath.includes(link.getAttribute('href').replace('/static/', ''))) {
                link.classList.add('active');
            }
        });
    }

    // Run when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', insertHeader);
    } else {
        insertHeader();
    }
})();

// =============================================================================
// QUICK DOCUMENT FAB - Always visible on all pages
// Philosophy: "Document Everything First" - Make documenting frictionless
// =============================================================================
(function() {
    // Skip if already added or on document intake page
    if (document.querySelector('.quick-document-fab')) return;
    if (window.location.pathname.includes('document_intake.html')) return;

    // Quick Document FAB HTML
    const fab = document.createElement('a');
    fab.href = '/static/document_intake.html?quick=true';
    fab.className = 'quick-document-fab';
    fab.innerHTML = '📸 Document';
    fab.title = 'Quick Document - Upload photo, receipt, or screenshot';
    fab.setAttribute('aria-label', 'Quick document upload');

    // FAB Styles
    const fabStyle = document.createElement('style');
    fabStyle.id = 'quick-document-fab-styles';
    fabStyle.textContent = `
        .quick-document-fab {
            position: fixed;
            bottom: 24px;
            right: 24px;
            background: linear-gradient(135deg, #3B5998 0%, #2d4a7c 100%);
            color: white;
            padding: 16px 20px;
            border-radius: 50px;
            text-decoration: none;
            font-weight: 600;
            font-size: 0.95rem;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            box-shadow: 0 4px 12px rgba(59, 89, 152, 0.4);
            z-index: 1000;
            transition: all 0.2s ease;
            display: flex;
            align-items: center;
            gap: 8px;
            min-width: 120px;
            justify-content: center;
        }
        .quick-document-fab:hover {
            background: linear-gradient(135deg, #2d4a7c 0%, #1e3a5f 100%);
            transform: translateY(-2px);
            box-shadow: 0 6px 16px rgba(59, 89, 152, 0.5);
            color: white;
            text-decoration: none;
        }
        .quick-document-fab:active {
            transform: translateY(0);
        }
        /* Pulse animation to draw attention initially */
        @keyframes fab-pulse {
            0%, 100% { box-shadow: 0 4px 12px rgba(59, 89, 152, 0.4); }
            50% { box-shadow: 0 4px 20px rgba(59, 89, 152, 0.7); }
        }
        .quick-document-fab.pulse {
            animation: fab-pulse 2s ease-in-out 3;
        }
        /* Mobile responsive */
        @media (max-width: 600px) {
            .quick-document-fab {
                bottom: 16px;
                right: 16px;
                padding: 14px 18px;
                font-size: 0.9rem;
                min-width: auto;
            }
        }
        /* When sidebar nav is pinned open, move FAB to avoid overlap */
        body.nav-pinned .quick-document-fab {
            right: calc(260px + 24px);
        }
    `;

    // Insert FAB when DOM is ready
    function insertFab() {
        if (!document.getElementById('quick-document-fab-styles')) {
            document.head.appendChild(fabStyle);
        }
        document.body.appendChild(fab);
        
        // Add pulse animation for first-time users
        const hasSeenFab = localStorage.getItem('semptify_seen_fab');
        if (!hasSeenFab) {
            fab.classList.add('pulse');
            localStorage.setItem('semptify_seen_fab', 'true');
        }
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', insertFab);
    } else {
        insertFab();
    }
})();
