// ==== static/js/markerFactory.js ====
import { MARKER_TYPES } from './config.js';
import { renderRetailerInfoWindow, renderEventInfoWindow } from './uiHelpers.js';

// Fetch user notes and show popup
function fetchUserNotesAndShowPopup(marker, retailer, isPro) {
  const base = marker.retailer_data ? { ...marker.retailer_data } : { ...retailer };
  
  // If user is not Pro, show popup without notes
  if (!isPro) {
    const html = renderRetailerInfoWindow({
      ...base,
      kiosk_count: (marker.kiosk_count ?? base.kiosk_current_count ?? base.kiosk_count ?? base.machine_count),
      machine_count: (base.machine_count)
    }, isPro);
    
    window.currentOpenMarker = marker;
    window.infoWindow.setContent(html);
    window.infoWindow.open(marker.getMap(), marker);
    handleInfoWindowOpen();
    return;
  }
  
  // Fetch user notes for Pro users
  fetch(`/api/user-notes/${retailer.id}`)
    .then(response => {
      if (response.status === 403) {
        // User is not Pro, show popup without notes
        const html = renderRetailerInfoWindow({
          ...base,
          kiosk_count: (marker.kiosk_count ?? base.kiosk_current_count ?? base.kiosk_count ?? base.machine_count),
          machine_count: (base.machine_count)
        }, false);
        
        window.currentOpenMarker = marker;
        window.infoWindow.setContent(html);
        window.infoWindow.open(marker.getMap(), marker);
        handleInfoWindowOpen();
        return;
      }
      
      if (!response.ok) {
        throw new Error('Failed to fetch notes');
      }
      
      return response.json();
    })
    .then(data => {
      // Add user notes to retailer data
      const retailerWithNotes = {
        ...base,
        kiosk_count: (marker.kiosk_count ?? base.kiosk_current_count ?? base.kiosk_count ?? base.machine_count),
        machine_count: (base.machine_count),
        user_notes: data.notes || null
      };
      
      // Add note decorator if notes exist
      if (data.notes && data.notes.trim().length > 0) {
        addNoteDecorator(marker, retailerWithNotes);
      }
      
      const html = renderRetailerInfoWindow(retailerWithNotes, isPro);
      
      window.currentOpenMarker = marker;
      window.infoWindow.setContent(html);
      window.infoWindow.open(marker.getMap(), marker);
      handleInfoWindowOpen();
    })
    .catch(error => {
      console.error('Error fetching user notes:', error);
      
      // Show popup without notes on error
      const html = renderRetailerInfoWindow({
        ...base,
        kiosk_count: (marker.kiosk_count ?? base.kiosk_current_count ?? base.kiosk_count ?? base.machine_count),
        machine_count: (base.machine_count)
      }, isPro);
      
      window.currentOpenMarker = marker;
      window.infoWindow.setContent(html);
      window.infoWindow.open(marker.getMap(), marker);
      handleInfoWindowOpen();
    });
}

// Make functions available globally for popup refresh
window.fetchUserNotesAndShowPopup = fetchUserNotesAndShowPopup;
window.addNoteDecorator = addNoteDecorator;
window.createRetailerMarker = createRetailerMarker;

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
  if (window.__TM_DEBUG__) {
    console.log('createRetailerMarker called:', {
      map: !!map,
      retailer: retailer?.retailer || 'unknown',
      coords: retailer?.latitude && retailer?.longitude ? 
        `${retailer.latitude}, ${retailer.longitude}` : 'missing'
    });
  }
  
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

  if (window.__TM_DEBUG__) {
    console.log('Retailer marker created:', {
      marker: !!marker,
      position: marker.getPosition?.(),
      iconUrl
    });
  }

  // Copy fields for filtering
  marker.retailer_type    = (retailer.retailer_type  || '').toLowerCase();
  marker.retailer_name    = (retailer.retailer       || '').toLowerCase();
  marker.retailer_address = (retailer.full_address   || '').toLowerCase();
  marker.retailer_phone   = (retailer.phone_number   || '').toLowerCase();
  // Expose common fields used by the route planner mapping step
  marker.place_id         = retailer.place_id || null;
  marker.address          = retailer.full_address || null;
  marker.phone            = retailer.phone_number || null;
  marker.opening_hours    = retailer.opening_hours;
  marker.status           = retailer.status; // Business logic status (new, updated, etc.)
  marker.enabled          = Boolean(retailer.enabled); // Enabled state: true = enabled, false = disabled
  
  // Copy business hours data for Open Now filtering
  marker.business_hours   = retailer.business_hours || retailer.opening_hours;
  
  // Store the full retailer data for advanced filtering
  marker.retailer_data    = { ...retailer };
  // Pass through counts for UI rendering (kiosk aggregation)
  marker.machine_count    = Number.isFinite(retailer.machine_count) ? retailer.machine_count : 0;
  marker.kiosk_count      = (
    Number.isFinite(retailer.kiosk_current_count) ? retailer.kiosk_current_count :
    (Number.isFinite(retailer.kiosk_count) ? retailer.kiosk_count :
     (Number.isFinite(retailer.machine_count) ? retailer.machine_count : undefined))
  );

  // Delegate HTML to UI helper; use marker.retailer_data to reflect merged updates
  marker.addListener('click', () => {
    if (window.currentOpenMarker === marker) {
      window.infoWindow.close();
      window.currentOpenMarker = null;
      handleInfoWindowClose();
      return;
    }

    if (window.currentOpenMarker) {
      window.infoWindow.close();
    }

    // Fetch user notes before rendering popup
    fetchUserNotesAndShowPopup(marker, retailer, isPro);
    
    fetch('/track/pin', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        marker_id: retailer.place_id || 'unknown',
        place_id: retailer.place_id || undefined,
        lat: parseFloat(retailer.latitude),
        lng: parseFloat(retailer.longitude)
      })
    }).catch(err => { if (window.__TM_DEBUG__) console.error('Error sending pin click data:', err); });
  });

  // Do not auto-bounce on create; preview handles bounce for selected stops only

  return marker;
}

/**
 * Add a subtle note decorator to a marker that has personal notes
 * @param {google.maps.Marker} marker - The marker to decorate
 * @param {object} retailer - The retailer data
 */
function addNoteDecorator(marker, retailer) {
  // Create a larger, more noticeable note icon overlay centered on the pin
  const noteIcon = new google.maps.Marker({
    position: marker.getPosition(),
    map: marker.getMap(),
    icon: {
      url: 'data:image/svg+xml;charset=UTF-8,' + encodeURIComponent(`
        <svg width="32" height="32" viewBox="0 0 32 32" xmlns="http://www.w3.org/2000/svg">
          <circle cx="16" cy="16" r="15" fill="#ff6b35" stroke="#ffffff" stroke-width="4"/>
          <path d="M10 10h12M10 16h8M10 22h6" stroke="#ffffff" stroke-width="3" stroke-linecap="round"/>
        </svg>
      `),
      scaledSize: new google.maps.Size(32, 32),
      anchor: new google.maps.Point(16, 16) // Center the decorator
    },
    zIndex: marker.getZIndex() + 10, // Higher z-index to appear on top
    title: 'Has Personal Notes - Click to edit'
  });
  
  // Position the note icon directly over the pin (no offset)
  const position = marker.getPosition();
  noteIcon.setPosition({
    lat: position.lat(),
    lng: position.lng()
  });
  
  // Store reference to the note icon on the main marker for cleanup
  marker.noteDecorator = noteIcon;
  
  // Add click handler to the note icon
  noteIcon.addListener('click', () => {
    // Trigger the edit note function
    if (window.editNote) {
      window.editNote(retailer.id);
    }
  });
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
