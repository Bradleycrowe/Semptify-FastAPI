/**
 * Semptify Shared Navigation Component
 * Single source of truth for all navigation across the app
 * 
 * Usage: Add to any page:
 *   <div id="semptify-nav"></div>
 *   <script src="/static/js/shared-nav.js"></script>
 */

const SemptifyNav = {
    // Navigation structure - edit here to update ALL pages
    sections: [
        {
            id: 'mission',
            title: '🎯 Mission Control',
            items: [
                { icon: '🎯', label: 'Dashboard', href: '/static/dashboard.html' },
                { icon: '🆘', label: 'Crisis Assessment', href: '/static/crisis_intake.html' },
            ]
        },
        {
            id: 'journey',
            title: '🏠 Tenant Journey',
            items: [
                { icon: '📝', label: '1. Lease & Move-In', href: '/static/journey.html' },
                { icon: '💰', label: '2. Rent Payments', href: '/static/document_intake.html?type=payment' },
                { icon: '🔧', label: '3. Maintenance', href: '/static/document_intake.html?type=maintenance' },
                { icon: '⚠️', label: '4. Notices', href: '/static/document_intake.html?type=notice' },
                { icon: '📅', label: '5. Timeline', href: '/static/timeline.html', badge: 'timelineCount' },
            ]
        },
        {
            id: 'defense',
            title: '⚖️ Legal Defense',
            items: [
                { icon: '📖', label: '6. Know Rights', href: '/static/law_library.html' },
                { icon: '📝', label: '7. Answer Summons', href: '/static/eviction_answer.html' },
                { icon: '⚔️', label: '8. Fight Back', href: '/static/eviction_defense.html' },
                { icon: '💻', label: '9. Court Prep', href: '/static/zoom_court.html' },
            ]
        },
        {
            id: 'documents',
            title: '📁 Documents',
            items: [
                { icon: '📁', label: 'Document Vault', href: '/static/documents.html' },
                { icon: '💼', label: 'Briefcase', href: '/static/briefcase.html' },
                { icon: '📦', label: 'Court Packet', href: '/static/court_packet.html' },
                { icon: '📑', label: 'PDF Tools', href: '/static/pdf_tools.html' },
                { icon: '🔍', label: 'Doc Recognition', href: '/static/recognition.html' },
            ]
        },
        {
            id: 'tools',
            title: '🔧 Tools',
            items: [
                { icon: '🧠', label: 'AI Assistant', href: '/static/brain.html' },
                { icon: '🗓️', label: 'Calendar', href: '/static/calendar.html' },
                { icon: '📇', label: 'Contacts', href: '/static/contacts.html' },
                { icon: '🔬', label: 'Research', href: '/static/research.html' },
                { icon: '⚖️', label: 'Legal Analysis', href: '/static/legal_analysis.html' },
                { icon: '💰', label: 'Funding Search', href: '/static/funding_search.html' },
            ]
        },
        {
            id: 'court',
            title: '💻 Zoom Court',
            items: [
                { icon: '📹', label: 'Zoom Helper', href: '/static/zoom_court.html' },
                { icon: '🎯', label: 'Hearing Prep', href: '/static/court_learning.html' },
                { icon: '👔', label: 'Court Etiquette', href: '/static/court_etiquette.html' },
            ]
        },
        {
            id: 'system',
            title: '⚙️ System',
            collapsed: true,
            items: [
                { icon: '🌐', label: 'Mesh Network', href: '/static/mesh_network.html' },
                { icon: '☁️', label: 'Cloud Storage', href: '/static/storage_setup.html' },
                { icon: '🔌', label: 'API Docs', href: '/api/docs', external: true },
            ]
        },
        {
            id: 'help',
            title: '❓ Help',
            items: [
                { icon: '📚', label: 'Help & Resources', href: '/static/help.html' },
                { icon: '🆘', label: 'Emergency Help', href: '/static/help.html#emergency' },
                { icon: '🔒', label: 'Privacy Policy', href: '/static/privacy.html' },
                { icon: '📊', label: 'Evaluation Report', href: '/static/evaluation_report.html' },
            ]
        },
    ],

    // Current page detection
    getCurrentPage() {
        return window.location.pathname;
    },

    // Check if item is active
    isActive(href) {
        const current = this.getCurrentPage();
        if (href === current) return true;
        // Also match without /static/ prefix
        if (href.replace('/static/', '/') === current) return true;
        if (current.includes(href.split('?')[0])) return true;
        return false;
    },

    // Generate HTML for a nav item
    renderItem(item) {
        const isActive = this.isActive(item.href);
        const target = item.external ? ' target="_blank"' : '';
        const activeClass = isActive ? ' active' : '';
        const badgeHtml = item.badge ? `<span class="nav-badge" id="${item.badge}">0</span>` : '';
        
        if (item.onclick) {
            return `
                <a href="#" class="nav-item${activeClass}" onclick="${item.onclick}; return false;">
                    <span class="nav-icon">${item.icon}</span>
                    <span class="nav-label">${item.label}</span>
                    ${badgeHtml}
                </a>
            `;
        }
        
        return `
            <a href="${item.href}" class="nav-item${activeClass}"${target}>
                <span class="nav-icon">${item.icon}</span>
                <span class="nav-label">${item.label}</span>
                ${badgeHtml}
            </a>
        `;
    },

    // Generate HTML for a section
    renderSection(section) {
        const collapsedClass = section.collapsed ? ' collapsed' : '';
        const itemsHtml = section.items.map(item => this.renderItem(item)).join('');
        
        return `
            <div class="nav-section${collapsedClass}" data-section="${section.id}">
                <div class="nav-section-header" onclick="SemptifyNav.toggleSection('${section.id}')">
                    <span class="nav-section-title">${section.title}</span>
                    <span class="nav-section-chevron">▼</span>
                </div>
                <div class="nav-section-items">
                    ${itemsHtml}
                </div>
            </div>
        `;
    },

    // Toggle section collapse
    toggleSection(sectionId) {
        const section = document.querySelector(`[data-section="${sectionId}"]`);
        if (section) {
            section.classList.toggle('collapsed');
            // Save state to localStorage
            const collapsed = JSON.parse(localStorage.getItem('semptify_nav_collapsed') || '{}');
            collapsed[sectionId] = section.classList.contains('collapsed');
            localStorage.setItem('semptify_nav_collapsed', JSON.stringify(collapsed));
        }
    },

    // Restore collapsed state from localStorage
    restoreCollapsedState() {
        const collapsed = JSON.parse(localStorage.getItem('semptify_nav_collapsed') || '{}');
        Object.keys(collapsed).forEach(sectionId => {
            if (collapsed[sectionId]) {
                const section = document.querySelector(`[data-section="${sectionId}"]`);
                if (section) section.classList.add('collapsed');
            }
        });
    },

    // Toggle mobile menu
    toggleMobile() {
        const sidebar = document.querySelector('.semptify-sidebar');
        const overlay = document.querySelector('.semptify-nav-overlay');
        if (sidebar) {
            sidebar.classList.toggle('open');
            overlay?.classList.toggle('open');
            document.body.classList.toggle('nav-open');
        }
    },

    // Close mobile menu
    closeMobile() {
        const sidebar = document.querySelector('.semptify-sidebar');
        const overlay = document.querySelector('.semptify-nav-overlay');
        sidebar?.classList.remove('open');
        overlay?.classList.remove('open');
        document.body.classList.remove('nav-open');
    },

    // Render the complete navigation
    render() {
        const sectionsHtml = this.sections.map(section => this.renderSection(section)).join('');
        
        return `
            <!-- Mobile Hamburger Button -->
            <button class="nav-hamburger" onclick="SemptifyNav.toggleMobile()" aria-label="Toggle navigation">
                <span class="hamburger-line"></span>
                <span class="hamburger-line"></span>
                <span class="hamburger-line"></span>
            </button>
            
            <!-- Mobile Overlay -->
            <div class="semptify-nav-overlay" onclick="SemptifyNav.closeMobile()"></div>
            
            <!-- Sidebar -->
            <nav class="semptify-sidebar">
                <div class="sidebar-header">
                    <a href="/static/dashboard.html" class="sidebar-logo">
                        <span class="logo-icon">⚖️</span>
                        <span class="logo-text">Semptify</span>
                    </a>
                    <button class="sidebar-close" onclick="SemptifyNav.closeMobile()">✕</button>
                </div>
                
                <div class="sidebar-content">
                    ${sectionsHtml}
                </div>
                
                <div class="sidebar-footer">
                    <div class="sidebar-version">v5.0.0</div>
                </div>
            </nav>
        `;
    },

    // Initialize the navigation
    init(containerId = 'semptify-nav') {
        const container = document.getElementById(containerId);
        if (!container) {
            console.warn('SemptifyNav: Container not found:', containerId);
            return;
        }

        // Inject CSS if not already present
        if (!document.getElementById('semptify-nav-styles')) {
            const link = document.createElement('link');
            link.id = 'semptify-nav-styles';
            link.rel = 'stylesheet';
            link.href = '/static/css/shared-nav.css';
            document.head.appendChild(link);
        }

        // Render navigation
        container.innerHTML = this.render();

        // Restore collapsed state
        this.restoreCollapsedState();

        // Close mobile nav on link click
        container.querySelectorAll('.nav-item').forEach(item => {
            item.addEventListener('click', () => {
                if (window.innerWidth <= 768) {
                    this.closeMobile();
                }
            });
        });

        // Close on escape key
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                this.closeMobile();
            }
        });

        console.log('✅ SemptifyNav initialized');
    }
};

// Auto-initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    if (document.getElementById('semptify-nav')) {
        SemptifyNav.init();
    }
});
