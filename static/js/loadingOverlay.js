/**
 * Loading Overlay Management
 * Handles the loading spinner and overlay display
 */

let loadingOverlay;

/**
 * Initialize the loading overlay
 */
function initLoadingOverlay() {
  if (loadingOverlay) return;
  
  loadingOverlay = document.createElement('div');
  loadingOverlay.id = 'loading-overlay';
  loadingOverlay.style.cssText = `
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background: rgba(0, 0, 0, 0.5);
    display: flex;
    justify-content: center;
    align-items: center;
    z-index: 9999;
  `;
  
  const spinner = document.createElement('div');
  spinner.style.cssText = `
    width: 50px;
    height: 50px;
    border: 5px solid #f3f3f3;
    border-top: 5px solid #3498db;
    border-radius: 50%;
    animation: spin 1s linear infinite;
  `;
  
  // Add CSS animation
  const style = document.createElement('style');
  style.textContent = `
    @keyframes spin {
      0% { transform: rotate(0deg); }
      100% { transform: rotate(360deg); }
    }
  `;
  document.head.appendChild(style);
  
  loadingOverlay.appendChild(spinner);
  document.body.appendChild(loadingOverlay);
  loadingOverlay.style.display = 'none';
}

/**
 * Show the loading overlay
 */
function showLoadingOverlay() {
  if (loadingOverlay) {
    loadingOverlay.style.display = 'flex';
  }
}

/**
 * Hide the loading overlay
 */
function hideLoadingOverlay() {
  if (loadingOverlay) {
    loadingOverlay.style.display = 'none';
  }
}

// Export functions
export { initLoadingOverlay, showLoadingOverlay, hideLoadingOverlay };
