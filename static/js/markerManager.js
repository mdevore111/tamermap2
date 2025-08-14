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
        this.viewportPadding = 0.1; // 10% padding around viewport
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
        // Debounced viewport change handler
        let boundsChangeTimer;
        this.map.addListener('bounds_changed', () => {
            clearTimeout(boundsChangeTimer);
            boundsChangeTimer = setTimeout(() => {
                this.handleViewportChange();
            }, 150);
        });
        
        // Zoom level changes
        this.map.addListener('zoom_changed', () => {
            this.handleZoomChange();
        });
    }
    
    handleViewportChange() {
        const bounds = this.map.getBounds();
        if (!bounds) return;
        
        // Check if viewport has changed significantly
        if (this.lastBounds && this.boundsEqual(bounds, this.lastBounds)) {
            return;
        }
        
        this.lastBounds = bounds;
        this.updateVisibleMarkers();
    }
    
    handleZoomChange() {
        const zoom = this.map.getZoom();
        
        // Simple clustering logic - cluster at low zoom levels
        const shouldCluster = zoom < 12;
        
        if (shouldCluster !== this.clusteringEnabled) {
            this.clusteringEnabled = shouldCluster;
            this.updateVisibleMarkers();
        }
    }
    
    boundsEqual(bounds1, bounds2, tolerance = 0.001) {
        const ne1 = bounds1.getNorthEast();
        const sw1 = bounds1.getSouthWest();
        const ne2 = bounds2.getNorthEast();
        const sw2 = bounds2.getSouthWest();
        
        return Math.abs(ne1.lat() - ne2.lat()) < tolerance &&
               Math.abs(ne1.lng() - ne2.lng()) < tolerance &&
               Math.abs(sw1.lat() - sw2.lat()) < tolerance &&
               Math.abs(sw1.lng() - sw2.lng()) < tolerance;
    }
    
    /**
     * Load retailer data and create markers progressively
     */
    async loadRetailers(retailers) {
        this.allRetailers = retailers || [];
        
        // Clear existing markers
        this.clearRetailerMarkers();
        
        // Create markers progressively
        if (Array.isArray(retailers) && retailers.length > 0) {
            await this.createMarkersProgressively(retailers, 'retailer');
        }
        
        // Update visible markers
        this.updateVisibleMarkers();
    }
    
    /**
     * Load event data and create markers progressively
     */
    async loadEvents(events) {
        this.allEvents = events || [];
        
        // Clear existing event markers
        this.clearEventMarkers();
        
        // Create markers progressively
        if (Array.isArray(events) && events.length > 0) {
            await this.createMarkersProgressively(events, 'event');
        }
        
        // Update visible markers
        this.updateVisibleMarkers();
    }
    
    /**
     * Create markers in batches to avoid blocking the main thread
     */
    async createMarkersProgressively(data, type) {
        if (!Array.isArray(data) || data.length === 0) {
            return;
        }
        
        const batchSize = this.maxMarkersPerFrame;
        
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
    updateVisibleMarkers() {
        this.currentFilters = this.getCurrentFiltersFromUI();
        const bounds = this.map.getBounds();
        if (!bounds) return;
        
        // Expand bounds for viewport padding
        const ne = bounds.getNorthEast();
        const sw = bounds.getSouthWest();
        const latRange = ne.lat() - sw.lat();
        const lngRange = ne.lng() - sw.lng();
        
        const expandedBounds = new google.maps.LatLngBounds(
            new google.maps.LatLng(
                sw.lat() - latRange * this.viewportPadding,
                sw.lng() - lngRange * this.viewportPadding
            ),
            new google.maps.LatLng(
                ne.lat() + latRange * this.viewportPadding,
                ne.lng() + lngRange * this.viewportPadding
            )
        );
        
        this.clearVisibleMarkers();
        
        let shown = 0;
        let processed = 0;
        this.markerCache.forEach((marker, key) => {
            processed++;
            let shouldShow = true;
            if (key.startsWith('retailer_')) {
                shouldShow = this.shouldShowRetailer(marker, this.currentFilters);
            } else if (key.startsWith('event_')) {
                shouldShow = this.shouldShowEvent(marker, this.currentFilters);
            }
            
            if (shouldShow && expandedBounds.contains(marker.getPosition())) {
                // Muted style for disabled (should not reach due to earlier check), or normal
                this.visibleMarkers.add(marker);
                marker.setMap(this.map);
                shown++;
            }
        });
        
        // console.log('updateVisibleMarkers: filters=', this.currentFilters, 'markers shown=', shown);
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
        this.currentFilters = filters;
        this.updateVisibleMarkers();
        // Optionally, update UI here if needed
    }
    
    shouldShowRetailer(marker, filters) {
        // Implement retailer filtering logic
        const type = (marker.retailer_type || '').toLowerCase();
        const status = (marker.retailer_data?.status || marker.status || '').toLowerCase();
        if (status === 'disabled') {
            return false;
        }
        const showKiosk = filters.showKiosk !== false;
        const showRetail = filters.showRetail !== false;
        const showIndie = filters.showIndie !== false;
        // Derive kiosk presence from counts if type metadata is missing
        const derivedKioskCount = Number(
            (marker.kiosk_count ?? marker.retailer_data?.kiosk_current_count ?? marker.retailer_data?.kiosk_count ?? marker.retailer_data?.machine_count ?? marker.machine_count ?? 0)
        ) || 0;
        const hasDerivedKiosk = derivedKioskCount > 0;
        

        
        // If there's a search term, bypass type filtering and show any matching results
        if (filters.searchText) {
            const searchText = filters.searchText.toLowerCase();
            const retailerData = marker.retailer_data || {};
            const searchableText = [
                retailerData.retailer || '',
                retailerData.full_address || '',
                retailerData.phone_number || '',
                retailerData.retailer_type || '',
                type
            ].join(' ').toLowerCase();
            
            let matchesSearch = searchableText.includes(searchText);
            
            // Apply additional filters only if search matches
            if (matchesSearch && filters.showOpenNow) {
                matchesSearch = isOpenNow(marker.retailer_data?.opening_hours);
            }
            if (matchesSearch && filters.showNew) {
                matchesSearch = marker.retailer_data && marker.retailer_data.is_new === true;
            }
            
            return matchesSearch;
        }
        
        // No search term - apply type filtering (robust kiosk inference)
        let matchesType = ((type.includes('kiosk') || hasDerivedKiosk) && showKiosk) ||
                          ((type.includes('store') || type.includes('retail')) && showRetail) ||
                          (type.includes('card shop') && showIndie);

        // Suppress kiosk-only pins that have zero machines when only Kiosks filter is active.
        // Do NOT suppress combo locations (store + kiosk) since they should remain visible.
        if (matchesType && showKiosk && !showRetail) {
            const isKioskOnly = type.includes('kiosk') && !(type.includes('store') || type.includes('retail'));
            if (isKioskOnly && derivedKioskCount <= 0) {
                return false;
            }
        }
        
        if (matchesType && filters.showOpenNow) {
            matchesType = isOpenNow(marker.retailer_data?.opening_hours);
        }
        if (matchesType && filters.showNew) {
            // Assume marker.retailer_data.is_new is a boolean or similar
            matchesType = marker.retailer_data && marker.retailer_data.is_new === true;
        }
        

        
        return matchesType;
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
        
        // console.log('getCurrentFiltersFromUI:', {
        //     kiosk,
        //     retail,
        //     indie,
        //     events,
        //     openNow,
        //     isNew,
        //     popular,
        //     eventDays
        // });
        return {
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
 