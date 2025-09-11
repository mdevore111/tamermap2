"""
Cache Headers Extension for Flask

Provides intelligent cache headers for better browser caching performance.
"""

from flask import request, current_app, url_for
from functools import wraps
import os

def add_cache_headers(response, max_age=3600, public=True, must_revalidate=False):
    """Add cache headers to response"""
    if public:
        response.headers['Cache-Control'] = f'public, max-age={max_age}'
    else:
        response.headers['Cache-Control'] = f'private, max-age={max_age}'
    
    if must_revalidate:
        response.headers['Cache-Control'] += ', must-revalidate'
    
    # Add ETag for better caching
    if hasattr(response, 'data') and response.data:
        import hashlib
        etag = hashlib.md5(response.data).hexdigest()
        response.headers['ETag'] = f'"{etag}"'
    
    return response

def cache_static_assets(response):
    """Add long-term cache headers for static assets"""
    if request.endpoint and request.endpoint.startswith('static'):
        # Static assets can be cached for a long time
        response = add_cache_headers(response, max_age=31536000, public=True)  # 1 year
        response.headers['Expires'] = 'Thu, 31 Dec 2025 23:59:59 GMT'
    return response

def cache_api_responses(response):
    """Add appropriate cache headers for API responses"""
    if request.endpoint and request.endpoint.startswith('api'):
        # API responses should be cached for shorter periods
        if 'retailers' in request.endpoint or 'events' in request.endpoint:
            # Data that changes less frequently
            response = add_cache_headers(response, max_age=300, public=True)  # 5 minutes
        else:
            # Dynamic data
            response = add_cache_headers(response, max_age=60, public=True)   # 1 minute
    return response

def cache_html_pages(response):
    """Add cache headers for HTML pages"""
    if response.content_type and 'text/html' in response.content_type:
        # HTML pages should be cached briefly
        response = add_cache_headers(response, max_age=300, public=True)  # 5 minutes
    return response

def init_cache_headers(app):
    """Initialize cache headers for the Flask app"""
    
    @app.after_request
    def after_request(response):
        """Apply cache headers to all responses"""
        # Skip caching for certain conditions
        if should_skip_caching(response):
            return response
            
        # Apply different caching strategies based on content type
        if request.endpoint and request.endpoint.startswith('static'):
            response = cache_static_assets(response)
        elif request.endpoint and request.endpoint.startswith('api'):
            response = cache_api_responses(response)
        elif response.content_type and 'text/html' in response.content_type:
            response = cache_html_pages(response)
        
        return response

def should_skip_caching(response):
    """Determine if caching should be skipped"""
    # Skip caching for error responses
    if response.status_code >= 400:
        return True
        
    # Skip caching for user-specific content
    if hasattr(request, 'endpoint') and request.endpoint:
        if any(skip_endpoint in request.endpoint for skip_endpoint in [
            'admin', 'user', 'account', 'payment'
        ]):
            return True
    
    # Skip caching for POST/PUT/DELETE requests
    if request.method in ['POST', 'PUT', 'DELETE', 'PATCH']:
        return True
        
    return False

def enable_cache_headers(app):
    """Enable cache headers for the app"""
    init_cache_headers(app)
    current_app.logger.info("Cache headers enabled")
