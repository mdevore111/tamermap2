/**
 * Error Handler
 * Handles error display and user notifications
 */

/**
 * Show error message to user
 */
function showErrorMessage(message) {
    // Create or update error display
    let errorDiv = document.getElementById('map-error');
    if (!errorDiv) {
        errorDiv = document.createElement('div');
        errorDiv.id = 'map-error';
        errorDiv.style.cssText = `
            position: absolute;
            top: 10px;
            left: 50%;
            transform: translateX(-50%);
            background: #ff4444;
            color: white;
            padding: 10px 20px;
            border-radius: 4px;
            z-index: 1001;
        `;
        document.getElementById('map').appendChild(errorDiv);
    }
    
    errorDiv.textContent = message;
    errorDiv.style.display = 'block';
    
    // Auto-hide after 5 seconds
    setTimeout(() => {
        errorDiv.style.display = 'none';
    }, 5000);
}

// Export functions
export { showErrorMessage };
