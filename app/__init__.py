"""
Application Factory Module

This module creates and configures the Flask application instance using
the factory pattern. It loads configuration from BaseConfig, initializes
extensions (SQLAlchemy, Flask-Security, Flask-Admin, etc.), registers
blueprints, and sets up the SQLAlchemyUserDatastore for authentication.

Usage:
    from app import create_app
    app = create_app()
"""

import logging
import os
from datetime import datetime
from logging.handlers import TimedRotatingFileHandler
import re
from functools import wraps
from flask import redirect
from flask_login import login_required

import requests
from flask import Flask, request, url_for, session, current_app, g
from flask_login import current_user, LoginManager, user_logged_in
from flask_security import utils as security_utils, Security
from flask_security.datastore import SQLAlchemyUserDatastore
from flask_compress import Compress
from flask_migrate import Migrate
from flask_mail import Mail

# Import extensions and modules
from app.auth.forms import ExtendedRegisterForm, ExtendedConfirmRegisterForm
from . import signals
from .config import BaseConfig
from .custom_email import custom_send_mail, send_email_with_context
from .models import User, Role, VisitorLog
from .extensions import db, mail, session as flask_session, cache, limiter
from .payment.route import payment_bp
from .payment.stripe_webhooks import stripe_webhooks_bp
from .routes.api import api_bp
from .routes.auth import auth_bp
from .routes.map import map_bp
from .routes.public import public_bp
from .routes.dev import dev_bp
from app.payment.mailgun_webhooks import mailgun_webhooks
from .admin_routes import admin_bp

# Global variable for the SQLAlchemyUserDatastore.
user_datastore = None

print("I'm running")

# Initialize Flask-Migrate
migrate = Migrate()

class DummyMail:
    """
    Dummy Mail Extension

    This dummy mail extension satisfies Flask-Security's requirement for an email
    extension by delegating email sending to the custom_send_mail function.
    """

    def __init__(self, default_sender):
        self.default_sender = default_sender

    @staticmethod
    def send(msg):
        # Delegate email sending to the custom email function.
        return custom_send_mail(msg)

def create_app(config_class=BaseConfig):
    """
    Application factory function.

    Creates and configures the Flask application instance.

    Steps:
      - Creates a Flask app with custom template and static folder paths.
      - Loads configuration from the given config class.
      - Initializes Flask-Session (using Redis as the session store).
      - Sets up SQLAlchemy, Flask-Security, and Flask-Admin.
      - Registers blueprints for different parts of the application.
      - Configures logging with timed rotation.
      - Sets up a before-request function to track visitor activity.

    Args:
        config_class: Configuration class to load (default is BaseConfig).

    Returns:
        A configured Flask application instance.
    """
    global user_datastore

    # Determine paths for templates and static files.
    template_dir = os.path.join(os.path.dirname(__file__), "..", "templates")
    static_dir = os.path.join(os.path.dirname(__file__), "..", "static")

    # Create the Flask application instance.
    app = Flask(__name__, instance_relative_config=True,
                template_folder=template_dir, static_folder=static_dir)

    # ProxyFix for nginx HTTPS detection (dev/prod environments)
    from werkzeug.middleware.proxy_fix import ProxyFix
    app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

    # Debug: Print template folder and list of templates
    app.logger.debug('TEMPLATE FOLDER: %s', app.template_folder)
    # print('TEMPLATE DEBUG:', app.jinja_loader.list_templates())

    # Debug headers for HTTPS detection
    @app.before_request
    def debug_headers():
        # Only log headers for non-static requests to reduce noise
        if not request.endpoint or not request.endpoint.startswith('static'):
            app.logger.info(f"=== HEADER DEBUG ===")
            app.logger.info(f"X-Forwarded-Proto: {request.headers.get('X-Forwarded-Proto')}")
            app.logger.info(f"X-Forwarded-Host: {request.headers.get('X-Forwarded-Host')}")
            app.logger.info(f"request.is_secure: {request.is_secure}")
            app.logger.info(f"request.scheme: {request.scheme}")
            app.logger.info(f"request.url: {request.url}")
            app.logger.info(f"==================")

    # Add a test route to render admin/master.html directly
    @app.route('/debug-template')
    def debug_template():
        return app.jinja_env.get_template('admin/master.html').render()

    # Load configuration.
    app.config.from_object(config_class)

    # REMOVED: Flask-Session initialization moved to after Flask-Login setup
    # This ensures proper initialization order for session management

    # Initialize caching
    cache.init_app(app)

    # Set up logging with timed rotation (rotates at midnight, keeps 7 backups).
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    logs_dir = os.path.join(base_dir, "logs")
    if not os.path.exists(logs_dir):
        os.makedirs(logs_dir)
    
    # Use a different log file for development
    if app.debug:
        log_file = os.path.join(logs_dir, "debug_dev.log")
        debug_handler = logging.FileHandler(log_file)
    else:
        log_file = os.path.join(logs_dir, "debug.log")
        debug_handler = TimedRotatingFileHandler(log_file, when="midnight", backupCount=7)
    
    debug_handler.setLevel(logging.DEBUG)
    debug_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s - %(exc_info)s')
    debug_handler.setFormatter(debug_formatter)
    app.logger.addHandler(debug_handler)
    app.logger.setLevel(logging.DEBUG)

    # Initialize SQLAlchemy.
    db.init_app(app)

    # Initialize Flask-Migrate
    migrate.init_app(app, db)

    # Ensure required tables exist in development without running an external migration
    # Covers engagement/popularity tables like `legend_clicks`, `pin_interactions`, etc.
    try:
        with app.app_context():
            db.create_all()
    except Exception as e:
        app.logger.error(f"db.create_all() failed: {e}")

    # Initialize Flask-Limiter
    limiter.init_app(app)

    # Set up the user datastore (for Flask-Security).
    user_datastore = SQLAlchemyUserDatastore(db, User, Role)

    # Suppress linter error: user_datastore is a custom attribute
    app.user_datastore = user_datastore

    # Initialize Flask-Security with extended registration and confirmation forms.
    security = Security(app, user_datastore)
    
    # Debug the user datastore to see what methods are available
    app.logger.info(f"USER DATASTORE DEBUG:")
    app.logger.info(f"   User model methods: {[m for m in dir(user_datastore.user_model) if not m.startswith('_')]}")
    app.logger.info(f"   Has verify_password: {hasattr(user_datastore.user_model, 'verify_password')}")
    app.logger.info(f"   Has get_id: {hasattr(user_datastore.user_model, 'get_id')}")
    app.logger.info(f"   Has is_active: {hasattr(user_datastore.user_model, 'is_active')}")
    app.logger.info(f"   Has is_authenticated: {hasattr(user_datastore.user_model, 'is_authenticated')}")
    app.logger.info(f"   Has is_anonymous: {hasattr(user_datastore.user_model, 'is_anonymous')}")
    
    # Debug Flask-Security configuration
    app.logger.info(f"FLASK-SECURITY CONFIGURATION:")
    app.logger.info(f"   Login URL: {app.config.get('SECURITY_LOGIN_URL', 'Not set')}")
    app.logger.info(f"   Post Login View: {app.config.get('SECURITY_POST_LOGIN_VIEW', 'Not set')}")
    app.logger.info(f"   Post Reset View: {app.config.get('SECURITY_POST_RESET_VIEW', 'Not set')}")
    app.logger.info(f"   User Datastore: {type(user_datastore).__name__}")
    app.logger.info(f"   User Model: {user_datastore.user_model.__name__}")
    app.logger.info(f"   Role Model: {user_datastore.role_model.__name__}")
    
    # Ensure Flask-Security uses the same user loader as Flask-Login
    # This should resolve the session mismatch by ensuring both systems see the same user state
    # Note: user_loader is set later in the file after the function is defined
    
    # Simple integration: Ensure Flask-Security recognizes Flask-Login's authentication
    # by setting the user loader and letting Flask-Security handle its own auth
    # Note: user_loader is set later in the file
    
    # Remove custom authentication decorator that was causing redirect issues
    # Let Flask-Security use its default authentication mechanism

    # Register a dummy mail extension for Flask-Security's email support.
    app.extensions = getattr(app, "extensions", {})
    app.extensions["mail"] = DummyMail(app.config.get("DEFAULT_EMAIL_SENDER", "no-reply@tamermap.com"))
    # Override Flask-Security's send_mail function.
    security_utils.send_mail = custom_send_mail

    # Initialize Flask-Compress
    compress = Compress()
    compress.init_app(app)

    # Register blueprints for various application modules.
    app.register_blueprint(public_bp)  # Public pages.
    app.register_blueprint(map_bp)  # Map functionality.
    app.register_blueprint(auth_bp, url_prefix="/auth")  # Authentication pages.
    app.register_blueprint(api_bp, url_prefix="/api")  # API endpoints.
    app.register_blueprint(payment_bp, url_prefix="/payment")  # Payment-related endpoints.
    app.register_blueprint(stripe_webhooks_bp, url_prefix='/webhooks')  # Stripe webhooks.
    app.register_blueprint(mailgun_webhooks)
    app.register_blueprint(admin_bp, url_prefix='/admin')
    
    # Register development routes only in development environment
    if app.config.get('ENV') == 'development':
        app.register_blueprint(dev_bp, url_prefix="/dev")

    # Register signal handlers for application events (like registration).
    signals.register_signals(app, user_datastore, db)

    # Add context processors for templates
    @app.context_processor
    def inject_template_variables():
        """Inject variables into template context."""
        context = {
            'datetime': datetime,
            'flask_env': app.config.get('FLASK_ENV', 'development'),
            'debug_mode': app.config.get('DEBUG', False)
        }
        
        # DEBUG: Log template context authentication state
        if current_user.is_authenticated:
            is_admin = current_user.has_role('Admin')
            is_pro = current_user.has_role('Pro')
            
            app.logger.info(f"Template Context: User {current_user.id} authenticated - Admin: {is_admin}, Pro: {is_pro}")
            
            context.update({
                'is_admin': is_admin,
                'is_pro': is_pro
            })
        else:
            app.logger.info(f"Template Context: User not authenticated")
            context.update({
                'is_admin': False,
                'is_pro': False
            })
        
        return context

    # Block malicious requests before processing
    @app.before_request
    def block_malicious_requests():
        # Block PHP injection attempts
        malicious_patterns = [
            'phpinfo', 'php://', 'data://', '{${', 'php:', 
            'phpinfo()', 'phpinfo();', 'phpinfo().'
        ]
        
        if any(pattern in request.path.lower() for pattern in malicious_patterns):
            app.logger.warning(f"Blocked malicious request: {request.path} from {request.remote_addr}")
            return '', 444
        
        # Block path traversal attempts
        traversal_patterns = [
            '/etc/passwd', '../', '..%', 'etc/passwd', 'etc/', 'passwd'
        ]
        
        if any(pattern in request.path for pattern in traversal_patterns):
            app.logger.warning(f"Blocked path traversal: {request.path} from {request.remote_addr}")
            return '', 444
        
        # Block suspicious user agents
        suspicious_agents = [
            'bot', 'crawler', 'spider', 'scanner', 'sqlmap', 'nikto', 'nmap'
        ]
        
        user_agent = request.headers.get('User-Agent', '').lower()
        if any(agent in user_agent for agent in suspicious_agents):
            app.logger.warning(f"Blocked suspicious user agent: {user_agent} from {request.remote_addr}")
            return '', 444

    # Track visitor activity and handle password reset before each request.
    @app.before_request
    def before_request():
        # Skip authentication check for static files
        if request.endpoint and request.endpoint.startswith('static'):
            return

        # DEBUG: Essential session/authentication debugging
        if not request.endpoint or not request.endpoint.startswith('static'):
            app.logger.info(f"=== AUTH DEBUG: {request.path} ===")
            app.logger.info(f"Endpoint: {request.endpoint}")
            try:
                session_keys = list(session.keys()) if hasattr(session, 'keys') else []
                app.logger.info(f"Session keys: {session_keys}")
            except Exception as e:
                app.logger.info(f"Session access error: {e}")
        
        try:
            # Try to get session keys safely
            session_keys = list(session.keys()) if hasattr(session, 'keys') else []
            app.logger.info(f"Session keys: {session_keys}")
            # Try to access specific session values (only if we have keys)
            if session_keys:
                for key in session_keys[:5]:  # Limit to first 5 keys to avoid overwhelming logs
                    try:
                        value = session.get(key, 'Error accessing value')
                        app.logger.info(f"Session[{key}]: {value}")
                    except Exception as e:
                        app.logger.info(f"Session[{key}] access error: {e}")
        except Exception as e:
            app.logger.info(f"Session contents access error: {e}")
        
        # Debug: Essential authentication state logging
        if hasattr(current_user, 'is_authenticated') and current_user.is_authenticated:
            user_id = getattr(current_user, 'id', None)
            roles = [role.name for role in getattr(current_user, 'roles', [])]
            app.logger.info(f"Flask-Login: User {user_id} authenticated with roles: {roles}")
        elif hasattr(current_user, 'is_authenticated'):
            app.logger.info(f"Flask-Login: User NOT authenticated")
        else:
            app.logger.info(f"Flask-Login: User object not properly initialized")



        # DEBUG: Track Flask-Security route access
        if request.endpoint and request.endpoint.startswith('security.'):
            app.logger.info(f"=== FLASK-SECURITY ROUTE ACCESS: {request.endpoint} ===")
            app.logger.info(f"Path: {request.path}")
            app.logger.info(f"Flask-Login current_user: {current_user}")
            app.logger.info(f"Flask-Login is_authenticated: {getattr(current_user, 'is_authenticated', 'N/A')}")
            app.logger.info(f"Flask-Login user ID: {getattr(current_user, 'id', 'N/A')}")
            
            # Add login form debugging
            if request.endpoint == 'security.login' and request.method == 'POST':
                app.logger.info(f"LOGIN ATTEMPT DEBUG:")
                app.logger.info(f"   Form data: {dict(request.form)}")
                app.logger.info(f"   Email: {request.form.get('email', 'No email')}")
                app.logger.info(f"   Password length: {len(request.form.get('password', ''))}")
                app.logger.info(f"   Remember me: {request.form.get('remember', 'No')}")
            
            try:
                session_keys = list(session.keys()) if hasattr(session, 'keys') else []
                app.logger.info(f"Session keys: {session_keys}")
                # Show key session values for debugging
                if '_user_id' in session_keys:
                    app.logger.info(f"Session _user_id: {session.get('_user_id')}")
                if 'fs_cc' in session_keys:
                    app.logger.info(f"Session fs_cc: {session.get('fs_cc')}")
            except Exception as e:
                app.logger.info(f"Session keys access error: {e}")
            app.logger.info(f"Request cookies: {dict(request.cookies)}")

        # Track visitor activity
        if request.endpoint and not request.endpoint.startswith('static'):
            excluded_prefixes = ['/api', '/admin', '/webhooks', '/static', '/track', '/reset', '/logout', '/login']
            if any(request.path.startswith(prefix) for prefix in excluded_prefixes):
                app.logger.info(f"Request excluded from tracking (prefix: {request.path})")
                return

            ip = request.headers.get('X-Forwarded-For', request.remote_addr)
            ip = ip.split(',')[0].strip() if ip else request.remote_addr

            user_id = current_user.id if current_user.is_authenticated else None
            ref_code = request.args.get("ref")

            # Initialize geographic variables.
            country = region = city = None
            latitude = longitude = None

            # Check if IP is internal
            is_internal_ip = False
            if ip:
                # Server IPs
                if ip in ["137.184.244.37", "144.126.210.185", "50.106.23.189", "10.48.0.2", "24.199.116.220"]:
                    is_internal_ip = True
                # DigitalOcean IPs
                elif re.match(r"^(144\.126\.\d+\.\d+|143\.198\.\d+\.\d+|134\.209\.\d+\.\d+)$", ip):
                    is_internal_ip = True
                # Private IP ranges (RFC 1918) - all non-routable addresses
                elif (ip.startswith("10.") or  # 10.0.0.0/8
                      ip.startswith("192.168.") or  # 192.168.0.0/16
                      ip.startswith("127.") or  # 127.0.0.0/8 (localhost)
                      re.match(r"^172\.(1[6-9]|2[0-9]|3[0-1])\.", ip) or  # 172.16.0.0/12
                      ip == "localhost"):
                    is_internal_ip = True

            # Check if referrer is internal
            referrer = request.referrer
            is_internal_referrer = False
            
            # Mark requests from internal IPs as internal referrers (even without referrer)
            if is_internal_ip:
                is_internal_referrer = True
            elif referrer:
                # Domain patterns for internal sites (tamermap.com and sister sites)
                internal_domain_patterns = [
                    re.compile(r"^(https?://(?:.+\.)?tamermap\.com)", re.IGNORECASE),
                    re.compile(r"^(https?://(?:.+\.)?bareista\.com)", re.IGNORECASE)
                ]
                
                # Local development URLs - more comprehensive pattern
                localhost_pattern = re.compile(r"^https?://(?:127\.0\.0\.1|localhost|0\.0\.0\.0)(?::\d+)?", re.IGNORECASE)
                
                # Server IP patterns - specific IPs and ranges
                server_ip_patterns = [
                    re.compile(r"^https?://137\.184\.244\.37(?::\d+)?", re.IGNORECASE),
                    re.compile(r"^https?://144\.126\.210\.185(?::\d+)?", re.IGNORECASE),  # Specific server IP
                    re.compile(r"^https?://144\.126\.\d+\.\d+(?::\d+)?", re.IGNORECASE),  # DigitalOcean range
                    re.compile(r"^https?://143\.198\.\d+\.\d+(?::\d+)?", re.IGNORECASE),  # DigitalOcean range
                    re.compile(r"^https?://134\.209\.\d+\.\d+(?::\d+)?", re.IGNORECASE),  # DigitalOcean range
                    re.compile(r"^https?://50\.106\.23\.189(?::\d+)?", re.IGNORECASE),    # Another server IP
                    re.compile(r"^https?://24\.199\.116\.220(?::\d+)?", re.IGNORECASE),   # Additional server IP
                    # Private IP ranges (RFC 1918) - all non-routable addresses
                    re.compile(r"^https?://10\.\d+\.\d+\.\d+(?::\d+)?", re.IGNORECASE),   # 10.0.0.0/8
                    re.compile(r"^https?://192\.168\.\d+\.\d+(?::\d+)?", re.IGNORECASE),  # 192.168.0.0/16
                    re.compile(r"^https?://172\.(1[6-9]|2[0-9]|3[0-1])\.\d+\.\d+(?::\d+)?", re.IGNORECASE)  # 172.16.0.0/12
                ]
                
                # Check if referrer matches any allowed patterns
                if (any(pattern.match(referrer) for pattern in internal_domain_patterns) or
                    localhost_pattern.match(referrer) or
                    any(pattern.match(referrer) for pattern in server_ip_patterns)):
                    is_internal_referrer = True

            # Skip tracking for monitor traffic
            if request.user_agent and "Tamermap-Monitor" in request.user_agent.string:
                return
            
            # Skip tracking for admin users
            if current_user.is_authenticated and any(r.name == "Admin" for r in getattr(current_user, "roles", [])):
                return

            # Track all visitors (both internal and external) but mark them appropriately
            try:
                # Get IP geolocation data for external IPs only
                if not is_internal_ip:
                    response = requests.get(f"http://ip-api.com/json/{ip}")
                    if response.status_code == 200:
                        data = response.json()
                        if data.get("status") == "success":
                            country = data.get("country")
                            region = data.get("regionName")
                            city = data.get("city")
                            latitude = data.get("lat")
                            longitude = data.get("lon")

                # Get or create session ID for improved tracking
                from app.session_middleware import get_or_create_session_id
                session_id, is_new_session = get_or_create_session_id()

                # Store session info in Flask g for cookie setting
                g.session_id = session_id
                g.is_new_session = is_new_session

                # Create visitor log entry with proper internal flags and session tracking
                log = VisitorLog(**{
                    'session_id': session_id,  # New session tracking field
                    'ip_address': ip,
                    'user_id': user_id,
                    'ref_code': ref_code,
                    'country': country,
                    'region': region,
                    'city': city,
                    'latitude': latitude,
                    'longitude': longitude,
                    'path': request.path,
                    'method': request.method,
                    'user_agent': request.user_agent.string,
                    'referrer': referrer,
                    'is_internal_referrer': is_internal_referrer
                })
                db.session.add(log)
                db.session.commit()

            except Exception as e:
                app.logger.error(f"Error tracking visitor: {str(e)}")
                db.session.rollback()

    # Add a debug route to check current user authentication and roles
    @app.route('/whoami')
    def whoami():
        from flask_login import current_user
        from flask import session
        
        try:
            session_keys = list(session.keys()) if hasattr(session, 'keys') else []
            session_info = f"Keys: {session_keys}"
        except Exception as e:
            session_info = f"Error accessing session: {e}"
            
        return f"Authenticated: {current_user.is_authenticated}, ID: {getattr(current_user, 'id', None)}, Roles: {[r.name for r in getattr(current_user, 'roles', [])]}, Session: {session_info}"

    # Add a debug route specifically for session debugging
    @app.route('/debug-session')
    def debug_session():
        from flask_login import current_user
        from flask import session, request
        
        try:
            session_keys = list(session.keys()) if hasattr(session, 'keys') else []
            session_id = session.get('_id', 'No Flask session ID') if session_keys else 'No session keys'
            session_info = f"Keys: {session_keys}"
        except Exception as e:
            session_id = f"Error accessing session: {e}"
            session_info = f"Error accessing session: {e}"
        
        debug_info = {
            'path': request.path,
            'endpoint': request.endpoint,
            'flask_login_authenticated': current_user.is_authenticated,
            'flask_login_user_id': getattr(current_user, 'id', None),
            'flask_login_user_email': getattr(current_user, 'email', None),
            'flask_session_id': session_id,
            'flask_session_info': session_info,
            'cookies': dict(request.cookies),
            'user_agent': request.headers.get('User-Agent', 'No User-Agent')
        }
        
        return debug_info
    
    # Custom change password route that bypasses Flask-Security
    @app.route('/change-password', methods=['GET', 'POST'])
    @login_required
    def custom_change_password():
        """Custom change password route that bypasses Flask-Security's redirect issues."""
        from flask import render_template, request, flash, redirect, url_for
        from app.auth.forms import ChangePasswordForm
        
        form = ChangePasswordForm()
        if form.validate_on_submit():
            # Use Flask-Security's password verification
            if security_utils.verify_and_update_password(form.current_password.data, current_user):
                # Use Flask-Security's password hashing
                current_user.password = security_utils.hash_password(form.new_password.data)
                db.session.commit()
                flash('Your password has been updated successfully!', 'success')
                return redirect(url_for('auth.account'))
            else:
                flash('Current password is incorrect.', 'error')
        
        return render_template('security/change_password.html', change_password_form=form)



    # Custom reset password route that bypasses Flask-Security's broken redirects
    @app.route('/reset-password/<token>', methods=['GET', 'POST'])
    def custom_reset_password(token):
        """Custom reset password route that bypasses Flask-Security's redirect issues."""
        from flask import render_template, request, flash, redirect, url_for
        from app.auth.forms import ResetPasswordForm
        from app.models import User
        from app.extensions import db
        from flask_security import utils as security_utils
        from itsdangerous import URLSafeTimedSerializer
        
        try:
            # Verify the token
            serializer = URLSafeTimedSerializer(app.config['SECRET_KEY'])
            email = serializer.loads(token, salt='password-reset-salt', max_age=3600)  # 1 hour expiry
            
            # Find the user
            user = User.query.filter_by(email=email).first()
            if not user:
                flash('Invalid or expired reset link.', 'error')
                return redirect(url_for('security.login'))
            
            form = ResetPasswordForm()
            if form.validate_on_submit():
                # Update the user's password
                user.password = security_utils.hash_password(form.password.data)
                db.session.commit()
                flash('Your password has been reset successfully!', 'success')
                return redirect(url_for('security.login'))
            
            return render_template('security/reset_password.html', reset_password_form=form)
            
        except Exception as e:
            flash('Invalid or expired reset link.', 'error')
            return redirect(url_for('security.login'))

    # Initialize Flask-Login
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'security.login'

    @login_manager.user_loader
    def load_user(user_id):
        try:
            user = User.query.get(int(user_id))
            if user:
                app.logger.info(f"Flask-Login: Loaded user {user.email} (ID: {user.id})")
            else:
                app.logger.info(f"Flask-Login: No user found with ID: {user_id}")
            return user
        except (ValueError, TypeError):
            user = User.query.filter_by(fs_uniquifier=user_id).first()
            if user:
                app.logger.info(f"Flask-Login: Found user by fs_uniquifier: {user.email} (ID: {user.id})")
            else:
                app.logger.info(f"Flask-Login: No user found with fs_uniquifier: {user_id}")
            return user
    
    # REMOVED: This was causing conflicts between Flask-Login and Flask-Security
    # security.user_loader = load_user

    # Initialize Flask-Session AFTER configuration is loaded
    # This ensures all session settings are properly applied
    flask_session.init_app(app)
    
    # REMOVED: Double initialization that was corrupting sessions
    # with app.app_context():
    #     session.init_app(app)

    @app.after_request
    def after_request(response):
        # Set session cookie if this is a new session
        if hasattr(g, 'is_new_session') and g.is_new_session and hasattr(g, 'session_id'):
            response.set_cookie(
                'tamermap_session_id', 
                g.session_id, 
                max_age=30 * 24 * 3600,  # 30 days
                httponly=True,
                secure=request.is_secure,
                samesite='Lax'
            )
        return response

    return app
