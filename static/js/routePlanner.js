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

                <!-- Popularity Filters -->
                <div class="route-control-group">
                    <h4><i class="fas fa-chart-line"></i> Popularity</h4>
                    <div class="route-checkbox-row">
                        <label class="route-checkbox">
                            <input type="checkbox" id="least-popular-checkbox">
                            <span>Least Popular</span>
                        </label>
                        <label class="route-checkbox">
                            <input type="checkbox" id="most-popular-checkbox">
                            <span>Most Popular</span>
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
            let distanceTimeout;
            distanceSlider.addEventListener('input', (e) => {
                this.maxDistance = parseInt(e.target.value);
                distanceValue.textContent = `${this.maxDistance} miles`;
                
                // Debounce the update to prevent rapid recalculations
                clearTimeout(distanceTimeout);
                distanceTimeout = setTimeout(() => {
                    this.updateDistanceDisplay();
                }, 100);
            });
        }

        // Stops slider
        const stopsSlider = document.getElementById('stops-slider');
        const stopsValue = document.getElementById('stops-value');
        
        if (stopsSlider) {
            let stopsTimeout;
            stopsSlider.addEventListener('input', (e) => {
                this.maxStops = parseInt(e.target.value);
                stopsValue.textContent = this.maxStops;
                
                // Debounce the update to prevent rapid recalculations
                clearTimeout(stopsTimeout);
                stopsTimeout = setTimeout(() => {
                    this.updateStopsDisplay();
                }, 100);
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

        // Initialize popularity checkboxes
        const leastPopularCheckbox = document.getElementById('least-popular-checkbox');
        const mostPopularCheckbox = document.getElementById('most-popular-checkbox');
        
        if (leastPopularCheckbox) {
            leastPopularCheckbox.addEventListener('change', () => {
                // Ensure only one popularity filter is active at a time
                if (leastPopularCheckbox.checked && mostPopularCheckbox) {
                    mostPopularCheckbox.checked = false;
                }
                this.updateRouteSummary();
            });
        }
        
        if (mostPopularCheckbox) {
            mostPopularCheckbox.addEventListener('change', () => {
                // Ensure only one popularity filter is active at a time
                if (mostPopularCheckbox.checked && leastPopularCheckbox) {
                    leastPopularCheckbox.checked = false;
                }
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
        let hasActiveFilter = false;
        
        filterToggles.forEach(toggle => {
            // Get the filter type from the data attribute
            const filterType = toggle.getAttribute('data-filter');
            const legendCheckbox = filterMap[filterType];
            
            // Set initial state based on legend checkbox
            if (legendCheckbox && legendCheckbox.checked) {
                toggle.classList.add('active');
                hasActiveFilter = true;
            }
            
            // Add click handler that only updates route planner state
            toggle.addEventListener('click', () => {
                toggle.classList.toggle('active');
                this.updateRouteSummary();
            });
        });
        
        // If no filters are active, activate the first one (kiosk) by default
        if (!hasActiveFilter && filterToggles.length > 0) {
            console.log('No filters active, activating kiosk filter by default');
            filterToggles[0].classList.add('active');
        }

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
        console.log('=== UPDATE ROUTE SUMMARY DEBUG ===');
        const summaryContent = document.getElementById('summary-content');
        
        if (!summaryContent) {
            console.warn('Summary content element not found');
            return;
        }

        if (!window.userCoords) {
            console.log('ERROR: No user coordinates available for route summary');
            summaryContent.innerHTML = 
                '<small style="color: #dc3545;">Location access required for route planning.</small>';
            return;
        }

        // Get current settings
        const roundTrip = document.getElementById('round-trip-checkbox')?.checked || false;
        const openNow = document.getElementById('open-now-checkbox')?.checked || false;
        const leastPopular = document.getElementById('least-popular-checkbox')?.checked || false;
        const mostPopular = document.getElementById('most-popular-checkbox')?.checked || false;
        
        console.log('1. Settings - roundTrip:', roundTrip, 'openNow:', openNow);
        
        // Debug: Log available data sources
        console.log('2. Available data sources:');
        console.log('- userCoords:', window.userCoords);
        console.log('- allMarkers:', window.allMarkers?.length || 0);
        console.log('- markerManager:', window.markerManager ? 'exists' : 'missing');
        console.log('- markerCache size:', window.markerManager?.markerCache?.size || 0);
        console.log('- dataService:', window.dataService ? 'exists' : 'missing');
        console.log('- dataService cache size:', window.dataService?.cache?.size || 0);
        
        // Additional debugging for markerManager
        if (window.markerManager) {
            console.log('- markerManager.markerCache keys:', Array.from(window.markerManager.markerCache?.keys() || []));
            console.log('- markerManager.markerCache values sample:', Array.from(window.markerManager.markerCache?.values() || []).slice(0, 3));
        }
        
        // Additional debugging for dataService
        if (window.dataService && window.dataService.cache) {
            console.log('- dataService.cache entries:');
            window.dataService.cache.forEach((value, key) => {
                console.log(`  - ${key}:`, value);
            });
        }
        
        // Get available locations and apply filters
        console.log('3. Getting filtered locations...');
        const availableLocations = this.getFilteredLocations(openNow, leastPopular, mostPopular);
        console.log('4. availableLocations after filtering:', availableLocations.length);
        console.log('5. availableLocations sample:', availableLocations.slice(0, 3));
        
        const optimalLocations = this.selectOptimalLocations(availableLocations);
        console.log('6. optimalLocations selected:', optimalLocations.length);
        console.log('7. optimalLocations details:', optimalLocations);
        
        if (optimalLocations.length === 0) {
            console.log('ERROR: No optimal locations found');
            // Provide more helpful feedback
            let message = 'No locations found matching your criteria.';
            if (availableLocations.length === 0) {
                message += ' Try adjusting your distance or store type filters.';
            } else {
                message += ' Try increasing the number of stops.';
            }
            summaryContent.innerHTML = `<small style="color: #dc3545;">${message}</small>`;
            return;
        }

        const storeList = optimalLocations.map(loc => 
            `• ${loc.retailer || 'Unknown'} (${loc.distance?.toFixed(1) || '?'} mi)`
        ).join('<br>');

        // Build filter description
        let filterDescription = '';
        if (roundTrip) filterDescription += '<strong>Round trip</strong> back to start<br>';
        if (openNow) filterDescription += '<strong>Open now</strong> only<br>';
        if (leastPopular) filterDescription += '<strong>Least popular</strong> locations<br>';
        if (mostPopular) filterDescription += '<strong>Most popular</strong> locations<br>';
        
        summaryContent.innerHTML = `
            <div class="store-list">
                <strong>${optimalLocations.length} stops</strong> within ${this.maxDistance} miles<br>
                ${filterDescription}
                <br>
                ${storeList}
            </div>
        `;
    }

    /**
     * Get filtered locations based on current settings
     */
    getFilteredLocations(openNow = false, leastPopular = false, mostPopular = false) {
        console.log('=== GET FILTERED LOCATIONS DEBUG ===');
        console.log('1. openNow parameter:', openNow);
        console.log('2. leastPopular parameter:', leastPopular);
        console.log('3. mostPopular parameter:', mostPopular);
        console.log('4. userCoords available:', !!window.userCoords);
        console.log('5. userCoords value:', window.userCoords);
        
        if (!window.userCoords) {
            console.log('ERROR: No user coordinates available');
            return [];
        }

        // Try different data sources in order of preference
        let locations = [];
        let dataSource = 'none';
        
        console.log('6. Checking data sources...');
        
        // First try window.allMarkers (from MarkerManager)
        if (window.allMarkers && window.allMarkers.length > 0) {
            // Convert Google Maps Marker objects to location data objects
            locations = window.allMarkers.map(marker => {
                const position = marker.getPosition();
                return {
                    lat: position.lat(),
                    lng: position.lng(),
                    retailer: marker.getTitle() || 'Unknown',
                    retailer_type: marker.retailer_type || 'unknown',
                    opening_hours: marker.opening_hours || null,
                    address: marker.address || null,
                    phone: marker.phone || null
                };
            });
            dataSource = 'allMarkers';
            console.log(`5. SUCCESS: Using data source: allMarkers (${locations.length} locations)`);
            console.log('6. Sample location:', locations[0]);
            console.log('7. First 3 locations:', locations.slice(0, 3));
        }
        // Fallback to markerManager.markerCache if available
        else if (window.markerManager && window.markerManager.markerCache && window.markerManager.markerCache.size > 0) {
            const markerCache = Array.from(window.markerManager.markerCache.values());
            locations = markerCache.filter(marker => marker.retailer_type); // Only retailer markers
            dataSource = 'markerCache';
            console.log(`5. SUCCESS: Using data source: markerCache (${locations.length} retailer locations from ${markerCache.length} total)`);
            console.log('6. Sample location:', locations[0]);
            console.log('7. First 3 locations:', locations.slice(0, 3));
        }
        // Try dataService if available
        else if (window.dataService && window.dataService.cache && window.dataService.cache.size > 0) {
            // Extract retailer data from dataService cache
            const cacheKeys = Array.from(window.dataService.cache.keys());
            console.log('5. DataService cache keys:', cacheKeys);
            
            const retailerKeys = cacheKeys.filter(key => key.includes('retailers') || key.includes('map-data'));
            console.log('6. Retailer keys found:', retailerKeys);
            
            if (retailerKeys.length > 0) {
                const cacheEntry = window.dataService.cache.get(retailerKeys[0]);
                console.log('7. Cache entry:', cacheEntry);
                
                if (cacheEntry && cacheEntry.data) {
                    locations = Array.isArray(cacheEntry.data) ? cacheEntry.data : 
                               (cacheEntry.data.retailers || []);
                    dataSource = 'dataService';
                    console.log(`8. SUCCESS: Using data source: dataService (${locations.length} locations from key: ${retailerKeys[0]})`);
                    console.log('9. Sample location:', locations[0]);
                    console.log('10. First 3 locations:', locations.slice(0, 3));
                }
            }
        }
        // Last fallback to any global markers array
        else if (window.markers && window.markers.length > 0) {
            locations = [...window.markers];
            dataSource = 'markers';
            console.log(`5. SUCCESS: Using data source: markers (${locations.length} locations)`);
            console.log('6. Sample location:', locations[0]);
            console.log('7. First 3 locations:', locations.slice(0, 3));
        }
        
        if (locations.length === 0) {
            console.log('ERROR: No marker data available for route planning');
            console.log('Debug - Available data sources:');
            console.log('- window.allMarkers:', window.allMarkers?.length || 0);
            console.log('- window.markerManager:', window.markerManager ? 'exists' : 'missing');
            console.log('- window.markerManager.markerCache:', window.markerManager?.markerCache?.size || 0);
            console.log('- window.dataService:', window.dataService ? 'exists' : 'missing');
            console.log('- window.dataService.cache:', window.dataService?.cache?.size || 0);
            console.log('- window.markers:', window.markers?.length || 0);
            
            // Additional debugging for markerManager
            if (window.markerManager) {
                console.log('- markerManager.markerCache keys:', Array.from(window.markerManager.markerCache?.keys() || []));
                console.log('- markerManager.markerCache values sample:', Array.from(window.markerManager.markerCache?.values() || []).slice(0, 3));
            }
            
            // Additional debugging for dataService
            if (window.dataService && window.dataService.cache) {
                console.log('- dataService.cache entries:');
                window.dataService.cache.forEach((value, key) => {
                    console.log(`  - ${key}:`, value);
                });
            }
            
            return [];
        }

        console.log(`8. Initial locations found: ${locations.length}`);
        console.log('9. Current maxDistance:', this.maxDistance);

        // Apply distance filter
        const beforeDistanceFilter = locations.length;
        locations = locations.filter(location => {
            const distance = this.calculateDistance(
                window.userCoords.lat, window.userCoords.lng,
                location.lat, location.lng
            );
            location.distance = distance;
            return distance <= this.maxDistance;
        });
        console.log(`10. After distance filter (${this.maxDistance} miles): ${locations.length} locations (was ${beforeDistanceFilter})`);
        
        if (locations.length > 0) {
            console.log('11. Sample locations after distance filter:', locations.slice(0, 3));
        }

        // Apply retailer type filters
        const beforeTypeFilter = locations.length;
        locations = this.applyRetailerTypeFilters(locations);
        console.log(`12. After retailer type filter: ${locations.length} locations (was ${beforeTypeFilter})`);
        
        if (locations.length > 0) {
            console.log('13. Sample locations after type filter:', locations.slice(0, 3));
        }

        // Apply opening hours filter
        if (openNow) {
            const beforeHoursFilter = locations.length;
            locations = this.filterByOpeningHours(locations);
            console.log(`14. After opening hours filter: ${locations.length} locations (was ${beforeHoursFilter})`);
            
            if (locations.length > 0) {
                console.log('15. Sample locations after hours filter:', locations.slice(0, 3));
            }
        } else {
            console.log('14. Skipping opening hours filter (openNow = false)');
        }

        // Apply popularity filter
        if (leastPopular || mostPopular) {
            const beforePopularityFilter = locations.length;
            locations = this.filterByPopularity(locations, leastPopular, mostPopular);
            console.log(`16. After popularity filter: ${locations.length} locations (was ${beforePopularityFilter})`);
            
            if (locations.length > 0) {
                console.log('17. Sample locations after popularity filter:', locations.slice(0, 3));
            }
        } else {
            console.log('16. Skipping popularity filter (no popularity filter selected)');
        }

        console.log(`18. FINAL: Returning ${locations.length} filtered locations`);
        return locations;
    }

    /**
     * Apply retailer type filters based on route planner toggles
     */
    applyRetailerTypeFilters(locations) {
        console.log('=== APPLY RETAILER TYPE FILTERS DEBUG ===');
        const activeFilters = [];
        
        // Check which toggles are active in the route planner
        const toggles = document.querySelectorAll('.route-filter-toggle');
        console.log('1. Found route filter toggles:', toggles.length);
        
        toggles.forEach((toggle, index) => {
            const filterType = toggle.getAttribute('data-filter');
            const isActive = toggle.classList.contains('active');
            console.log(`2. Toggle ${index + 1}: ${filterType} - ${isActive ? 'ACTIVE' : 'inactive'}`);
            
            if (isActive) {
                activeFilters.push(filterType);
            }
        });

        console.log('3. Active filters:', activeFilters);

        // If no filters are active, return all locations (don't filter)
        if (activeFilters.length === 0) {
            console.log('4. No retailer type filters active, showing all location types');
            return locations;
        }

        console.log('5. Applying retailer type filters:', activeFilters);
        
        // Debug: Show all unique retailer types in the data
        const uniqueTypes = [...new Set(locations.map(loc => loc.retailer_type).filter(Boolean))];
        console.log('6. All unique retailer types in data:', uniqueTypes);
        
        const filtered = locations.filter((location, index) => {
            const retailerType = (location.retailer_type || '').toLowerCase();
            const matches = activeFilters.includes(retailerType);
            if (index < 5) { // Log first 5 locations for debugging
                console.log(`   Location ${index + 1}: ${location.retailer} (${location.retailer_type || 'unknown'}) -> ${retailerType} - ${matches ? 'MATCHES' : 'no match'}`);
            }
            return matches;
        });
        console.log(`6. Filtered from ${locations.length} to ${filtered.length} locations`);
        return filtered;
    }

    /**
     * Filter locations by opening hours using the isOpenNow function from utils.js
     */
    filterByOpeningHours(locations) {
        // Import the isOpenNow function from utils.js
        if (typeof window.isOpenNow !== 'function') {
            console.warn('isOpenNow function not available, skipping opening hours filter');
            return locations;
        }

        return locations.filter(location => {
            const hours = location.opening_hours;
            if (!hours) {
                return false; // Exclude if no opening hours data
            }
            
            // Use the isOpenNow function from utils.js
            return window.isOpenNow(hours);
        });
    }

    /**
     * Filter locations by popularity (heatmap data)
     */
    filterByPopularity(locations, leastPopular, mostPopular) {
        if (!leastPopular && !mostPopular) {
            return locations; // No popularity filter applied
        }

        // Get heatmap data if available
        const heatmapData = window.heatmapData || [];
        if (heatmapData.length === 0) {
            console.warn('No heatmap data available for popularity filtering');
            return locations;
        }

        // Create a map of location popularity scores
        const popularityMap = new Map();
        heatmapData.forEach(point => {
            const key = `${point.lat},${point.lng}`;
            const existing = popularityMap.get(key) || 0;
            popularityMap.set(key, existing + (point.value || 1));
        });

        // Calculate popularity scores for each location
        const locationsWithScores = locations.map(location => {
            const key = `${location.lat},${location.lng}`;
            const popularityScore = popularityMap.get(key) || 0;
            return { ...location, popularityScore };
        });

        // Sort by popularity score
        locationsWithScores.sort((a, b) => a.popularityScore - b.popularityScore);

        // Filter based on selection
        if (leastPopular) {
            // Take the bottom 25% of locations (least popular)
            const cutoffIndex = Math.floor(locationsWithScores.length * 0.25);
            return locationsWithScores.slice(0, cutoffIndex);
        } else if (mostPopular) {
            // Take the top 25% of locations (most popular)
            const cutoffIndex = Math.floor(locationsWithScores.length * 0.75);
            return locationsWithScores.slice(cutoffIndex);
        }

        return locationsWithScores;
    }

    /**
     * Select optimal locations for the route
     */
    selectOptimalLocations(locations) {
        console.log('=== SELECT OPTIMAL LOCATIONS DEBUG ===');
        console.log('1. Input locations:', locations?.length || 0);
        console.log('2. Current maxStops:', this.maxStops);
        
        if (!locations || locations.length === 0) {
            console.log('3. ERROR: No locations provided');
            return [];
        }

        // Sort by distance and take the closest ones up to maxStops
        const sorted = locations.sort((a, b) => a.distance - b.distance);
        const selected = sorted.slice(0, this.maxStops);
        
        console.log('4. Sorted locations by distance');
        console.log('5. Selected locations:', selected.length);
        console.log('6. Selected locations details:', selected.map((loc, i) => 
            `${i + 1}. ${loc.retailer} (${loc.distance?.toFixed(1)} mi)`
        ));
        
        return selected;
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
        console.log('=== ROUTE PLANNER PREVIEW DEBUG ===');
        console.log('1. showPreviewPins called');
        console.log('2. userCoords:', window.userCoords);
        console.log('3. allMarkers:', window.allMarkers?.length || 0);
        console.log('4. markerManager:', window.markerManager ? 'exists' : 'missing');
        console.log('5. markerCache size:', window.markerManager?.markerCache?.size || 0);
        console.log('6. window.markers:', window.markers?.length || 0);
        console.log('7. dataService:', window.dataService ? 'exists' : 'missing');
        console.log('8. dataService cache size:', window.dataService?.cache?.size || 0);
        if (window.dataService?.cache) {
            console.log('9. dataService cache keys:', Array.from(window.dataService.cache.keys()));
        }
        
        // Additional debugging for markerManager
        if (window.markerManager) {
            console.log('10. markerManager.markerCache keys:', Array.from(window.markerManager.markerCache?.keys() || []));
            console.log('11. markerManager.markerCache values sample:', Array.from(window.markerManager.markerCache?.values() || []).slice(0, 3));
        }
        
        // Additional debugging for dataService
        if (window.dataService && window.dataService.cache) {
            console.log('12. dataService.cache entries:');
            window.dataService.cache.forEach((value, key) => {
                console.log(`  - ${key}:`, value);
            });
        }
        
        // Check if basic requirements are met
        if (!window.userCoords) {
            console.log('ERROR: No user coordinates available');
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
        
        console.log('13. hasMarkerData:', hasMarkerData);
        
        if (!hasMarkerData) {
            console.log('ERROR: No marker data available');
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
        const leastPopular = document.getElementById('least-popular-checkbox')?.checked || false;
        const mostPopular = document.getElementById('most-popular-checkbox')?.checked || false;
        console.log('14. openNow filter:', openNow);
        console.log('15. leastPopular filter:', leastPopular);
        console.log('16. mostPopular filter:', mostPopular);
        
        const availableLocations = this.getFilteredLocations(openNow, leastPopular, mostPopular);
        console.log('17. availableLocations:', availableLocations.length);
        console.log('18. availableLocations sample:', availableLocations.slice(0, 3));
        
        this.selectedLocations = this.selectOptimalLocations(availableLocations);
        console.log('19. selectedLocations:', this.selectedLocations.length);
        console.log('20. selectedLocations details:', this.selectedLocations);

        if (this.selectedLocations.length === 0) {
            console.log('ERROR: No locations selected after filtering');
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

        // Collect all positions for auto-zoom
        const allPositions = [
            { lat: window.userCoords.lat, lng: window.userCoords.lng }
        ];
        console.log('Starting position collection. User coords:', window.userCoords);

        // Create start pin (green) with shaded circle
        const startPin = new google.maps.Marker({
            position: { lat: window.userCoords.lat, lng: window.userCoords.lng },
            map: window.map,
            title: 'Start Location',
            icon: {
                path: google.maps.SymbolPath.CIRCLE,
                scale: 12,
                fillColor: '#28a745',
                fillOpacity: 1,
                strokeColor: '#ffffff',
                strokeWeight: 3
            }
        });
        this.previewPins.push(startPin);

        // Create shaded circle around start pin
        const startCircle = new google.maps.Circle({
            strokeColor: '#28a745',
            strokeOpacity: 0.3,
            strokeWeight: 2,
            fillColor: '#28a745',
            fillOpacity: 0.1,
            map: window.map,
            center: { lat: window.userCoords.lat, lng: window.userCoords.lng },
            radius: 500 // 500 meters radius
        });
        this.previewPins.push(startCircle);

        // Create stop pins (orange) with shaded circles
        this.selectedLocations.forEach((location) => {
            allPositions.push({ lat: location.lat, lng: location.lng });
            console.log('Added location to positions:', location.retailer, location.lat, location.lng);
            
            // Create shaded circle around stop pin FIRST (so it appears below)
            const stopCircle = new google.maps.Circle({
                strokeColor: '#ff6b35',
                strokeOpacity: 0.3,
                strokeWeight: 2,
                fillColor: '#ff6b35',
                fillOpacity: 0.1,
                map: window.map,
                center: { lat: location.lat, lng: location.lng },
                radius: 400 // 400 meters radius
            });
            this.previewPins.push(stopCircle);
            
            // Create stop pin (orange) with bouncing animation
            const stopPin = new google.maps.Marker({
                position: { lat: location.lat, lng: location.lng },
                map: window.map,
                title: `${location.retailer || 'Unknown'} (${location.distance?.toFixed(1) || '?'} mi)`,
                icon: {
                    path: google.maps.SymbolPath.CIRCLE,
                    scale: 12,
                    fillColor: '#ff6b35',
                    fillOpacity: 1,
                    strokeColor: '#ffffff',
                    strokeWeight: 3
                }
            });
            this.previewPins.push(stopPin);
            
            // Add bouncing animation to the pin
            this.addBouncingAnimation(stopPin);
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
                    scale: 12,
                    fillColor: '#dc3545',
                    fillOpacity: 1,
                    strokeColor: '#ffffff',
                    strokeWeight: 3
                }
            });
            this.previewPins.push(endPin);

            // Create shaded circle around end pin
            const endCircle = new google.maps.Circle({
                strokeColor: '#dc3545',
                strokeOpacity: 0.3,
                strokeWeight: 2,
                fillColor: '#dc3545',
                fillOpacity: 0.1,
                map: window.map,
                center: { lat: window.userCoords.lat, lng: window.userCoords.lng },
                radius: 500 // 500 meters radius
            });
            this.previewPins.push(endCircle);
        }

        // Auto-zoom to fit all preview points with padding
        console.log('Final positions for zooming:', allPositions);
        this.zoomToFitPreviewPoints(allPositions);
    }

    /**
     * Add bouncing animation to a marker
     */
    addBouncingAnimation(marker) {
        let bounceCount = 0;
        const maxBounces = 3;
        const bounceHeight = 10; // pixels
        const bounceDuration = 600; // milliseconds
        
        const bounce = () => {
            if (bounceCount >= maxBounces) return;
            
            // Get current position
            const position = marker.getPosition();
            const originalLat = position.lat();
            const originalLng = position.lng();
            
            // Bounce up
            const bounceUp = () => {
                const newPosition = new google.maps.LatLng(
                    originalLat + (bounceHeight / 100000), // Small lat offset for visual effect
                    originalLng
                );
                marker.setPosition(newPosition);
            };
            
            // Bounce down
            const bounceDown = () => {
                marker.setPosition(position);
                bounceCount++;
                
                // Schedule next bounce
                if (bounceCount < maxBounces) {
                    setTimeout(bounce, 1000); // Wait 1 second between bounces
                }
            };
            
            // Execute bounce sequence
            bounceUp();
            setTimeout(bounceDown, bounceDuration);
        };
        
        // Start bouncing after a short delay
        setTimeout(bounce, 500);
    }

    /**
     * Zoom map to fit all preview points with padding
     */
    zoomToFitPreviewPoints(positions) {
        if (!positions || positions.length === 0) {
            console.log('No positions to zoom to');
            return;
        }

        console.log('Zooming to fit positions:', positions);

        const bounds = new google.maps.LatLngBounds();
        
        // Add all positions to bounds
        positions.forEach(pos => {
            const latLng = new google.maps.LatLng(pos.lat, pos.lng);
            bounds.extend(latLng);
            console.log('Added position to bounds:', pos.lat, pos.lng);
        });

        // Add padding to bounds (expand by 20% for better visibility)
        const ne = bounds.getNorthEast();
        const sw = bounds.getSouthWest();
        const latDiff = (ne.lat() - sw.lat()) * 0.2;
        const lngDiff = (ne.lng() - sw.lng()) * 0.2;
        
        bounds.extend(new google.maps.LatLng(ne.lat() + latDiff, ne.lng() + lngDiff));
        bounds.extend(new google.maps.LatLng(sw.lat() - latDiff, sw.lng() - lngDiff));

        console.log('Bounds created:', {
            north: bounds.getNorthEast().lat(),
            east: bounds.getNorthEast().lng(),
            south: bounds.getSouthWest().lat(),
            west: bounds.getSouthWest().lng()
        });

        // Fit map to bounds with smooth animation
        window.map.fitBounds(bounds);
        
        // Ensure reasonable zoom level and add a small delay for the animation
        setTimeout(() => {
            const currentZoom = window.map.getZoom();
            console.log('Current zoom level:', currentZoom);
            
            // If zoomed out too far, set a reasonable zoom level
            if (currentZoom < 10) {
                window.map.setZoom(12);
                console.log('Adjusted zoom to 12');
            }
            // If zoomed in too close, set a reasonable zoom level
            else if (currentZoom > 16) {
                window.map.setZoom(14);
                console.log('Adjusted zoom to 14');
            }
        }, 500);
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
        const leastPopular = document.getElementById('least-popular-checkbox')?.checked || false;
        const mostPopular = document.getElementById('most-popular-checkbox')?.checked || false;
        
        const availableLocations = this.getFilteredLocations(openNow, leastPopular, mostPopular);
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
            const leastPopular = document.getElementById('least-popular-checkbox')?.checked || false;
            const mostPopular = document.getElementById('most-popular-checkbox')?.checked || false;
            const availableLocations = this.getFilteredLocations(openNow, leastPopular, mostPopular);
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