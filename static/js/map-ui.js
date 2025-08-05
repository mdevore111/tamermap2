// static/js/map-ui.js
import { isOpenNow } from './utils.js';

window.domCache = {};

/**
 * Reset filters to their default state
 */
function resetFilters() {
  const DB = window.domCache;

  // Reset to defaults
  if (DB.filterKiosk)       DB.filterKiosk.checked       = true;
  if (DB.filterRetail)      DB.filterRetail.checked      = is_pro ? true : false;
  if (DB.filterIndie)       DB.filterIndie.checked       = is_pro ? true : false;
  if (DB.filterNew)         DB.filterNew.checked         = false;
  if (DB.filterOpenNow)     DB.filterOpenNow.checked     = false;
  if (DB.filterEvents)      DB.filterEvents.checked      = false;
  if (DB.filterPopularAreas)DB.filterPopularAreas.checked = false;
  if (DB.legendFilter)      DB.legendFilter.value        = '';
  
  // Reset event days slider
  if (DB.eventDaysSlider) {
    DB.eventDaysSlider.value = 30; // Default 30 days
    if (DB.eventDaysValue) {
      DB.eventDaysValue.textContent = "30 days";
    }
    if (DB.eventDaysContainer) {
      DB.eventDaysContainer.style.display = 'none'; // Hide since events checkbox is false
    }
  }

  // Save reset state to localStorage
  [
    ['filter-kiosk', DB.filterKiosk ? DB.filterKiosk.checked : true],
    ['filter-retail', DB.filterRetail ? DB.filterRetail.checked : (is_pro ? true : false)],
    ['filter-indie', DB.filterIndie ? DB.filterIndie.checked : (is_pro ? true : false)],
    ['filter-new', DB.filterNew ? DB.filterNew.checked : false],
    ['filter-open-now', DB.filterOpenNow ? DB.filterOpenNow.checked : false],
    ['filter-events', DB.filterEvents ? DB.filterEvents.checked : false],
    ['filter-popular-areas', DB.filterPopularAreas ? DB.filterPopularAreas.checked : false]
  ].forEach(([id, checked]) => {
    localStorage.setItem(`checkbox_${id}`, checked);
  });
  localStorage.setItem('checkbox_legend_filter', '');
  localStorage.setItem('event_days_slider', '30'); // Reset slider value in localStorage

  window.applyFilters();
}

/**
 * Initialize UI: cache DOM nodes and wire all filter controls.
 */
function initUI() {
  const DB = window.domCache;

  // Cache legend controls
  DB.legendToggleBtn     = document.getElementById('legend-toggle');
  DB.legendResetBtn      = document.getElementById('legend-reset');
  DB.legend              = document.getElementById('legend');

  // Ensure legend is visible by default
  if (DB.legend) {
    DB.legend.style.display = 'block';
    DB.legend.style.visibility = 'visible';
  }

  // Cache all filter checkboxes
  DB.filterKiosk         = document.getElementById('filter-kiosk');
  DB.filterRetail        = document.getElementById('filter-retail');
  DB.filterIndie         = document.getElementById('filter-indie');
  DB.filterNew           = document.getElementById('filter-new');
  DB.filterOpenNow       = document.getElementById('filter-open-now');
  DB.filterEvents        = document.getElementById('filter-events');
  DB.filterPopularAreas  = document.getElementById('filter-popular-areas');

  // Cache slider and related elements
  DB.eventDaysSlider     = document.getElementById('event-days-slider');
  DB.eventDaysValue      = document.getElementById('event-days-value');
  DB.eventDaysContainer  = document.getElementById('event-days-slider-container');

  // Cache the text-search field
  DB.legendFilter        = document.getElementById('legend_filter');

  // Restore saved filter states from localStorage
  [
    'filter-kiosk',
    'filter-retail',
    'filter-indie',
    'filter-new',
    'filter-open-now',
    'filter-events',
    'filter-popular-areas'
  ].forEach(id => {
    const el = document.getElementById(id);
    const val = localStorage.getItem(`checkbox_${id}`);
    if (el && val !== null) {
      el.checked = (val === 'true');
    }
  });
  
  // Restore event days slider value from localStorage
  if (DB.eventDaysSlider) {
    const savedDays = localStorage.getItem('event_days_slider');
    if (savedDays !== null) {
      DB.eventDaysSlider.value = savedDays;
      if (DB.eventDaysValue) {
        DB.eventDaysValue.textContent = `${savedDays} days`;
      }
    }
  }
  
  // Update slider display and toggle container visibility based on events checkbox
  if (DB.filterEvents && DB.eventDaysContainer) {
    // Initialize container visibility
    DB.eventDaysContainer.style.display = DB.filterEvents.checked ? 'block' : 'none';
    
    // Toggle visibility when events checkbox changes
    DB.filterEvents.addEventListener('change', () => {
      DB.eventDaysContainer.style.display = DB.filterEvents.checked ? 'block' : 'none';
    });
  }
  
  // Handle slider input events
  if (DB.eventDaysSlider && DB.eventDaysValue) {
    DB.eventDaysSlider.addEventListener('input', () => {
      const days = DB.eventDaysSlider.value;
      DB.eventDaysValue.textContent = `${days} days`;
      localStorage.setItem('event_days_slider', days);
      window.applyFilters();
    });
  }

  // Style search input with Bootstrap and spacing
  if (DB.legendFilter) {
    DB.legendFilter.type = 'search';
    DB.legendFilter.classList.add('form-control', 'mb-2');
    DB.legendFilter.placeholder = DB.legendFilter.placeholder || 'Search…';
    
    // Restore search filter value from localStorage
    const savedSearch = localStorage.getItem('checkbox_legend_filter');
    if (savedSearch !== null) {
      DB.legendFilter.value = savedSearch;
    }
    
    // Handle clear button functionality
    const clearButton = document.getElementById('clear-legend');
    if (clearButton) {
      // Clear button click handler
      clearButton.addEventListener('click', () => {
        DB.legendFilter.value = '';
        localStorage.setItem('checkbox_legend_filter', '');
        
        // Restore original checkbox states when clearing search
        // You can customize this based on what the default state should be
        if (DB.filterKiosk) {
          DB.filterKiosk.checked = localStorage.getItem('checkbox_filter-kiosk') === 'true' || true; // Default to checked
          localStorage.setItem('checkbox_filter-kiosk', DB.filterKiosk.checked);
        }
        if (DB.filterRetail) {
          DB.filterRetail.checked = localStorage.getItem('checkbox_filter-retail') === 'true' || true; // Default to checked
          localStorage.setItem('checkbox_filter-retail', DB.filterRetail.checked);
        }
        if (DB.filterIndie) {
          DB.filterIndie.checked = localStorage.getItem('checkbox_filter-indie') === 'true' || false; // Default to unchecked
          localStorage.setItem('checkbox_filter-indie', DB.filterIndie.checked);
        }
        // Don't restore events checkbox - it has its own logic
        
        window.applyFilters();
        // Hide the clear button after clearing
        clearButton.style.display = 'none';
      });
      
      // Show/hide clear button based on input value
      const updateClearButtonVisibility = () => {
        clearButton.style.display = DB.legendFilter.value ? 'block' : 'none';
      };
      
      // Initial visibility check
      updateClearButtonVisibility();
      
      // Update visibility on input
      DB.legendFilter.addEventListener('input', updateClearButtonVisibility);
    }
    
    // Search input handler
    DB.legendFilter.addEventListener('input', () => {
      localStorage.setItem('checkbox_legend_filter', DB.legendFilter.value);
      
      // If there's a search term, automatically enable all relevant checkboxes
      if (DB.legendFilter.value.trim()) {
        // Enable all checkboxes when searching to show all matching results
        if (DB.filterKiosk) DB.filterKiosk.checked = true;
        if (DB.filterRetail) DB.filterRetail.checked = true;
        if (DB.filterIndie) DB.filterIndie.checked = true;
        // Don't automatically check events - they have their own search logic
        
        // Save the checkbox states
        localStorage.setItem('checkbox_filter-kiosk', 'true');
        localStorage.setItem('checkbox_filter-retail', 'true');
        localStorage.setItem('checkbox_filter-indie', 'true');
        // Don't save events state
      }
      
      window.applyFilters();
      
      // Update clear button visibility
      if (clearButton) {
        clearButton.style.display = DB.legendFilter.value ? 'block' : 'none';
      }
    });
  }

  // Wire all checkboxes—including Popular Areas—to applyFilters and save state
  [
    DB.filterKiosk,
    DB.filterRetail,
    DB.filterIndie,
    DB.filterNew,
    DB.filterOpenNow,
    DB.filterEvents,
    DB.filterPopularAreas
  ]
    .filter(cb => cb)
    .forEach(cb => cb.addEventListener('change', () => {
      localStorage.setItem(`checkbox_${cb.id}`, cb.checked);
      window.applyFilters();
    }));

// Legend show/hide toggle (only body)
if (DB.legendToggleBtn) {
  
  
  // Remove any existing event listeners to prevent duplicates
  const newToggleBtn = DB.legendToggleBtn.cloneNode(true);
  DB.legendToggleBtn.parentNode.replaceChild(newToggleBtn, DB.legendToggleBtn);
  DB.legendToggleBtn = newToggleBtn;
  
  DB.legendToggleBtn.addEventListener('click', () => {
    
    const body = document.getElementById('legend-body');
    const chevron = DB.legendToggleBtn.querySelector('i');
    if (body && chevron) {
      const isCollapsed = DB.legend.classList.contains('collapsed');
      
      
      // Toggle the collapsed class on the legend
      DB.legend.classList.toggle('collapsed', !isCollapsed);
      
      // Update the chevron icon
      chevron.classList.toggle('fa-chevron-up', !isCollapsed);
      chevron.classList.toggle('fa-chevron-down', isCollapsed);
      
      // Force the display style directly
      if (!isCollapsed) {
        // If we just collapsed, ensure body is hidden
        body.style.display = 'none';
      } else {
        // If we just expanded, ensure body is visible
        body.style.display = 'block';
      }
      
      
      
      // Store the collapsed state
      localStorage.setItem('legend_collapsed', !isCollapsed);
    } else {
      
    }
  });
  
  // Check if legend was collapsed previously and restore state
  const wasCollapsed = localStorage.getItem('legend_collapsed') === 'true';
  if (wasCollapsed) {
    const body = document.getElementById('legend-body');
    const chevron = DB.legendToggleBtn.querySelector('i');
    if (body && chevron) {
      DB.legend.classList.add('collapsed');
      chevron.classList.remove('fa-chevron-up');
      chevron.classList.add('fa-chevron-down');
      // Force the body to be hidden
      body.style.display = 'none';
    }
  }
} else {
  
}

// Reset button in header
if (DB.legendResetBtn) {
  DB.legendResetBtn.addEventListener('click', resetFilters);
}

// Pro‑only guard
if (!is_pro) {
  document.querySelectorAll('.pro-only').forEach(el => {
    el.addEventListener('click', e => {
      e.preventDefault();
      if (typeof Swal !== 'undefined') {
        Swal.fire({
          toast: true,
          position: 'top-start',
          icon: 'warning',
          title: 'This feature is available for Pro users only. <a href="/learn" style="color: #007bff; text-decoration: underline;">Go Pro</a>',
          showConfirmButton: false,
          timer: 2500,
          timerProgressBar: true,
          didOpen: (toast) => {
            toast.addEventListener('mouseenter', Swal.stopTimer);
            toast.addEventListener('mouseleave', Swal.resumeTimer);
          }
        });
      } else {
        alert('This feature is available for Pro users only.');
      }
    });
  });
}
}

/**
 * Handle search form submission
 */
function handleSearch(event) {
  event.preventDefault();
  
  const searchInput = document.getElementById('places_search');
  if (!searchInput || !searchInput.value.trim()) {
    return false;
  }
  
  // Use Google Places Autocomplete if available
  if (window.google && window.google.maps && window.google.maps.places) {
    const autocomplete = new google.maps.places.Autocomplete(searchInput);
    const place = autocomplete.getPlace();
    
    if (place && place.geometry) {
      window.map.setCenter(place.geometry.location);
      window.map.setZoom(15);
    } else {
      // Fallback: use geocoding
      const geocoder = new google.maps.Geocoder();
      geocoder.geocode({ address: searchInput.value }, (results, status) => {
        if (status === 'OK' && results[0]) {
          window.map.setCenter(results[0].geometry.location);
          window.map.setZoom(15);
        } else {
          console.warn('Geocoding failed:', status);
        }
      });
    }
  }
  
  return false;
}

// Expose handleSearch globally
window.handleSearch = handleSearch;

/**
 * Show pro upgrade modal for route planning
 */
function showProUpgradeModal() {
  if (typeof Swal !== 'undefined') {
    Swal.fire({
      title: '<i class="fas fa-route"></i> Route Planning',
      html: `
        <div style="text-align: center; padding: 20px;">
          <i class="fas fa-lock" style="font-size: 48px; color: #667eea; margin-bottom: 20px;"></i>
          <h4>Pro Feature</h4>
          <p>Route planning is available for Pro users only.</p>
          <p>Upgrade to Pro to plan optimized routes to multiple locations.</p>
        </div>
      `,
      showCancelButton: true,
      confirmButtonText: 'Go Pro',
      cancelButtonText: 'Maybe Later',
      confirmButtonColor: '#667eea',
      customClass: {
        popup: 'swal2-pro-upgrade'
      }
    }).then((result) => {
      if (result.isConfirmed) {
        window.location.href = '/learn';
      }
    });
  } else {
    alert('Route planning is available for Pro users only. Visit /learn to upgrade.');
  }
}

/**
 * Open route planner modal using SweetAlert2
 */
function openRoutePanel() {
  if (!window.routePlanner) {
    console.error('Route planner not initialized');
    return;
  }

  // Use the SweetAlert2 configuration from routePlanner
  Swal.fire({
    title: '<i class="fas fa-route"></i> Route Planner',
    html: window.routePlanner.createModalContent(),
    showConfirmButton: false,
    showCancelButton: false,
    showCloseButton: true,
    customClass: {
      popup: 'swal2-route-planner'
    },
    width: 'auto',
    didOpen: () => {
      window.routePlanner.initializeModalControls();
    }
  });
}

/**
 * Close route planner modal
 */
function closeRoutePanel() {
  Swal.close();
}

// Expose functions globally
window.openRoutePanel = openRoutePanel;
window.closeRoutePanel = closeRoutePanel;
window.initUI = initUI;

// Don't auto-initialize - let map-init.js handle it
// if (document.readyState === 'loading') {
//   document.addEventListener('DOMContentLoaded', initUI);
// } else {
//   initUI();
// }
// touch