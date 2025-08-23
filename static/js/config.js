// static/js/config.js
export const DEFAULT_COORDS = { lat: 32.7157, lng: -117.1611 };

// Only the pure settings (no google.*)
export const MAP_SETTINGS = {
  zoom: 11,
  minZoom: 7,
  maxZoom: 18,
  gestureHandling: "greedy",
  disableDefaultUI: true,
  zoomControl: true
};

// Named constants that we’ll turn into google.* at runtime
export const MAP_TYPE_ID         = 'ROADMAP';  // will use google.maps.MapTypeId[MAP_TYPE_ID]
export const ZOOM_CONTROL_STYLE = 'SMALL';    // will use google.maps.ZoomControlStyle[ZOOM_CONTROL_STYLE]

// Endpoints, icon sizes, and z‑indices stay the same
export const ENDPOINTS = {
  retailers:    '/api/retailers',
  events:       '/api/events',
  heatmap1:     '/api/heatmap-data',
  popularAreas: '/api/pin-heatmap-data',   // for heatmap display (rounded coordinates)
  individualPopularity: '/api/individual-popularity-data', // for routing (full precision)
  trackMap:     '/track/map',
  trackPin:     '/track/pin',
  routeOptimize: '/api/route-optimize'
};

export const ICON_SIZES = {
  retailer: { width: 48, height: 48, anchor: { x: 24, y: 48 } },
  event:    { width: 44, height: 44, anchor: { x: 16, y: 33 } },
  user:     { scale: 12 }
};

export const Z_INDICES = {
  retailer: 100,
  event:    50,
  ui:       1000
};

// Debounce timing constants for consistent event handling
export const DEBOUNCE_TIMINGS = {
  VIEWPORT_CHANGE: 500,    // Map bounds/zoom changes (marker updates)
  UI_UPDATE: 100,          // UI updates and filter changes
  FILTER_APPLY: 10,        // Filter application (very responsive)
  FLAG_RESET: 1000         // Reset flags and state
};

// New: centralize per‑type icon & z‑index info
export const MARKER_TYPES = {
  retailer: {
    iconBase: '/static/map-pins/',
    defaultIcon: 'default.png',
    freeIcon:    'free.png',
    size:        ICON_SIZES.retailer,
    zIndex:      Z_INDICES.retailer
  },
  event: {
    iconUrl: '/static/map-pins/event.png',
    size:     ICON_SIZES.event,
    zIndex:   Z_INDICES.event
  }
};
