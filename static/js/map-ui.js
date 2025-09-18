// static/js/map-ui.js
import { isOpenNow } from './utils.js';
console.log('[map-ui] module loaded');

let __tm_ui_initialized = false;

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
  localStorage.setItem('heatmap_days_slider', '60'); // Reset heatmap slider value in localStorage

  window.applyFilters();
}

/**
 * Initialize UI: cache DOM nodes and wire all filter controls.
 */
function initUI() {
  if (__tm_ui_initialized) { console.log('[map-ui] initUI skipped (already initialized)'); return; }
  console.log('[map-ui] initUI start');
  const DB = window.domCache;

  // Cache legend controls
  DB.legendResetBtn      = document.getElementById('legend-reset');
  DB.legend              = document.getElementById('legend');
  
  console.log('[map-ui] Legend elements found:', {
    legendResetBtn: !!DB.legendResetBtn,
    legend: !!DB.legend
  });

  // Ensure legend is visible by default
  if (DB.legend) {
    DB.legend.style.display = 'block';
    DB.legend.style.visibility = 'visible';
  }

  // Initialize mobile drawer functionality
  initializeMobileDrawer();
  
  // Initialize dynamic drawer height adjustment
  initializeDynamicDrawerHeight();

  // Cache all filter checkboxes
  DB.filterKiosk         = document.getElementById('filter-kiosk');
  DB.filterRetail        = document.getElementById('filter-retail');
  DB.filterIndie         = document.getElementById('filter-indie');
  DB.filterNew           = document.getElementById('filter-new');
  DB.filterOpenNow       = document.getElementById('filter-open-now');
  DB.filterEvents        = document.getElementById('filter-events');
  DB.filterPopularAreas  = document.getElementById('filter-popular-areas');
  console.log('[map-ui] Filter checkbox presence:', {
    kiosk: !!DB.filterKiosk,
    retail: !!DB.filterRetail,
    indie: !!DB.filterIndie,
    newOnly: !!DB.filterNew,
    openNow: !!DB.filterOpenNow,
    events: !!DB.filterEvents,
    popular: !!DB.filterPopularAreas
  });

  // Cache slider and related elements
  DB.eventDaysSlider     = document.getElementById('event-days-slider');
  DB.eventDaysValue      = document.getElementById('event-days-value');
  DB.eventDaysContainer  = document.getElementById('event-days-slider-container');
  console.log('[map-ui] Event slider present:', !!DB.eventDaysSlider, 'container:', !!DB.eventDaysContainer);
  
  // Cache heatmap slider elements
  DB.heatmapDaysSlider     = document.getElementById('heatmap-days-slider');
  DB.heatmapDaysValue      = document.getElementById('heatmap-days-value');
  DB.heatmapDaysContainer  = document.getElementById('heatmap-days-slider-container');
  console.log('[map-ui] Heatmap slider present:', !!DB.heatmapDaysSlider, 'container:', !!DB.heatmapDaysContainer);

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
  
  // Restore heatmap days slider value from localStorage
  if (DB.heatmapDaysSlider) {
    const savedDays = localStorage.getItem('heatmap_days_slider');
    if (savedDays !== null) {
      DB.heatmapDaysSlider.value = savedDays;
      if (DB.heatmapDaysValue) {
        DB.heatmapDaysValue.textContent = `${savedDays} days`;
      }
    }
  }
  
  // Update slider display and toggle container visibility based on events checkbox
  if (DB.filterEvents && DB.eventDaysContainer) {
    // Initialize container visibility - use flex on mobile, block on desktop
    const isMobile = window.innerWidth <= 768;
    DB.eventDaysContainer.style.display = DB.filterEvents.checked ? (isMobile ? 'flex' : 'block') : 'none';

    // Initialize label styling for mobile
    if (isMobile) {
      const label = DB.filterEvents.closest('label');
      if (label) {
        if (DB.filterEvents.checked) {
          label.style.display = 'inline-flex';
          label.style.alignItems = 'center';
          label.style.flexWrap = 'wrap';
          label.style.width = '100%';
          label.style.justifyContent = 'flex-start';
        } else {
          label.style.display = 'block';
          label.style.width = '';
          label.style.justifyContent = '';
        }
      }
    }
    
    // Toggle visibility when events checkbox changes
    DB.filterEvents.addEventListener('change', () => {
      const isMobile = window.innerWidth <= 768;
      DB.eventDaysContainer.style.display = DB.filterEvents.checked ? (isMobile ? 'flex' : 'block') : 'none';
      if (isMobile) {
        DB.eventDaysContainer.style.flexDirection = 'row';
        // Make the label inline when slider is visible
        const label = DB.filterEvents.closest('label');
        if (label) {
          if (DB.filterEvents.checked) {
            label.style.display = 'inline-flex';
            label.style.alignItems = 'center';
            label.style.flexWrap = 'wrap';
            label.style.width = '100%';
            label.style.justifyContent = 'flex-start';
          } else {
            label.style.display = 'block';
            label.style.width = '';
            label.style.justifyContent = '';
          }
        }
      }
    });
  }
  
  if (DB.filterPopularAreas && DB.heatmapDaysContainer) {
    // Initialize container visibility - use flex on mobile, block on desktop
    const isMobile = window.innerWidth <= 768;
    DB.heatmapDaysContainer.style.display = DB.filterPopularAreas.checked ? (isMobile ? 'flex' : 'block') : 'none';

    // Initialize label styling for mobile
    if (isMobile) {
      const label = DB.filterPopularAreas.closest('label');
      if (label) {
        if (DB.filterPopularAreas.checked) {
          label.style.display = 'inline-flex';
          label.style.alignItems = 'center';
          label.style.flexWrap = 'wrap';
          label.style.width = '100%';
          label.style.justifyContent = 'flex-start';
        } else {
          label.style.display = 'block';
          label.style.width = '';
          label.style.justifyContent = '';
        }
      }
    }
    
    // Toggle visibility when popular areas checkbox changes
    DB.filterPopularAreas.addEventListener('change', () => {
      const isMobile = window.innerWidth <= 768;
      DB.heatmapDaysContainer.style.display = DB.filterPopularAreas.checked ? (isMobile ? 'flex' : 'block') : 'none';
      if (isMobile) {
        DB.heatmapDaysContainer.style.flexDirection = 'row';
        // Make the label inline when slider is visible
        const label = DB.filterPopularAreas.closest('label');
        if (label) {
          if (DB.filterPopularAreas.checked) {
            label.style.display = 'inline-flex';
            label.style.alignItems = 'center';
            label.style.flexWrap = 'wrap';
            label.style.width = '100%';
            label.style.justifyContent = 'flex-start';
          } else {
            label.style.display = 'block';
            label.style.width = '';
            label.style.justifyContent = '';
          }
        }
      }
    });
  }

  // Ensure initial slider visibility syncs with current state (with DOM ready check)
  try {
    // Use setTimeout to ensure DOM is fully loaded
    setTimeout(() => {
      const filters = {
        showPopular: DB.filterPopularAreas ? DB.filterPopularAreas.checked : false,
        showEvents: DB.filterEvents ? DB.filterEvents.checked : false
      };
      if (window.__TM_DEBUG__) console.log('[map-ui] initializing slider visibility with filters:', filters);
      (window.updateFilterUI || function(){ })(filters);
    }, 100); // Small delay to ensure DOM is ready
  } catch (_) {}
  
  // Handle slider input events
  if (DB.eventDaysSlider && DB.eventDaysValue) {
    // Function to update slider progress bar (reuse from above)
    function updateSliderProgress(slider) {
      const value = ((slider.value - slider.min) / (slider.max - slider.min)) * 100;
      slider.style.setProperty('--progress', `${value}%`);
    }
    
    // Initialize progress bar
    updateSliderProgress(DB.eventDaysSlider);
    
    DB.eventDaysSlider.addEventListener('input', () => {
      // Check if user is pro before allowing slider interaction
      const proSection = document.getElementById('pro-features-section');
      const isPro = proSection ? proSection.getAttribute('data-is-pro') === 'true' : (window.is_pro === true);
      
      if (!isPro) {
        showProUpgradeToast();
        return;
      }
      
      const days = DB.eventDaysSlider.value;
      DB.eventDaysValue.textContent = `${days} days`;
      localStorage.setItem('event_days_slider', days);
      
      // Update progress bar
      updateSliderProgress(DB.eventDaysSlider);
      
      window.applyFilters();
    });
  }
  
  // Handle heatmap slider input events with debouncing
  if (DB.heatmapDaysSlider && DB.heatmapDaysValue) {
    let sliderDebounceTimer;
    
    // Function to update slider progress bar
    function updateSliderProgress(slider) {
      const value = ((slider.value - slider.min) / (slider.max - slider.min)) * 100;
      slider.style.setProperty('--progress', `${value}%`);
    }
    
    // Initialize progress bar
    updateSliderProgress(DB.heatmapDaysSlider);
    
    DB.heatmapDaysSlider.addEventListener('input', () => {
      // Check if user is pro before allowing slider interaction
      const proSection = document.getElementById('pro-features-section');
      const isPro = proSection ? proSection.getAttribute('data-is-pro') === 'true' : (window.is_pro === true);
      
      if (!isPro) {
        showProUpgradeToast();
        return;
      }
      
      const days = DB.heatmapDaysSlider.value;
      DB.heatmapDaysValue.textContent = `${days} days`;
      localStorage.setItem('heatmap_days_slider', days);
      
      // Update progress bar
      updateSliderProgress(DB.heatmapDaysSlider);
      
      // Debounce the API call to prevent rate limiting
      clearTimeout(sliderDebounceTimer);
      sliderDebounceTimer = setTimeout(() => {
        refreshHeatmapData(days);
      }, 1000); // 1000ms debounce to reduce rate limiting
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
        
        // Check pro status for other checkboxes
        const proSection = document.getElementById('pro-features-section');
        const isPro = proSection ? proSection.getAttribute('data-is-pro') === 'true' : false;
        
        if (isPro) {
          // For pro users, restore saved states or use sensible defaults
          if (DB.filterRetail) {
            const saved = localStorage.getItem('checkbox_filter-retail');
            DB.filterRetail.checked = (saved ?? 'true') === 'true'; // Pro default true
            localStorage.setItem('checkbox_filter-retail', String(DB.filterRetail.checked));
          }
          if (DB.filterIndie) {
            const saved = localStorage.getItem('checkbox_filter-indie');
            DB.filterIndie.checked = (saved ?? 'false') === 'true'; // Pro default false
            localStorage.setItem('checkbox_filter-indie', String(DB.filterIndie.checked));
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
        localStorage.setItem('checkbox_filter-kiosk', String(DB.filterKiosk.checked));
        localStorage.setItem('checkbox_filter-retail', String(DB.filterRetail.checked));
        localStorage.setItem('checkbox_filter-indie', String(DB.filterIndie.checked));
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
    // kiosk: default true on first load, but don't force it every time
    if (DB.filterKiosk) {
      const saved = localStorage.getItem('checkbox_filter-kiosk');
      DB.filterKiosk.checked = saved === null ? true : (saved === 'true');
      localStorage.setItem('checkbox_filter-kiosk', String(DB.filterKiosk.checked));
    }
    
    if (isPro) {
      // retail: default true for Pro, false for non-Pro, but honor saved value
      if (DB.filterRetail) {
        const fallback = 'true'; // Pro default
        const saved = localStorage.getItem('checkbox_filter-retail');
        DB.filterRetail.checked = (saved ?? fallback) === 'true';   // <-- no "|| true"
        localStorage.setItem('checkbox_filter-retail', String(DB.filterRetail.checked));
      }
      if (DB.filterIndie) {
        const fallback = 'false'; // Pro default
        const saved = localStorage.getItem('checkbox_filter-indie');
        DB.filterIndie.checked = (saved ?? fallback) === 'true';
        localStorage.setItem('checkbox_filter-indie', String(DB.filterIndie.checked));
      }
      if (DB.filterOpenNow) {
        const fallback = 'false';
        const saved = localStorage.getItem('checkbox_filter-open-now');
        DB.filterOpenNow.checked = (saved ?? fallback) === 'true';
        localStorage.setItem('checkbox_filter-open-now', String(DB.filterOpenNow.checked));
      }
      if (DB.filterNew) {
        const fallback = 'false';
        const saved = localStorage.getItem('checkbox_filter-new');
        DB.filterNew.checked = (saved ?? fallback) === 'true';
        localStorage.setItem('checkbox_filter-new', String(DB.filterNew.checked));
      }
      if (DB.filterPopularAreas) {
        const fallback = 'false';
        const saved = localStorage.getItem('checkbox_filter-popular-areas');
        DB.filterPopularAreas.checked = (saved ?? fallback) === 'true';
        localStorage.setItem('checkbox_filter-popular-areas', String(DB.filterPopularAreas.checked));
      }
      if (DB.filterEvents) {
        const fallback = 'false';
        const saved = localStorage.getItem('checkbox_filter-events');
        DB.filterEvents.checked = (saved ?? fallback) === 'true';
        localStorage.setItem('checkbox_filter-events', String(DB.filterEvents.checked));
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
        // Track legend interaction (except search)
        try {
          const center = window.map && window.map.getCenter ? window.map.getCenter() : null;
          const payload = {
            control_id: cb.id,
            path: location.pathname,
            zoom: window.map && window.map.getZoom ? window.map.getZoom() : undefined,
            center_lat: center ? center.lat() : undefined,
            center_lng: center ? center.lng() : undefined
          };
          fetch('/track/legend', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) }).catch(() => {});
        } catch {}
      });
    });

// Toggle button removed - mobile uses drawer, desktop shows full legend

// Reset button in header
if (DB.legendResetBtn) {
  console.log('[map-ui] setting up reset button event listener');
  DB.legendResetBtn.addEventListener('click', resetFilters);
} else {
  console.error('[map-ui] Reset button not found!');
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
        // Quiet in production; optional alert can be enabled for support
      }
    });
  });
}

  __tm_ui_initialized = true;
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
  
  // Note: Places Autocomplete already handles coordinate lookup when a user selects a place
  // The search form submission is mainly for user experience - the actual search happens via autocomplete
  // If you need to enable geocoding for direct address searches, enable the Geocoding API in Google Cloud Console
  
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
      icon: 'warning',
      title: 'Pro Feature',
      html: '<div style="font-size: 13px; margin: 6px 0; color: #6c757d;">Upgrade to access this feature</div>',
      showConfirmButton: true,
      confirmButtonText: 'Try Pro',
      confirmButtonColor: '#667eea',
      showCancelButton: false,
      showCloseButton: true,
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
        
        // Style the close button (X)
        const closeButton = toast.querySelector('.swal2-close');
        if (closeButton) {
          closeButton.style.color = '#6c757d';
          closeButton.style.fontSize = '18px';
          closeButton.style.fontWeight = '600';
          closeButton.style.opacity = '0.7';
          closeButton.style.transition = 'opacity 0.2s ease';
          closeButton.style.cursor = 'pointer';
          
          // Add hover effect to close button
          closeButton.addEventListener('mouseenter', () => {
            closeButton.style.opacity = '1';
            closeButton.style.color = '#dc3545';
          });
          closeButton.addEventListener('mouseleave', () => {
            closeButton.style.opacity = '0.7';
            closeButton.style.color = '#6c757d';
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

  // Use the new openPlanningModal method
  window.routePlanner.openPlanningModal();
}



// Expose functions globally
window.openRoutePanel = openRoutePanel;
window.showProUpgradeToast = showProUpgradeToast;
window.initUI = initUI;

// Fallback: ensure UI wiring after DOM is ready (idempotent)
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => {
    try { window.initUI(); } catch(e) { console.error('[map-ui] initUI DOMContentLoaded error', e); }
  });
} else {
  try { window.initUI(); } catch(e) { console.error('[map-ui] initUI immediate error', e); }
}

// Expose function to sync slider visibility
window.syncSliderVisibility = function() {
  const filterPopularAreas = document.getElementById('filter-popular-areas');
  const filterEvents = document.getElementById('filter-events');
  
  const filters = {
    showPopular: filterPopularAreas ? filterPopularAreas.checked : false,
    showEvents: filterEvents ? filterEvents.checked : false
  };
  if (window.__TM_DEBUG__) console.log('[map-ui] syncSliderVisibility called with filters:', filters);
  (window.updateFilterUI || function(){ })(filters);
};

// Dynamic Drawer Height Adjustment
function initializeDynamicDrawerHeight() {
  const legend = document.getElementById('legend');
  const filterPopularAreas = document.getElementById('filter-popular-areas');
  const filterEvents = document.getElementById('filter-events');
  
  if (!legend || !filterPopularAreas || !filterEvents) return;
  
  function adjustDrawerHeight() {
    const isMobile = window.innerWidth <= 768;
    if (!isMobile) return;
    
    // Reset to auto height to let content determine size
    legend.style.height = 'auto';
    
    // Force a reflow to get accurate measurements
    legend.offsetHeight;
    
    // Get the actual content height
    const contentHeight = legend.scrollHeight;
    const footerHeight = 50; // Account for footer space
    const maxHeight = window.innerHeight - footerHeight - 20; // Leave space for footer and padding
    
    // Set height to content size, but cap at max height
    const finalHeight = Math.min(contentHeight, maxHeight);
    legend.style.height = finalHeight + 'px';

    // If content exceeds max height, enable scrolling
    if (contentHeight > maxHeight) {
      legend.style.overflowY = 'auto';
    } else {
      legend.style.overflowY = 'visible';
    }

    // Let adjustMapHeight handle the map sizing
    // Just trigger a map height adjustment
    setTimeout(() => {
      adjustMapHeight();
    }, 50);

    console.log('[map-ui] Adjusted drawer height to', finalHeight + 'px', 'content height:', contentHeight, 'max height:', maxHeight, 'footer space:', footerHeight);
  }
  
  // Listen for checkbox changes
  filterPopularAreas.addEventListener('change', adjustDrawerHeight);
  filterEvents.addEventListener('change', adjustDrawerHeight);

  // Listen for drawer toggle changes
  const mobileDrawerHandle = document.getElementById('mobile-drawer-handle');
  if (mobileDrawerHandle) {
    mobileDrawerHandle.addEventListener('click', function() {
      // Wait for the transition to complete before adjusting
      setTimeout(adjustDrawerHeight, 300);
    });
  }

  // Initial adjustment
  adjustDrawerHeight();
}

// Mobile Drawer Functionality - Collapsible
function initializeMobileDrawer() {
  const legend = document.getElementById('legend');
  const handle = document.getElementById('mobile-drawer-handle');
  
  if (!legend || !handle) return;
  
  // Check if we're on mobile
  const isMobile = window.innerWidth <= 768;
  
  if (isMobile) {
    // Add mobile-specific classes
    legend.classList.add('mobile-drawer', 'mobile-expanded');
    
    // Add click handler to toggle drawer
    handle.addEventListener('click', () => {
      toggleMobileDrawer();
    });
    
    // Add touch handler for better mobile experience
    handle.addEventListener('touchstart', (e) => {
      e.preventDefault();
      toggleMobileDrawer();
    });
    
    // Initialize map height after a short delay to ensure DOM is ready
    setTimeout(() => {
      adjustMapHeight();
      forceInlineSliders();
    }, 100);
    
    console.log('[map-ui] Mobile drawer initialized with collapse functionality');
  }
}

// Toggle mobile drawer between collapsed and expanded
function toggleMobileDrawer() {
  const legend = document.getElementById('legend');
  if (!legend) return;
  
  const isCollapsed = legend.classList.contains('mobile-collapsed');
  
  if (isCollapsed) {
    // Expand drawer
    legend.classList.remove('mobile-collapsed');
    legend.classList.add('mobile-expanded');
    console.log('[map-ui] Mobile drawer expanded');
  } else {
    // Collapse drawer
    legend.classList.remove('mobile-expanded');
    legend.classList.add('mobile-collapsed');
    console.log('[map-ui] Mobile drawer collapsed');
  }
  
  // Adjust map height after drawer state change
  adjustMapHeight();
  
  // Force sliders to stay inline on mobile
  forceInlineSliders();
}

// Force sliders to stay inline on mobile
function forceInlineSliders() {
  const isMobile = window.innerWidth <= 768;
  if (!isMobile) return;
  
  const heatmapContainer = document.getElementById('heatmap-days-slider-container');
  const eventContainer = document.getElementById('event-days-slider-container');
  
  console.log('[map-ui] forceInlineSliders called', {
    isMobile,
    heatmapContainer: !!heatmapContainer,
    eventContainer: !!eventContainer,
    heatmapDisplay: heatmapContainer ? heatmapContainer.style.display : 'not found',
    eventDisplay: eventContainer ? eventContainer.style.display : 'not found'
  });
  
  if (heatmapContainer) {
    heatmapContainer.style.display = 'flex';
    heatmapContainer.style.flexDirection = 'row';
    console.log('[map-ui] Set heatmap container to flex');
  }
  
  if (eventContainer) {
    eventContainer.style.display = 'flex';
    eventContainer.style.flexDirection = 'row';
    console.log('[map-ui] Set event container to flex');
  }
  
  // Force labels with sliders to use flex layout
  const heatmapLabel = document.querySelector('label[data-has-slider="true"]:has(#heatmap-days-slider-container)');
  const eventLabel = document.querySelector('label[data-has-slider="true"]:has(#event-days-slider-container)');
  
  // Fallback for browsers that don't support :has()
  const heatmapLabelFallback = document.querySelector('label[data-has-slider="true"]');
  const eventLabelFallback = document.querySelectorAll('label[data-has-slider="true"]')[1];
  
  const labelsToFix = [heatmapLabel, eventLabel, heatmapLabelFallback, eventLabelFallback].filter(Boolean);
  
  labelsToFix.forEach(label => {
    if (label) {
      label.style.display = 'flex';
      label.style.alignItems = 'center';
      label.style.flexWrap = 'nowrap';
      label.style.width = '100%';
      console.log('[map-ui] Applied flex styling to label:', label);
    }
  });
}

// Adjust map height based on drawer state
function adjustMapHeight() {
  const isMobile = window.innerWidth <= 768;
  if (!isMobile) return; // Only adjust on mobile
  
  const legend = document.getElementById('legend');
  const map = document.getElementById('map');
  
  if (!legend || !map) return;
  
  const isCollapsed = legend.classList.contains('mobile-collapsed');
  
  if (isCollapsed) {
    // Collapsed: map gets almost full height
    const collapsedHeight = window.innerHeight - 20 - 50; // 20px drawer + 50px footer
    map.style.height = collapsedHeight + 'px';
    map.style.maxHeight = collapsedHeight + 'px';
    console.log('[map-ui] Map height adjusted for collapsed drawer:', collapsedHeight + 'px');
  } else {
    // Expanded: map gets reduced height
    const legendHeight = legend.offsetHeight;
    const expandedHeight = window.innerHeight - legendHeight - 50; // legend height + 50px footer
    map.style.height = expandedHeight + 'px';
    map.style.maxHeight = expandedHeight + 'px';
    console.log('[map-ui] Map height adjusted for expanded drawer:', expandedHeight + 'px');
  }
  
  // Trigger map resize to ensure proper rendering (but not if info window is open)
  if (window.map && typeof window.map.panToBounds === 'function' && !window.currentOpenMarker) {
    setTimeout(() => {
      google.maps.event.trigger(window.map, 'resize');
    }, 100);
  }
}

// Don't auto-initialize - let map-init.js handle it
// if (document.readyState === 'loading') {
//   document.addEventListener('DOMContentLoaded', initUI);
// } else {
//   initUI();
// }
// touch