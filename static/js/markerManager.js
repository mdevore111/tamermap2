// ==== static/js/markerManager.js ====
// Advanced marker management with clustering, viewport culling, and progressive loading

import { MARKER_TYPES, Z_INDICES } from './config.js';
import { createRetailerMarker, createEventMarker } from './markerFactory.js';
import { isOpenNow } from './utils.js';

/**
 * MarkerManager - Handles efficient marker rendering and clustering
 */
export class MarkerManager {
    constructor(map) {
        this.map = map;
        this.allRetailers = [];
        this.allEvents = [];
        this.visibleMarkers = new Set();
        this.markerCache = new Map();
        
        // Clustering configuration
        this.clusteringEnabled = false; // Start disabled, enable based on zoom
        this.clusterDistance = 50; // pixels
        this.minClusterSize = 2;
        
        // Viewport culling
        this.viewportPadding = 0.2; // 20% padding around viewport (reduced from 0.05)
        this.lastBounds = null;
        
        // Performance settings
        this.maxMarkersPerFrame = 50;
        this.renderingQueue = [];
        this.isRendering = false;
        this.currentFilters = {};
        
        // Bind map events
        this.bindMapEvents();
    }
    
    bindMapEvents() {
        // Debounced viewport change handler - INCREASED debounce time to prevent flickering
        let boundsChangeTimer;
        this.map.addListener('bounds_changed', () => {
            clearTimeout(boundsChangeTimer);
            boundsChangeTimer = setTimeout(() => {
                this.handleViewportChange();
            }, 500); // Increased to 500ms to reduce excessive updates and improve performance
        });
        
        // Zoom level changes - only handle clustering changes, not every zoom
        this.map.addListener('zoom_changed', () => {
            // Debounce zoom changes to prevent excessive updates
            clearTimeout(this.zoomChangeTimer);
            this.zoomChangeTimer = setTimeout(() => {
                this.handleZoomChange();
            }, 300);
        });
    }
    
    handleViewportChange() {
        const bounds = this.map.getBounds();
        if (!bounds) return;
        
        // Don't handle viewport changes until we have data loaded
        if (this.markerCache.size === 0) {
            if (window.__TM_DEBUG__) {
                console.log('Skipping viewport change - no markers loaded yet');
            }
            return;
        }
        
        // Check if viewport has changed significantly
        if (!this.hasViewportChanged(bounds)) {
            return;
        }
        
        if (window.__TM_DEBUG__) {
            console.log('Viewport changed significantly, updating visible markers');
        }
        
        // Only update if we have markers and filters haven't changed
        if (this.markerCache.size > 0 && this.currentFilters) {
            this.updateVisibleMarkers();
        }
    }
    
    handleZoomChange() {
        const zoom = this.map.getZoom();
        
        // Simple clustering logic - cluster at low zoom levels
        const shouldCluster = zoom < 12;
        
        if (shouldCluster !== this.clusteringEnabled) {
            this.clusteringEnabled = shouldCluster;
            // Only update if we have markers and filters haven't changed
            if (this.markerCache.size > 0 && this.currentFilters) {
                this.updateVisibleMarkers();
            }
        }
    }
    
    boundsEqual(bounds1, bounds2, tolerance = 0.01) { // Increased from 0.002 to 0.01 for less sensitivity
        const ne1 = bounds1.getNorthEast();
        const sw1 = bounds1.getSouthWest();
        const ne2 = bounds2.getNorthEast();
        const sw2 = bounds2.getSouthWest();
        
        // More efficient bounds comparison with reduced tolerance
        const latDiff = Math.abs(ne1.lat() - ne2.lat()) + Math.abs(sw1.lat() - sw2.lat());
        const lngDiff = Math.abs(ne1.lng() - ne2.lng()) + Math.abs(sw1.lng() - sw2.lng());
        
        return latDiff < tolerance && lngDiff < tolerance;
    }
    
    /**
     * Check if viewport has changed significantly
     */
    hasViewportChanged(bounds) {
        if (!this.lastBounds) return true;
        return !this.boundsEqual(bounds, this.lastBounds, 0.01);
    }
    
    /**
     * Load retailer data and create markers progressively
     */
    async loadRetailers(retailers, append = false) {

        
        if (append) {
            // Append to existing retailers
            this.allRetailers = [...(this.allRetailers || []), ...(retailers || [])];
        } else {
            // Replace existing retailers (initial load)
            this.allRetailers = retailers || [];
            // Clear existing markers only on initial load
            this.clearRetailerMarkers();
        }
        
        // Create markers progressively
        if (Array.isArray(retailers) && retailers.length > 0) {
            await this.createMarkersProgressively(retailers, 'retailer');
        }
        

        
        // Update visible markers with force to ensure first render works
        this.updateVisibleMarkers({ force: true });
    }
    
    /**
     * Load event data and create markers progressively
     */
    async loadEvents(events, append = false) {
        if (append) {
            // Append to existing events
            this.allEvents = [...(this.allEvents || []), ...(events || [])];
        } else {
            // Replace existing events (initial load)
            this.allEvents = events || [];
            // Clear existing event markers only on initial load
            this.clearEventMarkers();
        }
        
        // Create markers progressively
        if (Array.isArray(events) && events.length > 0) {
            await this.createMarkersProgressively(events, 'event');
        }
        
        // Update visible markers with force to ensure first render works
        this.updateVisibleMarkers({ force: true });
    }
    
    /**
     * Create markers in batches to avoid blocking the main thread
     */
    async createMarkersProgressively(data, type) {

        
        if (!Array.isArray(data) || data.length === 0) {
                    return;
        }
        
        const batchSize = this.maxMarkersPerFrame;
        let totalCreated = 0;
        
        for (let i = 0; i < data.length; i += batchSize) {
            const batch = data.slice(i, i + batchSize);
            
            // Process batch
            for (const item of batch) {
                const key = this.getMarkerKey(item, type);
                // De-duplicate by place_id-first key for retailers
                if (type === 'retailer' && this.markerCache.has(key)) {
                    // Merge retailer_type and kiosk counts onto existing marker for combined filtering
                    const existing = this.markerCache.get(key);
                    try {
                        const existingType = (existing.retailer_type || '').toLowerCase();
                        const incomingType = (item.retailer_type || '').toLowerCase();
                        const isKioskOnly = (t) => {
                            const parts = (t || '').split('+').map(p => p.trim()).filter(Boolean);
                            const hasKiosk = parts.includes('kiosk');
                            const hasStore = parts.includes('store') || parts.includes('retail') || parts.includes('card shop');
                            return hasKiosk && !hasStore;
                        };

                        // If both are kiosk-only and we collided via fallback key (no place_id),
                        // keep them separate to avoid collapsing distinct kiosk locations.
                        if (isKioskOnly(existingType) && isKioskOnly(incomingType)) {
                            const altKey = `${key}|kiosk-${item.place_id || item.id || item.full_address || Math.random()}`;
                            const altMarker = this.createMarker(item, type);
                            if (altMarker) {
                                this.markerCache.set(altKey, altMarker);
                                totalCreated++;
                            }
                            continue;
                        }
                        const parts = new Set();
                        if (existingType) existingType.split('+').forEach(t => parts.add(t.trim()));
                        if (incomingType) incomingType.split('+').forEach(t => parts.add(t.trim()));
                        const mergedType = Array.from(parts).filter(Boolean).join(' + ');
                        existing.retailer_type = mergedType;
                        if (existing.retailer_data) {
                            existing.retailer_data.retailer_type = mergedType;
                        }

                        // Aggregate kiosk count across duplicates (use max to avoid double counting)
                        const hasKiosk = (t) => t && t.split('+').some(p => p.trim() === 'kiosk');
                        const existingHasKiosk = hasKiosk(existingType);
                        const incomingHasKiosk = hasKiosk(incomingType);

                        // Initialize from existing data if undefined
                        if (typeof existing.kiosk_count === 'undefined') {
                            let base = 0;
                            if (existingHasKiosk && existing.retailer_data) {
                                const kd = existing.retailer_data;
                                base = (kd.kiosk_count ?? kd.machine_count ?? 1) || 0;
                            }
                            existing.kiosk_count = base;
                            if (existing.retailer_data) existing.retailer_data.kiosk_count = base;
                        }
                        // Add incoming kiosk machines if applicable
                        if (incomingHasKiosk) {
                            const incomingCount = (item.kiosk_count ?? item.machine_count ?? 1) || 0;
                            const nextVal = Math.max(existing.kiosk_count || 0, incomingCount);
                            existing.kiosk_count = nextVal;
                            if (existing.retailer_data) {
                                existing.retailer_data.kiosk_count = nextVal;
                            }
                        }
                    } catch (e) {
                        // Safe fallback: do nothing if merge fails
                    }
                    continue; // Skip creating a duplicate marker
                }
                const marker = this.createMarker(item, type);
                if (marker) {
                    this.markerCache.set(key, marker);
                    totalCreated++;
                }
            }
            
            // Yield control to browser between batches
            if (i + batchSize < data.length) {
                await new Promise(resolve => setTimeout(resolve, 0));
            }
        }
        

    }
    
    createMarker(data, type) {
        try {
            
            
            let marker;
            if (type === 'retailer') {
                marker = createRetailerMarker(null, data); // Don't add to map yet
                // Store additional data for filtering compatibility
                if (marker) {
                    marker.retailer_type = data.retailer_type || '';
                    marker.retailer_data = data;
                }
            } else if (type === 'event') {
                marker = createEventMarker(null, data); // Don't add to map yet
                // Store additional data for filtering compatibility
                if (marker) {
                    marker.event_title = data.event_title || '';
                    marker.event_data = data;
                }
            }
            
            
            
            return marker;
        } catch (error) {
            if (window.__TM_DEBUG__) console.warn(`Failed to create ${type} marker:`, error);
            return null;
        }
    }
    
    getMarkerKey(data, type) {
        if (type === 'retailer') {
            // Prefer place_id for stable de-duplication
            const pid = data.place_id || (data.retailer_data && data.retailer_data.place_id);
            if (pid) return `retailer_${pid}`;
            // Fallbacks to avoid duplicates when place_id missing
            const addr = (data.full_address || data.address || '').toLowerCase();
            const name = (data.retailer || data.name || '').toLowerCase();
            return `retailer_${name}|${addr}`;
        } else if (type === 'event') {
            return `event_${data.id}`;
        }
        return `${type}_${data.id}`;
    }
    
    /**
     * Update which markers are visible based on viewport and filters
     */
    updateVisibleMarkers(opts = {}) {
        const { force = false, filters: providedFilters } = opts;
        
        // Get bounds first
        const bounds = this.map.getBounds();
        if (!bounds) return;

        // Use provided filters or read from UI
        const newFilters = providedFilters || this.getCurrentFiltersFromUI();

        // Detect changes before mutating
        const filtersChanged = this.hasFiltersChanged(newFilters);
        const viewportChanged = !this.lastBounds || !this.boundsEqual(bounds, this.lastBounds, 0.002);
        const isFirstRun = !this.currentFilters;

        // Only skip if truly nothing changed
        if (!force && !filtersChanged && !viewportChanged && !isFirstRun && this.visibleMarkers.size > 0) {
            return;
        }

        // ✅ Commit filters & bounds now so downstream uses the right set
        this.currentFilters = newFilters;
        this.lastBounds = bounds;
        
        // Track which markers should be visible
        const newVisibleMarkers = new Set();
        
        let shown = 0;
        let processed = 0;
        let filteredOut = 0;
        let outOfBounds = 0;
        

        
        this.markerCache.forEach((marker, key) => {
            processed++;
            let shouldShow = true;
            if (key.startsWith('retailer_')) {
                shouldShow = this.shouldShowRetailer(marker, this.currentFilters);
                if (!shouldShow) filteredOut++;
            } else if (key.startsWith('event_')) {
                shouldShow = this.shouldShowEvent(marker, this.currentFilters);
                if (!shouldShow) filteredOut++;
            }
            
            // Show markers that pass filters AND are within the current map bounds
            if (shouldShow && bounds.contains(marker.getPosition())) {
                newVisibleMarkers.add(marker);
                // Only add to map if not already visible
                if (!this.visibleMarkers.has(marker)) {
                    marker.setMap(this.map);
                    shown++;
                }
            } else if (shouldShow) {
                outOfBounds++;

            }
        });
        
        // Remove markers that are no longer visible
        this.visibleMarkers.forEach(marker => {
            if (!newVisibleMarkers.has(marker)) {
                marker.setMap(null);
            }
        });
        
        // Update the visible markers set
        this.visibleMarkers = newVisibleMarkers;
        

    }
    
    /**
     * Check if filters have changed to prevent unnecessary updates
     */
    hasFiltersChanged(newFilters) {
        if (!this.currentFilters) return true;
        if (this.visibleMarkers.size === 0) return true;

        const keyFilters = [
            'showKiosk','showRetail','showIndie','showEvents',
            'showOpenNow','showNew','searchText','eventDays'
        ];

        for (const key of keyFilters) {
            if (this.currentFilters[key] !== newFilters[key]) {
                return true;
            }
        }
        
        return false;
    }
    
    clearVisibleMarkers() {
        this.visibleMarkers.forEach(marker => {
            marker.setMap(null);
        });
        this.visibleMarkers.clear();
    }
    
    clearRetailerMarkers() {
        // Remove retailer markers from cache
        for (const [key, marker] of this.markerCache.entries()) {
            if (key.startsWith('retailer_')) {
                marker.setMap(null);
                this.markerCache.delete(key);
            }
        }
    }
    
    clearEventMarkers() {
        // Remove event markers from cache
        for (const [key, marker] of this.markerCache.entries()) {
            if (key.startsWith('event_')) {
                marker.setMap(null);
                this.markerCache.delete(key);
            }
        }
    }
    
    /**
     * Apply filters to markers
     */
    applyFilters(filters) {
        if (filters) {
            // Use the provided filters to update visible markers
            this.updateVisibleMarkers({ force: true, filters: filters });
        } else {
            // Get filters from UI and update visible markers
            const uiFilters = this.getCurrentFiltersFromUI();
            this.updateVisibleMarkers({ force: true, filters: uiFilters });
        }
    }
    
    shouldShowRetailer(marker, filters) {
        // Check if marker is disabled
        const status = (marker.retailer_data?.status || marker.status || '').toLowerCase();
        if (status === 'disabled') {
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
        
        if (showKiosk) {
            // Check if this is a kiosk marker
            const hasKiosk = type.includes('kiosk') || 
                            (marker.kiosk_count > 0) || 
                            (marker.retailer_data?.kiosk_count > 0) ||
                            (marker.retailer_data?.machine_count > 0);
            if (hasKiosk) {
                matchesType = true;
            }
        }
        
        if (showRetail && !matchesType) {
            // Check if this is a retail store marker
            if (type.includes('store') || type.includes('retail')) {
                matchesType = true;
            }
        }
        
        if (showIndie && !matchesType) {
            // Check if this is an indie/card shop marker
            if (type.includes('card shop') || type.includes('indie')) {
                matchesType = true;
            }
        }
        
        // If no type matches, don't show the marker
        if (!matchesType) {
            return false;
        }
        

        
        // Open Now filter
        if (filters.showOpenNow) {
            if (!isOpenNow(marker.retailer_data?.opening_hours)) {
                return false;
            }
        }
        
        // New filter
        if (filters.showNew && !this.isNew(marker)) {
            return false;
        }
        
        // Search text filter
        if (filters.searchText && !this.matchesSearch(marker, filters.searchText)) {
            return false;
        }
        
        return true;
    }
    
    shouldShowEvent(marker, filters) {
        // Implement event filtering logic
        let matches = filters.showEvents !== false;
        
        if (!matches) {
            return false;
        }
        
        // Apply date range filter based on the slider value
        const eventData = marker.event_data || {};
        if (eventData.start_date) {
            const now = new Date();
            const startDate = new Date(eventData.start_date);
            const daysUntilEvent = (startDate - now) / (1000 * 60 * 60 * 24);
            const maxDays = filters.eventDays || 30;
            
            // Show only events that are in the future and within the selected day range
            matches = daysUntilEvent >= 0 && daysUntilEvent <= maxDays;
        }
        
        // Apply search filter to events
        if (matches && filters.searchText) {
            const searchText = filters.searchText.toLowerCase();
            const searchableText = [
                eventData.event_title || '',
                eventData.full_address || '',
                eventData.description || '',
                eventData.registration_url || ''
            ].join(' ').toLowerCase();
            matches = searchableText.includes(searchText);
        }
        
        return matches;
    }
    
    isInViewport(marker) {
        const bounds = this.map.getBounds();
        if (!bounds) return false;
        
        const position = marker.getPosition();
        return position && bounds.contains(position);
    }
    

    
    /**
     * Check if a retailer is new
     */
    isNew(marker) {
        // Check if there's a specific "new" field
        if (marker.retailer_data?.is_new === true) {
            return true;
        }
        
        // Check if there's a creation date and it's recent (within last 30 days)
        if (marker.retailer_data?.created_at) {
            const createdDate = new Date(marker.retailer_data.created_at);
            const now = new Date();
            const daysSinceCreation = (now - createdDate) / (1000 * 60 * 60 * 24);
            return daysSinceCreation <= 30;
        }
        
        // For now, assume all markers are not new if we don't have specific data
        return false;
    }
    
    /**
     * Check if a retailer matches search text
     */
    matchesSearch(marker, searchText) {
        if (!searchText) return true;
        
        const searchableText = [
            marker.retailer_data?.retailer || marker.retailer_type || '',
            marker.retailer_data?.full_address || marker.retailer_data?.address || '',
            marker.retailer_data?.phone || '',
            marker.retailer_data?.name || ''
        ].join(' ').toLowerCase();
        
        return searchableText.includes(searchText.toLowerCase());
    }
    

    

    
    /**
     * Get performance statistics
     */
    getStats() {
        return {
            totalMarkers: this.markerCache.size,
            visibleMarkers: this.visibleMarkers.size,
            clusteringEnabled: this.clusteringEnabled,
            totalRetailers: this.allRetailers.length,
            totalEvents: this.allEvents.length
        };
    }
    
    getCurrentFiltersFromUI() {
        const kiosk = document.getElementById('filter-kiosk');
        const retail = document.getElementById('filter-retail');
        const indie = document.getElementById('filter-indie');
        const events = document.getElementById('filter-events');
        const openNow = document.getElementById('filter-open-now');
        const isNew = document.getElementById('filter-new');
        const popular = document.getElementById('filter-popular-areas');
        const searchFilter = document.getElementById('legend_filter');
        const eventDaysSlider = document.getElementById('event-days-slider');
        
        const searchText = searchFilter ? searchFilter.value.toLowerCase() : '';
        const eventDays = eventDaysSlider ? parseInt(eventDaysSlider.value) : 30;
        
        const filters = {
            showKiosk: kiosk ? kiosk.checked : false,
            showRetail: retail ? retail.checked : false,
            showIndie: indie ? indie.checked : false,
            showEvents: events ? events.checked : false,
            showOpenNow: openNow ? openNow.checked : false,
            showNew: isNew ? isNew.checked : false,
            showPopular: popular ? popular.checked : false,
            searchText: searchText,
            eventDays: eventDays
        };
        

        
        return filters;
    }

    /**
     * Hide all visible markers
     */
    hideAllMarkers() {
        this.visibleMarkers.forEach(marker => {
            marker.setVisible(false);
        });
    }

    /**
     * Show all markers that should be visible based on current filters
     */
    showAllMarkers() {
        this.visibleMarkers.forEach(marker => {
            marker.setVisible(true);
        });
        // Re-apply current filters to ensure correct visibility
        this.applyFilters(this.currentFilters);
    }

    /**
     * Get all currently visible markers
     */
    getVisibleMarkers() {
        return Array.from(this.visibleMarkers);
    }
}
// touch
 
 