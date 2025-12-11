/**
 * Enterprise Dashboard - Advanced JavaScript Framework
 * Real-time updates, data visualization, WebSocket integration
 * Built for high-performance legal case management
 */

class EnterpriseDashboard {
    constructor() {
        this.ws = null;
        this.charts = {};
        this.updateInterval = null;
        this.init();
    }

    async init() {
        console.log('🚀 Initializing Enterprise Dashboard...');
        
        // Load initial data
        await this.loadDashboardData();
        
        // Setup WebSocket for real-time updates
        this.setupWebSocket();
        
        // Initialize charts
        this.initializeCharts();
        
        // Setup periodic refresh
        this.startPeriodicUpdate();
        
        // Setup event listeners
        this.setupEventListeners();
        
        console.log('✅ Enterprise Dashboard Ready');
    }

    async loadDashboardData() {
        try {
            // Load all dashboard data in parallel
            const [stats, activity, progress, documents, actions, insights] = await Promise.all([
                this.fetchStats(),
                this.fetchActivity(),
                this.fetchProgress(),
                this.fetchDocuments(),
                this.fetchQuickActions(),
                this.fetchAIInsights()
            ]);

            // Update UI with loaded data
            this.updateStats(stats);
            this.updateActivity(activity);
            this.updateProgress(progress);
            this.updateDocuments(documents);
            this.renderQuickActions(actions);
            this.renderAIInsights(insights);

        } catch (error) {
            console.error('Failed to load dashboard data:', error);
            this.showError('Failed to load dashboard data');
        }
    }

    async fetchStats() {
        const response = await fetch('/api/dashboard/stats');
        return await response.json();
    }

    async fetchActivity() {
        const response = await fetch('/api/dashboard/activity?limit=10');
        return await response.json();
    }

    async fetchProgress() {
        const response = await fetch('/api/dashboard/case-progress');
        return await response.json();
    }

    async fetchDocuments() {
        const response = await fetch('/api/dashboard/recent-documents?limit=10');
        return await response.json();
    }

    async fetchQuickActions() {
        const response = await fetch('/api/dashboard/quick-actions');
        return await response.json();
    }

    async fetchAIInsights() {
        const response = await fetch('/api/dashboard/ai-insights');
        return await response.json();
    }

    updateStats(stats) {
        // Update stat cards with animation
        this.animateValue('documents-count', stats.documents_count);
        this.animateValue('tasks-completed', stats.tasks_completed);
        this.animateValue('deadlines-count', stats.upcoming_deadlines);
        this.animateValue('case-strength', stats.case_strength, '%');
    }

    updateActivity(activities) {
        const container = document.getElementById('activity-timeline');
        if (!container) return;

        container.innerHTML = activities.map(activity => `
            <div class="timeline-item">
                <div class="timeline-icon" style="background: linear-gradient(135deg, ${activity.color}, ${this.darkenColor(activity.color)});">
                    <i class="fas fa-${activity.icon}"></i>
                </div>
                <div class="timeline-content">
                    <div class="timeline-title">${activity.title}</div>
                    <div class="timeline-desc">${activity.description}</div>
                    <div class="timeline-time">${this.formatTime(activity.timestamp)}</div>
                </div>
            </div>
        `).join('');
    }

    updateProgress(progress) {
        const items = [
            { label: 'Evidence Collection', value: progress.evidence_collection },
            { label: 'Legal Research', value: progress.legal_research },
            { label: 'Document Preparation', value: progress.document_preparation },
            { label: 'Court Filing Ready', value: progress.court_filing_ready }
        ];

        const container = document.getElementById('progress-list');
        if (!container) return;

        container.innerHTML = items.map(item => `
            <div class="progress-item">
                <div class="progress-header">
                    <span class="progress-label">${item.label}</span>
                    <span class="progress-value">${item.value}%</span>
                </div>
                <div class="progress-bar">
                    <div class="progress-fill" style="width: ${item.value}%"></div>
                </div>
            </div>
        `).join('');
    }

    updateDocuments(documents) {
        const tbody = document.getElementById('documents-table');
        if (!tbody) return;

        tbody.innerHTML = documents.map(doc => `
            <tr>
                <td>
                    <i class="fas fa-file-${this.getFileIcon(doc.file_type)}" 
                       style="color: ${this.getFileColor(doc.file_type)}; margin-right: 0.5rem;"></i>
                    ${doc.name}
                </td>
                <td>${doc.type}</td>
                <td>
                    <span class="status-badge status-${this.getStatusClass(doc.status)}">
                        ${doc.status}
                    </span>
                </td>
                <td>${this.formatDate(doc.date_added)}</td>
                <td>
                    <button class="icon-btn" onclick="dashboard.downloadDocument('${doc.id}')">
                        <i class="fas fa-download"></i>
                    </button>
                    <button class="icon-btn" onclick="dashboard.viewDocument('${doc.id}')">
                        <i class="fas fa-eye"></i>
                    </button>
                </td>
            </tr>
        `).join('');
    }

    renderQuickActions(actions) {
        // Create quick actions panel if it doesn't exist
        const existingPanel = document.getElementById('quick-actions-panel');
        if (existingPanel) return; // Already rendered

        const actionsHTML = `
            <div class="card" id="quick-actions-panel">
                <div class="card-header">
                    <h2 class="card-title">Quick Actions</h2>
                </div>
                <div class="quick-actions-grid">
                    ${actions.map(action => `
                        <a href="${action.url}" class="quick-action-item" style="border-left: 3px solid ${action.color}">
                            <i class="fas fa-${action.icon}" style="color: ${action.color}"></i>
                            <div class="quick-action-content">
                                <div class="quick-action-title">${action.title}</div>
                                <div class="quick-action-desc">${action.description}</div>
                            </div>
                        </a>
                    `).join('')}
                </div>
            </div>
        `;

        // Insert after stats grid
        const statsGrid = document.querySelector('.stats-grid');
        if (statsGrid) {
            statsGrid.insertAdjacentHTML('afterend', actionsHTML);
        }
    }

    renderAIInsights(insights) {
        const criticalInsights = insights.filter(i => i.action_required);
        
        if (criticalInsights.length > 0) {
            this.showInsightsBanner(criticalInsights);
        }
    }

    showInsightsBanner(insights) {
        const banner = `
            <div class="insights-banner" style="
                background: linear-gradient(135deg, rgba(124, 58, 237, 0.2), rgba(59, 130, 246, 0.1));
                border: 1px solid rgba(124, 58, 237, 0.3);
                border-radius: 16px;
                padding: 1.5rem;
                margin-bottom: 2rem;
            ">
                <div style="display: flex; align-items: center; gap: 1rem; margin-bottom: 1rem;">
                    <i class="fas fa-brain" style="font-size: 2rem; color: #7c3aed;"></i>
                    <div>
                        <h3 style="margin-bottom: 0.25rem;">AI Insights</h3>
                        <p style="color: var(--gray); margin: 0; font-size: 0.9rem;">
                            ${insights.length} recommendation${insights.length > 1 ? 's' : ''} require your attention
                        </p>
                    </div>
                </div>
                <div style="display: grid; gap: 1rem;">
                    ${insights.map(insight => `
                        <div style="
                            background: rgba(0, 0, 0, 0.2);
                            border-radius: 12px;
                            padding: 1rem;
                            border-left: 3px solid ${this.getSeverityColor(insight.severity)};
                        ">
                            <div style="font-weight: 600; margin-bottom: 0.25rem;">${insight.title}</div>
                            <div style="color: var(--gray); font-size: 0.9rem;">${insight.description}</div>
                            <div style="margin-top: 0.5rem; font-size: 0.85rem; color: var(--gray);">
                                Confidence: ${(insight.confidence * 100).toFixed(0)}%
                            </div>
                        </div>
                    `).join('')}
                </div>
            </div>
        `;

        const pageHeader = document.querySelector('.page-header');
        if (pageHeader) {
            pageHeader.insertAdjacentHTML('afterend', banner);
        }
    }

    setupWebSocket() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws/dashboard`;

        try {
            this.ws = new WebSocket(wsUrl);

            this.ws.onopen = () => {
                console.log('✅ WebSocket connected');
                this.showNotification('Connected to real-time updates', 'success');
            };

            this.ws.onmessage = (event) => {
                const data = JSON.parse(event.data);
                this.handleWebSocketMessage(data);
            };

            this.ws.onerror = (error) => {
                console.log('WebSocket not available (normal in development)');
            };

            this.ws.onclose = () => {
                console.log('WebSocket disconnected, attempting to reconnect...');
                setTimeout(() => this.setupWebSocket(), 5000);
            };
        } catch (error) {
            console.log('WebSocket not available');
        }
    }

    handleWebSocketMessage(data) {
        switch (data.type) {
            case 'stats_update':
                this.updateStats(data.data);
                break;
            case 'new_activity':
                this.addActivityItem(data.data);
                break;
            case 'notification':
                this.showNotification(data.message, data.level);
                break;
            default:
                console.log('Unknown WebSocket message:', data);
        }
    }

    initializeCharts() {
        // Document uploads trend chart
        this.createTrendChart('uploads-chart', [3, 7, 10, 4]);
        
        // Case timeline chart
        this.createTimelineChart('timeline-chart');
    }

    createTrendChart(elementId, data) {
        // Simple SVG-based chart (can be replaced with Chart.js or D3.js)
        const canvas = document.getElementById(elementId);
        if (!canvas) return;

        // Basic implementation - replace with proper charting library
        console.log(`Chart ${elementId} would be rendered with data:`, data);
    }

    createTimelineChart(elementId) {
        const canvas = document.getElementById(elementId);
        if (!canvas) return;

        console.log(`Timeline chart ${elementId} initialized`);
    }

    startPeriodicUpdate() {
        // Refresh dashboard every 60 seconds
        this.updateInterval = setInterval(() => {
            this.loadDashboardData();
        }, 60000);
    }

    setupEventListeners() {
        // Global search
        const searchInput = document.querySelector('.search-bar input');
        if (searchInput) {
            let searchTimeout;
            searchInput.addEventListener('input', (e) => {
                clearTimeout(searchTimeout);
                searchTimeout = setTimeout(() => {
                    this.performSearch(e.target.value);
                }, 300);
            });
        }

        // Notification panel
        const notifBtn = document.querySelector('.notification-btn');
        if (notifBtn) {
            notifBtn.addEventListener('click', () => {
                this.toggleNotificationPanel();
            });
        }
    }

    async performSearch(query) {
        if (query.length < 2) return;

        const response = await fetch(`/api/search?q=${encodeURIComponent(query)}`);
        const results = await response.json();
        
        this.showSearchResults(results);
    }

    showSearchResults(results) {
        // TODO: Implement search results dropdown
        console.log('Search results:', results);
    }

    toggleNotificationPanel() {
        // TODO: Implement notification panel
        console.log('Toggle notification panel');
    }

    // Utility methods
    animateValue(elementId, endValue, suffix = '') {
        const element = document.getElementById(elementId);
        if (!element) return;

        const startValue = parseInt(element.textContent) || 0;
        const duration = 1000;
        const startTime = Date.now();

        const animate = () => {
            const elapsed = Date.now() - startTime;
            const progress = Math.min(elapsed / duration, 1);
            
            const currentValue = Math.floor(startValue + (endValue - startValue) * progress);
            element.textContent = currentValue + suffix;

            if (progress < 1) {
                requestAnimationFrame(animate);
            }
        };

        animate();
    }

    formatTime(timestamp) {
        const date = new Date(timestamp);
        const now = new Date();
        const diffMs = now - date;
        const diffMins = Math.floor(diffMs / 60000);
        const diffHours = Math.floor(diffMs / 3600000);
        const diffDays = Math.floor(diffMs / 86400000);

        if (diffMins < 60) return `${diffMins} minute${diffMins !== 1 ? 's' : ''} ago`;
        if (diffHours < 24) return `${diffHours} hour${diffHours !== 1 ? 's' : ''} ago`;
        if (diffDays === 1) return 'Yesterday';
        if (diffDays < 7) return `${diffDays} days ago`;
        
        return date.toLocaleDateString();
    }

    formatDate(dateString) {
        const date = new Date(dateString);
        return date.toLocaleDateString('en-US', { 
            month: 'short', 
            day: 'numeric', 
            year: 'numeric' 
        });
    }

    getFileIcon(fileType) {
        const icons = {
            'pdf': 'pdf',
            'images': 'image',
            'excel': 'file-excel',
            'word': 'file-word',
            'default': 'file'
        };
        return icons[fileType] || icons.default;
    }

    getFileColor(fileType) {
        const colors = {
            'pdf': '#ef4444',
            'images': '#3b82f6',
            'excel': '#10b981',
            'word': '#2563eb',
            'default': '#64748b'
        };
        return colors[fileType] || colors.default;
    }

    getStatusClass(status) {
        const classes = {
            'Verified': 'success',
            'Processing': 'warning',
            'Pending': 'info',
            'Failed': 'danger'
        };
        return classes[status] || 'info';
    }

    getSeverityColor(severity) {
        const colors = {
            'critical': '#ef4444',
            'high': '#f59e0b',
            'medium': '#3b82f6',
            'low': '#10b981'
        };
        return colors[severity] || colors.medium;
    }

    darkenColor(color, amount = 20) {
        // Simple color darkening
        return color; // Simplified - can implement proper color manipulation
    }

    showNotification(message, type = 'info') {
        // TODO: Implement toast notification system
        console.log(`[${type.toUpperCase()}] ${message}`);
    }

    showError(message) {
        this.showNotification(message, 'error');
    }

    async downloadDocument(docId) {
        window.location.href = `/api/documents/${docId}/download`;
    }

    async viewDocument(docId) {
        window.open(`/documents/${docId}`, '_blank');
    }

    destroy() {
        if (this.ws) {
            this.ws.close();
        }
        if (this.updateInterval) {
            clearInterval(this.updateInterval);
        }
    }
}

// Initialize dashboard when DOM is ready
let dashboard;
document.addEventListener('DOMContentLoaded', () => {
    dashboard = new EnterpriseDashboard();
});

// Cleanup on page unload
window.addEventListener('beforeunload', () => {
    if (dashboard) {
        dashboard.destroy();
    }
});
