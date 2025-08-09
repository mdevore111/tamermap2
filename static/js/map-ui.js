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

  // Checkbox states will be set up in setupCheckboxStates() based on pro status
  
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
        
        // Always keep kiosk checked, others depend on pro status
        if (DB.filterKiosk) {
          DB.filterKiosk.checked = true;
          localStorage.setItem('checkbox_filter-kiosk', 'true');
        }
        
        // Check pro status for other checkboxes
        const proSection = document.getElementById('pro-features-section');
        const isPro = proSection ? proSection.getAttribute('data-is-pro') === 'true' : false;
        
        if (isPro) {
          // For pro users, restore saved states
          if (DB.filterRetail) {
            DB.filterRetail.checked = localStorage.getItem('checkbox_filter-retail') === 'true' || true;
            localStorage.setItem('checkbox_filter-retail', DB.filterRetail.checked);
          }
          if (DB.filterIndie) {
            DB.filterIndie.checked = localStorage.getItem('checkbox_filter-indie') === 'true' || false;
            localStorage.setItem('checkbox_filter-indie', DB.filterIndie.checked);
          }
        } else {
          // For non-pro users, uncheck pro checkboxes
          if (DB.filterRetail) {
            DB.filterRetail.checked = false;
            localStorage.setItem('checkbox_filter-retail', 'false');
          }
          if (DB.filterIndie) {
            DB.filterIndie.checked = false;
            localStorage.setItem('checkbox_filter-indie', 'false');
          }
        }
        
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

  // Add pro user check for pro-only section
  function setupProSectionCheck() {
    const proSection = document.getElementById('pro-features-section');
    if (!proSection) return;
    
    const isPro = proSection.getAttribute('data-is-pro') === 'true';
    
    // Set up checkbox states based on pro status
    setupCheckboxStates(isPro);
    
    // Add click handler to the entire pro section
    proSection.addEventListener('click', (e) => {
      if (!isPro) {
        // Check if the click was on a checkbox or button within the section
        const target = e.target;
        if (target.tagName === 'INPUT' || target.tagName === 'BUTTON' || target.closest('label')) {
          e.preventDefault();
          e.stopPropagation();
          showProUpgradeToast();
          return false;
        }
      }
    });
    
    // Handle route planning button specifically
    const routeBtn = document.getElementById('plan-route-btn');
    if (routeBtn) {
      routeBtn.addEventListener('click', (e) => {
        if (!isPro) {
          e.preventDefault();
          e.stopPropagation();
          showProUpgradeToast();
          return false;
        } else {
          openRoutePanel();
        }
      });
    }
  }
  
  // Setup checkbox states based on pro status
  function setupCheckboxStates(isPro) {
    // Always keep kiosk checkbox checked
    if (DB.filterKiosk) {
      DB.filterKiosk.checked = true;
      localStorage.setItem('checkbox_filter-kiosk', 'true');
    }
    
    if (isPro) {
      // For pro users, restore saved states or use defaults
      if (DB.filterRetail) {
        DB.filterRetail.checked = localStorage.getItem('checkbox_filter-retail') === 'true' || true;
        localStorage.setItem('checkbox_filter-retail', DB.filterRetail.checked);
      }
      if (DB.filterIndie) {
        DB.filterIndie.checked = localStorage.getItem('checkbox_filter-indie') === 'true' || false;
        localStorage.setItem('checkbox_filter-indie', DB.filterIndie.checked);
      }
      if (DB.filterOpenNow) {
        DB.filterOpenNow.checked = localStorage.getItem('checkbox_filter-open-now') === 'true' || false;
        localStorage.setItem('checkbox_filter-open-now', DB.filterOpenNow.checked);
      }
      if (DB.filterNew) {
        DB.filterNew.checked = localStorage.getItem('checkbox_filter-new') === 'true' || false;
        localStorage.setItem('checkbox_filter-new', DB.filterNew.checked);
      }
      if (DB.filterPopularAreas) {
        DB.filterPopularAreas.checked = localStorage.getItem('checkbox_filter-popular-areas') === 'true' || false;
        localStorage.setItem('checkbox_filter-popular-areas', DB.filterPopularAreas.checked);
      }
      if (DB.filterEvents) {
        DB.filterEvents.checked = localStorage.getItem('checkbox_filter-events') === 'true' || false;
        localStorage.setItem('checkbox_filter-events', DB.filterEvents.checked);
      }
    } else {
      // For non-pro users, uncheck all pro checkboxes
      if (DB.filterRetail) {
        DB.filterRetail.checked = false;
        localStorage.setItem('checkbox_filter-retail', 'false');
      }
      if (DB.filterIndie) {
        DB.filterIndie.checked = false;
        localStorage.setItem('checkbox_filter-indie', 'false');
      }
      if (DB.filterOpenNow) {
        DB.filterOpenNow.checked = false;
        localStorage.setItem('checkbox_filter-open-now', 'false');
      }
      if (DB.filterNew) {
        DB.filterNew.checked = false;
        localStorage.setItem('checkbox_filter-new', 'false');
      }
      if (DB.filterPopularAreas) {
        DB.filterPopularAreas.checked = false;
        localStorage.setItem('checkbox_filter-popular-areas', 'false');
      }
      if (DB.filterEvents) {
        DB.filterEvents.checked = false;
        localStorage.setItem('checkbox_filter-events', 'false');
      }
    }
    
    // Apply filters after setting states
    if (typeof window.applyFilters === 'function') {
      window.applyFilters();
    }
  }
  
  // Setup pro section check
  setupProSectionCheck();

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
    .forEach(cb => {
      cb.addEventListener('change', () => {
        localStorage.setItem(`checkbox_${cb.id}`, cb.checked);
        window.applyFilters();
      });
    });

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
 * Show pro upgrade toast message
 */
function showProUpgradeToast() {
  if (typeof Swal !== 'undefined') {
    Swal.fire({
      toast: true,
      position: 'top-start',
      icon: 'lock',
      title: 'Pro Feature',
      html: '<div style="font-size: 13px; margin: 6px 0; color: #6c757d;">Upgrade to access this feature</div>',
      showConfirmButton: true,
      confirmButtonText: 'Try Pro',
      confirmButtonColor: '#667eea',
      showCancelButton: false,
      timer: 5000,
      timerProgressBar: true,
      width: '270px',
      background: '#ffffff',
      customClass: {
        popup: 'swal2-toast-pro',
        confirmButton: 'btn btn-sm btn-primary',
        title: 'swal2-toast-title'
      },
      didOpen: (toast) => {
        // Enhanced styling for better appearance
        toast.style.fontSize = '12px';
        toast.style.padding = '12px 16px';
        toast.style.borderRadius = '10px';
        toast.style.boxShadow = '0 6px 20px rgba(0, 0, 0, 0.12)';
        toast.style.border = '1px solid #dee2e6';
        toast.style.background = 'linear-gradient(135deg, #ffffff 0%, #f8f9fa 100%)';
        
        // Style the title with pro badge
        const title = toast.querySelector('.swal2-title');
        if (title) {
          title.innerHTML = 'Pro Feature <span style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; font-size: 10px; padding: 2px 6px; border-radius: 10px; margin-left: 6px; font-weight: 400; text-transform: uppercase; letter-spacing: 0.5px;">Pro</span>';
          title.style.fontSize = '15px';
          title.style.fontWeight = '600';
          title.style.color = '#2c3e50';
          title.style.marginBottom = '6px';
          title.style.display = 'flex';
          title.style.alignItems = 'center';
        }
        
        // Style the message
        const message = toast.querySelector('.swal2-html-container');
        if (message) {
          message.style.fontSize = '13px';
          message.style.color = '#6c757d';
          message.style.lineHeight = '1.4';
        }
        
        // Style the button
        const button = toast.querySelector('.swal2-confirm');
        if (button) {
          button.style.fontSize = '11px';
          button.style.padding = '6px 14px';
          button.style.borderRadius = '6px';
          button.style.fontWeight = '600';
          button.style.background = 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)';
          button.style.border = 'none';
          button.style.boxShadow = '0 2px 8px rgba(102, 126, 234, 0.3)';
          button.style.transition = 'all 0.2s ease';
        }
        
        // Add hover effect to button
        const buttonElement = toast.querySelector('.swal2-confirm');
        if (buttonElement) {
          buttonElement.addEventListener('mouseenter', () => {
            buttonElement.style.transform = 'translateY(-1px)';
            buttonElement.style.boxShadow = '0 4px 12px rgba(102, 126, 234, 0.4)';
          });
          buttonElement.addEventListener('mouseleave', () => {
            buttonElement.style.transform = 'translateY(0)';
            buttonElement.style.boxShadow = '0 2px 8px rgba(102, 126, 234, 0.3)';
          });
        }
      }
    }).then((result) => {
      if (result.isConfirmed) {
        window.location.href = '/learn';
      }
    });
  } else {
    alert('Pro Feature - Upgrade to access this feature.');
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

  // If we're in preview mode, persist preferences and exit preview
  if (window.routePlanner.currentStep === 'preview') {
    // Ensure preferences are saved (in-memory state is the source of truth)
    if (typeof window.routePlanner.savePreferences === 'function') {
      window.routePlanner.savePreferences();
    }
    window.routePlanner.exitPreview();
  }

  // Use the new wizard-style modal
  window.routePlanner.openPlanningModal();
}



// Expose functions globally
window.openRoutePanel = openRoutePanel;
window.showProUpgradeToast = showProUpgradeToast;
window.initUI = initUI;

// Don't auto-initialize - let map-init.js handle it
// if (document.readyState === 'loading') {
//   document.addEventListener('DOMContentLoaded', initUI);
// } else {
//   initUI();
// }
// touch