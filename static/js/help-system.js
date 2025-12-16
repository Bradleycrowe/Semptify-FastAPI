/**
 * Semptify Site-Wide Help System (Self-Generating)
 * 
 * This system automatically analyzes the page and generates help content
 * in real-time by reading:
 * - Button text and icons
 * - Form labels and placeholders
 * - Card headers and structure
 * - Data attributes
 * 
 * No manual help content needed - it learns from the UI itself!
 */

const SemptifyHelp = {
    initialized: false,
    helpEnabled: false,
    
    // Knowledge base for generating contextual help
    // Enhanced with detailed user-friendly descriptions, when to use, and tips
    knowledge: {
        // Action verbs with detailed help - includes what it does, when to use, and tips
        actions: {
            'process': {
                what: 'Runs automated analysis on your document',
                details: 'This scans your document to extract key information like dates, names, amounts, and legal terms. It checks for completeness and flags any potential issues.',
                when: 'Use this right after uploading a new document to prepare it for your case.',
                tip: 'Process documents before registering them to catch errors early.'
            },
            'register': {
                what: 'Creates an official, tamper-proof record',
                details: 'Registering a document adds it to your secure registry with a unique fingerprint (hash). If anyone tries to alter it later, the system will detect the change.',
                when: 'Register documents you plan to use as evidence or submit to court.',
                tip: 'Once registered, the document cannot be modified without detection.'
            },
            'upload': {
                what: 'Adds a file from your computer to Semptify',
                details: 'Drag and drop files or click to browse. Supports PDF, Word docs, images (JPG, PNG), and text files up to 25MB.',
                when: 'Upload any document relevant to your case - leases, notices, receipts, photos, etc.',
                tip: 'Upload original documents when possible for the strongest evidence.'
            },
            'download': {
                what: 'Saves a copy to your computer',
                details: 'Downloads the file to your default downloads folder. You can then print it, email it, or store it offline.',
                when: 'Download documents you need to submit elsewhere or keep as backup.',
                tip: 'Downloaded files are copies - the originals stay safe in Semptify.'
            },
            'delete': {
                what: 'Permanently removes this item',
                details: 'This action cannot be undone. The item will be completely erased from the system.',
                when: 'Only delete items you are certain you no longer need.',
                tip: '⚠️ Consider archiving instead if you might need this later.'
            },
            'remove': {
                what: 'Takes this item out of the current view',
                details: 'Removes the item from this list or queue but does not permanently delete it.',
                when: 'Use when you want to clear something from a working queue.',
                tip: 'Removed items may still exist in other parts of the system.'
            },
            'clear': {
                what: 'Removes all items and resets to empty',
                details: 'Clears everything in the current list or queue at once.',
                when: 'Use when you want to start fresh or have processed all items.',
                tip: 'Make sure you have saved or processed important items first.'
            },
            'refresh': {
                what: 'Reloads the latest data from the server',
                details: 'Fetches the most current information. Useful if data might have changed or if something looks outdated.',
                when: 'Refresh when waiting for updates or if the display seems stale.',
                tip: 'Auto-refresh happens every few minutes, but you can force it anytime.'
            },
            'save': {
                what: 'Stores your changes permanently',
                details: 'Saves all the edits you have made so they are not lost.',
                when: 'Always save before leaving a page or closing a form.',
                tip: 'Look for the green checkmark to confirm your save succeeded.'
            },
            'cancel': {
                what: 'Discards changes and goes back',
                details: 'Abandons any edits you made and returns to the previous screen.',
                when: 'Click cancel if you made a mistake or changed your mind.',
                tip: 'Unsaved changes will be lost when you cancel.'
            },
            'submit': {
                what: 'Sends your information for processing',
                details: 'Submits the form or request. Once submitted, you may not be able to make changes.',
                when: 'Submit when you have reviewed everything and are ready to proceed.',
                tip: 'Double-check all fields before submitting.'
            },
            'add': {
                what: 'Creates a new entry',
                details: 'Adds a new item, event, document, or record to the system.',
                when: 'Use whenever you need to include something new.',
                tip: 'Fill in all required fields (marked with *) to complete the addition.'
            },
            'edit': {
                what: 'Opens this item for modification',
                details: 'Allows you to change or update the existing information.',
                when: 'Edit when you need to correct errors or add new details.',
                tip: 'Remember to save after making your changes.'
            },
            'view': {
                what: 'Opens for detailed examination',
                details: 'Shows the complete information in a read-only format.',
                when: 'View when you want to review without making changes.',
                tip: 'Click Edit if you need to make modifications.'
            },
            'search': {
                what: 'Finds items matching your keywords',
                details: 'Type words, names, dates, or case numbers to locate specific items quickly.',
                when: 'Use search when you know what you are looking for.',
                tip: 'Try different keywords if your first search does not find it.'
            },
            'filter': {
                what: 'Shows only items matching your criteria',
                details: 'Narrows down the list to show only items that match specific conditions like date range, type, or status.',
                when: 'Use filters when you have many items and need to focus on specific ones.',
                tip: 'Click "Clear Filters" to see all items again.'
            },
            'export': {
                what: 'Creates a downloadable file of your data',
                details: 'Generates a file (PDF, Excel, or CSV) containing the selected information that you can save or share.',
                when: 'Export when you need to share data with lawyers, courts, or keep offline records.',
                tip: 'Choose the right format - PDF for printing, Excel/CSV for data analysis.'
            },
            'import': {
                what: 'Brings in data from an external file',
                details: 'Loads information from a file on your computer into Semptify.',
                when: 'Import when you have existing data in spreadsheets or other formats.',
                tip: 'Make sure your file matches the expected format template.'
            },
            'sync': {
                what: 'Updates to match your cloud storage',
                details: 'Connects with Google Drive, OneDrive, or Dropbox to synchronize your files.',
                when: 'Sync after connecting a new cloud account or to get the latest files.',
                tip: 'Syncing happens automatically once connected.'
            },
            'verify': {
                what: 'Checks authenticity and accuracy',
                details: 'Confirms that the document has not been altered and matches its registered fingerprint.',
                when: 'Verify before submitting documents to court or sharing with others.',
                tip: 'A green checkmark means the document is authentic and unchanged.'
            },
            'validate': {
                what: 'Checks that all required information is complete',
                details: 'Reviews the form or document to ensure nothing important is missing or incorrectly formatted.',
                when: 'Validate before finalizing to catch errors.',
                tip: 'Fix any issues highlighted in red before proceeding.'
            },
            'generate': {
                what: 'Automatically creates content based on your data',
                details: 'Uses the information you have entered to produce documents, reports, or forms.',
                when: 'Use generate to quickly create standard documents from templates.',
                tip: 'Always review generated content before using it.'
            },
            'analyze': {
                what: 'Examines your data and provides insights',
                details: 'Uses AI to review your documents and suggest relevant laws, arguments, or actions.',
                when: 'Analyze to get smart recommendations for your case.',
                tip: 'Analysis suggestions are guidance only - not legal advice.'
            },
            'connect': {
                what: 'Links to an external service',
                details: 'Sets up a connection to cloud storage, calendar, or other services.',
                when: 'Connect to integrate your existing accounts with Semptify.',
                tip: 'You will be asked to authorize the connection securely.'
            },
            'configure': {
                what: 'Sets up options and preferences',
                details: 'Customizes how this feature works according to your needs.',
                when: 'Configure when you first use a feature or want to change its behavior.',
                tip: 'Default settings work for most users.'
            },
            'enable': {
                what: 'Turns on this feature',
                details: 'Activates a capability that was previously off.',
                when: 'Enable features you want to use.',
                tip: 'Some features may require additional setup after enabling.'
            },
            'disable': {
                what: 'Turns off this feature',
                details: 'Deactivates a capability. Your data is preserved and can be restored by enabling again.',
                when: 'Disable features you do not need to simplify your interface.',
                tip: 'Disabling does not delete your data.'
            },
            'login': {
                what: 'Signs in to your account',
                details: 'Enter your email and password to access your Semptify account.',
                when: 'Login when you start a new session.',
                tip: 'Use "Remember Me" on your personal devices for convenience.'
            },
            'logout': {
                what: 'Signs out and ends your session',
                details: 'Securely logs you out. All unsaved work should be saved first.',
                when: 'Always logout when using shared or public computers.',
                tip: 'Your data is safely stored and will be there when you return.'
            },
            'help': {
                what: 'Shows guidance and explanations',
                details: 'Opens help information about how to use this feature.',
                when: 'Click help whenever you are unsure how something works.',
                tip: 'Press H on your keyboard to toggle help mode on any page.'
            }
        },

        // Domain context with detailed explanations
        domains: {
            'document': {
                what: 'Legal Documents & Files',
                details: 'Any files related to your case - leases, notices, court papers, photos, receipts, letters, and more.',
                when: 'Work with documents when building your case or responding to legal matters.',
                tip: 'Keep all documents organized by type and date for easy access.'
            },
            'intake': {
                what: 'Document Collection & Processing',
                details: 'The starting point for new documents. Upload, scan, and prepare files before adding them to your case.',
                when: 'Use intake when you have new documents to add to your case.',
                tip: 'Process documents through intake to extract key information automatically.'
            },
            'queue': {
                what: 'Processing Queue',
                details: 'A list of items waiting to be handled. Shows what needs attention or is being worked on.',
                when: 'Check the queue to see what tasks are pending.',
                tip: 'Items move through the queue as they are processed.'
            },
            'registry': {
                what: 'Official Document Registry',
                details: 'Your tamper-proof record of all registered documents. Each document gets a unique fingerprint that proves it has not been altered.',
                when: 'Check the registry to verify document authenticity or find registered files.',
                tip: 'Registered documents are your strongest evidence.'
            },
            'vault': {
                what: 'Secure Encrypted Storage',
                details: 'Extra-secure storage for your most sensitive files. Uses bank-level encryption to keep documents safe.',
                when: 'Store highly sensitive documents like financial records or personal information in the vault.',
                tip: 'Vault documents have additional security but are slightly slower to access.'
            },
            'case': {
                what: 'Your Legal Case',
                details: 'The overall legal matter you are working on - could be eviction defense, tenant rights, small claims, or other proceedings.',
                when: 'Reference your case information when filing documents or tracking progress.',
                tip: 'Keep your case number handy - you will need it for court filings.'
            },
            'timeline': {
                what: 'Event Timeline',
                details: 'A chronological view showing all events, deadlines, and actions in your case from start to present.',
                when: 'Use the timeline to see the history of your case or plan next steps.',
                tip: 'A clear timeline helps you and your lawyer understand the case story.'
            },
            'calendar': {
                what: 'Calendar & Deadlines',
                details: 'Your schedule of important dates - court hearings, filing deadlines, response due dates, and reminders.',
                when: 'Check calendar regularly so you never miss a deadline.',
                tip: 'Set reminders at least 3 days before important deadlines.'
            },
            'brain': {
                what: 'AI Legal Assistant',
                details: 'Your intelligent helper that can answer legal questions, suggest strategies, and help you understand complex topics.',
                when: 'Ask the Brain when you need help understanding something or want suggestions.',
                tip: 'The Brain provides guidance but is not a substitute for professional legal advice.'
            },
            'complaint': {
                what: 'Legal Complaints & Filings',
                details: 'Formal complaints filed with courts or agencies. Includes HUD complaints, court filings, and formal grievances.',
                when: 'Use complaint features when you need to file official complaints.',
                tip: 'Review all complaint forms carefully before filing.'
            },
            'evidence': {
                what: 'Supporting Evidence',
                details: 'Documents, photos, and records that support your case. Evidence must be properly handled to be accepted in court.',
                when: 'Organize evidence when preparing for hearings or building your argument.',
                tip: 'Label evidence clearly and maintain chain of custody.'
            },
            'court': {
                what: 'Court Information',
                details: 'Details about court procedures, filing requirements, hearing schedules, and what to expect.',
                when: 'Reference court information when preparing filings or attending hearings.',
                tip: 'Each court has specific rules - make sure you follow the right ones.'
            },
            'deadline': {
                what: 'Important Deadlines',
                details: 'Critical dates that require action. Missing deadlines can seriously hurt your case.',
                when: 'Monitor deadlines constantly and take action well before they arrive.',
                tip: '⚠️ Court deadlines are strict - late filings may be rejected.'
            },
            'template': {
                what: 'Document Templates',
                details: 'Pre-made forms and documents that you can customize for your case. Saves time and ensures proper formatting.',
                when: 'Use templates instead of starting from scratch.',
                tip: 'Fill in all the highlighted fields in templates.'
            },
            'cloud': {
                what: 'Cloud Storage',
                details: 'Online storage services like Google Drive, OneDrive, or Dropbox where you may have existing files.',
                when: 'Connect cloud storage to import existing documents automatically.',
                tip: 'Syncing keeps your files backed up in multiple places.'
            },
            'storage': {
                what: 'File Storage',
                details: 'Where your documents and data are saved. Semptify stores everything securely with automatic backups.',
                when: 'Manage storage when you need to organize files or free up space.',
                tip: 'Your data is automatically backed up every day.'
            },
            'eviction': {
                what: 'Eviction Defense',
                details: 'Tools and resources for defending against eviction. Tracks notices, court dates, and defense strategies.',
                when: 'Use eviction features if you are facing or defending against eviction.',
                tip: 'Document everything from your landlord immediately.'
            },
            'tenant': {
                what: 'Tenant Rights & Information',
                details: 'Resources about your rights as a tenant, including fair housing laws and landlord obligations.',
                when: 'Research tenant rights when you believe your landlord has violated the law.',
                tip: 'Know your local tenant protection laws - they vary by location.'
            },
            'landlord': {
                what: 'Landlord Information',
                details: 'Records about your landlord, property manager, or property owner.',
                when: 'Reference landlord information when filing complaints or sending notices.',
                tip: 'Keep records of all communications with your landlord.'
            },
            'research': {
                what: 'Legal Research',
                details: 'Tools to find relevant laws, court cases, and legal information that applies to your situation.',
                when: 'Research when you need to understand the law or find supporting precedents.',
                tip: 'Focus on laws from your specific state and city.'
            },
            'form': {
                what: 'Legal Forms',
                details: 'Official forms required for court filings, complaints, and legal procedures.',
                when: 'Use official forms when submitting to courts or agencies.',
                tip: 'Make sure you have the most current version of required forms.'
            },
            'hearing': {
                what: 'Court Hearings',
                details: 'Scheduled court appearances where your case will be heard by a judge.',
                when: 'Prepare thoroughly before each hearing.',
                tip: 'Arrive early and bring all relevant documents.'
            },
            'notice': {
                what: 'Legal Notices',
                details: 'Official notifications - could be notices to quit, notices from the court, or notices you send.',
                when: 'Track all notices carefully and respond within deadlines.',
                tip: 'Keep copies of all notices with dates received.'
            }
        },

        // Icon meanings with more context
        icons: {
            '⚙️': { what: 'Process or Configure', details: 'Click to process this item or access settings.' },
            '📋': { what: 'Register Document', details: 'Add to official registry with tamper-proof tracking.' },
            '🗑️': { what: 'Delete or Remove', details: 'Permanently remove this item. Cannot be undone.' },
            '🔄': { what: 'Refresh or Sync', details: 'Reload data or synchronize with external services.' },
            '➕': { what: 'Add New', details: 'Create a new item, entry, or record.' },
            '✏️': { what: 'Edit', details: 'Modify or update this item.' },
            '👁️': { what: 'View Details', details: 'Open to see full information.' },
            '💾': { what: 'Save Changes', details: 'Store your modifications permanently.' },
            '📤': { what: 'Upload File', details: 'Add a file from your computer.' },
            '📥': { what: 'Download', details: 'Save a copy to your computer.' },
            '🔍': { what: 'Search', details: 'Find items using keywords.' },
            '🔒': { what: 'Secure/Locked', details: 'This item is encrypted or protected.' },
            '🔓': { what: 'Unlocked/Public', details: 'This item is accessible or shareable.' },
            '⚠️': { what: 'Warning', details: 'Attention needed - review this carefully.' },
            '✅': { what: 'Complete/Verified', details: 'This has been checked and confirmed.' },
            '❌': { what: 'Cancel/Error', details: 'Problem detected or action cancelled.' },
            '📁': { what: 'Folder', details: 'A collection or category of items.' },
            '📄': { what: 'Document', details: 'A single file or document.' },
            '🗓️': { what: 'Calendar/Date', details: 'Related to scheduling or dates.' },
            '⏰': { what: 'Deadline/Time', details: 'Time-sensitive - pay attention to this date.' },
            '🧠': { what: 'AI Assistant', details: 'Smart feature powered by artificial intelligence.' },
            '☁️': { what: 'Cloud Storage', details: 'Stored online or synced with cloud services.' },
            '🔗': { what: 'Link/Connect', details: 'Connection to related item or external service.' },
            '📊': { what: 'Statistics', details: 'Data visualization or analytics.' },
            '❓': { what: 'Help', details: 'Click for guidance and explanations.' },
            '⚖️': { what: 'Legal/Court', details: 'Related to legal proceedings or courts.' },
            '🏠': { what: 'Housing/Property', details: 'Related to your residence or property.' },
            '💰': { what: 'Financial', details: 'Related to money, payments, or fees.' },
            '📞': { what: 'Contact', details: 'Phone number or communication.' },
            '✉️': { what: 'Message/Email', details: 'Communication or notification.' },
            '🎯': { what: 'Goal/Target', details: 'Objective or important milestone.' },
            '🛡️': { what: 'Protected', details: 'This item has special protection or rights.' }
        },

        // Common UI element patterns with detailed help
        uiPatterns: {
            'case-number': {
                what: 'Case Number Field',
                details: 'Enter your official court case number (e.g., CV-2024-12345). Find this on any court documents.',
                when: 'Required for all court-related actions.',
                tip: 'The case number format varies by court - check your documents.'
            },
            'upload-zone': {
                what: 'File Upload Area',
                details: 'Drag files here from your computer, or click to browse. Supports PDF, Word, images up to 25MB.',
                when: 'Use to add new documents to your case.',
                tip: 'You can upload multiple files at once.'
            },
            'date-picker': {
                what: 'Date Selection',
                details: 'Click to open a calendar and select a date.',
                when: 'Use when entering dates for events, deadlines, or documents.',
                tip: 'Dates are in month/day/year format.'
            },
            'dropdown': {
                what: 'Selection Menu',
                details: 'Click to see available options and select one.',
                when: 'Use when choosing from a predefined list.',
                tip: 'You can usually type to search within the dropdown.'
            },
            'checkbox': {
                what: 'Checkbox Option',
                details: 'Click to enable or disable this option.',
                when: 'Use to turn features on/off or select multiple items.',
                tip: 'Checked = enabled, unchecked = disabled.'
            },
            'status-badge': {
                what: 'Status Indicator',
                details: 'Shows the current state of this item (pending, complete, error, etc.).',
                when: 'Check status to see where things stand.',
                tip: 'Green = good, Yellow = attention needed, Red = problem.'
            },
            'tab': {
                what: 'Navigation Tab',
                details: 'Click to switch between different sections or views.',
                when: 'Use tabs to navigate without leaving the page.',
                tip: 'The active tab is highlighted.'
            },
            'modal': {
                what: 'Popup Window',
                details: 'A dialog box that requires your attention. Complete or close it to continue.',
                when: 'Appears when additional input is needed.',
                tip: 'Click outside or press Escape to close most popups.'
            },
            'table': {
                what: 'Data Table',
                details: 'Lists of items with sortable columns. Click column headers to sort.',
                when: 'Use to browse, search, and manage multiple items.',
                tip: 'Look for action buttons in the rightmost column.'
            },
            'progress-bar': {
                what: 'Progress Indicator',
                details: 'Shows how far along a process has completed.',
                when: 'Watch during uploads, processing, or multi-step tasks.',
                tip: 'Wait for 100% before leaving the page.'
            }
        }
    },    /**
     * Initialize the help system
     */
    init(mode = 'auto') {
        if (this.initialized) return;
        
        console.log('🎓 Semptify Help System initializing (self-generating mode)...');
        
        // Inject CSS styles
        this.injectStyles();
        
        // Create the floating help toggle button
        this.createHelpToggle();
        
        // Analyze the page and generate help
        this.analyzePage();
        
        // Set up mutation observer for dynamic content
        this.observeChanges();
        
        this.initialized = true;
        console.log('✅ Help system ready');
    },

    /**
     * Analyze the page and generate help for all elements
     */
    analyzePage() {
        console.log('🔍 Analyzing page structure...');
        
        // Find and enhance buttons
        this.analyzeButtons();
        
        // Find and enhance forms
        this.analyzeForms();
        
        // Find and enhance cards
        this.analyzeCards();
        
        // Find and enhance tabs
        this.analyzeTabs();
        
        // Enhance existing help elements
        this.enhanceExistingHelp();
    },

    /**
     * Analyze all buttons and generate tooltips
     */
    analyzeButtons() {
        const buttons = document.querySelectorAll('button, .btn, [role="button"], input[type="submit"]');
        
        buttons.forEach(btn => {
            // Skip if already processed
            if (btn.classList.contains('help-processed') || btn.closest('.semptify-help-toggle')) return;
            
            const helpText = this.generateButtonHelp(btn);
            if (helpText) {
                this.addTooltip(btn, helpText);
            }
            btn.classList.add('help-processed');
        });
        
        console.log(`📌 Processed ${buttons.length} buttons`);
    },

    /**
     * Generate detailed, user-friendly help text for a button
     */
    generateButtonHelp(btn) {
        // Get button text (handling icons)
        let text = btn.textContent.trim().toLowerCase();
        let title = btn.getAttribute('title') || '';
        let ariaLabel = btn.getAttribute('aria-label') || '';
        let id = btn.id || '';
        let classes = btn.className || '';

        // Extract meaningful words
        const allText = `${text} ${title} ${ariaLabel} ${id} ${classes}`.toLowerCase();

        // Find matching action (now returns object with detailed info)
        let actionKey = '';
        let actionInfo = null;
        for (const [key, info] of Object.entries(this.knowledge.actions)) {
            if (allText.includes(key)) {
                actionKey = key;
                actionInfo = info;
                break;
            }
        }

        // Find domain context (now returns object with detailed info)
        let domainKey = '';
        let domainInfo = null;
        for (const [key, info] of Object.entries(this.knowledge.domains)) {
            if (allText.includes(key)) {
                domainKey = key;
                domainInfo = info;
                break;
            }
        }

        // Check for icons (now returns object with detailed info)
        let iconInfo = null;
        for (const [icon, info] of Object.entries(this.knowledge.icons)) {
            if (btn.innerHTML.includes(icon)) {
                iconInfo = info;
                break;
            }
        }

        // Check for UI patterns
        let patternInfo = null;
        for (const [pattern, info] of Object.entries(this.knowledge.uiPatterns || {})) {
            if (allText.includes(pattern.replace('-', ' ')) || allText.includes(pattern)) {
                patternInfo = info;
                break;
            }
        }

        // Generate detailed, user-friendly help
        return this.buildDetailedHelp(actionInfo, domainInfo, iconInfo, patternInfo, text, title);
    },

    /**
     * Build a detailed, user-friendly help message
     */
    buildDetailedHelp(actionInfo, domainInfo, iconInfo, patternInfo, text, title) {
        let helpParts = [];
        
        // Start with what this does
        if (actionInfo && actionInfo.what) {
            helpParts.push(`<strong>What it does:</strong> ${actionInfo.what}`);
            
            if (actionInfo.details) {
                helpParts.push(`<span class="help-details">${actionInfo.details}</span>`);
            }
        }
        
        // Add domain context
        if (domainInfo && domainInfo.what) {
            helpParts.push(`<strong>Related to:</strong> ${domainInfo.what}`);
            if (domainInfo.details && !actionInfo) {
                helpParts.push(`<span class="help-details">${domainInfo.details}</span>`);
            }
        }
        
        // Add when to use
        if (actionInfo && actionInfo.when) {
            helpParts.push(`<strong>When to use:</strong> ${actionInfo.when}`);
        } else if (domainInfo && domainInfo.when) {
            helpParts.push(`<strong>When to use:</strong> ${domainInfo.when}`);
        } else if (patternInfo && patternInfo.when) {
            helpParts.push(`<strong>When to use:</strong> ${patternInfo.when}`);
        }
        
        // Add tip
        if (actionInfo && actionInfo.tip) {
            helpParts.push(`<span class="help-tip">💡 ${actionInfo.tip}</span>`);
        } else if (domainInfo && domainInfo.tip) {
            helpParts.push(`<span class="help-tip">💡 ${domainInfo.tip}</span>`);
        } else if (patternInfo && patternInfo.tip) {
            helpParts.push(`<span class="help-tip">💡 ${patternInfo.tip}</span>`);
        }
        
        // If we found detailed help, return it
        if (helpParts.length > 0) {
            return helpParts.join('<br>');
        }
        
        // Fall back to icon info
        if (iconInfo) {
            if (typeof iconInfo === 'object') {
                return `<strong>${iconInfo.what}</strong><br>${iconInfo.details || ''}`;
            }
            return iconInfo;
        }
        
        // Fall back to pattern info
        if (patternInfo) {
            let parts = [`<strong>${patternInfo.what}</strong>`];
            if (patternInfo.details) parts.push(patternInfo.details);
            if (patternInfo.when) parts.push(`<strong>When:</strong> ${patternInfo.when}`);
            if (patternInfo.tip) parts.push(`<span class="help-tip">💡 ${patternInfo.tip}</span>`);
            return parts.join('<br>');
        }
        
        // Fall back to title attribute
        if (title) {
            return `<strong>${title}</strong>`;
        }
        
        // Generate simple help from button text
        if (text.length > 2 && text.length < 50) {
            return `<strong>Click to ${text}</strong>`;
        }

        return null;
    },    /**
     * Add a tooltip to an element
     */
    addTooltip(element, text) {
        // Create tooltip with enhanced formatting
        const tooltip = document.createElement('div');
        tooltip.className = 'semptify-auto-tooltip';
        
        // Check if text already has HTML formatting
        if (text.includes('<strong>') || text.includes('<br>')) {
            tooltip.innerHTML = `<div class="tooltip-content">${text}</div>`;
        } else {
            tooltip.innerHTML = `<span class="tooltip-icon">💡</span> ${text}`;
        }

        // Append to body for proper positioning (not clipped by overflow)
        document.body.appendChild(tooltip);

        // Add class and store reference
        element.classList.add('has-semptify-tooltip');
        element._semptifyTooltip = tooltip;

        // Position tooltip on hover
        element.addEventListener('mouseenter', () => {
            if (!document.body.classList.contains('help-mode')) return;
            this.positionTooltip(element, tooltip);
            tooltip.style.display = 'block';
        });

        element.addEventListener('mouseleave', () => {
            tooltip.style.display = 'none';
        });
    },    /**
     * Position tooltip so it's always visible - gravitates toward card center
     */
    positionTooltip(element, tooltip) {
        // Make tooltip visible briefly to measure it
        tooltip.style.visibility = 'hidden';
        tooltip.style.display = 'block';
        
        const rect = element.getBoundingClientRect();
        const tooltipRect = tooltip.getBoundingClientRect();
        const viewportWidth = window.innerWidth;
        const viewportHeight = window.innerHeight;
        
        // Find the parent card/container
        const card = element.closest('.card, .panel, .section, [class*="card"], .intake-section, .tab-content');
        let cardRect = card ? card.getBoundingClientRect() : { left: 0, right: viewportWidth, top: 0, bottom: viewportHeight };
        
        // Calculate card center
        const cardCenterX = (cardRect.left + cardRect.right) / 2;
        const cardCenterY = (cardRect.top + cardRect.bottom) / 2;
        
        // Element center
        const elemCenterX = rect.left + rect.width / 2;
        const elemCenterY = rect.top + rect.height / 2;
        
        // Reset arrow classes
        tooltip.classList.remove('arrow-up', 'arrow-down', 'arrow-left', 'arrow-right');
        
        let top, left;
        
        // Determine if element is in top or bottom half of card
        const inTopHalf = elemCenterY < cardCenterY;
        
        // Determine if element is in left or right half of card
        const inLeftHalf = elemCenterX < cardCenterX;
        
        // Position tooltip toward center of card
        if (inTopHalf) {
            // Element is in top half, show tooltip BELOW (toward center)
            top = rect.bottom + 10;
            tooltip.classList.add('arrow-up');
        } else {
            // Element is in bottom half, show tooltip ABOVE (toward center)
            top = rect.top - tooltipRect.height - 10;
            tooltip.classList.add('arrow-down');
        }
        
        // Horizontal positioning - gravitate toward card center
        if (inLeftHalf) {
            // Element is on left side, position tooltip to the right
            left = rect.left;
            // But not past the right edge
            if (left + tooltipRect.width > viewportWidth - 20) {
                left = viewportWidth - tooltipRect.width - 20;
            }
        } else {
            // Element is on right side, position tooltip to the left
            left = rect.right - tooltipRect.width;
            // But not past the left edge
            if (left < 20) {
                left = 20;
            }
        }
        
        // Final bounds check
        if (top < 10) top = 10;
        if (top + tooltipRect.height > viewportHeight - 10) {
            top = viewportHeight - tooltipRect.height - 10;
        }
        
        tooltip.style.top = `${top}px`;
        tooltip.style.left = `${left}px`;
        tooltip.style.visibility = 'visible';
    },

    /**
     * Analyze forms and generate field help
     */
    analyzeForms() {
        const forms = document.querySelectorAll('form, .form-group, .input-group');
        let fieldCount = 0;
        
        forms.forEach(form => {
            const inputs = form.querySelectorAll('input, select, textarea');
            inputs.forEach(input => {
                if (input.classList.contains('help-processed')) return;
                
                const helpText = this.generateInputHelp(input);
                if (helpText) {
                    this.addInputHelp(input, helpText);
                    fieldCount++;
                }
                input.classList.add('help-processed');
            });
        });
        
        console.log(`📝 Processed ${fieldCount} form fields`);
    },

    /**
     * Generate detailed help for form inputs
     */
    generateInputHelp(input) {
        const label = input.labels?.[0]?.textContent || '';
        const placeholder = input.placeholder || '';
        const name = input.name || '';
        const type = input.type || '';
        const ariaLabel = input.getAttribute('aria-label') || '';
        const id = input.id || '';

        const context = `${label} ${placeholder} ${name} ${ariaLabel} ${id}`.toLowerCase();

        // Check for UI patterns first
        for (const [pattern, info] of Object.entries(this.knowledge.uiPatterns || {})) {
            const patternKey = pattern.replace('-', ' ');
            if (context.includes(patternKey) || context.includes(pattern)) {
                return `<strong>${info.what}</strong><br>${info.details}${info.tip ? `<br><span class="help-tip">💡 ${info.tip}</span>` : ''}`;
            }
        }

        // Find domain context (now with detailed info)
        for (const [key, info] of Object.entries(this.knowledge.domains)) {
            if (context.includes(key)) {
                if (typeof info === 'object') {
                    return `<strong>${info.what}</strong><br>${info.details}${info.tip ? `<br><span class="help-tip">💡 ${info.tip}</span>` : ''}`;
                }
                return `Enter ${key}: ${info}`;
            }
        }

        // Detailed type-based help
        const typeHelp = {
            'email': {
                what: 'Email Address',
                details: 'Enter a valid email address (e.g., you@example.com)',
                tip: 'Use an email you check regularly for important notifications.'
            },
            'password': {
                what: 'Password',
                details: 'Enter a secure password. Use a mix of letters, numbers, and symbols.',
                tip: 'At least 8 characters with uppercase, lowercase, and numbers.'
            },
            'date': {
                what: 'Date Selection',
                details: 'Click to open the calendar and select a date.',
                tip: 'Use the arrows to navigate between months.'
            },
            'file': {
                what: 'File Upload',
                details: 'Click to browse your computer and select a file to upload.',
                tip: 'Supported formats: PDF, Word, images. Max size: 25MB.'
            },
            'number': {
                what: 'Numeric Value',
                details: 'Enter a number. You can use the arrows or type directly.',
                tip: 'Check for min/max limits on this field.'
            },
            'tel': {
                what: 'Phone Number',
                details: 'Enter a phone number including area code.',
                tip: 'Format: (555) 123-4567 or 555-123-4567'
            },
            'url': {
                what: 'Web Address',
                details: 'Enter a complete URL starting with http:// or https://',
                tip: 'Copy and paste from your browser for accuracy.'
            },
            'search': {
                what: 'Search Field',
                details: 'Type keywords to search. Results update as you type.',
                tip: 'Try different keywords if your first search doesn\'t find what you need.'
            },
            'text': {
                what: 'Text Input',
                details: 'Enter the requested information in this field.',
                tip: 'Required fields are marked with an asterisk (*).'
            }
        };

        if (typeHelp[type]) {
            const info = typeHelp[type];
            return `<strong>${info.what}</strong><br>${info.details}<br><span class="help-tip">💡 ${info.tip}</span>`;
        }

        if (label && label.trim()) {
            return `<strong>Enter ${label.trim()}</strong><br>Fill in this field with the requested information.`;
        }

        return null;
    },    /**
     * Add help indicator to form input
     */
    addInputHelp(input, text) {
        const wrapper = input.closest('.form-group, .input-group') || input.parentElement;
        if (!wrapper || wrapper.querySelector('.semptify-field-help')) return;
        
        const help = document.createElement('small');
        help.className = 'semptify-field-help';
        help.innerHTML = `❓ ${text}`;
        wrapper.appendChild(help);
    },

    /**
     * Analyze cards/sections and generate help banners
     */
    analyzeCards() {
        const cards = document.querySelectorAll('.card, .panel, .section, [class*="card"]');
        let cardCount = 0;
        
        cards.forEach(card => {
            if (card.classList.contains('help-processed')) return;
            if (card.querySelector('.card-help')) return; // Already has manual help
            
            const helpText = this.generateCardHelp(card);
            if (helpText) {
                this.addCardHelp(card, helpText);
                cardCount++;
            }
            card.classList.add('help-processed');
        });
        
        console.log(`🃏 Processed ${cardCount} cards/sections`);
    },

    /**
     * Generate help for a card/section
     */
    generateCardHelp(card) {
        // Look for header
        const header = card.querySelector('h1, h2, h3, h4, h5, .card-header, .card-title');
        if (!header) return null;
        
        const title = header.textContent.trim().toLowerCase();
        
        // Find domain context
        for (const [key, desc] of Object.entries(this.knowledge.domains)) {
            if (title.includes(key)) {
                return {
                    title: header.textContent.trim(),
                    description: desc
                };
            }
        }
        
        // Generic card help based on title
        if (title.length > 3 && title.length < 100) {
            return {
                title: header.textContent.trim(),
                description: `This section contains ${header.textContent.trim().toLowerCase()} information and controls.`
            };
        }
        
        return null;
    },

    /**
     * Add help banner to card
     */
    addCardHelp(card, helpInfo) {
        const banner = document.createElement('div');
        banner.className = 'card-help semptify-auto-card-help';
        banner.innerHTML = `
            <span class="help-icon">❓</span>
            <div class="help-content">
                <strong>${helpInfo.title}</strong>: ${helpInfo.description}
            </div>
        `;
        
        // Insert at top of card body or card itself
        const cardBody = card.querySelector('.card-body') || card;
        cardBody.insertBefore(banner, cardBody.firstChild);
    },

    /**
     * Analyze tabs and add descriptions
     */
    analyzeTabs() {
        const tabs = document.querySelectorAll('[role="tab"], .nav-tab, .tab-btn, [data-toggle="tab"]');
        let tabCount = 0;
        
        tabs.forEach(tab => {
            if (tab.classList.contains('help-processed')) return;
            
            const helpText = this.generateTabHelp(tab);
            if (helpText) {
                this.addTooltip(tab, helpText);
                tabCount++;
            }
            tab.classList.add('help-processed');
        });
        
        console.log(`📑 Processed ${tabCount} tabs`);
    },

    /**
     * Generate help for a tab
     */
    generateTabHelp(tab) {
        const text = tab.textContent.trim().toLowerCase();
        
        // Find domain context
        for (const [key, desc] of Object.entries(this.knowledge.domains)) {
            if (text.includes(key)) {
                return `View ${key}: ${desc}`;
            }
        }
        
        if (text.length > 2 && text.length < 30) {
            return `Switch to ${tab.textContent.trim()} view`;
        }
        
        return null;
    },

    /**
     * Enhance any existing help elements
     */
    enhanceExistingHelp() {
        // Look for elements with title attributes and enhance them
        const titled = document.querySelectorAll('[title]:not(.help-processed)');
        titled.forEach(el => {
            if (el.closest('.semptify-help-toggle')) return;
            el.classList.add('has-semptify-tooltip');
            el.classList.add('help-processed');
        });
    },

    /**
     * Observe DOM changes and auto-analyze new content
     */
    observeChanges() {
        const observer = new MutationObserver((mutations) => {
            let shouldAnalyze = false;
            mutations.forEach(mutation => {
                if (mutation.addedNodes.length > 0) {
                    shouldAnalyze = true;
                }
            });
            
            if (shouldAnalyze) {
                // Debounce analysis
                clearTimeout(this.analyzeTimeout);
                this.analyzeTimeout = setTimeout(() => {
                    this.analyzePage();
                }, 500);
            }
        });
        
        observer.observe(document.body, {
            childList: true,
            subtree: true
        });
    },

    /**
     * Create the floating help toggle button (draggable)
     */
    createHelpToggle() {
        // Don't create if already exists
        if (document.querySelector('.semptify-help-toggle')) return;
        
        const toggle = document.createElement('button');
        toggle.className = 'semptify-help-toggle';
        toggle.innerHTML = `
            <span class="drag-handle" title="Drag to move">⋮⋮</span>
            <span class="toggle-icon">❓</span>
            <span class="toggle-text">Help</span>
        `;
        toggle.setAttribute('title', 'Toggle help mode to see explanations for all features');
        
        // Click handler (only if not dragging)
        toggle.addEventListener('click', (e) => {
            if (!toggle.classList.contains('was-dragged')) {
                this.toggleHelp();
            }
            toggle.classList.remove('was-dragged');
        });
        
        // Make draggable
        this.makeDraggable(toggle);
        
        // Restore saved position
        this.restoreTogglePosition(toggle);
        
        document.body.appendChild(toggle);
    },

    /**
     * Make an element draggable with touch and mouse support
     */
    makeDraggable(element) {
        let isDragging = false;
        let hasMoved = false;
        let startX, startY, startLeft, startTop;
        
        const onStart = (e) => {
            // Only drag from the handle or element itself
            const touch = e.touches ? e.touches[0] : e;
            
            isDragging = true;
            hasMoved = false;
            
            const rect = element.getBoundingClientRect();
            startX = touch.clientX;
            startY = touch.clientY;
            startLeft = rect.left;
            startTop = rect.top;
            
            element.classList.add('dragging');
            element.style.transition = 'none';
            
            // Prevent text selection
            e.preventDefault();
        };
        
        const onMove = (e) => {
            if (!isDragging) return;
            
            const touch = e.touches ? e.touches[0] : e;
            const deltaX = touch.clientX - startX;
            const deltaY = touch.clientY - startY;
            
            // Only mark as moved if dragged more than 5px
            if (Math.abs(deltaX) > 5 || Math.abs(deltaY) > 5) {
                hasMoved = true;
            }
            
            // Calculate new position
            let newLeft = startLeft + deltaX;
            let newTop = startTop + deltaY;
            
            // Keep within viewport bounds
            const bounds = {
                minX: 0,
                maxX: window.innerWidth - element.offsetWidth,
                minY: 0,
                maxY: window.innerHeight - element.offsetHeight
            };
            
            newLeft = Math.max(bounds.minX, Math.min(bounds.maxX, newLeft));
            newTop = Math.max(bounds.minY, Math.min(bounds.maxY, newTop));
            
            // Apply position (switch from bottom/right to top/left for dragging)
            element.style.left = newLeft + 'px';
            element.style.top = newTop + 'px';
            element.style.right = 'auto';
            element.style.bottom = 'auto';
            
            e.preventDefault();
        };
        
        const onEnd = () => {
            if (!isDragging) return;
            
            isDragging = false;
            element.classList.remove('dragging');
            element.style.transition = '';
            
            if (hasMoved) {
                element.classList.add('was-dragged');
                // Save position
                this.saveTogglePosition(element);
                
                // Remove was-dragged after a short delay
                setTimeout(() => element.classList.remove('was-dragged'), 100);
            }
        };
        
        // Mouse events
        element.addEventListener('mousedown', onStart);
        document.addEventListener('mousemove', onMove);
        document.addEventListener('mouseup', onEnd);
        
        // Touch events
        element.addEventListener('touchstart', onStart, { passive: false });
        document.addEventListener('touchmove', onMove, { passive: false });
        document.addEventListener('touchend', onEnd);
    },

    /**
     * Save toggle button position to localStorage
     */
    saveTogglePosition(element) {
        const rect = element.getBoundingClientRect();
        const position = {
            left: rect.left,
            top: rect.top
        };
        localStorage.setItem('semptify_help_toggle_pos', JSON.stringify(position));
    },

    /**
     * Restore toggle button position from localStorage
     */
    restoreTogglePosition(element) {
        const saved = localStorage.getItem('semptify_help_toggle_pos');
        if (saved) {
            try {
                const pos = JSON.parse(saved);
                // Validate position is still within viewport
                if (pos.left >= 0 && pos.left <= window.innerWidth - 100 &&
                    pos.top >= 0 && pos.top <= window.innerHeight - 50) {
                    element.style.left = pos.left + 'px';
                    element.style.top = pos.top + 'px';
                    element.style.right = 'auto';
                    element.style.bottom = 'auto';
                }
            } catch (e) {
                console.warn('Failed to restore help toggle position');
            }
        }
    },

    /**
     * Toggle help mode on/off
     */
    toggleHelp() {
        this.helpEnabled = !this.helpEnabled;
        
        const toggle = document.querySelector('.semptify-help-toggle');
        
        if (this.helpEnabled) {
            document.body.classList.add('help-mode');
            toggle.classList.add('active');
            toggle.querySelector('.toggle-text').textContent = 'Help ON';
            console.log('🎓 Help mode ENABLED');
        } else {
            document.body.classList.remove('help-mode');
            toggle.classList.remove('active');
            toggle.querySelector('.toggle-text').textContent = 'Help';
            console.log('🎓 Help mode DISABLED');
        }
    },

    /**
     * Inject CSS styles for the help system
     */
    injectStyles() {
        if (document.getElementById('semptify-help-styles')) return;
        
        const styles = document.createElement('style');
        styles.id = 'semptify-help-styles';
        styles.textContent = `
            /* Help Toggle Button - Draggable */
            .semptify-help-toggle {
                position: fixed;
                bottom: 20px;
                right: 20px;
                z-index: 10000;
                display: flex;
                align-items: center;
                gap: 8px;
                padding: 12px 20px;
                background: linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%);
                color: white;
                border: none;
                border-radius: 25px;
                cursor: grab;
                font-size: 14px;
                font-weight: 600;
                box-shadow: 0 4px 15px rgba(59, 130, 246, 0.4);
                transition: all 0.3s ease, left 0s, top 0s;
                user-select: none;
                touch-action: none;
            }

            .semptify-help-toggle .drag-handle {
                opacity: 0.6;
                font-size: 12px;
                letter-spacing: -2px;
                cursor: grab;
                padding-right: 4px;
                border-right: 1px solid rgba(255,255,255,0.3);
                margin-right: 4px;
            }

            .semptify-help-toggle:hover .drag-handle {
                opacity: 1;
            }

            .semptify-help-toggle.dragging {
                cursor: grabbing;
                transform: scale(1.05);
                box-shadow: 0 8px 30px rgba(59, 130, 246, 0.6);
                opacity: 0.9;
            }

            .semptify-help-toggle.dragging .drag-handle {
                cursor: grabbing;
            }

            .semptify-help-toggle:hover:not(.dragging) {
                transform: translateY(-2px);
                box-shadow: 0 6px 20px rgba(59, 130, 246, 0.5);
            }

            .semptify-help-toggle.active {
                background: linear-gradient(135deg, #10b981 0%, #059669 100%);
                box-shadow: 0 4px 15px rgba(16, 185, 129, 0.4);
            }

            .semptify-help-toggle .toggle-icon {
                font-size: 18px;
            }

            /* Auto-generated tooltips - FIXED positioning */
            .semptify-auto-tooltip {
                display: none;
                position: fixed;
                background: linear-gradient(135deg, #1e3a5f 0%, #0f172a 100%);
                color: #e0f2fe;
                padding: 16px 18px;
                border-radius: 12px;
                font-size: 13px;
                line-height: 1.6;
                max-width: 380px;
                min-width: 280px;
                width: max-content;
                z-index: 99999;
                box-shadow: 0 8px 30px rgba(0, 0, 0, 0.4);
                border: 1px solid #3b82f6;
                pointer-events: none;
            }

            .semptify-auto-tooltip strong {
                color: #60a5fa;
                font-weight: 600;
                display: block;
                margin-bottom: 4px;
            }

            .semptify-auto-tooltip .help-details {
                color: #94a3b8;
                font-size: 12px;
                display: block;
                margin: 6px 0;
                padding-left: 8px;
                border-left: 2px solid #3b82f6;
            }

            .semptify-auto-tooltip .help-tip {
                display: block;
                margin-top: 10px;
                padding: 8px 12px;
                background: rgba(16, 185, 129, 0.15);
                border-radius: 6px;
                color: #34d399;
                font-size: 12px;
                border-left: 3px solid #10b981;
            }

            .semptify-auto-tooltip::after {
                content: '';
                position: absolute;
                border: 8px solid transparent;
            }
            
            /* Arrow pointing down (tooltip above element) */
            .semptify-auto-tooltip.arrow-down::after {
                top: 100%;
                left: 20px;
                border-top-color: #0f172a;
            }
            
            /* Arrow pointing up (tooltip below element) */
            .semptify-auto-tooltip.arrow-up::after {
                bottom: 100%;
                left: 20px;
                border-bottom-color: #0f172a;
            }

            .semptify-auto-tooltip .tooltip-icon {
                margin-right: 6px;
            }

            /* Show tooltips in help mode - handled by JS now */
            body.help-mode .has-semptify-tooltip {
                outline: 2px dashed #3b82f6 !important;
                outline-offset: 2px;
            }

            /* Field help */
            .semptify-field-help {
                display: none;
                color: #64748b;
                font-size: 11px;
                margin-top: 4px;
            }

            body.help-mode .semptify-field-help {
                display: block;
            }

            /* Auto card help */
            .semptify-auto-card-help {
                display: none;
                align-items: flex-start;
                gap: 10px;
                padding: 12px 15px;
                background: linear-gradient(135deg, #eff6ff 0%, #dbeafe 100%);
                border: 1px solid #bfdbfe;
                border-radius: 8px;
                margin-bottom: 15px;
                font-size: 13px;
                color: #1e40af;
            }

            body.help-mode .semptify-auto-card-help {
                display: flex;
            }

            .semptify-auto-card-help .help-icon {
                font-size: 18px;
            }

            /* Existing card-help styling */
            .card-help {
                display: none;
                align-items: flex-start;
                gap: 10px;
                padding: 12px 15px;
                background: linear-gradient(135deg, #eff6ff 0%, #dbeafe 100%);
                border: 1px solid #bfdbfe;
                border-radius: 8px;
                margin-bottom: 15px;
                font-size: 13px;
                color: #1e40af;
            }

            body.help-mode .card-help {
                display: flex;
            }

            .card-help .help-icon {
                font-size: 18px;
            }

            /* Help tooltip for existing has-help elements - FIXED positioning */
            .has-help {
                position: relative;
            }

            .has-help .help-tooltip {
                display: none;
                position: fixed;
                background: linear-gradient(135deg, #1e3a5f 0%, #0f172a 100%);
                color: #e0f2fe;
                padding: 10px 14px;
                border-radius: 8px;
                font-size: 12px;
                max-width: 280px;
                width: max-content;
                z-index: 99999;
                box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
                border: 1px solid #334155;
                pointer-events: none;
            }

            .has-help .help-tooltip::after {
                content: '';
                position: absolute;
                top: 100%;
                left: 50%;
                transform: translateX(-50%);
                border: 8px solid transparent;
                border-top-color: #0f172a;
            }

            body.help-mode .has-help:hover {
                outline: 2px dashed #3b82f6;
                outline-offset: 2px;
            }
        `;
        document.head.appendChild(styles);
        
        // Set up positioning for manual .has-help tooltips
        this.setupManualTooltips();
    },
    
    /**
     * Set up positioning for manually added .has-help tooltips
     */
    setupManualTooltips() {
        document.querySelectorAll('.has-help').forEach(el => {
            const tooltip = el.querySelector('.help-tooltip');
            if (!tooltip) return;
            
            // Move tooltip to body for proper z-index
            document.body.appendChild(tooltip);
            
            el.addEventListener('mouseenter', () => {
                if (!document.body.classList.contains('help-mode')) return;
                this.positionTooltip(el, tooltip);
                tooltip.style.display = 'block';
            });
            
            el.addEventListener('mouseleave', () => {
                tooltip.style.display = 'none';
            });
        });
    }
};

// Auto-initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    // Small delay to let page render
    setTimeout(() => SemptifyHelp.init('auto'), 100);
});
