/**
 * Semptify Guided Tour System
 * ============================
 * 
 * Step-by-step guided tours that help users navigate
 * the system with emotional awareness.
 */

const GuidedTour = {
    currentTour: null,
    currentStep: 0,
    overlay: null,
    tooltip: null,
    
    // Tour definitions
    tours: {
        welcome: {
            name: 'Welcome Tour',
            steps: [
                {
                    element: null, // Full screen
                    title: 'Welcome to Semptify',
                    content: 'I\'m here to help you protect your rights. Let me show you around.',
                    position: 'center',
                    emotionTrigger: 'session_start'
                },
                {
                    element: '.mission-header',
                    title: 'Your Mission Control',
                    content: 'This is your home base. It adapts to how you\'re feeling and shows what matters most right now.',
                    position: 'bottom'
                },
                {
                    element: '#todayTasks',
                    title: 'Today\'s Tasks',
                    content: 'These are your priorities for today, sorted by urgency. Completing them builds your case.',
                    position: 'top'
                },
                {
                    element: '#quickActions',
                    title: 'Quick Actions',
                    content: 'One-tap access to common tasks. Scan documents, check your briefcase, or get help.',
                    position: 'top'
                },
                {
                    element: '#floatingBar',
                    title: 'Always Available',
                    content: 'These buttons are always here. Capture evidence, see what\'s next, get help, or access crisis support.',
                    position: 'top'
                }
            ]
        },
        document_intake: {
            name: 'Document Upload Tour',
            steps: [
                {
                    element: '.document-type-selector',
                    title: 'Choose Document Type',
                    content: 'Select what kind of document you\'re uploading. This helps our AI analyze it correctly.',
                    position: 'bottom'
                },
                {
                    element: '.upload-zone',
                    title: 'Upload Your Document',
                    content: 'Drag and drop, click to browse, or use your camera. We accept photos, PDFs, and screenshots.',
                    position: 'bottom'
                },
                {
                    element: '.ai-analysis',
                    title: 'AI Analysis',
                    content: 'Our AI will automatically scan for violations, extract important dates, and identify key information.',
                    position: 'left',
                    emotionTrigger: 'document_analyzed'
                }
            ]
        },
        briefcase: {
            name: 'Briefcase Tour',
            steps: [
                {
                    element: '.folder-list',
                    title: 'Organized Folders',
                    content: 'Your documents are automatically organized into these categories. Click a folder to see what\'s inside.',
                    position: 'right'
                },
                {
                    element: '.document-list',
                    title: 'Your Documents',
                    content: 'Every document you upload appears here. Click to view, highlight, or add notes.',
                    position: 'left'
                },
                {
                    element: '.export-options',
                    title: 'Export for Court',
                    content: 'When you\'re ready, export your evidence as a professional court packet.',
                    position: 'bottom'
                }
            ]
        },
        crisis: {
            name: 'Crisis Mode Tour',
            steps: [
                {
                    element: '#singleActionCard',
                    title: 'One Thing at a Time',
                    content: 'When things feel overwhelming, we show you just ONE action. That\'s all you need to focus on.',
                    position: 'bottom'
                },
                {
                    element: '.crisis-btn',
                    title: 'Crisis Support',
                    content: 'If you need immediate help, this button connects you to crisis resources.',
                    position: 'top'
                }
            ]
        }
    },
    
    /**
     * Start a guided tour
     */
    start(tourName) {
        const tour = this.tours[tourName];
        if (!tour) {
            console.error('Tour not found:', tourName);
            return;
        }
        
        this.currentTour = tour;
        this.currentStep = 0;
        this.createOverlay();
        this.showStep(0);
        
        // Track tour start
        if (typeof EmotionEngine !== 'undefined') {
            EmotionEngine.trigger('help_accessed', { tour: tourName });
        }
    },
    
    /**
     * Create overlay element
     */
    createOverlay() {
        // Remove existing
        this.destroy();
        
        // Create overlay
        this.overlay = document.createElement('div');
        this.overlay.className = 'tour-overlay';
        this.overlay.innerHTML = `
            <div class="tour-spotlight"></div>
        `;
        
        // Create tooltip
        this.tooltip = document.createElement('div');
        this.tooltip.className = 'tour-tooltip';
        this.tooltip.innerHTML = `
            <div class="tour-tooltip-arrow"></div>
            <div class="tour-tooltip-content">
                <h4 class="tour-title"></h4>
                <p class="tour-content"></p>
                <div class="tour-progress">
                    <span class="tour-step-indicator"></span>
                </div>
                <div class="tour-actions">
                    <button class="tour-skip">Skip Tour</button>
                    <button class="tour-next">Next →</button>
                </div>
            </div>
        `;
        
        // Add styles
        this.addStyles();
        
        // Add to DOM
        document.body.appendChild(this.overlay);
        document.body.appendChild(this.tooltip);
        
        // Event listeners
        this.tooltip.querySelector('.tour-skip').addEventListener('click', () => this.end());
        this.tooltip.querySelector('.tour-next').addEventListener('click', () => this.next());
        this.overlay.addEventListener('click', () => this.next());
        
        // Keyboard navigation
        document.addEventListener('keydown', this.handleKeydown.bind(this));
    },
    
    /**
     * Add tour styles
     */
    addStyles() {
        if (document.getElementById('tour-styles')) return;
        
        const styles = document.createElement('style');
        styles.id = 'tour-styles';
        styles.textContent = `
            .tour-overlay {
                position: fixed;
                top: 0;
                left: 0;
                right: 0;
                bottom: 0;
                background: rgba(0, 0, 0, 0.7);
                z-index: 99998;
                pointer-events: auto;
            }
            
            .tour-spotlight {
                position: absolute;
                border-radius: 8px;
                box-shadow: 0 0 0 9999px rgba(0, 0, 0, 0.7);
                transition: all 0.3s ease;
                pointer-events: none;
            }
            
            .tour-tooltip {
                position: fixed;
                z-index: 99999;
                max-width: 350px;
                background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
                border: 2px solid #7c3aed;
                border-radius: 16px;
                padding: 1.5rem;
                color: white;
                box-shadow: 0 10px 40px rgba(124, 58, 237, 0.3);
                animation: tooltipAppear 0.3s ease;
            }
            
            @keyframes tooltipAppear {
                from {
                    opacity: 0;
                    transform: translateY(10px);
                }
                to {
                    opacity: 1;
                    transform: translateY(0);
                }
            }
            
            .tour-tooltip-arrow {
                position: absolute;
                width: 16px;
                height: 16px;
                background: #1a1a2e;
                border: 2px solid #7c3aed;
                border-right: none;
                border-bottom: none;
                transform: rotate(45deg);
            }
            
            .tour-tooltip[data-position="bottom"] .tour-tooltip-arrow {
                top: -9px;
                left: 50%;
                margin-left: -8px;
            }
            
            .tour-tooltip[data-position="top"] .tour-tooltip-arrow {
                bottom: -9px;
                left: 50%;
                margin-left: -8px;
                transform: rotate(225deg);
            }
            
            .tour-tooltip[data-position="left"] .tour-tooltip-arrow {
                right: -9px;
                top: 50%;
                margin-top: -8px;
                transform: rotate(135deg);
            }
            
            .tour-tooltip[data-position="right"] .tour-tooltip-arrow {
                left: -9px;
                top: 50%;
                margin-top: -8px;
                transform: rotate(-45deg);
            }
            
            .tour-title {
                font-size: 1.2rem;
                font-weight: 600;
                color: #7c3aed;
                margin: 0 0 0.75rem 0;
            }
            
            .tour-content {
                font-size: 0.95rem;
                line-height: 1.5;
                color: #ccc;
                margin: 0 0 1rem 0;
            }
            
            .tour-progress {
                display: flex;
                gap: 6px;
                justify-content: center;
                margin-bottom: 1rem;
            }
            
            .tour-progress-dot {
                width: 8px;
                height: 8px;
                border-radius: 50%;
                background: #333;
                transition: all 0.2s;
            }
            
            .tour-progress-dot.active {
                background: #7c3aed;
                transform: scale(1.2);
            }
            
            .tour-progress-dot.completed {
                background: #10b981;
            }
            
            .tour-actions {
                display: flex;
                justify-content: space-between;
                gap: 1rem;
            }
            
            .tour-skip {
                background: transparent;
                border: 1px solid #666;
                color: #888;
                padding: 0.5rem 1rem;
                border-radius: 8px;
                cursor: pointer;
                font-size: 0.9rem;
                transition: all 0.2s;
            }
            
            .tour-skip:hover {
                border-color: #999;
                color: #ccc;
            }
            
            .tour-next {
                background: #7c3aed;
                border: none;
                color: white;
                padding: 0.5rem 1.5rem;
                border-radius: 8px;
                cursor: pointer;
                font-size: 0.9rem;
                font-weight: 600;
                transition: all 0.2s;
            }
            
            .tour-next:hover {
                background: #6d28d9;
                transform: translateX(2px);
            }
            
            .tour-tooltip.center-mode {
                top: 50% !important;
                left: 50% !important;
                transform: translate(-50%, -50%);
            }
            
            .tour-tooltip.center-mode .tour-tooltip-arrow {
                display: none;
            }
        `;
        document.head.appendChild(styles);
    },
    
    /**
     * Show a specific step
     */
    showStep(index) {
        if (!this.currentTour || index >= this.currentTour.steps.length) {
            this.end();
            return;
        }
        
        const step = this.currentTour.steps[index];
        this.currentStep = index;
        
        // Update tooltip content
        this.tooltip.querySelector('.tour-title').textContent = step.title;
        this.tooltip.querySelector('.tour-content').textContent = step.content;
        
        // Update progress dots
        const progressContainer = this.tooltip.querySelector('.tour-progress');
        progressContainer.innerHTML = this.currentTour.steps.map((_, i) => `
            <div class="tour-progress-dot ${i < index ? 'completed' : ''} ${i === index ? 'active' : ''}"></div>
        `).join('');
        
        // Update button text
        const nextBtn = this.tooltip.querySelector('.tour-next');
        nextBtn.textContent = index === this.currentTour.steps.length - 1 ? 'Done ✓' : 'Next →';
        
        // Position tooltip
        if (step.element) {
            const el = document.querySelector(step.element);
            if (el) {
                this.positionTooltip(el, step.position);
                this.highlightElement(el);
                this.tooltip.classList.remove('center-mode');
            } else {
                this.centerTooltip();
            }
        } else {
            this.centerTooltip();
        }
        
        this.tooltip.setAttribute('data-position', step.position || 'bottom');
        
        // Trigger emotion if specified
        if (step.emotionTrigger && typeof EmotionEngine !== 'undefined') {
            EmotionEngine.trigger(step.emotionTrigger);
        }
    },
    
    /**
     * Position tooltip relative to element
     */
    positionTooltip(el, position) {
        const rect = el.getBoundingClientRect();
        const tooltipRect = this.tooltip.getBoundingClientRect();
        const padding = 20;
        
        let top, left;
        
        switch (position) {
            case 'bottom':
                top = rect.bottom + padding;
                left = rect.left + (rect.width / 2) - (tooltipRect.width / 2);
                break;
            case 'top':
                top = rect.top - tooltipRect.height - padding;
                left = rect.left + (rect.width / 2) - (tooltipRect.width / 2);
                break;
            case 'left':
                top = rect.top + (rect.height / 2) - (tooltipRect.height / 2);
                left = rect.left - tooltipRect.width - padding;
                break;
            case 'right':
                top = rect.top + (rect.height / 2) - (tooltipRect.height / 2);
                left = rect.right + padding;
                break;
            default:
                top = rect.bottom + padding;
                left = rect.left + (rect.width / 2) - (tooltipRect.width / 2);
        }
        
        // Keep on screen
        left = Math.max(10, Math.min(window.innerWidth - tooltipRect.width - 10, left));
        top = Math.max(10, Math.min(window.innerHeight - tooltipRect.height - 10, top));
        
        this.tooltip.style.top = top + 'px';
        this.tooltip.style.left = left + 'px';
    },
    
    /**
     * Center tooltip on screen
     */
    centerTooltip() {
        this.tooltip.classList.add('center-mode');
        this.overlay.querySelector('.tour-spotlight').style.cssText = '';
    },
    
    /**
     * Highlight an element
     */
    highlightElement(el) {
        const rect = el.getBoundingClientRect();
        const spotlight = this.overlay.querySelector('.tour-spotlight');
        const padding = 8;
        
        spotlight.style.cssText = `
            top: ${rect.top - padding}px;
            left: ${rect.left - padding}px;
            width: ${rect.width + padding * 2}px;
            height: ${rect.height + padding * 2}px;
        `;
        
        // Scroll element into view
        el.scrollIntoView({ behavior: 'smooth', block: 'center' });
    },
    
    /**
     * Go to next step
     */
    next() {
        if (this.currentStep < this.currentTour.steps.length - 1) {
            this.showStep(this.currentStep + 1);
        } else {
            this.end();
        }
    },
    
    /**
     * Go to previous step
     */
    prev() {
        if (this.currentStep > 0) {
            this.showStep(this.currentStep - 1);
        }
    },
    
    /**
     * End the tour
     */
    end() {
        this.destroy();
        
        // Mark tour as completed
        if (this.currentTour) {
            localStorage.setItem(`tour_completed_${this.currentTour.name}`, 'true');
        }
        
        // Trigger emotion
        if (typeof EmotionEngine !== 'undefined') {
            EmotionEngine.trigger('progress_made');
        }
        
        this.currentTour = null;
        this.currentStep = 0;
    },
    
    /**
     * Destroy tour elements
     */
    destroy() {
        if (this.overlay) {
            this.overlay.remove();
            this.overlay = null;
        }
        if (this.tooltip) {
            this.tooltip.remove();
            this.tooltip = null;
        }
        document.removeEventListener('keydown', this.handleKeydown);
    },
    
    /**
     * Handle keyboard navigation
     */
    handleKeydown(e) {
        if (!this.currentTour) return;
        
        switch (e.key) {
            case 'Escape':
                this.end();
                break;
            case 'ArrowRight':
            case 'Enter':
                this.next();
                break;
            case 'ArrowLeft':
                this.prev();
                break;
        }
    },
    
    /**
     * Check if tour should auto-start
     */
    shouldAutoStart(tourName) {
        return !localStorage.getItem(`tour_completed_${this.tours[tourName]?.name}`);
    }
};

// Export
if (typeof module !== 'undefined' && module.exports) {
    module.exports = GuidedTour;
}
