# app/signals.py
from datetime import datetime

from flask import request, session
from flask_login import user_logged_in
from flask_security.signals import user_registered, user_authenticated

from .models import LoginEvent
from .utils import trial_period
from .session_middleware import link_session_to_user


def register_signals(app, user_datastore, db):
    """
    Register signal handlers for user events.

    This function sets up handlers for the 'user_registered' and 'user_logged_in'
    signals. The 'user_registered' handler assigns a default role to new users,
    sets up their trial period dates, and commits these changes to the database.
    The 'user_logged_in' handler updates the user's last login timestamp upon each login
    and records a detailed LoginEvent.

    Args:
        app (Flask): The Flask application instance.
        user_datastore (SQLAlchemyUserDatastore): The datastore used by Flask-Security.
        db (SQLAlchemy): The SQLAlchemy database instance.
    """

    @user_logged_in.connect_via(app)
    def record_login(sender, user, **extra):
        """
        Update the last login timestamp for a user upon login and record the login event.

        This handler performs three actions:
          1. Updates the 'last_login' field on the user record to the current UTC time.
          2. Increments the 'login_count' field.
          3. Creates a new LoginEvent entry recording the login timestamp,
             the user's IP address, and the user agent.
          4. Links the current session ID to the user account for funnel tracking.

        Args:
            sender: The sender of the signal (usually the Flask app).
            user (User): The user who has just logged in.
            **extra: Additional keyword arguments passed by the signal.
        """
        # Get the current UTC time.
        current_time = datetime.utcnow()

        # Update the user's last login field and increment login count.
        user.last_login = current_time
        user.login_count += 1

        # Retrieve client information from the request.
        ip_address = request.remote_addr
        user_agent = request.headers.get('User-Agent')

        # Create a new LoginEvent record.
        event = LoginEvent(
            user_id=user.id,
            login_timestamp=current_time,
            ip_address=ip_address,
            user_agent=user_agent
        )

        # Link the current session ID to the user account for funnel tracking
        if 'visitor_session_id' in session:
            link_session_to_user(session['visitor_session_id'], user.id)

        db.session.add(user)
        db.session.add(event)
        db.session.commit()

    @user_logged_in.connect_via(app)
    def on_user_logged_in(sender, user, **extra):
        """
        Signal listener for when a user logs in.

        This function is triggered after a user successfully logs in. It checks the
        user's roles and sets boolean flags in the session for quick access
        to 'is_admin' and 'is_pro' status throughout the application.

        Args:
            sender: The application that sent the signal.
            user: The user object who has just logged in.
        """
        session['is_admin'] = user.has_role('Admin')
        session['is_pro'] = user.has_role('Pro')
    
    # Add Flask-Security debugging signals
    @user_authenticated.connect_via(app)
    def on_user_authenticated(sender, user, **extra):
        """Debug signal for when Flask-Security authenticates a user."""
        app.logger.info(f"FLASK-SECURITY: User authenticated: {user.email} (ID: {user.id})")
        app.logger.info(f"   Extra data: {extra}")
        
        # Also log the authentication method being used
        if 'authn_via' in extra:
            app.logger.info(f"   Authentication method: {extra['authn_via']}")
        if 'authn_mechanism' in extra:
            app.logger.info(f"   Auth mechanism: {extra['authn_mechanism']}")
    


    @user_registered.connect_via(app)
    def on_user_registered(sender, user, **extra):
        """
        Signal listener for when a user registers.

        This function is triggered after a user successfully registers. It links
        the current session ID to the user account for funnel tracking.

        Args:
            sender: The sender of the signal (usually the Flask app).
            user (User): The user who has just registered.
            **extra: Additional keyword arguments passed by the signal.
        """
        # Link the current session ID to the user account for funnel tracking
        if 'visitor_session_id' in session:
            link_session_to_user(session['visitor_session_id'], user.id)
