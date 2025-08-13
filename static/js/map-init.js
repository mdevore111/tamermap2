// ==== static/js/map-init.js ====
// Initializes the Google Map, handles geolocation, marker creation,
// data fetching, heatmaps, and orchestrates filtering.

// Entry point called by Google Maps API - expose to global scope immediately
function initApp() {
  if (navigator.geolocation) {
    navigator.geolocation.getCurrentPosition(
      pos => {
        window.userCoords = { lat: pos.coords.latitude, lng: pos.coords.longitude };
        renderMap();
      },
      () => {
        console.warn('Geolocation failed; using defaults.');
        renderMap();
      }
    );
  } else {
    console.warn('Geolocation not supported; using defaults.');
    renderMap();
  }
}

// Explicitly expose initApp to global scope for Google Maps callback
window.initApp = initApp;

// Side-effect imports
import './map-utils.js';   // getPinColor, formatHours
import './map-ui.js';      // initUI(), domCache, isOpenNow
import './uiHelpers.js';   // renderRetailerInfoWindow, renderEventInfoWindow

// Config & constants
import {
  DEFAULT_COORDS,
  MAP_SETTINGS,
  MAP_TYPE_ID,
  ZOOM_CONTROL_STYLE,
  ENDPOINTS,
  Z_INDICES
} from './config.js';

// Data & filtering
import { fetchRetailers, fetchEvents, DataService } from './dataService.js';
// import { filterMarkersViewport, filterEventMarkers } from './filterService.js';

// Marker factories
import { createRetailerMarker, createEventMarker } from './markerFactory.js';

// Utilities
import { isEventUpcoming, isOpenNow } from './utils.js';

import { MarkerManager } from './markerManager.js';

// Global state
// Comment out legacy filtering code and arrays
// import { filterMarkersViewport, filterEventMarkers } from './filterService.js';
// window.allMarkers        = [];
// window.allEventMarkers   = [];
// window.applyFilters = () => {
//   filterMarkersViewport(window.map, window.allMarkers, window.domCache, isOpenNow);
//   filterEventMarkers(window.map, window.allEventMarkers, window.domCache);
//   // ...heatmap code...
// };
// Use only the new system:
window.applyFilters = applyFilters;
window.userCoords        = DEFAULT_COORDS;
window.map               = null;
window.infoWindow        = null;
window.currentOpenMarker = null;
window.is_pro            = window.is_pro || false;

// Global variables
let map;
let markerManager;
let dataService;
let loadingOverlay;

// Unified filter function: applies retailer, event, and heatmap filters

// Create the map, markers, heatmap, and listeners
function renderMap() {
  // Initialize map
  window.map = new google.maps.Map(
    document.getElementById('map'),
    {
      center:           window.userCoords,
      zoom:             MAP_SETTINGS.zoom,
      minZoom:          MAP_SETTINGS.minZoom,
      maxZoom:          MAP_SETTINGS.maxZoom,
      gestureHandling:  MAP_SETTINGS.gestureHandling,
      disableDefaultUI: MAP_SETTINGS.disableDefaultUI,
      zoomControl:      MAP_SETTINGS.zoomControl,
      mapTypeId:        google.maps.MapTypeId[MAP_TYPE_ID],
      zoomControlOptions: { style: google.maps.ZoomControlStyle[ZOOM_CONTROL_STYLE] },
      styles: [
        { featureType: 'poi', elementType: 'labels', stylers: [{ visibility: 'off' }] },
        { featureType: 'poi.business', stylers: [{ visibility: 'off' }] },
        { featureType: 'poi.government', stylers: [{ visibility: 'off' }] },
        { featureType: 'poi.medical', stylers: [{ visibility: 'off' }] },
        { featureType: 'poi.park', elementType: 'labels', stylers: [{ visibility: 'off' }] },
        { featureType: 'poi.school', stylers: [{ visibility: 'off' }] },
        { featureType: 'poi.place_of_worship', stylers: [{ visibility: 'off' }] }
      ]
    }
  );

  // Auto‑center flag
  let autoCenter = true;

  // User location marker
  const userLocationMarker = new google.maps.Marker({
    position: window.userCoords,
    map: window.map,
    title: 'Your Location (Live)',
    icon: {
      path: google.maps.SymbolPath.CIRCLE,
      fillColor: '#1A73E8',
      fillOpacity: 0.9,
      strokeColor: 'white',
      strokeWeight: 2,
      scale: 10
    },
    zIndex: Z_INDICES.ui
  });

  // Continuously update user location with mobile-friendly settings
  let lastLocationUpdate = 0;
  if (navigator.geolocation) {
    navigator.geolocation.watchPosition(
      pos => {
        const now = Date.now();
        // Throttle updates to maximum once every 3 seconds
        if (now - lastLocationUpdate < 3000) return;
        
        const newCoords = { lat: pos.coords.latitude, lng: pos.coords.longitude };
        
        // Only update if location changed significantly (>10 meters)
        if (window.userCoords) {
          const distance = google.maps.geometry.spherical.computeDistanceBetween(
            new google.maps.LatLng(window.userCoords.lat, window.userCoords.lng),
            new google.maps.LatLng(newCoords.lat, newCoords.lng)
          );
          if (distance < 10) return; // Skip update if moved less than 10 meters
        }
        
        lastLocationUpdate = now;
        window.userCoords = newCoords;
        userLocationMarker.setPosition(newCoords);
        
        // Only auto-center if user hasn't interacted with map recently
        if (autoCenter && now - (window.lastMapInteraction || 0) > 5000) {
          window.map.setCenter(newCoords);
        }
      },
      err => console.error('Error watching position:', err),
      { 
        enableHighAccuracy: false, // Use network location instead of GPS
        maximumAge: 30000,         // Accept 30-second old location
        timeout: 15000             // Longer timeout
      }
    );
  }

  // Listen for manual interactions to disable auto-centering and track interaction time
  window.map.addListener('dragstart', () => { 
    autoCenter = false; 
    window.lastMapInteraction = Date.now();
  });
  window.map.addListener('zoom_changed', () => { 
    autoCenter = false; 
    window.lastMapInteraction = Date.now();
  });
  window.map.addListener('click', () => { 
    window.lastMapInteraction = Date.now();
  });

  // "My Location" button
  const myLocationButton = document.createElement('button');
  myLocationButton.innerHTML = `
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="24" height="24">
      <path fill="currentColor" d="M12 22C6.477 22 2 17.523 2 12S6.477 2 12 2s10 4.477 10
      10-4.477 10-10 10zm1-2.062 A8.004 8.004 0 0 0 19.938 13H16a1 1 0 1 1 0-2h3.938A8.004
      8.004 0 0 0 13 4.062V8a1 1 0 1 1-2 0V4.062A8.004 8.004 0 0 0 4.062 11H8a1 1 0
      1 1 0 2H4.062A8.004 8.004 0 0 0 11 19.938V16a1 1 0 1 1 2 0v3.938z"/>
    </svg>
  `;
  myLocationButton.classList.add('my-location-button');
  myLocationButton.setAttribute('aria-label', 'Center map on your location');
  myLocationButton.addEventListener('click', () => {
    autoCenter = true;
    window.map.setCenter(window.userCoords);
    window.map.setZoom(15);
  });
  window.map.controls[google.maps.ControlPosition.RIGHT_BOTTOM].push(myLocationButton);

  // Initialize InfoWindow with default positioning behavior
  window.infoWindow = new google.maps.InfoWindow({
    disableAutoPan: false, // Allow Google Maps to handle positioning
    pixelOffset: new google.maps.Size(0, -5),
    maxWidth: 320,
    // Ensure close button is enabled
    closeButton: true
  });
  window.currentOpenMarker = null;
  
  // Add close listener to restore legend appearance when InfoWindow is closed
  google.maps.event.addListener(window.infoWindow, 'closeclick', function() {
    window.currentOpenMarker = null;
    const legend = document.getElementById('legend');
    if (legend) legend.classList.remove('has-active-infowindow');
  });

  // Fetch and build Popular Areas heatmap layer (for display)
  fetch(ENDPOINTS.popularAreas)
    .then(res => { if (!res.ok) throw new Error(`Heatmap fetch failed: ${res.status}`); return res.json(); })
    .then(points => {
      // Convert array format [lat, lng, weight] to LatLng objects with weight for Google Maps
      const heatmapData = points.map(point => ({
        location: new google.maps.LatLng(point[0], point[1]),
        weight: point[2]
      }));

      window.popularAreasHeatmap = new google.maps.visualization.HeatmapLayer({
        data: heatmapData,
        radius: 50,  // Increased radius for better visibility
        opacity: 0.9,  // Increased opacity
        maxIntensity: 20,  // Adjusted for better color distribution
        dissipating: true,
        gradient: [
          'rgba(0, 0, 0, 0)',    // Start with transparent
          'rgba(0, 255, 255, 1)', // Cyan
          'rgba(0, 255, 0, 1)',   // Green
          'rgba(255, 255, 0, 1)', // Yellow
          'rgba(255, 0, 0, 1)'    // Red
        ]
      });

      // Set the z-index of the heatmap layer
      window.popularAreasHeatmap.setOptions({
        zIndex: 2  // This ensures the heatmap renders above the base map but below markers
      });

      if (window.domCache.filterPopularAreas?.checked) {
        window.popularAreasHeatmap.setMap(window.map);
      }
    })
    .catch(err => {
      console.error('Error fetching heatmap data:', err);
      // Notify user of error
      const toast = document.createElement('div');
      toast.className = 'toast align-items-center text-white bg-danger border-0';
      toast.setAttribute('role', 'alert');
      toast.setAttribute('aria-live', 'assertive');
      toast.setAttribute('aria-atomic', 'true');
      toast.innerHTML = `
        <div class="d-flex">
          <div class="toast-body">
            Failed to load heatmap data. Please try refreshing the page.
          </div>
          <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
        </div>
      `;
      document.body.appendChild(toast);
      const bsToast = new bootstrap.Toast(toast);
      bsToast.show();
    });

  // Fetch individual popularity data (for routing with full precision)
  fetch(ENDPOINTS.individualPopularity)
    .then(res => { if (!res.ok) throw new Error(`Individual popularity fetch failed: ${res.status}`); return res.json(); })
    .then(data => {
      // Store individual popularity data for route planner to use
      window.individualPopularityData = data;
      console.log('Loaded individual popularity data for', data.length, 'locations');
    })
    .catch(err => {
      console.error('Error fetching individual popularity data:', err);
      window.individualPopularityData = [];
    });

  // Helper: wire an Autocomplete with a session token lifecycle and details fallback
  function setupAutocompleteWithSession(inputEl) {
    if (!inputEl) return null;
    let sessionToken = null;
    const autocomplete = new google.maps.places.Autocomplete(inputEl, {
      fields: ['place_id','geometry'],
      types: ['establishment','address'],
      componentRestrictions: { country: 'us' }
    });
    autocomplete.bindTo('bounds', window.map);
    inputEl.addEventListener('focus', () => {
      sessionToken = new google.maps.places.AutocompleteSessionToken();
    });
    inputEl.addEventListener('blur', () => { sessionToken = null; });
    autocomplete.addListener('place_changed', () => {
      const place = autocomplete.getPlace();
      const applyPlace = (p) => {
        if (p && p.geometry) { window.map.setCenter(p.geometry.location); window.map.setZoom(12); }
      };
      if (place && place.geometry) {
        applyPlace(place);
        sessionToken = null; return;
      }
      if (place && place.place_id) {
        const svc = new google.maps.places.PlacesService(window.map);
        svc.getDetails({ placeId: place.place_id, fields: ['place_id','geometry'], sessionToken }, (res, status) => {
          if (status === google.maps.places.PlacesServiceStatus.OK && res && res.geometry) {
            applyPlace(res);
          } else {
            console.warn('Places getDetails failed:', status);
          }
          sessionToken = null;
        });
      } else {
        sessionToken = null;
      }
    });
    return autocomplete;
  }

  // Places Autocomplete (#pac-input)
  const placesInput = document.getElementById('pac-input');
  if (placesInput) {
    setupAutocompleteWithSession(placesInput);
    window.map.controls[google.maps.ControlPosition.TOP_LEFT].push(placesInput);
  }

  // Search-control Autocomplete
  const searchInput = document.querySelector('#search-control input.form-control');
  if (searchInput) {
    setupAutocompleteWithSession(searchInput);
  } else { console.warn('Search input for autocomplete not found.'); }

  // Also initialize the places_search input if it exists
  const placesSearchInput = document.getElementById('places_search');
  if (placesSearchInput) {
    setupAutocompleteWithSession(placesSearchInput);
  }

  // On idle: filters & track map
  window.map.addListener('idle', () => {
    window.applyFilters();
    const c = window.map.getCenter();
    fetch(ENDPOINTS.trackMap, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ lat: c.lat(), lng: c.lng(), zoom: window.map.getZoom() })
    }).catch(console.error);
  });

  // Close infoWindow on map click
  window.map.addListener('click', () => {
    window.infoWindow.close();
    window.currentOpenMarker = null;
    // Remove has-active-infowindow class from legend when infowindow is closed
    const legend = document.getElementById('legend');
    if (legend) legend.classList.remove('has-active-infowindow');
  });

  // Initialize marker manager and data service
  markerManager = new MarkerManager(window.map);
  dataService = new DataService();
  
  // Initialize loading overlay
  initLoadingOverlay();

  // Initialize UI components (legend, search, filters)
  initUI();

  // Set up proper stacking immediately and on idle
  setupMapStacking();
  window.map.addListener('idle', setupMapStacking);

  // Set up viewport change listeners for progressive loading
  setupMapEventListeners();

  // Wait for map to be properly initialized before loading data
  window.map.addListener('idle', () => {
    // Only load data on first idle event
    if (!window.dataLoaded) {
      window.dataLoaded = true;
      loadOptimizedMapData();
    }
  });
}

/**
 * Load optimized map data using the new system
 */
async function loadOptimizedMapData() {
  try {
    showLoadingOverlay();
    
    // Get initial viewport bounds for filtering
    const bounds = dataService.getMapBounds(window.map);
    
    // If no bounds available, use a default viewport around user location
    let effectiveBounds = bounds;
    if (!bounds && window.userCoords) {
      const defaultRadius = 0.1; // About 11km radius
      effectiveBounds = {
        north: window.userCoords.lat + defaultRadius,
        south: window.userCoords.lat - defaultRadius,
        east: window.userCoords.lng + defaultRadius,
        west: window.userCoords.lng - defaultRadius
      };
    }
    
    // Load combined data in a single request
    const mapData = await dataService.loadMapData(effectiveBounds, {
      includeEvents: true,
      daysAhead: 30
    });
    

    
    // Load markers progressively and maintain compatibility with existing filter system
    await Promise.all([
      markerManager.loadRetailers(mapData.retailers),
      markerManager.loadEvents(mapData.events)
    ]);
    
    // Populate legacy arrays for compatibility with existing filter system
    window.allMarkers = Array.from(markerManager.markerCache.values())
      .filter(marker => marker.retailer_type); // Only retailer markers
    
    window.allEventMarkers = Array.from(markerManager.markerCache.values())
      .filter(marker => marker.event_title); // Only event markers
    
    // Expose marker visibility functions globally for route planner
    window.hideAllMarkers = () => markerManager.hideAllMarkers();
    window.showAllMarkers = () => markerManager.showAllMarkers();
    window.getVisibleMarkers = () => markerManager.getVisibleMarkers();
    
    // Set up drag end listener for info windows
    window.map.addListener('dragend', () => {
      if (window.currentOpenMarker && !window.map.getBounds().contains(window.currentOpenMarker.getPosition())) {
        window.infoWindow.close(); 
        window.currentOpenMarker = null;
      }
    });
    
    // Apply filters to show markers
    window.applyFilters();
    
    // Update viewport tracking
    dataService.updateLastViewport(bounds);
    
    hideLoadingOverlay();
    
    // Show performance stats in console

    
  } catch (error) {
    console.error('Error loading optimized map data:', error);
    hideLoadingOverlay();
    showErrorMessage('Failed to load map data. Please refresh the page.');
    
    // Fallback to original system if optimization fails

    loadLegacyMapData();
  }
}

/**
 * Fallback to original data loading if optimization fails
 */
function loadLegacyMapData() {
  fetchRetailers()
    .then(data => {
      if (data && Array.isArray(data)) {
        window.allMarkers = data.map(r => createRetailerMarker(window.map, r)).filter(m => m);
      } else {
        window.allMarkers = [];
      }
      loadEventMarkers();
      window.applyFilters();
    })
    .catch(err => {
      console.error('Error fetching retailers:', err);
      window.allMarkers = [];
      loadEventMarkers();
      window.applyFilters();
    });
}

function loadEventMarkers() {
  fetchEvents()
    .then(events => {
      window.allEventMarkers.forEach(m => m.setMap(null));
      window.allEventMarkers = [];
      
      // Load all events and let the filter function handle date filtering
      if (events && Array.isArray(events)) {
        events.forEach(evt => {
          const m = createEventMarker(window.map, evt);
          if (m) window.allEventMarkers.push(m);
        });
      }
      
      window.applyFilters();
    })
    .catch(err => {
      console.error('Error fetching events:', err);
      // Initialize empty array if events fail to load
      window.allEventMarkers = [];
      window.applyFilters();
    });
}

// After creating the map, set up proper stacking context
function setupMapStacking() {
  // Force legend to have lower z-index
  const legend = document.getElementById('legend');
  if (legend) {
    legend.style.zIndex = '1';
  }
  
  // Just set z-indices, don't modify positioning
  setTimeout(() => {
    // Force any info windows to highest z-index
    const infoWindows = document.querySelectorAll('.gm-style-iw-c, .gm-style-iw-t, .gm-style-iw-a');
    infoWindows.forEach(iw => {
      iw.style.zIndex = '99999';
    });
    
    // Fix close buttons
    const closeButtons = document.querySelectorAll('button.gm-ui-hover-effect');
    closeButtons.forEach(btn => {
      btn.style.zIndex = '999999';
      btn.style.display = 'block';
      btn.style.visibility = 'visible';
      btn.style.opacity = '1';
    });
  }, 100);
}

/**
 * Set up optimized map event listeners
 */
function setupMapEventListeners() {
    // Debounced bounds change handler for viewport-based loading
    let boundsChangeTimer;
    window.map.addListener('bounds_changed', () => {
        clearTimeout(boundsChangeTimer);
        boundsChangeTimer = setTimeout(() => {
            handleViewportChange();
        }, 300); // Slightly longer debounce for data loading
    });
    
    // Idle event for loading new data when user stops moving
    window.map.addListener('idle', () => {
        handleMapIdle();
    });
}

/**
 * Handle viewport changes for progressive data loading
 */
async function handleViewportChange() {
    const bounds = dataService.getMapBounds(window.map);
    if (!bounds) return;
    
    // Check if viewport has changed significantly
    if (!dataService.hasViewportChanged(bounds, 0.2)) {
        return; // Not enough change to warrant new data
    }
    
    try {
        // Load new data for the viewport
        const mapData = await dataService.loadMapData(bounds, {
            includeEvents: true,
            daysAhead: 30
        });
        
        // Update markers if we got new data
        if (mapData.viewport_filtered) {
        
            
            // Update markers progressively
            await Promise.all([
                markerManager.loadRetailers(mapData.retailers),
                markerManager.loadEvents(mapData.events)
            ]);
        }
        
        // Update viewport tracking
        dataService.updateLastViewport(bounds);
        
    } catch (error) {
        console.warn('Error updating viewport data:', error);
    }
}

/**
 * Handle map idle event
 */
function handleMapIdle() {
    // Update visible markers based on current viewport
    // This is handled automatically by MarkerManager
    
    // Update UI elements if needed
    updateMapUI();
}

/**
 * Set up filter controls with optimized handling
 */
function setupFilterControls() {
    // Get filter elements
    const kioskToggle = document.getElementById('kiosk-toggle');
    const retailToggle = document.getElementById('retail-toggle');
    const indieToggle = document.getElementById('indie-toggle');
    const eventsToggle = document.getElementById('events-toggle');
    
    // Debounced filter handler
    let filterTimer;
    const handleFilterChange = () => {
        clearTimeout(filterTimer);
        filterTimer = setTimeout(() => {
            applyFilters();
        }, 100);
    };
    
    // Bind filter events
    if (kioskToggle) kioskToggle.addEventListener('change', handleFilterChange);
    if (retailToggle) retailToggle.addEventListener('change', handleFilterChange);
    if (indieToggle) indieToggle.addEventListener('change', handleFilterChange);
    if (eventsToggle) eventsToggle.addEventListener('change', handleFilterChange);
}

/**
 * Apply filters using the marker manager
 */
function applyFilters() {
    const eventDaysSlider = document.getElementById('event-days-slider');
    const filters = {
        showKiosk: document.getElementById('filter-kiosk')?.checked ?? false,
        showRetail: document.getElementById('filter-retail')?.checked ?? false,
        showIndie: document.getElementById('filter-indie')?.checked ?? false,
        showEvents: document.getElementById('filter-events')?.checked ?? false,
        showOpenNow: document.getElementById('filter-open-now')?.checked ?? false,
        showNew: document.getElementById('filter-new')?.checked ?? false,
        showPopular: document.getElementById('filter-popular-areas')?.checked ?? false,
        searchText: document.getElementById('legend_filter')?.value?.toLowerCase() || '',
        eventDays: eventDaysSlider ? parseInt(eventDaysSlider.value) : 30
    };

    // Debug logging


    markerManager.applyFilters(filters);

    // Toggle heatmap layer
    if (filters.showPopular) {
        window.popularAreasHeatmap?.setMap(window.map);
    } else {
        window.popularAreasHeatmap?.setMap(null);
    }

    updateFilterUI(filters);
}

/**
 * Initialize loading overlay
 */
function initLoadingOverlay() {
    loadingOverlay = document.createElement('div');
    loadingOverlay.id = 'map-loading-overlay';
    loadingOverlay.innerHTML = `
        <div class="loading-content">
            <div class="spinner"></div>
            <p>Loading map data...</p>
        </div>
    `;
    loadingOverlay.style.cssText = `
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background: rgba(255, 255, 255, 0.9);
        display: none;
        align-items: center;
        justify-content: center;
        z-index: 1000;
    `;
    
    document.getElementById('map').appendChild(loadingOverlay);
}

function showLoadingOverlay() {
    if (loadingOverlay) {
        loadingOverlay.style.display = 'flex';
    }
}

function hideLoadingOverlay() {
    if (loadingOverlay) {
        loadingOverlay.style.display = 'none';
    }
}

/**
 * Update map UI elements
 */
function updateMapUI() {
    // Update any UI elements that depend on map state
    const stats = markerManager.getStats();
    
    // Update marker count display if it exists
    const markerCount = document.getElementById('marker-count');
    if (markerCount) {
        markerCount.textContent = `${stats.visibleMarkers} visible`;
    }
}

/**
 * Update filter UI
 */
function updateFilterUI(filters) {
    // Update any filter-related UI elements

}

/**
 * Show error message to user
 */
function showErrorMessage(message) {
    // Create or update error display
    let errorDiv = document.getElementById('map-error');
    if (!errorDiv) {
        errorDiv = document.createElement('div');
        errorDiv.id = 'map-error';
        errorDiv.style.cssText = `
            position: absolute;
            top: 10px;
            left: 50%;
            transform: translateX(-50%);
            background: #ff4444;
            color: white;
            padding: 10px 20px;
            border-radius: 4px;
            z-index: 1001;
        `;
        document.getElementById('map').appendChild(errorDiv);
    }
    
    errorDiv.textContent = message;
    errorDiv.style.display = 'block';
    
    // Auto-hide after 5 seconds
    setTimeout(() => {
        errorDiv.style.display = 'none';
    }, 5000);
}

// touch
