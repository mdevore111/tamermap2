# app/routes/api.py

from flask import Blueprint, jsonify, request
from sqlalchemy import func
from datetime import datetime

from ..extensions import db, cache
from ..models import Retailer, Event
from app.routes.security import check_referrer
from app.utils import get_retailer_locations, get_event_locations

api_bp = Blueprint("api", __name__)


def parse_viewport_bounds():
    """Parse viewport bounds from request parameters"""
    try:
        bounds = {
            'north': request.args.get('north', type=float),
            'south': request.args.get('south', type=float),
            'east': request.args.get('east', type=float),
            'west': request.args.get('west', type=float)
        }
        
        # Validate bounds
        if all(v is not None for v in bounds.values()):
            # Basic sanity checks
            if (bounds['north'] > bounds['south'] and 
                bounds['north'] <= 90 and bounds['south'] >= -90 and
                bounds['east'] >= -180 and bounds['west'] >= -180):
                return bounds
    except (ValueError, TypeError):
        pass
    
    return None


@api_bp.route("/retailers")
@cache.cached(timeout=300, query_string=True)  # Cache with query parameters
def retailers_endpoint():
    """
    Return a JSON list of retailer locations with optional viewport filtering.

    Query Parameters:
        north, south, east, west: Viewport bounds for filtering
        fields_only: If 'false', return all fields (default: true for performance)

    Returns:
        A JSON response containing a list of retailer locations.
    """
    check_referrer()

    # Parse viewport bounds
    bounds = parse_viewport_bounds()
    
    # Check if full fields requested (admin use)
    fields_only = request.args.get('fields_only', 'true').lower() != 'false'
    
    # Get retailer locations with optimizations
    retailers = get_retailer_locations(db, bounds=bounds, fields_only=fields_only)

    # Filter out those with no place_id or a placeholder 'none'
    filtered_retailers = [
        r for r in retailers
        if r.get("place_id") and r["place_id"].strip().lower() != "none"
    ]

    return jsonify({
        'retailers': filtered_retailers,
        'count': len(filtered_retailers),
        'viewport_filtered': bounds is not None
    })


@api_bp.route("/events")
@cache.cached(timeout=180, query_string=True)  # Shorter cache for events (3 min)
def events_endpoint():
    """
    Return a JSON list of events with optional viewport filtering.

    Query Parameters:
        north, south, east, west: Viewport bounds for filtering
        days_ahead: Number of days ahead to include (default: 30)

    Returns:
        A JSON response containing a list of events.
    """
    check_referrer()

    # Parse viewport bounds
    bounds = parse_viewport_bounds()
    
    # Parse days ahead parameter
    days_ahead = request.args.get('days_ahead', 30, type=int)
    if days_ahead > 365:  # Reasonable limit
        days_ahead = 365

    # Get events with filtering
    events = get_event_locations(db, bounds=bounds, days_ahead=days_ahead)

    return jsonify({
        'events': events,
        'count': len(events),
        'viewport_filtered': bounds is not None,
        'days_ahead': days_ahead
    })


@api_bp.route("/map-data")
@cache.cached(timeout=300, query_string=True)
def combined_map_data():
    """
    Return combined map data (retailers + events) in a single request.
    
    This reduces the number of HTTP requests from 2 to 1 for initial map load.

    Query Parameters:
        north, south, east, west: Viewport bounds for filtering
        include_events: Whether to include events (default: true)
        days_ahead: Number of days ahead for events (default: 30)

    Returns:
        A JSON response containing both retailers and events data.
    """
    check_referrer()

    # Parse parameters
    bounds = parse_viewport_bounds()
    include_events = request.args.get('include_events', 'true').lower() != 'false'
    days_ahead = request.args.get('days_ahead', 30, type=int)
    
    # Get retailers (always included)
    retailers = get_retailer_locations(db, bounds=bounds, fields_only=True)
    filtered_retailers = [
        r for r in retailers
        if r.get("place_id") and r["place_id"].strip().lower() != "none"
    ]
    
    # Get events if requested
    events = []
    if include_events:
        events = get_event_locations(db, bounds=bounds, days_ahead=days_ahead)
    
    return jsonify({
        'retailers': filtered_retailers,
        'events': events,
        'retailer_count': len(filtered_retailers),
        'event_count': len(events),
        'viewport_filtered': bounds is not None,
        'timestamp': datetime.now().isoformat()
    })


# Keep legacy endpoints for backward compatibility
@api_bp.route("/retailers-legacy")
def retailers_legacy():
    """Legacy endpoint - use /retailers instead"""
    check_referrer()
    retailers = get_retailer_locations(db, fields_only=False)
    filtered_retailers = [
        r for r in retailers
        if r.get("place_id") and r["place_id"].strip().lower() != "none"
    ]
    return jsonify(filtered_retailers)


@api_bp.route("/events-legacy") 
def events_legacy():
    """Legacy endpoint - use /events instead"""
    check_referrer()
    events = get_event_locations(db)
    return jsonify(events)
