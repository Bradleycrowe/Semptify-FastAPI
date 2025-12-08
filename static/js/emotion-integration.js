/**
 * Semptify Emotion Engine Integration
 * ====================================
 * 
 * Shared JavaScript module for emotion engine integration across all pages.
 * This creates a consistent emotional experience throughout the application.
 * 
 * Usage:
 *   <script src="/static/js/emotion-integration.js"></script>
 *   <script>
 *     EmotionEngine.init();
 *     EmotionEngine.trigger('task_completed');
 *   </script>
 */

const EmotionEngine = {
    // Current emotional state
    state: null,
    
    // UI adaptation settings
    adaptation: null,
    
    // Configuration
    config: {
        apiBase: '/emotion',
        updateInterval: 30000, // 30 seconds
        enableAnimations: true,
        enableSounds: false,
        enableHaptics: false
    },
    
    // Trigger definitions for quick access
    triggers: {
        // Positive triggers
        TASK_COMPLETED: 'task_completed',
        EVIDENCE_UPLOADED: 'evidence_uploaded',
        VIOLATION_FOUND: 'violation_found',
        FORM_GENERATED: 'form_generated',
        DOCUMENT_ANALYZED: 'document_analyzed',
        DEADLINE_MET: 'deadline_met',
        PROGRESS_MADE: 'progress_made',
        HELP_ACCESSED: 'help_accessed',
        CONTACT_ADDED: 'contact_added',
        
        // Neutral/Informational triggers
        COURT_DATE_SET: 'court_date_set',
        NEW_INFORMATION: 'new_information',
        SESSION_START: 'session_start',
        SESSION_END: 'session_end',
        PAGE_NAVIGATION: 'page_navigation',
        
        // Stress triggers
        DEADLINE_APPROACHING: 'deadline_approaching',
        DEADLINE_MISSED: 'deadline_missed',
        ERROR_OCCURRED: 'error_occurred',
        COMPLEX_TASK_STARTED: 'complex_task_started',
        OVERWHELM_DETECTED: 'overwhelm_detected',
        INACTIVITY: 'inactivity',
        RAPID_NAVIGATION: 'rapid_navigation',
        CONFUSION_DETECTED: 'confusion_detected'
    },
    
    /**
     * Initialize the emotion engine
     */
    async init(options = {}) {
        this.config = { ...this.config, ...options };
        
        // Load current state
        await this.refreshState();
        
        // Start periodic updates
        this.startPeriodicUpdates();
        
        // Track session start
        this.trigger(this.triggers.SESSION_START);
        
        // Set up page visibility tracking
        this.setupVisibilityTracking();
        
        // Set up activity monitoring
        this.setupActivityMonitoring();
        
        // Apply initial UI adaptation
        this.applyUIAdaptation();
        
        console.log('🎭 Emotion Engine initialized', this.state);
        return this;
    },
    
    /**
     * Refresh emotional state from API
     */
    async refreshState() {
        try {
            const response = await fetch(`${this.config.apiBase}/state`);
            if (response.ok) {
                this.state = await response.json();
                this.adaptation = await this.getUIAdaptation();
                this.applyUIAdaptation();
            }
        } catch (error) {
            console.warn('Failed to refresh emotion state:', error);
        }
        return this.state;
    },
    
    /**
     * Get UI adaptation settings
     */
    async getUIAdaptation() {
        try {
            const response = await fetch(`${this.config.apiBase}/ui-adaptation`);
            if (response.ok) {
                return await response.json();
            }
        } catch (error) {
            console.warn('Failed to get UI adaptation:', error);
        }
        return null;
    },
    
    /**
     * Trigger an emotional event
     */
    async trigger(triggerType, metadata = {}) {
        try {
            const response = await fetch(`${this.config.apiBase}/trigger`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    trigger_type: triggerType,
                    metadata: metadata
                })
            });
            
            if (response.ok) {
                const result = await response.json();
                this.state = result.new_state;
                this.applyUIAdaptation();
                
                // Dispatch custom event for listeners
                window.dispatchEvent(new CustomEvent('emotion-change', {
                    detail: { trigger: triggerType, state: this.state }
                }));
                
                return result;
            }
        } catch (error) {
            console.warn('Failed to trigger emotion:', error);
        }
        return null;
    },
    
    /**
     * Apply UI adaptations based on emotional state
     */
    applyUIAdaptation() {
        if (!this.state) return;
        
        const body = document.body;
        const root = document.documentElement;
        
        // Calculate composite scores
        const crisisLevel = this.getCrisisLevel();
        const readiness = this.getReadinessScore();
        const overwhelm = this.state.overwhelm || 0.3;
        
        // Set CSS custom properties for emotion-aware styling
        root.style.setProperty('--emotion-intensity', this.state.intensity || 0.5);
        root.style.setProperty('--emotion-clarity', this.state.clarity || 0.6);
        root.style.setProperty('--emotion-confidence', this.state.confidence || 0.5);
        root.style.setProperty('--emotion-momentum', this.state.momentum || 0.4);
        root.style.setProperty('--emotion-overwhelm', overwhelm);
        root.style.setProperty('--emotion-trust', this.state.trust || 0.5);
        root.style.setProperty('--emotion-resolve', this.state.resolve || 0.5);
        root.style.setProperty('--crisis-level', crisisLevel);
        root.style.setProperty('--readiness-score', readiness);
        
        // Remove all mode classes
        body.classList.remove('mode-crisis', 'mode-focused', 'mode-guided', 'mode-flow', 'mode-power');
        
        // Apply mode based on state
        const mode = this.getDashboardMode();
        body.classList.add(`mode-${mode}`);
        body.setAttribute('data-emotion-mode', mode);
        
        // Adjust animation speed based on overwhelm
        if (overwhelm > 0.7) {
            root.style.setProperty('--animation-speed', '0.5');
            body.classList.add('reduced-motion');
        } else if (overwhelm > 0.5) {
            root.style.setProperty('--animation-speed', '0.75');
            body.classList.remove('reduced-motion');
        } else {
            root.style.setProperty('--animation-speed', '1');
            body.classList.remove('reduced-motion');
        }
        
        // Apply color temperature based on emotional state
        const colorTemp = this.getColorTemperature();
        root.style.setProperty('--color-temperature', colorTemp);
        
        // Update any emotion displays on the page
        this.updateEmotionDisplays();
    },
    
    /**
     * Get calculated crisis level (0-1)
     */
    getCrisisLevel() {
        if (!this.state) return 0.3;
        return Math.min(1, Math.max(0,
            (this.state.intensity * 0.3) +
            (this.state.overwhelm * 0.4) +
            ((1 - this.state.clarity) * 0.15) +
            ((1 - this.state.confidence) * 0.15)
        ));
    },
    
    /**
     * Get calculated readiness score (0-1)
     */
    getReadinessScore() {
        if (!this.state) return 0.5;
        return Math.min(1, Math.max(0,
            (this.state.clarity * 0.25) +
            (this.state.confidence * 0.25) +
            (this.state.resolve * 0.25) +
            (this.state.momentum * 0.25)
        ));
    },
    
    /**
     * Determine dashboard mode based on emotional state
     */
    getDashboardMode() {
        if (!this.state) return 'guided';
        
        const crisisLevel = this.getCrisisLevel();
        const readiness = this.getReadinessScore();
        const overwhelm = this.state.overwhelm || 0.3;
        
        if (crisisLevel > 0.7 || overwhelm > 0.8) {
            return 'crisis';
        } else if (crisisLevel > 0.5) {
            return 'focused';
        } else if (readiness < 0.4) {
            return 'guided';
        } else if (readiness > 0.7 && this.state.momentum > 0.6) {
            return 'power';
        } else if (this.state.momentum > 0.5 && this.state.clarity > 0.6) {
            return 'flow';
        }
        return 'guided';
    },
    
    /**
     * Get color temperature adjustment
     */
    getColorTemperature() {
        if (!this.state) return 'neutral';
        
        const crisisLevel = this.getCrisisLevel();
        if (crisisLevel > 0.6) return 'warm'; // Calming warm tones
        if (this.state.momentum > 0.7) return 'cool'; // Energizing cool tones
        return 'neutral';
    },
    
    /**
     * Update emotion display elements on the page
     */
    updateEmotionDisplays() {
        // Update any elements with data-emotion-display attribute
        document.querySelectorAll('[data-emotion-display]').forEach(el => {
            const displayType = el.dataset.emotionDisplay;
            
            switch (displayType) {
                case 'mode':
                    el.textContent = this.getDashboardMode().toUpperCase();
                    break;
                case 'crisis-level':
                    el.textContent = Math.round(this.getCrisisLevel() * 100) + '%';
                    break;
                case 'readiness':
                    el.textContent = Math.round(this.getReadinessScore() * 100) + '%';
                    break;
                case 'intensity':
                    el.textContent = Math.round((this.state?.intensity || 0.5) * 100) + '%';
                    break;
                case 'message':
                    el.textContent = this.getPersonalizedMessage();
                    break;
            }
        });
        
        // Update progress bars
        document.querySelectorAll('[data-emotion-progress]').forEach(el => {
            const progressType = el.dataset.emotionProgress;
            let value = 0;
            
            switch (progressType) {
                case 'crisis-level':
                    value = this.getCrisisLevel() * 100;
                    break;
                case 'readiness':
                    value = this.getReadinessScore() * 100;
                    break;
                default:
                    if (this.state && this.state[progressType] !== undefined) {
                        value = this.state[progressType] * 100;
                    }
            }
            
            el.style.width = value + '%';
            el.setAttribute('aria-valuenow', Math.round(value));
        });
    },
    
    /**
     * Get personalized message based on current state
     */
    getPersonalizedMessage() {
        if (!this.state) return "Let's get started together.";
        
        const mode = this.getDashboardMode();
        const messages = {
            crisis: [
                "One step at a time. Let's focus on what matters most right now.",
                "I'm here to help. Let's tackle this together.",
                "Take a breath. We'll get through this."
            ],
            focused: [
                "You're making progress. Keep going!",
                "Stay focused - you've got this.",
                "One task at a time leads to big results."
            ],
            guided: [
                "Let me help you find the best next step.",
                "We'll figure this out together.",
                "Every journey starts with a single step."
            ],
            flow: [
                "You're in the zone! Keep that momentum.",
                "Great progress - your hard work is paying off.",
                "You're building something powerful here."
            ],
            power: [
                "You're on fire! Let's maximize this energy.",
                "Peak performance mode activated.",
                "Nothing can stop you right now."
            ]
        };
        
        const modeMessages = messages[mode] || messages.guided;
        return modeMessages[Math.floor(Math.random() * modeMessages.length)];
    },
    
    /**
     * Start periodic state updates
     */
    startPeriodicUpdates() {
        if (this._updateInterval) {
            clearInterval(this._updateInterval);
        }
        
        this._updateInterval = setInterval(() => {
            this.refreshState();
        }, this.config.updateInterval);
    },
    
    /**
     * Set up page visibility tracking
     */
    setupVisibilityTracking() {
        document.addEventListener('visibilitychange', () => {
            if (document.hidden) {
                // User left the page
                this._lastActiveTime = Date.now();
            } else {
                // User returned
                const awayTime = Date.now() - (this._lastActiveTime || Date.now());
                if (awayTime > 300000) { // 5 minutes
                    this.trigger(this.triggers.INACTIVITY, { duration: awayTime });
                }
                this.refreshState();
            }
        });
    },
    
    /**
     * Set up activity monitoring
     */
    setupActivityMonitoring() {
        let lastActivityTime = Date.now();
        let navigationCount = 0;
        let navigationWindow = [];
        
        // Track user activity
        const updateActivity = () => {
            lastActivityTime = Date.now();
        };
        
        document.addEventListener('click', updateActivity);
        document.addEventListener('keypress', updateActivity);
        document.addEventListener('scroll', updateActivity);
        
        // Track navigation patterns
        window.addEventListener('popstate', () => {
            const now = Date.now();
            navigationWindow.push(now);
            
            // Keep only last 30 seconds of navigation
            navigationWindow = navigationWindow.filter(t => now - t < 30000);
            
            // Detect rapid navigation (possible confusion)
            if (navigationWindow.length > 5) {
                this.trigger(this.triggers.RAPID_NAVIGATION, {
                    count: navigationWindow.length
                });
            }
        });
    },
    
    /**
     * Create emotion indicator widget
     */
    createIndicatorWidget() {
        const widget = document.createElement('div');
        widget.className = 'emotion-indicator-widget';
        widget.innerHTML = `
            <div class="emotion-widget-content">
                <div class="emotion-mode" data-emotion-display="mode">--</div>
                <div class="emotion-bars">
                    <div class="bar-group">
                        <span>Crisis</span>
                        <div class="bar"><div class="fill" data-emotion-progress="crisis-level"></div></div>
                    </div>
                    <div class="bar-group">
                        <span>Ready</span>
                        <div class="bar"><div class="fill" data-emotion-progress="readiness"></div></div>
                    </div>
                </div>
                <div class="emotion-message" data-emotion-display="message"></div>
            </div>
        `;
        
        // Add styles if not already present
        if (!document.getElementById('emotion-widget-styles')) {
            const styles = document.createElement('style');
            styles.id = 'emotion-widget-styles';
            styles.textContent = `
                .emotion-indicator-widget {
                    position: fixed;
                    bottom: 20px;
                    right: 20px;
                    background: var(--bg-secondary, #1a1a2e);
                    border: 1px solid var(--border-color, #333);
                    border-radius: 12px;
                    padding: 12px 16px;
                    font-size: 0.8rem;
                    z-index: 9999;
                    box-shadow: 0 4px 20px rgba(0,0,0,0.3);
                    min-width: 180px;
                    transition: all 0.3s ease;
                }
                .emotion-indicator-widget:hover {
                    transform: translateY(-2px);
                    box-shadow: 0 6px 25px rgba(0,0,0,0.4);
                }
                .emotion-mode {
                    font-size: 0.65rem;
                    font-weight: 600;
                    text-transform: uppercase;
                    letter-spacing: 1px;
                    color: var(--primary, #7c3aed);
                    margin-bottom: 8px;
                }
                .emotion-bars {
                    display: flex;
                    flex-direction: column;
                    gap: 6px;
                    margin-bottom: 10px;
                }
                .bar-group {
                    display: flex;
                    align-items: center;
                    gap: 8px;
                }
                .bar-group span {
                    font-size: 0.65rem;
                    color: var(--text-muted, #888);
                    width: 40px;
                }
                .bar {
                    flex: 1;
                    height: 4px;
                    background: var(--bg-tertiary, #252540);
                    border-radius: 2px;
                    overflow: hidden;
                }
                .bar .fill {
                    height: 100%;
                    background: linear-gradient(90deg, #10b981, #f59e0b, #ef4444);
                    background-size: 300% 100%;
                    transition: width 0.5s ease;
                }
                .bar-group:first-child .fill {
                    background-position: right;
                }
                .bar-group:last-child .fill {
                    background: linear-gradient(90deg, #ef4444, #f59e0b, #10b981);
                    background-size: 300% 100%;
                    background-position: right;
                }
                .emotion-message {
                    font-size: 0.7rem;
                    color: var(--text-secondary, #aaa);
                    font-style: italic;
                    line-height: 1.4;
                }
                
                /* Mode-specific widget styling */
                .mode-crisis .emotion-indicator-widget {
                    border-color: #ef4444;
                    animation: pulse-border 2s infinite;
                }
                .mode-power .emotion-indicator-widget {
                    border-color: #10b981;
                }
                
                @keyframes pulse-border {
                    0%, 100% { border-color: #ef4444; }
                    50% { border-color: #f59e0b; }
                }
            `;
            document.head.appendChild(styles);
        }
        
        document.body.appendChild(widget);
        this.updateEmotionDisplays();
        return widget;
    },
    
    /**
     * Get suggested next action based on emotional state
     */
    async getSuggestedAction() {
        try {
            const response = await fetch(`${this.config.apiBase}/suggested-action`);
            if (response.ok) {
                return await response.json();
            }
        } catch (error) {
            console.warn('Failed to get suggested action:', error);
        }
        return null;
    },
    
    /**
     * Clean up
     */
    destroy() {
        if (this._updateInterval) {
            clearInterval(this._updateInterval);
        }
        this.trigger(this.triggers.SESSION_END);
    }
};

// Auto-initialize if data attribute present
document.addEventListener('DOMContentLoaded', () => {
    if (document.body.dataset.emotionEngine === 'auto') {
        EmotionEngine.init();
    }
});

// Global CSS for emotion-aware styling
const emotionGlobalStyles = document.createElement('style');
emotionGlobalStyles.id = 'emotion-global-styles';
emotionGlobalStyles.textContent = `
    /* Emotion-aware CSS custom properties */
    :root {
        --emotion-intensity: 0.5;
        --emotion-clarity: 0.6;
        --emotion-confidence: 0.5;
        --emotion-momentum: 0.4;
        --emotion-overwhelm: 0.3;
        --emotion-trust: 0.5;
        --emotion-resolve: 0.5;
        --crisis-level: 0.3;
        --readiness-score: 0.5;
        --animation-speed: 1;
        --color-temperature: neutral;
    }
    
    /* Reduced motion for high overwhelm */
    .reduced-motion * {
        animation-duration: 0.01s !important;
        transition-duration: 0.1s !important;
    }
    
    /* Mode-specific base styles */
    .mode-crisis {
        --primary: #ef4444;
        --primary-hover: #dc2626;
    }
    
    .mode-focused {
        --primary: #f59e0b;
        --primary-hover: #d97706;
    }
    
    .mode-guided {
        --primary: #7c3aed;
        --primary-hover: #6d28d9;
    }
    
    .mode-flow {
        --primary: #10b981;
        --primary-hover: #059669;
    }
    
    .mode-power {
        --primary: #06b6d4;
        --primary-hover: #0891b2;
    }
    
    /* Hide complexity in crisis mode */
    .mode-crisis .hide-in-crisis {
        display: none !important;
    }
    
    /* Simplify in high overwhelm */
    .mode-crisis .simplify-in-crisis {
        opacity: 0.5;
        pointer-events: none;
    }
`;

if (!document.getElementById('emotion-global-styles')) {
    document.head.appendChild(emotionGlobalStyles);
}

// Export for module usage
if (typeof module !== 'undefined' && module.exports) {
    module.exports = EmotionEngine;
}
