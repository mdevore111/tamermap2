import stripe
from flask import jsonify, url_for, Blueprint, current_app, request
from flask_security import login_required

from app.models import User

# Create a blueprint for payment routes, with URL prefix '/payment'
payment_bp = Blueprint('payment', __name__, url_prefix='/payment')


@payment_bp.route('/create-checkout-session', methods=['POST'])
def create_checkout_session():
    """
    Create a Stripe Checkout session for a Pro subscription.

    This endpoint checks if a user already exists by email or cust_id.
    If an existing user is found, the trial period is skipped; otherwise, a 7-day trial is applied.
    """
    try:
        data = request.get_json() or {}
        email = data.get("email")
        cust_id = data.get("cust_id")

        existing_user = None
        if email:
            existing_user = User.query.filter_by(email=email).first()
        if not existing_user and cust_id:
            existing_user = User.query.filter_by(cust_id=cust_id).first()

        trial_days = 7 if existing_user is None else 0

        stripe.api_key = current_app.config.get("STRIPE_SECRET_KEY")

        # Get price ID from configuration (environment-specific)
        price_id = current_app.config.get("STRIPE_PRO_MONTHLY_PRICE_ID")
        if not price_id:
            current_app.logger.error("STRIPE_PRO_MONTHLY_PRICE_ID not configured")
            return jsonify(error="Payment configuration error"), 500

        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            mode='subscription',
            line_items=[{
                'price': price_id,
                'quantity': 1,
            }],
            custom_fields=[
                {
                    "key": "full_name",
                    "label": {"type": "custom", "custom": "Full Name (if different from billing)"},
                    "type": "text",
                    "optional": True,
                }
            ],
            subscription_data={
                "trial_period_days": trial_days,
                "metadata": {"full_name": ""}
            },
            metadata={"full_name": ""},
            success_url=url_for('auth.initiate_password_setup', _external=True) + '?session_id={CHECKOUT_SESSION_ID}',
            cancel_url=url_for('public.cancel', _external=True)
        )
        return jsonify(id=session.id)

    except Exception as e:
        current_app.logger.error("Error creating checkout session: %s", e)
        return jsonify(error=str(e)), 400
