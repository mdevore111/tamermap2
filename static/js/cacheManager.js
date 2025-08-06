/**
 * Cache Manager Utility
 * Provides comprehensive cache clearing and debugging for the Tamermap application
 */

class CacheManager {
    constructor() {
        this.cacheTypes = {
            localStorage: 'localStorage',
            sessionStorage: 'sessionStorage',
            memoryCache: 'memoryCache',
            dataServiceCache: 'dataServiceCache',
            markerCache: 'markerCache',
            allMarkers: 'allMarkers',
            heatmapData: 'heatmapData'
        };
    }

    /**
     * Clear all types of caches
     */
    clearAllCaches() {
        console.log('🧹 Clearing all caches...');
        
        const results = {
            localStorage: this.clearLocalStorage(),
            sessionStorage: this.clearSessionStorage(),
            memoryCache: this.clearMemoryCache(),
            dataServiceCache: this.clearDataServiceCache(),
            markerCache: this.clearMarkerCache(),
            allMarkers: this.clearAllMarkers(),
            heatmapData: this.clearHeatmapData()
        };

        console.log('✅ Cache clearing results:', results);
        return results;
    }

    /**
     * Clear localStorage cache
     */
    clearLocalStorage() {
        try {
            const keysToRemove = [];
            
            // Get all localStorage keys
            for (let i = 0; i < localStorage.length; i++) {
                const key = localStorage.key(i);
                if (key && (key.startsWith('tamermap_') || 
                           key.startsWith('checkbox_') || 
                           key.includes('cache') ||
                           key.includes('legend') ||
                           key.includes('event_days'))) {
                    keysToRemove.push(key);
                }
            }

            // Remove the keys
            keysToRemove.forEach(key => {
                localStorage.removeItem(key);
                console.log(`🗑️ Removed localStorage key: ${key}`);
            });

            return {
                success: true,
                removed: keysToRemove.length,
                keys: keysToRemove
            };
        } catch (error) {
            console.error('❌ Error clearing localStorage:', error);
            return {
                success: false,
                error: error.message
            };
        }
    }

    /**
     * Clear sessionStorage cache
     */
    clearSessionStorage() {
        try {
            const keysToRemove = [];
            
            // Get all sessionStorage keys
            for (let i = 0; i < sessionStorage.length; i++) {
                const key = sessionStorage.key(i);
                if (key && (key.startsWith('tamermap_') || 
                           key.includes('cache'))) {
                    keysToRemove.push(key);
                }
            }

            // Remove the keys
            keysToRemove.forEach(key => {
                sessionStorage.removeItem(key);
                console.log(`🗑️ Removed sessionStorage key: ${key}`);
            });

            return {
                success: true,
                removed: keysToRemove.length,
                keys: keysToRemove
            };
        } catch (error) {
            console.error('❌ Error clearing sessionStorage:', error);
            return {
                success: false,
                error: error.message
            };
        }
    }

    /**
     * Clear memory cache (DataService)
     */
    clearMemoryCache() {
        try {
            if (window.dataService && typeof window.dataService.clearCache === 'function') {
                window.dataService.clearCache();
                console.log('🗑️ Cleared DataService memory cache');
                return {
                    success: true,
                    message: 'DataService cache cleared'
                };
            } else {
                console.log('⚠️ DataService not available or clearCache method not found');
                return {
                    success: false,
                    message: 'DataService not available'
                };
            }
        } catch (error) {
            console.error('❌ Error clearing memory cache:', error);
            return {
                success: false,
                error: error.message
            };
        }
    }

    /**
     * Clear DataService cache specifically
     */
    clearDataServiceCache() {
        try {
            if (window.dataService && window.dataService.cache) {
                const cacheSize = window.dataService.cache.size;
                window.dataService.cache.clear();
                console.log(`🗑️ Cleared DataService cache (${cacheSize} entries)`);
                return {
                    success: true,
                    clearedEntries: cacheSize
                };
            } else {
                console.log('⚠️ DataService cache not available');
                return {
                    success: false,
                    message: 'DataService cache not available'
                };
            }
        } catch (error) {
            console.error('❌ Error clearing DataService cache:', error);
            return {
                success: false,
                error: error.message
            };
        }
    }

    /**
     * Clear marker cache
     */
    clearMarkerCache() {
        try {
            if (window.markerManager && window.markerManager.markerCache) {
                const cacheSize = window.markerManager.markerCache.size;
                window.markerManager.markerCache.clear();
                console.log(`🗑️ Cleared marker cache (${cacheSize} entries)`);
                return {
                    success: true,
                    clearedEntries: cacheSize
                };
            } else {
                console.log('⚠️ Marker cache not available');
                return {
                    success: false,
                    message: 'Marker cache not available'
                };
            }
        } catch (error) {
            console.error('❌ Error clearing marker cache:', error);
            return {
                success: false,
                error: error.message
            };
        }
    }

    /**
     * Clear allMarkers array
     */
    clearAllMarkers() {
        try {
            if (window.allMarkers) {
                const markerCount = window.allMarkers.length;
                window.allMarkers = [];
                console.log(`🗑️ Cleared allMarkers array (${markerCount} markers)`);
                return {
                    success: true,
                    clearedMarkers: markerCount
                };
            } else {
                console.log('⚠️ allMarkers not available');
                return {
                    success: false,
                    message: 'allMarkers not available'
                };
            }
        } catch (error) {
            console.error('❌ Error clearing allMarkers:', error);
            return {
                success: false,
                error: error.message
            };
        }
    }

    /**
     * Clear heatmap data
     */
    clearHeatmapData() {
        try {
            if (window.heatmapData) {
                const dataCount = window.heatmapData.length;
                window.heatmapData = [];
                console.log(`🗑️ Cleared heatmap data (${dataCount} points)`);
                return {
                    success: true,
                    clearedPoints: dataCount
                };
            } else {
                console.log('⚠️ Heatmap data not available');
                return {
                    success: false,
                    message: 'Heatmap data not available'
                };
            }
        } catch (error) {
            console.error('❌ Error clearing heatmap data:', error);
            return {
                success: false,
                error: error.message
            };
        }
    }

    /**
     * Get cache statistics
     */
    getCacheStats() {
        const stats = {
            localStorage: {
                totalKeys: localStorage.length,
                tamermapKeys: 0,
                checkboxKeys: 0,
                cacheKeys: 0
            },
            sessionStorage: {
                totalKeys: sessionStorage.length,
                tamermapKeys: 0,
                cacheKeys: 0
            },
            dataService: {
                available: false,
                cacheSize: 0,
                cacheKeys: []
            },
            markers: {
                allMarkersCount: 0,
                markerCacheSize: 0,
                heatmapDataCount: 0
            }
        };

        // Count localStorage keys
        for (let i = 0; i < localStorage.length; i++) {
            const key = localStorage.key(i);
            if (key) {
                if (key.startsWith('tamermap_')) stats.localStorage.tamermapKeys++;
                if (key.startsWith('checkbox_')) stats.localStorage.checkboxKeys++;
                if (key.includes('cache')) stats.localStorage.cacheKeys++;
            }
        }

        // Count sessionStorage keys
        for (let i = 0; i < sessionStorage.length; i++) {
            const key = sessionStorage.key(i);
            if (key) {
                if (key.startsWith('tamermap_')) stats.sessionStorage.tamermapKeys++;
                if (key.includes('cache')) stats.sessionStorage.cacheKeys++;
            }
        }

        // DataService stats
        if (window.dataService && window.dataService.cache) {
            stats.dataService.available = true;
            stats.dataService.cacheSize = window.dataService.cache.size;
            stats.dataService.cacheKeys = Array.from(window.dataService.cache.keys());
        }

        // Marker stats
        if (window.allMarkers) {
            stats.markers.allMarkersCount = window.allMarkers.length;
        }
        if (window.markerManager && window.markerManager.markerCache) {
            stats.markers.markerCacheSize = window.markerManager.markerCache.size;
        }
        if (window.heatmapData) {
            stats.markers.heatmapDataCount = window.heatmapData.length;
        }

        return stats;
    }

    /**
     * Force refresh all data
     */
    async forceRefreshAllData() {
        console.log('🔄 Force refreshing all data...');
        
        // Clear all caches first
        this.clearAllCaches();
        
        // Force refresh DataService data
        if (window.dataService && typeof window.dataService.loadMapData === 'function') {
            try {
                console.log('🔄 Refreshing map data...');
                await window.dataService.loadMapData(null, { forceRefresh: true });
                console.log('✅ Map data refreshed');
            } catch (error) {
                console.error('❌ Error refreshing map data:', error);
            }
        }

        // Force refresh route planner data
        if (window.routePlanner && typeof window.routePlanner.updateRouteSummary === 'function') {
            try {
                console.log('🔄 Refreshing route planner data...');
                window.routePlanner.updateRouteSummary();
                console.log('✅ Route planner data refreshed');
            } catch (error) {
                console.error('❌ Error refreshing route planner data:', error);
            }
        }

        console.log('✅ Force refresh completed');
    }

    /**
     * Add cache clearing button to the page
     */
    addCacheClearingButton() {
        // Remove existing button if it exists
        const existingButton = document.getElementById('cache-clear-button');
        if (existingButton) {
            existingButton.remove();
        }

        // Create new button
        const button = document.createElement('button');
        button.id = 'cache-clear-button';
        button.innerHTML = '🧹 Clear Cache';
        button.style.cssText = `
            position: fixed;
            top: 10px;
            right: 10px;
            z-index: 10000;
            background: #ff6b35;
            color: white;
            border: none;
            border-radius: 5px;
            padding: 8px 12px;
            font-size: 12px;
            cursor: pointer;
            box-shadow: 0 2px 4px rgba(0,0,0,0.2);
        `;

        button.addEventListener('click', () => {
            this.clearAllCaches();
            button.innerHTML = '✅ Cleared!';
            setTimeout(() => {
                button.innerHTML = '🧹 Clear Cache';
            }, 2000);
        });

        document.body.appendChild(button);
        console.log('🔧 Cache clearing button added to page');
    }
}

// Create global instance
window.cacheManager = new CacheManager();

// Export for module usage
if (typeof module !== 'undefined' && module.exports) {
    module.exports = CacheManager;
} 