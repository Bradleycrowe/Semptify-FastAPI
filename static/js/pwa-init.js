/**
 * Semptify PWA Initialization
 * Auto-registers service worker and handles install prompts
 */

const SemptifyPWA = {
    deferredPrompt: null,
    isInstalled: false,

    async init() {
        // Check if already installed
        if (window.matchMedia('(display-mode: standalone)').matches) {
            this.isInstalled = true;
            console.log('[PWA] Running in standalone mode (installed)');
        }

        // Register service worker
        if ('serviceWorker' in navigator) {
            try {
                const registration = await navigator.serviceWorker.register('/static/sw.js', {
                    scope: '/'
                });
                console.log('[PWA] Service Worker registered:', registration.scope);

                // Check for updates
                registration.addEventListener('updatefound', () => {
                    const newWorker = registration.installing;
                    newWorker.addEventListener('statechange', () => {
                        if (newWorker.state === 'installed' && navigator.serviceWorker.controller) {
                            this.showUpdateNotification();
                        }
                    });
                });
            } catch (error) {
                console.error('[PWA] Service Worker registration failed:', error);
            }
        }

        // Listen for install prompt
        window.addEventListener('beforeinstallprompt', (e) => {
            e.preventDefault();
            this.deferredPrompt = e;
            this.showInstallButton();
            console.log('[PWA] Install prompt captured');
        });

        // Listen for app installed
        window.addEventListener('appinstalled', () => {
            this.isInstalled = true;
            this.hideInstallButton();
            console.log('[PWA] App installed successfully');
        });

        // Online/offline status
        this.setupNetworkStatus();
    },

    setupNetworkStatus() {
        const updateStatus = () => {
            const isOnline = navigator.onLine;
            document.body.classList.toggle('offline', !isOnline);
            
            // Show offline indicator if exists
            const indicator = document.getElementById('offline-indicator');
            if (indicator) {
                indicator.style.display = isOnline ? 'none' : 'flex';
            }
        };

        window.addEventListener('online', () => {
            updateStatus();
            this.showToast('✅ You\'re back online!', 'success');
        });

        window.addEventListener('offline', () => {
            updateStatus();
            this.showToast('📴 You\'re offline. Some features may be limited.', 'warning');
        });

        updateStatus();
    },

    showInstallButton() {
        // Create install button if it doesn't exist
        if (!document.getElementById('pwa-install-btn')) {
            const btn = document.createElement('button');
            btn.id = 'pwa-install-btn';
            btn.className = 'pwa-install-btn';
            btn.innerHTML = `
                <i class="fas fa-download"></i>
                <span>Install App</span>
            `;
            btn.onclick = () => this.promptInstall();
            btn.title = 'Install Semptify as an app';
            btn.setAttribute('aria-label', 'Install Semptify as an app');
            document.body.appendChild(btn);
            
            // Add styles
            this.addStyles();
        }
    },

    hideInstallButton() {
        const btn = document.getElementById('pwa-install-btn');
        if (btn) btn.remove();
    },

    async promptInstall() {
        if (!this.deferredPrompt) {
            console.log('[PWA] No install prompt available');
            return;
        }

        this.deferredPrompt.prompt();
        const { outcome } = await this.deferredPrompt.userChoice;
        console.log('[PWA] User response:', outcome);
        
        this.deferredPrompt = null;
        this.hideInstallButton();
    },

    showUpdateNotification() {
        const notification = document.createElement('div');
        notification.className = 'pwa-update-notification';
        notification.innerHTML = `
            <div class="pwa-update-content">
                <i class="fas fa-sync-alt"></i>
                <span>A new version is available!</span>
                <button onclick="location.reload()">Update Now</button>
                <button onclick="this.parentElement.parentElement.remove()">Later</button>
            </div>
        `;
        document.body.appendChild(notification);
    },

    showToast(message, type = 'info') {
        // Use existing toast system if available
        if (window.showToast) {
            window.showToast(message, type);
            return;
        }

        // Create simple toast
        const toast = document.createElement('div');
        toast.className = `pwa-toast pwa-toast-${type}`;
        toast.textContent = message;
        document.body.appendChild(toast);
        
        setTimeout(() => toast.classList.add('show'), 10);
        setTimeout(() => {
            toast.classList.remove('show');
            setTimeout(() => toast.remove(), 300);
        }, 3000);
    },

    addStyles() {
        if (document.getElementById('pwa-styles')) return;

        const style = document.createElement('style');
        style.id = 'pwa-styles';
        style.textContent = `
            .pwa-install-btn {
                position: fixed;
                bottom: 80px;
                right: 20px;
                display: flex;
                align-items: center;
                gap: 8px;
                padding: 12px 20px;
                background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
                color: white;
                border: none;
                border-radius: 8px;
                font-size: 14px;
                font-weight: 600;
                cursor: pointer;
                box-shadow: 0 4px 12px rgba(59, 130, 246, 0.4);
                z-index: 9998;
                transition: transform 0.2s, box-shadow 0.2s;
            }
            .pwa-install-btn:hover {
                transform: translateY(-2px);
                box-shadow: 0 6px 16px rgba(59, 130, 246, 0.5);
            }
            .pwa-install-btn i {
                font-size: 16px;
            }

            .pwa-update-notification {
                position: fixed;
                top: 20px;
                left: 50%;
                transform: translateX(-50%);
                z-index: 10000;
            }
            .pwa-update-content {
                display: flex;
                align-items: center;
                gap: 12px;
                padding: 12px 20px;
                background: #1e293b;
                border: 1px solid #3b82f6;
                border-radius: 8px;
                color: white;
                box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
            }
            .pwa-update-content button {
                padding: 6px 12px;
                border-radius: 4px;
                border: none;
                cursor: pointer;
                font-weight: 600;
            }
            .pwa-update-content button:first-of-type {
                background: #3b82f6;
                color: white;
            }
            .pwa-update-content button:last-of-type {
                background: transparent;
                color: #94a3b8;
            }

            .pwa-toast {
                position: fixed;
                bottom: 20px;
                left: 50%;
                transform: translateX(-50%) translateY(100px);
                padding: 12px 24px;
                background: #1e293b;
                color: white;
                border-radius: 8px;
                font-size: 14px;
                z-index: 10000;
                opacity: 0;
                transition: transform 0.3s, opacity 0.3s;
            }
            .pwa-toast.show {
                transform: translateX(-50%) translateY(0);
                opacity: 1;
            }
            .pwa-toast-success { border-left: 4px solid #10b981; }
            .pwa-toast-warning { border-left: 4px solid #f59e0b; }
            .pwa-toast-error { border-left: 4px solid #ef4444; }

            /* Offline indicator */
            #offline-indicator {
                position: fixed;
                top: 0;
                left: 0;
                right: 0;
                padding: 8px;
                background: #f59e0b;
                color: #000;
                text-align: center;
                font-size: 14px;
                font-weight: 600;
                display: none;
                align-items: center;
                justify-content: center;
                gap: 8px;
                z-index: 10001;
            }
            body.offline #offline-indicator {
                display: flex;
            }
            
            @media (max-width: 768px) {
                .pwa-install-btn {
                    bottom: 70px;
                    right: 10px;
                    padding: 10px 16px;
                    font-size: 13px;
                }
                .pwa-install-btn span {
                    display: none;
                }
            }
        `;
        document.head.appendChild(style);
    }
};

// Auto-initialize
document.addEventListener('DOMContentLoaded', () => {
    SemptifyPWA.init();
});
