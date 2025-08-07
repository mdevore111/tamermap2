# app/routes/map.py

from datetime import datetime, timedelta

from flask import Blueprint, jsonify, request, session
from sqlalchemy import func

from app.extensions import cache, limiter, db
from app.models import MapUsage, PinInteraction, Retailer
from app.routes.security import check_referrer

map_bp = Blueprint("map", __name__)


@map_bp.route("/track/map", methods=["POST"])
@limiter.limit("60/minute")
def track_map_usage():
    """
    Record a map usage event with latitude, longitude, and zoom level.

    Expects JSON data with 'lat' and 'lng'. Optionally accepts 'zoom_level'.
    Returns a JSON success message or an error if required fields are missing.
    """
    check_referrer()

    data = request.get_json(silent=True)
    if not data:
        return jsonify(success=False, error="Invalid or missing JSON data"), 400

    lat = data.get("lat")
    lng = data.get("lng")

    if lat is None or lng is None:
        return jsonify(success=False, error="Missing lat/lng"), 400

    usage = MapUsage(
        session_id=session.get("user_id", request.remote_addr),
        lat=lat,
        lng=lng,
        zoom_level=data.get("zoom_level")
    )

    db.session.add(usage)
    db.session.commit()
    return jsonify(success=True), 200


@map_bp.route("/track/pin", methods=["POST"])
@limiter.limit("60/minute")
def track_pin_click():
    """
    Record a pin click event with marker ID and location.

    Expects JSON data with 'marker_id', and optionally 'lat' and 'lng'.
    Returns a JSON success message or an error if 'marker_id' is missing.
    """
    check_referrer()

    data = request.get_json(silent=True)
    if not data:
        return jsonify(success=False, error="Invalid or missing JSON data"), 400

    marker_id = data.get("marker_id")
    if not marker_id:
        return jsonify(success=False, error="Missing marker_id"), 400

    marker_id = marker_id.strip()

    lat = data.get("lat")
    lng = data.get("lng")

    click = PinInteraction(
        session_id=session.get("user_id", request.remote_addr),
        marker_id=marker_id,
        lat=lat,
        lng=lng
    )

    db.session.add(click)
    db.session.commit()
    return jsonify(success=True), 200


@map_bp.route("/api/pin-heatmap-data", methods=["GET"])
@cache.cached(timeout=300)  # cache for 5 minutes
@limiter.limit("30/minute")
def get_pin_heatmap_data():
    """
    Retrieve aggregated pin click data for heatmap rendering.

    Joins PinInteraction with Retailer to match coordinates using Google Places IDs,
    aggregating the number of clicks for data within the last 30 days.
    This endpoint is for heatmap display only - coordinates are rounded to 2 decimals.

    Returns:
        A JSON response with a list of objects containing 'lat', 'lng', and 'weight'.
    """
    check_referrer()

    recent_cutoff = datetime.utcnow() - timedelta(days=30)

    # Join PinInteraction with Retailer on matching (trimmed, case-insensitive) IDs
    # Round coordinates for heatmap display only
    data = db.session.query(
        func.round(Retailer.latitude, 2).label("lat"),
        func.round(Retailer.longitude, 2).label("lng"),
        func.count().label("weight")
    ).select_from(PinInteraction).join(
        Retailer,
        Retailer.place_id == PinInteraction.marker_id
    ).filter(
        PinInteraction.timestamp >= recent_cutoff
    ).group_by("lat", "lng").all()

    heatmap = [[lat, lng, weight] for lat, lng, weight in data]
    return jsonify(heatmap)


@map_bp.route("/api/individual-popularity-data", methods=["GET"])
@cache.cached(timeout=300)  # cache for 5 minutes
@limiter.limit("30/minute")
def get_individual_popularity_data():
    """
    Retrieve individual location popularity data with full precision.

    Joins PinInteraction with Retailer to match coordinates using Google Places IDs,
    providing individual location popularity for routing and filtering.
    This endpoint maintains full coordinate precision for individual location targeting.

    Returns:
        A JSON response with a list of objects containing 'lat', 'lng', 'weight', 'place_id', and 'retailer_name'.
    """
    check_referrer()

    recent_cutoff = datetime.utcnow() - timedelta(days=30)

    # Join PinInteraction with Retailer on matching IDs
    # Use full precision coordinates for individual location targeting
    data = db.session.query(
        Retailer.latitude.label("lat"),
        Retailer.longitude.label("lng"),
        func.count().label("weight"),
        Retailer.place_id,
        Retailer.retailer.label("retailer_name")
    ).select_from(PinInteraction).join(
        Retailer,
        Retailer.place_id == PinInteraction.marker_id
    ).filter(
        PinInteraction.timestamp >= recent_cutoff
    ).group_by(
        Retailer.latitude,
        Retailer.longitude,
        Retailer.place_id,
        Retailer.retailer
    ).all()

    # Convert to list of dictionaries for easier frontend consumption
    individual_data = [
        {
            "lat": float(lat),
            "lng": float(lng),
            "weight": weight,
            "place_id": place_id,
            "retailer_name": retailer_name
        }
        for lat, lng, weight, place_id, retailer_name in data
    ]
    
    return jsonify(individual_data)


@map_bp.route("/api/heatmap-data", methods=["GET"])
@cache.cached(timeout=300)
@limiter.limit("30/minute")
def get_heatmap_data():
    """
    Retrieve aggregated map usage data for heatmap rendering.

    Groups map usage records by latitude and longitude from the last 30 days.

    Returns:
        A JSON response with a list of objects containing 'lat', 'lng', and 'weight'.
    """
    check_referrer()

    recent_cutoff = datetime.utcnow() - timedelta(days=30)

    data = db.session.query(
        func.round(MapUsage.lat, 2).label("lat"),
        func.round(MapUsage.lng, 2).label("lng"),
        func.count().label("weight")
    ).filter(
        MapUsage.timestamp >= recent_cutoff
    ).group_by("lat", "lng").all()

    heatmap = [{"lat": lat, "lng": lng, "weight": weight} for lat, lng, weight in data]
    return jsonify(heatmap)


@map_bp.route("/api/pin-stats", methods=["GET"])
@limiter.limit("30/minute")
def get_pin_interaction_counts():
    """
    Retrieve the number of pin clicks per marker.

    Returns:
        A JSON response with a list of objects containing 'marker_id' and 'clicks'.
    """
    check_referrer()

    data = db.session.query(
        PinInteraction.marker_id,
        func.count().label("clicks")
    ).group_by(PinInteraction.marker_id).all()

    result = [{"marker_id": marker_id, "clicks": clicks} for marker_id, clicks in data]
    return jsonify(result)
