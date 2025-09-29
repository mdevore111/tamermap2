# app/routes/auth.py

from flask import Blueprint, redirect, request, current_app, render_template, url_for, flash, session
from flask_login import login_required, current_user, logout_user
from flask_security import utils
from flask_security.utils import send_mail
from datetime import datetime
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

from ..extensions import db
from ..models import User, StripeSession, LoginEvent
from app.payment.stripe_utils import create_customer_portal_session
from app.auth.forms import ResetPasswordForm  # Import the ResetPasswordForm

# Create a blueprint for authentication-related routes
auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/account")
@login_required
def account():
    """
    Render the account page for the logged-in user.
    """
    from flask import session
    from flask_login import current_user
    
    # Only log if there's an actual issue (not every successful access)
    if not current_user.is_authenticated:
        current_app.logger.warning(f"Unauthenticated user attempting to access account page from IP {request.remote_addr}")
    
    # Get user roles and determine pro status
    user_roles = [role.name for role in current_user.roles]
    is_pro = current_user.has_role('Pro')
    
    return render_template("account.html", 
                         user_roles=user_roles, 
                         is_pro=is_pro, 
                         pro_end_date=current_user.pro_end_date)


@auth_bp.route('/customer-portal', methods=['GET'])
@login_required
def customer_portal():
    """
    Redirect the user to the Stripe customer portal.

    Retrieves the Stripe customer ID from the current user, creates a portal session,
    and then redirects the user to that session.
    """
    customer_id = current_user.stripe_customer_id
    return_url = request.args.get('return_url', current_app.config.get('DEFAULT_RETURN_URL'))
    portal_url = create_customer_portal_session(customer_id, return_url)
    return redirect(portal_url)


@auth_bp.route('/update_profile', methods=['POST'])
@login_required
def update_profile():
    """
    Update the current user's profile information.

    Retrieves form data for first name, last name, email, region, and language.
    Updates the user record and commits the changes to the database.
    A success message is flashed upon completion.
    """
    first_name = request.form.get('first_name')
    last_name = request.form.get('last_name')
    email = request.form.get('email')
    region = request.form.get('region')
    language = request.form.get('language')

    if first_name is not None:
        current_user.first_name = first_name
    if last_name is not None:
        current_user.last_name = last_name
    if region is not None:
        current_user.region = region
    if language is not None:
        current_user.language = language

    # Email change: send verification email if changed
    if email is not None and email != current_user.email:
        # Generate token
        s = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
        token = s.dumps({'user_id': current_user.id, 'new_email': email}, salt='email-change')
        # Build confirmation URL
        confirm_url = url_for('auth.confirm_email_change', token=token, _external=True)
        # Send email to new address
        subject = "Confirm your new email address"
        send_mail(subject, email, template="confirm_new_email", confirm_url=confirm_url, new_email=email)
        # Log the email change request
        current_app.logger.info(f"User {current_user.id} ({current_user.email}) requested email change to {email} from IP {request.remote_addr}")
        flash("A verification email has been sent to your new address. Please check your inbox to confirm the change.", "info")
        db.session.commit()
        return redirect(url_for('auth.account'))

    db.session.commit()
    flash("Your profile has been updated successfully!", "success")
    return redirect(url_for('auth.account'))


@auth_bp.route('/confirm_email_change/<token>')
def confirm_email_change(token):
    s = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    try:
        data = s.loads(token, salt='email-change', max_age=3600*24)  # 24 hours
        user_id = data['user_id']
        new_email = data['new_email']
    except (BadSignature, SignatureExpired):
        flash('The confirmation link is invalid or has expired.', 'danger')
        return redirect(url_for('auth.account'))
    user = User.query.get(user_id)
    if not user:
        flash('User not found.', 'danger')
        return redirect(url_for('auth.account'))
    old_email = user.email
    user.email = new_email
    db.session.commit()
    # Optionally notify old email
    if old_email:
        notify_subject = 'Your email was changed'
        send_mail(notify_subject, old_email, template="email_changed_notification", old_email=old_email, new_email=new_email)
    # Log the email change confirmation
    current_app.logger.info(f"User {user.id} confirmed email change: {old_email} → {new_email} from IP {request.remote_addr}")
    flash('Your email address has been updated!', 'success')
    return redirect(url_for('auth.account'))


@auth_bp.route('/set-password/<token>', methods=['GET', 'POST'])
def set_password(token):
    """
    Handle the initial password setup for users created via Stripe.

    Validates the provided token and, on GET requests, renders the password setup form.
    On POST, it validates the form submission, hashes the new password,
    and updates the user's password in the database.

    Args:
        token (str): The initial password setup token.

    Returns:
        A redirect to the login page upon successful password update, or re-renders
        the form with errors if validation fails.
    """
    user = User.verify_initial_password_token(token)
    if user is None:
        flash('That is an invalid or expired token', 'danger')
        return redirect(url_for('security.forgot_password'))

    form = ResetPasswordForm()
    if form.validate_on_submit():
        # Hash and update the user's password after successful form validation.
        new_password = form.password.data
        user.password = utils.hash_password(new_password)
        db.session.commit()
        flash('Your password has been set!', 'success')
        return redirect(url_for('security.login'))

    return render_template('security/set_password.html', token=token, form=form)


@auth_bp.route('/initiate_password_setup', methods=['GET'])
def initiate_password_setup():
    """
    Initiate the password setup process.

    Retrieves the session ID from the request, verifies it against stored Stripe sessions,
    and redirects the user to the set_password endpoint with the corresponding token.
    If the session ID is missing or invalid, an error message is flashed and the user
    is redirected to the public learning page.
    """
    session_id = request.args.get('session_id')
    if not session_id:
        flash("Session ID missing.", "error")
        return redirect(url_for('public.learn'))

    stripe_session = StripeSession.query.filter_by(session_id=session_id).first()
    if not stripe_session:
        flash("Invalid or expired session. Please try again.", "error")
        return redirect(url_for('public.learn'))

    token = stripe_session.initial_password_token
    current_app.logger.info("Redirecting to set_password with token: %s", token)
    return redirect(url_for('auth.set_password', token=token))


@auth_bp.route('/logout-manual', methods=['GET', 'POST'])
def manual_logout():
    """
    Manual logout route that explicitly clears session and redirects.

    This bypasses Flask-Security's logout mechanism which may not be
    properly clearing the Flask-Session data.
    """
    current_app.logger.info(f"LOGOUT: Starting manual logout for user: {current_user.email if current_user.is_authenticated else 'Not authenticated'}")

    # Clear Flask-Login user
    logout_user()
    current_app.logger.info("LOGOUT: Called logout_user()")

    # Clear the entire session
    session.clear()
    current_app.logger.info(f"LOGOUT: Cleared session, keys before: {list(session.keys())}")

    # Force session to be marked as modified and saved
    session.modified = True
    current_app.logger.info("LOGOUT: Marked session as modified")

    # Delete the session cookie
    response = redirect(url_for('public.home'))
    response.delete_cookie('tamermap_session')
    current_app.logger.info("LOGOUT: Deleted session cookie")

    # Flash a message
    flash('You have been logged out successfully.', 'info')
    current_app.logger.info("LOGOUT: Redirecting to home page")

    return response
