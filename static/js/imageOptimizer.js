/**
 * Image Optimization Helper
 * Handles WebP support detection and fallback to PNG
 */

/**
 * Check if browser supports WebP format
 */
export function supportsWebP() {
    return new Promise((resolve) => {
        const webP = new Image();
        webP.onload = webP.onerror = () => {
            resolve(webP.height === 2);
        };
        webP.src = 'data:image/webp;base64,UklGRjoAAABXRUJQVlA4IC4AAACyAgCdASoCAAIALmk0mk0iIiIiIgBoSygABc6WWgAA/veff/0PP8bA//LwYAAA';
    });
}

/**
 * Get optimized image URL with WebP fallback
 */
export function getOptimizedImageUrl(basePath, filename) {
    const baseUrl = basePath.replace('.png', '');
    
    // Check if WebP is supported
    if (window.webpSupported === undefined) {
        supportsWebP().then(supported => {
            window.webpSupported = supported;
        });
    }
    
    // Return WebP if supported, otherwise PNG
    if (window.webpSupported === true) {
        return `${baseUrl}.webp`;
    } else {
        return `${baseUrl}.png`;
    }
}

/**
 * Preload critical images with WebP support
 */
export function preloadCriticalImages() {
    const criticalImages = [
        'safeway.png',
        'qfc.png', 
        'fred-meyer.png',
        'card-shop.png',
        'best-buy.png',
        'target.png',
        'other.png'
    ];
    
    criticalImages.forEach(filename => {
        const link = document.createElement('link');
        link.rel = 'preload';
        link.as = 'image';
        link.href = getOptimizedImageUrl(`/static/map-pins/${filename}`, filename);
        document.head.appendChild(link);
    });
}
