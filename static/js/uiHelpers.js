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
function wrapInfoWindow(innerHtml, iconUrl, titleText, titleSize = 21) {
  return `
    <div class="info-window" style="padding:6px 8px; font-family:Arial, sans-serif;">
      <div class="iw-header" style="display:flex;align-items:center; margin:0 0 6px; gap:8px;">
        <img class="iw-icon" src="${iconUrl}" alt="" style="width:30px; height:30px;" />
        <h4 class="iw-title" style="margin:0; font-size:${titleSize}px; line-height:1.12;">${titleText}</h4>
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
      if (!isPro) return 'Kiosk (Count available with Pro)';
      const label = kioskCount === 1 ? '1 Kiosk' : `${kioskCount} Kiosks`;
      return label;
    }
    if (t === 'store' || t === 'retail') return 'Retail Store';
    if (t === 'card shop') return 'Indie Store';
    return retailer.retailer_type || 'N/A';
  }

  // Combined cases like "store + kiosk"
  if (hasStore && parts.some(p => p === 'kiosk')) {
    if (!isPro) return 'Store + Kiosk (Count available with Pro)';
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
    ? `<p style="margin:6px 0; font-size:14px;"><a href=\"tel:${phoneRaw}\">${phoneText}</a></p>`
    : `<p style="margin:6px 0; font-size:14px;">Phone (Pro Only)</p>`;

  // Website section
  const websiteSection = isPro
    ? `<p style="margin:6px 0; font-size:14px;"><a href=\"${websiteRaw}\" target=\"_blank\">${websiteText}</a></p>`
    : `<p style="margin:6px 0; font-size:14px;">Website (Pro Only)</p>`;

  // Hours section
  let hoursSection = '';
  if (isPro && typeof window.formatHours === 'function') {
    const lines = window.formatHours(retailer.opening_hours || 'N/A')
      .split('</div>').filter(Boolean)
      .map(line => line.replace(/<div[^>]*>/, '') + '</div>');
    hoursSection = `<div style="margin:6px 0;">${lines.map(line =>
      `<div style=\"display:flex;justify-content:space-between; font-size:14px; margin:2px 0;\">` +
        line.replace(/<\/div>/, '') +
      `</div>`
    ).join('')}</div>`;
  } else {
    hoursSection = `<p style="margin:6px 0; font-size:14px;">Hours (Pro Only)</p>`;
  }

  const reportLink = `<p style=\"margin-top:12px; font-size:12px;\">` +
    `<a href=\"/correct-location?address=${encodeURIComponent(retailer.full_address || '')}` +
      `&phone=${encodeURIComponent(phoneRaw)}&website=${encodeURIComponent(websiteRaw)}` +
      `&hours=${encodeURIComponent(retailer.opening_hours || '')}\">Correct Data</a></p>`;

  // User Notes Section (Pro only)
  const notesSection = isPro ? 
    (retailer.user_notes ? 
      `<div style="margin-top:8px; padding:8px; background:#f8f9fa; border-radius:4px; border-left:3px solid #007bff;">
        <p style="margin:0 0 4px 0; font-size:12px; font-weight:bold; color:#007bff;">Your Notes:</p>
        <p style="margin:0; font-size:12px; color:#333;">${retailer.user_notes}</p>
        <button onclick="editNote(${retailer.id})" style="margin-top:4px; padding:2px 6px; font-size:10px; background:#007bff; color:white; border:none; border-radius:2px; cursor:pointer;">Edit</button>
      </div>` : 
      `<div style="margin-top:8px; font-size:12px;">
        <button onclick="addNote(${retailer.id})" style="padding:4px 8px; font-size:10px; background:#28a745; color:white; border:none; border-radius:2px; cursor:pointer;">Add Personal Note</button>
      </div>`) :
    `<div style="margin-top:8px; padding:8px; background:#f8f9fa; border-radius:4px; border-left:3px solid #ffc107;">
      <p style="margin:0 0 4px 0; font-size:12px; font-weight:bold; color:#ffc107;">Personal Notes (Pro)</p>
      <p style="margin:0; font-size:12px; color:#666;">Track your hunting success with private notes</p>
      <button onclick="showProUpgradeToast()" style="margin-top:4px; padding:2px 6px; font-size:10px; background:#ffc107; color:#000; border:none; border-radius:2px; cursor:pointer;">Upgrade to Pro</button>
    </div>`;

  const inner = `
    <p style="margin:6px 0; font-size:16px;">${displayType(retailer, isPro)}</p>
    <p style="margin:6px 0; line-height:1.2; font-size:14px;"><a href=\"https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(retailer.full_address || '')}\" target=\"_blank\">${addressText}</a></p>
    ${phoneSection}
    ${websiteSection}
    ${hoursSection}
    ${notesSection}
    ${reportLink}
  `;

  return wrapInfoWindow(inner, iconUrl, titleText, 21);
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
  // Check if user is Pro - use window.is_pro as fallback
  const proSection = document.getElementById('pro-features-section');
  const isPro = proSection ? 
    proSection.getAttribute('data-is-pro') === 'true' : 
    (window.is_pro === true);
  
  if (!isPro) {
    showProUpgradeToast();
    return;
  }
  
  showNotesModal(retailerId);
};

window.editNote = function(retailerId) {
  // Check if user is Pro - use window.is_pro as fallback
  const proSection = document.getElementById('pro-features-section');
  const isPro = proSection ? 
    proSection.getAttribute('data-is-pro') === 'true' : 
    (window.is_pro === true);
  
  if (!isPro) {
    showProUpgradeToast();
    return;
  }
  
  showNotesModal(retailerId);
};

// Show the Personal Notes modal
function showNotesModal(retailerId) {
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
        const currentNotes = data.notes || '';
        showNotesModalWithContent(retailerId, currentNotes);
      }
    })
    .catch(error => {
      console.error('Error fetching note:', error);
      // Show modal with empty content if fetch fails
      showNotesModalWithContent(retailerId, '');
    });
}

// Refresh the current popup to show updated notes
function refreshCurrentPopup() {
  if (window.currentOpenMarker && window.infoWindow) {
    // Get the retailer data from the current marker
    const retailer = window.currentOpenMarker.retailer_data || window.currentOpenMarker.retailer;
    if (retailer) {
      // Re-fetch notes and update popup
      fetchUserNotesAndShowPopup(window.currentOpenMarker, retailer, window.is_pro);
    }
  }
}

// Add or remove note decorator based on notes existence
function updateNoteDecorator(marker, hasNotes, retailer) {
  console.log('updateNoteDecorator called:', { hasNotes, retailerId: retailer.id, hasDecorator: !!marker.noteDecorator });
  
  // ALWAYS remove existing decorator first, regardless of hasNotes value
  if (marker.noteDecorator) {
    console.log('Removing existing decorator');
    console.log('Decorator before removal:', marker.noteDecorator);
    console.log('Decorator map before removal:', marker.noteDecorator.getMap());
    
    // More aggressive removal
    try {
      marker.noteDecorator.setMap(null);
      marker.noteDecorator = null;
      console.log('Decorator removed successfully');
    } catch (error) {
      console.error('Error removing decorator:', error);
      marker.noteDecorator = null;
    }
    
    // Force a visual refresh by briefly changing the marker's z-index
    const originalZIndex = marker.getZIndex();
    marker.setZIndex(originalZIndex - 1);
    setTimeout(() => {
      marker.setZIndex(originalZIndex);
    }, 10);
    
    // Additional aggressive refresh: trigger map resize event
    setTimeout(() => {
      if (window.google && window.google.maps && window.map) {
        window.google.maps.event.trigger(window.map, 'resize');
      }
    }, 50);
  }
  
  // Only add decorator if notes exist
  if (hasNotes && window.addNoteDecorator) {
    console.log('Adding new decorator');
    window.addNoteDecorator(marker, retailer);
  } else {
    console.log('No notes, not adding decorator');
  }
}

// Show the modal with the actual content
function showNotesModalWithContent(retailerId, currentNotes) {
  Swal.fire({
    title: '<i class="fas fa-sticky-note text-primary me-2"></i>Personal Notes',
    html: `
      <div class="text-start">
        <p class="text-muted mb-3">Track your hunting success and build your strategy with private notes for this location.</p>
        <div class="mb-3">
          <label for="notesTextarea" class="form-label fw-bold">Your Notes:</label>
          <textarea 
            id="notesTextarea" 
            class="form-control" 
            rows="6" 
            placeholder="Record what you found, when you found it, best times to visit, or any other insights..."
            style="resize: vertical; min-height: 120px;"
          >${currentNotes}</textarea>
        </div>
        <div class="text-muted small">
          <i class="fas fa-info-circle me-1"></i>
          These notes are private and only visible to you. Use them to track patterns and optimize your hunting strategy.
        </div>
      </div>
    `,
    width: '500px',
    showCancelButton: true,
    confirmButtonText: '<i class="fas fa-save me-2"></i>Save Notes',
    cancelButtonText: '<i class="fas fa-times me-2"></i>Cancel',
    confirmButtonColor: '#007bff',
    cancelButtonColor: '#6c757d',
    showDenyButton: currentNotes ? true : false,
    denyButtonText: currentNotes ? '<i class="fas fa-trash me-2"></i>Delete Notes' : '',
    denyButtonColor: '#dc3545',
    focusConfirm: false,
    preConfirm: () => {
      const notes = document.getElementById('notesTextarea').value.trim();
      return { notes: notes };
    },
    didOpen: () => {
      // Focus on textarea
      const textarea = document.getElementById('notesTextarea');
      if (textarea) {
        textarea.focus();
        // Move cursor to end
        textarea.setSelectionRange(textarea.value.length, textarea.value.length);
      }
    }
  }).then((result) => {
    if (result.isConfirmed) {
      // Save notes
      const notes = result.value.notes;
      saveUserNote(retailerId, notes);
    } else if (result.isDenied) {
      // Delete notes
      Swal.fire({
        title: 'Delete Notes?',
        text: 'Are you sure you want to delete your notes for this location?',
        icon: 'warning',
        showCancelButton: true,
        confirmButtonText: 'Yes, delete',
        cancelButtonText: 'Cancel',
        confirmButtonColor: '#dc3545'
      }).then((deleteResult) => {
        if (deleteResult.isConfirmed) {
          deleteUserNote(retailerId);
        }
      });
    }
  });
}

function saveUserNote(retailerId, notes) {
  console.log('Saving note for retailer:', retailerId, 'Notes:', notes);
  
  fetch(`/api/user-notes/${retailerId}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ notes: notes })
  })
  .then(response => {
    console.log('Response status:', response.status);
    if (response.status === 403) {
      showProUpgradeToast();
      return;
    }
    return response.json();
  })
  .then(data => {
    console.log('Response data:', data);
    if (data && data.error) {
      Swal.fire({
        icon: 'error',
        title: 'Error',
        text: 'Failed to save note: ' + data.error
      });
    } else if (data) {
      // Show success message
      Swal.fire({
        icon: 'success',
        title: 'Notes Saved!',
        text: 'Your personal notes have been saved successfully.',
        timer: 2000,
        showConfirmButton: false
      });
      
      // Update decorator for the specific marker and refresh popup
      const hasNotes = notes && notes.trim().length > 0;
      
      console.log('SAVE: Looking for marker with retailer ID:', retailerId);
      console.log('SAVE: markerManager available:', !!window.markerManager);
      console.log('SAVE: markerManager.markerCache available:', !!(window.markerManager && window.markerManager.markerCache));
      
      if (window.markerManager && window.markerManager.markerCache) {
        console.log('SAVE: markerCache size:', window.markerManager.markerCache.size);
        // Find the marker by retailer ID
        const marker = Array.from(window.markerManager.markerCache.values())
          .find(m => m.retailer_data && m.retailer_data.id == retailerId);
        
        console.log('SAVE: Found marker:', !!marker);
        if (marker) {
          console.log('SAVE: Updating decorator for marker');
          updateNoteDecorator(marker, hasNotes, { id: retailerId });
        }
      } else {
        console.log('SAVE: markerManager not available, trying alternative approach');
        // Fallback: try to find marker in allMarkers or other global arrays
        if (window.allMarkers) {
          const marker = window.allMarkers.find(m => m.retailer_data && m.retailer_data.id == retailerId);
          if (marker) {
            console.log('SAVE: Found marker in allMarkers, updating decorator');
            updateNoteDecorator(marker, hasNotes, { id: retailerId });
          }
        }
      }
      
      // Also update current open marker if it's the same one
      if (window.currentOpenMarker && window.currentOpenMarker.retailer_data && 
          window.currentOpenMarker.retailer_data.id == retailerId) {
        updateNoteDecorator(window.currentOpenMarker, hasNotes, { id: retailerId });
        
        // Keep the info window open and update its content
        const retailer = window.currentOpenMarker.retailer_data;
        const retailerWithUpdatedNotes = {
          ...retailer,
          user_notes: hasNotes ? notes : null
        };
        
        // Update the popup content directly without closing it
        const html = renderRetailerInfoWindow(retailerWithUpdatedNotes, window.is_pro);
        window.infoWindow.setContent(html);
      } else {
        // Fallback to the original refresh method
        refreshCurrentPopup();
      }
    }
  })
  .catch(error => {
    console.error('Error saving note:', error);
    Swal.fire({
      icon: 'error',
      title: 'Error',
      text: 'Failed to save note. Please try again.'
    });
  });
}

function deleteUserNote(retailerId) {
  fetch(`/api/user-notes/${retailerId}`, {
    method: 'DELETE',
    headers: {
      'Content-Type': 'application/json',
    }
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
      Swal.fire({
        icon: 'error',
        title: 'Error',
        text: 'Failed to delete note: ' + data.error
      });
    } else {
      // Show success message
      Swal.fire({
        icon: 'success',
        title: 'Notes Deleted!',
        text: 'Your personal notes have been deleted.',
        timer: 2000,
        showConfirmButton: false
      });
      
      // Use the aggressive decorator removal function
      console.log('DELETE: Using aggressive decorator removal for retailer:', retailerId);
      if (window.removeAllDecoratorsForRetailer) {
        window.removeAllDecoratorsForRetailer(retailerId);
      }
      
      // Keep the info window open and update its content
      if (window.currentOpenMarker && window.currentOpenMarker.retailer_data && 
          window.currentOpenMarker.retailer_data.id == retailerId) {
        console.log('DELETE: Updating current popup directly (keeping it open)');
        console.log('DELETE: Current marker has decorator:', !!window.currentOpenMarker.noteDecorator);
        
        const retailer = window.currentOpenMarker.retailer_data;
        const retailerWithNoNotes = {
          ...retailer,
          user_notes: null
        };
        
        // Update the popup content directly without closing it
        const html = renderRetailerInfoWindow(retailerWithNoNotes, window.is_pro);
        window.infoWindow.setContent(html);
        
        // Also update the decorator for the current marker
        console.log('DELETE: Calling updateNoteDecorator with hasNotes=false');
        updateNoteDecorator(window.currentOpenMarker, false, retailerWithNoNotes);
        
        // Additional check after decorator update
        setTimeout(() => {
          console.log('DELETE: After decorator update, marker has decorator:', !!window.currentOpenMarker.noteDecorator);
        }, 100);
      } else {
        console.log('DELETE: Current marker not found, using fallback refresh');
        // Fallback to the original refresh method
        refreshCurrentPopup();
      }
    }
  })
  .catch(error => {
    console.error('Error deleting note:', error);
    Swal.fire({
      icon: 'error',
      title: 'Error',
      text: 'Failed to delete note. Please try again.'
    });
  });
}

// Expose updateNoteDecorator globally
window.updateNoteDecorator = updateNoteDecorator;

// Global decorator tracking for more aggressive cleanup
window.noteDecorators = window.noteDecorators || new Map();

// Enhanced decorator removal function
window.removeAllDecoratorsForRetailer = function(retailerId) {
  console.log('REMOVE_ALL: Removing all decorators for retailer:', retailerId);
  
  // Remove from global tracking
  if (window.noteDecorators.has(retailerId)) {
    const decorators = window.noteDecorators.get(retailerId);
    decorators.forEach(decorator => {
      try {
        decorator.setMap(null);
        console.log('REMOVE_ALL: Removed tracked decorator');
      } catch (error) {
        console.error('REMOVE_ALL: Error removing tracked decorator:', error);
      }
    });
    window.noteDecorators.delete(retailerId);
  }
  
  // Also search all markers aggressively
  const allMarkers = [];
  if (window.markerManager && window.markerManager.markerCache) {
    allMarkers.push(...Array.from(window.markerManager.markerCache.values()));
  }
  if (window.allMarkers) {
    allMarkers.push(...window.allMarkers);
  }
  if (window.currentOpenMarker) {
    allMarkers.push(window.currentOpenMarker);
  }
  
  allMarkers.forEach(marker => {
    if (marker && marker.retailer_data && marker.retailer_data.id == retailerId && marker.noteDecorator) {
      console.log('REMOVE_ALL: Found and removing decorator from marker');
      try {
        marker.noteDecorator.setMap(null);
        marker.noteDecorator = null;
      } catch (error) {
        console.error('REMOVE_ALL: Error removing marker decorator:', error);
        marker.noteDecorator = null;
      }
    }
  });
  
  // Force map refresh
  setTimeout(() => {
    if (window.google && window.google.maps && window.map) {
      window.google.maps.event.trigger(window.map, 'resize');
    }
  }, 100);
};
