// static/js/config.js
export const DEFAULT_COORDS = { lat: 32.7157, lng: -117.1611 };

// Only the pure settings (no google.*)
export const MAP_SETTINGS = {
  zoom: 9,
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
  popularAreas: '/api/pin-heatmap-data',   // renamed here
  trackMap:     '/track/map',
  trackPin:     '/track/pin'
};

export const ICON_SIZES = {
  retailer: { width: 40, height: 40, anchor: { x: 20, y: 40 } },
  event:    { width: 40, height: 40, anchor: { x: 15, y: 30 } },
  user:     { scale: 10 }
};

export const Z_INDICES = {
  retailer: 100,
  event:    50,
  ui:       1000
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
