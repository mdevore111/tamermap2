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
from .extensions import db, mail, security, session, cache, limiter
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

    # Debug: Print template folder and list of templates
    app.logger.debug('TEMPLATE FOLDER: %s', app.template_folder)
    # print('TEMPLATE DEBUG:', app.jinja_loader.list_templates())

    # Add a test route to render admin/master.html directly
    @app.route('/debug-template')
    def debug_template():
        return app.jinja_env.get_template('admin/master.html').render()

    # Load configuration.
    app.config.from_object(config_class)

    # Initialize Flask-Session (using Redis as configured in BaseConfig).
    session.init_app(app)

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
        
        if current_user.is_authenticated:
            is_admin = current_user.has_role('Admin')
            is_pro = current_user.has_role('Pro')
            
            context.update({
                'is_admin': is_admin,
                'is_pro': is_pro
            })
        else:
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

        # Debug: Print current user ID and roles to the terminal
        if hasattr(current_user, 'is_authenticated'):
            if current_user.is_authenticated:
                user_id = getattr(current_user, 'id', None)
                roles = [role.name for role in getattr(current_user, 'roles', [])]
                # app.logger.debug("User ID: %s, Roles: %s - Request: %s", user_id, roles, request.endpoint)
                pass
            else:
                # app.logger.debug("User not authenticated - Request: %s", request.endpoint)
                # Check if there's a remember me cookie
                remember_cookie = request.cookies.get('remember_token')
                if remember_cookie:
                    # app.logger.debug("Remember me cookie present but user not authenticated - Request: %s", request.endpoint)
                    pass
                pass
        else:
            # app.logger.debug("User object not properly initialized - Request: %s", request.endpoint)
            pass

        # Handle password reset
        if request.endpoint == 'security.forgot_password':
            def send_reset_password_instructions(user):
                token = user.get_reset_password_token()
                reset_link = url_for('security.reset_password', token=token, _external=True)
                return send_email_with_context(
                    subject="TAMERMAP.COM Password Reset Instructions",
                    template="security/email/reset_instructions",
                    recipient=user.email,
                    user=user,
                    reset_link=reset_link,
                    config=app.config
                )
            # Suppress linter error: send_reset_password_instructions is a custom attribute
            security.send_reset_password_instructions = send_reset_password_instructions
            return

        # Track visitor activity
        if request.endpoint and not request.endpoint.startswith('static'):
            excluded_prefixes = ['/api', '/admin', '/webhooks', '/static', '/track', '/reset', '/logout', '/login']
            if any(request.path.startswith(prefix) for prefix in excluded_prefixes):
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
        return f"Authenticated: {current_user.is_authenticated}, ID: {getattr(current_user, 'id', None)}, Roles: {[r.name for r in getattr(current_user, 'roles', [])]}"



    # Initialize Flask-Login
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'security.login'

    @login_manager.user_loader
    def load_user(user_id):
        try:
            return User.query.get(int(user_id))
        except (ValueError, TypeError):
            return User.query.filter_by(fs_uniquifier=user_id).first()

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

if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)
