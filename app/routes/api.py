# app/routes/api.py

from flask import Blueprint, jsonify, request, current_app
from flask_security import login_required
from sqlalchemy import func
from datetime import datetime

from ..extensions import db, cache
from ..models import Retailer, Event, UserNote
from app.routes.security import check_referrer
from app.utils import get_retailer_locations, get_event_locations
import requests
import urllib.parse
import json

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

    # Add user notes for logged-in users
    from flask_login import current_user
    if current_user.is_authenticated:
        for retailer in filtered_retailers:
            note = UserNote.query.filter_by(
                user_id=current_user.id, 
                retailer_id=retailer['id']
            ).first()
            retailer['user_notes'] = note.notes if note else None

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


@api_bp.route('/route-optimize', methods=['POST'])
@login_required
def route_optimize():
    """
    Server-side waypoint optimization using Google Routes Preferred (v2).
    Expects JSON body: { origin: {lat,lng}, destination: {lat,lng} or null if roundTrip,
                         roundTrip: bool, waypoints: [{lat,lng}, ...] }
    Returns: { waypoint_order: [int,...] }
    """
    try:
        payload = request.get_json(force=True) or {}
        origin = payload.get('origin')
        destination = payload.get('destination')
        round_trip = bool(payload.get('roundTrip'))
        waypoints = payload.get('waypoints') or []

        if not origin or not isinstance(waypoints, list) or len(waypoints) == 0:
            return jsonify({'error': 'origin and waypoints are required'}), 400

        # Compute destination for round trips
        dest = destination
        if round_trip:
            dest = origin

        # Prefer a dedicated server-side key if provided; fall back to browser key
        api_key = (current_app.config.get('GOOGLE_SERVER_API_KEY')
                   or current_app.config.get('GOOGLE_API_KEY'))
        if not api_key:
            return jsonify({'error': 'server not configured with GOOGLE_API_KEY'}), 500

        # Use Routes Preferred v2 computeRoutes only
        origin_body = {'location': {'latLng': {'latitude': origin['lat'], 'longitude': origin['lng']}}}
        destination_body = {'location': {'latLng': {'latitude': dest['lat'], 'longitude': dest['lng']}}}
        intermediates_body = [
            {'location': {'latLng': {'latitude': w['lat'], 'longitude': w['lng']}}}
            for w in waypoints
        ]
        body = {
            'origin': origin_body,
            'destination': destination_body,
            'intermediates': intermediates_body,
            'travelMode': 'DRIVE',
            'routingPreference': 'TRAFFIC_AWARE',
            'optimizeWaypointOrder': True
        }
        headers = {
            'Content-Type': 'application/json',
            'X-Goog-Api-Key': api_key,
            'X-Goog-FieldMask': 'routes.optimizedIntermediateWaypointIndex'
        }
        v2_url = 'https://routes.googleapis.com/directions/v2:computeRoutes'
        current_app.logger.info(f"Directions v2 request body: {json.dumps(body)[:500]}")
        v2_resp = requests.post(v2_url, headers=headers, json=body, timeout=12)
        v2_json = v2_resp.json()
        order = (v2_json.get('routes') or [{}])[0].get('optimizedIntermediateWaypointIndex')
        if isinstance(order, list):
            return jsonify({'waypoint_order': order})
        current_app.logger.warning(f"Directions v2 failed: {v2_json}")
        return jsonify({'error': 'directions_failed'}), 502
    except Exception as exc:
        return jsonify({'error': 'server_error', 'message': str(exc)}), 500


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


# User Notes API Endpoints
@api_bp.route("/user-notes/<int:retailer_id>", methods=['GET'])
@login_required
def get_user_note(retailer_id):
    """Get user's note for a specific retailer location"""
    from flask_login import current_user
    
    note = UserNote.query.filter_by(
        user_id=current_user.id, 
        retailer_id=retailer_id
    ).first()
    
    if note:
        return jsonify({
            'id': note.id,
            'notes': note.notes,
            'created_at': note.created_at.isoformat(),
            'updated_at': note.updated_at.isoformat()
        })
    else:
        return jsonify({'notes': ''})


@api_bp.route("/user-notes/<int:retailer_id>", methods=['POST', 'PUT'])
@login_required
def save_user_note(retailer_id):
    """Create or update user's note for a specific retailer location"""
    from flask_login import current_user
    
    data = request.get_json()
    notes = data.get('notes', '').strip()
    
    if not notes:
        # Delete note if empty
        note = UserNote.query.filter_by(
            user_id=current_user.id, 
            retailer_id=retailer_id
        ).first()
        if note:
            db.session.delete(note)
            db.session.commit()
        return jsonify({'message': 'Note deleted'})
    
    # Check if retailer exists
    retailer = Retailer.query.get(retailer_id)
    if not retailer:
        return jsonify({'error': 'Retailer not found'}), 404
    
    # Create or update note
    note = UserNote.query.filter_by(
        user_id=current_user.id, 
        retailer_id=retailer_id
    ).first()
    
    if note:
        note.notes = notes
        note.updated_at = datetime.utcnow()
    else:
        note = UserNote(
            user_id=current_user.id,
            retailer_id=retailer_id,
            notes=notes
        )
        db.session.add(note)
    
    try:
        db.session.commit()
        return jsonify({
            'id': note.id,
            'notes': note.notes,
            'created_at': note.created_at.isoformat(),
            'updated_at': note.updated_at.isoformat()
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to save note'}), 500


@api_bp.route("/user-notes/<int:retailer_id>", methods=['DELETE'])
@login_required
def delete_user_note(retailer_id):
    """Delete user's note for a specific retailer location"""
    from flask_login import current_user
    
    note = UserNote.query.filter_by(
        user_id=current_user.id, 
        retailer_id=retailer_id
    ).first()
    
    if note:
        db.session.delete(note)
        db.session.commit()
        return jsonify({'message': 'Note deleted'})
    else:
        return jsonify({'error': 'Note not found'}), 404
