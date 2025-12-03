/**
 * Semptify 5.0 - Adaptive UI Application
 * 
 * This isn't a static app - it builds itself based on what YOU need.
 * Upload a document, and the interface adapts. That's the magic.
 */

// ============================================================================
// State Management
// ============================================================================

const state = {
    user: {
        id: null,
        phase: 'active',
        documents: [],
    },
    widgets: [],
    documents: [],
    rights: [],
    timeline: [],
    loading: {
        widgets: false,
        documents: false,
        upload: false,
    },
    currentView: 'dashboard',
};

// ============================================================================
// API Functions
// ============================================================================

const API = {
    baseUrl: '/api',

    async fetch(endpoint, options = {}) {
        const headers = {
            'Content-Type': 'application/json',
            ...(state.user.id && { 'X-User-ID': state.user.id }),
            ...options.headers,
        };

        try {
            const response = await fetch(`${this.baseUrl}${endpoint}`, {
                ...options,
                headers,
            });

            if (!response.ok) {
                throw new Error(`API Error: ${response.status}`);
            }

            return await response.json();
        } catch (error) {
            console.error('API Error:', error);
            throw error;
        }
    },

    // Adaptive UI endpoints
    async getWidgets() {
        return this.fetch('/ui/widgets');
    },

    async getContext() {
        return this.fetch('/ui/context');
    },

    async dismissWidget(widgetId) {
        return this.fetch(`/ui/dismiss/${widgetId}`, { method: 'POST' });
    },

    async recordAction(action) {
        return this.fetch(`/ui/action/${action}`, { method: 'POST' });
    },

    async getPredictions() {
        return this.fetch('/ui/predictions');
    },

    // Document endpoints
    async uploadDocument(file) {
        const formData = new FormData();
        formData.append('file', file);

        const response = await fetch(`${this.baseUrl}/documents/upload`, {
            method: 'POST',
            headers: state.user.id ? { 'X-User-ID': state.user.id } : {},
            body: formData,
        });

        if (!response.ok) {
            throw new Error(`Upload failed: ${response.status}`);
        }

        return response.json();
    },

    async getDocuments() {
        return this.fetch('/documents/');
    },

    async getRights() {
        return this.fetch('/documents/rights/');
    },

    async getTimeline() {
        return this.fetch('/documents/timeline/');
    },

    async getLaws() {
        return this.fetch('/documents/laws/');
    },
};

// ============================================================================
// Widget Renderers
// ============================================================================

const WidgetRenderers = {
    /**
     * Render an alert widget (urgent, can't miss)
     */
    alert(widget) {
        return `
            <div class="widget widget-alert priority-${widget.priority}" data-widget-id="${widget.id}">
                <div class="widget-header">
                    <h3 class="widget-title">${widget.title}</h3>
                    ${widget.dismissible ? `<button class="dismiss-btn" onclick="UI.dismissWidget('${widget.id}')">&times;</button>` : ''}
                </div>
                <div class="widget-content">
                    <p class="alert-message">${widget.content.message}</p>
                    ${widget.content.steps ? `
                        <ul class="alert-steps">
                            ${widget.content.steps.map(step => `<li>${step}</li>`).join('')}
                        </ul>
                    ` : ''}
                </div>
                ${this.renderActions(widget.actions)}
                ${widget.reason ? `<div class="widget-reason">💡 ${widget.reason}</div>` : ''}
            </div>
        `;
    },

    /**
     * Render an action card (suggested action)
     */
    action_card(widget) {
        return `
            <div class="widget widget-action priority-${widget.priority}" data-widget-id="${widget.id}">
                <div class="widget-header">
                    <h3 class="widget-title">${widget.title}</h3>
                    ${widget.dismissible ? `<button class="dismiss-btn" onclick="UI.dismissWidget('${widget.id}')">&times;</button>` : ''}
                </div>
                <div class="widget-content">
                    <p>${widget.content.message}</p>
                    ${widget.content.tips ? `
                        <ul class="tips-list">
                            ${widget.content.tips.map(tip => `<li>✓ ${tip}</li>`).join('')}
                        </ul>
                    ` : ''}
                    ${widget.content.suggestions ? `
                        <ul class="suggestions-list">
                            ${widget.content.suggestions.map(s => `<li>• ${s}</li>`).join('')}
                        </ul>
                    ` : ''}
                    ${widget.content.why ? `<p class="why-text"><strong>Why:</strong> ${widget.content.why}</p>` : ''}
                </div>
                ${this.renderActions(widget.actions)}
                ${widget.reason ? `<div class="widget-reason">💡 ${widget.reason}</div>` : ''}
            </div>
        `;
    },

    /**
     * Render an info panel
     */
    info_panel(widget) {
        const colorClass = widget.content.color ? `color-${widget.content.color}` : '';
        return `
            <div class="widget widget-info ${colorClass} priority-${widget.priority}" data-widget-id="${widget.id}">
                <div class="widget-header">
                    <h3 class="widget-title">${widget.title}</h3>
                    ${widget.dismissible ? `<button class="dismiss-btn" onclick="UI.dismissWidget('${widget.id}')">&times;</button>` : ''}
                </div>
                <div class="widget-content">
                    <p class="info-message">${widget.content.message}</p>
                    ${widget.content.documents_count !== undefined ? `
                        <div class="stat-row">
                            <span class="stat-label">Documents:</span>
                            <span class="stat-value">${widget.content.documents_count}</span>
                        </div>
                    ` : ''}
                    ${widget.content.your_rights ? `
                        <ul class="rights-list">
                            ${widget.content.your_rights.map(r => `<li>⚖️ ${r}</li>`).join('')}
                        </ul>
                    ` : ''}
                    ${widget.content.check_points ? `
                        <ul class="check-points">
                            ${widget.content.check_points.map(c => `<li>☐ ${c}</li>`).join('')}
                        </ul>
                    ` : ''}
                </div>
                ${this.renderActions(widget.actions)}
            </div>
        `;
    },

    /**
     * Render a checklist widget
     */
    checklist(widget) {
        return `
            <div class="widget widget-checklist priority-${widget.priority}" data-widget-id="${widget.id}">
                <div class="widget-header">
                    <h3 class="widget-title">${widget.title}</h3>
                    ${widget.dismissible ? `<button class="dismiss-btn" onclick="UI.dismissWidget('${widget.id}')">&times;</button>` : ''}
                </div>
                <div class="widget-content">
                    <p>${widget.content.message}</p>
                    <ul class="checklist">
                        ${widget.content.items.map(item => `
                            <li class="${item.checked ? 'checked' : ''}">
                                <span class="check-icon">${item.checked ? '✓' : '○'}</span>
                                ${item.text}
                            </li>
                        `).join('')}
                    </ul>
                </div>
                ${this.renderActions(widget.actions)}
                ${widget.reason ? `<div class="widget-reason">💡 ${widget.reason}</div>` : ''}
            </div>
        `;
    },

    /**
     * Render a document request widget
     */
    doc_request(widget) {
        return `
            <div class="widget widget-doc-request priority-${widget.priority}" data-widget-id="${widget.id}">
                <div class="widget-header">
                    <h3 class="widget-title">${widget.title}</h3>
                    ${widget.dismissible ? `<button class="dismiss-btn" onclick="UI.dismissWidget('${widget.id}')">&times;</button>` : ''}
                </div>
                <div class="widget-content">
                    <p>${widget.content.message}</p>
                    <ul class="missing-docs">
                        ${widget.content.missing.map(doc => `<li>📄 ${doc}</li>`).join('')}
                    </ul>
                </div>
                ${this.renderActions(widget.actions)}
            </div>
        `;
    },

    /**
     * Render warning widget
     */
    warning(widget) {
        return `
            <div class="widget widget-warning priority-${widget.priority}" data-widget-id="${widget.id}">
                <div class="widget-header">
                    <h3 class="widget-title">⚠️ ${widget.title}</h3>
                    ${widget.dismissible ? `<button class="dismiss-btn" onclick="UI.dismissWidget('${widget.id}')">&times;</button>` : ''}
                </div>
                <div class="widget-content">
                    <p>${widget.content.message}</p>
                </div>
                ${this.renderActions(widget.actions)}
            </div>
        `;
    },

    /**
     * Render action buttons for a widget
     */
    renderActions(actions) {
        if (!actions || actions.length === 0) return '';
        
        return `
            <div class="widget-actions">
                ${actions.map(action => `
                    <button class="action-btn" onclick="UI.handleAction('${action.action}')">
                        ${action.label}
                    </button>
                `).join('')}
            </div>
        `;
    },

    /**
     * Render any widget by type
     */
    render(widget) {
        const renderer = this[widget.type];
        if (renderer) {
            return renderer.call(this, widget);
        }
        // Fallback for unknown types
        return this.info_panel(widget);
    },
};

// ============================================================================
// UI Controller
// ============================================================================

const UI = {
    /**
     * Initialize the application
     */
    async init() {
        console.log('🏠 Semptify 5.0 - Initializing Adaptive UI');
        
        // Generate or restore user ID
        this.initUser();
        
        // Set up event listeners
        this.setupEventListeners();
        
        // Load initial data
        await this.loadWidgets();
        
        // Show dashboard by default
        this.showView('dashboard');
        
        console.log('✅ Semptify ready');
    },

    /**
     * Initialize user (generate ID if needed)
     */
    initUser() {
        let userId = localStorage.getItem('semptify_user_id');
        if (!userId) {
            // Generate a simple user ID
            userId = 'U' + Math.random().toString(36).substring(2, 10).toUpperCase();
            localStorage.setItem('semptify_user_id', userId);
        }
        state.user.id = userId;
        
        // Update UI with user ID
        const userIdEl = document.getElementById('user-id');
        if (userIdEl) {
            userIdEl.textContent = userId;
        }
    },

    /**
     * Set up event listeners
     */
    setupEventListeners() {
        // Navigation
        document.querySelectorAll('.nav-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const view = e.target.dataset.view;
                if (view) this.showView(view);
            });
        });

        // Upload zone
        const uploadZone = document.getElementById('upload-zone');
        const fileInput = document.getElementById('file-input');

        if (uploadZone && fileInput) {
            // Click to upload
            uploadZone.addEventListener('click', () => fileInput.click());

            // Drag and drop
            uploadZone.addEventListener('dragover', (e) => {
                e.preventDefault();
                uploadZone.classList.add('dragover');
            });

            uploadZone.addEventListener('dragleave', () => {
                uploadZone.classList.remove('dragover');
            });

            uploadZone.addEventListener('drop', (e) => {
                e.preventDefault();
                uploadZone.classList.remove('dragover');
                const files = e.dataTransfer.files;
                if (files.length > 0) {
                    this.handleFileUpload(files[0]);
                }
            });

            // File input change
            fileInput.addEventListener('change', (e) => {
                if (e.target.files.length > 0) {
                    this.handleFileUpload(e.target.files[0]);
                }
            });
        }
    },

    /**
     * Show a specific view
     */
    showView(viewName) {
        state.currentView = viewName;
        
        // Update navigation
        document.querySelectorAll('.nav-btn').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.view === viewName);
        });

        // Update content based on view
        switch (viewName) {
            case 'dashboard':
                this.loadWidgets();
                break;
            case 'documents':
                this.loadDocuments();
                break;
            case 'upload':
                this.showUploadView();
                break;
            case 'rights':
                this.loadRights();
                break;
            case 'timeline':
                this.loadTimeline();
                break;
        }
    },

    /**
     * Load and render adaptive widgets
     */
    async loadWidgets() {
        state.loading.widgets = true;
        this.showLoading('Loading your personalized dashboard...');

        try {
            const response = await API.getWidgets();
            state.widgets = response.widgets || [];
            this.renderWidgets();
        } catch (error) {
            this.showError('Could not load dashboard. Please try again.');
        } finally {
            state.loading.widgets = false;
        }
    },

    /**
     * Render widgets to the main content area
     */
    renderWidgets() {
        const content = document.getElementById('main-content');
        if (!content) return;

        if (state.widgets.length === 0) {
            content.innerHTML = `
                <div class="empty-state">
                    <div class="empty-icon">📋</div>
                    <h2>Welcome to Semptify</h2>
                    <p>Upload your first document and watch the interface build itself around your needs.</p>
                    <button class="btn btn-primary" onclick="UI.showView('upload')">
                        Upload Document
                    </button>
                </div>
            `;
            return;
        }

        const widgetsHtml = state.widgets.map(widget => 
            WidgetRenderers.render(widget)
        ).join('');

        content.innerHTML = `
            <div class="widgets-grid">
                ${widgetsHtml}
            </div>
        `;
    },

    /**
     * Dismiss a widget
     */
    async dismissWidget(widgetId) {
        try {
            await API.dismissWidget(widgetId);
            state.widgets = state.widgets.filter(w => w.id !== widgetId);
            this.renderWidgets();
        } catch (error) {
            console.error('Failed to dismiss widget:', error);
        }
    },

    /**
     * Handle an action from a widget
     */
    async handleAction(action) {
        console.log('Action:', action);
        
        // Record the action for learning
        API.recordAction(action).catch(() => {});

        // Handle different actions
        switch (action) {
            case 'upload_document':
                this.showView('upload');
                break;
            case 'show_eviction_rights':
            case 'show_habitability_rights':
            case 'show_rent_laws':
                this.showView('rights');
                break;
            case 'find_legal_aid':
                window.open('https://www.lawhelp.org/', '_blank');
                break;
            case 'letter_builder':
            case 'repair_letter':
            case 'repair_followup_letter':
            case 'deposit_demand_letter':
                this.showLetterBuilder(action);
                break;
            case 'photo_checklist':
                this.showPhotoChecklist();
                break;
            default:
                console.log('Unhandled action:', action);
        }
    },

    /**
     * Show the upload view
     */
    showUploadView() {
        const content = document.getElementById('main-content');
        if (!content) return;

        content.innerHTML = `
            <div class="upload-section">
                <h2>Upload Document</h2>
                <p class="upload-description">
                    Upload any document related to your tenancy. Semptify will analyze it,
                    identify what it is, and build your case accordingly.
                </p>
                
                <div id="upload-zone" class="upload-zone">
                    <div class="upload-icon">📄</div>
                    <div class="upload-text">
                        <strong>Drop your document here</strong>
                        <span>or click to browse</span>
                    </div>
                    <div class="upload-hint">
                        Supports: PDF, Images, Word documents
                    </div>
                </div>
                <input type="file" id="file-input" hidden accept=".pdf,.doc,.docx,.jpg,.jpeg,.png,.gif">
                
                <div id="upload-status" class="upload-status"></div>
                
                <div class="document-suggestions">
                    <h3>Suggested Documents</h3>
                    <div class="suggestion-cards">
                        <div class="suggestion-card" onclick="document.getElementById('file-input').click()">
                            <span class="card-icon">📝</span>
                            <span class="card-title">Lease Agreement</span>
                        </div>
                        <div class="suggestion-card" onclick="document.getElementById('file-input').click()">
                            <span class="card-icon">💰</span>
                            <span class="card-title">Rent Receipt</span>
                        </div>
                        <div class="suggestion-card" onclick="document.getElementById('file-input').click()">
                            <span class="card-icon">📸</span>
                            <span class="card-title">Condition Photos</span>
                        </div>
                        <div class="suggestion-card" onclick="document.getElementById('file-input').click()">
                            <span class="card-icon">✉️</span>
                            <span class="card-title">Landlord Communication</span>
                        </div>
                    </div>
                </div>
            </div>
        `;

        // Re-setup upload listeners
        this.setupEventListeners();
    },

    /**
     * Handle file upload
     */
    async handleFileUpload(file) {
        const statusEl = document.getElementById('upload-status');
        const uploadZone = document.getElementById('upload-zone');
        
        if (statusEl) {
            statusEl.innerHTML = `
                <div class="upload-progress">
                    <div class="spinner"></div>
                    <span>Analyzing "${file.name}"...</span>
                </div>
            `;
        }

        if (uploadZone) {
            uploadZone.classList.add('uploading');
        }

        try {
            const result = await API.uploadDocument(file);
            
            if (statusEl) {
                statusEl.innerHTML = `
                    <div class="upload-success">
                        <span class="success-icon">✓</span>
                        <div class="success-details">
                            <strong>Document Analyzed</strong>
                            <p>Type: ${result.document?.type || 'Document'}</p>
                            <p>Status: ${result.document?.status || 'Processed'}</p>
                            ${result.document?.law_references?.length ? `
                                <p class="law-refs">
                                    📚 ${result.document.law_references.length} applicable laws identified
                                </p>
                            ` : ''}
                        </div>
                    </div>
                `;
            }

            // Refresh the dashboard after successful upload
            setTimeout(() => {
                this.showView('dashboard');
            }, 2000);

        } catch (error) {
            if (statusEl) {
                statusEl.innerHTML = `
                    <div class="upload-error">
                        <span class="error-icon">✕</span>
                        <span>Upload failed. Please try again.</span>
                    </div>
                `;
            }
        } finally {
            if (uploadZone) {
                uploadZone.classList.remove('uploading');
            }
        }
    },

    /**
     * Load and display documents
     */
    async loadDocuments() {
        const content = document.getElementById('main-content');
        if (!content) return;

        this.showLoading('Loading your documents...');

        try {
            const response = await API.getDocuments();
            state.documents = response.documents || [];
            this.renderDocuments();
        } catch (error) {
            this.showError('Could not load documents.');
        }
    },

    /**
     * Render documents list
     */
    renderDocuments() {
        const content = document.getElementById('main-content');
        if (!content) return;

        if (state.documents.length === 0) {
            content.innerHTML = `
                <div class="empty-state">
                    <div class="empty-icon">📁</div>
                    <h2>No Documents Yet</h2>
                    <p>Upload your first document to start building your case.</p>
                    <button class="btn btn-primary" onclick="UI.showView('upload')">
                        Upload Document
                    </button>
                </div>
            `;
            return;
        }

        const docsHtml = state.documents.map(doc => `
            <div class="document-card">
                <div class="doc-icon">${this.getDocIcon(doc.type)}</div>
                <div class="doc-info">
                    <h4>${doc.filename || 'Document'}</h4>
                    <span class="doc-type">${doc.type}</span>
                    <span class="doc-date">${new Date(doc.uploaded_at).toLocaleDateString()}</span>
                </div>
                <div class="doc-status status-${doc.status}">${doc.status}</div>
                ${doc.law_references?.length ? `
                    <div class="doc-laws">
                        <span class="laws-count">${doc.law_references.length} laws</span>
                    </div>
                ` : ''}
            </div>
        `).join('');

        content.innerHTML = `
            <div class="documents-section">
                <div class="section-header">
                    <h2>Your Documents</h2>
                    <button class="btn btn-primary" onclick="UI.showView('upload')">
                        + Add Document
                    </button>
                </div>
                <div class="documents-list">
                    ${docsHtml}
                </div>
            </div>
        `;
    },

    /**
     * Load and display rights
     */
    async loadRights() {
        const content = document.getElementById('main-content');
        if (!content) return;

        this.showLoading('Loading your rights...');

        try {
            const [rightsResponse, lawsResponse] = await Promise.all([
                API.getRights(),
                API.getLaws(),
            ]);

            state.rights = rightsResponse.rights || [];
            this.renderRights(lawsResponse.laws || []);
        } catch (error) {
            this.showError('Could not load rights information.');
        }
    },

    /**
     * Render rights panel
     */
    renderRights(laws) {
        const content = document.getElementById('main-content');
        if (!content) return;

        const lawsHtml = laws.map(law => `
            <div class="law-card">
                <div class="law-header">
                    <span class="law-category">${law.category}</span>
                    <span class="law-jurisdiction">${law.jurisdiction || 'General'}</span>
                </div>
                <h4>${law.title}</h4>
                <p>${law.summary}</p>
                ${law.key_points?.length ? `
                    <ul class="key-points">
                        ${law.key_points.map(point => `<li>${point}</li>`).join('')}
                    </ul>
                ` : ''}
            </div>
        `).join('');

        const rightsHtml = state.rights.map(right => `
            <div class="right-item">
                <span class="right-icon">⚖️</span>
                <span>${right}</span>
            </div>
        `).join('');

        content.innerHTML = `
            <div class="rights-section">
                <h2>Your Tenant Rights</h2>
                <p class="rights-intro">
                    Based on your documents and situation, here are the laws and rights
                    that apply to you.
                </p>
                
                ${state.rights.length ? `
                    <div class="rights-summary">
                        <h3>Key Rights</h3>
                        <div class="rights-list">
                            ${rightsHtml}
                        </div>
                    </div>
                ` : ''}
                
                <div class="laws-grid">
                    ${lawsHtml || '<p class="no-laws">Upload documents to see applicable laws.</p>'}
                </div>
            </div>
        `;
    },

    /**
     * Load and display timeline
     */
    async loadTimeline() {
        const content = document.getElementById('main-content');
        if (!content) return;

        this.showLoading('Loading timeline...');

        try {
            const response = await API.getTimeline();
            state.timeline = response.timeline || [];
            this.renderTimeline();
        } catch (error) {
            this.showError('Could not load timeline.');
        }
    },

    /**
     * Render timeline
     */
    renderTimeline() {
        const content = document.getElementById('main-content');
        if (!content) return;

        if (state.timeline.length === 0) {
            content.innerHTML = `
                <div class="empty-state">
                    <div class="empty-icon">📅</div>
                    <h2>No Timeline Events</h2>
                    <p>Your timeline will build as you add documents and events.</p>
                    <button class="btn btn-primary" onclick="UI.showView('upload')">
                        Upload Document
                    </button>
                </div>
            `;
            return;
        }

        const timelineHtml = state.timeline.map(event => `
            <div class="timeline-event">
                <div class="event-date">
                    ${new Date(event.date).toLocaleDateString()}
                </div>
                <div class="event-content">
                    <div class="event-type">${event.type}</div>
                    <h4>${event.title}</h4>
                    <p>${event.description || ''}</p>
                </div>
            </div>
        `).join('');

        content.innerHTML = `
            <div class="timeline-section">
                <h2>Your Tenancy Timeline</h2>
                <p class="timeline-intro">
                    A chronological view of everything in your tenancy.
                    This timeline can be used as evidence if needed.
                </p>
                <div class="timeline">
                    ${timelineHtml}
                </div>
            </div>
        `;
    },

    /**
     * Show letter builder modal
     */
    showLetterBuilder(type) {
        alert(`Letter builder for "${type}" coming soon!\n\nThis will generate professional letters to your landlord based on your situation.`);
    },

    /**
     * Show photo checklist
     */
    showPhotoChecklist() {
        const content = document.getElementById('main-content');
        if (!content) return;

        content.innerHTML = `
            <div class="checklist-section">
                <h2>📸 Move-In Photo Checklist</h2>
                <p>Take photos of these areas to protect your security deposit:</p>
                
                <div class="photo-checklist">
                    ${[
                        'All walls in each room (look for marks, holes, damage)',
                        'All floors/carpets (stains, wear, damage)',
                        'All windows (cracks, screens, locks)',
                        'Kitchen appliances (inside and out)',
                        'Bathroom fixtures (tub, toilet, sink)',
                        'All closets and storage areas',
                        'Light fixtures and switches',
                        'Doors and door frames',
                        'Outdoor areas (patio, yard)',
                        'Any existing damage you notice'
                    ].map(item => `
                        <label class="checklist-item">
                            <input type="checkbox">
                            <span>${item}</span>
                        </label>
                    `).join('')}
                </div>
                
                <div class="photo-tips">
                    <h3>Photo Tips</h3>
                    <ul>
                        <li>Include something showing the date (newspaper, phone screen)</li>
                        <li>Take wide shots AND close-ups of any damage</li>
                        <li>Note the address and date in your photo app</li>
                        <li>Upload to Semptify immediately for timestamped proof</li>
                    </ul>
                </div>
                
                <button class="btn btn-primary" onclick="UI.showView('upload')">
                    Upload Photos Now
                </button>
            </div>
        `;
    },

    /**
     * Get icon for document type
     */
    getDocIcon(type) {
        const icons = {
            'lease': '📝',
            'rent_receipt': '💰',
            'photo_evidence': '📸',
            'repair_request': '🔧',
            'communication': '✉️',
            'notice': '📋',
            'eviction': '⚠️',
            'unknown': '📄',
        };
        return icons[type] || icons['unknown'];
    },

    /**
     * Show loading state
     */
    showLoading(message = 'Loading...') {
        const content = document.getElementById('main-content');
        if (content) {
            content.innerHTML = `
                <div class="loading-state">
                    <div class="spinner"></div>
                    <p>${message}</p>
                </div>
            `;
        }
    },

    /**
     * Show error state
     */
    showError(message) {
        const content = document.getElementById('main-content');
        if (content) {
            content.innerHTML = `
                <div class="error-state">
                    <div class="error-icon">⚠️</div>
                    <p>${message}</p>
                    <button class="btn" onclick="UI.loadWidgets()">Try Again</button>
                </div>
            `;
        }
    },
};

// ============================================================================
// Initialize on load
// ============================================================================

document.addEventListener('DOMContentLoaded', () => {
    UI.init();
});
