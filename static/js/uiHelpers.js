// static/js/uiHelpers.js

/**
 * Parse an ISO date string or formatted date and return "Apr 22, 2025"
 */
export function formatDate(dateString) {
  if (!dateString) return 'TBA';
  
  // Try parsing as ISO string first
  let d = new Date(dateString);
  
  // If that fails, try parsing as formatted date (e.g. "Apr 22, 2025")
  if (isNaN(d.getTime())) {
    d = new Date(dateString.replace(/(\d+)(st|nd|rd|th)/, '$1'));
  }
  
  // If still invalid, return original string
  if (isNaN(d.getTime())) {
    return dateString;
  }
  
  return d.toLocaleDateString(undefined, {
    year:  'numeric',
    month: 'short',
    day:   'numeric',
  });
}

/**
 * Parse an HH:MM:SS or ISO string and return "3:30 PM"
 */
export function formatTime(timeString) {
  if (!timeString) return 'TBA';
  
  try {
    // Handle HH:MM:SS format
    if (timeString.match(/^\d{2}:\d{2}:\d{2}$/)) {
      const [hours, minutes] = timeString.split(':');
      const date = new Date();
      date.setHours(parseInt(hours, 10));
      date.setMinutes(parseInt(minutes, 10));
      return date.toLocaleTimeString(undefined, {
        hour: 'numeric',
        minute: '2-digit',
      });
    }
    
    // Handle ISO format (with T)
    if (timeString.includes('T')) {
      const d = new Date(timeString);
      if (!isNaN(d.getTime())) {
        return d.toLocaleTimeString(undefined, {
          hour: 'numeric',
          minute: '2-digit',
        });
      }
    }
    
    // If all else fails, try parsing with 1970-01-01
    const d = new Date(`1970-01-01T${timeString}`);
    if (!isNaN(d.getTime())) {
      return d.toLocaleTimeString(undefined, {
        hour: 'numeric',
        minute: '2-digit',
      });
    }
  } catch (e) {
    // Silently fall back to original string
  }
  
  return timeString; // Return original if parsing fails
}

/**
 * Wrap the inner HTML in a styled info-window container.
 */
function wrapInfoWindow(innerHtml, iconUrl, titleText, titleSize = 26) {
  return `
    <div class="info-window" style="padding:10px; font-family:Arial, sans-serif; font-size:14px;">
      <div style="display:flex;align-items:center; margin-bottom:12px;">
        <img src="${iconUrl}" alt="" style="width:40px; height:40px; margin-right:12px;" />
        <h4 style="margin:0; font-size:${titleSize}px;">${titleText}</h4>
      </div>
      ${innerHtml}
    </div>
  `;
}

/**
 * Generate the display string for retailer type and machine count.
 */
function displayType(retailer, isPro) {
  const typeRaw = (retailer.retailer_type || 'N/A').toLowerCase().trim();
  const parts = typeRaw.split('+').map(t => t.trim()).filter(Boolean);
  const hasStore = parts.some(p => p === 'store' || p === 'retail');
  // Prefer aggregated kiosk_count if provided by marker layer; fallback to machine_count
  const kioskCount = (Number.isFinite(retailer.kiosk_count) ? retailer.kiosk_count : (retailer.machine_count || 0));

  // Singular cases
  if (parts.length === 1) {
    const t = parts[0];
    if (t === 'kiosk') {
      if (!isPro) return 'Kiosk (Pro Only)';
      const label = kioskCount === 1 ? '1 Kiosk' : `${kioskCount} Kiosks`;
      return label;
    }
    if (t === 'store' || t === 'retail') return 'Retail Store';
    if (t === 'card shop') return 'Indie Store';
    return retailer.retailer_type || 'N/A';
  }

  // Combined cases like "store + kiosk"
  if (hasStore && parts.some(p => p === 'kiosk')) {
    const label = kioskCount === 1 ? 'Kiosk' : 'Kiosks';
    return `Store + ${kioskCount} ${label}`;
  }

  // Fallback to original
  return retailer.retailer_type || 'N/A';
}

/**
 * Generate HTML for a retailer info window.
 */
export function renderRetailerInfoWindow(retailer, isPro) {
  const slice50     = s => (s || '').length > 50 ? s.slice(0, 50) + '…' : (s || '');
  const slice35     = s => (s || '').length > 35 ? s.slice(0, 35) + '…' : (s || '');
  const titleText   = slice50(retailer.retailer || 'Retailer');
  const addressText = slice50(retailer.full_address || 'N/A');
  const phoneRaw    = retailer.phone_number || '';
  const phoneText   = slice50(phoneRaw);
  const websiteRaw  = retailer.website || '';
  const websiteText = slice35(websiteRaw);

  // Determine pin icon
  const custom = typeof window.getPinColor === 'function'
    ? window.getPinColor(retailer)
    : 'default.png';
  const iconUrl = isPro
    ? `/static/map-pins/${custom}`
    : '/static/map-pins/free.png';

  // Phone section
  const phoneSection = isPro
    ? `<p style="margin:8px 0; font-size:14px;"><a href=\"tel:${phoneRaw}\">${phoneText}</a></p>`
    : `<p style="margin:8px 0; font-size:14px;">Phone (Pro Only)</p>`;

  // Website section
  const websiteSection = isPro
    ? `<p style="margin:8px 0; font-size:14px;"><a href=\"${websiteRaw}\" target=\"_blank\">${websiteText}</a></p>`
    : `<p style="margin:8px 0; font-size:14px;">Website (Pro Only)</p>`;

  // Hours section
  let hoursSection = '';
  if (isPro && typeof window.formatHours === 'function') {
    const lines = window.formatHours(retailer.opening_hours || 'N/A')
      .split('</div>').filter(Boolean)
      .map(line => line.replace(/<div[^>]*>/, '') + '</div>');
    hoursSection = `<div style="margin:8px 0;">${lines.map(line =>
      `<div style=\"display:flex;justify-content:space-between; font-size:14px; margin:2px 0;\">` +
        line.replace(/<\/div>/, '') +
      `</div>`
    ).join('')}</div>`;
  } else {
    hoursSection = `<p style="margin:8px 0; font-size:14px;">Hours (Pro Only)</p>`;
  }

  const reportLink = `<p style=\"margin-top:12px; font-size:12px;\">` +
    `<a href=\"/correct-location?address=${encodeURIComponent(retailer.full_address || '')}` +
      `&phone=${encodeURIComponent(phoneRaw)}&website=${encodeURIComponent(websiteRaw)}` +
      `&hours=${encodeURIComponent(retailer.opening_hours || '')}\">Correct Data</a></p>`;

  // User Notes Section (Pro only)
  const notesSection = isPro ? 
    (retailer.user_notes ? 
      `<div style="margin-top:12px; padding:8px; background:#f8f9fa; border-radius:4px; border-left:3px solid #007bff;">
        <p style="margin:0 0 4px 0; font-size:12px; font-weight:bold; color:#007bff;">Your Notes:</p>
        <p style="margin:0; font-size:12px; color:#333;">${retailer.user_notes}</p>
        <button onclick="editNote(${retailer.id})" style="margin-top:4px; padding:2px 6px; font-size:10px; background:#007bff; color:white; border:none; border-radius:2px; cursor:pointer;">Edit</button>
      </div>` : 
      `<div style="margin-top:12px; font-size:12px;">
        <button onclick="addNote(${retailer.id})" style="padding:4px 8px; font-size:10px; background:#28a745; color:white; border:none; border-radius:2px; cursor:pointer;">Add Note</button>
      </div>`) :
    `<div style="margin-top:12px; padding:8px; background:#f8f9fa; border-radius:4px; border-left:3px solid #ffc107;">
      <p style="margin:0 0 4px 0; font-size:12px; font-weight:bold; color:#ffc107;">Personal Notes (Pro)</p>
      <p style="margin:0; font-size:12px; color:#666;">Track your hunting success with private notes</p>
      <button onclick="showProUpgradeToast()" style="margin-top:4px; padding:2px 6px; font-size:10px; background:#ffc107; color:#000; border:none; border-radius:2px; cursor:pointer;">Upgrade to Pro</button>
    </div>`;

  const inner = `
    <p style="margin:8px 0; font-size:16px;">${displayType(retailer, isPro)}</p>
    <p style="margin:8px 0; line-height:1.2; font-size:14px;"><a href=\"https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(retailer.full_address || '')}\" target=\"_blank\">${addressText}</a></p>
    ${phoneSection}
    ${websiteSection}
    ${hoursSection}
    ${notesSection}
    ${reportLink}
  `;

  return wrapInfoWindow(inner, iconUrl, titleText, 26);
}

/**
 * Generate HTML for an event info window.
 */
export function renderEventInfoWindow(evt) {
  const slice50     = s => (s || '').length > 50 ? s.slice(0, 50) + '…' : (s || '');
  const titleText   = slice50(evt.event_title);
  const addressText = slice50(evt.full_address);
  const dateText    = formatDate(evt.start_date);
  const timeText    = formatTime(evt.start_time);

  const inner = `
    <p style="margin:8px 0; font-size:16px;">Event</p>
    <p style="margin:8px 0; font-size:14px;"><strong>Date:</strong> ${dateText}</p>
    <p style="margin:8px 0; font-size:14px;"><strong>Time:</strong> ${timeText}</p>
    <p style="margin:8px 0;"><a href=\"https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(evt.full_address)}\" target=\"_blank\" style=\"font-size:14px;\">${addressText}</a></p>
  `;

  return wrapInfoWindow(inner, '/static/map-pins/event.png', titleText, 18);
}

// User Notes Management Functions
window.addNote = function(retailerId) {
  // Check if user is Pro
  const proSection = document.getElementById('pro-section');
  const isPro = proSection ? proSection.getAttribute('data-is-pro') === 'true' : false;
  
  if (!isPro) {
    showProUpgradeToast();
    return;
  }
  
  const notes = prompt('Add your notes for this location:');
  if (notes !== null) {
    saveUserNote(retailerId, notes);
  }
};

window.editNote = function(retailerId) {
  // Check if user is Pro
  const proSection = document.getElementById('pro-section');
  const isPro = proSection ? proSection.getAttribute('data-is-pro') === 'true' : false;
  
  if (!isPro) {
    showProUpgradeToast();
    return;
  }
  
  // First get the current note
  fetch(`/api/user-notes/${retailerId}`)
    .then(response => {
      if (response.status === 403) {
        showProUpgradeToast();
        return;
      }
      return response.json();
    })
    .then(data => {
      if (data) {
        const notes = prompt('Edit your notes for this location:', data.notes || '');
        if (notes !== null) {
          saveUserNote(retailerId, notes);
        }
      }
    })
    .catch(error => {
      console.error('Error fetching note:', error);
      alert('Error loading note. Please try again.');
    });
};

function saveUserNote(retailerId, notes) {
  fetch(`/api/user-notes/${retailerId}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ notes: notes })
  })
  .then(response => {
    if (response.status === 403) {
      showProUpgradeToast();
      return;
    }
    return response.json();
  })
  .then(data => {
    if (data && data.error) {
      alert('Error saving note: ' + data.error);
    } else if (data) {
      // Refresh the map to show updated notes
      if (window.refreshMap) {
        window.refreshMap();
      }
    }
  })
  .catch(error => {
    console.error('Error saving note:', error);
    alert('Error saving note. Please try again.');
  });
}
