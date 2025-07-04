// JavaScript global pour EduAI Tutor

document.addEventListener('DOMContentLoaded', function() {
    // Initialiser les icônes Lucide
    if (typeof lucide !== 'undefined') {
        lucide.createIcons();
    }
    
    // Gestion du temps en temps réel
    updateTime();
    setInterval(updateTime, 1000);
    
    // Initialiser la gestion des tabs
    initTabManagement();
    
    // Initialiser les tooltips
    initTooltips();
});

// Fonction pour mettre à jour l'heure
function updateTime() {
    const timeElement = document.getElementById('current-time');
    if (timeElement) {
        const now = new Date();
        timeElement.textContent = now.toLocaleTimeString();
    }
}

// Gestion des tabs
function initTabManagement() {
    const tabsContainer = document.getElementById('tabs-container');
    if (!tabsContainer) return;
    
    const openTabs = new Map();

    window.addTab = function(title, url, isActive = false) {
        if (openTabs.has(url)) {
            if (isActive) {
                setActiveTab(url);
            }
            return;
        }
        
        const tab = document.createElement('div');
        tab.className = `tab-item ${isActive ? 'active' : ''}`;
        tab.dataset.url = url;
        
        tab.innerHTML = `
            <span class="mr-2 truncate max-w-32">${title}</span>
            <button class="opacity-0 group-hover:opacity-100 transition-opacity duration-150 p-1 hover:bg-gray-600 rounded" onclick="closeTab('${url}', event)">
                <i data-lucide="x" class="w-3 h-3"></i>
            </button>
        `;
        
        tab.onclick = (e) => {
            if (!e.target.closest('button')) {
                window.location.href = url;
            }
        };
        
        tabsContainer.appendChild(tab);
        openTabs.set(url, { element: tab, title, isActive });
        
        // Re-initialiser les icônes Lucide
        if (typeof lucide !== 'undefined') {
            lucide.createIcons();
        }
        
        if (isActive) {
            setActiveTab(url);
        }
    };

    window.setActiveTab = function(url) {
        openTabs.forEach((tab, tabUrl) => {
            if (tabUrl === url) {
                tab.element.classList.add('active');
                tab.element.classList.remove('bg-gray-800', 'text-gray-300');
                tab.element.classList.add('bg-gray-900', 'text-white');
                tab.isActive = true;
            } else {
                tab.element.classList.remove('active');
                tab.element.classList.remove('bg-gray-900', 'text-white');
                tab.element.classList.add('bg-gray-800', 'text-gray-300');
                tab.isActive = false;
            }
        });
    };

    window.closeTab = function(url, event) {
        event.stopPropagation();
        const tab = openTabs.get(url);
        if (tab) {
            tab.element.remove();
            openTabs.delete(url);
            
            // Si on ferme l'onglet actif et qu'il y en a d'autres, activer le premier
            if (tab.isActive && openTabs.size > 0) {
                const firstTab = openTabs.entries().next().value;
                window.location.href = firstTab[0];
            }
        }
    };

    // Ajouter l'onglet de la page actuelle
    const currentPath = window.location.pathname;
    let pageTitle = 'EduAI Tutor';
    
    if (currentPath.includes('courses')) pageTitle = 'Générateur de Cours';
    else if (currentPath.includes('chat')) pageTitle = 'Recherche IA';
    else if (currentPath.includes('quiz')) pageTitle = 'Quiz & QCM';
    else if (currentPath.includes('tracker')) pageTitle = 'Performances';
    else if (currentPath.includes('revision')) pageTitle = 'Révision';
    
    addTab(pageTitle, currentPath, true);
}

// Initialiser les tooltips
function initTooltips() {
    const tooltipElements = document.querySelectorAll('[title]');
    tooltipElements.forEach(element => {
        element.addEventListener('mouseenter', showTooltip);
        element.addEventListener('mouseleave', hideTooltip);
    });
}

function showTooltip(event) {
    const element = event.target;
    const title = element.getAttribute('title');
    if (!title) return;
    
    // Créer le tooltip
    const tooltip = document.createElement('div');
    tooltip.className = 'absolute z-50 px-2 py-1 text-xs text-white bg-gray-800 rounded shadow-lg pointer-events-none';
    tooltip.textContent = title;
    tooltip.id = 'tooltip';
    
    document.body.appendChild(tooltip);
    
    // Positionner le tooltip
    const rect = element.getBoundingClientRect();
    tooltip.style.left = rect.left + (rect.width / 2) - (tooltip.offsetWidth / 2) + 'px';
    tooltip.style.top = rect.bottom + 5 + 'px';
    
    // Supprimer temporairement l'attribut title pour éviter le tooltip natif
    element.setAttribute('data-original-title', title);
    element.removeAttribute('title');
}

function hideTooltip(event) {
    const element = event.target;
    const tooltip = document.getElementById('tooltip');
    if (tooltip) {
        tooltip.remove();
    }
    
    // Restaurer l'attribut title
    const originalTitle = element.getAttribute('data-original-title');
    if (originalTitle) {
        element.setAttribute('title', originalTitle);
        element.removeAttribute('data-original-title');
    }
}

// Utilitaires pour les notifications
window.showNotification = function(message, type = 'info') {
    const notification = document.createElement('div');
    notification.className = `fixed top-4 right-4 z-50 px-4 py-3 rounded-lg shadow-lg transition-all duration-300 transform translate-x-full`;
    
    const colors = {
        success: 'bg-green-500 text-white',
        error: 'bg-red-500 text-white',
        warning: 'bg-yellow-500 text-black',
        info: 'bg-blue-500 text-white'
    };
    
    notification.className += ` ${colors[type] || colors.info}`;
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
};

// Utilitaires pour les modales
window.showModal = function(content, title = '') {
    const modal = document.createElement('div');
    modal.className = 'fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50';
    modal.innerHTML = `
        <div class="bg-gray-800 rounded-lg p-6 max-w-md w-full mx-4 border border-gray-700">
            ${title ? `<h3 class="text-xl font-bold text-white mb-4">${title}</h3>` : ''}
            <div class="text-gray-300 mb-6">${content}</div>
            <div class="flex justify-end space-x-4">
                <button onclick="closeModal()" class="px-4 py-2 bg-gray-600 text-white rounded hover:bg-gray-500 transition-colors">
                    Fermer
                </button>
            </div>
        </div>
    `;
    
    document.body.appendChild(modal);
    modal.id = 'current-modal';
};

window.closeModal = function() {
    const modal = document.getElementById('current-modal');
    if (modal) {
        modal.remove();
    }
};