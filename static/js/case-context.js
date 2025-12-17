/**
 * Semptify Case Context Manager
 * ============================
 * Central service for managing case information across all pages.
 * Stores active case data in localStorage and provides methods to
 * access, update, and sync case info throughout the application.
 */

const CaseContext = {
    STORAGE_KEY: 'semptify_active_case',
    CASES_KEY: 'semptify_cases_cache',
    
    /**
     * Get the currently active case
     */
    getActiveCase() {
        try {
            const data = localStorage.getItem(this.STORAGE_KEY);
            return data ? JSON.parse(data) : null;
        } catch (e) {
            console.error('Error reading active case:', e);
            return null;
        }
    },
    
    /**
     * Set the active case
     */
    setActiveCase(caseData) {
        try {
            if (caseData) {
                localStorage.setItem(this.STORAGE_KEY, JSON.stringify(caseData));
                this.updateCacheEntry(caseData);
                this.notifyListeners('case-changed', caseData);
            } else {
                localStorage.removeItem(this.STORAGE_KEY);
                this.notifyListeners('case-cleared', null);
            }
            return true;
        } catch (e) {
            console.error('Error saving active case:', e);
            return false;
        }
    },
    
    /**
     * Clear the active case
     */
    clearActiveCase() {
        localStorage.removeItem(this.STORAGE_KEY);
        this.notifyListeners('case-cleared', null);
    },
    
    /**
     * Get a specific field from the active case
     */
    getField(fieldPath) {
        const caseData = this.getActiveCase();
        if (!caseData) return null;
        
        // Support dot notation like "plaintiff.name"
        const parts = fieldPath.split('.');
        let value = caseData;
        for (const part of parts) {
            if (value && typeof value === 'object') {
                value = value[part];
            } else {
                return null;
            }
        }
        return value;
    },
    
    /**
     * Update a specific field in the active case
     */
    updateField(fieldPath, value) {
        const caseData = this.getActiveCase() || {};
        const parts = fieldPath.split('.');
        let obj = caseData;
        
        for (let i = 0; i < parts.length - 1; i++) {
            if (!obj[parts[i]]) {
                obj[parts[i]] = {};
            }
            obj = obj[parts[i]];
        }
        
        obj[parts[parts.length - 1]] = value;
        caseData.updated_at = new Date().toISOString();
        
        return this.setActiveCase(caseData);
    },
    
    /**
     * Get common case info (most frequently needed fields)
     */
    getCommonInfo() {
        const c = this.getActiveCase();
        if (!c) return null;
        
        return {
            caseNumber: c.case_number,
            caseType: c.case_type,
            court: c.court,
            propertyAddress: c.property_address,
            
            // Plaintiff (landlord/property manager)
            plaintiffName: c.plaintiff?.name || c.plaintiff_name,
            plaintiffAddress: c.plaintiff?.address,
            plaintiffPhone: c.plaintiff?.phone,
            plaintiffEmail: c.plaintiff?.email,
            
            // Defendant (tenant/you)
            defendantName: c.defendant?.name || c.defendant_name,
            defendantAddress: c.defendant?.address || c.property_address,
            defendantPhone: c.defendant?.phone,
            defendantEmail: c.defendant?.email,
            
            // Financial
            rentAmount: c.rent_amount,
            securityDeposit: c.security_deposit,
            
            // Key dates
            hearingDate: c.hearing_date,
            leaseStart: c.lease_start,
            leaseEnd: c.lease_end,
            noticeDate: c.notice_date,
            answerDue: c.answer_due,
            
            // Status
            status: c.status,
            progress: c.progress
        };
    },
    
    /**
     * Auto-fill form fields based on mapping
     * @param {Object} fieldMap - Maps form field IDs to case field paths
     * @example autoFillForm({'plaintiff-name': 'plaintiff.name', 'property-address': 'property_address'})
     */
    autoFillForm(fieldMap) {
        const caseData = this.getActiveCase();
        if (!caseData) {
            console.warn('No active case to fill form from');
            return 0;
        }
        
        let filledCount = 0;
        
        for (const [formFieldId, caseFieldPath] of Object.entries(fieldMap)) {
            const value = this.getField(caseFieldPath);
            const element = document.getElementById(formFieldId);
            
            if (element && value !== null && value !== undefined) {
                if (element.type === 'date' && typeof value === 'string') {
                    element.value = value.split('T')[0];
                } else if (element.type === 'checkbox') {
                    element.checked = !!value;
                } else {
                    element.value = value;
                }
                filledCount++;
                
                // Trigger change event for any listeners
                element.dispatchEvent(new Event('change', { bubbles: true }));
            }
        }
        
        console.log(`Auto-filled ${filledCount} fields from active case`);
        return filledCount;
    },
    
    /**
     * Standard field mappings for common forms
     */
    getStandardMappings() {
        return {
            // Case basics
            'case-number': 'case_number',
            'case-type': 'case_type',
            'court': 'court',
            'case-court': 'court',
            
            // Property
            'property-address': 'property_address',
            'case-property': 'property_address',
            'address': 'property_address',
            
            // Plaintiff
            'plaintiff-name': 'plaintiff.name',
            'case-plaintiff': 'plaintiff.name',
            'landlord-name': 'plaintiff.name',
            'property-manager': 'plaintiff.name',
            'plaintiff-address': 'plaintiff.address',
            'plaintiff-phone': 'plaintiff.phone',
            'plaintiff-email': 'plaintiff.email',
            
            // Defendant
            'defendant-name': 'defendant.name',
            'case-defendant': 'defendant.name',
            'your-name': 'defendant.name',
            'tenant-name': 'defendant.name',
            'defendant-address': 'defendant.address',
            'defendant-phone': 'defendant.phone',
            'defendant-email': 'defendant.email',
            
            // Financial
            'rent-amount': 'rent_amount',
            'case-rent': 'rent_amount',
            'monthly-rent': 'rent_amount',
            'security-deposit': 'security_deposit',
            'case-deposit': 'security_deposit',
            
            // Dates
            'hearing-date': 'hearing_date',
            'case-hearing-date': 'hearing_date',
            'lease-start': 'lease_start',
            'case-lease-start': 'lease_start',
            'lease-end': 'lease_end',
            'case-lease-end': 'lease_end',
            'notice-date': 'notice_date'
        };
    },
    
    /**
     * Auto-detect and fill form fields using standard mappings
     */
    autoFillStandard() {
        return this.autoFillForm(this.getStandardMappings());
    },
    
    /**
     * Load case from API and set as active
     */
    async loadCase(caseId) {
        try {
            const response = await fetch(`/api/case-builder/cases/${encodeURIComponent(caseId)}`);
            if (response.ok) {
                const caseData = await response.json();
                this.setActiveCase(caseData);
                return caseData;
            } else {
                console.error('Failed to load case:', response.status);
                return null;
            }
        } catch (e) {
            console.error('Error loading case:', e);
            return null;
        }
    },
    
    /**
     * Save current active case to API
     */
    async saveCase() {
        const caseData = this.getActiveCase();
        if (!caseData || !caseData.case_number) {
            console.error('No active case to save');
            return false;
        }
        
        try {
            const response = await fetch(`/api/case-builder/cases/${encodeURIComponent(caseData.case_number)}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(caseData)
            });
            
            return response.ok;
        } catch (e) {
            console.error('Error saving case:', e);
            return false;
        }
    },
    
    /**
     * Get all cached cases
     */
    getCachedCases() {
        try {
            const data = localStorage.getItem(this.CASES_KEY);
            return data ? JSON.parse(data) : {};
        } catch (e) {
            return {};
        }
    },
    
    /**
     * Update a case in the cache
     */
    updateCacheEntry(caseData) {
        if (!caseData || !caseData.case_number) return;
        
        try {
            const cache = this.getCachedCases();
            cache[caseData.case_number] = {
                ...caseData,
                cached_at: new Date().toISOString()
            };
            localStorage.setItem(this.CASES_KEY, JSON.stringify(cache));
        } catch (e) {
            console.error('Error updating case cache:', e);
        }
    },
    
    /**
     * Get case from cache by number
     */
    getCachedCase(caseNumber) {
        const cache = this.getCachedCases();
        return cache[caseNumber] || null;
    },
    
    // Event listener management
    _listeners: {},
    
    /**
     * Add event listener for case changes
     * @param {string} event - 'case-changed', 'case-cleared', 'field-updated'
     * @param {Function} callback
     */
    on(event, callback) {
        if (!this._listeners[event]) {
            this._listeners[event] = [];
        }
        this._listeners[event].push(callback);
    },
    
    /**
     * Remove event listener
     */
    off(event, callback) {
        if (this._listeners[event]) {
            this._listeners[event] = this._listeners[event].filter(cb => cb !== callback);
        }
    },
    
    /**
     * Notify all listeners of an event
     */
    notifyListeners(event, data) {
        const listeners = this._listeners[event] || [];
        listeners.forEach(cb => {
            try {
                cb(data);
            } catch (e) {
                console.error('Error in case context listener:', e);
            }
        });
    },
    
    /**
     * Initialize case context - call on page load
     */
    init() {
        // Check URL params for case to load
        const urlParams = new URLSearchParams(window.location.search);
        const caseNumber = urlParams.get('case') || urlParams.get('case_number') || urlParams.get('caseId');
        
        if (caseNumber) {
            // Load specific case
            this.loadCase(caseNumber).then(caseData => {
                if (caseData) {
                    console.log(`📋 Case Context: Loaded case ${caseNumber}`);
                    // Auto-fill any forms on the page
                    setTimeout(() => this.autoFillStandard(), 100);
                }
            });
        } else {
            // Check if we have an active case and auto-fill
            const activeCase = this.getActiveCase();
            if (activeCase) {
                console.log(`📋 Case Context: Using active case ${activeCase.case_number}`);
                setTimeout(() => this.autoFillStandard(), 100);
            }
        }
    },
    
    /**
     * Display current case info in a status bar element
     */
    showStatusBar(containerId = 'case-status-bar') {
        const container = document.getElementById(containerId);
        if (!container) return;
        
        const caseData = this.getActiveCase();
        if (!caseData) {
            container.innerHTML = `
                <div class="alert alert-info mb-3 d-flex align-items-center">
                    <i class="bi bi-info-circle me-2"></i>
                    <span>No active case selected. <a href="/static/cases.html">Select a case</a> to auto-fill forms.</span>
                </div>
            `;
            return;
        }
        
        container.innerHTML = `
            <div class="alert alert-success mb-3 d-flex justify-content-between align-items-center">
                <div>
                    <i class="bi bi-folder-check me-2"></i>
                    <strong>Active Case:</strong> ${caseData.case_number}
                    <span class="ms-2 text-muted">
                        ${caseData.plaintiff?.name || caseData.plaintiff_name || ''} • 
                        ${caseData.property_address || ''}
                    </span>
                </div>
                <div>
                    <button class="btn btn-sm btn-outline-light me-2" onclick="CaseContext.autoFillStandard()">
                        <i class="bi bi-arrow-repeat"></i> Fill Form
                    </button>
                    <button class="btn btn-sm btn-outline-danger" onclick="CaseContext.clearActiveCase(); CaseContext.showStatusBar();">
                        <i class="bi bi-x"></i>
                    </button>
                </div>
            </div>
        `;
    },
    
    /**
     * Create a case selector dropdown
     */
    async createCaseSelector(containerId, onSelect) {
        const container = document.getElementById(containerId);
        if (!container) return;
        
        try {
            const response = await fetch('/api/case-builder/cases');
            const data = response.ok ? await response.json() : { cases: [] };
            const cases = data.cases || [];
            
            const activeCase = this.getActiveCase();
            const activeCaseNumber = activeCase?.case_number;
            
            let html = `
                <label class="form-label">Select Case</label>
                <select class="form-select" id="case-selector-dropdown">
                    <option value="">-- Select a case --</option>
            `;
            
            cases.forEach(c => {
                const selected = c.case_number === activeCaseNumber ? 'selected' : '';
                html += `<option value="${c.case_number}" ${selected}>${c.case_number} - ${c.plaintiff_name || 'Unknown'}</option>`;
            });
            
            html += '</select>';
            container.innerHTML = html;
            
            // Add change handler
            document.getElementById('case-selector-dropdown').addEventListener('change', async (e) => {
                const caseNumber = e.target.value;
                if (caseNumber) {
                    await this.loadCase(caseNumber);
                    if (onSelect) onSelect(this.getActiveCase());
                } else {
                    this.clearActiveCase();
                    if (onSelect) onSelect(null);
                }
            });
            
        } catch (e) {
            console.error('Error creating case selector:', e);
            container.innerHTML = '<p class="text-danger">Error loading cases</p>';
        }
    }
};

// Auto-initialize on DOMContentLoaded
document.addEventListener('DOMContentLoaded', () => {
    // Only auto-init if page has case context elements
    if (document.querySelector('[data-case-context]') || 
        document.getElementById('case-status-bar') ||
        new URLSearchParams(window.location.search).has('case')) {
        CaseContext.init();
    }
});

// Export for ES modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = CaseContext;
}
