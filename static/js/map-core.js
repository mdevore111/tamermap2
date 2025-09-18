// ==== static/js/map-init-v2.js ====
// Initializes the Google Map, handles geolocation, marker creation,
// data fetching, heatmaps, and orchestrates filtering.

window.__V2_LOADED__ = true;

// Entry point called by Google Maps API - expose to global scope immediately
function initApp() {
  if (window.__TM_DEBUG__) console.log('[map-init] initApp start');
  // Ensure userCoords is always set
  if (!window.userCoords) {
    window.userCoords = DEFAULT_COORDS;
  }
  
  if (navigator.geolocation) {
    navigator.geolocation.getCurrentPosition(
      pos => {
        window.userCoords = { lat: pos.coords.latitude, lng: pos.coords.longitude };
        if (window.__TM_DEBUG__) console.log('[map-init] geolocation success');
        renderMap();
      },
      () => { 
        // Fallback to default coordinates if geolocation fails
        window.userCoords = DEFAULT_COORDS;
        if (window.__TM_DEBUG__) console.warn('[map-init] geolocation failed, using default coords');
        renderMap(); 
      }
    );
  } else { 
    if (window.__TM_DEBUG__) console.log('[map-init] geolocation not available, rendering map');
    renderMap(); 
  }
}

// Explicitly expose initApp to global scope for Google Maps callback
// Change: expose as initAppImpl so maps.html wrapper can call it when ready
window.initAppImpl = initApp;
// updateFilterUI will be defined later in this file
if (window.__TM_DEBUG__) console.log('[map-init-v2] FILE LOADING - initAppImpl exposed');

// Define global variables before imports
window.is_pro = window.is_pro || false;

/**
 * Sync UI controls (slider containers) with current filter state
 * MUST be defined before imports since map-ui.js calls it during module load
 */
function updateFilterUI(filters) {
    if (window.__TM_DEBUG__) console.log('[map-core] updateFilterUI called with:', filters);
    try {
        const heatCont = document.getElementById('heatmap-days-slider-container');
        if (heatCont) {
            heatCont.style.display = filters && filters.showPopular ? 'block' : 'none';
        }

        const eventCont = document.getElementById('event-days-slider-container');
        if (eventCont) {
            eventCont.style.display = filters && filters.showEvents ? 'block' : 'none';
        }
    } catch (e) {
        console.error('[map-core] updateFilterUI error:', e);
    }
}

// Bind globally before imports
window.updateFilterUI = updateFilterUI;
if (window.__TM_DEBUG__) console.log('[map-core] updateFilterUI bound globally before imports');

// Side-effect imports
import './map-utils.js';   // getPinColor, formatHours
import './map-ui.js';      // initUI(), domCache, isOpenNow
import './uiHelpers.js';   // renderRetailerInfoWindow, renderEventInfoWindow
import './loadingOverlay.js'; // Loading overlay management
import './errorHandler.js';   // Error handling

// Config & constants
import {
  DEFAULT_COORDS,
  MAP_SETTINGS,
  MAP_TYPE_ID,
  ZOOM_CONTROL_STYLE,
  ENDPOINTS,
  Z_INDICES,
  DEBOUNCE_TIMINGS
} from './config.js';

// Data & filtering
import { DataService } from './dataService.js';


// Marker factories - imported by markerManager.js, not needed here

// Utilities
import { isOpenNow } from './utils.js';

import { MarkerManager } from './markerManager.js';
import { initLoadingOverlay, showLoadingOverlay, hideLoadingOverlay } from './loadingOverlay.js';
import { showErrorMessage } from './errorHandler.js';

// Global state
// Use only the new system:
window.applyFilters = applyFilters;
window.userCoords        = DEFAULT_COORDS;
window.map               = null;
window.infoWindow        = null;
window.currentOpenMarker = null;

// Global variables
let markerManager;
let dataService;
// Loading overlay is now imported from loadingOverlay.js

// Unified filter function: applies retailer, event, and heatmap filters

// Create the map, markers, heatmap, and listeners
function renderMap() {
  if (window.__TM_DEBUG__) console.log('[map-init] renderMap start');
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
  if (window.__TM_DEBUG__) console.log('[map-init] map object created');

  // Auto‑center flag
  let autoCenter = true;

  // Early wiring: create managers and kick off data load ASAP
  try {
    if (!markerManager) {
      markerManager = new MarkerManager(window.map);
      window.markerManager = markerManager; // Expose globally
      if (window.__TM_DEBUG__) console.log('[map-init] MarkerManager constructed early');
    }
    if (!dataService) {
      dataService = new DataService();
      if (window.__TM_DEBUG__) console.log('[map-init] DataService constructed early');
    }
    if (!loadingOverlay) {
      initLoadingOverlay();
      if (window.__TM_DEBUG__) console.log('[map-init] loading overlay initialized (early)');
    }
    if (window.initUI) {
      window.initUI();
      if (window.__TM_DEBUG__) console.log('[map-init] window.initUI called (early)');
    }
    // Kick off data load immediately
    if (window.__TM_DEBUG__) console.log('[map-init] About to call loadOptimizedMapData');
    loadOptimizedMapData().catch(err => {
      console.error('[map-init] loadOptimizedMapData failed:', err);
    });
    if (window.__TM_DEBUG__) console.log('[map-init] loadOptimizedMapData triggered (early)');
  } catch (e) {
    if (window.__TM_DEBUG__) console.warn('[map-init] Early wiring/load failed:', e);
  }

  if (window.__TM_DEBUG__) console.log('[map-init] About to create user location marker');

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

  if (window.__TM_DEBUG__) console.log('[map-init] User location marker created');

  // Continuously update user location with mobile-friendly settings
  if (window.__TM_DEBUG__) console.log('[map-init] Setting up continuous user location tracking');
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
      err => { 
        // Only log timeout errors in debug mode, they're non-critical
        if (window.__TM_DEBUG__ && err.code !== 3) {
          if (window.__TM_DEBUG__) console.warn('Geolocation error (non-critical):', err.message);
        }
      },
      { 
        enableHighAccuracy: false, // Use network location instead of GPS
        maximumAge: 60000,         // Accept 60-second old location
        timeout: 30000             // Much longer timeout (30s)
      }
    );
  }

  if (window.__TM_DEBUG__) console.log('[map-init] Geolocation watch setup complete');

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

  if (window.__TM_DEBUG__) console.log('[map-init] Map interaction listeners setup complete');

  // "My Location" button
  if (window.__TM_DEBUG__) console.log('[map-init] Creating My Location button');
  const myLocationButton = document.createElement('button');
  myLocationButton.innerHTML = `
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="18" height="18">
      <path fill="currentColor" d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7zm0 9.5c-1.38 0-2.5-1.12-2.5-2.5s1.12-2.5 2.5-2.5 2.5 1.12 2.5 2.5-1.12 2.5-2.5 2.5z"/>
    </svg>
  `;
  myLocationButton.classList.add('my-location-button');
  myLocationButton.setAttribute('aria-label', 'Center map on your location');
  myLocationButton.addEventListener('click', () => {
    autoCenter = true;
    window.map.setCenter(window.userCoords);
    window.map.setZoom(11); // Set to same zoom level as initial map
  });
  window.map.controls[google.maps.ControlPosition.RIGHT_TOP].push(myLocationButton);

  if (window.__TM_DEBUG__) console.log('[map-init] My Location button added to map controls');

  // Create custom zoom controls
  if (window.__TM_DEBUG__) console.log('[map-init] Creating custom zoom controls');
  
  // Zoom In button
  const zoomInButton = document.createElement('button');
  zoomInButton.innerHTML = `
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="18" height="18">
      <path d="M19 13h-6v6h-2v-6H5v-2h6V5h2v6h6v2z" fill="currentColor"/>
    </svg>
  `;
  zoomInButton.classList.add('custom-zoom-button', 'custom-zoom-in');
  zoomInButton.setAttribute('aria-label', 'Zoom in');
  zoomInButton.addEventListener('click', () => {
    const currentZoom = window.map.getZoom();
    window.map.setZoom(currentZoom + 1);
  });

  // Zoom Out button
  const zoomOutButton = document.createElement('button');
  zoomOutButton.innerHTML = `
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="18" height="18">
      <path d="M19 13H5v-2h14v2z" fill="currentColor"/>
    </svg>
  `;
  zoomOutButton.classList.add('custom-zoom-button', 'custom-zoom-out');
  zoomOutButton.setAttribute('aria-label', 'Zoom out');
  zoomOutButton.addEventListener('click', () => {
    const currentZoom = window.map.getZoom();
    window.map.setZoom(currentZoom - 1);
  });

  // Create container for zoom controls
  const zoomContainer = document.createElement('div');
  zoomContainer.classList.add('custom-zoom-container');
  zoomContainer.appendChild(zoomInButton);
  zoomContainer.appendChild(zoomOutButton);

  // Add to map - position in upper right, below My Location button
  window.map.controls[google.maps.ControlPosition.RIGHT_TOP].push(zoomContainer);
  // Spacing handled in CSS so controls stack consistently with My Location

  if (window.__TM_DEBUG__) console.log('[map-init] Custom zoom controls added to map');

  // Initialize InfoWindow with better positioning behavior
  if (window.__TM_DEBUG__) console.log('[map-init] Creating InfoWindow');
  window.infoWindow = new google.maps.InfoWindow({
    disableAutoPan: false, // Let Google handle primary auto-pan
    pixelOffset: new google.maps.Size(0, 0), // Revert: anchor bubble normally to the marker
    maxWidth: 320,
    // Ensure close button is enabled
    closeButton: true,
    // Set better positioning to avoid edge conflicts
    position: null, // Let Google Maps calculate optimal position
    // Add options to prevent excessive auto-pan
    shouldFocus: false // Don't automatically focus the map
  });

  // Removed custom ensure-in-view; rely on Google auto-pan to avoid oscillations

  // Add listener to adjust info window position and ensure full visibility
  window.infoWindow.addListener('domready', function() {
    const isMobile = window.innerWidth <= 768;
    if (isMobile) {
      const legend = document.getElementById('legend');
      if (legend && !legend.classList.contains('mobile-collapsed')) {
        // Drawer is open, adjust info window position to avoid being covered
        const infoWindowElement = document.querySelector('.gm-style-iw');
        if (infoWindowElement) {
          const drawerHeight = legend.offsetHeight;
          const currentTop = parseInt(infoWindowElement.style.top || '0');

          // If info window would be too low, move it up
          if (currentTop + infoWindowElement.offsetHeight > window.innerHeight - drawerHeight - 60) {
            infoWindowElement.style.top = (window.innerHeight - drawerHeight - infoWindowElement.offsetHeight - 60) + 'px';
          }
        }
      }
    }
    // No extra pan logic here; prevents tug-of-war with Google auto-pan
  });
  window.currentOpenMarker = null;
  
  // Add close listener to restore legend appearance when InfoWindow is closed
  google.maps.event.addListener(window.infoWindow, 'closeclick', function() {
    window.currentOpenMarker = null;
    const legend = document.getElementById('legend');
    if (legend) legend.classList.remove('has-active-infowindow');
  });

  // Remove previous throttling of auto-pan; rely on Google Maps + ensureInView

  if (window.__TM_DEBUG__) console.log('[map-init] InfoWindow setup complete');

  // Fetch and build Popular Areas heatmap layer (for display)
  if (window.__TM_DEBUG__) console.log('[map-init] About to fetch heatmap data');
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
      console.error('[renderMap] Error fetching heatmap data:', err);
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

  if (window.__TM_DEBUG__) console.log('[map-init] Heatmap fetch initiated, continuing with renderMap');

  // Set up viewport change listeners for progressive loading - MUST be in renderMap()
  if (window.__TM_DEBUG__) console.log('[renderMap] About to call setupMapEventListeners');
  setupMapEventListeners();
  if (window.__TM_DEBUG__) console.log('[renderMap] setupMapEventListeners call completed');
}

/**
 * Refresh heatmap data with specified time range
 */
function refreshHeatmapData(days) {
  if (!window.popularAreasHeatmap) {
    if (window.__TM_DEBUG__) console.warn('Heatmap not initialized yet');
    return;
  }

  // Show loading indicator
  if (window.__TM_DEBUG__) console.log(`[refreshHeatmapData] Refreshing heatmap data for ${days} days`);
  const url = `${ENDPOINTS.popularAreas}?days=${days}`;
  
  fetch(url)
    .then(res => { 
      if (!res.ok) throw new Error(`Heatmap fetch failed: ${res.status}`); 
      return res.json(); 
    })
    .then(points => {
      // Convert array format [lat, lng, weight] to LatLng objects with weight for Google Maps
      const heatmapData = points.map(point => ({
        location: new google.maps.LatLng(point[0], point[1]),
        weight: point[2]
      }));
      
      // Update the heatmap data
      window.popularAreasHeatmap.setData(heatmapData);
      
      if (window.__TM_DEBUG__) console.log(`[refreshHeatmapData] ✅ Heatmap updated with ${points.length} data points for ${days} days`);
    })
    .catch(err => {
      console.error(`[refreshHeatmapData] ❌ Failed to refresh heatmap data for ${days} days:`, err);
      // Notify user of error
      const toast = document.createElement('div');
      toast.className = 'toast align-items-center text-white bg-danger border-0';
      toast.setAttribute('role', 'alert');
      toast.setAttribute('aria-live', 'assertive');
      toast.setAttribute('aria-atomic', 'true');
      toast.innerHTML = `
        <div class="d-flex">
          <div class="toast-body">
            Failed to refresh heatmap data. Please try again.
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
      if (window.__TM_DEBUG__) console.log('Loaded individual popularity data for', data.length, 'locations');
    })
    .catch(err => { if (window.__TM_DEBUG__) console.error('Error fetching individual popularity data:', err); window.individualPopularityData = []; });

  // Helper: wire an Autocomplete with a session token lifecycle and details fallback
  function setupAutocompleteWithSession(inputEl) {
    if (!inputEl) return null;
    let sessionToken = null;
    const autocomplete = new google.maps.places.Autocomplete(inputEl, {
      fields: ['place_id','geometry'],
      types: ['establishment'],
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
          if (status === google.maps.places.PlacesServiceStatus.OK && res && res.geometry) { applyPlace(res); }
          else { if (window.__TM_DEBUG__) console.warn('Places getDetails failed:', status); }
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
  } else { if (window.__TM_DEBUG__) console.warn('Search input for autocomplete not found.'); }

  // Also initialize the places_search input if it exists
  const placesSearchInput = document.getElementById('places_search');
  if (placesSearchInput) {
    setupAutocompleteWithSession(placesSearchInput);
  }

  // On idle: filters & track map - OPTIMIZED to prevent excessive calls
  let idleTimer;
  window.map.addListener('idle', () => {
    // Debounce idle events to prevent excessive filtering
    clearTimeout(idleTimer);
    idleTimer = setTimeout(() => {
      // Only apply filters if they haven't been applied recently
      if (!window.filtersAppliedRecently) {
        window.applyFilters();
        window.filtersAppliedRecently = true;
        // Reset flag after a delay
        setTimeout(() => { window.filtersAppliedRecently = false; }, DEBOUNCE_TIMINGS.FLAG_RESET);
      }
      
      const c = window.map.getCenter();
      fetch(ENDPOINTS.trackMap, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ lat: c.lat(), lng: c.lng(), zoom: window.map.getZoom() })
      }).catch(console.error);
    }, DEBOUNCE_TIMINGS.UI_UPDATE); // Use constant for consistent timing
  });

  // Track if map is currently auto-panning
  window.isAutoPanning = false;
  window.autoPanTimeout = null;
  
  // Track map readiness to ensure auto-pan works from the start
  window.mapReady = false;
  
  // Multiple events to ensure map is ready
  window.map.addListener('tilesloaded', () => {
    window.mapReady = true;
    console.log('🗺️ Map tiles loaded - auto-pan should now work');
  });
  
  window.map.addListener('idle', () => {
    window.mapReady = true;
    console.log('🗺️ Map idle - auto-pan should now work');
  });
  
  // Fallback: set ready after a short delay regardless
  setTimeout(() => {
    window.mapReady = true;
    console.log('🗺️ Map ready fallback - auto-pan should now work');
  }, 1000);
  
  // Test debugging is working
  console.log('🔧 Debugging initialized - map click handler should work');

  // Track when info window was last opened to prevent immediate closure
  window.infoWindowOpenedAt = 0;
  window.mapClickDisabled = false;
  
  // Close infoWindow on map click - BUT NOT on drag or other map movements
  window.map.addListener('click', (event) => {
    const now = Date.now();
    const timeSinceInfoWindowOpened = now - window.infoWindowOpenedAt;
    
    // Only close info window if it's a genuine click, not a drag end, and enough time has passed
    if (!window.isDragging && !window.isAutoPanning && !window.mapClickDisabled && timeSinceInfoWindowOpened > 300) {
      // Add a short delay to prevent closing during auto-pan
      setTimeout(() => {
        // Triple-check that we're not in a drag state, auto-panning, and info window is still open
        if (!window.isDragging && !window.isAutoPanning && !window.mapClickDisabled && window.infoWindow && window.currentOpenMarker) {
          window.infoWindow.close();
          window.currentOpenMarker = null;
          // Remove has-active-infowindow class from legend when infowindow is closed
          const legend = document.getElementById('legend');
          if (legend) legend.classList.remove('has-active-infowindow');
        }
      }, 100); // Very short delay
    }
  });

  // Track dragging state to prevent info window closure during drag
  window.isDragging = false;
  window.map.addListener('dragstart', () => {
    console.log('🔄 Drag started - setting isDragging to true');
    window.isDragging = true;
  });
  
  window.map.addListener('dragend', () => {
    console.log('🔄 Drag ended - setting isDragging to false after 100ms delay');
    // Small delay to prevent immediate closure after drag
    setTimeout(() => {
      window.isDragging = false;
    }, 100);
  });

  // Initialize marker manager and data service
  markerManager = new MarkerManager(window.map);
  dataService = new DataService();
  
  // Expose markerManager globally for Personal Notes functionality
  window.markerManager = markerManager;
  
  // Initialize loading overlay
  initLoadingOverlay();
  if (window.__TM_DEBUG__) console.log('[map-init] loading overlay initialized');

  // Initialize UI components (legend, search, filters)
    if (window.__TM_DEBUG__) console.log('[map-init] About to check/call window.initUI');
  if (window.initUI) {
    if (window.__TM_DEBUG__) console.log('[map-init] window.initUI found, calling it');
    window.initUI();
    if (window.__TM_DEBUG__) console.log('[map-init] window.initUI called');
  } else {
    console.error('[map-init] window.initUI not found');
  }
  
      // Set up filter controls to wire up checkbox event listeners
    if (window.__TM_DEBUG__) {
        if (window.__TM_DEBUG__) console.log('Setting up filter controls...');
    }
  setupFilterControls();
  if (window.__TM_DEBUG__) console.log('[map-init] setupFilterControls called');
  
  if (window.__TM_DEBUG__) {
        if (window.__TM_DEBUG__) console.log('Filter controls setup complete');
    }
    
  if (window.__TM_DEBUG__) console.log('[renderMap] Reached end of renderMap function, about to setup event listeners');

  
  // Set up proper stacking immediately and on idle
  setupMapStacking();

  // Set up viewport change listeners for progressive loading
  if (window.__TM_DEBUG__) console.log('[renderMap] About to call setupMapEventListeners');
  setupMapEventListeners();
  if (window.__TM_DEBUG__) console.log('[renderMap] setupMapEventListeners call completed');

  // Early data load with safe fallback bounds (do not wait on timers)
  try {
    const b = dataService.getMapBounds(window.map);
    const fb = b || { north: window.userCoords.lat + 0.25, south: window.userCoords.lat - 0.25, east: window.userCoords.lng + 0.25, west: window.userCoords.lng - 0.25 };
    if (window.__TM_DEBUG__) console.log('[map-init] Early data load with bounds:', b || fb);
    loadOptimizedMapData();
  } catch (e) {
    if (window.__TM_DEBUG__) console.warn('[map-init] Early data load failed to start:', e);
  }

  // Wait for map to be properly initialized before loading data
  // Use a more reliable approach than the 'idle' event
  setTimeout(() => {
    // Ensure map is properly centered and zoomed before loading data
    if (window.userCoords && window.map) {
      if (window.__TM_DEBUG__) {
        if (window.__TM_DEBUG__) console.log('Initializing map with user coordinates:', window.userCoords);
      }
      
      // Center the map on user location (keep default zoom from MAP_SETTINGS)
      window.map.setCenter(window.userCoords);
      // Don't change zoom - let it stay at the default from MAP_SETTINGS
      
      if (window.__TM_DEBUG__) {
        if (window.__TM_DEBUG__) console.log('Map centered and zoomed, waiting for settlement...');
      }
      
      // Wait for the map to settle and get proper bounds, then load data
      setTimeout(() => {
        if (!window.dataLoaded) {
          // Get the actual map bounds after it has settled
          const actualBounds = dataService.getMapBounds(window.map);
          if (window.__TM_DEBUG__) {
            if (window.__TM_DEBUG__) console.log('Map settled, actual bounds:', actualBounds);
          }
          
          // If bounds are still not available, use a fallback approach
          if (!actualBounds) {
            if (window.__TM_DEBUG__) console.warn('Map bounds not available, using fallback bounds around user location');
            const fallbackBounds = {
              north: window.userCoords.lat + 0.1,
              south: window.userCoords.lat - 0.1,
              east: window.userCoords.lng + 0.1,
              west: window.userCoords.lng - 0.1
            };
            if (window.__TM_DEBUG__) {
              if (window.__TM_DEBUG__) console.log('Using fallback bounds:', fallbackBounds);
            }
            // Temporarily override getMapBounds to return fallback bounds
            const originalGetMapBounds = dataService.getMapBounds;
            dataService.getMapBounds = () => fallbackBounds;
            loadOptimizedMapData();
            // Restore original function after loading
            setTimeout(() => {
              dataService.getMapBounds = originalGetMapBounds;
            }, 1000);
          } else {
            window.dataLoaded = true;
            loadOptimizedMapData();
          }
        }
      }, 1000); // Increased wait time to ensure map is fully settled
    }
  }, 1500); // Increased initial wait time
  

}

// Expose for map-ui slider handler
window.refreshHeatmapData = refreshHeatmapData;

/**
 * Load optimized map data using the new system
 */
async function loadOptimizedMapData() {
  try {
    if (window.__TM_DEBUG__) console.log('[map-init] loadOptimizedMapData start');
    showLoadingOverlay();
    
    // Get initial viewport bounds for filtering
    const bounds = dataService.getMapBounds(window.map);
    
    if (window.__TM_DEBUG__) console.log('[map-init] Loading map data with bounds:', bounds);
    
    // Ensure we have bounds; if not, synthesize fallback around user coords
    let effectiveBounds = bounds;
    if (!effectiveBounds) {
      const uc = window.userCoords || DEFAULT_COORDS;
      effectiveBounds = {
        north: uc.lat + 0.25,
        south: uc.lat - 0.25,
        east:  uc.lng + 0.25,
        west:  uc.lng - 0.25
      };
      if (window.__TM_DEBUG__) console.warn('[map-init] No bounds yet; using fallback:', effectiveBounds);
    }
    

    
    // Load combined data in a single request
    if (window.__TM_DEBUG__) console.log('[map-init] Fetching map data with bounds:', effectiveBounds);
    let mapData = await dataService.loadMapData(effectiveBounds, {
      includeEvents: true,
      daysAhead: 30
    });
    
    if (window.__TM_DEBUG__) console.log('[map-init] Received map data counts:', {
      retailers: mapData && mapData.retailers ? mapData.retailers.length : -1,
      events: mapData && mapData.events ? mapData.events.length : -1
    });

    // Fallback: if zero results, try without bounds once
    if ((!mapData.retailers || mapData.retailers.length === 0) && (!mapData.events || mapData.events.length === 0)) {
      if (window.__TM_DEBUG__) console.warn('[map-init] Empty map-data within bounds; retrying without bounds');
      mapData = await dataService.loadMapData(null, { includeEvents: true, daysAhead: 30, forceRefresh: true });
      if (window.__TM_DEBUG__) console.log('[map-init] Fallback map-data counts:', {
        retailers: mapData && mapData.retailers ? mapData.retailers.length : -1,
        events: mapData && mapData.events ? mapData.events.length : -1
      });
    }
    

    
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
    

    
    // Markers are already visible from the loadRetailers/loadEvents calls
    // No need to apply filters again - just update viewport tracking
    // Track the viewport we actually used to fetch
    dataService.updateLastViewport(effectiveBounds);
    
    hideLoadingOverlay();
    
    // Sync slider visibility after everything is loaded
    setTimeout(() => {
      if (window.syncSliderVisibility) {
        window.syncSliderVisibility();
      }
    }, 200); // Small delay to ensure everything is rendered
    
    // Show performance stats in console

    
  } catch (error) {
    console.error('Error loading optimized map data:', error);
    hideLoadingOverlay();
    showErrorMessage('Failed to load map data. Please refresh the page.');
    
    // No fallback - new system should handle all cases
    // If this fails, user should refresh the page
  }
}



// After creating the map, set up proper stacking context - only run once
function setupMapStacking() {
  // Force legend to have lower z-index
  const legend = document.getElementById('legend');
  if (legend) {
    legend.style.zIndex = '1';
  }
  
  // Set z-indices only once, not on every idle event
  setTimeout(() => {
    // Set info window z-index without being overly aggressive
    const infoWindows = document.querySelectorAll('.gm-style-iw-c, .gm-style-iw-t, .gm-style-iw-a');
    infoWindows.forEach(iw => {
      if (!iw.style.zIndex || iw.style.zIndex === 'auto') {
        iw.style.zIndex = '9000';
      }
    });
    
    // Fix close buttons without being overly aggressive
    const closeButtons = document.querySelectorAll('button.gm-ui-hover-effect');
    closeButtons.forEach(btn => {
      if (!btn.style.zIndex || btn.style.zIndex === 'auto') {
        btn.style.zIndex = '9001';
      }
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
    if (window.__TM_DEBUG__) console.log('[setupMapEventListeners] Setting up map idle listener');
    if (window.__TM_DEBUG__) console.log('[setupMapEventListeners] window.map exists:', !!window.map);
    if (!window.map) {
        console.error('[setupMapEventListeners] ERROR: window.map is not defined!');
        return;
    }
    // REMOVED duplicate bounds_changed listener - marker manager handles this
    // Only handle idle events for data loading, not marker updates
    
    // Idle event for loading new data when user stops moving (debounced)
    let idleDebounceTimer;
    window.map.addListener('idle', () => {
        if (window.__TM_DEBUG__) console.log('[map idle event] Map idle event fired, starting debounce timer');
        clearTimeout(idleDebounceTimer);
        idleDebounceTimer = setTimeout(() => {
            if (window.__TM_DEBUG__) console.log('[map idle event] Debounce timer expired, calling handleMapIdle');
            handleMapIdle();
        }, 300); // 300ms debounce for map idle
    });
    if (window.__TM_DEBUG__) console.log('[setupMapEventListeners] Map idle listener setup complete');
}

/**
 * Handle map idle: intelligently load data for new areas
 */
async function handleMapIdle() {
  const bounds = dataService.getMapBounds(window.map);
  if (!bounds) return;

  // Only fetch if viewport really changed significantly
  const hasChanged = dataService.hasViewportChanged(bounds, 0.02);
  if (window.__TM_DEBUG__) console.log('[handleMapIdle] called; hasChanged=', hasChanged, 'bounds=', bounds);
  if (!hasChanged) {
    if (window.__TM_DEBUG__) console.log('[handleMapIdle] No significant change, skipping fetch');
    updateMapUI();
    return;
  }

  // If new viewport is smaller AND we have plenty of markers, skip fetch; otherwise allow fetching on expansion
  const currentBounds = dataService.lastViewport;
  if (currentBounds) {
    const latRange = Math.abs(bounds.north - bounds.south);
    const lngRange = Math.abs(bounds.east - bounds.west);
    const currentLatRange = Math.abs(currentBounds.north - currentBounds.south);
    const currentLngRange = Math.abs(currentBounds.east - currentBounds.west);
    const isSmaller = latRange <= currentLatRange && lngRange <= currentLngRange;
    if (window.__TM_DEBUG__) console.log('[handleMapIdle] Viewport comparison:', {
      isSmaller, 
      latRange, currentLatRange, 
      lngRange, currentLngRange,
      markerCacheSize: markerManager.markerCache.size
    });
    if (isSmaller && markerManager.markerCache.size > 200) {
      if (window.__TM_DEBUG__) console.log('[handleMapIdle] Skipping fetch - viewport smaller and enough markers');
      updateMapUI();
      return;
    }
  }

  // Only load new data if we don't have it already
  try {
    if (window.__TM_DEBUG__) console.log('[handleMapIdle] Proceeding with data fetch for expanded viewport');
    const daysAhead = parseInt(document.getElementById('event-days-slider')?.value, 10) || 30;

    // Fetch fresh data for the new viewport
    const mapData = await dataService.loadMapData(bounds, {
      includeEvents: true,
      daysAhead,
    });

    // Only add new markers, don't replace existing ones
    if (mapData.retailers && mapData.retailers.length > 0) {
      await markerManager.loadRetailers(mapData.retailers, true); // append = true
    }
    if (mapData.events && mapData.events.length > 0) {
      await markerManager.loadEvents(mapData.events, true); // append = true
    }

    // Track viewport for next change detection
    dataService.updateLastViewport(bounds);

    // Update UI without re-applying filters (markers are already visible from loadRetailers/loadEvents)
    updateMapUI();
  } catch (err) {
    console.error('Idle load failed:', err);
  }
}

/**
 * Debounce function to limit the frequency of function calls
 */
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

/**
 * Setup filter controls and bind event listeners
 */
function setupFilterControls() {
    if (window.__TM_DEBUG__) console.log('Setting up filter controls...');
    
    // Get filter elements using the correct IDs from the HTML
    const kioskToggle = document.getElementById('filter-kiosk');
    const retailToggle = document.getElementById('filter-retail');
    const indieToggle = document.getElementById('filter-indie');
    const eventsToggle = document.getElementById('filter-events');
    const openNowToggle = document.getElementById('filter-open-now');
    const newToggle = document.getElementById('filter-new');
    const popularToggle = document.getElementById('filter-popular-areas');
    
    if (window.__TM_DEBUG__) console.log('Filter elements found:', {
        kioskToggle: !!kioskToggle,
        retailToggle: !!retailToggle,
        indieToggle: !!indieToggle,
        eventsToggle: !!eventsToggle,
        openNowToggle: !!openNowToggle,
        newToggle: !!newToggle,
        popularToggle: !!popularToggle
    });
    
    // Debounced filter change handler
    const handleFilterChange = debounce(() => {
        applyFilters();
    }, 100);
    
    // Bind filter events
    if (kioskToggle) kioskToggle.addEventListener('change', handleFilterChange);
    if (retailToggle) retailToggle.addEventListener('change', handleFilterChange);
    if (indieToggle) indieToggle.addEventListener('change', handleFilterChange);
    if (eventsToggle) eventsToggle.addEventListener('change', handleFilterChange);
    if (openNowToggle) openNowToggle.addEventListener('change', handleFilterChange);
    if (newToggle) newToggle.addEventListener('change', handleFilterChange);
    if (popularToggle) popularToggle.addEventListener('change', handleFilterChange);
}

// updateFilterUI is now defined at the top of this file before imports

/**
 * Apply filters using the marker manager
 */
let filterDebounceTimer;
function applyFilters() {
    // Don't apply filters if markers aren't loaded yet
    if (!markerManager || markerManager.markerCache.size === 0) {
        return;
    }
    
    // Debounce filter application to prevent excessive calls
    clearTimeout(filterDebounceTimer);
    filterDebounceTimer = setTimeout(() => {
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

        if (markerManager) {
            // Force immediate update by clearing current filters
            markerManager.currentFilters = null;
            markerManager.applyFilters(filters);
        }

        // Toggle heatmap layer
        if (filters.showPopular) {
            window.popularAreasHeatmap?.setMap(window.map);
        } else {
            window.popularAreasHeatmap?.setMap(null);
        }

        // Update slider UI safely
        (window.updateFilterUI || function(){ })(filters);
    }, DEBOUNCE_TIMINGS.FILTER_APPLY); // Use constant for consistent timing
}

// Loading overlay functions are now imported from loadingOverlay.js

// updateFilterUI moved to top of file before imports

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



// Error handling functions are now imported from errorHandler.js




