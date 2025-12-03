/**
 * ELBOW — Real-time Tenant Rights Assistant
 * Professional, smooth, helpful interface powered by Context Data Loop
 */

class Elbow {
    constructor() {
        this.state = {
            intensity: 0,
            phase: 'onboarding',
            events: [],
            deadlines: [],
            documents: [],
            widgets: [],
            issues: [],
            predictions: []
        };
        
        this.pollInterval = null;
        this.init();
    }

    async init() {
        // Bind UI elements
        this.bindElements();
        this.bindEvents();
        
        // Start real-time updates
        await this.refresh();
        this.startPolling();
        
        console.log('🦾 Elbow initialized');
    }

    bindElements() {
        // Header
        this.intensityFill = document.getElementById('intensity-fill');
        this.intensityLabel = document.getElementById('intensity-label');
        this.notificationDot = document.getElementById('notification-dot');
        
        // Left panel
        this.phaseBadge = document.getElementById('phase-badge');
        this.situationSummary = document.getElementById('situation-summary');
        this.timeline = document.getElementById('timeline');
        this.deadlines = document.getElementById('deadlines');
        
        // Center
        this.urgentAlert = document.getElementById('urgent-alert');
        this.alertTitle = document.getElementById('alert-title');
        this.alertMessage = document.getElementById('alert-message');
        this.welcomeState = document.getElementById('welcome-state');
        this.widgetsContainer = document.getElementById('widgets-container');
        this.userInput = document.getElementById('user-input');
        this.fileInput = document.getElementById('file-input');
        
        // Right panel
        this.nextSteps = document.getElementById('next-steps');
        this.rightsList = document.getElementById('rights-list');
        this.documentsList = document.getElementById('documents-list');
        
        // Modal
        this.modalOverlay = document.getElementById('modal-overlay');
        this.modalContent = document.getElementById('modal-content');
        
        // Toast
        this.toastContainer = document.getElementById('toast-container');
    }

    bindEvents() {
        // Quick action cards
        document.querySelectorAll('.action-card').forEach(card => {
            card.addEventListener('click', (e) => this.handleQuickAction(e.currentTarget.dataset.action));
        });
        
        // Input
        document.getElementById('btn-send').addEventListener('click', () => this.handleInput());
        this.userInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') this.handleInput();
        });
        
        // File upload
        document.getElementById('btn-attach').addEventListener('click', () => this.fileInput.click());
        this.fileInput.addEventListener('change', (e) => this.handleFileUpload(e));
        
        // Drag and drop
        const dropZone = document.getElementById('main-content');
        dropZone.addEventListener('dragover', (e) => {
            e.preventDefault();
            dropZone.classList.add('drag-over');
        });
        dropZone.addEventListener('dragleave', () => dropZone.classList.remove('drag-over'));
        dropZone.addEventListener('drop', (e) => this.handleDrop(e));
        
        // Modal
        document.getElementById('modal-close').addEventListener('click', () => this.closeModal());
        this.modalOverlay.addEventListener('click', (e) => {
            if (e.target === this.modalOverlay) this.closeModal();
        });
        
        // Alert action
        document.getElementById('alert-action').addEventListener('click', () => this.handleUrgentAction());
    }

    startPolling() {
        // Poll every 3 seconds for real-time updates
        this.pollInterval = setInterval(() => this.refresh(), 3000);
    }

    async refresh() {
        try {
            const [stateRes, widgetsRes] = await Promise.all([
                fetch('/api/core/state'),
                fetch('/api/ui/widgets')
            ]);
            
            if (stateRes.ok) {
                const stateData = await stateRes.json();
                this.updateState(stateData);
            }
            
            if (widgetsRes.ok) {
                const widgetsData = await widgetsRes.json();
                this.state.widgets = widgetsData.widgets || [];
                this.renderWidgets();
            }
        } catch (err) {
            console.warn('Refresh failed:', err);
        }
    }

    updateState(data) {
        // Update intensity
        if (data.intensity !== undefined) {
            this.state.intensity = data.intensity.overall || data.intensity;
            this.updateIntensityDisplay();
        }
        
        // Update phase
        if (data.phase) {
            this.state.phase = data.phase;
            this.updatePhaseDisplay();
        }
        
        // Update events timeline
        if (data.events) {
            this.state.events = data.events;
            this.renderTimeline();
        }
        
        // Update deadlines
        if (data.deadlines) {
            this.state.deadlines = data.deadlines;
            this.renderDeadlines();
        }
        
        // Update documents
        if (data.documents) {
            this.state.documents = data.documents;
            this.renderDocuments();
        }
        
        // Update predictions/next steps
        if (data.predictions) {
            this.state.predictions = data.predictions;
            this.renderNextSteps();
        }
        
        // Update rights at risk
        if (data.rights_at_risk) {
            this.renderRights(data.rights_at_risk);
        }
        
        // Update situation summary
        if (data.summary) {
            this.situationSummary.textContent = data.summary;
        }
        
        // Show/hide urgent alert
        if (this.state.intensity >= 70) {
            this.showUrgentAlert(data);
        } else {
            this.urgentAlert.style.display = 'none';
        }
        
        // Show widgets or welcome state
        if (this.state.events && this.state.events.length > 0) {
            this.welcomeState.style.display = 'none';
            this.widgetsContainer.style.display = 'flex';
        }
    }

    updateIntensityDisplay() {
        const intensity = this.state.intensity;
        this.intensityFill.style.width = `${intensity}%`;
        
        // Color gradient based on intensity
        let color, label;
        if (intensity < 20) {
            color = 'var(--intensity-0)';
            label = 'Calm';
        } else if (intensity < 40) {
            color = 'var(--intensity-20)';
            label = 'Active';
        } else if (intensity < 60) {
            color = 'var(--intensity-40)';
            label = 'Attention';
        } else if (intensity < 80) {
            color = 'var(--intensity-60)';
            label = 'Urgent';
        } else {
            color = 'var(--intensity-100)';
            label = 'Critical';
        }
        
        this.intensityFill.style.background = color;
        this.intensityLabel.textContent = label;
        
        // Notification dot for high intensity
        this.notificationDot.style.display = intensity >= 60 ? 'block' : 'none';
    }

    updatePhaseDisplay() {
        const phaseLabels = {
            'onboarding': 'Getting Started',
            'pre_move_in': 'Pre Move-In',
            'active': 'Active Tenancy',
            'issue_emerging': 'Issue Emerging',
            'dispute': 'Dispute Active',
            'eviction': 'Eviction Process',
            'move_out': 'Move Out',
            'post_tenancy': 'Post-Tenancy'
        };
        
        this.phaseBadge.textContent = phaseLabels[this.state.phase] || this.state.phase;
        
        // Style based on severity
        this.phaseBadge.className = 'phase-badge';
        if (['eviction', 'dispute'].includes(this.state.phase)) {
            this.phaseBadge.classList.add('danger');
        } else if (['issue_emerging'].includes(this.state.phase)) {
            this.phaseBadge.classList.add('warning');
        } else if (['post_tenancy'].includes(this.state.phase)) {
            this.phaseBadge.classList.add('success');
        }
    }

    renderTimeline() {
        if (!this.state.events || this.state.events.length === 0) {
            this.timeline.innerHTML = '<div class="timeline-empty">No events yet</div>';
            return;
        }
        
        // Show last 5 events, newest first
        const events = [...this.state.events].reverse().slice(0, 5);
        
        this.timeline.innerHTML = events.map(event => {
            const severity = event.severity || 'info';
            const date = this.formatDate(event.timestamp);
            return `
                <div class="timeline-item ${severity === 'critical' ? 'danger' : severity === 'high' ? 'warning' : ''}">
                    <div class="timeline-date">${date}</div>
                    <div class="timeline-text">${event.description || event.event_type}</div>
                </div>
            `;
        }).join('');
    }

    renderDeadlines() {
        if (!this.state.deadlines || this.state.deadlines.length === 0) {
            this.deadlines.innerHTML = '<div class="no-deadlines">No upcoming deadlines</div>';
            return;
        }
        
        this.deadlines.innerHTML = this.state.deadlines.map(deadline => {
            const daysUntil = this.daysUntil(deadline.date);
            const urgency = daysUntil <= 3 ? 'urgent' : daysUntil <= 7 ? 'soon' : '';
            const icon = deadline.type === 'court' ? '⚖️' : deadline.type === 'response' ? '📝' : '📅';
            
            return `
                <div class="deadline-item ${urgency}">
                    <span class="deadline-icon">${icon}</span>
                    <div class="deadline-info">
                        <div class="deadline-title">${deadline.title}</div>
                        <div class="deadline-date">${this.formatDate(deadline.date)}</div>
                    </div>
                    <span class="deadline-days">${daysUntil}d</span>
                </div>
            `;
        }).join('');
    }

    renderDocuments() {
        if (!this.state.documents || this.state.documents.length === 0) {
            this.documentsList.innerHTML = '<div class="no-documents">No documents uploaded yet</div>';
            return;
        }
        
        this.documentsList.innerHTML = this.state.documents.map(doc => {
            const icon = doc.type === 'lease' ? '📄' : doc.type === 'notice' ? '📬' : '📎';
            return `
                <div class="doc-item" data-id="${doc.id}">
                    <span class="doc-icon">${icon}</span>
                    <div class="doc-info">
                        <div class="doc-name">${doc.filename || doc.type}</div>
                        <div class="doc-date">${this.formatDate(doc.timestamp)}</div>
                    </div>
                </div>
            `;
        }).join('');
    }

    renderNextSteps() {
        if (!this.state.predictions || this.state.predictions.length === 0) {
            return;
        }
        
        this.nextSteps.innerHTML = this.state.predictions.slice(0, 3).map((step, i) => {
            const completed = step.completed || false;
            const suggested = i === 0 && !completed;
            
            return `
                <div class="step-item ${completed ? 'completed' : ''} ${suggested ? 'suggested' : ''}">
                    <span class="step-icon">${completed ? '' : i + 1}</span>
                    <span class="step-text">${step.action || step}</span>
                </div>
            `;
        }).join('');
    }

    renderRights(rightsAtRisk) {
        const baseRights = [
            { text: 'Right to habitable housing', atRisk: false },
            { text: 'Protection from retaliation', atRisk: false },
            { text: 'Proper notice requirements', atRisk: false },
            { text: 'Right to due process', atRisk: false }
        ];
        
        // Mark at-risk rights
        if (rightsAtRisk && rightsAtRisk.length > 0) {
            rightsAtRisk.forEach(risk => {
                const right = baseRights.find(r => r.text.toLowerCase().includes(risk.toLowerCase()));
                if (right) right.atRisk = true;
            });
        }
        
        this.rightsList.innerHTML = baseRights.map(right => `
            <div class="right-item ${right.atRisk ? 'at-risk' : ''}">
                <span class="right-icon">${right.atRisk ? '⚠' : '✓'}</span>
                <span class="right-text">${right.text}</span>
            </div>
        `).join('');
    }

    renderWidgets() {
        if (!this.state.widgets || this.state.widgets.length === 0) {
            return;
        }
        
        this.widgetsContainer.innerHTML = this.state.widgets.map(widget => {
            return this.renderWidget(widget);
        }).join('');
        
        // Bind widget action buttons
        this.widgetsContainer.querySelectorAll('[data-widget-action]').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const action = e.currentTarget.dataset.widgetAction;
                const widgetId = e.currentTarget.closest('.widget').dataset.widgetId;
                this.handleWidgetAction(widgetId, action);
            });
        });
    }

    renderWidget(widget) {
        const priorityClass = widget.priority || 'medium';
        const typeClass = widget.type === 'alert' ? 'alert' : 
                         widget.type === 'warning' ? 'warning' :
                         widget.type === 'info' ? 'info' : '';
        
        let content = '';
        
        switch (widget.type) {
            case 'checklist':
                content = this.renderChecklistWidget(widget);
                break;
            case 'action_card':
                content = this.renderActionWidget(widget);
                break;
            default:
                content = `<div class="widget-body">${widget.content || widget.description || ''}</div>`;
        }
        
        return `
            <div class="widget ${typeClass}" data-widget-id="${widget.id}">
                <div class="widget-header">
                    <div>
                        <div class="widget-title">${widget.title}</div>
                        ${widget.subtitle ? `<div class="widget-subtitle">${widget.subtitle}</div>` : ''}
                    </div>
                    <span class="widget-priority ${priorityClass}">${priorityClass}</span>
                </div>
                ${content}
                ${widget.actions ? this.renderWidgetActions(widget.actions) : ''}
            </div>
        `;
    }

    renderChecklistWidget(widget) {
        const items = widget.items || [];
        return `
            <div class="checklist-items">
                ${items.map((item, i) => `
                    <div class="checklist-item ${item.completed ? 'completed' : ''}" data-index="${i}">
                        <span class="checklist-checkbox">${item.completed ? '✓' : ''}</span>
                        <span class="checklist-text">${item.text || item}</span>
                    </div>
                `).join('')}
            </div>
        `;
    }

    renderActionWidget(widget) {
        return `
            <div class="widget-body">${widget.description || ''}</div>
        `;
    }

    renderWidgetActions(actions) {
        return `
            <div class="widget-actions">
                ${actions.map(action => `
                    <button class="btn ${action.primary ? 'btn-primary' : 'btn-secondary'}" 
                            data-widget-action="${action.action}">
                        ${action.label}
                    </button>
                `).join('')}
            </div>
        `;
    }

    showUrgentAlert(data) {
        this.urgentAlert.style.display = 'flex';
        
        if (data.critical_issues && data.critical_issues.length > 0) {
            this.alertTitle.textContent = data.critical_issues[0].type || 'Urgent Action Required';
            this.alertMessage.textContent = data.critical_issues[0].description || 'Review your situation immediately';
        } else {
            this.alertTitle.textContent = 'Attention Required';
            this.alertMessage.textContent = 'Your situation needs immediate attention';
        }
    }

    // === Action Handlers ===

    async handleQuickAction(action) {
        switch (action) {
            case 'upload-lease':
                this.fileInput.accept = '.pdf,.doc,.docx,.jpg,.png';
                this.fileInput.click();
                break;
                
            case 'report-issue':
                this.showIssueModal();
                break;
                
            case 'got-notice':
                this.showNoticeModal();
                break;
                
            case 'emergency':
                this.showEmergencyModal();
                break;
        }
    }

    async handleInput() {
        const text = this.userInput.value.trim();
        if (!text) return;
        
        this.userInput.value = '';
        
        // Quick analysis of input to determine intent
        const lowerText = text.toLowerCase();
        
        if (lowerText.includes('evict') || lowerText.includes('notice') || lowerText.includes('court')) {
            await this.reportIssue('notice', text);
        } else if (lowerText.includes('mold') || lowerText.includes('repair') || lowerText.includes('broken') || lowerText.includes('leak')) {
            await this.reportIssue('habitability', text);
        } else if (lowerText.includes('landlord') || lowerText.includes('harass') || lowerText.includes('retaliat')) {
            await this.reportIssue('harassment', text);
        } else {
            // General event
            await this.emitEvent('USER_INPUT', { text });
        }
        
        this.toast('Got it! Analyzing your situation...', 'success');
        await this.refresh();
    }

    async handleFileUpload(e) {
        const file = e.target.files[0];
        if (!file) return;
        
        const formData = new FormData();
        formData.append('file', file);
        
        this.toast('Uploading document...', 'info');
        
        try {
            const res = await fetch('/api/documents/upload', {
                method: 'POST',
                body: formData
            });
            
            if (res.ok) {
                this.toast('Document uploaded and analyzed!', 'success');
                await this.refresh();
            } else {
                throw new Error('Upload failed');
            }
        } catch (err) {
            this.toast('Upload failed. Please try again.', 'error');
        }
        
        this.fileInput.value = '';
    }

    handleDrop(e) {
        e.preventDefault();
        document.getElementById('main-content').classList.remove('drag-over');
        
        const files = e.dataTransfer.files;
        if (files.length > 0) {
            this.fileInput.files = files;
            this.handleFileUpload({ target: this.fileInput });
        }
    }

    handleUrgentAction() {
        // Navigate to most urgent widget or show action modal
        if (this.state.phase === 'eviction') {
            this.showEvictionGuidance();
        } else if (this.state.deadlines.length > 0) {
            this.showDeadlineGuidance(this.state.deadlines[0]);
        } else {
            this.showModal('What to Do Next', `
                <p>Based on your situation, here are your immediate priorities:</p>
                <ol style="margin: 1rem 0; padding-left: 1.5rem;">
                    <li>Document everything in writing</li>
                    <li>Keep copies of all communications</li>
                    <li>Know your response deadlines</li>
                    <li>Consider consulting a tenant attorney</li>
                </ol>
                <button class="btn btn-primary" onclick="elbow.closeModal()">Got It</button>
            `);
        }
    }

    async handleWidgetAction(widgetId, action) {
        await fetch('/api/ui/action/' + action, { method: 'POST' });
        await this.refresh();
    }

    // === API Methods ===

    async reportIssue(type, description) {
        try {
            await fetch('/api/core/issue', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ type, description })
            });
        } catch (err) {
            console.error('Failed to report issue:', err);
        }
    }

    async emitEvent(type, data = {}) {
        try {
            await fetch('/api/core/event', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ type, data })
            });
        } catch (err) {
            console.error('Failed to emit event:', err);
        }
    }

    // === Modal Methods ===

    showModal(title, content) {
        this.modalContent.innerHTML = `
            <h2 class="modal-title">${title}</h2>
            ${content}
        `;
        this.modalOverlay.classList.add('active');
    }

    closeModal() {
        this.modalOverlay.classList.remove('active');
    }

    showIssueModal() {
        this.showModal('Report an Issue', `
            <p class="modal-text">What type of issue are you experiencing?</p>
            <div style="display: flex; flex-direction: column; gap: 0.5rem;">
                <button class="btn btn-secondary" onclick="elbow.selectIssueType('repair')">🔧 Repair needed</button>
                <button class="btn btn-secondary" onclick="elbow.selectIssueType('habitability')">🏠 Habitability (mold, pests, heat)</button>
                <button class="btn btn-secondary" onclick="elbow.selectIssueType('harassment')">😤 Landlord harassment</button>
                <button class="btn btn-secondary" onclick="elbow.selectIssueType('rent')">💰 Rent dispute</button>
                <button class="btn btn-secondary" onclick="elbow.selectIssueType('other')">❓ Something else</button>
            </div>
        `);
    }

    showNoticeModal() {
        this.showModal('What Notice Did You Receive?', `
            <p class="modal-text">Select the type of notice you received:</p>
            <div style="display: flex; flex-direction: column; gap: 0.5rem;">
                <button class="btn btn-danger" onclick="elbow.selectNoticeType('eviction_3day')">🚨 3-Day Notice to Pay or Quit</button>
                <button class="btn btn-secondary" onclick="elbow.selectNoticeType('eviction_30day')">📋 30-Day Notice</button>
                <button class="btn btn-secondary" onclick="elbow.selectNoticeType('eviction_60day')">📋 60-Day Notice</button>
                <button class="btn btn-secondary" onclick="elbow.selectNoticeType('rent_increase')">📈 Rent Increase</button>
                <button class="btn btn-secondary" onclick="elbow.selectNoticeType('entry')">🚪 Notice to Enter</button>
                <button class="btn btn-secondary" onclick="elbow.selectNoticeType('other')">❓ Other notice</button>
            </div>
        `);
    }

    showEmergencyModal() {
        this.showModal('Emergency Situation', `
            <p class="modal-text" style="color: var(--color-danger); font-weight: 500;">
                If you're being locked out right now, call the police at 911.
            </p>
            <p class="modal-text">What's your emergency?</p>
            <div style="display: flex; flex-direction: column; gap: 0.5rem;">
                <button class="btn btn-danger" onclick="elbow.selectEmergency('lockout')">🔒 Locked out of my unit</button>
                <button class="btn btn-danger" onclick="elbow.selectEmergency('court')">⚖️ Court date soon</button>
                <button class="btn btn-secondary" onclick="elbow.selectEmergency('utilities')">💡 Utilities shut off</button>
                <button class="btn btn-secondary" onclick="elbow.selectEmergency('harassment')">😱 Immediate harassment</button>
            </div>
        `);
    }

    showEvictionGuidance() {
        this.showModal('Eviction Process Guidance', `
            <p class="modal-text">You're facing an eviction. Here's what you need to know:</p>
            <ol style="margin: 1rem 0; padding-left: 1.5rem; line-height: 1.8;">
                <li><strong>Don't panic</strong> — you have legal rights and options</li>
                <li><strong>Read the notice carefully</strong> — note all dates and deadlines</li>
                <li><strong>Respond in writing</strong> — if you dispute the claims</li>
                <li><strong>Appear in court</strong> — if a court date is set, YOU MUST attend</li>
                <li><strong>Seek legal help</strong> — many areas have free tenant attorneys</li>
            </ol>
            <div style="background: var(--color-warning-light); padding: 1rem; border-radius: 8px; margin-bottom: 1rem;">
                <strong>⚠️ Important:</strong> Do NOT move out until legally required to do so.
            </div>
            <button class="btn btn-primary" onclick="elbow.closeModal()">I Understand</button>
        `);
    }

    showDeadlineGuidance(deadline) {
        this.showModal(`Deadline: ${deadline.title}`, `
            <p class="modal-text">
                <strong>Due:</strong> ${this.formatDate(deadline.date)}<br>
                <strong>Days remaining:</strong> ${this.daysUntil(deadline.date)} days
            </p>
            <p class="modal-text">${deadline.description || 'Make sure to take action before this deadline.'}</p>
            <button class="btn btn-primary" onclick="elbow.closeModal()">Got It</button>
        `);
    }

    async selectIssueType(type) {
        this.closeModal();
        await this.reportIssue(type, `User reported ${type} issue`);
        this.toast('Issue recorded. Updating your guidance...', 'success');
        await this.refresh();
    }

    async selectNoticeType(type) {
        this.closeModal();
        const noticeMap = {
            'eviction_3day': { type: '3_day_notice', description: 'Received 3-day notice to pay or quit', intensity: 90 },
            'eviction_30day': { type: '30_day_notice', description: 'Received 30-day notice', intensity: 70 },
            'eviction_60day': { type: '60_day_notice', description: 'Received 60-day notice', intensity: 60 },
            'rent_increase': { type: 'rent_increase', description: 'Received rent increase notice', intensity: 40 },
            'entry': { type: 'entry_notice', description: 'Received notice to enter', intensity: 20 },
            'other': { type: 'other_notice', description: 'Received other notice', intensity: 30 }
        };
        
        const notice = noticeMap[type] || noticeMap['other'];
        await this.reportIssue(notice.type, notice.description);
        this.toast('Notice recorded. Updating your guidance...', 'success');
        await this.refresh();
    }

    async selectEmergency(type) {
        this.closeModal();
        
        const emergencyMap = {
            'lockout': { description: 'Illegal lockout in progress', intensity: 100 },
            'court': { description: 'Court date imminent', intensity: 95 },
            'utilities': { description: 'Utilities illegally shut off', intensity: 85 },
            'harassment': { description: 'Active harassment situation', intensity: 80 }
        };
        
        const emergency = emergencyMap[type];
        await this.reportIssue(type, emergency.description);
        this.toast('Emergency recorded. Getting you help...', 'warning');
        await this.refresh();
    }

    // === Utility Methods ===

    toast(message, type = 'info') {
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        toast.textContent = message;
        this.toastContainer.appendChild(toast);
        
        setTimeout(() => {
            toast.style.opacity = '0';
            setTimeout(() => toast.remove(), 300);
        }, 3000);
    }

    formatDate(dateStr) {
        if (!dateStr) return '';
        const date = new Date(dateStr);
        const now = new Date();
        const diff = Math.floor((date - now) / (1000 * 60 * 60 * 24));
        
        if (diff === 0) return 'Today';
        if (diff === 1) return 'Tomorrow';
        if (diff === -1) return 'Yesterday';
        if (diff > 0 && diff < 7) return `In ${diff} days`;
        
        return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
    }

    daysUntil(dateStr) {
        const date = new Date(dateStr);
        const now = new Date();
        return Math.ceil((date - now) / (1000 * 60 * 60 * 24));
    }
}

// Initialize Elbow
const elbow = new Elbow();
