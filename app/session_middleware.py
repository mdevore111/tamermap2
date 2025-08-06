"""
Session tracking middleware for visitor analytics
"""

import uuid
from flask import request, g, session
from app.models import VisitorLog
from app.extensions import db

def generate_session_id():
    """Generate a unique session ID"""
    return str(uuid.uuid4())

def get_or_create_session_id():
    """
    Get the current session ID from the session, or create a new one.
    This ensures every visitor gets a unique identifier that persists across visits.
    Returns a tuple (session_id, is_new_session) for compatibility with existing code.
    """
    is_new_session = False
    if 'visitor_session_id' not in session:
        session['visitor_session_id'] = generate_session_id()
        is_new_session = True
    return session['visitor_session_id'], is_new_session

def log_visit_with_session():
    """
    Log the current visit with session tracking.
    This should be called on every request to track visitor journeys.
    """
    try:
        # Get or create session ID
        session_id = get_or_create_session_id()
        
        # Get user ID if logged in
        user_id = None
        if hasattr(g, 'user') and g.user and hasattr(g.user, 'id'):
            user_id = g.user.id
        
        # Create visit log entry
        visit_log = VisitorLog(
            timestamp=db.func.now(),
            ip_address=request.remote_addr,
            path=request.path,
            method=request.method,
            referrer=request.referrer,
            ref_code=request.args.get('ref'),
            user_agent=request.headers.get('User-Agent'),
            user_id=user_id,
            session_id=session_id
        )
        
        # Add to database
        db.session.add(visit_log)
        db.session.commit()
        
        return session_id
        
    except Exception as e:
        # Log error but don't break the application
        print(f"Error logging visit: {e}")
        db.session.rollback()
        return None

def link_session_to_user(session_id, user_id):
    """
    Link a session ID to a user account when they register or log in.
    This allows us to track anonymous visitors who later become registered users.
    """
    try:
        # Update all visit logs for this session to include the user_id
        VisitorLog.query.filter_by(session_id=session_id).update({
            'user_id': user_id
        })
        db.session.commit()
        
    except Exception as e:
        print(f"Error linking session to user: {e}")
        db.session.rollback() 