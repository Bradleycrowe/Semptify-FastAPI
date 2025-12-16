/**
 * ============================================================================
 * SEMPTIFY MAIN APPLICATION
 * ============================================================================
 * 
 * Main application initialization and orchestration.
 * This file coordinates all modules and handles app lifecycle.
 */

// Import modules (these are also available globally)
// import { api, authApi, systemApi } from './modules/api.js';
// import { wsManager, connectEvents } from './modules/websocket.js';
// import { toast, modal, loading } from './modules/ui.js';
// import { appStore, actions, selectors } from './modules/state.js';

class SemptifyApp {
  constructor() {
    this.initialized = false;
    this.version = '5.0.0';
    this.config = {
      apiBaseUrl: window.location.origin,
      wsEnabled: true,
      debugMode: window.location.hostname === 'localhost'
    };
  }

  /**
   * Initialize the application
   */
  async init() {
    if (this.initialized) {
      console.warn('App already initialized');
      return;
    }

    console.log(`🚀 Semptify v${this.version} initializing...`);

    try {
      // Initialize core systems
      await this.initTheme();
      await this.initAuth();
      await this.initWebSocket();
      await this.initHealthCheck();
      this.initGlobalHandlers();

      this.initialized = true;
      console.log('✅ Semptify initialized successfully');

      // Emit ready event
      window.dispatchEvent(new CustomEvent('semptify:ready', { detail: { app: this } }));

    } catch (error) {
      console.error('❌ Semptify initialization failed:', error);
      this.handleInitError(error);
    }
  }

  /**
   * Initialize theme from preferences
   */
  async initTheme() {
    const storedTheme = localStorage.getItem('semptify_theme');
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    const theme = storedTheme || (prefersDark ? 'dark' : 'light');
    
    document.documentElement.setAttribute('data-theme', theme);
    
    if (typeof actions !== 'undefined') {
      actions.setTheme(theme);
    }

    // Listen for system theme changes
    window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', (e) => {
      if (!localStorage.getItem('semptify_theme')) {
        const newTheme = e.matches ? 'dark' : 'light';
        document.documentElement.setAttribute('data-theme', newTheme);
        if (typeof actions !== 'undefined') {
          actions.setTheme(newTheme);
        }
      }
    });
  }

  /**
   * Initialize authentication state
   */
  async initAuth() {
    // Check for existing token
    const token = typeof api !== 'undefined' ? api.getToken() : null;
    
    if (token) {
      try {
        // Verify token and get user info
        if (typeof authApi !== 'undefined') {
          const response = await authApi.getCurrentUser();
          if (response.data) {
            if (typeof actions !== 'undefined') {
              actions.setUser(response.data);
            }
          }
        }
      } catch (error) {
        // Token invalid, clear it
        console.log('Auth token invalid, clearing');
        if (typeof api !== 'undefined') {
          api.clearToken();
        }
        if (typeof actions !== 'undefined') {
          actions.logout();
        }
      }
    }
  }

  /**
   * Initialize WebSocket connections
   */
  async initWebSocket() {
    if (!this.config.wsEnabled) return;

    if (typeof connectEvents === 'function') {
      const events = connectEvents();

      events.on('open', () => {
        if (typeof actions !== 'undefined') {
          actions.setWebSocketConnected(true);
        }
        if (this.config.debugMode) {
          console.log('🔌 WebSocket connected');
        }
      });

      events.on('close', () => {
        if (typeof actions !== 'undefined') {
          actions.setWebSocketConnected(false);
        }
        if (this.config.debugMode) {
          console.log('🔌 WebSocket disconnected');
        }
      });

      events.on('reconnecting', ({ attempt, maxAttempts }) => {
        console.log(`🔄 Reconnecting... (${attempt}/${maxAttempts})`);
      });

      // Handle various message types
      events.on('notification', (data) => {
        if (typeof toast !== 'undefined') {
          toast.info(data.message, { title: data.title });
        }
        if (typeof actions !== 'undefined') {
          actions.addNotification(data);
        }
      });

      events.on('document:processed', (data) => {
        if (typeof toast !== 'undefined') {
          toast.success(`Document "${data.filename}" processed`);
        }
      });

      events.on('sync:complete', (data) => {
        if (typeof actions !== 'undefined') {
          actions.setSyncStatus({
            connected: true,
            lastSync: new Date().toISOString(),
            provider: data.provider
          });
        }
      });
    }
  }

  /**
   * Perform health check
   */
  async initHealthCheck() {
    try {
      if (typeof systemApi !== 'undefined') {
        const response = await systemApi.health();
        if (this.config.debugMode) {
          console.log('🏥 Health check:', response.data);
        }
      }
    } catch (error) {
      console.warn('Health check failed:', error.message);
      if (typeof toast !== 'undefined') {
        toast.warning('Unable to connect to server. Some features may be unavailable.');
      }
    }
  }

  /**
   * Initialize global event handlers
   */
  initGlobalHandlers() {
    // Online/offline detection
    window.addEventListener('online', () => {
      if (typeof actions !== 'undefined') {
        actions.setOnlineStatus(true);
      }
      if (typeof toast !== 'undefined') {
        toast.success('Connection restored');
      }
    });

    window.addEventListener('offline', () => {
      if (typeof actions !== 'undefined') {
        actions.setOnlineStatus(false);
      }
      if (typeof toast !== 'undefined') {
        toast.warning('You are offline. Changes will sync when connection is restored.');
      }
    });

    // Global error handler
    window.addEventListener('error', (event) => {
      console.error('Global error:', event.error);
      if (this.config.debugMode) {
        if (typeof toast !== 'undefined') {
          toast.error(`Error: ${event.message}`);
        }
      }
    });

    // Unhandled promise rejection handler
    window.addEventListener('unhandledrejection', (event) => {
      console.error('Unhandled promise rejection:', event.reason);
      if (this.config.debugMode) {
        if (typeof toast !== 'undefined') {
          toast.error(`Promise error: ${event.reason?.message || 'Unknown error'}`);
        }
      }
    });

    // Handle keyboard shortcuts
    document.addEventListener('keydown', (e) => {
      // Cmd/Ctrl + K for global search
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        const searchInput = document.getElementById('global-search');
        const searchExpanded = document.getElementById('search-expanded');
        const searchToggle = document.getElementById('search-toggle');
        
        if (searchExpanded && searchToggle) {
          searchExpanded.hidden = false;
          searchToggle.hidden = true;
          searchInput?.focus();
        }
      }

      // Escape to close modals
      if (e.key === 'Escape') {
        if (typeof modal !== 'undefined' && modal.activeModals?.length > 0) {
          // Modal manager handles this internally
        }
      }
    });

    // Handle visibility change
    document.addEventListener('visibilitychange', () => {
      if (document.visibilityState === 'visible') {
        // Refresh data when tab becomes visible
        this.onTabVisible();
      }
    });
  }

  /**
   * Called when tab becomes visible
   */
  onTabVisible() {
    // Refresh connection status
    if (typeof systemApi !== 'undefined') {
      systemApi.health().catch(() => {});
    }
  }

  /**
   * Handle initialization errors
   */
  handleInitError(error) {
    // Show error UI
    const main = document.querySelector('.main-content');
    if (main) {
      main.innerHTML = `
        <div class="empty-state">
          <div class="empty-state-icon">
            <i class="fas fa-exclamation-triangle"></i>
          </div>
          <h2 class="empty-state-title">Unable to load application</h2>
          <p class="empty-state-description">
            ${error.message || 'An unexpected error occurred. Please try refreshing the page.'}
          </p>
          <div class="empty-state-actions">
            <button class="btn btn-primary" onclick="window.location.reload()">
              <i class="fas fa-redo"></i>
              Refresh Page
            </button>
          </div>
        </div>
      `;
    }
  }

  /**
   * Navigate to a page
   */
  navigate(path) {
    window.location.href = path;
  }

  /**
   * Get app version
   */
  getVersion() {
    return this.version;
  }

  /**
   * Check if app is initialized
   */
  isReady() {
    return this.initialized;
  }
}

// ============================================================================
// UTILITY FUNCTIONS
// ============================================================================

/**
 * Format a date for display
 */
function formatDate(date, options = {}) {
  const d = date instanceof Date ? date : new Date(date);
  const defaultOptions = {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    ...options
  };
  return d.toLocaleDateString('en-US', defaultOptions);
}

/**
 * Format a date and time for display
 */
function formatDateTime(date, options = {}) {
  const d = date instanceof Date ? date : new Date(date);
  const defaultOptions = {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
    ...options
  };
  return d.toLocaleDateString('en-US', defaultOptions);
}

/**
 * Format a relative time (e.g., "2 hours ago")
 */
function formatRelativeTime(date) {
  const d = date instanceof Date ? date : new Date(date);
  const now = new Date();
  const diffMs = now - d;
  const diffSecs = Math.floor(diffMs / 1000);
  const diffMins = Math.floor(diffSecs / 60);
  const diffHours = Math.floor(diffMins / 60);
  const diffDays = Math.floor(diffHours / 24);

  if (diffSecs < 60) return 'just now';
  if (diffMins < 60) return `${diffMins} minute${diffMins === 1 ? '' : 's'} ago`;
  if (diffHours < 24) return `${diffHours} hour${diffHours === 1 ? '' : 's'} ago`;
  if (diffDays < 7) return `${diffDays} day${diffDays === 1 ? '' : 's'} ago`;
  
  return formatDate(d);
}

/**
 * Format file size for display
 */
function formatFileSize(bytes) {
  if (bytes === 0) return '0 Bytes';
  const k = 1024;
  const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

/**
 * Debounce a function
 */
function debounce(fn, delay = 300) {
  let timeoutId;
  return function (...args) {
    clearTimeout(timeoutId);
    timeoutId = setTimeout(() => fn.apply(this, args), delay);
  };
}

/**
 * Throttle a function
 */
function throttle(fn, limit = 300) {
  let inThrottle;
  return function (...args) {
    if (!inThrottle) {
      fn.apply(this, args);
      inThrottle = true;
      setTimeout(() => inThrottle = false, limit);
    }
  };
}

/**
 * Copy text to clipboard
 */
async function copyToClipboard(text) {
  try {
    await navigator.clipboard.writeText(text);
    if (typeof toast !== 'undefined') {
      toast.success('Copied to clipboard');
    }
    return true;
  } catch (error) {
    console.error('Failed to copy:', error);
    if (typeof toast !== 'undefined') {
      toast.error('Failed to copy to clipboard');
    }
    return false;
  }
}

/**
 * Generate a unique ID
 */
function generateId(prefix = 'id') {
  return `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 11)}`;
}

// ============================================================================
// SINGLETON INSTANCE
// ============================================================================

const app = new SemptifyApp();

// ============================================================================
// AUTO INITIALIZATION
// ============================================================================

// Initialize when DOM is ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => app.init());
} else {
  app.init();
}

// ============================================================================
// EXPORTS
// ============================================================================

// Global exports
window.app = app;
window.SemptifyApp = SemptifyApp;
window.formatDate = formatDate;
window.formatDateTime = formatDateTime;
window.formatRelativeTime = formatRelativeTime;
window.formatFileSize = formatFileSize;
window.debounce = debounce;
window.throttle = throttle;
window.copyToClipboard = copyToClipboard;
window.generateId = generateId;

// ES Module exports
export {
  SemptifyApp,
  app,
  formatDate,
  formatDateTime,
  formatRelativeTime,
  formatFileSize,
  debounce,
  throttle,
  copyToClipboard,
  generateId
};
