"""
Resource Preloader for Flask

Provides HTTP/2 push and resource preloading for critical assets.
"""

from flask import request, current_app, url_for
from functools import wraps

def add_preload_headers(response, resources):
    """Add preload headers for critical resources"""
    preload_headers = []
    
    for resource in resources:
        if resource['type'] == 'style':
            preload_headers.append(f'<{resource["url"]}>; rel=preload; as=style')
        elif resource['type'] == 'script':
            preload_headers.append(f'<{resource["url"]}>; rel=preload; as=script')
        elif resource['type'] == 'font':
            preload_headers.append(f'<{resource["url"]}>; rel=preload; as=font; type=font/woff2')
        elif resource['type'] == 'image':
            preload_headers.append(f'<{resource["url"]}>; rel=preload; as=image')
    
    if preload_headers:
        response.headers['Link'] = ', '.join(preload_headers)
    
    return response

def get_critical_resources():
    """Get list of critical resources for the current page"""
    resources = []
    
    # Critical CSS files
    resources.extend([
        {'url': url_for('static', filename='css/base.css'), 'type': 'style'},
        {'url': url_for('static', filename='css/maps.css'), 'type': 'style'},
    ])
    
    # Critical JavaScript files
    resources.extend([
        {'url': url_for('static', filename='js/config.js'), 'type': 'script'},
        {'url': url_for('static', filename='js/utils.js'), 'type': 'script'},
        {'url': url_for('static', filename='js/map-core.js'), 'type': 'script'},
    ])
    
    # Critical images (only for maps page)
    if request.endpoint == 'public.splash':
        resources.extend([
            {'url': url_for('static', filename='map-pins/safeway.png'), 'type': 'image'},
            {'url': url_for('static', filename='map-pins/qfc.png'), 'type': 'image'},
            {'url': url_for('static', filename='map-pins/fred-meyer.png'), 'type': 'image'},
            {'url': url_for('static', filename='map-pins/card-shop.png'), 'type': 'image'},
        ])
    
    return resources

def add_dns_prefetch():
    """Add DNS prefetch for external domains"""
    external_domains = [
        'https://maps.googleapis.com',
        'https://cdn.jsdelivr.net',
        'https://cdnjs.cloudflare.com',
        'https://fonts.googleapis.com',
        'https://fonts.gstatic.com'
    ]
    
    prefetch_headers = []
    for domain in external_domains:
        prefetch_headers.append(f'<{domain}>; rel=dns-prefetch')
    
    return prefetch_headers

def init_resource_preloader(app):
    """Initialize resource preloader for the Flask app"""
    
    @app.after_request
    def after_request(response):
        """Add preload headers to responses"""
        # Only add preload headers to HTML responses
        if (response.content_type and 'text/html' in response.content_type and 
            response.status_code == 200):
            
            # Add critical resource preloading
            critical_resources = get_critical_resources()
            response = add_preload_headers(response, critical_resources)
            
            # Add DNS prefetch
            dns_prefetch = add_dns_prefetch()
            if dns_prefetch:
                existing_link = response.headers.get('Link', '')
                if existing_link:
                    response.headers['Link'] = existing_link + ', ' + ', '.join(dns_prefetch)
                else:
                    response.headers['Link'] = ', '.join(dns_prefetch)
        
        return response

def enable_resource_preloader(app):
    """Enable resource preloader for the app"""
    init_resource_preloader(app)
    current_app.logger.info("Resource preloader enabled")
