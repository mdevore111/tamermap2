/**
 * Route Planner Module
 * Handles route planning functionality with SweetAlert2 modal interface
 */

class RoutePlanner {
    constructor() {
        this.selectedLocations = [];
        this.previewPins = [];
        this.maxDistance = 50; // miles
        this.maxStops = 5;
        this.isInitialized = false;
    }

    /**
     * Initialize the route planner
     */
    async initialize() {
        if (this.isInitialized) return;
        
        console.log('Initializing Route Planner...');
        this.initializeUI();
        this.isInitialized = true;
    }

    /**
     * Initialize UI components
     */
    initializeUI() {
        // Set up SweetAlert2 modal configuration
        this.setupSweetAlert2Modal();
    }

    /**
     * Configure SweetAlert2 for route planning
     */
    setupSweetAlert2Modal() {
        this.swalConfig = {
            title: '<i class="fas fa-route"></i> Route Planner',
            html: this.createModalContent(),
            showConfirmButton: false,
            showCancelButton: false,
            showCloseButton: true,
            customClass: {
                popup: 'swal2-route-planner'
            },
            width: 'auto',
            didOpen: () => {
                this.initializeModalControls();
            },
            willClose: () => {
                // Clean up any event listeners if needed
            }
        };
    }

    /**
     * Create the modal content HTML
     */
    createModalContent() {
        return this.createControlsHTML();
    }

    /**
     * Create the controls HTML for the modal
     */
    createControlsHTML() {
        return `
            <div class="route-planner-container">
                <!-- Distance Control -->
                <div class="route-control-group">
                    <h4><i class="fas fa-road"></i> Distance</h4>
                    <div class="route-slider-container">
                        <label for="distance-slider">
                            Max Distance: <span id="distance-value">${this.maxDistance} miles</span>
                        </label>
                        <input type="range" id="distance-slider" class="route-slider" 
                               min="5" max="100" value="${this.maxDistance}" step="5">
                    </div>
                </div>

                <!-- Stops Control -->
                <div class="route-control-group">
                    <h4><i class="fas fa-map-marker-alt"></i> Stops</h4>
                    <div class="route-slider-container">
                        <label for="stops-slider">
                            Max Stops: <span id="stops-value">${this.maxStops}</span>
                        </label>
                        <input type="range" id="stops-slider" class="route-slider" 
                               min="2" max="10" value="${this.maxStops}" step="1">
                    </div>
                </div>

                <!-- Route Options -->
                <div class="route-control-group">
                    <h4><i class="fas fa-cog"></i> Options</h4>
                    <div class="route-checkbox-row">
                        <label class="route-checkbox">
                            <input type="checkbox" id="round-trip-checkbox">
                            <span>Round Trip</span>
                        </label>
                        <label class="route-checkbox">
                            <input type="checkbox" id="open-now-checkbox">
                            <span>Open Now</span>
                        </label>
                    </div>
                </div>

                <!-- Store Type Filters -->
                <div class="route-control-group">
                    <h4><i class="fas fa-filter"></i> Store Types</h4>
                    <div class="route-filter-toggles">
                        <div class="route-filter-toggle" data-filter="kiosk">
                            <i class="fas fa-robot"></i> Kiosk
                        </div>
                        <div class="route-filter-toggle" data-filter="retail">
                            <i class="fas fa-store"></i> Retail
                        </div>
                        <div class="route-filter-toggle" data-filter="indie">
                            <i class="fas fa-heart"></i> Indie
                        </div>
                    </div>
                </div>

                <!-- Action Buttons -->
                <div class="route-actions">
                    <button type="button" class="route-btn route-btn-secondary" id="modal-preview-route-btn">
                        <i class="fas fa-eye"></i> Preview
                    </button>
                    <button type="button" class="route-btn route-btn-primary" id="modal-open-in-maps-btn">
                        <i class="fas fa-external-link-alt"></i> Go!
                    </button>
                </div>

                <!-- Route Summary -->
                <div class="route-summary" id="route-summary">
                    <h4>Route Summary</h4>
                    <div id="summary-content">
                        <small>Configure your preferences above to see route details.</small>
                    </div>
                </div>
            </div>
        `;
    }

    /**
     * Initialize modal controls after SweetAlert2 opens
     */
    initializeModalControls() {
        // Distance slider
        const distanceSlider = document.getElementById('distance-slider');
        const distanceValue = document.getElementById('distance-value');
        
        if (distanceSlider) {
            distanceSlider.addEventListener('input', (e) => {
                this.maxDistance = parseInt(e.target.value);
                distanceValue.textContent = `${this.maxDistance} miles`;
                this.updateDistanceDisplay();
            });
        }

        // Stops slider
        const stopsSlider = document.getElementById('stops-slider');
        const stopsValue = document.getElementById('stops-value');
        
        if (stopsSlider) {
            stopsSlider.addEventListener('input', (e) => {
                this.maxStops = parseInt(e.target.value);
                stopsValue.textContent = this.maxStops;
                this.updateStopsDisplay();
            });
        }

        // Initialize checkboxes
        const roundTripCheckbox = document.getElementById('round-trip-checkbox');
        const openNowCheckbox = document.getElementById('open-now-checkbox');
        
        // Sync Open Now with legend state initially, then work independently
        const legendOpenNowCheckbox = document.getElementById('filter-open-now');
        if (openNowCheckbox && legendOpenNowCheckbox) {
            // Set initial state from legend, but then work independently
            openNowCheckbox.checked = legendOpenNowCheckbox.checked;
            
            // Route planner's Open Now only affects route planning
            openNowCheckbox.addEventListener('change', () => {
                this.updateRouteSummary();
            });
        }

        if (roundTripCheckbox) {
            roundTripCheckbox.addEventListener('change', () => {
                this.updateRouteSummary();
            });
        }

        // Initialize filter toggles based on legend state
        const filterMap = {
            'kiosk': document.getElementById('filter-kiosk'),
            'retail': document.getElementById('filter-retail'),
            'indie': document.getElementById('filter-indie')
        };
        
        const filterToggles = document.querySelectorAll('.route-filter-toggle');
        filterToggles.forEach(toggle => {
            // Get the filter type from the data attribute
            const filterType = toggle.getAttribute('data-filter');
            const legendCheckbox = filterMap[filterType];
            
            // Set initial state based on legend checkbox
            if (legendCheckbox && legendCheckbox.checked) {
                toggle.classList.add('active');
            }
            
            // Add click handler that only updates route planner state
            toggle.addEventListener('click', () => {
                toggle.classList.toggle('active');
                this.updateRouteSummary();
            });
        });

        // Action buttons
        const previewBtn = document.getElementById('modal-preview-route-btn');
        const openMapsBtn = document.getElementById('modal-open-in-maps-btn');

        if (previewBtn) {
            previewBtn.addEventListener('click', () => this.showPreviewPins());
        }

        if (openMapsBtn) {
            openMapsBtn.addEventListener('click', () => this.openInGoogleMaps());
        }

        // Update layout based on orientation
        this.updateLayoutOrientation();
        
        // Initial route summary update
        this.updateRouteSummary();
    }

    /**
     * Update layout based on screen orientation
     */
    updateLayoutOrientation() {
        // This could be enhanced to modify the modal layout based on orientation
        // For now, CSS handles the responsive design
    }

    /**
     * Update distance display (with debounced preview clear)
     */
    updateDistanceDisplay() {
        this.clearPreview(true); // Skip reopening modal to prevent bouncing
        this.updateRouteSummary();
    }

    /**
     * Update stops display (with debounced preview clear)
     */
    updateStopsDisplay() {
        this.clearPreview(true); // Skip reopening modal to prevent bouncing
        this.updateRouteSummary();
    }

    /**
     * Update route summary
     */
    updateRouteSummary() {
        if (!window.userCoords) {
            document.getElementById('summary-content').innerHTML = 
                '<small style="color: #dc3545;">Location access required for route planning.</small>';
            return;
        }

        // Get current settings
        const roundTrip = document.getElementById('round-trip-checkbox')?.checked || false;
        const openNow = document.getElementById('open-now-checkbox')?.checked || false;
        
        // Get available locations and apply filters
        const availableLocations = this.getFilteredLocations(openNow);
        const optimalLocations = this.selectOptimalLocations(availableLocations);
        
        const summaryContent = document.getElementById('summary-content');
        if (optimalLocations.length === 0) {
            summaryContent.innerHTML = '<small style="color: #dc3545;">No locations found matching your criteria.</small>';
            return;
        }

        const storeList = optimalLocations.map(loc => 
            `• ${loc.retailer || 'Unknown'} (${loc.distance?.toFixed(1) || '?'} mi)`
        ).join('<br>');

        summaryContent.innerHTML = `
            <div class="store-list">
                <strong>${optimalLocations.length} stops</strong> within ${this.maxDistance} miles<br>
                ${roundTrip ? '<strong>Round trip</strong> back to start<br>' : ''}
                ${openNow ? '<strong>Open now</strong> only<br>' : ''}
                <br>
                ${storeList}
            </div>
        `;
    }

    /**
     * Get filtered locations based on current settings
     */
    getFilteredLocations(openNow = false) {
        if (!window.userCoords) {
            return [];
        }

        // Try different data sources in order of preference
        let locations = [];
        
        // First try window.allMarkers (from MarkerManager)
        if (window.allMarkers && window.allMarkers.length > 0) {
            locations = [...window.allMarkers];
        }
        // Fallback to markerManager.markerCache if available
        else if (window.markerManager && window.markerManager.markerCache) {
            locations = Array.from(window.markerManager.markerCache.values())
                .filter(marker => marker.retailer_type); // Only retailer markers
        }
        // Try dataService if available
        else if (window.dataService && window.dataService.cache) {
            // Extract retailer data from dataService cache
            const cacheKeys = Array.from(window.dataService.cache.keys());
            const retailerKeys = cacheKeys.filter(key => key.includes('retailers') || key.includes('map-data'));
            if (retailerKeys.length > 0) {
                const cacheEntry = window.dataService.cache.get(retailerKeys[0]);
                if (cacheEntry && cacheEntry.data) {
                    locations = Array.isArray(cacheEntry.data) ? cacheEntry.data : 
                               (cacheEntry.data.retailers || []);
                }
            }
        }
        // Last fallback to any global markers array
        else if (window.markers && window.markers.length > 0) {
            locations = [...window.markers];
        }
        
        if (locations.length === 0) {
            console.warn('No marker data available for route planning');
            console.log('Debug - Available data sources:');
            console.log('- window.allMarkers:', window.allMarkers?.length || 0);
            console.log('- window.markerManager:', window.markerManager ? 'exists' : 'missing');
            console.log('- window.markerManager.markerCache:', window.markerManager?.markerCache?.size || 0);
            console.log('- window.dataService:', window.dataService ? 'exists' : 'missing');
            console.log('- window.dataService.cache:', window.dataService?.cache?.size || 0);
            console.log('- window.markers:', window.markers?.length || 0);
            return [];
        }

        // Apply distance filter
        locations = locations.filter(location => {
            const distance = this.calculateDistance(
                window.userCoords.lat, window.userCoords.lng,
                location.lat, location.lng
            );
            location.distance = distance;
            return distance <= this.maxDistance;
        });

        // Apply retailer type filters
        locations = this.applyRetailerTypeFilters(locations);

        // Apply opening hours filter
        if (openNow) {
            locations = this.filterByOpeningHours(locations);
        }

        return locations;
    }

    /**
     * Apply retailer type filters based on route planner toggles
     */
    applyRetailerTypeFilters(locations) {
        const activeFilters = [];
        
        // Check which toggles are active in the route planner
        const toggles = document.querySelectorAll('.route-filter-toggle');
        toggles.forEach(toggle => {
            if (toggle.classList.contains('active')) {
                activeFilters.push(toggle.getAttribute('data-filter'));
            }
        });

        // If no filters are active, return empty array
        if (activeFilters.length === 0) {
            return [];
        }

        return locations.filter(location => {
            const retailerType = location.retailer_type || '';
            return activeFilters.includes(retailerType);
        });
    }

    /**
     * Filter locations by opening hours
     */
    filterByOpeningHours(locations) {
        const now = new Date();
        const currentDay = now.toLocaleDateString('en-US', { weekday: 'long' }).toLowerCase();
        const currentTime = now.getHours() * 60 + now.getMinutes(); // minutes since midnight

        return locations.filter(location => {
            const hours = location.opening_hours;
            if (!hours || typeof hours !== 'object') {
                return false; // Exclude if no opening hours data
            }

            const todayHours = hours[currentDay];
            if (!todayHours) {
                return false; // Closed today
            }

            if (todayHours.toLowerCase() === 'closed') {
                return false;
            }

            // Parse opening hours (e.g., "9:00 AM - 9:00 PM")
            const match = todayHours.match(/(\d{1,2}):(\d{2})\s*(AM|PM)?\s*-\s*(\d{1,2}):(\d{2})\s*(AM|PM)?/i);
            if (!match) {
                return false; // Can't parse, exclude
            }

            let [, openHour, openMin, openPeriod, closeHour, closeMin, closePeriod] = match;
            
            // Convert to 24-hour format
            openHour = parseInt(openHour);
            closeHour = parseInt(closeHour);
            
            if (openPeriod && openPeriod.toUpperCase() === 'PM' && openHour !== 12) {
                openHour += 12;
            }
            if (openPeriod && openPeriod.toUpperCase() === 'AM' && openHour === 12) {
                openHour = 0;
            }
            
            if (closePeriod && closePeriod.toUpperCase() === 'PM' && closeHour !== 12) {
                closeHour += 12;
            }
            if (closePeriod && closePeriod.toUpperCase() === 'AM' && closeHour === 12) {
                closeHour = 0;
            }

            const openTime = openHour * 60 + parseInt(openMin);
            let closeTime = closeHour * 60 + parseInt(closeMin);

            // Handle overnight hours (e.g., 10 PM - 2 AM)
            if (closeTime < openTime) {
                closeTime += 24 * 60; // Add 24 hours
                // Check if current time is past midnight but before closing
                if (currentTime < openTime) {
                    return currentTime <= (closeTime - 24 * 60);
                }
            }

            return currentTime >= openTime && currentTime <= closeTime;
        });
    }

    /**
     * Select optimal locations for the route
     */
    selectOptimalLocations(locations) {
        if (!locations || locations.length === 0) {
            return [];
        }

        // Sort by distance and take the closest ones up to maxStops
        const sorted = locations.sort((a, b) => a.distance - b.distance);
        return sorted.slice(0, this.maxStops);
    }

    /**
     * Calculate distance between two coordinates (Haversine formula)
     */
    calculateDistance(lat1, lng1, lat2, lng2) {
        const R = 3959; // Earth's radius in miles
        const dLat = this.toRadians(lat2 - lat1);
        const dLng = this.toRadians(lng2 - lng1);
        const a = Math.sin(dLat / 2) * Math.sin(dLat / 2) +
                  Math.cos(this.toRadians(lat1)) * Math.cos(this.toRadians(lat2)) *
                  Math.sin(dLng / 2) * Math.sin(dLng / 2);
        const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
        return R * c;
    }

    /**
     * Convert degrees to radians
     */
    toRadians(degrees) {
        return degrees * (Math.PI / 180);
    }

    /**
     * Show preview pins on the map
     */
    showPreviewPins() {
        // Debug logging
        console.log('showPreviewPins called');
        console.log('userCoords:', window.userCoords);
        console.log('allMarkers:', window.allMarkers?.length || 0);
        console.log('markerManager:', window.markerManager ? 'exists' : 'missing');
        console.log('markerCache size:', window.markerManager?.markerCache?.size || 0);
        console.log('window.markers:', window.markers?.length || 0);
        
        // Check if basic requirements are met
        if (!window.userCoords) {
            Swal.fire({
                title: 'Location Required',
                text: 'Please allow location access to use route planning.',
                icon: 'warning',
                timer: 3000,
                showConfirmButton: false
            });
            return;
        }

        // Check if we have any marker data available
        const hasMarkerData = (window.allMarkers && window.allMarkers.length > 0) ||
                             (window.markerManager && window.markerManager.markerCache && window.markerManager.markerCache.size > 0) ||
                             (window.markers && window.markers.length > 0);
        
        if (!hasMarkerData) {
            Swal.fire({
                title: 'No Store Data',
                text: 'Store data is still loading. Please try again in a moment.',
                icon: 'warning',
                timer: 3000,
                showConfirmButton: false
            });
            return;
        }

        // Get current route with default settings if modal isn't open
        const openNow = document.getElementById('open-now-checkbox')?.checked || false;
        console.log('openNow filter:', openNow);
        
        const availableLocations = this.getFilteredLocations(openNow);
        console.log('availableLocations:', availableLocations.length);
        
        this.selectedLocations = this.selectOptimalLocations(availableLocations);
        console.log('selectedLocations:', this.selectedLocations.length);

        if (this.selectedLocations.length === 0) {
            Swal.fire({
                title: 'No Locations Found',
                text: 'Could not find enough locations matching your criteria. Try adjusting your filters or opening the route planner first.',
                icon: 'warning',
                timer: 4000,
                showConfirmButton: false
            });
            return;
        }

        // Close the route planner modal
        Swal.close();

        // Hide regular markers
        this.hideRegularMarkers();

        // Clear any existing preview pins
        this.clearPreviewPins();

        // Create preview pins
        this.createPreviewPins();

        // Show success toast with store count
        const Toast = Swal.mixin({
            toast: true,
            position: 'top-end',
            showConfirmButton: false,
            timer: 3000,
            timerProgressBar: true
        });

        Toast.fire({
            icon: 'success',
            title: `Showing ${this.selectedLocations.length} locations in your route`
        });

        // Update preview button state
        this.updatePreviewButtonState();
    }

    /**
     * Hide regular markers
     */
    hideRegularMarkers() {
        if (window.hideAllMarkers) {
            window.hideAllMarkers();
        }
    }

    /**
     * Show regular markers
     */
    showRegularMarkers() {
        if (window.showAllMarkers) {
            window.showAllMarkers();
        }
    }

    /**
     * Clear preview pins
     */
    clearPreviewPins() {
        this.previewPins.forEach(pin => pin.setMap(null));
        this.previewPins = [];
    }

    /**
     * Create preview pins for the route
     */
    createPreviewPins() {
        if (!window.userCoords || !this.selectedLocations.length) return;

        // Create start pin (green)
        const startPin = new google.maps.Marker({
            position: { lat: window.userCoords.lat, lng: window.userCoords.lng },
            map: window.map,
            title: 'Start Location',
            icon: {
                path: google.maps.SymbolPath.CIRCLE,
                scale: 8,
                fillColor: '#28a745',
                fillOpacity: 1,
                strokeColor: '#ffffff',
                strokeWeight: 2
            }
        });
        this.previewPins.push(startPin);

        // Create stop pins (blue) - no numbers since Google will optimize route
        this.selectedLocations.forEach((location) => {
            const stopPin = new google.maps.Marker({
                position: { lat: location.lat, lng: location.lng },
                map: window.map,
                title: `${location.retailer || 'Unknown'} (${location.distance?.toFixed(1) || '?'} mi)`,
                icon: {
                    path: google.maps.SymbolPath.CIRCLE,
                    scale: 8,
                    fillColor: '#007bff',
                    fillOpacity: 1,
                    strokeColor: '#ffffff',
                    strokeWeight: 2
                }
            });
            this.previewPins.push(stopPin);
        });

        // Create end pin (red) if round trip
        const roundTrip = document.getElementById('round-trip-checkbox')?.checked || false;
        if (roundTrip) {
            const endPin = new google.maps.Marker({
                position: { lat: window.userCoords.lat, lng: window.userCoords.lng },
                map: window.map,
                title: 'End Location (Round Trip)',
                icon: {
                    path: google.maps.SymbolPath.CIRCLE,
                    scale: 8,
                    fillColor: '#dc3545',
                    fillOpacity: 1,
                    strokeColor: '#ffffff',
                    strokeWeight: 2
                }
            });
            this.previewPins.push(endPin);
        }
    }

    /**
     * Update preview button state
     */
    updatePreviewButtonState() {
        // This could be used to update UI elements showing preview state
    }

    /**
     * Clear preview and optionally skip reopening modal
     */
    clearPreview(skipReopenModal = false) {
        // Clear preview pins
        this.previewPins.forEach(pin => pin.setMap(null));
        this.previewPins = [];
        
        // Show regular markers again
        this.showRegularMarkers();
        
        // Update button state
        this.updatePreviewButtonState();
        
        // Show the route planner modal again only if not skipped
        if (!skipReopenModal) {
            openRoutePanel();
        }
    }

    /**
     * Generate route and open in Google Maps
     */
    openInGoogleMaps() {
        const openNow = document.getElementById('open-now-checkbox')?.checked || false;
        const roundTrip = document.getElementById('round-trip-checkbox')?.checked || false;
        
        const availableLocations = this.getFilteredLocations(openNow);
        this.selectedLocations = this.selectOptimalLocations(availableLocations);

        if (this.selectedLocations.length < 2) {
            Swal.fire({
                title: 'Not Enough Locations',
                text: 'Could not find enough locations matching your criteria for routing.',
                icon: 'warning'
            });
            return;
        }

        this.generateRoute(roundTrip);
    }

    /**
     * Generate route with current selections
     */
    generateRoute(roundTrip = false) {
        if (!window.userCoords) {
            Swal.fire({
                title: 'Location Required',
                text: 'Please allow location access to plan routes.',
                icon: 'warning'
            });
            return;
        }

        // Ensure we have selected locations
        if (!this.selectedLocations || this.selectedLocations.length === 0) {
            const openNow = document.getElementById('open-now-checkbox')?.checked || false;
            const availableLocations = this.getFilteredLocations(openNow);
            this.selectedLocations = this.selectOptimalLocations(availableLocations);
        }

        if (this.selectedLocations.length < 2) {
            Swal.fire({
                title: 'Route Planning Error',
                text: 'Could not find enough locations matching your criteria.',
                icon: 'error'
            });
            return;
        }

        // Generate Google Maps URL and open
        const mapsUrl = this.generateGoogleMapsURL(this.selectedLocations, window.userCoords, roundTrip);
        window.open(mapsUrl, '_blank');
        
        // Close the modal
        Swal.close();
    }

    /**
     * Generate Google Maps URL for the route
     */
    generateGoogleMapsURL(locations, userCoords, roundTrip = false) {
        let waypoints = [];
        
        // Add start coordinates
        const startPoint = `${userCoords.lat},${userCoords.lng}`;
        waypoints.push(startPoint);
        
        // Filter out any duplicate locations by coordinates
        const uniqueLocations = locations.filter((location, index, self) =>
            index === self.findIndex(l => 
                l.lat === location.lat && l.lng === location.lng
            )
        );
        
        // Add all unique store stops with names
        uniqueLocations.forEach(location => {
            const storeName = location.retailer || 'Location';
            const coordinates = `${location.lat},${location.lng}`;
            waypoints.push(`${encodeURIComponent(storeName)}@${coordinates}`);
        });
        
        // For round trips, add the start coordinates again at the end
        if (roundTrip) {
            waypoints.push(startPoint);
        }
        
        const waypointString = waypoints.join('/');
        const url = `https://www.google.com/maps/dir/${waypointString}`;
        
        // Debug output to verify URL generation
        console.log('Generated Google Maps URL:', url);
        console.log('Route stops:', locations.map(l => `${l.retailer} (${l.lat}, ${l.lng})`));
        console.log('Round trip:', roundTrip);
        console.log('Unique locations:', uniqueLocations.length, 'of', locations.length);
        
        return url;
    }
}

// Create global instance
window.routePlanner = new RoutePlanner();

// Initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        window.routePlanner.initialize();
    });
} else {
    window.routePlanner.initialize();
}

export default RoutePlanner;