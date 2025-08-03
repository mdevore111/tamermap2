"""
Session ID generation and tracking middleware.
This module provides utilities for generating and managing session IDs
for improved user journey tracking.
"""

import uuid
import hashlib
from datetime import datetime, timedelta
from flask import request, g, current_app
from app.models import VisitorLog
from app import db


def generate_session_id():
    """Generate a unique session ID."""
    return str(uuid.uuid4())


def get_or_create_session_id():
    """
    Get existing session ID from cookie or create a new one.
    Returns the session ID and whether it's a new session.
    """
    session_id = request.cookies.get('tamermap_session_id')
    is_new_session = False
    
    if not session_id:
        session_id = generate_session_id()
        is_new_session = True
    
    return session_id, is_new_session


def log_visit_with_session(request, response, **kwargs):
    """
    Log a visit with session ID tracking.
    
    Args:
        request: Flask request object
        response: Flask response object
        **kwargs: Additional fields to log
    """
    try:
        # Get or create session ID
        session_id, is_new_session = get_or_create_session_id()
        
        # Set session cookie if it's a new session
        if is_new_session:
            # Set cookie to expire in 30 days
            response.set_cookie(
                'tamermap_session_id', 
                session_id, 
                max_age=30 * 24 * 3600,  # 30 days
                httponly=True,
                secure=request.is_secure,
                samesite='Lax'
            )
        
        # Extract referrer code from URL parameters
        ref_code = request.args.get('ref') or request.args.get('ref_code')
        
        # Create visitor log entry
        visitor_log = VisitorLog(
            session_id=session_id,
            ip_address=request.remote_addr,
            path=request.path,
            method=request.method,
            referrer=request.referrer,
            ref_code=ref_code,
            user_agent=request.headers.get('User-Agent', ''),
            user_id=getattr(g, 'user_id', None),
            timestamp=datetime.utcnow(),
            **kwargs
        )
        
        # Add to database
        db.session.add(visitor_log)
        db.session.commit()
        
        # Store session info in Flask g for potential use elsewhere
        g.session_id = session_id
        g.is_new_session = is_new_session
        
        return visitor_log
        
    except Exception as e:
        current_app.logger.error(f"Error logging visit with session: {e}")
        db.session.rollback()
        return None


def get_user_session_info():
    """
    Get current user's session information.
    Returns dict with session_id, is_new_session, and session_age.
    """
    session_id = request.cookies.get('tamermap_session_id')
    
    if not session_id:
        return {
            'session_id': None,
            'is_new_session': True,
            'session_age': None
        }
    
    # Calculate session age (approximate, based on cookie creation)
    # Note: This is approximate since we don't store cookie creation time
    session_age = None
    
    return {
        'session_id': session_id,
        'is_new_session': False,
        'session_age': session_age
    }


def get_session_visits(session_id, days=30):
    """
    Get all visits for a specific session.
    
    Args:
        session_id: The session ID to look up
        days: Number of days to look back
    
    Returns:
        List of VisitorLog objects
    """
    since = datetime.utcnow() - timedelta(days=days)
    
    return VisitorLog.query.filter(
        VisitorLog.session_id == session_id,
        VisitorLog.timestamp >= since
    ).order_by(VisitorLog.timestamp).all()


def get_user_journey(session_id, include_subsequent_sessions=True):
    """
    Get complete user journey for a session.
    
    Args:
        session_id: The session ID to analyze
        include_subsequent_sessions: Whether to include later sessions from same IP
    
    Returns:
        Dict with journey information
    """
    # Get the initial session
    initial_visits = get_session_visits(session_id)
    
    if not initial_visits:
        return {
            'session_id': session_id,
            'visits': [],
            'total_visits': 0,
            'duration': 0,
            'pages_visited': [],
            'subsequent_sessions': []
        }
    
    # Calculate session duration
    if len(initial_visits) > 1:
        duration = (initial_visits[-1].timestamp - initial_visits[0].timestamp).total_seconds() / 60
    else:
        duration = 0
    
    # Get pages visited
    pages_visited = [visit.path for visit in initial_visits]
    
    # Get subsequent sessions if requested
    subsequent_sessions = []
    if include_subsequent_sessions:
        first_visit = initial_visits[0]
        later_visits = VisitorLog.query.filter(
            VisitorLog.ip_address == first_visit.ip_address,
            VisitorLog.timestamp > first_visit.timestamp + timedelta(hours=1),
            VisitorLog.session_id != session_id,
            VisitorLog.session_id.isnot(None)
        ).order_by(VisitorLog.timestamp).all()
        
        # Group by session
        session_groups = {}
        for visit in later_visits:
            if visit.session_id not in session_groups:
                session_groups[visit.session_id] = []
            session_groups[visit.session_id].append(visit)
        
        subsequent_sessions = [
            {
                'session_id': sid,
                'visits': visits,
                'first_visit': visits[0].timestamp,
                'last_visit': visits[-1].timestamp,
                'pages_visited': [v.path for v in visits]
            }
            for sid, visits in session_groups.items()
        ]
    
    return {
        'session_id': session_id,
        'visits': initial_visits,
        'total_visits': len(initial_visits),
        'duration': round(duration, 1),
        'pages_visited': pages_visited,
        'subsequent_sessions': subsequent_sessions
    }


def cleanup_old_sessions(days=90):
    """
    Clean up session IDs from old visitor log entries.
    This helps maintain database performance.
    
    Args:
        days: Remove session IDs from entries older than this many days
    """
    try:
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        # Update old records to remove session_id
        updated = db.session.query(VisitorLog).filter(
            VisitorLog.timestamp < cutoff_date,
            VisitorLog.session_id.isnot(None)
        ).update({VisitorLog.session_id: None})
        
        db.session.commit()
        
        current_app.logger.info(f"Cleaned up session IDs from {updated} old visitor log entries")
        return updated
        
    except Exception as e:
        current_app.logger.error(f"Error cleaning up old sessions: {e}")
        db.session.rollback()
        return 0 