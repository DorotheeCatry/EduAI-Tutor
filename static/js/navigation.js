// Navigation Management System for EduAI Tutor

class NavigationManager {
    constructor() {
        this.openTabs = new Map();
        this.currentPath = window.location.pathname;
        this.tabsContainer = document.getElementById('tabs-container');
    }

    init() {
        this.setupTabClickHandlers();
        this.setupSidebarClickHandlers();
        this.initializeCurrentTab();
    }

    setupTabClickHandlers() {
        if (!this.tabsContainer) return;

        this.tabsContainer.addEventListener('click', (e) => {
            const tabItem = e.target.closest('.tab-nav-item');
            if (!tabItem) return;

            // Ignore clicks on close button
            if (e.target.closest('.tab-close-btn')) return;

            const url = tabItem.dataset.url;
            if (url && url !== this.currentPath) {
                this.navigateToTab(url);
            }
        });
    }

    setupSidebarClickHandlers() {
        const sidebarItems = document.querySelectorAll('.sidebar-nav-item');
        sidebarItems.forEach(item => {
            item.addEventListener('click', (e) => {
                e.preventDefault();
                const url = item.getAttribute('href');
                if (url && url !== '#' && url !== this.currentPath) {
                    this.navigateToTab(url);
                }
            });
        });
    }

    initializeCurrentTab() {
        // Mark current tab as active
        const currentTab = this.tabsContainer?.querySelector(`[data-url="${this.currentPath}"]`);
        if (currentTab) {
            this.setActiveTab(currentTab);
        }
    }

    navigateToTab(url) {
        // Add loading state
        this.showLoadingState();
        
        // Navigate to the URL
        window.location.href = url;
    }

    setActiveTab(tabElement) {
        // Remove active class from all tabs
        const allTabs = this.tabsContainer?.querySelectorAll('.tab-nav-item');
        allTabs?.forEach(tab => {
            tab.classList.remove('active');
            tab.classList.add('bg-gray-800', 'text-gray-300');
            tab.classList.remove('bg-gray-900', 'text-white');
        });

        // Add active class to current tab
        if (tabElement) {
            tabElement.classList.add('active');
            tabElement.classList.remove('bg-gray-800', 'text-gray-300');
            tabElement.classList.add('bg-gray-900', 'text-white');
        }
    }

    closeTab(url) {
        const tabElement = this.tabsContainer?.querySelector(`[data-url="${url}"]`);
        if (!tabElement) return;

        const isActive = tabElement.classList.contains('active');
        
        // Remove the tab
        tabElement.remove();

        // If we closed the active tab, navigate to the first remaining tab
        if (isActive) {
            const remainingTabs = this.tabsContainer?.querySelectorAll('.tab-nav-item');
            if (remainingTabs && remainingTabs.length > 0) {
                const firstTab = remainingTabs[0];
                const firstTabUrl = firstTab.dataset.url;
                if (firstTabUrl) {
                    this.navigateToTab(firstTabUrl);
                }
            } else {
                // No tabs left, go to home
                this.navigateToTab('/courses/generator/');
            }
        }
    }

    showLoadingState() {
        // Add loading indicator to the page
        const loadingIndicator = document.createElement('div');
        loadingIndicator.id = 'page-loading';
        loadingIndicator.className = 'fixed top-0 left-0 w-full h-1 bg-primary-green z-50';
        loadingIndicator.innerHTML = '<div class="h-full bg-primary-green animate-pulse"></div>';
        
        document.body.appendChild(loadingIndicator);

        // Remove after a short delay (will be removed when page loads)
        setTimeout(() => {
            const loader = document.getElementById('page-loading');
            if (loader) loader.remove();
        }, 3000);
    }

    showNotification(message, type = 'info') {
        const notification = document.createElement('div');
        notification.className = `notification ${type} translate-x-full`;
        notification.textContent = message;
        
        document.body.appendChild(notification);
        
        // Animation d'entrée
        setTimeout(() => {
            notification.classList.remove('translate-x-full');
        }, 100);
        
        // Suppression automatique
        setTimeout(() => {
            notification.classList.add('translate-x-full');
            setTimeout(() => {
                notification.remove();
            }, 300);
        }, 3000);
    }

    addTab(title, url, isActive = false) {
        if (this.tabsContainer?.querySelector(`[data-url="${url}"]`)) {
            return; // Tab already exists
        }

        const tab = document.createElement('div');
        tab.className = `tab-nav-item ${isActive ? 'active' : ''}`;
        tab.dataset.url = url;
        
        tab.innerHTML = `
            <span class="tab-title">${title}</span>
            <button class="tab-close-btn" onclick="Navigation.closeTab('${url}')">
                <i data-lucide="x" class="w-3 h-3"></i>
            </button>
        `;
        
        this.tabsContainer?.appendChild(tab);
        
        // Re-initialize Lucide icons
        if (typeof lucide !== 'undefined') {
            lucide.createIcons();
        }
        
        if (isActive) {
            this.setActiveTab(tab);
        }
    }

    removeTab(url) {
        const tab = this.tabsContainer?.querySelector(`[data-url="${url}"]`);
        if (tab) {
            tab.remove();
        }
    }

    getPageTitle(path) {
        const titleMap = {
            '/courses/generator/': 'Générateur de Cours',
            '/chat/search/': 'Recherche IA',
            '/quiz/lobby/': 'Quiz & QCM',
            '/tracker/dashboard/': 'Performances',
            '/revision/flashcards/': 'Révision'
        };
        
        return titleMap[path] || 'EduAI Tutor';
    }
}

// Global Navigation instance
const Navigation = new NavigationManager();

// Export for global use
window.Navigation = Navigation;

// Utility functions
window.showNotification = function(message, type = 'info') {
    Navigation.showNotification(message, type);
};

window.closeTab = function(event, url) {
    if (event) {
        event.stopPropagation();
    }
    Navigation.closeTab(url);
};

// Keyboard shortcuts
document.addEventListener('keydown', function(e) {
    // Ctrl+W to close current tab
    if (e.ctrlKey && e.key === 'w') {
        e.preventDefault();
        Navigation.closeTab(Navigation.currentPath);
    }
    
    // Ctrl+T to open new tab (navigate to courses)
    if (e.ctrlKey && e.key === 't') {
        e.preventDefault();
        Navigation.navigateToTab('/courses/generator/');
    }
    
    // Ctrl+1-5 for quick navigation
    if (e.ctrlKey && e.key >= '1' && e.key <= '5') {
        e.preventDefault();
        const urls = [
            '/courses/generator/',
            '/chat/search/',
            '/quiz/lobby/',
            '/tracker/dashboard/',
            '/revision/flashcards/'
        ];
        const index = parseInt(e.key) - 1;
        if (urls[index]) {
            Navigation.navigateToTab(urls[index]);
        }
    }
});

// Handle page visibility changes
document.addEventListener('visibilitychange', function() {
    if (!document.hidden) {
        // Page became visible, refresh time
        const timeElement = document.getElementById('current-time');
        if (timeElement) {
            const now = new Date();
            timeElement.textContent = now.toLocaleTimeString();
        }
    }
});