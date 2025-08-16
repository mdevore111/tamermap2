/**
 * Route Planner Module
 * Handles route planning functionality with SweetAlert2 modal interface
 * Now supports wizard-style flow: Planning -> Preview -> Execute
 */

class RoutePlanner {
    constructor() {
        this.selectedLocations = [];
        this.previewPins = [];
        this.maxDistance = 25; // default miles (max 50)
        this.maxStops = 5;
        this.mergeThresholdMeters = 60; // base merge radius in meters (nearby duplicates)
        this.mergeSameNameBoostMeters = 250; // looser radius when names match (big-footprint venues)
        this.isInitialized = false;
        this.currentStep = 'planning'; // 'planning', 'preview', 'execute'
        // Use localStorage to persist preferences across sessions
        this.sessionKey = 'routePlannerPreferences';
        // Store all checkbox/toggle preferences here
        this.sessionCheckboxStates = {
            roundTrip: false,
            openNow: false,
            leastPopular: false,
            mostPopular: false,
            kiosk: true,
            retail: true,
            indie: false,
            mergeNearby: true
        };
    }

    /**
     * Merge nearby duplicate locations (same venue kiosk + retail, minor coord differences)
     * Returns a new array with merged representatives.
     */
    mergeNearbyLocations(locations, thresholdMeters = 60) {
        if (!Array.isArray(locations) || locations.length <= 1) return locations || [];

        const degPerMeter = 1 / 111320; // rough conversion at mid-latitude
        // Use the largest possible merge radius for bucketing so we don't miss candidates
        const maxMergeMeters = Math.max(thresholdMeters, this.mergeSameNameBoostMeters);
        const cellSizeDeg = maxMergeMeters * degPerMeter;

        const normalizeName = (name = '') => {
            const base = (name || '').toLowerCase().trim()
                .replace(/[^a-z0-9\s]/g, '')
                .replace(/\s+-\s+[a-z\s,]*$/i, '')
                .replace(/\s+/g, ' ');
            // Keep first two tokens to collapse variants like "fred meyer fuel center"
            const tokens = base.split(' ').filter(Boolean);
            return tokens.slice(0, 2).join(' ');
        };

        const normalizeStreet = (addr = '') => {
            if (!addr) return '';
            const firstLine = addr.toLowerCase().split(',')[0];
            // Remove unit/suite
            let s = firstLine.replace(/\b(ste|suite|unit|bldg|building)\b\s*[^\s]+/g, '')
                             .replace(/#/g, ' ');
            // Normalize common abbreviations
            const reps = [
                [/\bst\.?\b/g, ' street'],
                [/\brd\.?\b/g, ' road'],
                [/\bave\.?\b/g, ' avenue'],
                [/\bblvd\.?\b/g, ' boulevard'],
                [/\bpkwy\.?\b/g, ' parkway'],
                [/\bhwy\.?\b/g, ' highway'],
                [/\bctr\.?\b/g, ' center']
            ];
            reps.forEach(([re, to]) => { s = s.replace(re, to); });
            s = s.replace(/[^a-z0-9\s]/g, ' ').replace(/\s+/g, ' ').trim();
            return s;
        };

        // Precompute quick-identity keys
        const nameStreetKey = new Map();
        const placeIdGroups = new Map();
        locations.forEach((loc, i) => {
            const nk = normalizeName(loc.retailer);
            const sk = normalizeStreet(loc.address);
            if (nk && sk) {
                const key = `${nk}|${sk}`;
                if (!nameStreetKey.has(key)) nameStreetKey.set(key, []);
                nameStreetKey.get(key).push(i);
            }
            if (loc.place_id) {
                const pid = String(loc.place_id);
                if (!placeIdGroups.has(pid)) placeIdGroups.set(pid, []);
                placeIdGroups.get(pid).push(i);
            }
        });

        // Union by identical place_id first
        const parent = new Array(locations.length).fill(0).map((_, i) => i);
        const find = (i) => (parent[i] === i ? i : (parent[i] = find(parent[i])));
        const union = (i, j) => { const pi = find(i), pj = find(j); if (pi !== pj) parent[pi] = pj; };
        placeIdGroups.forEach(indices => { if (indices.length > 1) { const head = indices[0]; indices.slice(1).forEach(j => union(head, j)); } });

        // Union by identical (normalized name, normalized street)
        nameStreetKey.forEach(indices => { if (indices.length > 1) { const head = indices[0]; indices.slice(1).forEach(j => union(head, j)); } });

        // Bucket by geocell to limit pair checks (proximity-based union)
        const buckets = new Map();
        locations.forEach((loc, idx) => {
            const cellX = Math.floor(loc.lng / cellSizeDeg);
            const cellY = Math.floor(loc.lat / cellSizeDeg);
            const key = `${cellX}:${cellY}`;
            if (!buckets.has(key)) buckets.set(key, []);
            buckets.get(key).push({ loc, idx });
        });

        const haversineMeters = (a, b) => {
            const R = 6371000; // meters
            const toRad = (d) => d * Math.PI / 180;
            const dLat = toRad(b.lat - a.lat);
            const dLng = toRad(b.lng - a.lng);
            const lat1 = toRad(a.lat);
            const lat2 = toRad(b.lat);
            const h = Math.sin(dLat/2)**2 + Math.cos(lat1) * Math.cos(lat2) * Math.sin(dLng/2)**2;
            return 2 * R * Math.asin(Math.sqrt(h));
        };

        const getNeighbors = (cellX, cellY) => {
            const arr = [];
            for (let dx = -1; dx <= 1; dx++) {
                for (let dy = -1; dy <= 1; dy++) {
                    const key = `${cellX+dx}:${cellY+dy}`;
                    if (buckets.has(key)) arr.push(...buckets.get(key));
                }
            }
            return arr;
        };

        // Union duplicates within threshold and with similar venue identity
        buckets.forEach((items, key) => {
            const [xStr, yStr] = key.split(':');
            const cx = parseInt(xStr, 10), cy = parseInt(yStr, 10);
            const candidates = getNeighbors(cx, cy);
            items.forEach(({ loc, idx }) => {
                const baseName = normalizeName(loc.retailer);
                candidates.forEach(({ loc: other, idx: j }) => {
                    if (idx === j) return;
                    const dist = haversineMeters({ lat: loc.lat, lng: loc.lng }, { lat: other.lat, lng: other.lng });
                    const otherName = normalizeName(other.retailer);
                    const sameName = baseName && baseName === otherName;
                    const samePlace = loc.place_id && other.place_id && (loc.place_id === other.place_id);
                    const addrA = (loc.address || '').toLowerCase();
                    const addrB = (other.address || '').toLowerCase();
                    const streetA = addrA.split(',')[0].trim();
                    const streetB = addrB.split(',')[0].trim();
                    const similarAddress = streetA && streetA === streetB;

                    // Dynamic threshold: allow larger radius for strong identity matches (same name or place)
                    const dynamicThreshold = (sameName || samePlace || similarAddress) ? Math.max(thresholdMeters, this.mergeSameNameBoostMeters) : thresholdMeters;
                    if (dist <= dynamicThreshold && (sameName || samePlace || similarAddress)) {
                        union(idx, j);
                    }
                });
            });
        });

        // Group by parent and build representatives
        const groups = new Map();
        locations.forEach((loc, i) => {
            const p = find(i);
            if (!groups.has(p)) groups.set(p, []);
            groups.get(p).push(loc);
        });

        const representativeOf = (group) => {
            const preferScore = (g) => {
                let score = 0;
                if (g.place_id) score += 100; // Strongly prefer entries with a valid place_id
                if (g.opening_hours) score += 3;
                const type = (g.retailer_type || '').toLowerCase();
                if (type.includes('store')) score += 2; else if (type.includes('kiosk')) score += 1;
                if (window.userCoords && typeof g.distance === 'number') score += Math.max(0, 1 - (g.distance / 100));
                return score;
            };
            let best = group[0];
            let bestScore = -Infinity;
            group.forEach(g => { const s = preferScore(g); if (s > bestScore) { best = g; bestScore = s; } });
            const types = [...new Set(group.flatMap(g => String(g.retailer_type || '').split('+').map(t => t.trim())).filter(Boolean))];
            return {
                ...best,
                retailer_type: types.join(' + '),
                mergedFrom: group
            };
        };

        const merged = [];
        groups.forEach((group) => {
            if (group.length === 1) { merged.push(group[0]); }
            else { merged.push(representativeOf(group)); }
        });

        // Recompute distance for merged representatives because we may have chosen coords from a member
        if (window.userCoords) {
            merged.forEach(m => {
                m.distance = this.calculateDistance(window.userCoords.lat, window.userCoords.lng, m.lat, m.lng);
            });
        }

        return merged;
    }

    /**
     * Initialize the route planner
     */
    async initialize() {
        if (this.isInitialized) return;
        
        if (window.__TM_DEBUG__) console.log('Initializing Route Planner...');
        this.initializeUI();
        this.loadPreferences();
        this.isInitialized = true;
    }

    /**
     * Load preferences from localStorage
     */
    loadPreferences() {
        try {
            const raw = localStorage.getItem(this.sessionKey);
            if (raw) {
                const data = JSON.parse(raw);
                this.maxDistance = Number.isFinite(data.maxDistance) ? data.maxDistance : 25;
                this.maxStops = Number.isInteger(data.maxStops) ? data.maxStops : 5;
                this.sessionCheckboxStates = {
                    roundTrip: !!data.checkboxStates?.roundTrip,
                    openNow: !!data.checkboxStates?.openNow,
                    leastPopular: !!data.checkboxStates?.leastPopular,
                    mostPopular: !!data.checkboxStates?.mostPopular,
                    kiosk: data.checkboxStates?.kiosk !== undefined ? !!data.checkboxStates.kiosk : true,
                    retail: data.checkboxStates?.retail !== undefined ? !!data.checkboxStates.retail : true,
                    indie: data.checkboxStates?.indie !== undefined ? !!data.checkboxStates.indie : false,
                    mergeNearby: data.checkboxStates?.mergeNearby !== undefined ? !!data.checkboxStates.mergeNearby : true
                };
                if (window.__TM_DEBUG__) console.log('Loaded preferences:', {
                    maxDistance: this.maxDistance,
                    maxStops: this.maxStops,
                    checkboxStates: this.sessionCheckboxStates
                });
            } else {
                if (window.__TM_DEBUG__) console.log('No stored preferences found; using defaults');
                this.maxDistance = 25;
                this.maxStops = 5;
                this.sessionCheckboxStates = {
                    roundTrip: false,
                    openNow: false,
                    leastPopular: false,
                    mostPopular: false,
                    kiosk: true,
                    retail: true,
                    indie: false,
                    mergeNearby: true
                };
            }
        } catch (error) {
            if (window.__TM_DEBUG__) console.warn('Failed to load route planner preferences:', error);
        }
    }

    /**
     * Save preferences to localStorage
     */
    savePreferences() {
        try {
            const sessionData = {
                maxDistance: this.maxDistance,
                maxStops: this.maxStops,
                checkboxStates: this.sessionCheckboxStates,
                timestamp: Date.now()
            };
            if (window.__TM_DEBUG__) console.log('Saving route planner preferences', sessionData);
            localStorage.setItem(this.sessionKey, JSON.stringify(sessionData));
        } catch (error) {
            if (window.__TM_DEBUG__) console.warn('Failed to save route planner preferences:', error);
        }
    }

    /**
     * Get current checkbox states
     */
    getCurrentCheckboxStates() {
        // Return in-memory state to avoid DOM dependency
        return { ...this.sessionCheckboxStates };
    }

    /**
     * Clear preferences (Reset to Defaults handler will call this)
     */
    clearSessionData() {
        try {
            localStorage.removeItem(this.sessionKey);
        } catch (error) {
            if (window.__TM_DEBUG__) console.warn('Failed to clear route planner preferences:', error);
        }
    }

    /**
     * Initialize UI components
     */
    initializeUI() {
        // Set up SweetAlert2 modal configuration
        this.setupSweetAlert2Modal();
    }

    /**
     * Configure SweetAlert2 for route planning
     */
    setupSweetAlert2Modal() {
        this.swalConfig = {
            title: '<i class="fas fa-route"></i> Route Planner',
            html: this.createModalContent(),
            showConfirmButton: false,
            showCancelButton: false,
            showCloseButton: true,
            customClass: {
                popup: 'swal2-route-planner'
            },
            width: '560px',
            didOpen: () => {
                this.initializeModalControls();
            },
            willClose: () => {
                // Do not clear preferences on close; persist across sessions
                this.currentStep = 'planning';
            }
        };
    }

    /**
     * Create the modal content HTML
     */
    createModalContent() {
        return this.createControlsHTML();
    }

    /**
     * Create the controls HTML for the modal
     */
    createControlsHTML() {
        return `
            <div class="route-planner-container" style="font-size:13px; padding:6px 8px;">
                <!-- Distance Control -->
                <div class="route-control-group" style="margin:6px 0;">
                    <div style="display:flex; align-items:center; justify-content: space-between; margin-bottom:4px;">
                        <div style="font-weight:600;"><i class="fas fa-road"></i> Distance</div>
                        <div id="distance-value" style="color:#6c757d;">${this.maxDistance} miles</div>
                    </div>
                    <div class="route-slider-container" style="padding:0 2px;">
                        <label for="distance-slider" style="display:none">Max Distance</label>
                        <input type="range" id="distance-slider" class="route-slider" min="5" max="50" value="${this.maxDistance}" step="5" data-bs-toggle="tooltip" data-bs-placement="top" title="Limit the farthest store distance">
                    </div>
                </div>

                <!-- Stops Control -->
                <div class="route-control-group" style="margin:6px 0;">
                    <div style="display:flex; align-items:center; justify-content: space-between; margin-bottom:4px;">
                        <div style="font-weight:600;"><i class="fas fa-map-marker-alt"></i> Stops</div>
                        <div id="stops-value" style="color:#6c757d;">${this.maxStops}</div>
                    </div>
                    <div class="route-slider-container" style="padding:0 2px;">
                        <label for="stops-slider" style="display:none">Max Stops</label>
                        <input type="range" id="stops-slider" class="route-slider" min="2" max="10" value="${this.maxStops}" step="1" data-bs-toggle="tooltip" data-bs-placement="top" title="Number of stops to include">
                    </div>
                </div>

                <!-- Route Options + Popularity Segmented -->
                <div class="route-control-group" style="margin:8px 0;">
                    <div style="font-weight:600; margin-bottom:6px;"><i class="fas fa-cog"></i> Options</div>
                    <div style="display:flex; align-items:center; justify-content: space-between; gap:12px; flex-wrap:wrap;">
                        <div style="display:flex; align-items:center; gap:8px;">
                            <div style="min-width:70px; color:#6c757d;">Popularity</div>
                            <div id="popularity-segment" style="display:inline-flex; border:1px solid #ced4da; border-radius:8px; overflow:hidden;" data-bs-toggle="tooltip" data-bs-placement="top" title="Choose popularity filter">
                                <button type="button" id="popularity-off" style="padding:6px 10px; border:none; background:#f8f9fa; cursor:pointer;" data-bs-toggle="tooltip" data-bs-placement="top" title="No popularity filter">Off</button>
                                <button type="button" id="popularity-least" style="padding:6px 10px; border:none; background:#f8f9fa; cursor:pointer;" data-bs-toggle="tooltip" data-bs-placement="top" title="Prefer least popular">Least</button>
                                <button type="button" id="popularity-most" style="padding:6px 10px; border:none; background:#f8f9fa; cursor:pointer;" data-bs-toggle="tooltip" data-bs-placement="top" title="Prefer most popular">Most</button>
                            </div>
                        </div>
                        <div style="display:flex; gap:12px; align-items:center;">
                            <label class="route-checkbox" style="display:flex; gap:6px; align-items:center; margin:0;" data-bs-toggle="tooltip" data-bs-placement="top" title="Return to your start location at the end">
                            <input type="checkbox" id="round-trip-checkbox">
                            <span>Round Trip</span>
                        </label>
                            <label class="route-checkbox" style="display:flex; gap:6px; align-items:center; margin:0;" data-bs-toggle="tooltip" data-bs-placement="top" title="Only include locations currently open">
                            <input type="checkbox" id="open-now-checkbox">
                            <span>Open Now</span>
                        </label>
                            <label class="route-checkbox" style="display:flex; gap:6px; align-items:center; margin:0;" data-bs-toggle="tooltip" data-bs-placement="top" title="Merge multiple stops that are very close to each other into a single location">
                                <input type="checkbox" id="merge-nearby-checkbox">
                                <span>Merge Nearby</span>
                        </label>
                        </div>
                    </div>
                </div>

                <!-- Store Type Filters -->
                <div class="route-control-group" style="margin:8px 0;">
                    <div style="font-weight:600; margin-bottom:6px; text-align:center;"><i class="fas fa-filter"></i> Store Types</div>
                    <div class="route-filter-toggles" style="display:flex; gap:8px; flex-wrap:wrap; justify-content:center;">
                        <div class="route-filter-toggle" data-filter="kiosk" style="padding:6px 10px; border:1px solid #667eea; border-radius:8px; cursor:pointer; background:#ffffff; color:#667eea;" data-bs-toggle="tooltip" data-bs-placement="top" title="Include kiosks">
                            <i class="fas fa-robot"></i> Kiosk
                        </div>
                        <div class="route-filter-toggle" data-filter="retail" style="padding:6px 10px; border:1px solid #667eea; border-radius:8px; cursor:pointer; background:#ffffff; color:#667eea;" data-bs-toggle="tooltip" data-bs-placement="top" title="Include retail stores">
                            <i class="fas fa-store"></i> Retail
                        </div>
                        <div class="route-filter-toggle" data-filter="indie" style="padding:6px 10px; border:1px solid #667eea; border-radius:8px; cursor:pointer; background:#ffffff; color:#667eea;" data-bs-toggle="tooltip" data-bs-placement="top" title="Include indie/card shops">
                            <i class="fas fa-heart"></i> Indie
                        </div>
                    </div>
                </div>

                <!-- Quick Picks -->
                <div class="route-control-group" style="margin:6px 0;">
                    <div style="font-weight:600; margin-bottom:6px; text-align:center;"><i class="fas fa-bolt"></i> Quick Picks</div>
                    <div style="display:flex; flex-wrap:wrap; justify-content:center; gap:8px;">
                        <button type="button" class="route-quick-pick" data-pick="kiosk5" style="padding:6px 10px; background:#eef2ff; color:#3b5bdb; border:none; border-radius:8px; cursor:pointer;">Nearest 5 Kiosks</button>
                        <button type="button" class="route-quick-pick" data-pick="retail5" style="padding:6px 10px; background:#e6fcf5; color:#087f5b; border:none; border-radius:8px; cursor:pointer;">Nearest 5 Stores</button>
                        <button type="button" class="route-quick-pick" data-pick="balanced5" style="padding:6px 10px; background:#fff4e6; color:#d9480f; border:none; border-radius:8px; cursor:pointer;">Balanced 5</button>
                    </div>
                </div>

                <!-- Wizard Navigation Buttons -->
                <div class="route-actions" style="display:flex; align-items:center; gap:8px; margin-top:8px;">
                    <button type="button" class="route-btn route-btn-secondary" id="modal-back-to-map-btn" data-bs-toggle="tooltip" data-bs-placement="top" title="Close planner and return to map">
                        <i class="fas fa-chevron-left"></i> Map
                    </button>
                    <button type="button" class="route-btn route-btn-primary" id="modal-preview-route-btn" data-bs-toggle="tooltip" data-bs-placement="top" title="Preview your stops on the map" style="background:#667eea; color:#fff; border:none; padding:8px 14px; border-radius:8px;">
                        Preview <i class="fas fa-chevron-right"></i>
                    </button>
                    <button type="button" class="route-btn route-btn-secondary" id="modal-reset-route-btn" style="margin-left:auto;" data-bs-toggle="tooltip" data-bs-placement="top" title="Reset all preferences to defaults">
                        Reset
                    </button>
                </div>

                <!-- Route Summary -->
                <div class="route-summary" id="route-summary" style="margin-top:8px;">
                    <div id="summary-content" style="max-height: 180px; overflow-y: auto; padding-right: 6px; color:#2c3e50;">
                        <small style="color:#6c757d;">Configure your preferences above to see route details.</small>
                    </div>
                </div>
            </div>
        `;
    }

    /**
     * Initialize modal controls after SweetAlert2 opens
     */
    initializeModalControls() {
        // Distance slider
        const distanceSlider = document.getElementById('distance-slider');
        const distanceValue = document.getElementById('distance-value');
        
        if (distanceSlider) {
            let distanceTimeout;
            distanceSlider.addEventListener('input', (e) => {
                this.maxDistance = parseInt(e.target.value);
                distanceValue.textContent = `${this.maxDistance} miles`;
                
                // Debounce the update to prevent rapid recalculations
                clearTimeout(distanceTimeout);
                distanceTimeout = setTimeout(() => {
                    this.updateDistanceDisplay();
                }, 100);
            });
        }

        // Stops slider
        const stopsSlider = document.getElementById('stops-slider');
        const stopsValue = document.getElementById('stops-value');
        
        if (stopsSlider) {
            let stopsTimeout;
            stopsSlider.addEventListener('input', (e) => {
                this.maxStops = parseInt(e.target.value);
                stopsValue.textContent = this.maxStops;
                
                // Debounce the update to prevent rapid recalculations
                clearTimeout(stopsTimeout);
                stopsTimeout = setTimeout(() => {
                    this.updateStopsDisplay();
                }, 100);
            });
        }

        // Initialize option controls
        const roundTripCheckbox = document.getElementById('round-trip-checkbox');
        const openNowCheckbox = document.getElementById('open-now-checkbox');
        const popularityOffBtn = document.getElementById('popularity-off');
        const popularityLeastBtn = document.getElementById('popularity-least');
        const popularityMostBtn = document.getElementById('popularity-most');
        const mergeNearbyCheckbox = document.getElementById('merge-nearby-checkbox');
        
        // Restore checkbox states from session data if available
        if (window.__TM_DEBUG__) console.log('Restoring session state', this.sessionCheckboxStates);
        
        if (this.sessionCheckboxStates) {
            console.log('Restoring option states from preferences...');
            if (roundTripCheckbox) roundTripCheckbox.checked = !!this.sessionCheckboxStates.roundTrip;
            if (openNowCheckbox) openNowCheckbox.checked = !!this.sessionCheckboxStates.openNow;
            if (mergeNearbyCheckbox) mergeNearbyCheckbox.checked = !!this.sessionCheckboxStates.mergeNearby;
            // Set segmented control selection
            const mode = this.sessionCheckboxStates.mostPopular
                ? 'most'
                : this.sessionCheckboxStates.leastPopular
                ? 'least'
                : 'off';
            const setSegActive = (btn, active) => {
                if (!btn) return;
                btn.style.background = active ? '#667eea' : '#f8f9fa';
                btn.style.color = active ? '#fff' : '#212529';
                btn.style.border = active ? '1px solid #667eea' : '1px solid transparent';
            };
            setSegActive(popularityOffBtn, mode === 'off');
            setSegActive(popularityLeastBtn, mode === 'least');
            setSegActive(popularityMostBtn, mode === 'most');
        }
        
        // No legend fallback: planner is legend-agnostic
            
        // Add event listeners
        if (roundTripCheckbox) {
            roundTripCheckbox.addEventListener('change', () => {
                this.sessionCheckboxStates.roundTrip = !!roundTripCheckbox.checked;
                this.savePreferences();
                this.updateRouteSummary();
            });
        }

        if (openNowCheckbox) {
            openNowCheckbox.addEventListener('change', () => {
                this.sessionCheckboxStates.openNow = !!openNowCheckbox.checked;
                this.savePreferences();
                this.updateRouteSummary();
            });
        }
        if (mergeNearbyCheckbox) {
            mergeNearbyCheckbox.addEventListener('change', () => {
                this.sessionCheckboxStates.mergeNearby = !!mergeNearbyCheckbox.checked;
                this.savePreferences();
                this.updateRouteSummary();
            });
        }
        
        // Popularity segmented control handlers
        const setPopularityMode = (mode) => {
            this.sessionCheckboxStates.leastPopular = mode === 'least';
            this.sessionCheckboxStates.mostPopular = mode === 'most';
            const setSegActive = (btn, active) => {
                if (!btn) return;
                btn.style.background = active ? '#667eea' : '#f8f9fa';
                btn.style.color = active ? '#fff' : '#212529';
                btn.style.border = active ? '1px solid #667eea' : '1px solid transparent';
            };
            setSegActive(popularityOffBtn, mode === 'off');
            setSegActive(popularityLeastBtn, mode === 'least');
            setSegActive(popularityMostBtn, mode === 'most');
            this.savePreferences();
                this.updateRouteSummary();
        };
        if (popularityOffBtn) popularityOffBtn.addEventListener('click', () => setPopularityMode('off'));
        if (popularityLeastBtn) popularityLeastBtn.addEventListener('click', () => setPopularityMode('least'));
        if (popularityMostBtn) popularityMostBtn.addEventListener('click', () => setPopularityMode('most'));



        // Initialize filter toggles with session data restoration
        const filterToggles = document.querySelectorAll('.route-filter-toggle');
        let hasActiveFilter = false;
        
        filterToggles.forEach(toggle => {
            // Get the filter type from the data attribute
            const filterType = toggle.getAttribute('data-filter');
            console.log(`Processing filter toggle: ${filterType}`);
            
            // Restore state from preferences if available
            if (this.sessionCheckboxStates && filterType in this.sessionCheckboxStates) {
                // Session data exists for this filter type - use it regardless of true/false
                const shouldBeActive = this.sessionCheckboxStates[filterType];
                if (window.__TM_DEBUG__) console.log(`Restoring ${filterType} -> ${shouldBeActive ? 'active' : 'inactive'}`);
                if (shouldBeActive) {
                    toggle.classList.add('active');
                    toggle.style.background = '#667eea';
                    toggle.style.color = '#fff';
                    toggle.style.border = '1px solid #667eea';
                    hasActiveFilter = true;
                } else {
                    toggle.classList.remove('active');
                    toggle.style.background = '#ffffff';
                    toggle.style.color = '#667eea';
                    toggle.style.border = '1px solid #667eea';
                }
            } else {
                // No legend fallback; rely on defaults if not present in prefs
                if (window.__TM_DEBUG__) console.log(`No stored state for ${filterType}; using default`);
                const defaultActive = (filterType === 'kiosk' || filterType === 'retail');
                if (defaultActive) {
                toggle.classList.add('active');
                    toggle.style.background = '#667eea';
                    toggle.style.color = '#fff';
                    toggle.style.border = '1px solid #667eea';
                hasActiveFilter = true;
                    this.sessionCheckboxStates[filterType] = true;
                } else {
                    toggle.classList.remove('active');
                    toggle.style.background = '#ffffff';
                    toggle.style.color = '#667eea';
                    toggle.style.border = '1px solid #667eea';
                    this.sessionCheckboxStates[filterType] = false;
                }
            }
            
            // Add click handler that only updates route planner state
            toggle.addEventListener('click', () => {
                const willBeActive = !toggle.classList.contains('active');
                toggle.classList.toggle('active');
                this.sessionCheckboxStates[filterType] = willBeActive;
                // Apply visual theme
                if (willBeActive) {
                    toggle.style.background = '#667eea';
                    toggle.style.color = '#fff';
                    toggle.style.border = '1px solid #667eea';
                } else {
                    toggle.style.background = '#ffffff';
                    toggle.style.color = '#667eea';
                    toggle.style.border = '1px solid #667eea';
                }
                this.savePreferences();
                this.updateRouteSummary();
            });
        });
        
        // If no filters are active, activate the first one (kiosk) by default
        if (!hasActiveFilter && filterToggles.length > 0) {
            if (window.__TM_DEBUG__) console.log('No type filters active; defaulting kiosk on');
            const kioskToggle = Array.from(filterToggles).find(t => t.getAttribute('data-filter') === 'kiosk');
            if (kioskToggle) {
                kioskToggle.classList.add('active');
                this.sessionCheckboxStates.kiosk = true;
            }
        }

        // Reset button: clear preferences to defaults and re-render controls
        const resetBtn = document.getElementById('modal-reset-route-btn');
        if (resetBtn) {
            resetBtn.addEventListener('click', () => {
                this.maxDistance = 25;
                this.maxStops = 5;
                this.sessionCheckboxStates = {
                    roundTrip: false,
                    openNow: false,
                    leastPopular: false,
                    mostPopular: false,
                    kiosk: true,
                    retail: true,
                    indie: false
                };
                this.savePreferences();
                // Re-render the modal content to reflect defaults
                Swal.update({ html: this.createModalContent() });
                // Re-init controls and summary after update
                this.initializeModalControls();
            });
        }

        // Wizard Navigation Buttons
        const backToMapBtn = document.getElementById('modal-back-to-map-btn');
        const previewBtn = document.getElementById('modal-preview-route-btn');
        // Quick Picks
        const quickPickButtons = document.querySelectorAll('.route-quick-pick');

        if (backToMapBtn) {
            backToMapBtn.addEventListener('click', () => {
                this.savePreferences();
                Swal.close();
            });
        }

        if (previewBtn) {
            previewBtn.addEventListener('click', () => {
                this.savePreferences();
                this.showPreviewPins();
            });
        }

        if (quickPickButtons && quickPickButtons.length > 0) {
            quickPickButtons.forEach(btn => {
                btn.addEventListener('click', () => {
                    const pick = btn.getAttribute('data-pick');
                    if (pick === 'kiosk5') {
                        this.maxStops = 5;
                        this.maxDistance = 25;
                        this.sessionCheckboxStates.kiosk = true;
                        this.sessionCheckboxStates.retail = false;
                        this.sessionCheckboxStates.indie = false;
                        this.sessionCheckboxStates.roundTrip = false;
                        this.sessionCheckboxStates.openNow = false;
                        this.sessionCheckboxStates.leastPopular = false;
                        this.sessionCheckboxStates.mostPopular = false;
                    } else if (pick === 'retail5') {
                        this.maxStops = 5;
                        this.maxDistance = 25;
                        this.sessionCheckboxStates.kiosk = false;
                        this.sessionCheckboxStates.retail = true;
                        this.sessionCheckboxStates.indie = false;
                        this.sessionCheckboxStates.roundTrip = false;
                        this.sessionCheckboxStates.openNow = false;
                        this.sessionCheckboxStates.leastPopular = false;
                        this.sessionCheckboxStates.mostPopular = false;
                    } else if (pick === 'balanced5') {
                        this.maxStops = 5;
                        this.maxDistance = 25;
                        this.sessionCheckboxStates.kiosk = true;
                        this.sessionCheckboxStates.retail = true;
                        this.sessionCheckboxStates.indie = false;
                        this.sessionCheckboxStates.roundTrip = false;
                        this.sessionCheckboxStates.openNow = false;
                        this.sessionCheckboxStates.leastPopular = false;
                        this.sessionCheckboxStates.mostPopular = false;
                    } else if (pick === 'roundtrip') {
                        this.sessionCheckboxStates.roundTrip = true;
                    }
                    this.savePreferences();
                    Swal.update({ html: this.createModalContent() });
                    this.initializeModalControls();
                });
            });
        }

        // Update layout based on orientation
        this.updateLayoutOrientation();
        
        // Initial route summary update
        this.updateRouteSummary();
    }

    /**
     * Update layout based on screen orientation
     */
    updateLayoutOrientation() {
        // This could be enhanced to modify the modal layout based on orientation
        // For now, CSS handles the responsive design
    }

    /**
     * Update distance display (with debounced preview clear)
     */
    updateDistanceDisplay() {
        this.savePreferences();
        this.clearPreview(true); // Skip reopening modal to prevent bouncing
        this.updateRouteSummary();
    }

    /**
     * Update stops display (with debounced preview clear)
     */
    updateStopsDisplay() {
        this.savePreferences();
        this.clearPreview(true); // Skip reopening modal to prevent bouncing
        this.updateRouteSummary();
    }

    /**
     * Update route summary
     */
    updateRouteSummary() {
        if (window.__TM_DEBUG__) console.log('Update route summary');
        const summaryContent = document.getElementById('summary-content');
        const routeSummary = document.getElementById('route-summary');
        
        if (!summaryContent) {
            if (window.__TM_DEBUG__) console.warn('Summary content element not found');
            return;
        }

        // Always show the route summary container to maintain consistent width
        if (routeSummary) {
            routeSummary.style.display = 'block';
        }

        // Check if any store type filters are active
        const toggles = document.querySelectorAll('.route-filter-toggle');
        const activeFilters = Array.from(toggles).filter(toggle => toggle.classList.contains('active'));
        
        if (activeFilters.length === 0) {
            if (window.__TM_DEBUG__) console.log('No type filters active; empty route summary');
            summaryContent.innerHTML = '<div style="min-height: 60px; display: flex; align-items: center;"><small style="color: #6c757d;">Select store types to see route details.</small></div>';
            return;
        }

        if (!window.userCoords) {
            if (window.__TM_DEBUG__) console.log('No user coordinates for route summary');
            summaryContent.innerHTML = 
                '<div style="min-height: 60px; display: flex; align-items: center;"><small style="color: #dc3545;">Location access required for route planning.</small></div>';
            return;
        }

        // Get current settings
        const roundTrip = !!this.sessionCheckboxStates.roundTrip;
        const openNow = !!this.sessionCheckboxStates.openNow;
        const leastPopular = !!this.sessionCheckboxStates.leastPopular;
        const mostPopular = !!this.sessionCheckboxStates.mostPopular;
        
        if (window.__TM_DEBUG__) console.log('Summary settings', { roundTrip, openNow });
        
        // Debug: Log available data sources
        if (window.__TM_DEBUG__) console.log('Data sources snapshot', {
            userCoords: window.userCoords,
            allMarkers: window.allMarkers?.length || 0,
            markerManager: !!window.markerManager,
            markerCache: window.markerManager?.markerCache?.size || 0,
            dataService: !!window.dataService,
            dataCache: window.dataService?.cache?.size || 0,
        });
        
        // Additional debugging for markerManager
        if (window.markerManager) {
            if (window.__TM_DEBUG__) {
            console.log('- markerManager.markerCache keys:', Array.from(window.markerManager.markerCache?.keys() || []));
            console.log('- markerManager.markerCache values sample:', Array.from(window.markerManager.markerCache?.values() || []).slice(0, 3));
            }
        }
        
        // Additional debugging for dataService
        if (window.dataService && window.dataService.cache) {
            if (window.__TM_DEBUG__ && window.dataService?.cache) {
            console.log('- dataService.cache entries:');
                window.dataService.cache.forEach((value, key) => console.log(`  - ${key}:`, value));
            }
        }
        
        // Get available locations and apply filters
        if (window.__TM_DEBUG__) console.log('Getting filtered locations...');
        // Capture pre-merge count for UI notice
        const beforeMergeCount = this.getFilteredLocations(openNow, leastPopular, mostPopular).length;
        let availableLocations = this.getFilteredLocations(openNow, leastPopular, mostPopular);
        // Merge nearby duplicates when enabled (e.g., kiosk + retail within the same venue)
        if (this.sessionCheckboxStates.mergeNearby) {
            availableLocations = this.mergeNearbyLocations(availableLocations, this.mergeThresholdMeters);
        }
        const afterMergeCount = availableLocations.length;
        if (window.__TM_DEBUG__) console.log('availableLocations after filtering:', availableLocations.length);
        if (window.__TM_DEBUG__) console.log('availableLocations sample:', availableLocations.slice(0, 3));
        
        const optimalLocations = this.selectOptimalLocations(availableLocations);
        if (window.__TM_DEBUG__) console.log('optimalLocations selected:', optimalLocations.length);
        
        if (optimalLocations.length === 0) {
            if (window.__TM_DEBUG__) console.log('No optimal locations found');
            // Provide more helpful feedback
            let message = 'No locations found matching your criteria.';
            if (availableLocations.length === 0) {
                message += ' Try adjusting your distance or store type filters.';
            } else {
                message += ' Try increasing the number of stops.';
            }
            summaryContent.innerHTML = `<div style="min-height: 60px; display: flex; align-items: center;"><small style="color: #dc3545;">${message}</small></div>`;
            return;
        }

        const storeItems = optimalLocations.map(loc => {
            const openNow = (typeof window.isOpenNow === 'function') && window.isOpenNow(loc.opening_hours);
            return `<li style="margin:6px 0;">
                ${this.formatStopLine(loc, openNow)}
            </li>`;
        }).join('');

        // Build compact filter badges
        const pills = [];
        if (roundTrip) pills.push('<span style="display:inline-block; padding:2px 8px; border-radius:12px; background:#eef2ff; color:#3b5bdb; font-size:12px; margin-right:6px;">Round trip</span>');
        if (openNow) pills.push('<span style="display:inline-block; padding:2px 8px; border-radius:12px; background:#e6fcf5; color:#087f5b; font-size:12px; margin-right:6px;">Open now only</span>');
        if (leastPopular) pills.push('<span style="display:inline-block; padding:2px 8px; border-radius:12px; background:#fff4e6; color:#d9480f; font-size:12px; margin-right:6px;">Least popular</span>');
        if (mostPopular) pills.push('<span style="display:inline-block; padding:2px 8px; border-radius:12px; background:#ffe8cc; color:#d9480f; font-size:12px; margin-right:6px;">Most popular</span>');
        const filterDescription = pills.join('');
        // Merge notice (optional transparency)
        let mergeNotice = '';
        if (this.sessionCheckboxStates.mergeNearby && beforeMergeCount > afterMergeCount) {
            const mergedGroups = availableLocations.filter(l => Array.isArray(l.mergedFrom) && l.mergedFrom.length > 1);
            const mergedCount = beforeMergeCount - afterMergeCount;
            if (mergedCount > 0 && mergedGroups.length > 0) {
                const details = mergedGroups.slice(0, 5).map(g => {
                    const title = this.cleanRetailerName(g.retailer || 'Unknown', g.retailer_type, g.address);
                    const members = g.mergedFrom.map(m => this.cleanRetailerName(m.retailer || 'Unknown', m.retailer_type, m.address)).join(', ');
                    return `<div style=\"margin:2px 0;\"><em>${title}</em><br><small style=\"color:#6c757d;\">${members}</small></div>`;
                }).join('');
                mergeNotice = `
                    <div style=\"margin:6px 0 4px; color:#495057;\">
                        <small><strong>Merged ${mergedCount} nearby entries</strong> to avoid duplicates.</small>
                        <details style=\"margin-top:2px;\">
                            <summary style=\"cursor:pointer; color:#667eea;\">View merged</summary>
                            ${details}
                        </details>
                    </div>
                `;
            }
        }
        
        summaryContent.innerHTML = `
            <div>
                <div style="margin-bottom:6px;">
                    <strong>${optimalLocations.length} stops</strong> within ${this.maxDistance} miles
                </div>
                <div style="margin:-2px 0 8px; color:#6c757d;"><small>Note: Stops may be reordered for an optimal route.</small></div>
                <div style="margin-bottom:6px;">${filterDescription || ''}</div>
                ${mergeNotice}
                <ol style="padding-left:18px; margin:6px 0;">${storeItems}</ol>
            </div>
        `;
    }

    /**
     * Get filtered locations based on current settings
     */
    getFilteredLocations(openNow = false, leastPopular = false, mostPopular = false) {
        console.log('=== GET FILTERED LOCATIONS DEBUG ===');
        console.log('1. openNow parameter:', openNow);
        console.log('2. leastPopular parameter:', leastPopular);
        console.log('3. mostPopular parameter:', mostPopular);
        console.log('4. userCoords available:', !!window.userCoords);
        console.log('5. userCoords value:', window.userCoords);
        
        if (!window.userCoords) {
            console.log('ERROR: No user coordinates available');
            return [];
        }

        // Try different data sources in order of preference
        let locations = [];
        let dataSource = 'none';
        
        console.log('6. Checking data sources...');
        
        // First try window.allMarkers (from MarkerManager)
        if (window.allMarkers && window.allMarkers.length > 0) {
            // Convert Google Maps Marker objects to location data objects
            locations = window.allMarkers.map(marker => {
                const position = marker.getPosition();
                return {
                    lat: position.lat(),
                    lng: position.lng(),
                    retailer: marker.getTitle() || 'Unknown',
                    retailer_type: marker.retailer_type || 'unknown',
                    opening_hours: marker.opening_hours || null,
                    address: marker.address || null,
                    phone: marker.phone || null,
                    place_id: marker.place_id || null
                };
            });
            dataSource = 'allMarkers';
            console.log(`5. SUCCESS: Using data source: allMarkers (${locations.length} locations)`);
            console.log('6. Sample location:', locations[0]);
            console.log('7. First 3 locations:', locations.slice(0, 3));
            
            // Debug: Show retailer type distribution
            const typeCounts = {};
            locations.forEach(loc => {
                const type = loc.retailer_type || 'unknown';
                typeCounts[type] = (typeCounts[type] || 0) + 1;
            });
            console.log('8. Retailer type distribution:', typeCounts);
        }
        // Fallback to markerManager.markerCache if available
        else if (window.markerManager && window.markerManager.markerCache && window.markerManager.markerCache.size > 0) {
            const markerCache = Array.from(window.markerManager.markerCache.values());
            // Normalize markers → plain location objects with lat/lng
            locations = markerCache
                .filter(marker => marker.retailer_type) // Only retailer markers
                .map(marker => {
                    const pos = marker.getPosition && marker.getPosition();
                    const rd = marker.retailer_data || {};
                    return {
                        lat: pos ? pos.lat() : parseFloat(rd.latitude),
                        lng: pos ? pos.lng() : parseFloat(rd.longitude),
                        retailer: rd.retailer || marker.getTitle?.() || 'Unknown',
                        retailer_type: (marker.retailer_type || rd.retailer_type || 'unknown'),
                        opening_hours: rd.opening_hours || marker.opening_hours || null,
                        address: rd.full_address || marker.address || null,
                        phone: rd.phone_number || marker.phone || null,
                        place_id: rd.place_id || marker.place_id || null
                    };
                })
                .filter(loc => Number.isFinite(loc.lat) && Number.isFinite(loc.lng));
            dataSource = 'markerCache';
            console.log(`5. SUCCESS: Using data source: markerCache (${locations.length} retailer locations from ${markerCache.length} total)`);
            console.log('6. Sample location:', locations[0]);
            console.log('7. First 3 locations:', locations.slice(0, 3));
        }
        // Try dataService if available
        else if (window.dataService && window.dataService.cache && window.dataService.cache.size > 0) {
            // Extract retailer data from dataService cache
            const cacheKeys = Array.from(window.dataService.cache.keys());
            console.log('5. DataService cache keys:', cacheKeys);
            
            const retailerKeys = cacheKeys.filter(key => key.includes('retailers') || key.includes('map-data'));
            console.log('6. Retailer keys found:', retailerKeys);
            
            if (retailerKeys.length > 0) {
                const cacheEntry = window.dataService.cache.get(retailerKeys[0]);
                console.log('7. Cache entry:', cacheEntry);
                
                if (cacheEntry && cacheEntry.data) {
                    const raw = Array.isArray(cacheEntry.data) ? cacheEntry.data : (cacheEntry.data.retailers || []);
                    // Normalize {latitude,longitude} → {lat,lng}
                    locations = raw.map(r => ({
                        lat: parseFloat(r.lat ?? r.latitude),
                        lng: parseFloat(r.lng ?? r.longitude),
                        retailer: r.retailer || 'Unknown',
                        retailer_type: r.retailer_type || 'unknown',
                        opening_hours: r.opening_hours || null,
                        address: r.full_address || r.address || null,
                        phone: r.phone_number || r.phone || null,
                        place_id: r.place_id || null
                    })).filter(loc => Number.isFinite(loc.lat) && Number.isFinite(loc.lng));
                    dataSource = 'dataService';
                    console.log(`8. SUCCESS: Using data source: dataService (${locations.length} locations from key: ${retailerKeys[0]})`);
                    console.log('9. Sample location:', locations[0]);
                    console.log('10. First 3 locations:', locations.slice(0, 3));
                }
            }
        }
        // Last fallback to any global markers array
        else if (window.markers && window.markers.length > 0) {
            // Normalize generic markers → plain objects
            locations = window.markers.map(marker => {
                const pos = marker.getPosition && marker.getPosition();
                return {
                    lat: pos ? pos.lat() : parseFloat(marker.lat ?? marker.latitude),
                    lng: pos ? pos.lng() : parseFloat(marker.lng ?? marker.longitude),
                    retailer: marker.getTitle?.() || marker.retailer || 'Unknown',
                    retailer_type: marker.retailer_type || 'unknown',
                    opening_hours: marker.opening_hours || null,
                    address: marker.address || marker.full_address || null,
                    phone: marker.phone || marker.phone_number || null,
                    place_id: marker.place_id || null
                };
            }).filter(loc => Number.isFinite(loc.lat) && Number.isFinite(loc.lng));
            dataSource = 'markers';
            console.log(`5. SUCCESS: Using data source: markers (${locations.length} locations)`);
            console.log('6. Sample location:', locations[0]);
            console.log('7. First 3 locations:', locations.slice(0, 3));
        }
        
        if (locations.length === 0) {
            console.log('ERROR: No marker data available for route planning');
            console.log('Debug - Available data sources:');
            console.log('- window.allMarkers:', window.allMarkers?.length || 0);
            console.log('- window.markerManager:', window.markerManager ? 'exists' : 'missing');
            console.log('- window.markerManager.markerCache:', window.markerManager?.markerCache?.size || 0);
            console.log('- window.dataService:', window.dataService ? 'exists' : 'missing');
            console.log('- window.dataService.cache:', window.dataService?.cache?.size || 0);
            console.log('- window.markers:', window.markers?.length || 0);
            
            // Additional debugging for markerManager
            if (window.markerManager) {
                console.log('- markerManager.markerCache keys:', Array.from(window.markerManager.markerCache?.keys() || []));
                console.log('- markerManager.markerCache values sample:', Array.from(window.markerManager.markerCache?.values() || []).slice(0, 3));
            }
            
            // Additional debugging for dataService
            if (window.dataService && window.dataService.cache) {
                console.log('- dataService.cache entries:');
                window.dataService.cache.forEach((value, key) => {
                    console.log(`  - ${key}:`, value);
                });
            }
            
            return [];
        }

        console.log(`8. Initial locations found: ${locations.length}`);
        console.log('9. Current maxDistance:', this.maxDistance);

        // Apply distance filter
        const beforeDistanceFilter = locations.length;
        locations = locations.filter(location => {
            const distance = this.calculateDistance(
                window.userCoords.lat, window.userCoords.lng,
                location.lat, location.lng
            );
            location.distance = distance;
            return distance <= this.maxDistance;
        });
        console.log(`10. After distance filter (${this.maxDistance} miles): ${locations.length} locations (was ${beforeDistanceFilter})`);
        
        if (locations.length > 0) {
            console.log('11. Sample locations after distance filter:', locations.slice(0, 3));
        }

        // Apply retailer type filters only if at least one type toggle is active
        const toggles = document.querySelectorAll('.route-filter-toggle');
        const anyActive = Array.from(toggles || []).some(t => t.classList.contains('active'));
        let beforeTypeFilter = locations.length;
        if (anyActive) {
        locations = this.applyRetailerTypeFilters(locations);
        } else {
            console.log('12. No retailer type toggles active, skipping type filter');
        }
        console.log(`12. After retailer type filter: ${locations.length} locations (was ${beforeTypeFilter})`);
        
        if (locations.length > 0) {
            console.log('13. Sample locations after type filter:', locations.slice(0, 3));
        }

        // Apply opening hours filter
        if (openNow === true) {
            const beforeHoursFilter = locations.length;
            locations = this.filterByOpeningHours(locations);
            console.log(`14. After opening hours filter: ${locations.length} locations (was ${beforeHoursFilter})`);
            
            if (locations.length > 0) {
                console.log('15. Sample locations after hours filter:', locations.slice(0, 3));
            }
        } else {
            console.log('14. Skipping opening hours filter (openNow = false)');
        }

        // Apply popularity filter
        if (leastPopular === true || mostPopular === true) {
            const beforePopularityFilter = locations.length;
            locations = this.filterByPopularity(locations, leastPopular, mostPopular);
            console.log(`16. After popularity filter: ${locations.length} locations (was ${beforePopularityFilter})`);
            
            if (locations.length > 0) {
                console.log('17. Sample locations after popularity filter:', locations.slice(0, 3));
            }
        } else {
            console.log('16. Skipping popularity filter (no popularity filter selected)');
        }

        console.log(`18. FINAL: Returning ${locations.length} filtered locations`);
        return locations;
    }

    applyPlannerFiltersToMap() {
        // Force map to reflect planner's toggles while open
        try {
            const kiosk = this.sessionCheckboxStates.kiosk;
            const retail = this.sessionCheckboxStates.retail;
            const indie = this.sessionCheckboxStates.indie;
            const openNow = this.sessionCheckboxStates.openNow;
            const events = false;
            const filters = { showKiosk: kiosk, showRetail: retail, showIndie: indie, showOpenNow: openNow, showEvents: events, showPopular: false, searchText: '' };
            // Mirror into legend checkboxes if present (visual sync)
            const set = (id, val) => { const el = document.getElementById(id); if (el) el.checked = !!val; };
            set('filter-kiosk', kiosk); set('filter-retail', retail); set('filter-indie', indie);
            set('filter-open-now', openNow); set('filter-events', false); set('filter-popular-areas', false);
            if (typeof window.applyFilters === 'function') window.applyFilters(filters);
        } catch {}
    }

    restoreMapFiltersFromLegend() {
        try {
            if (typeof window.applyFilters === 'function') window.applyFilters();
        } catch {}
    }

    disableLegendControls() {
        try {
            const legend = document.getElementById('legend');
            if (!legend) return;
            legend.style.opacity = '0.6';
            legend.querySelectorAll('input, button, select, textarea').forEach(el => { el.disabled = true; });
            if (!document.getElementById('legend-route-lock')) {
                const banner = document.createElement('div');
                banner.id = 'legend-route-lock';
                banner.textContent = 'Route Planner is controlling filters';
                banner.style.cssText = 'font-size:12px; padding:6px 8px; margin:4px; border:1px solid #ffeeba; background:#fff3cd; color:#856404; border-radius:4px;';
                legend.insertBefore(banner, legend.firstChild);
            }
        } catch {}
    }

    enableLegendControls() {
        try {
            const legend = document.getElementById('legend');
            if (!legend) return;
            legend.style.opacity = '';
            legend.querySelectorAll('input, button, select, textarea').forEach(el => { el.disabled = false; });
            const banner = document.getElementById('legend-route-lock');
            if (banner && banner.parentNode) banner.parentNode.removeChild(banner);
        } catch {}
    }

    /**
     * Apply retailer type filters based on route planner toggles
     */
    applyRetailerTypeFilters(locations) {
        console.log('=== APPLY RETAILER TYPE FILTERS DEBUG ===');
        const activeFilters = [];
        
        // Check which toggles are active in the route planner
        const toggles = document.querySelectorAll('.route-filter-toggle');
        console.log('1. Found route filter toggles:', toggles.length);
        
        toggles.forEach((toggle, index) => {
            const filterType = toggle.getAttribute('data-filter');
            const isActive = toggle.classList.contains('active');
            console.log(`2. Toggle ${index + 1}: ${filterType} - ${isActive ? 'ACTIVE' : 'inactive'}`);
            
            if (isActive) {
                activeFilters.push(filterType);
            }
        });

        console.log('3. Active filters:', activeFilters);

        // If no filters are active, return all locations
        if (activeFilters.length === 0) {
            console.log('4. No retailer type filters active, showing all location types');
            return locations;
        }

        console.log('5. Applying retailer type filters:', activeFilters);
        
        // Debug: Show all unique retailer types in the data
        const uniqueTypes = [...new Set(locations.map(loc => loc.retailer_type).filter(Boolean))];
        console.log('6. All unique retailer types in data:', uniqueTypes);
        
        // Additional debugging: Show sample locations with their types
        console.log('7. Sample locations with types:');
        locations.slice(0, 10).forEach((loc, index) => {
            console.log(`   ${index + 1}. ${loc.retailer} -> type: "${loc.retailer_type || 'unknown'}"`);
        });
        
        const filtered = locations.filter((location, index) => {
            const retailerTypeRaw = (location.retailer_type || '').toLowerCase();
            const hasRetail = retailerTypeRaw.includes('store');
            const hasKiosk = retailerTypeRaw.includes('kiosk');
            const hasIndie = retailerTypeRaw.includes('card shop');
            
            let matches = false;
            for (const filter of activeFilters) {
                if (filter === 'retail' && hasRetail) { matches = true; break; }
                if (filter === 'kiosk' && hasKiosk) { matches = true; break; }
                if (filter === 'indie' && hasIndie) { matches = true; break; }
            }

            if (index < 5) {
                console.log(`   Location ${index + 1}: ${location.retailer} (${location.retailer_type || 'unknown'}) -> match=${matches}`);
            }
            return matches;
        });
        console.log(`7. Filtered from ${locations.length} to ${filtered.length} locations`);
        return filtered;
    }

    /**
     * Filter locations by opening hours using the isOpenNow function from utils.js
     */
    filterByOpeningHours(locations) {
        // Import the isOpenNow function from utils.js
        if (typeof window.isOpenNow !== 'function') {
            console.warn('isOpenNow function not available, skipping opening hours filter');
            return locations;
        }

        return locations.filter(location => {
            const hours = location.opening_hours;
            if (!hours) {
                return false; // Exclude if no opening hours data
            }
            
            // Use the isOpenNow function from utils.js
            return window.isOpenNow(hours);
        });
    }

    /**
     * Filter locations by popularity (heatmap data)
     */
    filterByPopularity(locations, leastPopular, mostPopular) {
        if (!leastPopular && !mostPopular) {
            return locations; // No popularity filter applied
        }

        // Get individual popularity data if available
        const individualData = window.individualPopularityData || [];
        if (window.__TM_DEBUG__) console.log('Popularity data size', individualData.length);
        
        if (individualData.length === 0) {
            if (window.__TM_DEBUG__) console.warn('No popularity data');
            return locations;
        }

        // Create a map of location popularity scores using full precision coordinates
        const popularityMap = new Map();
        individualData.forEach(item => {
            // Use full precision coordinates for exact location matching
            const key = `${item.lat},${item.lng}`;
            popularityMap.set(key, item.weight || 0);
        });

        if (window.__TM_DEBUG__) console.log('Popularity map size', popularityMap.size);

        // Calculate popularity scores for each location using full precision matching
        const locationsWithScores = locations.map(location => {
            // Use full precision coordinates for exact location matching
            const key = `${location.lat},${location.lng}`;
            const popularityScore = popularityMap.get(key) || 0;
            return { ...location, popularityScore };
        });

        if (window.__TM_DEBUG__) console.log('Scored', locationsWithScores.length);

        // Sort by popularity score first
        locationsWithScores.sort((a, b) => a.popularityScore - b.popularityScore);

        // Filter based on selection
        if (leastPopular) {
            // Take the bottom 25% of locations (least popular)
            const cutoffIndex = Math.floor(locationsWithScores.length * 0.25);
            const leastPopularLocations = locationsWithScores.slice(0, cutoffIndex);
            
            // Then sort by distance within the least popular group to prioritize closer locations
            leastPopularLocations.sort((a, b) => a.distance - b.distance);
            
            if (window.__TM_DEBUG__) console.log('Least popular:', leastPopularLocations.length);
            console.log('6. Sample least popular locations:', leastPopularLocations.slice(0, 3).map(loc => 
                `${loc.retailer}: popularity=${loc.popularityScore}, distance=${loc.distance?.toFixed(1)}mi`
            ));
            return leastPopularLocations;
        } else if (mostPopular) {
            // Take the top 25% of locations (most popular)
            const cutoffIndex = Math.floor(locationsWithScores.length * 0.75);
            const mostPopularLocations = locationsWithScores.slice(cutoffIndex);
            
            // Then sort by distance within the most popular group to prioritize closer locations
            mostPopularLocations.sort((a, b) => a.distance - b.distance);
            
            if (window.__TM_DEBUG__) console.log('Most popular:', mostPopularLocations.length);
            console.log('6. Sample most popular locations:', mostPopularLocations.slice(0, 3).map(loc => 
                `${loc.retailer}: popularity=${loc.popularityScore}, distance=${loc.distance?.toFixed(1)}mi`
            ));
            return mostPopularLocations;
        }

        return locationsWithScores;
    }

    /**
     * Select optimal locations for the route
     */
    selectOptimalLocations(locations) {
        if (window.__TM_DEBUG__) console.log('Select optimal locations', { count: locations?.length || 0, maxStops: this.maxStops });
        
        if (!locations || locations.length === 0) {
            if (window.__TM_DEBUG__) console.log('No locations provided');
            return [];
        }

        // Sort by distance and take the closest ones up to maxStops
        const sorted = [...locations].sort((a, b) => a.distance - b.distance);
        const selected = sorted.slice(0, this.maxStops);
        
        if (window.__TM_DEBUG__) console.log('Selected locations', selected.length);
        
        return selected;
    }

    /**
     * Calculate distance between two coordinates (Haversine formula)
     */
    calculateDistance(lat1, lng1, lat2, lng2) {
        const R = 3959; // Earth radius in miles
        const dLat = this.toRadians(lat2 - lat1);
        const dLng = this.toRadians(lng2 - lng1);
        const a = Math.sin(dLat / 2) * Math.sin(dLat / 2) +
                  Math.cos(this.toRadians(lat1)) * Math.cos(this.toRadians(lat2)) *
                  Math.sin(dLng / 2) * Math.sin(dLng / 2);
        const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
        return R * c;
    }

    /**
     * Convert degrees to radians
     */
    toRadians(degrees) {
        return degrees * (Math.PI / 180);
    }

    /**
     * Increment popularity for selected locations by calling the track pin API
     */
    incrementLocationPopularity(locations) {
            if (window.__TM_DEBUG__) console.log('Increment popularity for', locations.length, 'locations');
        
        // Call the track pin API for each location to increment popularity
        locations.forEach(location => {
            // Find the marker ID from the location data
            let markerId = location.place_id || location.marker_id;
            
            // If we dont have a place_id, try to find it from the marker data
            if (!markerId && window.allMarkers) {
                const marker = window.allMarkers.find(m => 
                    m.getPosition().lat() === location.lat && 
                    m.getPosition().lng() === location.lng
                );
                if (marker) {
                    markerId = marker.getTitle() || marker.place_id;
                }
            }
            
            if (markerId) {
                if (window.__TM_DEBUG__) console.log('Incrementing popularity for:', location.retailer, 'ID:', markerId);
                
                // Call the track pin API
                fetch('/track/pin', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        marker_id: markerId,
                        lat: location.lat,
                        lng: location.lng
                    })
                }).then(response => {
                    if (window.__TM_DEBUG__) console.log('Popularity increment response ok:', response.ok);
                }).catch(error => {
                    if (window.__TM_DEBUG__) console.error('Error incrementing popularity for:', location.retailer, error);
                });
            } else {
                if (window.__TM_DEBUG__) console.warn('Could not find marker ID for:', location.retailer);
            }
        });
    }

    /**
     * Format retailer name with type and city in parentheses
     */
    cleanRetailerName(retailerName, retailerType = null, address = null) {
        if (!retailerName || retailerName === 'Unknown') {
            return retailerName;
        }
        
        // Extract base name and city
        let baseName = retailerName;
        let city = '';
        
        // First check if there is a city suffix in the retailer name (e.g., " - Lynnwood", " - Seattle")
        const citySuffixPattern = /\s*-\s*([A-Za-z\s]+(?:,\s*[A-Z]{2})?)$/;
        const cityMatch = retailerName.match(citySuffixPattern);
        
        if (cityMatch) {
            baseName = retailerName.replace(citySuffixPattern, '').trim();
            city = cityMatch[1].trim();
        }
        // If no city suffix in retailer name, try to extract from address
        else if (address) {
            // Try to extract city from address (common patterns)
            // Look for patterns like "City, State" or "City, ST"
            const addressCityPattern = /([A-Za-z\s]+),\s*[A-Z]{2}\s*\d{5}/; // "City, ST 12345"
            const addressCityMatch = address.match(addressCityPattern);
            
            if (addressCityMatch) {
                city = addressCityMatch[1].trim();
            } else {
                // Try simpler pattern for "City, State"
                const simpleCityPattern = /([A-Za-z\s]+),\s*[A-Z]{2}/; // "City, ST"
                const simpleCityMatch = address.match(simpleCityPattern);
                
                if (simpleCityMatch) {
                    city = simpleCityMatch[1].trim();
                }
            }
        }
        
        // Maintain original behavior for other callers
        if (retailerType && city) return `${baseName} (${retailerType} - ${city})`;
        if (retailerType)         return `${baseName} (${retailerType})`;
        if (city)                 return `${baseName} (${city})`;
            return baseName;
        }

    // New: Format a stop line as "Name (Store + Kiosk) City 1.3 mi — Open until 9:00 PM"
    formatStopLine(loc, isOpen) {
        const name = (loc.retailer || 'Unknown').trim();
        const type = this.formatTypeSentenceCase(loc.retailer_type);
        const city = this.extractCity(loc.address) || '';
        const dist = (typeof loc.distance === 'number') ? `${loc.distance.toFixed(1)} mi` : '';
        const openTxtRaw = isOpen ? this.formatOpenUntil(loc.opening_hours) : 'Closed now';
        const openTxt = this.normalizeTimeLabel(openTxtRaw);
        const typePill = type ? `<span style="display:inline-block; padding:0 6px; border-radius:10px; border:1px solid #ced4da; font-size:12px; color:#495057; margin-left:6px;">${type}</span>` : '';
        const meta = [city, dist, openTxt].filter(Boolean).join(' · ');
        return `<span style="font-weight:600;">${name}</span>${typePill} <span style="color:#6c757d; font-size:12px;">${meta}</span>`;
    }

    normalizeTimeLabel(label) {
        if (!label) return '';
        // Convert patterns like "12 00 AM" → "12:00 AM" and ensure spaces
        try {
            return String(label)
                .replace(/(\d{1,2})\s(\d{2})\s*(AM|PM)/gi, '$1:$2 $3')
                .replace(/\s+/g, ' ')
                .trim();
        } catch {
            return label;
        }
    }

    formatTypeSentenceCase(retailerType) {
        if (!retailerType) return '';
        // Split on '+' and convert each to Title Case with known mappings
        const parts = String(retailerType).split('+').map(p => p.trim().toLowerCase()).filter(Boolean);
        const title = parts.map(p => {
            if (p === 'card shop') return 'Card Shop';
            if (p === 'retail' || p === 'store') return 'Store';
            if (p === 'kiosk') return 'Kiosk';
            // Fallback title case
            return p.replace(/\b\w/g, c => c.toUpperCase());
        }).join(' + ');
        return title;
    }

    extractCity(address) {
        if (!address) return '';
        // Prefer "City, ST" pattern
        const m1 = address.match(/([A-Za-z\s]+),\s*[A-Z]{2}\b/);
        if (m1) return m1[1].trim();
        // Fallback: last token before ZIP
        const m2 = address.match(/,\s*([A-Za-z\s]+)\s*,?\s*[A-Z]{2}\s*\d{5}/);
        if (m2) return m2[1].trim();
        return '';
    }

    formatOpenUntil(opening_hours) {
        if (!opening_hours || typeof window.isOpenNow !== 'function') return '';
        // If today is listed as "Open 24 hours"
        const days = ['Sunday','Monday','Tuesday','Wednesday','Thursday','Friday','Saturday'];
        const todayFull = days[new Date().getDay()];
        const lines = String(opening_hours).split(/\r?\n/).map(l => l.trim());
        const todayLine = lines.find(l => l.toLowerCase().startsWith(`${todayFull.toLowerCase()}:`));
        if (todayLine && /open\s*24/i.test(todayLine)) return 'Open 24 hours';

        const open = window.isOpenNow(opening_hours);
        if (!open) return '';

        // Try to extract today's closing time from the raw line first
        try {
            if (todayLine) {
                // Split on dash variants: –, —, -
                const parts = todayLine.split(/[:,]\s*/).slice(1).join(' ').split(/[\u2013\u2014\-–]/);
                const endStr = (parts[1] || '').trim();
                if (endStr) return `Open until ${endStr}`;
            }
        } catch {}

        // Fallback: use formatted HTML if available
        try {
            if (typeof window.formatHours === 'function') {
                const html = window.formatHours(opening_hours) || '';
                const todayShort = new Date().toLocaleString(undefined, { weekday: 'short' }); // Mon
                const re = new RegExp(`${todayShort}[^\n]*?[\u2013\u2014\-–]\s*([^<]+)`, 'i');
                const match = html.match(re);
                const closing = match && match[1] ? match[1].trim() : '';
                if (closing) return `Open until ${closing}`;
            }
        } catch {}

        return 'Open now';
    }

    /**
     * Show preview pins on the map
     */
    showPreviewPins() {
        // Persist preferences before going to preview
        this.savePreferences();
        
        console.log('=== ROUTE PLANNER PREVIEW DEBUG ===');
        console.log('1. showPreviewPins called');
        console.log('2. userCoords:', window.userCoords);
        console.log('3. allMarkers:', window.allMarkers?.length || 0);
        console.log('4. markerManager:', window.markerManager ? 'exists' : 'missing');
        console.log('5. markerCache size:', window.markerManager?.markerCache?.size || 0);
        console.log('6. window.markers:', window.markers?.length || 0);
        console.log('7. dataService:', window.dataService ? 'exists' : 'missing');
        console.log('8. dataService cache size:', window.dataService?.cache?.size || 0);
        if (window.dataService?.cache) {
            console.log('9. dataService cache keys:', Array.from(window.dataService.cache.keys()));
        }
        
        // Additional debugging for markerManager
        if (window.markerManager) {
            console.log('10. markerManager.markerCache keys:', Array.from(window.markerManager.markerCache?.keys() || []));
            console.log('11. markerManager.markerCache values sample:', Array.from(window.markerManager.markerCache?.values() || []).slice(0, 3));
        }
        
        // Additional debugging for dataService
        if (window.dataService && window.dataService.cache) {
            console.log('12. dataService.cache entries:');
            window.dataService.cache.forEach((value, key) => {
                console.log(`  - ${key}:`, value);
            });
        }
        
        // Check if basic requirements are met
        if (!window.userCoords) {
            console.log('ERROR: No user coordinates available');
            Swal.fire({
                title: 'Location Required',
                text: 'Please allow location access to use route planning.',
                icon: 'warning',
                timer: 3000,
                showConfirmButton: false
            });
            return;
        }

        // Check if we have any marker data available
        const hasMarkerData = (window.allMarkers && window.allMarkers.length > 0) ||
                             (window.markerManager && window.markerManager.markerCache && window.markerManager.markerCache.size > 0) ||
                             (window.markers && window.markers.length > 0);
        
        console.log('13. hasMarkerData:', hasMarkerData);
        
        if (!hasMarkerData) {
            console.log('ERROR: No marker data available');
            Swal.fire({
                title: 'No Store Data',
                text: 'Store data is still loading. Please try again in a moment.',
                icon: 'warning',
                timer: 3000,
                showConfirmButton: false
            });
            return;
        }

        // Get current route with default settings if modal isn't open
        const openNow = !!this.sessionCheckboxStates.openNow;
        const leastPopular = !!this.sessionCheckboxStates.leastPopular;
        const mostPopular = !!this.sessionCheckboxStates.mostPopular;
        console.log('14. openNow filter:', openNow);
        console.log('15. leastPopular filter:', leastPopular);
        console.log('16. mostPopular filter:', mostPopular);
        
        let availableLocations = this.getFilteredLocations(openNow, leastPopular, mostPopular);
        if (this.sessionCheckboxStates.mergeNearby) {
            availableLocations = this.mergeNearbyLocations(availableLocations, this.mergeThresholdMeters);
        }
        console.log('17. availableLocations:', availableLocations.length);
        console.log('18. availableLocations sample:', availableLocations.slice(0, 3));
        
        this.selectedLocations = this.selectOptimalLocations(availableLocations);
        console.log('19. selectedLocations:', this.selectedLocations.length);
        console.log('20. selectedLocations details:', this.selectedLocations);

        // Track route planner preview
        try {
            fetch('/track/route', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    event: 'preview',
                    max_distance: this.maxDistance,
                    max_stops: this.maxStops,
                    options_json: JSON.stringify(this.sessionCheckboxStates || {})
                })
            }).catch(() => {});
        } catch {}

        if (this.selectedLocations.length === 0) {
            console.log('ERROR: No locations selected after filtering');
            Swal.fire({
                title: 'No Locations Found',
                text: 'Could not find enough locations matching your criteria. Try adjusting your filters or opening the route planner first.',
                icon: 'warning',
                timer: 4000,
                showConfirmButton: false
            });
            return;
        }

        // Prepare preview efficiently and then update UI to avoid flicker
        // Hide regular markers first
        this.hideRegularMarkers();

        // Clear any existing preview pins
        this.clearPreviewPins();

        // Create preview pins after map idle to ensure it's ready
        const addPins = () => this.createPreviewPins();
        if (window.map) {
            const once = google.maps.event.addListenerOnce(window.map, 'idle', addPins);
            // Safety fallback in case idle doesn't fire quickly
            setTimeout(() => { try { google.maps.event.removeListener(once); } catch {} addPins(); }, 150);
        } else {
        this.createPreviewPins();
        }

        // Close the planner modal after pins are on the map to reduce visual pop
        Swal.close();

        // Set current step to preview
        this.currentStep = 'preview';

        // Create floating menu for preview step
        this.createFloatingMenu();

        // Show success toast with store count
        const Toast = Swal.mixin({
            toast: true,
            position: 'top-end',
            showConfirmButton: false,
            timer: 3000,
            timerProgressBar: true
        });

        Toast.fire({
            icon: 'success',
            title: `Showing ${this.selectedLocations.length} locations in your route`
        });
    }

    /**
     * Create floating menu for preview step
     */
    createFloatingMenu() {
        // Remove existing floating menu if it exists
        const existingMenu = document.getElementById('route-planner-floating-menu');
        if (existingMenu) {
            existingMenu.remove();
        }

        // Create floating menu container
        const floatingMenu = document.createElement('div');
        floatingMenu.id = 'route-planner-floating-menu';
        floatingMenu.style.cssText = `
            position: fixed;
            bottom: 20px;
            left: 50%;
            transform: translateX(-50%);
            background: white;
            border-radius: 12px;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.15);
            padding: 16px 24px;
            z-index: 1000;
            display: flex;
            gap: 12px;
            align-items: center;
            border: 1px solid #e9ecef;
            font-family: -apple-system, BlinkMacSystemFont, \'Segoe UI\', Roboto, sans-serif;
        `;

        // Create navigation buttons
        const backToPlanningBtn = document.createElement('button');
        backToPlanningBtn.innerHTML = '<i class="fas fa-chevron-left"></i> Route Planning';
        backToPlanningBtn.style.cssText = `
            background: #6c757d;
            color: white;
            border: none;
            padding: 10px 16px;
            border-radius: 8px;
            font-size: 14px;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.2s ease;
            display: flex;
            align-items: center;
            gap: 6px;
        `;
        backToPlanningBtn.addEventListener('mouseenter', () => {
            backToPlanningBtn.style.background = '#5a6268';
        });
        backToPlanningBtn.addEventListener('mouseleave', () => {
            backToPlanningBtn.style.background = '#6c757d';
        });
        backToPlanningBtn.addEventListener('click', () => {
            this.backToPlanning();
        });

        const goBtn = document.createElement('button');
        goBtn.innerHTML = 'Go! <i class="fas fa-chevron-right"></i>';
        goBtn.style.cssText = `
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 8px;
            font-size: 14px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s ease;
            display: flex;
            align-items: center;
            gap: 6px;
            box-shadow: 0 2px 8px rgba(102, 126, 234, 0.3);
        `;
        goBtn.addEventListener('mouseenter', () => {
            goBtn.style.transform = 'translateY(-1px)';
            goBtn.style.boxShadow = '0 4px 12px rgba(102, 126, 234, 0.4)';
        });
        goBtn.addEventListener('mouseleave', () => {
            goBtn.style.transform = 'translateY(0)';
            goBtn.style.boxShadow = '0 2px 8px rgba(102, 126, 234, 0.3)';
        });
        goBtn.addEventListener('click', () => {
            this.executeRoute();
        });

        const exitBtn = document.createElement('button');
        exitBtn.innerHTML = '<i class="fas fa-times"></i> Exit';
        exitBtn.style.cssText = `
            background: #dc3545;
            color: white;
            border: none;
            padding: 10px 16px;
            border-radius: 8px;
            font-size: 14px;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.2s ease;
            display: flex;
            align-items: center;
            gap: 6px;
        `;
        exitBtn.addEventListener('mouseenter', () => {
            exitBtn.style.background = '#c82333';
        });
        exitBtn.addEventListener('mouseleave', () => {
            exitBtn.style.background = '#dc3545';
        });
        exitBtn.addEventListener('click', () => {
            this.exitPreview();
        });

        // Add buttons to menu
        floatingMenu.appendChild(backToPlanningBtn);
        floatingMenu.appendChild(goBtn);
        floatingMenu.appendChild(exitBtn);

        // Add menu to page
        document.body.appendChild(floatingMenu);
    }

    /**
     * Remove floating menu
     */
    removeFloatingMenu() {
        const floatingMenu = document.getElementById('route-planner-floating-menu');
        if (floatingMenu) {
            floatingMenu.remove();
        }
    }

    /**
     * Back to planning step
     */
    backToPlanning() {
        // Save current session data before switching back to planning
        // We need to capture the checkbox states BEFORE closing the modal
        const currentCheckboxStates = this.getCurrentCheckboxStates();
        console.log('=== BACK TO PLANNING DEBUG ===');
        console.log('Captured checkbox states before modal close:', currentCheckboxStates);
        
        // Store the states temporarily so we can restore them
        this.sessionCheckboxStates = currentCheckboxStates;
        
        this.currentStep = 'planning';
        this.removeFloatingMenu();
        this.clearPreviewPins();
        this.showRegularMarkers();
        
        // Reopen the planning modal
        this.openPlanningModal();
    }

    /**
     * Execute the route
     */
    executeRoute() {
        this.currentStep = 'execute';
        this.removeFloatingMenu();
        
        // Increment popularity for selected locations
        this.incrementLocationPopularity(this.selectedLocations);
        // Track route planner go
        try {
            fetch('/track/route', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    event: 'go',
                    max_distance: this.maxDistance,
                    max_stops: this.maxStops,
                    options_json: JSON.stringify(this.sessionCheckboxStates || {})
                })
            }).catch(() => {});
        } catch {}
        
        // Generate and open the route
        const roundTrip = !!this.sessionCheckboxStates.roundTrip;
        this.generateRoute(roundTrip);
        
        // Clear preview and return to normal state
        this.clearPreviewPins();
        this.showRegularMarkers();
        this.clearSessionData();
    }

    /**
     * Exit preview and return to map
     */
    exitPreview() {
        this.currentStep = 'planning';
        this.removeFloatingMenu();
        this.clearPreviewPins();
        this.showRegularMarkers();
        // Don't clear session data here - it should be preserved for planning transitions
        // this.clearSessionData();
    }

    /**
     * Open planning modal
     */
    openPlanningModal() {
        // Use the SweetAlert2 configuration from routePlanner
        Swal.fire({
            title: '<i class="fas fa-route"></i> Route Planner',
            html: this.createModalContent(),
            showConfirmButton: false,
            showCancelButton: false,
            showCloseButton: true,
            customClass: {
                popup: 'swal2-route-planner'
            },
            width: '650px',
            didOpen: () => {
                // Sync map to planner filters while planner is open
                this.applyPlannerFiltersToMap();
                this.disableLegendControls();
                // Initialize controls - session data is already loaded in this.sessionCheckboxStates
                console.log('=== OPEN PLANNING MODAL DEBUG ===');
                console.log('this.sessionCheckboxStates available:', this.sessionCheckboxStates);
                this.initializeModalControls();
                // Track route planner open
                try {
                    fetch('/track/route', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            event: 'open',
                            max_distance: this.maxDistance,
                            max_stops: this.maxStops,
                            options_json: JSON.stringify(this.sessionCheckboxStates || {})
                        })
                    }).catch(() => {});
                } catch {}
            },
            willClose: () => {
                // Only clear session data if we're exiting the workflow entirely
                // (not when navigating between planning and preview)
                if (this.currentStep === 'planning') {
                    this.clearSessionData();
                }
                this.currentStep = 'planning';
                // Restore legend/map filters after planner closes
                this.restoreMapFiltersFromLegend();
                this.enableLegendControls();
            }
        });
    }

    /**
     * Hide regular markers
     */
    hideRegularMarkers() {
        if (window.hideAllMarkers) {
            window.hideAllMarkers();
        }
    }

    /**
     * Show regular markers
     */
    showRegularMarkers() {
        if (window.showAllMarkers) {
            window.showAllMarkers();
        }
    }

    /**
     * Clear preview pins
     */
    clearPreviewPins() {
        this.previewPins.forEach(pin => pin.setMap(null));
        this.previewPins = [];
    }

    /**
     * Create preview pins for the route
     */
    createPreviewPins() {
        if (!window.userCoords || !this.selectedLocations.length) return;

        // Collect all positions for auto-zoom
        const allPositions = [
            { lat: window.userCoords.lat, lng: window.userCoords.lng }
        ];
        console.log('Starting position collection. User coords:', window.userCoords);

        // Create start pin (green) with shaded circle
        const startPin = new google.maps.Marker({
            position: { lat: window.userCoords.lat, lng: window.userCoords.lng },
            map: window.map,
            title: 'Start Location',
            icon: {
                path: google.maps.SymbolPath.CIRCLE,
                scale: 12,
                fillColor: '#28a745',
                fillOpacity: 1,
                strokeColor: '#ffffff',
                strokeWeight: 3
            },
            zIndex: 1000
        });
        this.previewPins.push(startPin);

        // Create shaded circle around start pin
        const startCircle = new google.maps.Circle({
            strokeColor: '#28a745',
            strokeOpacity: 0.3,
            strokeWeight: 2,
            fillColor: '#28a745',
            fillOpacity: 0.1,
            map: window.map,
            center: { lat: window.userCoords.lat, lng: window.userCoords.lng },
            radius: 500, // 500 meters radius
            zIndex: 1
        });
        this.previewPins.push(startCircle);

        // Create stop pins (orange) with shaded circles
        this.selectedLocations.forEach((location) => {
            allPositions.push({ lat: location.lat, lng: location.lng });
            console.log('Added location to positions:', location.retailer, location.lat, location.lng);
            
            // Create shaded circle around stop pin FIRST (so it appears below)
            const stopCircle = new google.maps.Circle({
                strokeColor: '#ff6b35',
                strokeOpacity: 0.3,
                strokeWeight: 2,
                fillColor: '#ff6b35',
                fillOpacity: 0.1,
                map: window.map,
                center: { lat: location.lat, lng: location.lng },
                radius: 400, // 400 meters radius
                zIndex: 1
            });
            this.previewPins.push(stopCircle);
            
            // Create stop pin (orange) with bouncing animation
            const stopPin = new google.maps.Marker({
                position: { lat: location.lat, lng: location.lng },
                map: window.map,
                title: `${location.retailer || 'Unknown'} (${location.distance?.toFixed(1) || '?'} mi)`,
                icon: {
                    path: google.maps.SymbolPath.CIRCLE,
                    scale: 12,
                    fillColor: '#ff6b35',
                    fillOpacity: 1,
                    strokeColor: '#ffffff',
                    strokeWeight: 3
                },
                zIndex: 1001
            });
            this.previewPins.push(stopPin);
            
            // Add bouncing animation to the pin
            this.addBouncingAnimation(stopPin);
        });

        // Create end pin (red) if round trip
        const roundTrip = !!this.sessionCheckboxStates.roundTrip;
        if (roundTrip) {
            const endPin = new google.maps.Marker({
                position: { lat: window.userCoords.lat, lng: window.userCoords.lng },
                map: window.map,
                title: 'End Location (Round Trip)',
                icon: {
                    path: google.maps.SymbolPath.CIRCLE,
                    scale: 12,
                    fillColor: '#dc3545',
                    fillOpacity: 1,
                    strokeColor: '#ffffff',
                    strokeWeight: 3
                },
                zIndex: 1000
            });
            this.previewPins.push(endPin);

            // Create shaded circle around end pin
            const endCircle = new google.maps.Circle({
                strokeColor: '#dc3545',
                strokeOpacity: 0.3,
                strokeWeight: 2,
                fillColor: '#dc3545',
                fillOpacity: 0.1,
                map: window.map,
                center: { lat: window.userCoords.lat, lng: window.userCoords.lng },
                radius: 500, // 500 meters radius
                zIndex: 1
            });
            this.previewPins.push(endCircle);
        }

        // Auto-zoom to fit all preview points with padding after map is ready
        if (window.__TM_DEBUG__) console.log('Final positions for zooming:', allPositions);
        if (window.map) {
            const runZoom = () => this.zoomToFitPreviewPoints(allPositions);
            const once = google.maps.event.addListenerOnce(window.map, 'idle', runZoom);
            setTimeout(() => { try { google.maps.event.removeListener(once); } catch {} runZoom(); }, 120);
        } else {
            setTimeout(() => this.zoomToFitPreviewPoints(allPositions), 120);
        }
    }

    /**
     * Add bouncing animation to a marker
     */
    addBouncingAnimation(marker) {
        // Prefer built-in Google Maps bounce animation to avoid map reflows/flicker
        try {
            if (google && google.maps && google.maps.Animation && marker.setAnimation) {
                marker.setAnimation(google.maps.Animation.BOUNCE);
                // Stop bounce after ~1.8s (~3 cycles visually)
                setTimeout(() => {
                    marker.setAnimation(null);
                }, 1800);
                return;
            }
        } catch (e) {
            // fall through to no-op fallback
        }
        // Fallback: no movement to avoid flicker on some devices
        // Optionally could implement a subtle icon scale using custom overlays; omitted to keep stable
    }

    /**
     * Zoom map to fit all preview points with padding
     */
    zoomToFitPreviewPoints(positions) {
        if (!positions || positions.length === 0) {
            console.log('No positions to zoom to');
            return;
        }

        if (window.__TM_DEBUG__) console.log('Zooming to fit positions:', positions);

        const bounds = new google.maps.LatLngBounds();
        
        // Add all positions to bounds
        positions.forEach(pos => {
            const latLng = new google.maps.LatLng(pos.lat, pos.lng);
            bounds.extend(latLng);
            if (window.__TM_DEBUG__) console.log('Added position to bounds:', pos.lat, pos.lng);
        });

        // Add padding to bounds (expand by 20% for better visibility)
        const ne = bounds.getNorthEast();
        const sw = bounds.getSouthWest();
        const latDiff = (ne.lat() - sw.lat()) * 0.2;
        const lngDiff = (ne.lng() - sw.lng()) * 0.2;
        
        bounds.extend(new google.maps.LatLng(ne.lat() + latDiff, ne.lng() + lngDiff));
        bounds.extend(new google.maps.LatLng(sw.lat() - latDiff, sw.lng() - lngDiff));

        if (window.__TM_DEBUG__) console.log('Bounds created:', {
            north: bounds.getNorthEast().lat(),
            east: bounds.getNorthEast().lng(),
            south: bounds.getSouthWest().lat(),
            west: bounds.getSouthWest().lng()
        });

        // Fit map to bounds with smooth animation
        window.map.fitBounds(bounds);
        
        // Ensure reasonable zoom level and add a small delay for the animation
        setTimeout(() => {
            const currentZoom = window.map.getZoom();
            if (window.__TM_DEBUG__) console.log('Current zoom level:', currentZoom);
            
            // If zoomed out too far, set a reasonable zoom level
            if (currentZoom < 10) {
                window.map.setZoom(12);
                if (window.__TM_DEBUG__) console.log('Adjusted zoom to 12');
            }
            // If zoomed in too close, set a reasonable zoom level
            else if (currentZoom > 16) {
                window.map.setZoom(14);
                if (window.__TM_DEBUG__) console.log('Adjusted zoom to 14');
            }
        }, 500);
    }



    /**
     * Clear preview and optionally skip reopening modal
     */
    clearPreview(skipReopenModal = false) {
        // Clear preview pins
        this.previewPins.forEach(pin => pin.setMap(null));
        this.previewPins = [];
        
        // Show regular markers again
        this.showRegularMarkers();
        
        // Remove floating menu if in preview step
        this.removeFloatingMenu();
        
        // Reset to planning step
        this.currentStep = 'planning';
        
        // Show the route planner modal again only if not skipped
        if (!skipReopenModal) {
            this.openPlanningModal();
        }
    }



    /**
     * Generate route with current selections
     */
    generateRoute(roundTrip = false) {
        if (!window.userCoords) {
            Swal.fire({
                title: 'Location Required',
                text: 'Please allow location access to plan routes.',
                icon: 'warning'
            });
            return;
        }

        // Ensure we have selected locations
        if (!this.selectedLocations || this.selectedLocations.length === 0) {
            const openNow = !!this.sessionCheckboxStates.openNow;
            const leastPopular = !!this.sessionCheckboxStates.leastPopular;
            const mostPopular = !!this.sessionCheckboxStates.mostPopular;
            let availableLocations = this.getFilteredLocations(openNow, leastPopular, mostPopular);
            if (this.sessionCheckboxStates.mergeNearby) {
                availableLocations = this.mergeNearbyLocations(availableLocations, this.mergeThresholdMeters);
            }
            this.selectedLocations = this.selectOptimalLocations(availableLocations);
        }

        if (this.selectedLocations.length < 2) {
            Swal.fire({
                title: 'Route Planning Error',
                text: 'Could not find enough locations matching your criteria.',
                icon: 'error'
            });
            return;
        }

        // Warn if any selected stop lacks a valid place_id
        const missingPid = this.selectedLocations.filter(l => !l.place_id || String(l.place_id).trim() === '');
        if (missingPid.length > 0 && typeof Swal !== 'undefined') {
            const names = missingPid.slice(0,5).map(l => (l.retailer || l.address || `${l.lat.toFixed(5)},${l.lng.toFixed(5)}`));
            Swal.fire({
                toast: true,
                position: 'top-end',
                icon: 'info',
                title: 'Some stops may show as an address only',
                html: `<small>Missing place IDs for: ${names.join(', ')}${missingPid.length>5?'…':''}</small>`,
                showConfirmButton: false,
                timer: 3500,
                timerProgressBar: true
            });
        }

        // Increment popularity for all selected locations
        this.incrementLocationPopularity(this.selectedLocations);

        // Optimize order on server, then open Maps without optimize:true
        this.optimizeAndOpen(this.selectedLocations, window.userCoords, roundTrip);
    }

    async optimizeAndOpen(locations, userCoords, roundTrip) {
        try {
            // Deduplicate waypoints by rounded coordinates to prevent near-identical duplicates in Maps
            const uniq = new Map();
            locations.forEach(l => {
                const key = `${l.retailer || ''}|${(l.full_address||l.address||'').toLowerCase()}|${l.place_id || ''}|${l.lat.toFixed(5)},${l.lng.toFixed(5)}`;
                if (!uniq.has(key)) uniq.set(key, l);
            });
            const uniqueLocations = Array.from(uniq.values());
            const waypoints = uniqueLocations.map(l => ({ lat: l.lat, lng: l.lng }));
            const dest = roundTrip ? null : waypoints[waypoints.length - 1];
            const wpForOptimize = roundTrip ? waypoints : waypoints.slice(0, -1);
            const res = await fetch('/api/route-optimize', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ origin: userCoords, destination: dest, roundTrip, waypoints: wpForOptimize })
            });
            let ordered = locations;
            if (res.ok) {
                const data = await res.json();
                if (Array.isArray(data.waypoint_order)) {
                    const base = roundTrip ? uniqueLocations : uniqueLocations.slice(0, -1);
                    const reordered = data.waypoint_order.map(i => base[i]).filter(Boolean);
                    ordered = roundTrip ? reordered : [...reordered, uniqueLocations[uniqueLocations.length - 1]];
                }
            }
            const url = this.generateGoogleMapsURL_NoOptimize(ordered, userCoords, roundTrip);
            window.open(url, '_blank');

            // Persist and show ordered list for user clarity
            const stopLabels = ordered.map((loc) => {
                const name = (loc.retailer || '').trim();
                const addr = (loc.full_address || loc.address || `${loc.lat.toFixed(5)}, ${loc.lng.toFixed(5)}`).trim();
                return `${[name, addr].filter(Boolean).join(' — ')}`;
            });
            try { localStorage.setItem('routePlanner:lastOrderedStops', JSON.stringify(stopLabels)); } catch {}
            this.showPostGoSummary(stopLabels);
        } catch (e) {
            const fallback = this.generateGoogleMapsURL(locations, userCoords, roundTrip);
            window.open(fallback, '_blank');
        }
    }

    /**
     * Generate Google Maps URL for the route
     */
    generateGoogleMapsURL(locations, userCoords, roundTrip = false) {
        // Always start from user's location
        const originParam = `origin=${userCoords.lat},${userCoords.lng}`;

        const stops = [...locations];
        let destinationParam = '';
        if (roundTrip) {
            destinationParam = `destination=${userCoords.lat},${userCoords.lng}`;
        } else {
            const last = stops[stops.length - 1];
            if (last) destinationParam = `destination=${last.lat},${last.lng}`;
            stops.pop();
        }

        // Use strict lat,lng (or place_id when available) for all waypoints and re-enable
        // Google's built-in optimization. Encode the full value segment to avoid the
        // UI treating 'optimize:true' as a freetext search item.
        // Use strict lat,lng only for waypoints to avoid any place_id resolution issues
        const waypointTokens = ['optimize:true', ...stops.map(loc => `${loc.lat},${loc.lng}`)];
        const waypointsParam = stops.length > 0 ? `waypoints=${encodeURIComponent(waypointTokens.join('|'))}` : '';

        const params = [
            'api=1',
            'travelmode=driving',
            originParam,
            destinationParam,
            waypointsParam
        ].filter(Boolean).join('&');

        const url = `https://www.google.com/maps/dir/?${params}`;

        // Lightweight debug to help diagnose any mismatches in Google Maps
        try {
            const debugRows = locations.map((loc, idx) => ({
                stop: idx + 1,
                retailer: loc.retailer || '',
                address: loc.full_address || loc.address || '',
                lat: loc.lat,
                lng: loc.lng,
                place_id: loc.place_id || ''
            }));
            if (window.__TM_DEBUG__) {
                // eslint-disable-next-line no-console
                console.groupCollapsed('RoutePlanner Debug');
                // eslint-disable-next-line no-console
                console.table(debugRows);
                // eslint-disable-next-line no-console
        console.log('Generated Google Maps URL:', url);
                // eslint-disable-next-line no-console
                console.groupEnd();
            }
        } catch (_) {
            // ignore
        }
        
        return url;
    }

    showPostGoSummary(stopLabels) {
        if (typeof Swal === 'undefined') return;
        const html = `
            <div style="text-align:left; max-height:50vh; overflow:auto;">
                <div style="margin-bottom:8px; color:#6c757d;">Your route has opened in a new tab. Here are the exact stops in order:</div>
                <div style="margin-bottom:12px; color:#dc3545; font-weight:bold; font-size:0.9em;">⚠️ If you don't see the map, make sure your browser isn't blocking popups!</div>
                <ol style="padding-left:18px;">${stopLabels.map(s => `<li style='margin:4px 0;'>${s.replace(/</g,'&lt;')}</li>`).join('')}</ol>
            </div>`;
        Swal.fire({
            title: 'Route opened',
            html,
            width: '90vw',
            maxWidth: 600,
            showCancelButton: true,
            confirmButtonText: 'Copy addresses',
            cancelButtonText: 'Close',
            customClass: {
                popup: 'route-summary-modal'
            },
            didOpen: (popup) => {
                popup.setAttribute('data-route-summary', 'true');
            }
        }).then(async (r) => {
            if (r.isConfirmed) {
                const text = stopLabels.join('\n');
                try { await navigator.clipboard.writeText(text); } catch {}
            }
        });
    }

    // Build URL without optimize:true, assuming locations are already ordered
    generateGoogleMapsURL_NoOptimize(locations, userCoords, roundTrip = false) {
        const originParam = `origin=${userCoords.lat},${userCoords.lng}`;
        const stops = [...locations];
        let destinationParam = '';
        const extraParams = [];
        const formatLabel = (loc) => {
            const name = (loc.retailer || '').trim();
            const addr = (loc.full_address || loc.address || '').trim();
            const label = [name, addr].filter(Boolean).join(' ');
            return label ? encodeURIComponent(label) : null;
        };
        if (roundTrip) {
            destinationParam = `destination=${userCoords.lat},${userCoords.lng}`;
        } else {
            const last = stops[stops.length - 1];
            if (last) {
                const validPid = typeof last.place_id === 'string' && last.place_id.length >= 10 && !/\s/.test(last.place_id);
                if (validPid) {
                    // Pass destination text + companion place_id parameter (preferred pattern for Maps URLs)
                    const label = formatLabel(last) || encodeURIComponent('Destination');
                    destinationParam = `destination=${label}`;
                    extraParams.push(`destination_place_id=${last.place_id}`);
                } else {
                    const label = formatLabel(last);
                    destinationParam = label ? `destination=${label}` : `destination=${last.lat},${last.lng}`;
                }
            }
            stops.pop();
        }
        // Use strict lat,lng for waypoints to avoid Google re-geocoding duplicates
        const waypointVals = stops.map(loc => `${loc.lat},${loc.lng}`);
        const waypointsParam = waypointVals.length > 0 ? `waypoints=${encodeURIComponent(waypointVals.join('|'))}` : '';
        const params = ['api=1','travelmode=driving',originParam,destinationParam,waypointsParam,...extraParams]
            .filter(Boolean)
            .join('&');
        return `https://www.google.com/maps/dir/?${params}`;
    }
}

// Create global instance
window.routePlanner = new RoutePlanner();

// Initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        window.routePlanner.initialize();
    });
} else {
    window.routePlanner.initialize();
}

export default RoutePlanner;