import os
from datetime import timedelta, datetime
import redis
from dotenv import load_dotenv
import platform

# Load environment variables from a .env file, if present.
import os
env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
load_dotenv(env_path)

# Load Stripe keys silently
stripe_pub_key = os.getenv("STRIPE_PUBLISHABLE_KEY")


class BaseConfig:
    """
    Base configuration for the Flask application.

    This class sets up various application settings including:
      - Payment processing via Stripe and email via Mailgun.
      - Security settings for Flask-Security (authentication, password recovery, etc.).
      - Database connection via SQLAlchemy using a SQLite file.
      - Session management using Redis (via Flask-Session).
      - Environment and debug settings.

    Values are read from environment variables where available.
    """

    # --------------------------
    # Site Information
    # --------------------------
    SITE_NAME = os.getenv("SITE_NAME", "TAMERMAP.COM")

    # --------------------------
    # Stripe Payment Settings
    # --------------------------
    STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
    STRIPE_PUBLISHABLE_KEY = os.getenv("STRIPE_PUBLISHABLE_KEY", "")
    STRIPE_ENDPOINT_SECRET = os.getenv("STRIPE_ENDPOINT_SECRET", "")
    
    # Stripe Price IDs (environment-specific)
    STRIPE_PRO_MONTHLY_PRICE_ID = os.getenv("STRIPE_PRO_MONTHLY_PRICE_ID", "")
    # Future subscription tiers can be added here:
    # STRIPE_PRO_YEARLY_PRICE_ID = os.getenv("STRIPE_PRO_YEARLY_PRICE_ID", "")
    # STRIPE_BASIC_MONTHLY_PRICE_ID = os.getenv("STRIPE_BASIC_MONTHLY_PRICE_ID", "")

    # --------------------------
    # Email Settings (Mailgun)
    # --------------------------
    MAILGUN_API_KEY = os.getenv("MAILGUN_API_KEY")
    MAILGUN_DOMAIN = os.getenv("MAILGUN_DOMAIN")
    MAILGUN_SENDER = os.getenv("MAILGUN_SENDER", "Tamermap <postmaster@mg.tamermap.com>")
    MAILGUN_FROM_NAME = os.getenv("MAILGUN_FROM_NAME", "Tamermap")
    MAILGUN_REPLY_TO = os.getenv("MAILGUN_REPLY_TO", "support@tamermap.com")
    MAILGUN_LIST_UNSUBSCRIBE = os.getenv("MAILGUN_LIST_UNSUBSCRIBE", "https://tamermap.com/unsubscribe")

    # Email tracking and validation
    MAILGUN_TRACK_OPENS = True
    MAILGUN_TRACK_CLICKS = True
    MAILGUN_DKIM_ENABLED = True
    MAILGUN_SPF_ENABLED = True
    MAILGUN_DMARC_ENABLED = True

    # Bounce handling
    MAILGUN_BOUNCE_WEBHOOK = os.getenv("MAILGUN_BOUNCE_WEBHOOK", "https://tamermap.com/webhooks/mailgun/bounce")
    MAILGUN_COMPLAINT_WEBHOOK = os.getenv("MAILGUN_COMPLAINT_WEBHOOK", "https://tamermap.com/webhooks/mailgun/complaint")
    MAILGUN_DELIVERY_WEBHOOK = os.getenv("MAILGUN_DELIVERY_WEBHOOK", "https://tamermap.com/webhooks/mailgun/delivery")
    MAILGUN_BOUNCE_THRESHOLD = 5
    MAILGUN_COMPLAINT_THRESHOLD = 1

    # Email validation
    MAILGUN_VALIDATE_EMAILS = True
    MAILGUN_VALIDATION_WEBHOOK = os.getenv("MAILGUN_VALIDATION_WEBHOOK", "https://tamermap.com/webhooks/mailgun/validation")

    # Email static resources - use Mailgun hosted images for better deliverability
    EMAIL_LOGO_URL = os.getenv("EMAIL_LOGO_URL", "https://mg.tamermap.com/static/images/logo.png")
    EMAIL_PREVIEW_URL = os.getenv("EMAIL_PREVIEW_URL", "https://mg.tamermap.com/static/images/preview.png")
    EMAIL_BASE_URL = os.getenv("EMAIL_BASE_URL", "https://tamermap.com")
    
    # Email templates
    SECURITY_EMAIL_TEMPLATE_REGISTER = 'security/email/register_user.html'
    SECURITY_EMAIL_TEMPLATE_CONFIRM = 'security/email/register_user.html'
    SECURITY_EMAIL_TEMPLATE_FORGOT_PASSWORD = 'security/email/forgot_password'
    SECURITY_EMAIL_TEMPLATE_RESET_PASSWORD = 'security/email/reset_instructions'
    SECURITY_EMAIL_TEMPLATE_PASSWORD_CHANGED = 'security/email/password_changed'

    # --------------------------
    # Security & General Credentials
    # --------------------------
    SECRET_KEY = os.getenv("SECRET_KEY", "")  # Used for session management and CSRF protection.
    SECURITY_PASSWORD_SALT = os.getenv("SECURITY_PASSWORD_SALT", "")
    GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
    SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY", "")

    # --------------------------
    # SQLAlchemy Configuration
    # --------------------------
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    basedir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(basedir, 'instance', 'tamermap_data.db')

    # --------------------------
    # Custom Usage Tracking Storage
    # --------------------------
    TRACK_USAGE_STORAGE_CLASS = "app.track_usage_storage.SQLAlchemyStorage"

    # --------------------------
    # Flask Environment Settings
    # --------------------------
    FLASK_ENV = os.getenv("FLASK_ENV", "development")
    DEBUG = os.getenv("DEBUG", "False").lower() == "true"

    # ─── Flask-Caching ───────────────────────────────
    # Use different cache types depending on the platform
    if platform.system() == "Windows":
        # Use simple memory cache on Windows to avoid Redis requirements
        CACHE_TYPE = "SimpleCache"
    else:
        # Use Redis on Linux/Ubuntu
        CACHE_TYPE = "redis"
        CACHE_REDIS_URL = "redis://localhost:6379/1"   # use DB 1, sessions can stay on DB 0
        CACHE_KEY_PREFIX = "tamermap:"                 # optional but recommended
    
    # Common cache settings
    CACHE_DEFAULT_TIMEOUT = 300                    # 5 min fall-back

    # Server compression algo
    COMPRESS_ALGORITHM = 'gzip'

    # --------------------------
    # Flask-Security Configuration
    # --------------------------
    SECURITY_POST_LOGIN_VIEW = "/maps"
    SECURITY_POST_RESET_VIEW = "/maps"
    SECURITY_POST_FORGOT_PASSWORD_VIEW = "/splash"
    SECURITY_REGISTERABLE = False  # Registration controlled by Stripe payment system webhooks.
    SECURITY_RECOVERABLE = True
    SECURITY_CHANGEABLE = True
    SECURITY_CONFIRMABLE = False
    SECURITY_REMEMBER_ME = True
    SECURITY_REMEMBER_COOKIE_DURATION = timedelta(days=14)
    SECURITY_SEND_REGISTER_EMAIL = True

    # Add datetime to template context
    SECURITY_EMAIL_TEMPLATE_CONTEXT = {
        'datetime': datetime
    }

    # Preferred URL scheme and protocol.
    PREFERRED_URL_SCHEME = "http"
    SECURITY_DEFAULT_HTTP_PROTOCOL = "http"

    # Email templates.
    SECURITY_EMAIL_HTML = True

    # --------------------------
    # Session & Cookie Settings
    # --------------------------
    SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "True").lower() == "true"
    SESSION_COOKIE_SAMESITE = 'Lax'
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_NAME = 'tamermap_session'  # Custom session cookie name
    SESSION_REFRESH_EACH_REQUEST = True  # Refresh session on each request
    SESSION_COOKIE_DOMAIN = None  # Allow cross-subdomain cookies if needed

    # --------------------------
    # Flask-Session Configuration (Using Redis)
    # --------------------------
    # Use filesystem sessions if running on Windows (for development) to avoid Redis errors.
    if platform.system() == "Windows":
        SESSION_TYPE = 'filesystem'
        # Optionally, set a directory where session files are stored.
        SESSION_FILE_DIR = os.path.join(os.path.abspath(os.path.dirname(__file__)), "flask_session_files")
    else:
        # On Linux/Ubuntu, use Redis (adjust as needed for your production/staging settings)
        SESSION_TYPE = 'redis'
        SESSION_REDIS = redis.Redis(host='localhost', port=6379, db=0)

    SESSION_USE_SIGNER = True  # Sign the session cookie to protect against tampering.
    PERMANENT_SESSION_LIFETIME = timedelta(days=14)

    # --------------------------
    # Admin Email for Notifications
    # --------------------------
    ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "mark@markdevore.com")
