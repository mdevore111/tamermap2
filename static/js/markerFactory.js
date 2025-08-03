// ==== static/js/markerFactory.js ====
import { MARKER_TYPES } from './config.js';
import { renderRetailerInfoWindow, renderEventInfoWindow } from './uiHelpers.js';

// Simplified function to ensure InfoWindow close button is visible
function handleInfoWindowOpen() {
  // Make sure close button is visible
  setTimeout(() => {
    const closeButtons = document.querySelectorAll('button.gm-ui-hover-effect');
    closeButtons.forEach(btn => {
      btn.style.display = 'block';
      btn.style.visibility = 'visible';
      btn.style.opacity = '1';
    });
    
    // Add class to legend - CSS will handle the styling
    const legend = document.getElementById('legend');
    if (legend) {
      legend.classList.add('has-active-infowindow');
    }
  }, 50);
}

// Restore legend when InfoWindow closes
function handleInfoWindowClose() {
  const legend = document.getElementById('legend');
  if (legend) {
    legend.classList.remove('has-active-infowindow');
  }
}

/**
 * Create a Google Maps Marker for a retailer.
 * @param {google.maps.Map} map - The map instance.
 * @param {object} retailer - The retailer data from API.
 * @returns {google.maps.Marker|null} The created marker, or null if coords invalid.
 */
export function createRetailerMarker(map, retailer) {
  const cfg = MARKER_TYPES.retailer;
  const isPro = window.is_pro;
  // choose pin filename
  const pinName = isPro && typeof window.getPinColor === 'function'
    ? window.getPinColor(retailer)
    : cfg.defaultIcon;
  // build URL
  const iconUrl = isPro
    ? `${cfg.iconBase}${pinName}`
    : `${cfg.iconBase}${cfg.freeIcon}`;

  const marker = new google.maps.Marker({
    position: { lat: parseFloat(retailer.latitude), lng: parseFloat(retailer.longitude) },
    map,
    title: retailer.retailer || 'Retailer',
    icon: {
      url: iconUrl,
      scaledSize: new google.maps.Size(cfg.size.width, cfg.size.height),
      anchor: new google.maps.Point(cfg.size.anchor.x, cfg.size.anchor.y)
    },
    zIndex: cfg.zIndex
  });

  // Copy fields for filtering
  marker.retailer_type    = (retailer.retailer_type  || '').toLowerCase();
  marker.retailer_name    = (retailer.retailer       || '').toLowerCase();
  marker.retailer_address = (retailer.full_address   || '').toLowerCase();
  marker.retailer_phone   = (retailer.phone_number   || '').toLowerCase();
  marker.opening_hours    = retailer.opening_hours;
  marker.status           = retailer.status;

  // Delegate HTML to UI helper
  marker.addListener('click', () => {
    const html = renderRetailerInfoWindow(retailer, isPro);

    if (window.currentOpenMarker === marker) {
      window.infoWindow.close();
      window.currentOpenMarker = null;
      handleInfoWindowClose();
      return;
    }

    if (window.currentOpenMarker) {
      window.infoWindow.close();
    }

    window.currentOpenMarker = marker;
    window.infoWindow.setContent(html);
    window.infoWindow.open(map, marker);

    // Ensure InfoWindow is visible with close button
    handleInfoWindowOpen();
    
    fetch('/track/pin', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ marker_id: retailer.place_id || 'unknown', lat: parseFloat(retailer.latitude), lng: parseFloat(retailer.longitude) })
    }).catch(err => console.error('Error sending pin click data:', err));
  });

  // Bounce animation for new locations (non-blank status field)
  if (retailer.status && retailer.status.trim() !== '') {
    marker.setAnimation(google.maps.Animation.BOUNCE);
    setTimeout(() => marker.setAnimation(null), 5000);
  }

  return marker;
}

/** Event marker */
export function createEventMarker(map, evt) {
  const cfg = MARKER_TYPES.event;
  const marker = new google.maps.Marker({
    position: { lat: parseFloat(evt.latitude), lng: parseFloat(evt.longitude) },
    map,
    title: evt.event_title,
    icon: {
      url: cfg.iconUrl,
      scaledSize: new google.maps.Size(cfg.size.width, cfg.size.height),
      anchor: new google.maps.Point(cfg.size.anchor.x, cfg.size.anchor.y)
    },
    zIndex: cfg.zIndex
  });
  
  // Store event data with the marker for filtering
  marker.set('eventData', evt);

  marker.addListener('click', () => {
    const html = renderEventInfoWindow(evt);
    window.infoWindow.setContent(html);
    window.infoWindow.open(map, marker);
    
    // Ensure InfoWindow is visible with close button
    handleInfoWindowOpen();
  });

  return marker;
}
