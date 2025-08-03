// Main initialization function that will be called by Google Maps
function initMap() {
    
    
    // Initialize MapConfig first
    if (typeof initMapConfig === 'function') {
        initMapConfig();
    } else {
        console.error('MapConfig initialization function not found');
        return;
    }
    
    // Get configuration from the template
    const configScript = document.getElementById('map-config');
    const config = configScript ? JSON.parse(configScript.textContent) : {};
    
    let autoCenter = true;
    let userLocationMarker = null;
    window.userCoords = null;

    // Try to get user's location first
    if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(
            function(position) {
                const userLat = position.coords.latitude;
                const userLng = position.coords.longitude;
                window.userCoords = { lat: userLat, lng: userLng };
                config.center = { lat: userLat, lng: userLng };
                initializeMapWithConfig(config);

                // Add a marker for the user's location
                userLocationMarker = new google.maps.Marker({
                    position: config.center,
                    map: map,
                    title: 'Your location',
                    icon: {
                        path: google.maps.SymbolPath.CIRCLE,
                        scale: 10,
                        fillColor: '#4285F4',
                        fillOpacity: 1,
                        strokeColor: '#ffffff',
                        strokeWeight: 2
                    }
                });

                // Watch user location and update marker with mobile-friendly settings
                let lastLocationUpdate = 0;
                navigator.geolocation.watchPosition(
                    pos => {
                        const now = Date.now();
                        // Throttle updates to maximum once every 3 seconds
                        if (now - lastLocationUpdate < 3000) return;
                        
                        const newCoords = { lat: pos.coords.latitude, lng: pos.coords.longitude };
                        
                        // Only update if location changed significantly (>10 meters)
                        if (window.userCoords) {
                            const distance = google.maps.geometry.spherical.computeDistanceBetween(
                                new google.maps.LatLng(window.userCoords.lat, window.userCoords.lng),
                                new google.maps.LatLng(newCoords.lat, newCoords.lng)
                            );
                            if (distance < 10) return; // Skip update if moved less than 10 meters
                        }
                        
                        lastLocationUpdate = now;
                        window.userCoords = newCoords;
                        if (userLocationMarker) userLocationMarker.setPosition(newCoords);
                        
                        // Only auto-center if user hasn't interacted with map recently
                        if (autoCenter && window.map && now - (window.lastMapInteraction || 0) > 5000) {
                            window.map.setCenter(newCoords);
                        }
                    },
                    err => console.error('Error watching position:', err),
                    { 
                        enableHighAccuracy: false, // Use network location instead of GPS
                        maximumAge: 30000,         // Accept 30-second old location
                        timeout: 15000             // Longer timeout
                    }
                );

                // Listen for manual interactions to disable auto-centering and track interaction time
                window.map.addListener('dragstart', () => { 
                    autoCenter = false; 
                    window.lastMapInteraction = Date.now();
                });
                window.map.addListener('zoom_changed', () => { 
                    autoCenter = false; 
                    window.lastMapInteraction = Date.now();
                });
                window.map.addListener('click', () => { 
                    window.lastMapInteraction = Date.now();
                });

                // Add "My Location" button
                const myLocationButton = document.createElement('button');
                myLocationButton.innerHTML = `
                  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="24" height="24">
                    <path fill="currentColor" d="M12 22C6.477 22 2 17.523 2 12S6.477 2 12 2s10 4.477 10
                    10-4.477 10-10 10zm1-2.062 A8.004 8.004 0 0 0 19.938 13H16a1 1 0 1 1 0-2h3.938A8.004
                    8.004 0 0 0 13 4.062V8a1 1 0 1 1-2 0V4.062A8.004 8.004 0 0 0 4.062 11H8a1 1 0
                    1 1 0 2H4.062A8.004 8.004 0 0 0 11 19.938V16a1 1 0 1 1 2 0v3.938z"/>
                  </svg>
                `;
                myLocationButton.classList.add('my-location-button');
                myLocationButton.setAttribute('aria-label', 'Center map on your location');
                myLocationButton.addEventListener('click', () => {
                    autoCenter = true;
                    if (window.userCoords && window.map) {
                        window.map.setCenter(window.userCoords);
                        window.map.setZoom(15);
                    }
                });
                window.map.controls[google.maps.ControlPosition.RIGHT_BOTTOM].push(myLocationButton);
            },
            function(error) {
                console.error('Error getting user location:', error);
                initializeMapWithConfig(config);
            }
        );
    } else {
        console.warn('Geolocation is not supported by this browser');
        initializeMapWithConfig(config);
    }
} 