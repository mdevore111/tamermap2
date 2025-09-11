/**
 * Cache Invalidation Script
 * Run this in the browser console to invalidate all caches
 */

(function() {
    console.log('🧹 Starting comprehensive cache invalidation...');
    
    // Function to clear all localStorage items related to Tamermap
    function clearLocalStorage() {
        const keysToRemove = [];
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
        
        keysToRemove.forEach(key => {
            localStorage.removeItem(key);
            console.log(`🗑️ Removed localStorage: ${key}`);
        });
        
        return keysToRemove.length;
    }
    
    // Function to clear sessionStorage
    function clearSessionStorage() {
        const keysToRemove = [];
        for (let i = 0; i < sessionStorage.length; i++) {
            const key = sessionStorage.key(i);
            if (key && (key.startsWith('tamermap_') || key.includes('cache'))) {
                keysToRemove.push(key);
            }
        }
        
        keysToRemove.forEach(key => {
            sessionStorage.removeItem(key);
            console.log(`🗑️ Removed sessionStorage: ${key}`);
        });
        
        return keysToRemove.length;
    }
    
    // Function to clear DataService cache
    function clearDataServiceCache() {
        if (window.dataService && window.dataService.cache) {
            const size = window.dataService.cache.size;
            window.dataService.cache.clear();
            console.log(`🗑️ Cleared DataService cache (${size} entries)`);
            return size;
        }
        return 0;
    }
    
    // Function to clear marker cache
    function clearMarkerCache() {
        if (window.markerManager && window.markerManager.markerCache) {
            const size = window.markerManager.markerCache.size;
            window.markerManager.markerCache.clear();
            console.log(`🗑️ Cleared marker cache (${size} entries)`);
            return size;
        }
        return 0;
    }
    
    // Function to clear allMarkers array
    function clearAllMarkers() {
        if (window.allMarkers) {
            const count = window.allMarkers.length;
            window.allMarkers = [];
            console.log(`🗑️ Cleared allMarkers array (${count} markers)`);
            return count;
        }
        return 0;
    }
    
    // Function to clear heatmap data
    function clearHeatmapData() {
        if (window.heatmapData) {
            const count = window.heatmapData.length;
            window.heatmapData = [];
            console.log(`🗑️ Cleared heatmap data (${count} points)`);
            return count;
        }
        return 0;
    }
    
    // Function to clear route planner data
    function clearRoutePlannerData() {
        if (window.routePlanner) {
            window.routePlanner.selectedLocations = [];
            window.routePlanner.previewPins = [];
            console.log('🗑️ Cleared route planner data');
            return 1;
        }
        return 0;
    }
    
    // Execute all clearing functions
    const results = {
        localStorage: clearLocalStorage(),
        sessionStorage: clearSessionStorage(),
        dataServiceCache: clearDataServiceCache(),
        markerCache: clearMarkerCache(),
        allMarkers: clearAllMarkers(),
        heatmapData: clearHeatmapData(),
        routePlanner: clearRoutePlannerData()
    };
    
    console.log('✅ Cache invalidation completed!');
    console.log('📊 Results:', results);
    
    // Force a page reload to ensure fresh data
    console.log('🔄 Reloading page in 3 seconds...');
    setTimeout(() => {
        window.location.reload();
    }, 3000);
    
    return results;
})(); 