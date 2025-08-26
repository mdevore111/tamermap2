"""
Development-only routes.
These routes are only registered when running in development mode.
"""

import os
from functools import wraps
from flask import Blueprint, jsonify, request, abort, render_template, current_app
from flask_security import roles_required
from app.extensions import limiter, cache
from datetime import datetime

dev_bp = Blueprint("dev", __name__)

def dev_only(f):
    """Decorator to ensure route only works in development environment"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        is_dev = os.environ.get('FLASK_ENV') == 'development'
        is_staging = 'dev.tamermap.com' in request.host
        if not (is_dev or is_staging):
            abort(404)  # Return 404 in production to hide endpoint existence
        return f(*args, **kwargs)
    return decorated_function

def require_test_key(f):
    """Decorator to require test API key"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        api_key = request.headers.get('X-Test-Key')
        if not api_key or api_key != os.environ.get('TEST_API_KEY', 'test_key_local'):
            abort(403)
        return f(*args, **kwargs)
    return decorated_function

@dev_bp.route("/environment-check")
@dev_only
@require_test_key
@roles_required('Admin')
def check_environment():
    """Check the current environment configuration"""
    return jsonify({
        "FLASK_ENV": os.environ.get('FLASK_ENV'),
        "DEBUG": current_app.debug,
        "ENV": current_app.env,
        "HOST": request.host,
        "IS_STAGING": 'dev.tamermap.com' in request.host
    })

@dev_bp.route("/test-limit")
@dev_only
@require_test_key
@roles_required('Admin')
@limiter.limit("3 per minute")
def test_rate_limit():
    """
    Test endpoint for rate limiting.
    Only available in development environment or on staging.
    Requires X-Test-Key header.
    Limited to 3 requests per minute.
    """
    return jsonify({
        "message": "Rate limit test successful",
        "status": "ok",
        "environment": os.environ.get('FLASK_ENV', 'development'),
        "host": request.host
    })

@dev_bp.route("/test-cache")
@dev_only
@require_test_key
@roles_required('Admin')
def test_cache():
    """
    Test endpoint for cache functionality.
    Only available in development environment or on staging.
    Requires X-Test-Key header.
    """
    return render_template("dev/test-cache.html")

@dev_bp.route("/api/test-cache-data")
@dev_only
@require_test_key
@roles_required('Admin')
@cache.cached(timeout=60)  # Cache for 1 minute
def test_cache_data():
    """
    Test endpoint that returns cached data.
    The response includes a timestamp to verify caching.
    Only available in development environment or on staging.
    Requires X-Test-Key header.
    """
    current_time = datetime.now().strftime("%H:%M:%S.%f")
    return jsonify({
        "message": "Cache test data",
        "timestamp": current_time,
        "cache_status": "This response is cached for 60 seconds",
        "host": request.host
    }) 