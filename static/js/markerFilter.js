/**
 * Marker Filtering Logic
 * Handles all marker filtering and visibility logic
 */

/**
 * Check if a retailer marker should be shown based on filters
 */
export function shouldShowRetailer(marker, filters) {
    // Respect explicit disables only; default to visible when undefined
    const enabledRaw = marker.retailer_data?.enabled;
    const explicitlyDisabled = (enabledRaw === false || enabledRaw === 0 || enabledRaw === '0');
    if (explicitlyDisabled) {
        if (window.__TM_DEBUG__) {
            console.log('[markerFilter] Hiding explicitly disabled marker', marker.retailer_data?.retailer || marker.retailer_name);
        }
        return false;
    }
    
    // Get checkbox states - these should be boolean values
    const showKiosk = filters.showKiosk === true;
    const showRetail = filters.showRetail === true;
    const showIndie = filters.showIndie === true;
    
    // If NO checkboxes are checked, show NO markers
    if (!showKiosk && !showRetail && !showIndie) {
        return false;
    }
    
    // Get marker type for filtering
    const type = (marker.retailer_type || '').toLowerCase();
    
    // Check if marker matches any of the checked categories
    let matchesType = false;
    
    if (showKiosk && type.includes('kiosk')) {
        matchesType = true;
    }
    if (showRetail && (type.includes('store') || type.includes('retail'))) {
        matchesType = true;
    }
    if (showIndie && type.includes('card shop')) {
        matchesType = true;
    }
    
    if (!matchesType) {
        return false;
    }
    
    // Check "Open Now" filter
    if (filters.showOpenNow === true) {
        const isOpen = marker.retailer_data?.is_open_now;
        if (isOpen !== true) {
            return false;
        }
    }
    
    // Check "New Locations" filter
    if (filters.showNew === true) {
        const isNew = marker.retailer_data?.is_new_location;
        if (isNew !== true) {
            return false;
        }
    }
    
    // Check search filter
    if (filters.searchText && filters.searchText.trim()) {
        const searchText = filters.searchText.toLowerCase();
        const retailer = (marker.retailer_data?.retailer || '').toLowerCase();
        const address = (marker.retailer_data?.full_address || '').toLowerCase();
        const phone = (marker.retailer_data?.phone || '').toLowerCase();
        
        if (!retailer.includes(searchText) && 
            !address.includes(searchText) && 
            !phone.includes(searchText)) {
            return false;
        }
    }
    
    return true;
}

/**
 * Check if an event marker should be shown based on filters
 */
export function shouldShowEvent(marker, filters) {
    if (filters.showEvents !== true) {
        return false;
    }
    
    // Check event days filter
    if (filters.eventDays && filters.eventDays > 0) {
        const eventDate = new Date(marker.eventData?.event_date);
        const now = new Date();
        const daysDiff = Math.ceil((eventDate - now) / (1000 * 60 * 60 * 24));
        
        if (daysDiff < 0 || daysDiff > filters.eventDays) {
            return false;
        }
    }
    
    // Check search filter
    if (filters.searchText && filters.searchText.trim()) {
        const searchText = filters.searchText.toLowerCase();
        const eventName = (marker.eventData?.event_name || '').toLowerCase();
        const location = (marker.eventData?.location || '').toLowerCase();
        
        if (!eventName.includes(searchText) && !location.includes(searchText)) {
            return false;
        }
    }
    
    return true;
}

/**
 * Check if marker is within viewport bounds
 */
export function isMarkerInBounds(marker, bounds, padding = 0.2) {
    if (!bounds || !marker.position) return false;
    
    const position = marker.position;
    const ne = bounds.getNorthEast();
    const sw = bounds.getSouthWest();
    
    // Add padding to bounds
    const latRange = ne.lat() - sw.lat();
    const lngRange = ne.lng() - sw.lng();
    
    const paddedNE = {
        lat: ne.lat() + (latRange * padding),
        lng: ne.lng() + (lngRange * padding)
    };
    const paddedSW = {
        lat: sw.lat() - (latRange * padding),
        lng: sw.lng() - (lngRange * padding)
    };
    
    return position.lat() >= paddedSW.lat && 
           position.lat() <= paddedNE.lat &&
           position.lng() >= paddedSW.lng && 
           position.lng() <= paddedNE.lng;
}

/**
 * Check if filters have changed
 */
export function hasFiltersChanged(newFilters, currentFilters) {
    if (!currentFilters) return true;
    
    const keys = ['showKiosk', 'showRetail', 'showIndie', 'showEvents', 'showOpenNow', 'showNew', 'showPopular', 'searchText', 'eventDays'];
    
    for (const key of keys) {
        if (newFilters[key] !== currentFilters[key]) {
            return true;
        }
    }
    
    return false;
}
