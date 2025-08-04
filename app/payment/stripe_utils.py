import stripe
from flask import current_app


def create_customer_portal_session(customer_id, return_url):
    stripe.api_key = current_app.config.get("STRIPE_SECRET_KEY")
    session = stripe.billing_portal.Session.create(
        customer=customer_id,
        return_url=return_url,
    )
    return session.url
