import hmac
import hashlib
from flask import Blueprint, request, jsonify, current_app
from ..extensions import db
from ..models import User
from datetime import datetime
import logging

logger = logging.getLogger(__name__)
mailgun_webhooks = Blueprint('mailgun_webhooks', __name__)

def verify_mailgun_webhook():
    """Verify that the webhook request is from Mailgun."""
    if not request.form.get('timestamp') or not request.form.get('token') or not request.form.get('signature'):
        return False
    
    timestamp = request.form.get('timestamp')
    token = request.form.get('token')
    signature = request.form.get('signature')
    
    # Verify timestamp is not too old (e.g., not more than 5 minutes old)
    if abs(int(timestamp) - datetime.now().timestamp()) > 300:
        logger.warning("Mailgun webhook timestamp too old")
        return False
    
    # Verify signature
    data = f"{timestamp}{token}".encode('utf-8')
    expected_signature = hmac.new(
        current_app.config['MAILGUN_API_KEY'].encode('utf-8'),
        data,
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(signature, expected_signature)

@mailgun_webhooks.route('/webhooks/mailgun/bounce', methods=['POST'])
def handle_bounce():
    """Handle email bounce notifications from Mailgun."""
    if not verify_mailgun_webhook():
        return jsonify({'error': 'Invalid signature'}), 401
    
    try:
        recipient = request.form.get('recipient')
        code = request.form.get('code')
        error = request.form.get('error')
        event = request.form.get('event')
        
        logger.info(f"Mailgun bounce received for {recipient}: {event} - {code} - {error}")
        
        # Find user by email
        user = User.query.filter_by(email=recipient).first()
        if user:
            # Increment bounce count
            user.bounce_count = (user.bounce_count or 0) + 1
            
            # Check if we should mark the email as invalid
            if user.bounce_count >= current_app.config['MAILGUN_BOUNCE_THRESHOLD']:
                user.email_valid = False
                logger.warning(f"Marking email as invalid for user {user.id} due to multiple bounces")
            
            db.session.commit()
        
        return jsonify({'status': 'success'}), 200
    
    except Exception as e:
        logger.error(f"Error processing bounce webhook: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@mailgun_webhooks.route('/webhooks/mailgun/complaint', methods=['POST'])
def handle_complaint():
    """Handle spam complaint notifications from Mailgun."""
    if not verify_mailgun_webhook():
        return jsonify({'error': 'Invalid signature'}), 401
    
    try:
        recipient = request.form.get('recipient')
        event = request.form.get('event')
        
        logger.info(f"Mailgun complaint received for {recipient}: {event}")
        
        # Find user by email
        user = User.query.filter_by(email=recipient).first()
        if user:
            # Mark email as invalid immediately for complaints
            user.email_valid = False
            user.complaint_count = (user.complaint_count or 0) + 1
            db.session.commit()
            logger.warning(f"Marked email as invalid for user {user.id} due to spam complaint")
        
        return jsonify({'status': 'success'}), 200
    
    except Exception as e:
        logger.error(f"Error processing complaint webhook: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@mailgun_webhooks.route('/webhooks/mailgun/delivery', methods=['POST'])
def handle_delivery():
    """Handle successful delivery notifications from Mailgun."""
    if not verify_mailgun_webhook():
        return jsonify({'error': 'Invalid signature'}), 401
    
    try:
        recipient = request.form.get('recipient')
        event = request.form.get('event')
        
        logger.info(f"Mailgun delivery confirmed for {recipient}: {event}")
        
        # Find user by email
        user = User.query.filter_by(email=recipient).first()
        if user:
            # Reset bounce count on successful delivery
            user.bounce_count = 0
            user.email_valid = True
            db.session.commit()
        
        return jsonify({'status': 'success'}), 200
    
    except Exception as e:
        logger.error(f"Error processing delivery webhook: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@mailgun_webhooks.route('/webhooks/mailgun/validation', methods=['POST'])
def handle_validation():
    """Handle email validation results from Mailgun."""
    if not verify_mailgun_webhook():
        return jsonify({'error': 'Invalid signature'}), 401
    
    try:
        recipient = request.form.get('recipient')
        is_valid = request.form.get('is_valid', '').lower() == 'true'
        risk = request.form.get('risk', '')
        
        logger.info(f"Mailgun validation result for {recipient}: valid={is_valid}, risk={risk}")
        
        # Find user by email
        user = User.query.filter_by(email=recipient).first()
        if user:
            user.email_valid = is_valid
            user.email_risk = risk
            db.session.commit()
        
        return jsonify({'status': 'success'}), 200
    
    except Exception as e:
        logger.error(f"Error processing validation webhook: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500 