// static/js/dataService.js
// Centralizes all data-fetching calls for the map application with caching

import { ENDPOINTS } from './config.js';

// Cache configuration
const CACHE_CONFIG = {
  RETAILERS: {
    MEMORY_TTL: 5 * 60 * 1000, // 5 minutes in ms
    LS_KEY: 'tamermap_retailers_cache',
    VERSION: '1.0.0' // Cache version for invalidation
  },
  EVENTS: {
    MEMORY_TTL: 2 * 60 * 1000, // 2 minutes in ms
    LS_KEY: 'tamermap_events_cache',
    VERSION: '1.0.0' // Cache version for invalidation
  }
};

// In-memory cache
const memoryCache = {
  retailers: null,
  events: null
};

/**
 * Check if cache entry is still valid based on timestamp and TTL
 * @param {Object} cacheEntry The cache entry with timestamp and data
 * @param {number} ttl Time-to-live in milliseconds
 * @returns {boolean} True if cache is valid, false if expired
 */
function isCacheValid(cacheEntry, ttl) {
  if (!cacheEntry || !cacheEntry.timestamp || !cacheEntry.data) return false;
  
  const now = Date.now();
  return (now - cacheEntry.timestamp) < ttl;
}

/**
 * Save data to localStorage
 * @param {string} key The localStorage key
 * @param {Object} data The data to cache
 * @param {string} version The cache version
 */
function saveToLocalStorage(key, data, version = '1.0.0') {
  try {
    const cacheEntry = {
      timestamp: Date.now(),
      data: data,
      version: version
    };
    localStorage.setItem(key, JSON.stringify(cacheEntry));
  } catch (error) {
    // Silently fail - data will be fetched from server instead
  }
}

/**
 * Load data from localStorage
 * @param {string} key The localStorage key
 * @param {number} ttl Time-to-live in milliseconds
 * @param {string} expectedVersion The expected cache version
 * @returns {Array|null} The cached data or null if invalid/expired
 */
function loadFromLocalStorage(key, ttl, expectedVersion = '1.0.0') {
  try {
    const cachedData = localStorage.getItem(key);
    if (!cachedData) return null;
    
    const cacheEntry = JSON.parse(cachedData);
    
    // Check if cache version matches
    if (cacheEntry.version !== expectedVersion) {
      console.log(`Cache version mismatch for ${key}: expected ${expectedVersion}, got ${cacheEntry.version}`);
      return null;
    }
    
    return isCacheValid(cacheEntry, ttl) ? cacheEntry.data : null;
  } catch (error) {
    return null;
  }
}

/**
 * Fetch retailer data from the backend API with caching.
 * @param {boolean} [forceRefresh=false] Whether to force a refresh from the server
 * @returns {Promise<Array>} Resolves to an array of retailer objects.
 */
export async function fetchRetailers(forceRefresh = false) {
  // Check memory cache first if not forcing refresh
  if (!forceRefresh && memoryCache.retailers && 
      isCacheValid(memoryCache.retailers, CACHE_CONFIG.RETAILERS.MEMORY_TTL)) {
    return memoryCache.retailers.data;
  }
  
  // Then check localStorage cache if not forcing refresh
  if (!forceRefresh) {
    const localData = loadFromLocalStorage(
      CACHE_CONFIG.RETAILERS.LS_KEY, 
      CACHE_CONFIG.RETAILERS.MEMORY_TTL,
      CACHE_CONFIG.RETAILERS.VERSION
    );
    if (localData) {
      // Update memory cache
      memoryCache.retailers = {
        timestamp: Date.now(),
        data: localData
      };
      return localData;
    }
  }
  
  // Fetch from server if cache invalid or forcing refresh
  try {
    const response = await fetch(ENDPOINTS.retailers);
    if (!response.ok) {
      throw new Error(`Failed fetching retailers: ${response.status}`);
    }
    
    const data = await response.json();
    
    // Update caches
    memoryCache.retailers = {
      timestamp: Date.now(),
      data: data
    };
    
    saveToLocalStorage(CACHE_CONFIG.RETAILERS.LS_KEY, data, CACHE_CONFIG.RETAILERS.VERSION);
    
    return data;
  } catch (error) {
    if (window.__TM_DEBUG__) console.error('Error fetching retailers:', error);
    throw error;
  }
}

/**
 * Fetch event data from the backend API with caching.
 * @param {boolean} [forceRefresh=false] Whether to force a refresh from the server
 * @returns {Promise<Array>} Resolves to an array of event objects.
 */
export async function fetchEvents(forceRefresh = false) {
  // Check memory cache first if not forcing refresh
  if (!forceRefresh && memoryCache.events && 
      isCacheValid(memoryCache.events, CACHE_CONFIG.EVENTS.MEMORY_TTL)) {
    return memoryCache.events.data;
  }
  
  // Then check localStorage cache if not forcing refresh
  if (!forceRefresh) {
    const localData = loadFromLocalStorage(
      CACHE_CONFIG.EVENTS.LS_KEY, 
      CACHE_CONFIG.EVENTS.MEMORY_TTL,
      CACHE_CONFIG.EVENTS.VERSION
    );
    if (localData) {
      // Update memory cache
      memoryCache.events = {
        timestamp: Date.now(),
        data: localData
      };
      return localData;
    }
  }
  
  // Fetch from server if cache invalid or forcing refresh
  try {
    const response = await fetch(ENDPOINTS.events);
    if (!response.ok) {
      throw new Error(`Failed fetching events: ${response.status}`);
    }
    
    const data = await response.json();
    
    // Update caches
    memoryCache.events = {
      timestamp: Date.now(),
      data: data
    };
    
    saveToLocalStorage(CACHE_CONFIG.EVENTS.LS_KEY, data, CACHE_CONFIG.EVENTS.VERSION);
    
    return data;
  } catch (error) {
    if (window.__TM_DEBUG__) console.error('Error fetching events:', error);
    throw error;
  }
}

/**
 * Refresh all cached data by forcing a server fetch
 * @returns {Promise<void>}
 */
export async function refreshCache() {
  try {
    await Promise.all([
      fetchRetailers(true),
      fetchEvents(true)
    ]);
  } catch (error) {
    // Silently fail - next request will fetch fresh data
    throw error;
  }
}

/**
 * Clear all cached data, both memory and localStorage
 */
export function clearCache() {
  // Clear memory cache
  memoryCache.retailers = null;
  memoryCache.events = null;
  
  // Clear localStorage cache
  try {
    localStorage.removeItem(CACHE_CONFIG.RETAILERS.LS_KEY);
    localStorage.removeItem(CACHE_CONFIG.EVENTS.LS_KEY);
  } catch (error) {
    // Silently fail - next request will fetch fresh data
  }
}

/**
 * Enhanced data service with viewport filtering and combined requests
 */
class DataService {
    constructor() {
        this.cache = new Map();
        this.lastViewport = null;
        this.cacheTimeout = 5 * 60 * 1000; // 5 minutes
        this.requestQueue = [];
        this.isLoading = false;
    }

    /**
     * Load combined map data (retailers + events) in a single request
     * This reduces HTTP requests from 2 to 1 for initial load
     */
    async loadMapData(bounds = null, options = {}) {
        const {
            includeEvents = true,
            daysAhead = 30,
            forceRefresh = false
        } = options;

        // Create cache key
        const cacheKey = this.createCacheKey('map-data', bounds, { includeEvents, daysAhead });
        
        // Check cache first
        if (!forceRefresh && this.cache.has(cacheKey)) {
            const cached = this.cache.get(cacheKey);
            if (Date.now() - cached.timestamp < this.cacheTimeout) {
                return cached.data;
            }
        }

        try {
            // Build query parameters
            const params = new URLSearchParams();
            
            if (bounds) {
                params.append('north', bounds.north);
                params.append('south', bounds.south);
                params.append('east', bounds.east);
                params.append('west', bounds.west);
            }
            
            params.append('include_events', includeEvents);
            params.append('days_ahead', daysAhead);

            const response = await fetch(`/api/map-data?${params.toString()}`);
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const data = await response.json();
            
            // Cache the result
            this.cache.set(cacheKey, {
                data: data,
                timestamp: Date.now()
            });

            return data;

        } catch (error) {
            if (window.__TM_DEBUG__) console.error('Error loading map data:', error);
            throw error;
        }
    }

    /**
     * Load retailers with viewport filtering
     */
    async loadRetailers(bounds = null, fieldsOnly = true) {
        const cacheKey = this.createCacheKey('retailers', bounds, { fieldsOnly });
        
        // Check cache
        if (this.cache.has(cacheKey)) {
            const cached = this.cache.get(cacheKey);
            if (Date.now() - cached.timestamp < this.cacheTimeout) {
                return cached.data;
            }
        }

        try {
            const params = new URLSearchParams();
            
            if (bounds) {
                params.append('north', bounds.north);
                params.append('south', bounds.south);
                params.append('east', bounds.east);
                params.append('west', bounds.west);
            }
            
            params.append('fields_only', fieldsOnly);

            const response = await fetch(`/api/retailers?${params.toString()}`);
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const data = await response.json();
            
            // Cache the result
            this.cache.set(cacheKey, {
                data: data.retailers || data, // Handle both new and legacy formats
                timestamp: Date.now()
            });

            return data.retailers || data;

        } catch (error) {
            console.error('Error loading retailers:', error);
            throw error;
        }
    }

    /**
     * Load events with viewport filtering
     */
    async loadEvents(bounds = null, daysAhead = 30) {
        const cacheKey = this.createCacheKey('events', bounds, { daysAhead });
        
        // Check cache
        if (this.cache.has(cacheKey)) {
            const cached = this.cache.get(cacheKey);
            if (Date.now() - cached.timestamp < this.cacheTimeout) {
                return cached.data;
            }
        }

        try {
            const params = new URLSearchParams();
            
            if (bounds) {
                params.append('north', bounds.north);
                params.append('south', bounds.south);
                params.append('east', bounds.east);
                params.append('west', bounds.west);
            }
            
            params.append('days_ahead', daysAhead);

            const response = await fetch(`/api/events?${params.toString()}`);
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const data = await response.json();
            
            // Cache the result
            this.cache.set(cacheKey, {
                data: data.events || data, // Handle both new and legacy formats
                timestamp: Date.now()
            });

            return data.events || data;

        } catch (error) {
            console.error('Error loading events:', error);
            throw error;
        }
    }

    /**
     * Create a cache key based on endpoint, bounds, and options
     */
    createCacheKey(endpoint, bounds, options = {}) {
        let key = endpoint;
        
        if (bounds) {
            key += `_${bounds.north}_${bounds.south}_${bounds.east}_${bounds.west}`;
        }
        
        Object.keys(options).forEach(optKey => {
            key += `_${optKey}:${options[optKey]}`;
        });
        
        return key;
    }

    /**
     * Get map bounds from Google Maps instance
     */
    getMapBounds(map) {
        const bounds = map.getBounds();
        if (!bounds) return null;

        const ne = bounds.getNorthEast();
        const sw = bounds.getSouthWest();

        return {
            north: ne.lat(),
            south: sw.lat(),
            east: ne.lng(),
            west: sw.lng()
        };
    }

    /**
     * Check if viewport has changed significantly
     */
    hasViewportChanged(newBounds, threshold = 0.1) {
        if (!this.lastViewport || !newBounds) return true;

        const latDiff = Math.abs(newBounds.north - this.lastViewport.north) + 
                      Math.abs(newBounds.south - this.lastViewport.south);
        const lngDiff = Math.abs(newBounds.east - this.lastViewport.east) + 
                      Math.abs(newBounds.west - this.lastViewport.west);

        const latRange = newBounds.north - newBounds.south;
        const lngRange = newBounds.east - newBounds.west;

        return (latDiff / latRange > threshold) || (lngDiff / lngRange > threshold);
    }

    /**
     * Update last viewport for change detection
     */
    updateLastViewport(bounds) {
        this.lastViewport = bounds;
    }

    /**
     * Clear cache (useful for debugging or forced refresh)
     */
    clearCache() {
        this.cache.clear();
    }

    /**
     * Get cache statistics
     */
    getCacheStats() {
        return {
            size: this.cache.size,
            keys: Array.from(this.cache.keys())
        };
    }
}

// Export the DataService class
export { DataService };
