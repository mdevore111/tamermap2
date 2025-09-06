console.error('[map-init-test] ===== TEST FILE LOADING =====');
window.__TEST_LOADED__ = true;

function updateFilterUI(filters) {
    console.log('[map-init-test] updateFilterUI called with:', filters);
}

window.updateFilterUI = updateFilterUI;
console.log('[map-init-test] updateFilterUI defined globally');
