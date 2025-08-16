"""
Models for the application.

This module defines the SQLAlchemy models for the application including
Retailer, Machine, Role, User, and Message. It also sets up the association
table for the many-to-many relationship between users and roles.
"""

import uuid
import datetime as _datetime

from flask import current_app
from flask_security.core import UserMixin, RoleMixin
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature

from .extensions import db

# Association table for the many-to-many relationship between Users and Roles.
roles_users = db.Table(
    'roles_users',
    db.Column('user_id', db.Integer(), db.ForeignKey('user.id')),
    db.Column('role_id', db.Integer(), db.ForeignKey('role.id'))
)


class TrackUsageLog(db.Model):
    """
    Model for storing usage log records.

    This table holds data on requests including the endpoint accessed,
    the HTTP method, user agent details, IP address, and a timestamp.
    """
    __tablename__ = "track_usage_log"
    id = db.Column(db.Integer, primary_key=True)
    endpoint = db.Column(db.String(255))
    method = db.Column(db.String(10))
    user_agent = db.Column(db.String(255))
    ip_address = db.Column(db.String(45))
    timestamp = db.Column(db.DateTime, default=_datetime.datetime.utcnow)

    def __repr__(self):
        return f"<TrackUsageLog {self.method} {self.endpoint} at {self.timestamp}>"


class VisitorLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=_datetime.datetime.utcnow)
    ip_address = db.Column(db.String(100))
    path = db.Column(db.String(500))
    method = db.Column(db.String(10))
    referrer = db.Column(db.String(500))
    is_internal_referrer = db.Column(db.Boolean, default=False)
    ref_code = db.Column(db.String(100))
    user_agent = db.Column(db.String(500))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    session_id = db.Column(db.String(100), nullable=True)  # New session tracking field
    country = db.Column(db.String(100))
    region = db.Column(db.String(100))
    city = db.Column(db.String(100))
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)


class Event(db.Model):
    """
    Model representing an event hosted at a retailer or facility.

    Attributes:
        id (int): Primary key.
        event_title (str): Name of the event.
        full_address (str): Complete address of the event location.
        start_date (str): Start date in YYYY-MM-DD format.
        start_time (str): Start time in HH:mm format.
        latitude (float): Geocoded latitude.
        longitude (float): Geocoded longitude.
        first_seen (str): Timestamp when the event was first scraped.
        timestamp (datetime): Computed timestamp for calculations.
    """
    __tablename__ = "events"

    id = db.Column(db.Integer, primary_key=True)
    event_title = db.Column(db.String(255), nullable=False)
    full_address = db.Column(db.String(255), nullable=False)
    start_date = db.Column(db.String(100), nullable=True)
    start_time = db.Column(db.String(100), nullable=True)
    latitude = db.Column(db.Float, nullable=True)
    longitude = db.Column(db.Float, nullable=True)
    first_seen = db.Column(db.String(100), nullable=True)
    end_date = db.Column(db.DateTime, nullable=True)
    end_time = db.Column(db.Time, nullable=True)
    registration_url = db.Column(db.Text, nullable=True)
    price = db.Column(db.Float, nullable=True)
    email = db.Column(db.Text, nullable=True)
    phone = db.Column(db.Text, nullable=True)
    timestamp = db.Column(db.DateTime, nullable=True)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._update_timestamp()

    def _update_timestamp(self):
        """Update timestamp based on start_date and start_time"""
        if self.start_date and self.start_time:
            try:
                date_str = f"{self.start_date} {self.start_time}"
                self.timestamp = _datetime.datetime.strptime(date_str, '%Y-%m-%d %H:%M')
            except ValueError:
                current_app.logger.error(f"Error updating timestamp for event {self.id}: Invalid date/time format")

    @property
    def formatted_date(self):
        """Return date in MMM d, YYYY format"""
        from .utils import format_date_for_display
        return format_date_for_display(self.start_date)

    @property
    def formatted_time(self):
        """Return time in h:mm AM/PM format"""
        from .utils import format_time_for_display
        return format_time_for_display(self.start_time)

    def to_dict(self):
        """Convert event to dictionary for JSON serialization"""
        return {
            'id': self.id,
            'event_title': self.event_title,
            'start_date': self.formatted_date,
            'start_time': self.formatted_time,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'latitude': self.latitude,
            'longitude': self.longitude,
            'full_address': self.full_address
        }


class Retailer(db.Model):
    """
    Model representing a retailer or location.

    Attributes:
        id (int): Primary key.
        retailer (str): Name of the retailer.
        retailer_type (str): Type or category of the retailer.
        full_address (str): Complete address (must be unique).
        latitude (float): Geographic latitude.
        longitude (float): Geographic longitude.
        place_id (str): External identifier (e.g., Google Place ID).
        first_seen (datetime): First seen timestamp.
        phone_number (str): Contact phone number.
        website (str): Retailer website.
        opening_hours (Text): Operating hours.
        rating (float): Retailer rating.
        last_api_update (datetime): Timestamp of the last update from an API.
        machine_count (int): Number of machines at the retailer.
        previous_count (int): Previous machine count.
        status (str): Current status.
        enabled (bool): Whether the retailer is enabled (default: True).
    """
    __tablename__ = "retailers"
    id = db.Column(db.Integer, primary_key=True)
    retailer = db.Column(db.String(255))
    retailer_type = db.Column(db.String(20))
    full_address = db.Column(db.String(255), unique=True, nullable=False)
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    place_id = db.Column(db.String(100))
    first_seen = db.Column(db.DateTime)
    phone_number = db.Column(db.String(50))
    website = db.Column(db.String(255))
    opening_hours = db.Column(db.Text)
    rating = db.Column(db.Float)
    last_api_update = db.Column(db.DateTime, nullable=True)
    machine_count = db.Column(db.Integer, default=0)
    previous_count = db.Column(db.Integer, default=0)
    status = db.Column(db.String(100))
    enabled = db.Column(db.Boolean, default=True)


class Role(db.Model, RoleMixin):
    """
    Model representing a user role.

    Attributes:
        id (int): Primary key.
        name (str): Unique role name.
        description (str): Description of the role.
    """
    id = db.Column(db.Integer(), primary_key=True)
    name = db.Column(db.String(80), unique=True)
    description = db.Column(db.String(255))


class User(db.Model, UserMixin):
    """
    Model representing a user in the system.

    Essential fields for Flask-Security:
      - email: the user's email address.
      - password: the hashed password.
      - active: indicates if the user is active.
      - fs_uniquifier: a unique string to invalidate sessions when security credentials change.
    Additional fields include first_name, last_name, and pro_end_date.
    Billing address fields have been removed.
    New cancellation fields have been added to record:
      - canceled_at: the datetime when a cancellation is processed.
      - cancellation_reason: the reason provided for cancellation.
      - cancellation_comment: any additional comments regarding the cancellation.
    """
    __tablename__ = "user"

    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(25), nullable=True)
    last_name = db.Column(db.String(25), nullable=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    fs_uniquifier = db.Column(db.String(64), unique=True, nullable=False, default=lambda: uuid.uuid4().hex)
    active = db.Column(db.Boolean())
    confirmed_at = db.Column(db.DateTime())
    roles = db.relationship('Role', secondary=roles_users, backref=db.backref('users', lazy='dynamic'))
    pro_end_date = db.Column(db.DateTime(), nullable=True)
    last_login = db.Column(db.DateTime(), nullable=True)
    login_count = db.Column(db.Integer(), default=0, nullable=False)
    cust_id = db.Column(db.String(255), unique=True)
    canceled_at = db.Column(db.DateTime(), nullable=True)
    cancellation_reason = db.Column(db.String(255), nullable=True)
    cancellation_comment = db.Column(db.Text, nullable=True)



    def get_initial_password_token(self, expires_in=3600):
        """
        Generate a time-limited token for initial password setup for Stripe users.

        This token is used to allow a user created via Stripe to set their
        password for the first time.

        Args:
            expires_in (int): The number of seconds the token should be valid for.

        Returns:
            str: The generated token, or None if an error occurred.
        """
        try:
            s = URLSafeTimedSerializer(current_app.config['SECRET_KEY'], salt='initial-password-salt')
            token = s.dumps({'initial_password': self.id, 'uniquifier': self.fs_uniquifier})
            current_app.logger.info(f"Initial password token generated for user {self.email}")
            return token
        except Exception as e:
            current_app.logger.error(f"Error generating initial password token for user {self.email}: {e}")
            return None

    @staticmethod
    def verify_initial_password_token(token):
        """
        Verify an initial password token and return the corresponding user if valid.

        This method is used to verify tokens generated by get_initial_password_token.

        Args:
            token (str): The token to verify.

        Returns:
            User: The user associated with the token, or None if the token is invalid.
        """
        s = URLSafeTimedSerializer(current_app.config['SECRET_KEY'], salt='initial-password-salt')
        try:
            data = s.loads(token, max_age=3600)
        except SignatureExpired:
            current_app.logger.warning("Initial password token expired")
            return None
        except BadSignature:
            current_app.logger.warning("Invalid initial password token")
            return None
        except Exception as e:
            current_app.logger.error(f"Error verifying initial password token: {e}")
            return None
        user_id = data.get('initial_password')
        uniquifier = data.get('uniquifier')
        user = User.query.get(user_id)
        if user is None or user.fs_uniquifier != uniquifier:
            current_app.logger.warning(f"Initial password token verification failed for user_id: {user_id}")
            return None
        current_app.logger.info(f"Initial password token verified for user: {user.email}")
        return user



    def verify_password(self, password):
        """
        Verify a password against the stored hash.
        
        This method is required by Flask-Security for password authentication.
        """
        from werkzeug.security import check_password_hash
        from flask import current_app
        
        current_app.logger.info(f"VERIFY_PASSWORD called for user {self.email}")
        current_app.logger.info(f"   Password length: {len(password)}")
        current_app.logger.info(f"   Stored hash length: {len(self.password)}")
        
        result = check_password_hash(self.password, password)
        current_app.logger.info(f"   Verification result: {result}")
        
        return result

    def __repr__(self):
        return (f"<User id={self.id} email={self.email} first_name={self.first_name} "
                f"last_name={self.last_name} cust_id={self.cust_id}>")


class BillingEvent(db.Model):
    __tablename__ = 'billing_event'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    event_type = db.Column(db.String(255), nullable=False)
    event_timestamp = db.Column(db.DateTime, default=_datetime.datetime.utcnow, nullable=False)
    details = db.Column(db.Text)

    def __repr__(self):
        return f'<BillingEvent {self.event_type} for user_id {self.user_id} at {self.event_timestamp}>'


class MapUsage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.String(100), nullable=False)
    lat = db.Column(db.Float, nullable=False)
    lng = db.Column(db.Float, nullable=False)
    zoom_level = db.Column(db.Integer)
    timestamp = db.Column(db.DateTime, default=_datetime.datetime.utcnow)


class LegendClick(db.Model):
    __tablename__ = 'legend_clicks'
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=_datetime.datetime.utcnow, index=True)
    session_id = db.Column(db.String(100), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    is_pro = db.Column(db.Boolean, default=False)
    control_id = db.Column(db.String(100), nullable=False, index=True)
    path = db.Column(db.String(500))
    zoom = db.Column(db.Integer)
    center_lat = db.Column(db.Float)
    center_lng = db.Column(db.Float)


class RouteEvent(db.Model):
    __tablename__ = 'route_events'
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=_datetime.datetime.utcnow, index=True)
    session_id = db.Column(db.String(100), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    is_pro = db.Column(db.Boolean, default=False)
    event = db.Column(db.String(20), nullable=False, index=True)  # open | preview | go
    max_distance = db.Column(db.Integer)
    max_stops = db.Column(db.Integer)
    options_json = db.Column(db.Text)  # JSON-encoded options snapshot


class OutboundMessage(db.Model):
    __tablename__ = 'outbound_messages'
    id = db.Column(db.Integer, primary_key=True)
    parent_message_id = db.Column(db.Integer, db.ForeignKey('message.id'), nullable=True)
    to_email = db.Column(db.String(255), nullable=False)
    subject = db.Column(db.String(255), nullable=False)
    body = db.Column(db.Text, nullable=False)
    sent_by_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    sent_at = db.Column(db.DateTime, default=_datetime.datetime.utcnow, index=True)


class BulkEmailJob(db.Model):
    __tablename__ = 'bulk_email_jobs'
    id = db.Column(db.Integer, primary_key=True)
    subject = db.Column(db.String(255), nullable=False)
    body = db.Column(db.Text, nullable=False)
    created_by_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=_datetime.datetime.utcnow)
    total_recipients = db.Column(db.Integer, default=0)
    sent_count = db.Column(db.Integer, default=0)
    failed_count = db.Column(db.Integer, default=0)

class BulkEmailRecipient(db.Model):
    __tablename__ = 'bulk_email_recipients'
    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.Integer, db.ForeignKey('bulk_email_jobs.id'), nullable=False, index=True)
    email = db.Column(db.String(255), nullable=False)
    status = db.Column(db.String(20), default='pending')  # pending | sent | failed
    error = db.Column(db.Text)
    sent_at = db.Column(db.DateTime)
class PinInteraction(db.Model):
    __tablename__ = 'pin_interactions'
    id = db.Column(db.Integer, primary_key=True)
    # Canonical identity: place_id when available
    marker_id = db.Column(db.String(100), nullable=False)
    place_id = db.Column(db.String(100), nullable=True, index=True)
    session_id = db.Column(db.String(100), nullable=False)
    lat = db.Column(db.Float)
    lng = db.Column(db.Float)
    timestamp = db.Column(db.DateTime, default=_datetime.datetime.utcnow)


class PinPopularity(db.Model):
    __tablename__ = 'pin_popularity'
    place_id = db.Column(db.String(100), primary_key=True)
    total_clicks = db.Column(db.Integer, nullable=False, default=0)
    last_clicked_at = db.Column(db.DateTime)
    last_lat = db.Column(db.Float)
    last_lng = db.Column(db.Float)


class Message(db.Model):
    """
    Model representing a message sent by a user.

    Attributes:
        id (int): Primary key.
        sender_id (int): Foreign key linking to the sender (User).
        recipient_id (int): Foreign key linking to the recipient (User).
        communication_type (str): Type of communication (e.g., suggestion, report).
        subject (str): Subject of the message.
        body (Text): Body content of the message.
        reported_address (str): Reported address (for report messages).
        reported_phone (str): Reported phone number (for report messages).
        reported_website (str): Reported website (for report messages).
        reported_hours (str): Reported opening hours (for report messages).
        timestamp (datetime): Time when the message was created.
        read (bool): Indicates if the message has been read.
        name (str): Name for response
        address (str): Address for response
        email (str): Email for response
    """
    __tablename__ = 'message'

    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    recipient_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    communication_type = db.Column(db.String(50), nullable=False)
    subject = db.Column(db.String(255), nullable=False)
    body = db.Column(db.Text, nullable=False)
    reported_address = db.Column(db.String(255), nullable=True)
    reported_phone = db.Column(db.String(100), nullable=True)
    reported_website = db.Column(db.String(255), nullable=True)
    reported_hours = db.Column(db.String(255), nullable=True)
    timestamp = db.Column(db.DateTime, default=_datetime.datetime.utcnow)
    read = db.Column(db.Boolean, default=False)
    name = db.Column(db.String(255), nullable=True)
    address = db.Column(db.String(255), nullable=True)
    email = db.Column(db.String(255), nullable=True)


class LoginEvent(db.Model):
    """
    Model representing an individual login event for a user.

    This table logs each login event so you can analyze user engagement,
    login frequency, and trends over time.

    Attributes:
        id (int): Primary key.
        user_id (int): Foreign key linking to the user who logged in.
        login_timestamp (datetime): The time the login occurred.
        ip_address (str): (Optional) The IP address from which the login occurred.
        user_agent (str): (Optional) The user agent string from the client.
    """
    __tablename__ = 'login_event'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    login_timestamp = db.Column(db.DateTime, nullable=False, default=_datetime.datetime.utcnow)
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.Text)


class ProcessedWebhookEvent(db.Model):
    """
    Model for storing processed Stripe webhook event IDs to enable idempotency.

    Attributes:
      - id (int): Primary key.
      - event_id (str): The unique Stripe event identifier.
      - processed_at (datetime): Timestamp when the event was processed.
    """
    __tablename__ = 'processed_webhook_events'

    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.String(255), unique=True, nullable=False)
    processed_at = db.Column(db.DateTime, default=_datetime.datetime.utcnow, nullable=False)

    def __repr__(self):
        return f"<ProcessedWebhookEvent event_id={self.event_id} processed_at={self.processed_at}>"


class StripeSession(db.Model):
    __tablename__ = 'stripe_session'
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.String(255), unique=True, nullable=False)
    initial_password_token = db.Column(db.String(255), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=_datetime.datetime.utcnow)

    def __repr__(self):
        return f"<StripeSession session_id={self.session_id} user_id={self.user_id}>"


class Page(db.Model):
    """
    Model representing a page in the application.
    
    Attributes:
        id (int): Primary key.
        path (str): The URL path of the page.
        visits (int): Number of visits to this page.
        last_visit (datetime): Timestamp of the last visit.
    """
    __tablename__ = 'pages'
    
    id = db.Column(db.Integer, primary_key=True)
    path = db.Column(db.String(500), unique=True, nullable=False)
    visits = db.Column(db.Integer, default=0)
    last_visit = db.Column(db.DateTime, default=_datetime.datetime.utcnow)

    def __repr__(self):
        return f"<Page {self.path}>"


class Referrer(db.Model):
    """
    Model representing a referrer to the application.
    
    Attributes:
        id (int): Primary key.
        url (str): The referrer URL.
        visits (int): Number of visits from this referrer.
        last_visit (datetime): Timestamp of the last visit.
        is_internal (bool): Whether this is an internal referrer.
    """
    __tablename__ = 'referrers'
    
    id = db.Column(db.Integer, primary_key=True)
    url = db.Column(db.String(500), unique=True, nullable=False)
    visits = db.Column(db.Integer, default=0)
    last_visit = db.Column(db.DateTime, default=_datetime.datetime.utcnow)
    is_internal = db.Column(db.Boolean, default=False)

    def __repr__(self):
        return f"<Referrer {self.url}>"


class ReferrerCode(db.Model):
    """
    Model representing a referrer code used in the application.
    
    Attributes:
        id (int): Primary key.
        code (str): The referrer code.
        visits (int): Number of visits using this code.
        last_visit (datetime): Timestamp of the last visit.
    """
    __tablename__ = 'referrer_codes'
    
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(100), unique=True, nullable=False)
    visits = db.Column(db.Integer, default=0)
    last_visit = db.Column(db.DateTime, default=_datetime.datetime.utcnow)

    def __repr__(self):
        return f"<ReferrerCode {self.code}>"


class Location(db.Model):
    """
    Model representing a visitor location.
    
    Attributes:
        id (int): Primary key.
        city (str): City name.
        region (str): Region/state name.
        country (str): Country name.
        visits (int): Number of visits from this location.
        last_visit (datetime): Timestamp of the last visit.
    """
    __tablename__ = 'locations'
    
    id = db.Column(db.Integer, primary_key=True)
    city = db.Column(db.String(100))
    region = db.Column(db.String(100))
    country = db.Column(db.String(100))
    visits = db.Column(db.Integer, default=0)
    last_visit = db.Column(db.DateTime, default=_datetime.datetime.utcnow)

    def __repr__(self):
        return f"<Location {self.city}, {self.region}, {self.country}>"
