import requests
import time
import logging
from datetime import datetime
from flask import current_app, render_template
from flask_mail import Message

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


def get_domain_settings(recipient_domain):
    """Get email settings for a specific domain."""
    domain_settings = current_app.config.get('MAILGUN_DOMAIN_ALIASES', {}).get(recipient_domain, {})
    return {
        'from_name': domain_settings.get('from_name', current_app.config['MAILGUN_FROM_NAME']),
        'reply_to': domain_settings.get('reply_to', current_app.config['MAILGUN_REPLY_TO']),
        'unsubscribe': domain_settings.get('unsubscribe', current_app.config['MAILGUN_LIST_UNSUBSCRIBE'])
    }


def custom_send_mail(message):
    """
    Send email using Mailgun API with retries.
    
    Args:
        message: A Flask-Mail style message object with recipients, subject, html attributes.

    Returns:
        Response from Mailgun API or None if failed.
    """
    api_key = current_app.config["MAILGUN_API_KEY"]
    domain = current_app.config["MAILGUN_DOMAIN"]
    sender = "Tamermap.com <no-reply@mg.tamermap.com>"
    if not sender or 'no-reply' not in sender:
        sender = "no-reply@mg.tamermap.com"

    url = f"https://api.mailgun.net/v3/{domain}/messages"

    recipients = message.recipients if isinstance(message.recipients, list) else [message.recipients]
    message_id = f"{datetime.now().strftime('%Y%m%d%H%M%S')}.{recipients[0].split('@')[0]}@{domain}"

    data = {
        "from": sender,
        "to": recipients,
        "subject": message.subject,
        "html": message.html,
        "text": message.body,
        "h:Reply-To": current_app.config["MAILGUN_REPLY_TO"],
        "h:List-Unsubscribe": current_app.config["MAILGUN_LIST_UNSUBSCRIBE"],
        "o:tracking": current_app.config["MAILGUN_TRACK_OPENS"],
        "o:tracking-clicks": current_app.config["MAILGUN_TRACK_CLICKS"],
        "o:dkim": "yes",
        "o:tag": ["account-management", "password-reset"],
        "h:X-Mailgun-Variables": '{"category": "account", "type": "password-reset"}',
        "h:Message-ID": f"<{message_id}>",
        "h:Sender": f"postmaster@{domain}",
        "h:X-Mailer": "TamermapMailer/1.0",
        "h:X-Auto-Response-Suppress": "OOF, AutoReply",
        "h:Precedence": "bulk",
        "h:X-Report-Abuse": f"Please report abuse here: {current_app.config['MAILGUN_REPLY_TO']}",
        "h:List-Id": f"Tamermap Account Management <account.{domain}>",
        "h:Feedback-ID": f"password-reset:{domain}",
        "h:Authentication-Results": f"spf=pass smtp.mailfrom=postmaster@{domain}",
        "h:ARC-Authentication-Results": f"i=1; mx.mailgun.org; spf=pass smtp.mailfrom=postmaster@{domain}",
        "h:Return-Path": f"<bounce+{message_id}>",
        "v:user-type": "registered",
        "v:template": "password-reset",
        "v:sender-domain": domain
    }

    max_retries = 5
    retry_delay = 3  # seconds

    for attempt in range(1, max_retries + 1):
        try:
            response = requests.post(
                url,
                auth=("api", api_key),
                data=data
            )
            response.raise_for_status()
            logger.info(f"Email sent successfully via Mailgun to {recipients}")
            return response
        except requests.RequestException as e:
            logger.error(f"Mailgun send attempt {attempt} failed: {e}")
            if attempt == max_retries:
                logger.error("Reached maximum retries, email not sent.")
                return None
            time.sleep(retry_delay)


def send_email_with_context(subject, template, recipient, **kwargs):
    """
    Send an email with proper context including datetime.
    
    Args:
        subject (str): Email subject
        template (str): Template path without extension
        recipient (str): Recipient email address
        **kwargs: Additional context variables for the template
    """
    try:
        # Add datetime to context
        context = {
            'datetime': datetime,
            **kwargs
        }

        # Render both HTML and text versions; allow raw body overrides
        body_html_override = kwargs.get('body_html')
        body_text_override = kwargs.get('body_text')
        html_content = body_html_override or render_template(f"{template}.html", **context)
        text_content = body_text_override or render_template(f"{template}.txt", **context)

        # Create message
        msg = Message(
            subject=subject,
            recipients=[recipient],
            html=html_content,
            body=text_content
        )

        # Send using custom email function
        return custom_send_mail(msg)

    except Exception as e:
        current_app.logger.error(f"Failed to send email to {recipient}: {str(e)}", exc_info=True)
        return False
