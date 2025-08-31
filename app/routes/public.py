# app/routes/public.py
import stripe
from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app, jsonify
from flask import session
from flask_login import current_user
from datetime import datetime
from sqlalchemy import func

from ..extensions import db, limiter
from ..models import Message, Retailer, Event, VisitorLog
from app.communication_forms import MessageForm
from app.routes.security import check_referrer
from app.custom_email import send_email_with_context

# Create a blueprint for public (unprotected) routes
public_bp = Blueprint("public", __name__)


@public_bp.route("/")
def splash():  # Or rename to 'index' for clarity
    google_api_key = current_app.config.get("GOOGLE_API_KEY")
    return render_template("maps.html", google_api_key=google_api_key)


@public_bp.route("/maps")
def maps():
    """Redirect /maps to root for SEO consolidation."""
    return redirect(url_for("public.splash"), code=301)


@public_bp.route("/learn")
def learn():
    """
    Render the learn page, which contains educational or informational content.

    Returns:
        str: Rendered HTML for the learn page.
    """
    stripe_public_key = current_app.config.get('STRIPE_PUBLISHABLE_KEY')
    return render_template("learn.html", stripe_public_key=stripe_public_key)


@public_bp.route("/states")
def states_index():
    """
    States index page showing all available state pages.
    BLOCKED: This route is for search engines only, not user access.
    
    Returns:
        str: 404 error for users, XML for search engines
    """
    # Block user access - this is for search engines only
    user_agent = request.headers.get('User-Agent', '').lower()
    if not any(bot in user_agent for bot in ['bot', 'crawler', 'spider', 'googlebot', 'bingbot']):
        return "Page not found", 404
    
    # Define all available states with their metadata
    states = [
        {
            'name': 'Washington',
            'slug': 'washington',
            'description': 'Pacific Northwest Pokemon card hunting paradise',
            'icon': 'fas fa-mountain'
        },
        {
            'name': 'California',
            'slug': 'california',
            'description': 'Golden State with diverse card hunting opportunities',
            'icon': 'fas fa-sun'
        },
        {
            'name': 'Texas',
            'slug': 'texas',
            'description': 'Lone Star State with wide coverage',
            'icon': 'fas fa-star'
        },
        {
            'name': 'Florida',
            'slug': 'florida',
            'description': 'Sunshine State card hunting destinations',
            'icon': 'fas fa-umbrella-beach'
        },
        {
            'name': 'New York',
            'slug': 'new-york',
            'description': 'Empire State with urban and suburban locations',
            'icon': 'fas fa-city'
        },
        {
            'name': 'Illinois',
            'slug': 'illinois',
            'description': 'Prairie State with Chicago area coverage',
            'icon': 'fas fa-building'
        },
        {
            'name': 'Pennsylvania',
            'slug': 'pennsylvania',
            'description': 'Keystone State card hunting spots',
            'icon': 'fas fa-key'
        },
        {
            'name': 'Ohio',
            'slug': 'ohio',
            'description': 'Buckeye State with diverse locations',
            'icon': 'fas fa-leaf'
        },
        {
            'name': 'Michigan',
            'slug': 'michigan',
            'description': 'Great Lakes State card hunting',
            'icon': 'fas fa-water'
        },
        {
            'name': 'Georgia',
            'slug': 'georgia',
            'description': 'Peach State with growing coverage',
            'icon': 'fas fa-tree'
        }
    ]
    
    # Return XML for search engines instead of HTML template
    from flask import make_response
    xml_content = f'''<?xml version="1.0" encoding="UTF-8"?>
<states xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
    <title>Pokemon Card Kiosks by State</title>
    <description>Find Pokemon card kiosks across the United States</description>
    <total_states>{len(states)}</total_states>
    <states_list>
'''
    
    for state in states:
        xml_content += f'''        <state>
            <name>{state['name']}</name>
            <slug>{state['slug']}</slug>
            <description>{state['description']}</description>
            <url>{request.url_root.rstrip('/')}/state/{state['slug']}</url>
        </state>
'''
    
    xml_content += '''    </states_list>
</states>'''
    
    response = make_response(xml_content)
    response.headers['Content-Type'] = 'application/xml'
    return response


@public_bp.route("/state/<state_name>")
def state_page(state_name):
    """
    Dynamic state page showing all KIOSKS ONLY in a specific state organized by city.
    BLOCKED: This route is for search engines only, not user access.
    
    Args:
        state_name (str): The state name (e.g., 'washington', 'california')
    
    Returns:
        str: 404 error for users, XML for search engines
    """
    # Block user access - this is for search engines only
    user_agent = request.headers.get('User-Agent', '').lower()
    if not any(bot in user_agent for bot in ['bot', 'crawler', 'spider', 'googlebot', 'bingbot']):
        return "Page not found", 404
    
    # Normalize state name for database query
    state_name_normalized = state_name.title()
    
    # Handle common state name variations
    state_variations = {
        'washington': ['Washington', 'WA', 'Wash'],
        'california': ['California', 'CA', 'Calif'],
        'texas': ['Texas', 'TX', 'Tex'],
        'florida': ['Florida', 'FL', 'Fla'],
        'new-york': ['New York', 'NY', 'New York State'],
        'illinois': ['Illinois', 'IL', 'Ill'],
        'pennsylvania': ['Pennsylvania', 'PA', 'Penn'],
        'ohio': ['Ohio', 'OH'],
        'michigan': ['Michigan', 'MI', 'Mich'],
        'georgia': ['Georgia', 'GA']
    }
    
    # Get state variations for search
    search_terms = state_variations.get(state_name.lower(), [state_name_normalized])
    
    # Build query for KIOSKS ONLY (retailer_type = 'kiosk') with multiple state name variations
    query = db.session.query(Retailer).filter(
        Retailer.enabled == True,
        Retailer.retailer_type.ilike('kiosk')  # ONLY kiosks (case-insensitive)
    )
    
    # Use OR conditions for multiple state name variations
    from sqlalchemy import or_
    state_filters = []
    for term in search_terms:
        state_filters.append(Retailer.full_address.ilike(f'%{term}%'))
    
    retailers = query.filter(or_(*state_filters)).all()
    
    # Group retailers by city with better address parsing
    cities = {}
    for retailer in retailers:
        # Extract city from address (assuming format: "Street, City, State ZIP")
        address_parts = retailer.full_address.split(',')
        if len(address_parts) >= 2:
            city = address_parts[1].strip()
            # Clean up city name (remove extra spaces, etc.)
            city = ' '.join(city.split())
            if city and city not in cities:
                cities[city] = []
            if city:
                cities[city].append(retailer)
    
    # Sort cities alphabetically
    sorted_cities = dict(sorted(cities.items()))
    
    # Return XML for search engines instead of HTML template
    from flask import make_response
    xml_content = f'''<?xml version="1.0" encoding="UTF-8"?>
<state_kiosks xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
    <state_name>{state_name_normalized}</state_name>
    <total_kiosks>{len(retailers)}</total_kiosks>
    <total_cities>{len(sorted_cities)}</total_cities>
    <cities>
'''
    
    for city, city_retailers in sorted_cities.items():
        xml_content += f'''        <city>
            <name>{city}</name>
            <kiosk_count>{len(city_retailers)}</kiosk_count>
            <kiosks>
'''
        for retailer in city_retailers:
            xml_content += f'''                <kiosk>
                    <name>{retailer.retailer}</name>
                    <address>{retailer.full_address}</address>
                    <phone>{retailer.phone_number or 'N/A'}</phone>
                    <website>{retailer.website or 'N/A'}</website>
                    <machine_count>{retailer.machine_count}</machine_count>
                    <hours>{retailer.opening_hours or 'N/A'}</hours>
                    <coordinates>
                        <latitude>{retailer.latitude or 'N/A'}</latitude>
                        <longitude>{retailer.longitude or 'N/A'}</longitude>
                    </coordinates>
                </kiosk>
'''
        xml_content += '''            </kiosks>
        </city>
'''
    
    xml_content += '''    </cities>
</state_kiosks>'''
    
    response = make_response(xml_content)
    response.headers['Content-Type'] = 'application/xml'
    return response





@public_bp.route("/message", methods=["GET", "POST"])
# @limiter.limit("5 per minute")  # Rate limit message submissions (DISABLED - Cloudflare handles this)
def send_message():
    """
    Display and process the message form.

    - On GET: Displays the message form.
    - On POST: Validates and processes the submitted form data to create a new message.
      If the form includes a communication type (e.g., suggestion, contact, support, or report),
      it pre-populates the form accordingly. Additional context (like the reported address)
      is appended to the message body if provided.

    If the user is authenticated, their name and user ID are captured.
    Otherwise, "Anonymous" is used and no sender ID is recorded.

    Returns:
        str or Response: Rendered message form template on GET,
        or a redirect response on successful POST.
    """
    form = MessageForm()

    # only override on GET when link provides type & metadata
    if request.method == "GET":
        pre = request.args.get("type", "")
        form.communication_type.data = (
            pre if pre in ["suggestion", "contact", "report", "support", "business"] else "contact"
        )
        if form.communication_type.data == "report":
            addr = request.args.get("address", "")
            form.subject.data = addr
            form.reported_address.data = addr
            form.reported_phone.data = request.args.get("phone", "")
            form.reported_website.data = request.args.get("website", "")
            form.reported_hours.data = request.args.get("hours", "")

    if form.validate_on_submit():
        # Additional SPAM protection checks
        client_ip = request.remote_addr
        
        # Check for suspicious patterns in the message
        body_text = form.body.data.lower()
        subject_text = form.subject.data.lower() if form.subject.data else ""
        
        # Check for excessive punctuation
        if body_text.count('!') > 5 or body_text.count('?') > 5:
            current_app.logger.warning(f"Potential spam from IP {client_ip}: excessive punctuation")
            flash("Message contains too much punctuation.", "danger")
            return render_template("message_form.html", form=form)
        
        # Check for suspicious keywords in subject or body
        spam_keywords = ['urgent', 'act now', 'limited time', 'free money', 'make money fast', 'work from home', 'earn cash']
        for keyword in spam_keywords:
            if keyword in body_text or keyword in subject_text:
                current_app.logger.warning(f"Potential spam from IP {client_ip}: keyword '{keyword}' detected")
                flash("Message contains inappropriate content.", "danger")
                return render_template("message_form.html", form=form)
        
        # Check for suspicious user agent
        user_agent = request.headers.get('User-Agent', '').lower()
        if 'bot' in user_agent or 'crawler' in user_agent or 'spider' in user_agent:
            current_app.logger.warning(f"Bot detected from IP {client_ip}: {user_agent}")
            flash("Automated submissions are not allowed.", "danger")
            return render_template("message_form.html", form=form)
        
        # Get sender info
        if current_user.is_authenticated:
            user_name = (
                f"{current_user.first_name} {current_user.last_name}".strip()
                if current_user.first_name or current_user.last_name
                else current_user.email or "User"
            )
            sender_id = current_user.id
        else:
            user_name = "Anonymous"
            sender_id = None

        # Category-specific metadata
        extra_lines = [f"Reported by {user_name}:"]
        if form.communication_type.data == 'support':
            if form.support_topic.data:
                extra_lines.append(f"Support Topic: {form.support_topic.data}")
            if form.order_number.data:
                extra_lines.append(f"Order Number: {form.order_number.data}")
        if form.communication_type.data == 'business':
            if form.company_name.data:
                extra_lines.append(f"Company: {form.company_name.data}")
            if form.company_website.data:
                extra_lines.append(f"Website: {form.company_website.data}")
            if form.company_size.data:
                extra_lines.append(f"Company Size: {form.company_size.data}")
        extra = "\n".join(extra_lines) + "\n"

        try:
            msg_record = Message(
                sender_id=sender_id,
                recipient_id=None,
                communication_type=form.communication_type.data,
                subject=form.subject.data,
                body=extra + form.body.data,
                reported_address=form.reported_address.data,
                reported_phone=form.reported_phone.data,
                reported_website=form.reported_website.data,
                reported_hours=form.reported_hours.data,
                out_of_business=form.out_of_business.data,
                name=form.name.data,
                address=form.address.data
            )
            db.session.add(msg_record)
            db.session.commit()

            # Send admin notification email
            send_email_with_context(
                subject="New Communication Form Submission",
                template="email/admin_message_notification",
                recipient=current_app.config.get('ADMIN_EMAIL', 'mark@markdevore.com'),
                communication_type=form.communication_type.data,
                name=form.name.data,
                address=form.address.data,
                form_subject=form.subject.data,
                body=form.body.data,
                reported_address=form.reported_address.data,
                reported_phone=form.reported_phone.data,
                reported_website=form.reported_website.data,
                reported_hours=form.reported_hours.data,
                out_of_business=form.out_of_business.data,
                config=current_app.config
            )

            # Log successful submission for monitoring
            current_app.logger.info(f"Message submitted successfully from IP {client_ip} by {user_name}")
            
            flash("Your message has been sent.", "success")
            return redirect(url_for("public.maps"))
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Failed to save message: {e}")
            flash("An error occurred while sending your message.", "danger")

    # Render the message form template (on GET or if form submission fails)
    return render_template("message_form.html", form=form)


@public_bp.route("/terms")
def terms():
    """
    Render the 'terms' page.

    Returns:
        str: Rendered HTML for the 'terms' page.
    """
    return render_template("terms.html")


@public_bp.route("/privacy")
def privacy():
    """
    Render the 'privacy' page.

    Returns:
        str: Rendered HTML for the 'privacy' page.
    """
    return render_template("privacy.html")


@public_bp.route("/about")
def about():
    """
    Render the 'about' page.

    Returns:
        str: Rendered HTML for the 'about' page.
    """
    return render_template("about.html")


@public_bp.route("/sitemap")
def sitemap():
    """
    Render the 'sitemap' page.

    Returns:
        str: Rendered HTML for the 'sitemap' page.
    """
    return render_template("sitemap.html")


@public_bp.route("/how-to")
def how_to():
    """Render the how-to guides page."""
    return render_template("how-to.html")


@public_bp.route("/card-hunting-tips")
def card_hunting_tips():
    """Render the advanced card hunting tips page."""
    return render_template("card-hunting-tips.html")


@public_bp.route("/sitemap.xml")
def sitemap_xml():
    """Generate dynamic XML sitemap for search engines."""
    from flask import make_response
    from datetime import datetime
    
    # Get current date
    now = datetime.utcnow().strftime('%Y-%m-%d')
    
    # Base URL
    base_url = request.url_root.rstrip('/')
    
    # Static pages with their priorities and change frequencies
    pages = [
        {'url': '/', 'priority': '1.0', 'changefreq': 'daily'},
        {'url': '/maps', 'priority': '0.9', 'changefreq': 'daily'},
        {'url': '/learn', 'priority': '0.8', 'changefreq': 'weekly'},
        {'url': '/how-to', 'priority': '0.8', 'changefreq': 'weekly'},
        {'url': '/card-hunting-tips', 'priority': '0.8', 'changefreq': 'weekly'},
        {'url': '/states', 'priority': '0.8', 'changefreq': 'weekly'},
        {'url': '/about', 'priority': '0.7', 'changefreq': 'monthly'},
        {'url': '/sitemap', 'priority': '0.5', 'changefreq': 'monthly'},
    ]
    
    # Add state pages for major states with Pokemon card KIOSKS ONLY
    # These will be dynamically generated XML pages showing kiosks by city (search engines only)
    state_pages = [
        {'url': '/state/washington', 'priority': '0.8', 'changefreq': 'weekly'},
        {'url': '/state/california', 'priority': '0.8', 'changefreq': 'weekly'},
        {'url': '/state/texas', 'priority': '0.8', 'changefreq': 'weekly'},
        {'url': '/state/florida', 'priority': '0.8', 'changefreq': 'weekly'},
        {'url': '/state/new-york', 'priority': '0.8', 'changefreq': 'weekly'},
        {'url': '/state/illinois', 'priority': '0.8', 'changefreq': 'weekly'},
        {'url': '/state/pennsylvania', 'priority': '0.8', 'changefreq': 'weekly'},
        {'url': '/state/ohio', 'priority': '0.8', 'changefreq': 'weekly'},
        {'url': '/state/michigan', 'priority': '0.8', 'changefreq': 'weekly'},
        {'url': '/state/georgia', 'priority': '0.8', 'changefreq': 'weekly'},
    ]
    
    # Combine all pages
    all_pages = pages + state_pages
    
    # Generate XML sitemap
    xml_content = f'''<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
'''
    
    for page in all_pages:
        xml_content += f'''  <url>
    <loc>{base_url}{page['url']}</loc>
    <lastmod>{now}</lastmod>
    <changefreq>{page['changefreq']}</changefreq>
    <priority>{page['priority']}</priority>
  </url>
'''
    
    xml_content += '</urlset>'
    
    # Create response with proper headers
    response = make_response(xml_content)
    response.headers['Content-Type'] = 'application/xml'
    return response


@public_bp.route('/success')
def success():
    """
    After a successful Checkout session, retrieve the session details,
    extract the custom 'full_name' field (if provided), and update the subscription metadata.
    """
    session_id = request.args.get('session_id')
    if not session_id:
        flash("No session ID provided.", "error")
        return redirect(url_for("auth.account"))

    try:
        # Retrieve the Checkout Session and expand the subscription object.
        session = stripe.checkout.Session.retrieve(
            session_id,
            expand=["subscription"]
        )

        # Extract the custom fields (ensure it's a list).
        custom_fields = session.get("custom_fields") or []
        full_name = None
        for field in custom_fields:
            if field.get('key') == 'full_name':
                value = field.get('text', {}).get('value', '').strip()
                if value:
                    optional_full_name = value
                break

        if full_name:
            # Update subscription metadata with the full name.
            subscription_id = session.subscription.id
            stripe.Subscription.modify(
                subscription_id,
                metadata={"full_name": full_name}
            )
            flash("Your subscription has been updated with your full name.", "success")
        else:
            flash("No custom full name provided; using billing name.", "info")
    except Exception as e:
        # Log and flash an error message if something goes wrong.
        current_app.logger.error("Error updating subscription metadata: %s", e)
        flash("There was an error updating your subscription details.", "error")

    # Continue with redirecting the user to their account page.
    return redirect(url_for("auth.account"))


@public_bp.route('/cancel')
def cancel():
    """
    Handle a canceled checkout session.

    This route flashes a cancellation message and redirects the user back to the account page.

    Returns:
        A redirect response to the account page.
    """
    current_app.logger.info("Checkout session canceled by user.")
    flash("Payment was canceled. You can try again if you like.", "warning")
    return redirect(url_for("auth.account"))


@public_bp.route("/test-cache")
def test_cache():
    """
    Render the test-cache page for testing the caching functionality.
    
    Returns:
        str: Rendered HTML for the test-cache page.
    """
    return render_template("test-cache.html")


@public_bp.route("/robots.txt")
def robots_txt():
    """Generate robots.txt for search engines."""
    from flask import make_response
    
    robots_content = f"""User-agent: *
Allow: /
Allow: /maps
Allow: /learn
Allow: /how-to
Allow: /card-hunting-tips
Allow: /about
Allow: /sitemap

# State pages are search engine only (XML) - users get 404
Disallow: /states
Disallow: /state/

# Disallow admin and private areas
Disallow: /admin/
Disallow: /auth/
Disallow: /payment/
Disallow: /api/
Disallow: /dev/

# Sitemap location
Sitemap: {request.url_root.rstrip('/')}/sitemap.xml

# Crawl delay (optional - be respectful to search engines)
Crawl-delay: 1
"""
    
    response = make_response(robots_content)
    response.headers['Content-Type'] = 'text/plain'
    return response
