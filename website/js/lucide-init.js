(function initLucideRefresh() {
    function refreshLucideIcons() {
        if (
            typeof window.lucide === 'undefined'
            || typeof window.lucide.createIcons !== 'function'
        ) {
            return false;
        }

        try {
            window.lucide.createIcons();
            return true;
        } catch (error) {
            console.warn('Lucide icon refresh failed:', error);
            return false;
        }
    }

    window.refreshLucideIcons = refreshLucideIcons;
    refreshLucideIcons();
})();
