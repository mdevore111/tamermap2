"""
Stripe Webhooks Module

This module defines a Flask Blueprint to handle incoming Stripe webhook events.
It processes events such as checkout.session.completed, invoice.payment_succeeded,
customer.subscription.updated, and invoice.payment_failed.

Enhancements include persistent idempotency through the ProcessedWebhookEvent table,
handling out-of-order events, reactivation, and additional error handling.
"""

import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

import stripe
from dateutil.relativedelta import relativedelta
from flask import Blueprint, request, abort, jsonify, url_for, current_app, redirect, flash, render_template
from flask_security import send_mail
from werkzeug.security import generate_password_hash
from flask_mail import Message
import json

from ..extensions import db
from ..models import User, Role, StripeSession, BillingEvent, ProcessedWebhookEvent

# Create a Blueprint for Stripe webhooks with URL prefix /webhooks
stripe_webhooks_bp = Blueprint('stripe_webhooks', __name__, url_prefix='/webhooks')

# Event handler registry
EVENT_HANDLERS = {
    'checkout.session.completed': 'handle_checkout_session',
    'invoice.payment_succeeded': 'handle_invoice_payment_succeeded',
    'customer.subscription.updated': 'handle_subscription_updated',
    'invoice.payment_failed': 'handle_invoice_payment_failed',
    'customer.created': 'handle_customer_created',
    'customer.updated': 'handle_customer_updated',
    'setup_intent.created': 'handle_setup_intent_created',
    'setup_intent.requires_action': 'handle_setup_intent_requires_action',
    'setup_intent.succeeded': 'handle_setup_intent_succeeded',
    'setup_intent.setup_failed': 'handle_setup_intent_failed',
    'customer.subscription.created': 'handle_subscription_created',
    'customer.subscription.deleted': 'handle_subscription_deleted',
    'invoice.created': 'handle_invoice_created',
    'payment_intent.created': 'handle_payment_intent_created',
    'payment_intent.payment_failed': 'handle_payment_intent_failed',
    'charge.failed': 'handle_charge_failed',
    'invoice.updated': 'handle_invoice_updated',
    'customer.subscription.trial_will_end': 'handle_trial_will_end',
    'payment_intent.succeeded': 'handle_payment_intent_succeeded',
    'charge.succeeded': 'handle_charge_succeeded',
    'charge.refunded': 'handle_charge_refunded',
    'charge.dispute.created': 'handle_charge_dispute_created',
    'customer.source.expiring': 'handle_customer_source_expiring',
    'customer.source.updated': 'handle_customer_source_updated',
    'invoice.finalized': 'handle_invoice_finalized',
    'invoice.paid': 'handle_invoice_paid',
}


@stripe_webhooks_bp.route('/stripe', methods=['POST'])
def stripe_webhook():
    """
    Main webhook handler that validates and routes Stripe events to appropriate handlers.
    """
    current_app.logger.info("Received Stripe webhook request")

    # Validate webhook signature and construct event
    event = validate_webhook_request()
    if not event:
        return jsonify({'error': 'Invalid webhook request'}), 400

    # Check idempotency
    if not check_idempotency(event):
        return jsonify({'status': 'duplicate'}), 200

    # Process the event
    try:
        process_event(event)
        return jsonify({'status': 'success'}), 200
    except Exception as exc:
        current_app.logger.error("Error processing event %s: %s", event.get('id'), exc)
        return jsonify({'error': str(exc)}), 500


def validate_webhook_request() -> Optional[Dict[str, Any]]:
    """
    Validate the webhook request and construct the event object.
    Returns None if validation fails.
    """
    payload = request.data
    sig_header = request.headers.get('Stripe-Signature')
    stripe.api_key = current_app.config.get("STRIPE_SECRET_KEY")
    endpoint_secret = current_app.config.get("STRIPE_ENDPOINT_SECRET")

    # Skip signature verification in development mode
    if current_app.debug:
        return json.loads(payload)

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)
        return event
    except ValueError as e:
        current_app.logger.error("Invalid payload: %s", e)
        return None
    except stripe.error.SignatureVerificationError as e:
        current_app.logger.error("Signature verification failed: %s", e)
        return None


def check_idempotency(event: Dict[str, Any]) -> bool:
    """
    Check if the event has already been processed.
    Returns True if the event should be processed, False if it's a duplicate.
    """
    event_id = event.get("id")
    current_app.logger.debug("Checking idempotency for event: %s", event_id)

    existing_event = ProcessedWebhookEvent.query.filter_by(event_id=event_id).first()
    if existing_event:
        current_app.logger.info("Duplicate event detected (%s); skipping processing.", event_id)
        return False

    return True


def process_event(event: Dict[str, Any]) -> None:
    """
    Process the event by routing it to the appropriate handler.
    """
    event_type = event.get('type')
    current_app.logger.info("Processing event type: %s", event_type)

    handler_name = EVENT_HANDLERS.get(event_type)
    if not handler_name:
        current_app.logger.info("Unhandled event type: %s", event_type)
        return

    handler = globals().get(handler_name)
    if not handler:
        current_app.logger.error("Handler not found for event type: %s", event_type)
        return

    try:
        # Record that the event has been processed BEFORE handling it
        # This ensures we don't process the same event twice
        try:
            processed_event = ProcessedWebhookEvent(event_id=event.get("id"))
            db.session.add(processed_event)
            db.session.commit()
        except Exception as e:
            if "UNIQUE constraint failed" in str(e):
                current_app.logger.info("Event %s already processed, skipping", event.get("id"))
                return
            raise

        # Now handle the event
        handler(event)
    except Exception as e:
        current_app.logger.error("Error in handler %s: %s", handler_name, e)
        # Don't raise the exception - we want to return a 200 status even if processing fails
        # This prevents Stripe from retrying the webhook unnecessarily


# Event Handlers
def handle_customer_created(event: Dict[str, Any]) -> None:
    """
    Handle customer.created event.
    This is a no-op as customer creation is handled during checkout.
    """
    customer = event['data']['object']
    current_app.logger.info("Received customer.created event for customer: %s", customer.get('id'))
    current_app.logger.debug("Customer details: %s", customer)


def handle_customer_updated(event: Dict[str, Any]) -> None:
    """
    Handle customer.updated event.
    Updates user information if needed.
    """
    customer = event['data']['object']
    current_app.logger.info("Processing customer.updated event for customer: %s", customer.get('id'))

    user = get_user_by_stripe_customer_id(customer.get('id'))
    if user:
        # Update user information if needed
        if customer.get('email') and customer.get('email').lower() != user.email.lower():
            user.email = customer.get('email').lower()
            current_app.logger.info("Updated user email: %s", user.email)

        if customer.get('currency'):
            user.currency = customer.get('currency')
            current_app.logger.info("Updated user currency: %s", user.currency)

        db.session.commit()


def handle_setup_intent_created(event: Dict[str, Any]) -> None:
    """
    Handle setup_intent.created event.
    Logs the creation of a new payment method setup intent.
    """
    setup_intent = event['data']['object']
    current_app.logger.info("Processing setup_intent.created event: %s", setup_intent.get('id'))
    current_app.logger.debug("Setup intent details: %s", setup_intent)


def handle_setup_intent_requires_action(event: Dict[str, Any]) -> None:
    """
    Handle setup_intent.requires_action event.
    This event occurs when 3D Secure authentication is required.
    The customer needs to complete authentication on the frontend.
    """
    setup_intent = event['data']['object']
    current_app.logger.info("Processing setup_intent.requires_action event: %s", setup_intent.get('id'))
    
    customer_id = setup_intent.get('customer')
    client_secret = setup_intent.get('client_secret')
    next_action = setup_intent.get('next_action', {})
    
    current_app.logger.info("SetupIntent requires 3D Secure authentication for customer: %s", customer_id)
    current_app.logger.debug("Next action type: %s", next_action.get('type'))
    current_app.logger.debug("Client secret: %s", client_secret[:20] + "..." if client_secret else None)
    
    # Log this for monitoring - the actual authentication happens on the frontend
    user = get_user_by_stripe_customer_id(customer_id)
    if user:
        log_billing_event(user, 'setup_intent_requires_action', {
            "setup_intent_id": setup_intent.get('id'),
            "payment_method_id": setup_intent.get('payment_method'),
            "next_action_type": next_action.get('type'),
            "requires_3d_secure": True
        })
        current_app.logger.info("Logged requires_action event for user: %s", user.email)
        
        # Send email notification to user about 3D Secure requirement
        try:
            from app.custom_email import send_email_with_context
            send_email_with_context(
                subject="Action Required: Complete Your Payment Setup",
                template="email/3d_secure_notification",
                recipient=user.email,
                user_name=user.first_name or user.email,
                setup_intent_id=setup_intent.get('id'),
                config=current_app.config
            )
            current_app.logger.info("Sent 3D Secure notification email to: %s", user.email)
        except Exception as e:
            current_app.logger.error("Failed to send 3D Secure notification email: %s", e)
        
        # Send admin notification for important events
        try:
            send_admin_notification(
                subject="🚨 Setup Intent Requires Action",
                template="email/admin_setup_intent_notification",
                setup_intent_id=setup_intent.get('id'),
                user_email=user.email,
                user_name=user.first_name or user.email,
                event_type="requires_action",
                next_action_type=next_action.get('type'),
                config=current_app.config
            )
            current_app.logger.info("Sent admin notification for setup intent requires_action")
        except Exception as e:
            current_app.logger.error("Failed to send admin notification: %s", e)


def handle_setup_intent_succeeded(event: Dict[str, Any]) -> None:
    """
    Handle setup_intent.succeeded event.
    Updates the user's payment method information.
    """
    setup_intent = event['data']['object']
    current_app.logger.info("Processing setup_intent.succeeded event: %s", setup_intent.get('id'))

    customer_id = setup_intent.get('customer')
    payment_method_id = setup_intent.get('payment_method')

    if customer_id and payment_method_id:
        user = get_user_by_stripe_customer_id(customer_id)
        if user:
            user.payment_method_id = payment_method_id
            db.session.commit()
            current_app.logger.info("Updated payment method for user: %s", user.email)


def handle_setup_intent_failed(event: Dict[str, Any]) -> None:
    """
    Handle setup_intent.failed event.
    Logs the failure of a payment method setup.
    """
    setup_intent = event['data']['object']
    current_app.logger.info("Processing setup_intent.failed event: %s", setup_intent.get('id'))

    user = get_user_by_stripe_customer_id(setup_intent.get('customer'))
    
    # Log the failure details
    log_billing_event(
        user=user,
        event_type="payment_method_setup_failed",
        event_data={
            "setup_intent_id": setup_intent.get('id'),
            "failure_reason": setup_intent.get('last_setup_error', {}).get('message'),
            "payment_method_type": setup_intent.get('payment_method_types', [])[0] if setup_intent.get('payment_method_types') else None
        }
    )
    
    # Send admin notification for failed setup intents
    if user:
        try:
            send_admin_notification(
                subject="❌ Setup Intent Failed",
                template="email/admin_setup_intent_notification",
                setup_intent_id=setup_intent.get('id'),
                user_email=user.email,
                user_name=user.first_name or user.email,
                event_type="failed",
                failure_reason=setup_intent.get('last_setup_error', {}).get('message'),
                config=current_app.config
            )
            current_app.logger.info("Sent admin notification for setup intent failed")
        except Exception as e:
            current_app.logger.error("Failed to send admin notification: %s", e)


def handle_checkout_session(event: Dict[str, Any]) -> None:
    """
    Handle checkout.session.completed event.
    Creates or updates user and sets up their subscription.
    """
    session = event['data']['object']
    current_app.logger.info("Processing checkout.session.completed event: %s", session.get('id'))

    # Check if this session has already been processed
    existing_session = StripeSession.query.filter_by(session_id=session.get('id')).first()
    if existing_session:
        current_app.logger.info("Session already processed: %s", session.get('id'))
        return

    customer_details = session.get('customer_details', {})
    email = customer_details.get('email')
    if not email:
        current_app.logger.error("No email provided in checkout session")
        return

    # Normalize email to lowercase
    email = email.lower().strip()

    # Get customer info
    customer_id = session.get('customer')
    name = customer_details.get('name', '')
    address = customer_details.get('address', {})

    # Split name into first and last
    name_parts = name.split()
    first_name = name_parts[0] if name_parts else None
    last_name = name_parts[-1] if len(name_parts) > 1 else None

    # Get or create user
    user = get_user_by_stripe_customer_id(customer_id)
    if not user:
        user = User.query.filter(User.email.ilike(email)).first()
        if user:
            current_app.logger.info("Found existing user by email: %s", email)
            if not user.cust_id:
                user.cust_id = customer_id
                db.session.commit()
        else:
            current_app.logger.info("Creating new user with email: %s", email)
            user = create_user_from_stripe(customer_id, first_name, last_name, email)

    # Update user details
    if first_name and last_name:
        user.first_name = first_name
        user.last_name = last_name
    if address:
        user.address = address
    db.session.commit()

    # Generate password token
    try:
        token = user.get_initial_password_token()
        current_app.logger.info("Generated token for user: %s", user.email)

        # Store session
        stripe_session = StripeSession(
            session_id=session.get('id'),
            initial_password_token=token,
            user_id=user.id
        )
        db.session.add(stripe_session)
        db.session.commit()
        current_app.logger.info("Stored Stripe session: %s", stripe_session)
    except Exception as e:
        current_app.logger.error("Failed to generate token for user: %s", user.email)
        current_app.logger.error("Error: %s", e)


def handle_invoice_payment_succeeded(event: Dict[str, Any]) -> None:
    """
    Handle invoice.payment_succeeded event.
    Updates subscription status and dates.
    """
    invoice = event['data']['object']
    current_app.logger.info("Processing invoice.payment_succeeded event: %s", invoice.get('id'))

    customer_id = invoice.get('customer')
    user = get_user_by_stripe_customer_id(customer_id)
    if not user:
        current_app.logger.warning("No user found for customer: %s", customer_id)
        return

    # Check if this is a trial period invoice
    is_trial = False
    for line in invoice.get('lines', {}).get('data', []):
        if 'Trial period' in line.get('description', ''):
            is_trial = True
            break

    if is_trial:
        current_app.logger.info("Processing trial period invoice for user: %s", user.email)
        # Update trial period dates
        trial_end = datetime.fromtimestamp(invoice.get('period', {}).get('end', 0))
        user.trial_end = trial_end
        db.session.commit()
        current_app.logger.info("Updated trial end date: %s", trial_end)

        # Log billing event for trial period
        log_billing_event(
            user=user,
            event_type="trial_period_updated",
            event_data={
                "trial_end": trial_end.isoformat(),
                "invoice_id": invoice.get('id')
            }
        )
    else:
        current_app.logger.info("Processing paid invoice for user: %s", user.email)
        # Log the successful payment before extending subscription
        log_billing_event(
            user=user,
            event_type="payment_succeeded",
            event_data={
                "invoice_id": invoice.get('id'),
                "amount_paid": invoice.get('amount_paid'),
                "currency": invoice.get('currency')
            }
        )
        # Extend subscription
        update_or_extend_subscription_for_user(user, extend_subscription=True)


def handle_invoice_payment_failed(event: Dict[str, Any]) -> None:
    """
    Handle invoice.payment_failed event.
    Logs the failure and notifies the user.
    """
    invoice = event['data']['object']
    current_app.logger.info("Processing invoice.payment_failed event: %s", invoice.get('id'))

    customer_id = invoice.get('customer')
    user = get_user_by_stripe_customer_id(customer_id)
    if not user:
        current_app.logger.warning("No user found for customer: %s", customer_id)
        return

    # Log the failure
    log_billing_event(
        user=user,
        event_type="payment_failed",
        event_data={
            "invoice_id": invoice.get('id'),
            "amount_due": invoice.get('amount_due'),
            "attempt_count": invoice.get('attempt_count'),
            "next_payment_attempt": invoice.get('next_payment_attempt')
        }
    )

    # Send admin notification for invoice payment failures
    try:
        send_admin_notification(
            subject="📄 Invoice Payment Failed",
            template="email/admin_invoice_notification",
            invoice_id=invoice.get('id'),
            user_email=user.email,
            user_name=user.first_name or user.email,
            event_type="invoice_payment_failed",
            amount_due=invoice.get('amount_due'),
            attempt_count=invoice.get('attempt_count'),
            next_payment_attempt=invoice.get('next_payment_attempt'),
            config=current_app.config
        )
        current_app.logger.info("Sent admin notification for invoice payment failed")
    except Exception as e:
        current_app.logger.error("Failed to send admin notification: %s", e)


def handle_subscription_updated(event: Dict[str, Any]) -> None:
    """
    Handle customer.subscription.updated event.
    Updates subscription status and handles trial period.
    Note: Stripe handles most subscription-related emails, but we might want to
    add custom notifications for specific status changes.
    """
    subscription = event['data']['object']
    current_app.logger.info("Processing subscription.updated event: %s", subscription.get('id'))

    customer_id = subscription.get('customer')
    user = get_user_by_stripe_customer_id(customer_id)
    if not user:
        current_app.logger.warning("No user found for customer: %s", customer_id)
        return

    # Update subscription status
    status = subscription.get('status')
    current_app.logger.info("Subscription status: %s", status)

    if status == 'trialing':
        trial_end = datetime.fromtimestamp(subscription.get('trial_end', 0))
        user.trial_end = trial_end
        current_app.logger.info("Updated trial end date: %s", trial_end)
    elif status == 'active':
        user.trial_end = None
        current_app.logger.info("Subscription is now active")
    elif status == 'canceled':
        canceled_at = datetime.fromtimestamp(subscription.get('canceled_at', 0))
        user.canceled_at = canceled_at
        current_app.logger.info("Subscription canceled at: %s", canceled_at)
        # Note: Stripe handles cancellation confirmation emails

    # Handle cancellation details if present
    cancellation_details = subscription.get('cancellation_details')
    if cancellation_details:
        user.cancellation_reason = cancellation_details.get('reason')
        user.cancellation_comment = cancellation_details.get('comment')
        current_app.logger.info("Updated cancellation details")

    db.session.commit()


def get_user_by_stripe_customer_id(customer_id):
    """
    Retrieve a local user by their Stripe customer ID.
    """
    user = User.query.filter_by(cust_id=customer_id).first()
    current_app.logger.info("User lookup by Stripe ID: %s", user)
    return user


def update_or_extend_subscription_for_user(user, stripe_customer_id=None, extend_subscription=False):
    """
    Update the user record.
    If extend_subscription is True, extend the subscription end date by one month (from now or from current pro_end_date).
    """
    stripe.api_key = current_app.config.get("STRIPE_SECRET_KEY")
    if stripe_customer_id:
        user.cust_id = stripe_customer_id

    if extend_subscription:
        current_date = datetime.utcnow()

        # Check if we've recently extended this subscription
        recent_extension = BillingEvent.query.filter(
            BillingEvent.user_id == user.id,
            BillingEvent.event_type == "subscription_extended",
            BillingEvent.event_timestamp >= current_date - timedelta(minutes=5)
        ).first()

        if recent_extension:
            current_app.logger.warning(
                "Skipping subscription extension for user %s - recent extension detected within last 5 minutes",
                user.email
            )
            return user

        old_end_date = user.pro_end_date
        if user.pro_end_date and user.pro_end_date > current_date:
            new_end_date = user.pro_end_date + relativedelta(months=+1)
        else:
            new_end_date = current_date + relativedelta(months=+1)
            if not user.confirmed_at:
                user.confirmed_at = current_date
        user.pro_end_date = new_end_date

        # Log the subscription extension
        current_app.logger.info(
            "Extended subscription for user %s: %s -> %s",
            user.email,
            old_end_date,
            new_end_date
        )

        # Log billing event for the extension
        log_billing_event(
            user=user,
            event_type="subscription_extended",
            event_data={
                "old_end_date": old_end_date.isoformat() if old_end_date else None,
                "new_end_date": new_end_date.isoformat(),
                "extension_date": current_date.isoformat()
            }
        )

    db.session.add(user)
    db.session.commit()
    current_app.logger.info("User saved: %s", user)
    return user


def create_user_from_stripe(stripe_customer_id, first_name, last_name, email):
    """
    Create a new user from Stripe Checkout session data.
    Billing address fields are not collected.
    The new user is created as a Pro user with an initial trial period,
    and a welcome email is sent.
    """
    temp_password = generate_password_hash(uuid.uuid4().hex)
    now = datetime.utcnow()

    current_app.logger.info(f"Creating user: {email} with Stripe ID: {stripe_customer_id}")

    new_user = User(
        email=email,
        password=temp_password,
        first_name=first_name,
        last_name=last_name,
        active=True,
        confirmed_at=now,
        pro_end_date=now + timedelta(days=7),
        cust_id=stripe_customer_id
    )

    pro_role = Role.query.filter_by(name="Pro").first()
    if pro_role:
        new_user.roles.append(pro_role)
        current_app.logger.info(f"Assigned 'Pro' role to {email}")
    else:
        current_app.logger.warning("Pro role missing; user created without Pro role.")

    send_welcome_email(new_user)

    db.session.add(new_user)
    db.session.commit()
    current_app.logger.info("Created new user: %s", new_user)

    try:
        token = new_user.get_initial_password_token()
        current_app.logger.info(f"Initial password token generated for {email}")
    except Exception as e:
        current_app.logger.error(f"Token generation failed: {e}")
        token = None

    if not token:
        flash("Please request a password reset email again.", "info")
        return redirect(url_for('security.forgot_password'))

    return new_user


def send_welcome_email(user):
    """
    Send a welcome email to the new user using an HTML template.

    :param user: The User object.
    """
    current_app.logger.info(f"Starting welcome email process for user: {user.email}")

    from flask import render_template
    from flask_mail import Message

    forgot_password_link = url_for('security.forgot_password', _external=True)
    current_app.logger.debug(f"Generated forgot password link: {forgot_password_link}")

    try:
        # Render both HTML and text versions of the email
        current_app.logger.debug("Rendering email templates")
        html_content = render_template('email/welcome.html', user=user, forgot_password_link=forgot_password_link)
        text_content = render_template('email/welcome.txt', user=user, forgot_password_link=forgot_password_link)
        current_app.logger.debug("Email templates rendered successfully")

        # Create the message
        msg = Message(
            subject="Welcome to Tamermap.com!",
            recipients=[user.email],
            html=html_content,
            body=text_content
        )
        current_app.logger.debug(f"Message created for recipient: {user.email}")

        # Send using custom email function
        from app.custom_email import custom_send_mail
        current_app.logger.debug("Attempting to send email via custom_send_mail")
        response = custom_send_mail(msg)

        if response:
            current_app.logger.info("Welcome email sent successfully to: %s", user.email)
            current_app.logger.debug(f"Mail server response: {response}")
        else:
            current_app.logger.error("Failed to send welcome email to: %s - No response from mail server", user.email)

    except Exception as e:
        current_app.logger.error("Failed to send welcome email to %s: %s", user.email, str(e), exc_info=True)
        # Don't raise the exception - we don't want to block user creation if email fails
        # But we should log it for monitoring


def log_billing_event(user, event_type, event_data):
    """
    Log a billing or subscription event.
    For cancellation events, event_data should contain stripe_event_id, canceled_at, reason, and comment.
    """
    event = BillingEvent(
        user_id=user.id,
        event_type=event_type,
        event_timestamp=datetime.utcnow(),
        details=json.dumps(event_data)
    )
    db.session.add(event)
    db.session.commit()
    current_app.logger.info("Logged billing event for user %s: %s", user.email, event_type)


def send_admin_notification(subject, template, **kwargs):
    """
    Send notification email to admin for important events.
    """
    try:
        from app.custom_email import send_email_with_context
        send_email_with_context(
            subject=subject,
            template=template,
            recipient=current_app.config.get('ADMIN_EMAIL', 'mark@markdevore.com'),
            **kwargs
        )
        current_app.logger.info("Sent admin notification: %s", subject)
    except Exception as e:
        current_app.logger.error("Failed to send admin notification: %s", e)


def handle_subscription_created(event: Dict[str, Any]) -> None:
    """
    Handle customer.subscription.created event.
    Logs the creation of a new subscription.
    """
    subscription = event['data']['object']
    current_app.logger.info("Processing subscription.created event: %s", subscription.get('id'))
    current_app.logger.debug("Subscription details: %s", subscription)

    customer_id = subscription.get('customer')
    user = get_user_by_stripe_customer_id(customer_id)
    if user:
        log_billing_event(
            user=user,
            event_type="subscription_created",
            event_data={
                "subscription_id": subscription.get('id'),
                "status": subscription.get('status'),
                "trial_end": subscription.get('trial_end'),
                "current_period_end": subscription.get('current_period_end')
            }
        )


def handle_subscription_deleted(event: Dict[str, Any]) -> None:
    """
    Handle customer.subscription.deleted event.
    Logs the deletion of a subscription.
    """
    subscription = event['data']['object']
    current_app.logger.info("Processing subscription.deleted event: %s", subscription.get('id'))
    current_app.logger.debug("Subscription details: %s", subscription)

    customer_id = subscription.get('customer')
    user = get_user_by_stripe_customer_id(customer_id)
    if user:
        log_billing_event(
            user=user,
            event_type="subscription_deleted",
            event_data={
                "subscription_id": subscription.get('id'),
                "canceled_at": subscription.get('canceled_at'),
                "ended_at": subscription.get('ended_at')
            }
        )
        
        # Send admin notification for subscription cancellations
        try:
            send_admin_notification(
                subject="🚫 Subscription Cancelled",
                template="email/admin_subscription_notification",
                subscription_id=subscription.get('id'),
                user_email=user.email,
                user_name=user.first_name or user.email,
                event_type="subscription_deleted",
                canceled_at=subscription.get('canceled_at'),
                ended_at=subscription.get('ended_at'),
                config=current_app.config
            )
            current_app.logger.info("Sent admin notification for subscription deleted")
        except Exception as e:
            current_app.logger.error("Failed to send admin notification: %s", e)


def handle_invoice_created(event: Dict[str, Any]) -> None:
    """
    Handle invoice.created event.
    Logs the creation of a new invoice.
    """
    invoice = event['data']['object']
    current_app.logger.info("Processing invoice.created event: %s", invoice.get('id'))
    current_app.logger.debug("Invoice details: %s", invoice)

    customer_id = invoice.get('customer')
    user = get_user_by_stripe_customer_id(customer_id)
    if user:
        log_billing_event(
            user=user,
            event_type="invoice_created",
            event_data={
                "invoice_id": invoice.get('id'),
                "amount_due": invoice.get('amount_due'),
                "billing_reason": invoice.get('billing_reason'),
                "subscription": invoice.get('subscription')
            }
        )


def handle_payment_intent_created(event: Dict[str, Any]) -> None:
    """
    Handle payment_intent.created event.
    Logs the creation of a new payment intent.
    """
    payment_intent = event['data']['object']
    current_app.logger.info("Processing payment_intent.created event: %s", payment_intent.get('id'))
    current_app.logger.debug("Payment intent details: %s", payment_intent)

    customer_id = payment_intent.get('customer')
    user = get_user_by_stripe_customer_id(customer_id)
    if user:
        log_billing_event(
            user=user,
            event_type="payment_intent_created",
            event_data={
                "payment_intent_id": payment_intent.get('id'),
                "amount": payment_intent.get('amount'),
                "currency": payment_intent.get('currency'),
                "status": payment_intent.get('status')
            }
        )


def handle_payment_intent_failed(event: Dict[str, Any]) -> None:
    """
    Handle payment_intent.payment_failed event.
    Note: Stripe already sends an email notification for payment failures.
    We'll just update the user's status and log the event.
    """
    payment_intent = event['data']['object']
    current_app.logger.info("Processing payment_intent.payment_failed event: %s", payment_intent.get('id'))

    customer_id = payment_intent.get('customer')
    user = get_user_by_stripe_customer_id(customer_id)
    if user:
        # Log the failure
        log_billing_event(
            user=user,
            event_type="payment_intent_failed",
            event_data={
                "payment_intent_id": payment_intent.get('id'),
                "amount": payment_intent.get('amount'),
                "currency": payment_intent.get('currency'),
                "last_payment_error": payment_intent.get('last_payment_error'),
                "status": payment_intent.get('status')
            }
        )

        # Update user status if needed
        if user.pro_end_date and user.pro_end_date <= datetime.utcnow():
            user.pro_end_date = None
            user.trial_end = None
            db.session.commit()
            current_app.logger.info("Updated user pro status to False due to payment failure: %s", user.email)
        
        # Send admin notification for payment failures
        try:
            send_admin_notification(
                subject="💳 Payment Intent Failed",
                template="email/admin_payment_notification",
                payment_intent_id=payment_intent.get('id'),
                user_email=user.email,
                user_name=user.first_name or user.email,
                event_type="payment_intent_failed",
                amount=payment_intent.get('amount'),
                currency=payment_intent.get('currency'),
                error_message=payment_intent.get('last_payment_error', {}).get('message'),
                config=current_app.config
            )
            current_app.logger.info("Sent admin notification for payment intent failed")
        except Exception as e:
            current_app.logger.error("Failed to send admin notification: %s", e)


def handle_charge_failed(event: Dict[str, Any]) -> None:
    """
    Handle charge.failed event.
    Note: Stripe already sends an email notification for charge failures.
    We'll just update the user's status and log the event.
    """
    charge = event['data']['object']
    current_app.logger.info("Processing charge.failed event: %s", charge.get('id'))

    customer_id = charge.get('customer')
    user = get_user_by_stripe_customer_id(customer_id)
    if user:
        # Log the failure
        log_billing_event(
            user=user,
            event_type="charge_failed",
            event_data={
                "charge_id": charge.get('id'),
                "amount": charge.get('amount'),
                "currency": charge.get('currency'),
                "failure_message": charge.get('failure_message'),
                "failure_code": charge.get('failure_code')
            }
        )

        # Update user status if needed
        if user.pro_end_date and user.pro_end_date <= datetime.utcnow():
            user.pro_end_date = None
            user.trial_end = None
            db.session.commit()
            current_app.logger.info("Updated user pro status to False due to charge failure: %s", user.email)
        # No need to send email as Stripe handles this


def handle_invoice_updated(event: Dict[str, Any]) -> None:
    """
    Handle invoice.updated event.
    Logs updates to invoices and handles status changes.
    """
    invoice = event['data']['object']
    current_app.logger.info("Processing invoice.updated event: %s", invoice.get('id'))
    current_app.logger.debug("Invoice details: %s", invoice)

    customer_id = invoice.get('customer')
    user = get_user_by_stripe_customer_id(customer_id)
    if user:
        # Log the update
        log_billing_event(
            user=user,
            event_type="invoice_updated",
            event_data={
                "invoice_id": invoice.get('id'),
                "status": invoice.get('status'),
                "amount_due": invoice.get('amount_due'),
                "attempt_count": invoice.get('attempt_count'),
                "next_payment_attempt": invoice.get('next_payment_attempt')
            }
        )


def handle_trial_will_end(event: Dict[str, Any]) -> None:
    """
    Handle customer.subscription.trial_will_end event.
    Note: Stripe already sends an email notification 7 days before trial ends.
    We'll just log this event for tracking purposes.
    """
    subscription = event['data']['object']
    current_app.logger.info("Processing trial_will_end event for subscription: %s", subscription.get('id'))

    customer_id = subscription.get('customer')
    user = get_user_by_stripe_customer_id(customer_id)
    if user:
        # Log the event
        log_billing_event(
            user=user,
            event_type="trial_will_end",
            event_data={
                "subscription_id": subscription.get('id'),
                "trial_end": subscription.get('trial_end'),
                "current_period_end": subscription.get('current_period_end')
            }
        )
        # No need to send email as Stripe handles this


def handle_payment_intent_succeeded(event):
    """Handle successful payment intent."""
    try:
        payment_intent = event.data.object
        current_app.logger.info(f"Payment intent succeeded: {payment_intent.id}")
        current_app.logger.info(f"Amount: {payment_intent.amount / 100} {payment_intent.currency}")
        current_app.logger.info(f"Customer: {payment_intent.customer}")
        return jsonify({'status': 'success'}), 200
    except Exception as e:
        current_app.logger.error(f"Error processing payment_intent.succeeded: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500


def handle_charge_succeeded(event):
    """Handle successful charge."""
    try:
        charge = event.data.object
        current_app.logger.info(f"Charge succeeded: {charge.id}")
        current_app.logger.info(f"Amount: {charge.amount / 100} {charge.currency}")
        current_app.logger.info(f"Customer: {charge.customer}")
        return jsonify({'status': 'success'}), 200
    except Exception as e:
        current_app.logger.error(f"Error processing charge.succeeded: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500


def handle_charge_refunded(event):
    """Handle charge refund."""
    try:
        charge = event.data.object
        current_app.logger.info(f"Charge refunded: {charge.id}")
        current_app.logger.info(f"Amount: {charge.amount / 100} {charge.currency}")
        current_app.logger.info(f"Customer: {charge.customer}")
        current_app.logger.info(f"Refund amount: {charge.amount_refunded / 100}")
        return jsonify({'status': 'success'}), 200
    except Exception as e:
        current_app.logger.error(f"Error processing charge.refunded: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500


def handle_charge_dispute_created(event):
    """Handle charge dispute creation."""
    try:
        dispute = event.data.object
        current_app.logger.info(f"Dispute created: {dispute.id}")
        current_app.logger.info(f"Amount: {dispute.amount / 100} {dispute.currency}")
        current_app.logger.info(f"Reason: {dispute.reason}")
        current_app.logger.info(f"Status: {dispute.status}")
        
        # Get user info for admin notification
        customer_id = dispute.customer
        user = get_user_by_stripe_customer_id(customer_id)
        
        # Log the dispute
        if user:
            log_billing_event(
                user=user,
                event_type="charge_dispute_created",
                event_data={
                    "dispute_id": dispute.id,
                    "charge_id": dispute.charge,
                    "amount": dispute.amount,
                    "currency": dispute.currency,
                    "reason": dispute.reason,
                    "status": dispute.status
                }
            )
            
            # Send admin notification for charge disputes (very important!)
            try:
                send_admin_notification(
                    subject="🚨 CHARGEBACK ALERT - Immediate Action Required",
                    template="email/admin_dispute_notification",
                    dispute_id=dispute.id,
                    charge_id=dispute.charge,
                    user_email=user.email,
                    user_name=user.first_name or user.email,
                    event_type="charge_dispute_created",
                    amount=dispute.amount,
                    currency=dispute.currency,
                    reason=dispute.reason,
                    status=dispute.status,
                    config=current_app.config
                )
                current_app.logger.info("Sent admin notification for charge dispute")
            except Exception as e:
                current_app.logger.error("Failed to send admin notification: %s", e)
        
        return jsonify({'status': 'success'}), 200
    except Exception as e:
        current_app.logger.error(f"Error processing charge.dispute.created: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500


def handle_customer_source_expiring(event):
    """Handle expiring payment method."""
    try:
        source = event.data.object
        current_app.logger.info(f"Payment method expiring: {source.id}")
        current_app.logger.info(f"Customer: {source.customer}")
        current_app.logger.info(f"Expiry: {source.exp_month}/{source.exp_year}")
        
        # Get user info for admin notification
        customer_id = source.customer
        user = get_user_by_stripe_customer_id(customer_id)
        
        # Log the expiring payment method
        if user:
            log_billing_event(
                user=user,
                event_type="payment_method_expiring",
                event_data={
                    "source_id": source.id,
                    "exp_month": source.exp_month,
                    "exp_year": source.exp_year,
                    "card_type": getattr(source, 'brand', 'unknown')
                }
            )
            
            # Send admin notification for expiring payment methods
            try:
                send_admin_notification(
                    subject="⚠️ Payment Method Expiring Soon",
                    template="email/admin_payment_method_notification",
                    source_id=source.id,
                    user_email=user.email,
                    user_name=user.first_name or user.email,
                    event_type="payment_method_expiring",
                    exp_month=source.exp_month,
                    exp_year=source.exp_year,
                    card_type=getattr(source, 'brand', 'unknown'),
                    config=current_app.config
                )
                current_app.logger.info("Sent admin notification for expiring payment method")
            except Exception as e:
                current_app.logger.error("Failed to send admin notification: %s", e)
        
        return jsonify({'status': 'success'}), 200
    except Exception as e:
        current_app.logger.error(f"Error processing customer.source.expiring: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500


def handle_customer_source_updated(event):
    """Handle payment method update."""
    try:
        source = event.data.object
        current_app.logger.info(f"Payment method updated: {source.id}")
        current_app.logger.info(f"Customer: {source.customer}")
        current_app.logger.info(f"Type: {source.type}")
        return jsonify({'status': 'success'}), 200
    except Exception as e:
        current_app.logger.error(f"Error processing customer.source.updated: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500


def handle_invoice_finalized(event):
    """Handle invoice finalization."""
    try:
        invoice = event.data.object
        current_app.logger.info(f"Invoice finalized: {invoice.id}")
        current_app.logger.info(f"Amount: {invoice.amount_due / 100} {invoice.currency}")
        current_app.logger.info(f"Customer: {invoice.customer}")
        current_app.logger.info(f"Status: {invoice.status}")
        return jsonify({'status': 'success'}), 200
    except Exception as e:
        current_app.logger.error(f"Error processing invoice.finalized: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500


def handle_invoice_paid(event):
    """Handle paid invoice."""
    try:
        invoice = event.data.object
        current_app.logger.info(f"Invoice paid: {invoice.id}")
        current_app.logger.info(f"Amount: {invoice.amount_paid / 100} {invoice.currency}")
        current_app.logger.info(f"Customer: {invoice.customer}")
        current_app.logger.info(f"Payment intent: {invoice.payment_intent}")
        return jsonify({'status': 'success'}), 200
    except Exception as e:
        current_app.logger.error(f"Error processing invoice.paid: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500
