/**
 * Semptify Shared Navigation Component
 * Single source of truth for all navigation across the app
 * 
 * Usage: Add to any page:
 *   <div id="semptify-nav"></div>
 *   <script src="/static/js/shared-nav.js"></script>
 */

const SemptifyNav = {
    // =========================================================================
    // SIMPLIFIED 7-SECTION NAVIGATION (v3.0)
    // Logical workflow: Home → Intake → Timeline → Defense → Court → Tools → Vault
    // =========================================================================
    sections: [
        {
            id: 'home',
            title: '🏠 Home',
            items: [
                { icon: '🏠', label: 'Dashboard', href: '/static/home.html' },
                { icon: '📊', label: 'My Case', href: '/static/case.html' },
                { icon: '🆘', label: 'Crisis Help', href: '/static/crisis_intake.html' },
            ]
        },
        {
            id: 'intake',
            title: '📥 Step 1: Intake',
            items: [
                { icon: '📋', label: 'Upload Documents', href: '/static/document_intake.html' },
                { icon: '🔍', label: 'AI Recognition', href: '/static/recognition.html' },
                { icon: '💼', label: 'Briefcase', href: '/static/briefcase.html' },
            ]
        },
        {
            id: 'timeline',
            title: '📅 Step 2: Timeline',
            items: [
                { icon: '⚡', label: 'Auto-Build', href: '/static/timeline_auto_build.html' },
                { icon: '📅', label: 'View Timeline', href: '/static/timeline.html', badge: 'timelineCount' },
                { icon: '📆', label: 'Calendar', href: '/static/calendar.html' },
            ]
        },
        {
            id: 'defense',
            title: '⚖️ Step 3: Defense',
            items: [
                { icon: '📖', label: 'Law Library', href: '/static/law_library.html' },
                { icon: '📝', label: 'File Answer', href: '/static/eviction_answer.html' },
                { icon: '⚔️', label: 'Counterclaim', href: '/static/counterclaim.html' },
                { icon: '📋', label: 'File Motion', href: '/static/motions.html' },
            ]
        },
        {
            id: 'court',
            title: '🏛️ Step 4: Court',
            items: [
                { icon: '📦', label: 'Court Packet', href: '/static/court_packet.html' },
                { icon: '🎯', label: 'Hearing Prep', href: '/static/hearing_prep.html' },
                { icon: '💻', label: 'Zoom Court', href: '/static/zoom_court.html' },
            ]
        },
        {
            id: 'tools',
            title: '🔧 Tools',
            items: [
                { icon: '✉️', label: 'Letters', href: '/static/letter_builder.html' },
                { icon: '📝', label: 'Complaints', href: '/static/complaints.html' },
                { icon: '📇', label: 'Contacts', href: '/static/contacts.html' },
                { icon: '📬', label: 'Correspondence', href: '/static/correspondence.html' },
            ]
        },
        {
            id: 'vault',
            title: '📁 Vault',
            items: [
                { icon: '🔐', label: 'Document Vault', href: '/static/vault.html' },
                { icon: '📑', label: 'PDF Tools', href: '/static/pdf_tools.html' },
            ]
        },
        {
            id: 'settings',
            title: '⚙️ Settings',
            collapsed: true,
            items: [
                { icon: '☁️', label: 'Cloud Storage', href: '/static/storage_setup.html' },
                { icon: '❓', label: 'Help', href: '/static/help.html' },
                { icon: '🔒', label: 'Privacy', href: '/static/privacy.html' },
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

    // Toggle pinned/expanded state (desktop)
    togglePin() {
        const isPinned = document.body.classList.toggle('nav-pinned');
        const pinIcon = document.getElementById('pinIcon');
        if (pinIcon) {
            pinIcon.textContent = isPinned ? '◀' : '📌';
        }
        // Save preference
        localStorage.setItem('semptify_nav_pinned', isPinned ? 'true' : 'false');
    },

    // Restore pinned state from localStorage
    restorePinnedState() {
        const isPinned = localStorage.getItem('semptify_nav_pinned') === 'true';
        if (isPinned) {
            document.body.classList.add('nav-pinned');
            const pinIcon = document.getElementById('pinIcon');
            if (pinIcon) pinIcon.textContent = '◀';
        }
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
                <!-- Pin/Expand Toggle Button -->
                <button class="sidebar-toggle" onclick="SemptifyNav.togglePin()" title="Pin sidebar open">
                    <span id="pinIcon">📌</span>
                </button>
                <div class="sidebar-header">
                    <a href="/static/home.html" class="sidebar-logo">
                        <span class="logo-icon">⚖️</span>
                        <span class="logo-text">Semptify</span>
                    </a>
                    <button class="sidebar-close" onclick="SemptifyNav.closeMobile()">✕</button>
                </div>
                
                <div class="sidebar-content">
                    ${sectionsHtml}
                </div>
                
                <div class="sidebar-footer">
                    <!-- User Button -->
                    <button class="user-button" onclick="SemptifyNav.toggleUserPanel()" id="navUserButton">
                        <span class="user-avatar" id="navUserAvatar">👤</span>
                        <span class="user-info">
                            <span class="user-role" id="navUserRole">User</span>
                            <span class="user-storage" id="navUserStorage">Loading...</span>
                        </span>
                        <span class="user-chevron">▼</span>
                    </button>
                    <div class="sidebar-version">v5.0.0</div>
                </div>
            </nav>
            
            <!-- User Panel Popup -->
            <div class="user-panel-overlay" id="userPanelOverlay" onclick="SemptifyNav.closeUserPanel()"></div>
            <div class="user-panel" id="userPanel">
                <div class="user-panel-header">
                    <h3>👤 Account</h3>
                    <button class="user-panel-close" onclick="SemptifyNav.closeUserPanel()">✕</button>
                </div>
                <div class="user-panel-content">
                    <!-- User ID Section -->
                    <div class="user-panel-section">
                        <label>User ID</label>
                        <div class="user-id-display">
                            <code id="panelUserId">Loading...</code>
                            <button class="copy-btn" onclick="SemptifyNav.copyUserId()" title="Copy ID">📋</button>
                        </div>
                    </div>
                    
                    <!-- Role Section -->
                    <div class="user-panel-section">
                        <label>Role</label>
                        <div class="role-badge-large" id="panelUserRole">User</div>
                    </div>
                    
                    <!-- Storage Section -->
                    <div class="user-panel-section">
                        <label>Cloud Storage</label>
                        <div class="storage-status-box" id="panelStorageStatus">
                            <span class="storage-icon" id="panelStorageIcon">🔐</span>
                            <span class="storage-name" id="panelStorageName">Session Storage</span>
                            <span class="storage-dot disconnected" id="panelStorageDot"></span>
                        </div>
                        <p class="storage-hint" id="panelStorageHint">Connect cloud storage to sync your data across devices</p>
                    </div>
                    
                    <!-- Storage Actions -->
                    <div class="user-panel-actions">
                        <button class="btn-reconnect" id="btnReconnect" onclick="SemptifyNav.reconnectStorage()">
                            🔄 Reconnect Storage
                        </button>
                        <button class="btn-change-storage" onclick="SemptifyNav.changeStorage()">
                            ☁️ Change Storage Provider
                        </button>
                    </div>
                    
                    <!-- Session Info -->
                    <div class="user-panel-section session-info">
                        <label>Session</label>
                        <div class="session-details">
                            <div><span>Status:</span> <span id="panelSessionStatus" class="status-active">Active</span></div>
                            <div><span>Expires:</span> <span id="panelSessionExpires">--</span></div>
                        </div>
                    </div>
                </div>
                <div class="user-panel-footer">
                    <button class="btn-signout" onclick="SemptifyNav.signOut()">
                        🚪 Sign Out
                    </button>
                </div>
            </div>
        `;
    },

    // =================================================================
    // User Panel Functions
    // =================================================================
    
    userInfo: null,
    
    toggleUserPanel() {
        const panel = document.getElementById('userPanel');
        const overlay = document.getElementById('userPanelOverlay');
        if (panel && overlay) {
            const isOpen = panel.classList.contains('open');
            if (isOpen) {
                this.closeUserPanel();
            } else {
                panel.classList.add('open');
                overlay.classList.add('open');
                this.loadUserInfo();
            }
        }
    },
    
    closeUserPanel() {
        const panel = document.getElementById('userPanel');
        const overlay = document.getElementById('userPanelOverlay');
        panel?.classList.remove('open');
        overlay?.classList.remove('open');
    },
    
    getCookie(name) {
        const value = `; ${document.cookie}`;
        const parts = value.split(`; ${name}=`);
        if (parts.length === 2) return parts.pop().split(';').shift();
        return null;
    },
    
    parseUserId(userId) {
        if (!userId || userId.length < 3) return null;
        
        const PROVIDERS = {
            'G': { id: 'google_drive', name: 'Google Drive', icon: '🔵' },
            'D': { id: 'dropbox', name: 'Dropbox', icon: '💧' },
            'O': { id: 'onedrive', name: 'OneDrive', icon: '☁️' },
            'S': { id: 'session', name: 'Session Storage', icon: '🔐' }
        };
        
        const ROLES = {
            'U': { id: 'user', name: 'User' },
            'M': { id: 'manager', name: 'Manager' },
            'V': { id: 'advocate', name: 'Advocate' },
            'L': { id: 'legal', name: 'Legal' },
            'A': { id: 'admin', name: 'Admin' }
        };
        
        const providerChar = userId[0].toUpperCase();
        const roleChar = userId[1].toUpperCase();
        
        const provider = PROVIDERS[providerChar] || { id: 'unknown', name: 'Unknown', icon: '❓' };
        const role = ROLES[roleChar] || { id: 'user', name: 'User' };
        
        return {
            userId: userId,
            provider: provider.id,
            providerName: provider.name,
            providerIcon: provider.icon,
            role: role.id,
            roleName: role.name,
            isSession: providerChar === 'S',
            isConnected: ['G', 'D', 'O'].includes(providerChar)
        };
    },
    
    async loadUserInfo() {
        // Fetch from API since cookie is httponly
        try {
            const response = await fetch('/storage/status');
            const data = await response.json();
            console.log('📋 loadUserInfo - API response:', data);
            
            const userId = data.user_id;
            const parsed = this.parseUserId(userId);
            
            // Update panel elements
            document.getElementById('panelUserId').textContent = userId || 'Not set';
            
            if (parsed && data.authenticated) {
                document.getElementById('panelUserRole').textContent = parsed.roleName;
                document.getElementById('panelStorageIcon').textContent = parsed.providerIcon;
                document.getElementById('panelStorageName').textContent = parsed.providerName;
                
                const dot = document.getElementById('panelStorageDot');
                const hint = document.getElementById('panelStorageHint');
                const reconnectBtn = document.getElementById('btnReconnect');
                
                dot.classList.remove('disconnected');
                dot.classList.add('connected');
                hint.textContent = 'Your data is synced to the cloud';
                reconnectBtn.style.display = 'block';
                
                if (data.expires_at) {
                    const expires = new Date(data.expires_at);
                    document.getElementById('panelSessionExpires').textContent = expires.toLocaleString();
                }
                
                this.userInfo = { ...parsed, userId };
            } else {
                document.getElementById('panelStorageDot')?.classList.add('disconnected');
                document.getElementById('panelStorageHint').textContent = 'Connect cloud storage to sync your data';
                document.getElementById('btnReconnect').style.display = 'none';
            }
        } catch (e) {
            console.error('❌ loadUserInfo failed:', e);
            document.getElementById('panelUserId').textContent = 'Error loading';
        }
    },
    
    async updateNavUserButton() {
        // Cookie is httponly so we must fetch from API
        try {
            const response = await fetch('/storage/status');
            const data = await response.json();
            console.log('🔍 updateNavUserButton - API response:', data);
            
            if (data.authenticated && data.user_id) {
                const parsed = this.parseUserId(data.user_id);
                console.log('🔍 Parsed user ID:', parsed);
                
                if (parsed) {
                    const avatar = document.getElementById('navUserAvatar');
                    const role = document.getElementById('navUserRole');
                    const storage = document.getElementById('navUserStorage');
                    
                    if (avatar) avatar.textContent = parsed.providerIcon;
                    if (role) role.textContent = parsed.roleName;
                    if (storage) {
                        storage.textContent = parsed.providerName;
                        storage.className = 'user-storage connected';
                    }
                    console.log('✅ User button updated:', parsed.providerName, parsed.roleName);
                }
            } else {
                console.log('⚠️ Not authenticated - showing defaults');
                const storage = document.getElementById('navUserStorage');
                if (storage) storage.textContent = 'Not Connected';
            }
        } catch (e) {
            console.error('❌ Failed to fetch user status:', e);
            const storage = document.getElementById('navUserStorage');
            if (storage) storage.textContent = 'Error';
        }
    },
    
    copyUserId() {
        const userId = document.getElementById('panelUserId').textContent;
        navigator.clipboard.writeText(userId).then(() => {
            const btn = document.querySelector('.copy-btn');
            const original = btn.textContent;
            btn.textContent = '✓';
            setTimeout(() => btn.textContent = original, 1500);
        });
    },
    
    async reconnectStorage() {
        const parsed = this.userInfo;
        if (!parsed || !parsed.isConnected) return;
        
        const btn = document.getElementById('btnReconnect');
        btn.textContent = '🔄 Reconnecting...';
        btn.disabled = true;
        
        try {
            // Redirect to OAuth flow for current provider
            const providerMap = {
                'google_drive': '/storage/auth/google',
                'dropbox': '/storage/auth/dropbox',
                'onedrive': '/storage/auth/onedrive'
            };
            
            const authUrl = providerMap[parsed.provider];
            if (authUrl) {
                window.location.href = authUrl + '?redirect=' + encodeURIComponent(window.location.pathname);
            }
        } catch (e) {
            btn.textContent = '🔄 Reconnect Storage';
            btn.disabled = false;
            alert('Failed to reconnect. Please try again.');
        }
    },
    
    changeStorage() {
        window.location.href = '/static/storage_setup.html';
    },
    
    signOut() {
        if (confirm('Sign out and clear your session?')) {
            // Clear cookies
            document.cookie = 'semptify_uid=; path=/; expires=Thu, 01 Jan 1970 00:00:00 GMT';
            document.cookie = 'semptify_session=; path=/; expires=Thu, 01 Jan 1970 00:00:00 GMT';
            
            // Redirect to welcome
            window.location.href = '/static/welcome.html';
        }
    },

    // Initialize the navigation
    async init(containerId = 'semptify-nav') {
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
        
        // Restore pinned state (desktop)
        this.restorePinnedState();
        
        // Update user button from API (async)
        console.log('🔄 Calling updateNavUserButton...');
        await this.updateNavUserButton();

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
                this.closeUserPanel();
            }
        });

        console.log('✅ SemptifyNav initialized');
    }
};

// Auto-initialize when DOM is ready
document.addEventListener('DOMContentLoaded', async () => {
    if (document.getElementById('semptify-nav')) {
        await SemptifyNav.init();
    }
});
