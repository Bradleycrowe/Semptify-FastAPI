/**
 * Semptify Document Picker
 * Popup modal to select documents from vault for use in any module
 * 
 * Usage:
 *   DocumentPicker.open({
 *       onSelect: (documents) => { console.log('Selected:', documents); },
 *       multiple: true,
 *       filter: 'court' // optional filter by type
 *   });
 */

const DocumentPicker = {
    modal: null,
    documents: [],
    selectedDocs: [],
    options: {},
    currentView: 'grid',
    currentSort: 'date-desc',
    currentFilter: 'all',
    
    // Initialize the picker
    init() {
        if (document.getElementById('documentPickerModal')) return;
        
        const modalHTML = `
            <div class="doc-picker-overlay" id="documentPickerModal">
                <div class="doc-picker-modal">
                    <div class="doc-picker-header">
                        <h2>📁 Select Documents from Vault</h2>
                        <button class="doc-picker-close" onclick="DocumentPicker.close()">×</button>
                    </div>
                    
                    <div class="doc-picker-toolbar">
                        <div class="doc-picker-views">
                            <button class="view-btn active" data-view="grid" onclick="DocumentPicker.setView('grid')">📊</button>
                            <button class="view-btn" data-view="list" onclick="DocumentPicker.setView('list')">📋</button>
                            <button class="view-btn" data-view="folder" onclick="DocumentPicker.setView('folder')">📁</button>
                        </div>
                        
                        <div class="doc-picker-filters">
                            <select id="pickerFilter" onchange="DocumentPicker.setFilter(this.value)">
                                <option value="all">All Documents</option>
                                <option value="lease">📄 Lease</option>
                                <option value="notice">⚠️ Notices</option>
                                <option value="court">⚖️ Court</option>
                                <option value="photo">📸 Photos</option>
                                <option value="receipt">🧾 Receipts</option>
                                <option value="letter">✉️ Letters</option>
                            </select>
                            
                            <select id="pickerSort" onchange="DocumentPicker.setSort(this.value)">
                                <option value="date-desc">Newest First</option>
                                <option value="date-asc">Oldest First</option>
                                <option value="name-asc">Name A-Z</option>
                                <option value="name-desc">Name Z-A</option>
                            </select>
                        </div>
                        
                        <div class="doc-picker-search">
                            <input type="text" id="pickerSearch" placeholder="🔍 Search documents..." oninput="DocumentPicker.search(this.value)">
                        </div>
                    </div>
                    
                    <div class="doc-picker-selected-bar" id="pickerSelectedBar" style="display: none;">
                        <span id="pickerSelectedCount">0 selected</span>
                        <button class="clear-selection" onclick="DocumentPicker.clearSelection()">Clear</button>
                    </div>
                    
                    <div class="doc-picker-content" id="pickerContent">
                        <div class="doc-picker-loading">
                            <div class="spinner"></div>
                            <p>Loading documents...</p>
                        </div>
                    </div>
                    
                    <div class="doc-picker-footer">
                        <button class="btn-cancel" onclick="DocumentPicker.close()">Cancel</button>
                        <button class="btn-select" id="btnSelectDocs" onclick="DocumentPicker.confirm()" disabled>
                            Select Documents
                        </button>
                    </div>
                </div>
            </div>
        `;
        
        document.body.insertAdjacentHTML('beforeend', modalHTML);
        this.modal = document.getElementById('documentPickerModal');
        this.injectStyles();
    },
    
    // Inject CSS styles
    injectStyles() {
        if (document.getElementById('docPickerStyles')) return;
        
        const styles = `
            <style id="docPickerStyles">
                .doc-picker-overlay {
                    position: fixed;
                    inset: 0;
                    background: rgba(0,0,0,0.6);
                    display: none;
                    align-items: center;
                    justify-content: center;
                    z-index: 10000;
                    padding: 20px;
                }
                
                .doc-picker-overlay.open {
                    display: flex;
                }
                
                .doc-picker-modal {
                    background: #fff;
                    border-radius: 16px;
                    width: 100%;
                    max-width: 900px;
                    max-height: 85vh;
                    display: flex;
                    flex-direction: column;
                    box-shadow: 0 20px 50px rgba(0,0,0,0.3);
                }
                
                .doc-picker-header {
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    padding: 20px 24px;
                    border-bottom: 1px solid #e2e8f0;
                }
                
                .doc-picker-header h2 {
                    font-size: 20px;
                    font-weight: 700;
                    color: #1e293b;
                    margin: 0;
                }
                
                .doc-picker-close {
                    width: 36px;
                    height: 36px;
                    background: #f1f5f9;
                    border: none;
                    border-radius: 8px;
                    font-size: 24px;
                    cursor: pointer;
                    color: #64748b;
                }
                
                .doc-picker-close:hover {
                    background: #e2e8f0;
                    color: #1e293b;
                }
                
                .doc-picker-toolbar {
                    display: flex;
                    gap: 12px;
                    padding: 12px 24px;
                    background: #f8fafc;
                    border-bottom: 1px solid #e2e8f0;
                    flex-wrap: wrap;
                    align-items: center;
                }
                
                .doc-picker-views {
                    display: flex;
                    background: #e2e8f0;
                    border-radius: 8px;
                    padding: 4px;
                }
                
                .doc-picker-views .view-btn {
                    padding: 8px 12px;
                    border: none;
                    background: transparent;
                    border-radius: 6px;
                    cursor: pointer;
                    font-size: 16px;
                }
                
                .doc-picker-views .view-btn.active {
                    background: #1e40af;
                    color: white;
                }
                
                .doc-picker-filters {
                    display: flex;
                    gap: 8px;
                }
                
                .doc-picker-filters select {
                    padding: 8px 12px;
                    border: 1px solid #e2e8f0;
                    border-radius: 8px;
                    font-size: 14px;
                    background: white;
                }
                
                .doc-picker-search {
                    flex: 1;
                    min-width: 200px;
                }
                
                .doc-picker-search input {
                    width: 100%;
                    padding: 8px 12px;
                    border: 1px solid #e2e8f0;
                    border-radius: 8px;
                    font-size: 14px;
                }
                
                .doc-picker-selected-bar {
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    padding: 8px 24px;
                    background: #dbeafe;
                    color: #1e40af;
                    font-weight: 600;
                }
                
                .clear-selection {
                    background: transparent;
                    border: none;
                    color: #1e40af;
                    cursor: pointer;
                    text-decoration: underline;
                }
                
                .doc-picker-content {
                    flex: 1;
                    overflow-y: auto;
                    padding: 16px 24px;
                    min-height: 300px;
                }
                
                .doc-picker-loading {
                    display: flex;
                    flex-direction: column;
                    align-items: center;
                    justify-content: center;
                    height: 200px;
                    color: #64748b;
                }
                
                .doc-picker-loading .spinner {
                    width: 40px;
                    height: 40px;
                    border: 3px solid #e2e8f0;
                    border-top-color: #1e40af;
                    border-radius: 50%;
                    animation: spin 1s linear infinite;
                    margin-bottom: 12px;
                }
                
                @keyframes spin {
                    to { transform: rotate(360deg); }
                }
                
                /* Grid View */
                .doc-picker-grid {
                    display: grid;
                    grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
                    gap: 12px;
                }
                
                .doc-picker-item {
                    background: #fff;
                    border: 2px solid #e2e8f0;
                    border-radius: 12px;
                    padding: 16px;
                    cursor: pointer;
                    transition: all 0.2s;
                    text-align: center;
                }
                
                .doc-picker-item:hover {
                    border-color: #3b82f6;
                    transform: translateY(-2px);
                    box-shadow: 0 4px 12px rgba(0,0,0,0.1);
                }
                
                .doc-picker-item.selected {
                    border-color: #1e40af;
                    background: #eff6ff;
                }
                
                .doc-picker-item.selected::after {
                    content: '✓';
                    position: absolute;
                    top: 8px;
                    right: 8px;
                    width: 24px;
                    height: 24px;
                    background: #1e40af;
                    color: white;
                    border-radius: 50%;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    font-size: 14px;
                }
                
                .doc-picker-item {
                    position: relative;
                }
                
                .doc-item-icon {
                    font-size: 40px;
                    margin-bottom: 8px;
                }
                
                .doc-item-name {
                    font-size: 13px;
                    font-weight: 600;
                    color: #1e293b;
                    white-space: nowrap;
                    overflow: hidden;
                    text-overflow: ellipsis;
                }
                
                .doc-item-meta {
                    font-size: 11px;
                    color: #64748b;
                    margin-top: 4px;
                }
                
                /* List View */
                .doc-picker-list {
                    display: flex;
                    flex-direction: column;
                    gap: 8px;
                }
                
                .doc-picker-list .doc-picker-item {
                    display: flex;
                    align-items: center;
                    gap: 16px;
                    text-align: left;
                    padding: 12px 16px;
                }
                
                .doc-picker-list .doc-item-icon {
                    font-size: 32px;
                    margin-bottom: 0;
                    flex-shrink: 0;
                }
                
                .doc-picker-list .doc-item-info {
                    flex: 1;
                    min-width: 0;
                }
                
                .doc-picker-list .doc-item-date {
                    font-size: 12px;
                    color: #64748b;
                    white-space: nowrap;
                }
                
                /* Folder View */
                .doc-picker-folder-section {
                    margin-bottom: 24px;
                }
                
                .folder-header {
                    display: flex;
                    align-items: center;
                    gap: 8px;
                    padding: 8px 0;
                    cursor: pointer;
                    font-weight: 600;
                    color: #1e293b;
                }
                
                .folder-header:hover {
                    color: #1e40af;
                }
                
                .folder-icon {
                    font-size: 20px;
                }
                
                .folder-count {
                    background: #e2e8f0;
                    padding: 2px 8px;
                    border-radius: 10px;
                    font-size: 12px;
                    color: #64748b;
                }
                
                .folder-content {
                    padding-left: 28px;
                    margin-top: 8px;
                }
                
                .folder-content.collapsed {
                    display: none;
                }
                
                /* Empty State */
                .doc-picker-empty {
                    text-align: center;
                    padding: 40px;
                    color: #64748b;
                }
                
                .doc-picker-empty-icon {
                    font-size: 48px;
                    margin-bottom: 12px;
                    opacity: 0.5;
                }
                
                .doc-picker-footer {
                    display: flex;
                    justify-content: flex-end;
                    gap: 12px;
                    padding: 16px 24px;
                    border-top: 1px solid #e2e8f0;
                }
                
                .doc-picker-footer .btn-cancel {
                    padding: 10px 20px;
                    background: #f1f5f9;
                    border: 1px solid #e2e8f0;
                    border-radius: 8px;
                    font-size: 14px;
                    cursor: pointer;
                }
                
                .doc-picker-footer .btn-cancel:hover {
                    background: #e2e8f0;
                }
                
                .doc-picker-footer .btn-select {
                    padding: 10px 24px;
                    background: #1e40af;
                    color: white;
                    border: none;
                    border-radius: 8px;
                    font-size: 14px;
                    font-weight: 600;
                    cursor: pointer;
                }
                
                .doc-picker-footer .btn-select:disabled {
                    background: #94a3b8;
                    cursor: not-allowed;
                }
                
                .doc-picker-footer .btn-select:not(:disabled):hover {
                    background: #1e3a8a;
                }
            </style>
        `;
        
        document.head.insertAdjacentHTML('beforeend', styles);
    },
    
    // Open the picker
    open(options = {}) {
        this.init();
        this.options = {
            multiple: true,
            filter: null,
            onSelect: null,
            ...options
        };
        this.selectedDocs = [];
        this.currentFilter = options.filter || 'all';
        
        // Set initial filter
        if (options.filter) {
            document.getElementById('pickerFilter').value = options.filter;
        }
        
        this.modal.classList.add('open');
        this.loadDocuments();
    },
    
    // Close the picker
    close() {
        this.modal.classList.remove('open');
        this.selectedDocs = [];
        this.updateSelectedBar();
    },
    
    // Load documents from vault
    async loadDocuments() {
        const content = document.getElementById('pickerContent');
        content.innerHTML = '<div class="doc-picker-loading"><div class="spinner"></div><p>Loading documents...</p></div>';
        
        try {
            const userId = localStorage.getItem('semptify_user_id') || 'default';
            
            // Try vault API
            let response = await fetch('/api/vault/all', {
                headers: { 'X-User-ID': userId }
            });
            
            if (response.ok) {
                const data = await response.json();
                this.documents = data.documents || [];
            } else {
                // Fallback to briefcase
                response = await fetch('/api/briefcase/');
                if (response.ok) {
                    const data = await response.json();
                    this.documents = data.documents || [];
                } else {
                    this.documents = [];
                }
            }
            
            this.renderDocuments();
            
        } catch (error) {
            console.error('Error loading documents:', error);
            content.innerHTML = '<div class="doc-picker-empty"><div class="doc-picker-empty-icon">❌</div><p>Error loading documents</p></div>';
        }
    },
    
    // Render documents based on current view
    renderDocuments() {
        let docs = this.getFilteredDocs();
        docs = this.sortDocs(docs);
        
        if (docs.length === 0) {
            document.getElementById('pickerContent').innerHTML = `
                <div class="doc-picker-empty">
                    <div class="doc-picker-empty-icon">📁</div>
                    <p>No documents found</p>
                    <p style="font-size: 13px;">Upload documents to your vault first</p>
                </div>
            `;
            return;
        }
        
        switch (this.currentView) {
            case 'list':
                this.renderListView(docs);
                break;
            case 'folder':
                this.renderFolderView(docs);
                break;
            default:
                this.renderGridView(docs);
        }
    },
    
    // Get filtered documents
    getFilteredDocs() {
        if (this.currentFilter === 'all') return this.documents;
        
        return this.documents.filter(doc => {
            const type = (doc.document_type || doc.type || '').toLowerCase();
            return type.includes(this.currentFilter);
        });
    },
    
    // Sort documents
    sortDocs(docs) {
        const sorted = [...docs];
        switch (this.currentSort) {
            case 'date-desc':
                sorted.sort((a, b) => new Date(b.uploaded_at || b.created_at) - new Date(a.uploaded_at || a.created_at));
                break;
            case 'date-asc':
                sorted.sort((a, b) => new Date(a.uploaded_at || a.created_at) - new Date(b.uploaded_at || b.created_at));
                break;
            case 'name-asc':
                sorted.sort((a, b) => (a.filename || a.name || '').localeCompare(b.filename || b.name || ''));
                break;
            case 'name-desc':
                sorted.sort((a, b) => (b.filename || b.name || '').localeCompare(a.filename || a.name || ''));
                break;
        }
        return sorted;
    },
    
    // Grid View
    renderGridView(docs) {
        const html = `
            <div class="doc-picker-grid">
                ${docs.map(doc => this.renderGridItem(doc)).join('')}
            </div>
        `;
        document.getElementById('pickerContent').innerHTML = html;
    },
    
    renderGridItem(doc) {
        const id = doc.vault_id || doc.id;
        const isSelected = this.selectedDocs.some(d => (d.vault_id || d.id) === id);
        
        return `
            <div class="doc-picker-item ${isSelected ? 'selected' : ''}" 
                 onclick="DocumentPicker.toggleSelect('${id}')"
                 data-id="${id}">
                <div class="doc-item-icon">${this.getIcon(doc.mime_type || doc.type)}</div>
                <div class="doc-item-name">${doc.filename || doc.name}</div>
                <div class="doc-item-meta">${this.formatSize(doc.file_size)}</div>
            </div>
        `;
    },
    
    // List View
    renderListView(docs) {
        const html = `
            <div class="doc-picker-list">
                ${docs.map(doc => this.renderListItem(doc)).join('')}
            </div>
        `;
        document.getElementById('pickerContent').innerHTML = html;
    },
    
    renderListItem(doc) {
        const id = doc.vault_id || doc.id;
        const isSelected = this.selectedDocs.some(d => (d.vault_id || d.id) === id);
        
        return `
            <div class="doc-picker-item ${isSelected ? 'selected' : ''}" 
                 onclick="DocumentPicker.toggleSelect('${id}')"
                 data-id="${id}">
                <div class="doc-item-icon">${this.getIcon(doc.mime_type || doc.type)}</div>
                <div class="doc-item-info">
                    <div class="doc-item-name">${doc.filename || doc.name}</div>
                    <div class="doc-item-meta">${doc.document_type || doc.type || 'Document'} • ${this.formatSize(doc.file_size)}</div>
                </div>
                <div class="doc-item-date">${this.formatDate(doc.uploaded_at || doc.created_at)}</div>
            </div>
        `;
    },
    
    // Folder View
    renderFolderView(docs) {
        const folders = {
            court: { name: 'Court Documents', icon: '⚖️', docs: [] },
            lease: { name: 'Lease & Rental', icon: '📄', docs: [] },
            notice: { name: 'Notices & Letters', icon: '⚠️', docs: [] },
            evidence: { name: 'Photos & Evidence', icon: '📸', docs: [] },
            financial: { name: 'Financial', icon: '💰', docs: [] },
            other: { name: 'Other', icon: '📁', docs: [] }
        };
        
        docs.forEach(doc => {
            const type = (doc.document_type || doc.type || '').toLowerCase();
            if (type.includes('court')) folders.court.docs.push(doc);
            else if (type.includes('lease')) folders.lease.docs.push(doc);
            else if (type.includes('notice') || type.includes('letter')) folders.notice.docs.push(doc);
            else if (type.includes('photo') || type.includes('image')) folders.evidence.docs.push(doc);
            else if (type.includes('receipt') || type.includes('payment')) folders.financial.docs.push(doc);
            else folders.other.docs.push(doc);
        });
        
        let html = '';
        Object.keys(folders).forEach(key => {
            const folder = folders[key];
            if (folder.docs.length > 0) {
                html += `
                    <div class="doc-picker-folder-section">
                        <div class="folder-header" onclick="DocumentPicker.toggleFolder('${key}')">
                            <span class="folder-icon">${folder.icon}</span>
                            <span>${folder.name}</span>
                            <span class="folder-count">${folder.docs.length}</span>
                        </div>
                        <div class="folder-content doc-picker-grid" id="folder-${key}">
                            ${folder.docs.map(doc => this.renderGridItem(doc)).join('')}
                        </div>
                    </div>
                `;
            }
        });
        
        document.getElementById('pickerContent').innerHTML = html || '<div class="doc-picker-empty"><div class="doc-picker-empty-icon">📁</div><p>No documents found</p></div>';
    },
    
    // Toggle folder
    toggleFolder(folderId) {
        const content = document.getElementById(`folder-${folderId}`);
        if (content) {
            content.classList.toggle('collapsed');
        }
    },
    
    // Set view mode
    setView(view) {
        this.currentView = view;
        document.querySelectorAll('.doc-picker-views .view-btn').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.view === view);
        });
        this.renderDocuments();
    },
    
    // Set filter
    setFilter(filter) {
        this.currentFilter = filter;
        this.renderDocuments();
    },
    
    // Set sort
    setSort(sort) {
        this.currentSort = sort;
        this.renderDocuments();
    },
    
    // Search
    search(query) {
        if (!query) {
            this.renderDocuments();
            return;
        }
        
        query = query.toLowerCase();
        const filtered = this.documents.filter(doc => 
            (doc.filename || doc.name || '').toLowerCase().includes(query) ||
            (doc.document_type || doc.type || '').toLowerCase().includes(query)
        );
        
        this.renderGridView(filtered);
    },
    
    // Toggle document selection
    toggleSelect(docId) {
        const doc = this.documents.find(d => (d.vault_id || d.id) === docId);
        if (!doc) return;
        
        const idx = this.selectedDocs.findIndex(d => (d.vault_id || d.id) === docId);
        
        if (idx >= 0) {
            this.selectedDocs.splice(idx, 1);
        } else {
            if (!this.options.multiple) {
                this.selectedDocs = [doc];
            } else {
                this.selectedDocs.push(doc);
            }
        }
        
        this.updateSelectedBar();
        this.renderDocuments();
    },
    
    // Clear selection
    clearSelection() {
        this.selectedDocs = [];
        this.updateSelectedBar();
        this.renderDocuments();
    },
    
    // Update selected bar
    updateSelectedBar() {
        const bar = document.getElementById('pickerSelectedBar');
        const count = document.getElementById('pickerSelectedCount');
        const btn = document.getElementById('btnSelectDocs');
        
        if (this.selectedDocs.length > 0) {
            bar.style.display = 'flex';
            count.textContent = `${this.selectedDocs.length} document${this.selectedDocs.length > 1 ? 's' : ''} selected`;
            btn.disabled = false;
        } else {
            bar.style.display = 'none';
            btn.disabled = true;
        }
    },
    
    // Confirm selection
    confirm() {
        if (this.options.onSelect && this.selectedDocs.length > 0) {
            this.options.onSelect(this.selectedDocs);
        }
        this.close();
    },
    
    // Helper functions
    getIcon(type) {
        if (!type) return '📄';
        type = type.toLowerCase();
        if (type.includes('pdf')) return '📕';
        if (type.includes('image') || type.includes('jpg') || type.includes('png')) return '🖼️';
        if (type.includes('word') || type.includes('doc')) return '📘';
        if (type.includes('court')) return '⚖️';
        if (type.includes('lease')) return '📜';
        if (type.includes('notice')) return '⚠️';
        return '📄';
    },
    
    formatSize(bytes) {
        if (!bytes) return '';
        if (bytes > 1024 * 1024) return (bytes / 1024 / 1024).toFixed(1) + ' MB';
        if (bytes > 1024) return (bytes / 1024).toFixed(1) + ' KB';
        return bytes + ' B';
    },
    
    formatDate(dateStr) {
        if (!dateStr) return '';
        return new Date(dateStr).toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
    }
};

// Export for use
window.DocumentPicker = DocumentPicker;
