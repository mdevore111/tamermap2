# app/routes/map.py

from datetime import datetime, timedelta

from flask import Blueprint, jsonify, request, session
from sqlalchemy import func

from app.extensions import cache, limiter, db
from app.models import MapUsage, PinInteraction, Retailer, PinPopularity, LegendClick, RouteEvent
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
    place_id = (data.get("place_id") or marker_id).strip()

    click = PinInteraction(
        session_id=session.get("user_id", request.remote_addr),
        marker_id=marker_id,
        place_id=place_id,
        lat=lat,
        lng=lng
    )

    db.session.add(click)
    # Upsert into PinPopularity by place_id
    existing = PinPopularity.query.get(place_id)
    now = datetime.utcnow()
    if existing:
        existing.total_clicks = (existing.total_clicks or 0) + 1
        existing.last_clicked_at = now
        if lat is not None and lng is not None:
            existing.last_lat = lat
            existing.last_lng = lng
    else:
        db.session.add(PinPopularity(
            place_id=place_id,
            total_clicks=1,
            last_clicked_at=now,
            last_lat=lat,
            last_lng=lng
        ))
    db.session.commit()
    return jsonify(success=True), 200


@map_bp.route("/api/pin-heatmap-data", methods=["GET"])
@cache.cached(timeout=60, query_string=True)  # Reduced cache timeout for testing
@limiter.limit("60/minute")  # Increased for testing
def get_pin_heatmap_data():
    """
    Retrieve aggregated pin click data for heatmap rendering.

    Joins PinInteraction with Retailer to match coordinates using Google Places IDs,
    aggregating the number of clicks for data within the specified time range.
    This endpoint is for heatmap display only - coordinates are rounded to 2 decimals.

    Query Parameters:
        days (int): Number of days to look back (1-60, default: 60)

    Returns:
        A JSON response with a list of objects containing 'lat', 'lng', and 'weight'.
    """
    check_referrer()

    # Get days parameter, default to 60, clamp between 1-60
    days = max(1, min(60, int(request.args.get('days', 60))))
    recent_cutoff = datetime.utcnow() - timedelta(days=days)
    
    # Debug logging  
    print(f"[DEBUG] pin-heatmap-data called with days={days}, cutoff={recent_cutoff}")

    # Use time-filtered PinInteraction data to respect the days parameter
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
    print(f"[DEBUG] pin-heatmap-data returning {len(heatmap)} points for {days} days")
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

    recent_cutoff = datetime.utcnow() - timedelta(days=60)

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
        PinInteraction.timestamp >= recent_cutoff,
        Retailer.latitude.isnot(None),
        Retailer.longitude.isnot(None)
    ).group_by(
        Retailer.latitude,
        Retailer.longitude,
        Retailer.place_id,
        Retailer.retailer
    ).all()

    # Convert to list of dictionaries for easier frontend consumption
    individual_data = []
    for lat, lng, weight, place_id, retailer_name in data:
        # Double-guard in case of unexpected NULLs
        if lat is None or lng is None:
            continue
        try:
            individual_data.append({
                "lat": float(lat),
                "lng": float(lng),
                "weight": int(weight) if weight is not None else 0,
                "place_id": place_id,
                "retailer_name": retailer_name
            })
        except Exception:
            # Skip malformed rows defensively
            continue
    
    return jsonify(individual_data)


@map_bp.route("/api/heatmap-data", methods=["GET"])
@cache.cached(timeout=300, query_string=True)  # cache with query parameters
@limiter.limit("30/minute")
def get_heatmap_data():
    """
    Retrieve aggregated map usage data for heatmap rendering.

    Groups map usage records by latitude and longitude from the specified time range.

    Query Parameters:
        days (int): Number of days to look back (1-60, default: 60)

    Returns:
        A JSON response with a list of objects containing 'lat', 'lng', and 'weight'.
    """
    check_referrer()

    # Get days parameter, default to 60, clamp between 1-60
    days = max(1, min(60, int(request.args.get('days', 60))))
    recent_cutoff = datetime.utcnow() - timedelta(days=days)

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

    # Prefer place_id popularity totals
    data = db.session.query(
        PinPopularity.place_id,
        PinPopularity.total_clicks
    ).all()

    result = [{"place_id": pid, "clicks": clicks} for pid, clicks in data]
    return jsonify(result)


@map_bp.route('/track/legend', methods=['POST'])
@limiter.limit("120/minute")
def track_legend_click():
    check_referrer()
    data = request.get_json(silent=True) or {}
    control_id = (data.get('control_id') or '').strip()
    if not control_id:
        return jsonify(success=False, error='control_id required'), 400

    sess_id = session.get('visitor_session_id') or session.get('user_id') or request.remote_addr
    user_id = session.get('user_id') if isinstance(session.get('user_id'), int) else None
    
    # Debug logging
    print(f"🔍 DEBUG: track_legend_click - user_id: {user_id}, session keys: {list(session.keys())}")
    print(f"🔍 DEBUG: session.get('is_pro'): {session.get('is_pro')}, session.get('user_id'): {session.get('user_id')}")
    
    # Better Pro user detection - check session first, then fall back to database lookup
    is_pro = False
    if user_id:
        try:
            from app.models import User
            user = User.query.get(user_id)
            if user and user.is_pro:
                is_pro = True
                print(f"🔍 DEBUG: User {user_id} is Pro (from database)")
            else:
                print(f"🔍 DEBUG: User {user_id} is NOT Pro (from database)")
        except Exception as e:
            print(f"🔍 DEBUG: Error looking up user {user_id}: {e}")
            pass
    
    # Fall back to session if database lookup fails
    if not is_pro:
        is_pro = bool(session.get('is_pro'))
        print(f"🔍 DEBUG: Fallback to session: is_pro = {is_pro}")
    
    print(f"🔍 DEBUG: Final is_pro value: {is_pro}")

    click = LegendClick(
        session_id=sess_id,
        user_id=user_id,
        is_pro=is_pro,
        control_id=control_id,
        path=data.get('path'),
        zoom=data.get('zoom'),
        center_lat=data.get('center_lat'),
        center_lng=data.get('center_lng')
    )
    db.session.add(click)
    db.session.commit()
    return jsonify(success=True)


@map_bp.route('/track/route', methods=['POST'])
@limiter.limit("120/minute")
def track_route_event():
    check_referrer()
    data = request.get_json(silent=True) or {}
    event = (data.get('event') or '').strip().lower()
    if event not in ('open', 'preview', 'go'):
        return jsonify(success=False, error='invalid event'), 400

    sess_id = session.get('visitor_session_id') or session.get('user_id') or request.remote_addr
    user_id = session.get('user_id') if isinstance(session.get('user_id'), int) else None
    
    # Debug logging
    print(f"🔍 DEBUG: track_route_event - user_id: {user_id}, session keys: {list(session.keys())}")
    print(f"🔍 DEBUG: session.get('is_pro'): {session.get('is_pro')}, session.get('user_id'): {session.get('user_id')}")
    
    # Better Pro user detection - check session first, then fall back to database lookup
    is_pro = False
    if user_id:
        try:
            from app.models import User
            user = User.query.get(user_id)
            if user and user.is_pro:
                is_pro = True
                print(f"🔍 DEBUG: User {user_id} is Pro (from database)")
            else:
                print(f"🔍 DEBUG: User {user_id} is NOT Pro (from database)")
        except Exception as e:
            print(f"🔍 DEBUG: Error looking up user {user_id}: {e}")
            pass
    
    # Fall back to session if database lookup fails
    if not is_pro:
        is_pro = bool(session.get('is_pro'))
        print(f"🔍 DEBUG: Fallback to session: is_pro = {is_pro}")
    
    print(f"🔍 DEBUG: Final is_pro value: {is_pro}")

    re = RouteEvent(
        session_id=sess_id,
        user_id=user_id,
        is_pro=is_pro,
        event=event,
        max_distance=data.get('max_distance'),
        max_stops=data.get('max_stops'),
        options_json=data.get('options_json')
    )
    db.session.add(re)
    db.session.commit()
    return jsonify(success=True)


@map_bp.route('/api/admin/engagement/legend', methods=['GET'])
def engagement_legend():
    days = int(request.args.get('days', 30))
    cutoff = datetime.utcnow() - timedelta(days=days)
    rows = db.session.query(
        LegendClick.control_id,
        LegendClick.is_pro,
        func.count().label('cnt')
    ).filter(
        LegendClick.created_at >= cutoff
    ).group_by(LegendClick.control_id, LegendClick.is_pro).all()
    result = {}
    for control_id, is_pro, cnt in rows:
        bucket = result.setdefault(control_id, {"pro": 0, "non_pro": 0})
        bucket['pro' if is_pro else 'non_pro'] += cnt
    return jsonify(result)


@map_bp.route('/api/admin/engagement/route', methods=['GET'])
def engagement_route():
    days = int(request.args.get('days', 30))
    cutoff = datetime.utcnow() - timedelta(days=days)
    # Totals per event
    totals = dict(db.session.query(RouteEvent.event, func.count()).filter(RouteEvent.created_at >= cutoff).group_by(RouteEvent.event).all())
    # Unique sessions that opened
    open_sessions = db.session.query(func.count(func.distinct(RouteEvent.session_id))).filter(RouteEvent.created_at >= cutoff, RouteEvent.event == 'open').scalar() or 0
    go_sessions = db.session.query(func.count(func.distinct(RouteEvent.session_id))).filter(RouteEvent.created_at >= cutoff, RouteEvent.event == 'go').scalar() or 0
    completion_rate = (go_sessions / open_sessions) if open_sessions else 0
    return jsonify({
        'totals': totals,
        'sessions_open': open_sessions,
        'sessions_go': go_sessions,
        'completion_rate': completion_rate
    })
