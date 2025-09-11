// static/js/filterService.js

/**
 * Filters markers on the map based on viewport bounds and UI controls.
 * @param {google.maps.Map} map - The Google Map instance.
 * @param {google.maps.Marker[]} markers - Array of markers to filter.
 * @param {Object} domCache - Cached DOM elements for filter controls.
 * @param {Function} isOpenNow - Function(openingHoursStr) ⇒ boolean, to test "Open Now".
 */
// Comment out legacy filtering functions
// export function filterMarkersViewport(map, markers, domCache, isOpenNow) {
//   if (!map || !Array.isArray(markers) || markers.length === 0) return;
//   const bounds = map.getBounds();
//   if (!bounds) return;
//
//   // Read filter settings
//   const showKiosk    = domCache.filterKiosk?.checked ?? true;
//   const showRetail   = domCache.filterRetail?.checked ?? true;
//   const showIndie    = domCache.filterIndie?.checked ?? true;
//   const showNew      = domCache.filterNew?.checked ?? false;
//   const showOpenNow  = domCache.filterOpenNow?.checked ?? false;
//   const searchText   = (domCache.legendFilter?.value || '').trim().toLowerCase();
//
//   // Debug logging for filter states
//   console.log('Filter states:', {
//     showKiosk,
//     showRetail,
//     showIndie,
//     showNew,
//     showOpenNow,
//     searchText
//   });
//
//   markers.forEach(marker => {
//     const position    = marker.getPosition();
//     const inBounds    = bounds.contains(position);
//     let shouldDisplay = inBounds;
//
//     if (shouldDisplay) {
//       const type        = marker.retailer_type || '';
//       
//       // Debug logging to see what types we have
//       if (type && !window.typeDebugLogged) {
//         console.log('Retailer types found:', type);
//         window.typeDebugLogged = true;
//       }
//       
//       // Debug logging to see retailer names for categorization
//       if (marker.retailer_name && !window.nameDebugLogged) {
//         console.log('Sample retailer names:', marker.retailer_name);
//         window.nameDebugLogged = true;
//       }
//       
//       // Case-insensitive matching for database types: 'kiosk', 'Card Shop', 'Store'
//       const typeLower = type.toLowerCase();
//       const matchesType =
//         (typeLower === 'kiosk' && showKiosk) ||
//         (typeLower === 'store' && showRetail) ||
//         (typeLower === 'card shop' && showIndie);
//
//       const matchesSearch = !searchText || [
//         marker.retailer_name,
//         marker.retailer_address,
//         marker.retailer_phone,
//         marker.retailer_type
//       ].some(field => (field || '').includes(searchText));
//
//       const matchesNew     = !showNew || Boolean(marker.status?.trim());
//       const matchesOpen    = !showOpenNow || isOpenNow(marker.opening_hours);
//
//       shouldDisplay = matchesType && matchesSearch && matchesNew && matchesOpen;
//     }
//
//     // Show or hide marker
//     marker.setMap(shouldDisplay ? map : null);
//   });
// }

/**
 * Shows or hides event markers based on the "Events" checkbox and slider value.
 * @param {google.maps.Map} map
 * @param {google.maps.Marker[]} eventMarkers
 * @param {object} domCache
 */
// Comment out legacy filtering functions
// export function filterEventMarkers(map, eventMarkers, domCache) {
//   if (!map || !Array.isArray(eventMarkers)) return;
//   
//   const showEvents = domCache.filterEvents?.checked ?? false;
//   
//   // If events are turned off entirely, hide all markers
//   if (!showEvents) {
//     eventMarkers.forEach(marker => {
//       marker.setMap(null);
//     });
//     return;
//   }
//   
//   // Get the event date range from the slider
//   const maxDays = parseInt(domCache.eventDaysSlider?.value || '30');
//   
//   // Apply filtering for each marker based on its date
//   eventMarkers.forEach(marker => {
//     // Each marker has event data attached to it when created
//     const eventData = marker.get('eventData');
//     
//     if (eventData && eventData.start_date) {
//       const now = new Date();
//       const start = new Date(eventData.start_date);
//       const days = (start - now) / (1000 * 60 * 60 * 24);
//       
//       // Show only if within the selected day range
//       marker.setMap((days >= 0 && days <= maxDays) ? map : null);
//     } else {
//       // If we can't determine the date, default to showing it
//       marker.setMap(map);
//     }
//   });
// }
