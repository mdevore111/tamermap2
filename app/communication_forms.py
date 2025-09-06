# communication_forms.py

from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SubmitField, SelectField, ValidationError, HiddenField, BooleanField
from wtforms.validators import DataRequired, Length, Optional
from datetime import datetime
import re


class MessageForm(FlaskForm):
    """
    Form for sending messages, including suggestions, general contact inquiries, or data reports.

    This form collects:
      - The type of communication (suggestion, contact, or report)
      - A subject line with a maximum length restriction
      - The message body

    The form ensures all fields are provided using validators.
    """

    # Select field to choose the type of communication, with predefined options.
    communication_type = SelectField(
        'Communication Type',
        choices=[
            ('suggestion', 'Suggestion / Site Improvement'),
            ('contact', 'Let\'s Connect'),
            ('location', 'Report Location'),
            ('report', 'Report Missing or Incorrect Vendor Data'),
            ('support', 'Customer Support'),
            ('business', 'Business Inquiry'),
            ('post_wins', 'Post Wins')
        ],
        default='contact',
        validators=[DataRequired()]
    )

    # Option fields for reply
    name = StringField('Your Name (Required if you would like a response)', validators=[Optional(), Length(max=255)])
    address = StringField('Your Email Address (Required if you would like a response)', validators=[Optional(), Length(max=255)])

    # Only enforce on non‐report types; for 'report' we'll use the hidden input in the template
    subject = StringField('Subject', validators=[Optional(), Length(max=255)])

    # Single body field for everything; label gets overridden in the template for reports
    body = TextAreaField('Message', validators=[DataRequired()])

    # Optional, category-specific fields (stored inline in message body by server)
    # Support
    support_topic = SelectField('Support Topic', choices=[
        ('account', 'Account / Login'),
        ('billing', 'Billing / Payments'),
        ('pro', 'Pro Features'),
        ('bug', 'Bug Report'),
        ('other', 'Other')
    ], validators=[Optional()])
    order_number = StringField('Order Number', validators=[Optional(), Length(max=255)])

    # Business
    company_name = StringField('Company Name', validators=[Optional(), Length(max=255)])
    company_website = StringField('Company Website', validators=[Optional(), Length(max=255)])
    company_size = SelectField('Company Size', choices=[
        ('1-10', '1-10'), ('11-50', '11-50'), ('51-200', '51-200'), ('200+', '200+')
    ], validators=[Optional()])

    # Post Wins
    win_type = SelectField('Type of Win', choices=[
        ('single_trip', 'Single Trip Success'),
        ('route_planning', 'Route Planning Success'),
        ('heatmap_usage', 'Heat Map Success'),
        ('collection_building', 'Collection Building'),
        ('time_saved', 'Time Saved'),
        ('money_saved', 'Money Saved'),
        ('rare_find', 'Rare Card Find'),
        ('other', 'Other')
    ], validators=[Optional()])
    location_used = StringField('Location(s) Used', validators=[Optional(), Length(max=255)])
    cards_found = StringField('Cards Found', validators=[Optional(), Length(max=255)])
    time_saved = StringField('Time Saved', validators=[Optional(), Length(max=100)])
    money_saved = StringField('Money Saved', validators=[Optional(), Length(max=100)])
    allow_feature = BooleanField('Allow us to feature your win (with permission)')

    reported_address = StringField('Reported Address', validators=[Optional()])
    reported_phone   = StringField('Reported Phone',   validators=[Optional()])
    reported_website = StringField('Reported Website', validators=[Optional()])
    reported_hours   = StringField('Reported Hours',   validators=[Optional()])
    out_of_business = BooleanField('Appears to be out of business')
    is_new_location = BooleanField('This is a new location')
    is_admin_report = BooleanField('This is for Admin review (not updating/correcting a location)')
    form_type = SelectField('Form Type', choices=[
        ('add_new', 'Add New Location'),
        ('correct_existing', 'Correct Existing Location')
    ], validators=[Optional()])

    # Spam prevention fields
    honeypot = HiddenField('Honeypot')  # Hidden field to catch bots
    timestamp = HiddenField('Timestamp')  # Form submission timestamp
    website = HiddenField('Website')  # Another honeypot field
    phone = HiddenField('Phone')  # Another honeypot field
    
    submit = SubmitField('Send Message')

    def validate_subject(self, field):
        if self.communication_type.data != 'report' and not field.data:
            raise ValidationError('Subject is required.')
    
    def validate_honeypot(self, field):
        """Honeypot validation - if this field is filled, it's likely a bot"""
        if field.data:
            raise ValidationError('Invalid form submission.')
    
    def validate_website(self, field):
        """Honeypot validation for website field"""
        if field.data:
            raise ValidationError('Invalid form submission.')
    
    def validate_phone(self, field):
        """Honeypot validation for phone field"""
        if field.data:
            raise ValidationError('Invalid form submission.')
    
    def validate_timestamp(self, field):
        """Validate timestamp to prevent instant submissions"""
        if not field.data:
            raise ValidationError('Invalid form submission.')
        
        try:
            timestamp = int(field.data)
            current_time = int(datetime.now().timestamp() * 1000)  # Convert to milliseconds
            time_diff = current_time - timestamp
            
            # Reject if submitted too quickly (less than 3 seconds)
            if time_diff < 3000:
                raise ValidationError('Form submitted too quickly. Please wait a moment and try again.')
            
            # Reject if timestamp is too old (more than 1 hour)
            if time_diff > 3600000:
                raise ValidationError('Form session expired. Please refresh and try again.')
                
        except (ValueError, TypeError):
            raise ValidationError('Invalid form submission.')
    
    def validate_body(self, field):
        """Validate message body for spam indicators"""
        if not field.data:
            return
            
        text = field.data.lower()
        
        # Check for excessive links (more than 3)
        link_count = len(re.findall(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', text))
        if link_count > 3:
            raise ValidationError('Too many links in message.')
        
        # Check for excessive caps (more than 70% caps)
        if len(text) > 10:
            caps_count = sum(1 for c in text if c.isupper())
            if caps_count / len(text) > 0.7:
                raise ValidationError('Too much text in capital letters.')
        
        # Check for common spam words
        spam_words = ['viagra', 'casino', 'loan', 'debt', 'credit', 'make money', 'earn money', 'work from home']
        for word in spam_words:
            if word in text:
                raise ValidationError('Message contains inappropriate content.')
        
        # Check for excessive repetition
        words = text.split()
        if len(words) > 5:
            word_counts = {}
            for word in words:
                word_counts[word] = word_counts.get(word, 0) + 1
            max_repetition = max(word_counts.values())
            if max_repetition > len(words) * 0.3:  # More than 30% repetition
                raise ValidationError('Message contains too much repetition.')
    
    def validate_name(self, field):
        """Validate name field for spam"""
        if not field.data:
            return
            
        name = field.data.lower()
        
        # Check for suspicious patterns
        if re.search(r'\d', name):  # Numbers in name
            raise ValidationError('Name should not contain numbers.')
        
        if len(name) > 50:  # Very long names
            raise ValidationError('Name is too long.')
        
        # Check for common spam names
        spam_names = ['admin', 'test', 'spam', 'bot', 'robot']
        if name in spam_names:
            raise ValidationError('Invalid name provided.')
    
    def validate_address(self, field):
        """Validate email address for spam"""
        if not field.data:
            return
            
        email = field.data.lower()
        
        # Basic email validation
        if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
            raise ValidationError('Invalid email format.')
        
        # Check for disposable email domains
        disposable_domains = [
            '10minutemail.com', 'guerrillamail.com', 'mailinator.com', 'tempmail.org',
            'throwaway.email', 'temp-mail.org', 'sharklasers.com', 'getairmail.com'
        ]
        domain = email.split('@')[-1]
        if domain in disposable_domains:
            raise ValidationError('Please use a valid email address.')
