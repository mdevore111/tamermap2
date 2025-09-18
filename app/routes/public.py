# app/routes/public.py
import stripe
from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app, jsonify, Response
from flask import session
from flask_login import current_user
from datetime import datetime
from sqlalchemy import func

from ..extensions import db, limiter
from ..models import Message, Retailer, Event, VisitorLog
from app.communication_forms import MessageForm
from app.routes.security import check_referrer
from app.custom_email import send_email_with_context

import time
import json
from threading import Lock

# Simple in-memory cache for sitemap
_sitemap_cache = {}
_sitemap_cache_lock = Lock()
_sitemap_cache_ttl = 3600  # 1 hour in seconds

def _get_cached_sitemap(cache_key):
    """Get cached sitemap if it exists and is not expired."""
    with _sitemap_cache_lock:
        if cache_key in _sitemap_cache:
            cached_data, timestamp = _sitemap_cache[cache_key]
            if time.time() - timestamp < _sitemap_cache_ttl:
                return cached_data
        return None

def _set_cached_sitemap(cache_key, data):
    """Cache sitemap data with timestamp."""
    with _sitemap_cache_lock:
        _sitemap_cache[cache_key] = (data, time.time())

# Create a blueprint for public (unprotected) routes
public_bp = Blueprint("public", __name__)


@public_bp.route("/")
def home():
    """Render the home page with the interactive map."""
    print(f"DEBUG: home function called - Method: {request.method}")
    current_app.logger.info(f"home function called - Method: {request.method}")
    google_api_key = current_app.config.get("GOOGLE_API_KEY")
    return render_template("maps.html", google_api_key=google_api_key)


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
    # Allow preview via query param; otherwise restrict to bots
    if 'preview' not in request.args and not any(bot in user_agent for bot in ['bot', 'crawler', 'spider', 'googlebot', 'bingbot']):
        return "Page not found", 404
    
    # Define all available states with their metadata and keyword-rich descriptions
    states = [
        # West Coast
        {
            'name': 'Washington',
            'slug': 'washington',
            'description': 'Find Pokemon cards early in Washington - Premier card hunting spots in Pacific Northwest with fresh Pokemon card inventory and rare finds',
            'icon': 'fas fa-mountain'
        },
        {
            'name': 'Oregon',
            'slug': 'oregon',
            'description': 'Discover Pokemon cards first in Oregon - Top card hunting locations in Beaver State with early access to new releases and exclusive Pokemon cards',
            'icon': 'fas fa-tree'
        },
        {
            'name': 'California',
            'slug': 'california',
            'description': 'Get Pokemon cards before anyone else in California - Best card hunting destinations in Golden State with first pick of rare Pokemon cards and fresh stock',
            'icon': 'fas fa-sun'
        },
        {
            'name': 'Nevada',
            'slug': 'nevada',
            'description': 'Find Pokemon cards early in Nevada - Premier card hunting spots in Silver State with fresh Pokemon card inventory and exclusive finds',
            'icon': 'fas fa-diamond'
        },
        {
            'name': 'Arizona',
            'slug': 'arizona',
            'description': 'Discover Pokemon cards first in Arizona - Top card hunting locations in Grand Canyon State with early access to new releases and rare Pokemon cards',
            'icon': 'fas fa-mountain'
        },
        
        # Southwest
        {
            'name': 'Texas',
            'slug': 'texas',
            'description': 'Get Pokemon cards before anyone else in Texas - Best card hunting destinations in Lone Star State with first pick of rare Pokemon cards and fresh inventory',
            'icon': 'fas fa-star'
        },
        {
            'name': 'New Mexico',
            'slug': 'new-mexico',
            'description': 'Find Pokemon cards early in New Mexico - Premier card hunting spots in Land of Enchantment with fresh Pokemon card inventory and rare finds',
            'icon': 'fas fa-sun'
        },
        
        # Southeast
        {
            'name': 'Florida',
            'slug': 'florida',
            'description': 'Discover Pokemon cards first in Florida - Top card hunting locations in Sunshine State with early access to new releases and exclusive Pokemon cards',
            'icon': 'fas fa-umbrella-beach'
        },
        {
            'name': 'Georgia',
            'slug': 'georgia',
            'description': 'Get Pokemon cards before anyone else in Georgia - Best card hunting destinations in Peach State with first pick of rare Pokemon cards and fresh stock',
            'icon': 'fas fa-tree'
        },
        {
            'name': 'North Carolina',
            'slug': 'north-carolina',
            'description': 'Find Pokemon cards early in North Carolina - Premier card hunting spots in Tar Heel State with fresh Pokemon card inventory and rare finds',
            'icon': 'fas fa-leaf'
        },
        {
            'name': 'South Carolina',
            'slug': 'south-carolina',
            'description': 'Discover Pokemon cards first in South Carolina - Top card hunting locations in Palmetto State with early access to new releases and exclusive Pokemon cards',
            'icon': 'fas fa-palm-tree'
        },
        {
            'name': 'Tennessee',
            'slug': 'tennessee',
            'description': 'Get Pokemon cards before anyone else in Tennessee - Best card hunting destinations in Volunteer State with first pick of rare Pokemon cards and fresh inventory',
            'icon': 'fas fa-music'
        },
        {
            'name': 'Alabama',
            'slug': 'alabama',
            'description': 'Find Pokemon cards early in Alabama - Premier card hunting spots in Yellowhammer State with fresh Pokemon card inventory and rare finds',
            'icon': 'fas fa-bird'
        },
        {
            'name': 'Mississippi',
            'slug': 'mississippi',
            'description': 'Discover Pokemon cards first in Mississippi - Top card hunting locations in Magnolia State with early access to new releases and exclusive Pokemon cards',
            'icon': 'fas fa-flower'
        },
        {
            'name': 'Louisiana',
            'slug': 'louisiana',
            'description': 'Get Pokemon cards before anyone else in Louisiana - Best card hunting destinations in Pelican State with first pick of rare Pokemon cards and fresh stock',
            'icon': 'fas fa-water'
        },
        {
            'name': 'Arkansas',
            'slug': 'arkansas',
            'description': 'Find Pokemon cards early in Arkansas - Premier card hunting spots in Natural State with fresh Pokemon card inventory and rare finds',
            'icon': 'fas fa-mountain'
        },
        
        # Northeast
        {
            'name': 'New York',
            'slug': 'new-york',
            'description': 'Discover Pokemon cards first in New York - Top card hunting locations in Empire State with early access to new releases and exclusive Pokemon cards',
            'icon': 'fas fa-city'
        },
        {
            'name': 'New Jersey',
            'slug': 'new-jersey',
            'description': 'Get Pokemon cards before anyone else in New Jersey - Best card hunting destinations in Garden State with first pick of rare Pokemon cards and fresh inventory',
            'icon': 'fas fa-flower'
        },
        {
            'name': 'Pennsylvania',
            'slug': 'pennsylvania',
            'description': 'Find Pokemon cards early in Pennsylvania - Premier card hunting spots in Keystone State with fresh Pokemon card inventory and rare finds',
            'icon': 'fas fa-key'
        },
        {
            'name': 'Delaware',
            'slug': 'delaware',
            'description': 'Discover Pokemon cards first in Delaware - Top card hunting locations in First State with early access to new releases and exclusive Pokemon cards',
            'icon': 'fas fa-flag'
        },
        {
            'name': 'Maryland',
            'slug': 'maryland',
            'description': 'Get Pokemon cards before anyone else in Maryland - Best card hunting destinations in Old Line State with first pick of rare Pokemon cards and fresh stock',
            'icon': 'fas fa-crab'
        },
        {
            'name': 'Virginia',
            'slug': 'virginia',
            'description': 'Find Pokemon cards early in Virginia - Premier card hunting spots in Old Dominion with fresh Pokemon card inventory and rare finds',
            'icon': 'fas fa-mountain'
        },
        {
            'name': 'West Virginia',
            'slug': 'west-virginia',
            'description': 'Discover Pokemon cards first in West Virginia - Top card hunting locations in Mountain State with early access to new releases and exclusive Pokemon cards',
            'icon': 'fas fa-mountain'
        },
        {
            'name': 'Massachusetts',
            'slug': 'massachusetts',
            'description': 'Get Pokemon cards before anyone else in Massachusetts - Best card hunting destinations in Bay State with first pick of rare Pokemon cards and fresh inventory',
            'icon': 'fas fa-ship'
        },
        {
            'name': 'Connecticut',
            'slug': 'connecticut',
            'description': 'Find Pokemon cards early in Connecticut - Premier card hunting spots in Constitution State with fresh Pokemon card inventory and rare finds',
            'icon': 'fas fa-book'
        },
        {
            'name': 'Rhode Island',
            'slug': 'rhode-island',
            'description': 'Discover Pokemon cards first in Rhode Island - Top card hunting locations in Ocean State with early access to new releases and exclusive Pokemon cards',
            'icon': 'fas fa-water'
        },
        {
            'name': 'Vermont',
            'slug': 'vermont',
            'description': 'Get Pokemon cards before anyone else in Vermont - Best card hunting destinations in Green Mountain State with first pick of rare Pokemon cards and fresh stock',
            'icon': 'fas fa-mountain'
        },
        {
            'name': 'New Hampshire',
            'slug': 'new-hampshire',
            'description': 'Find Pokemon cards early in New Hampshire - Premier card hunting spots in Granite State with fresh Pokemon card inventory and rare finds',
            'icon': 'fas fa-mountain'
        },
        {
            'name': 'Maine',
            'slug': 'maine',
            'description': 'Discover Pokemon cards first in Maine - Top card hunting locations in Pine Tree State with early access to new releases and exclusive Pokemon cards',
            'icon': 'fas fa-tree'
        },
        
        # Midwest
        {
            'name': 'Illinois',
            'slug': 'illinois',
            'description': 'Get Pokemon cards before anyone else in Illinois - Best card hunting destinations in Prairie State with first pick of rare Pokemon cards and fresh inventory',
            'icon': 'fas fa-building'
        },
        {
            'name': 'Indiana',
            'slug': 'indiana',
            'description': 'Find Pokemon cards early in Indiana - Premier card hunting spots in Hoosier State with fresh Pokemon card inventory and rare finds',
            'icon': 'fas fa-basketball'
        },
        {
            'name': 'Michigan',
            'slug': 'michigan',
            'description': 'Discover Pokemon cards first in Michigan - Top card hunting locations in Great Lakes State with early access to new releases and exclusive Pokemon cards',
            'icon': 'fas fa-water'
        },
        {
            'name': 'Ohio',
            'slug': 'ohio',
            'description': 'Get Pokemon cards before anyone else in Ohio - Best card hunting destinations in Buckeye State with first pick of rare Pokemon cards and fresh stock',
            'icon': 'fas fa-leaf'
        },
        {
            'name': 'Wisconsin',
            'slug': 'wisconsin',
            'description': 'Find Pokemon cards early in Wisconsin - Premier card hunting spots in Badger State with fresh Pokemon card inventory and rare finds',
            'icon': 'fas fa-cheese'
        },
        {
            'name': 'Minnesota',
            'slug': 'minnesota',
            'description': 'Discover Pokemon cards first in Minnesota - Top card hunting locations in North Star State with early access to new releases and exclusive Pokemon cards',
            'icon': 'fas fa-star'
        },
        {
            'name': 'Iowa',
            'slug': 'iowa',
            'description': 'Get Pokemon cards before anyone else in Iowa - Best card hunting destinations in Hawkeye State with first pick of rare Pokemon cards and fresh inventory',
            'icon': 'fas fa-eye'
        },
        {
            'name': 'Missouri',
            'slug': 'missouri',
            'description': 'Find Pokemon cards early in Missouri - Premier card hunting spots in Show Me State with fresh Pokemon card inventory and rare finds',
            'icon': 'fas fa-hand'
        },
        {
            'name': 'Kansas',
            'slug': 'kansas',
            'description': 'Discover Pokemon cards first in Kansas - Top card hunting locations in Sunflower State with early access to new releases and exclusive Pokemon cards',
            'icon': 'fas fa-sun'
        },
        {
            'name': 'Nebraska',
            'slug': 'nebraska',
            'description': 'Get Pokemon cards before anyone else in Nebraska - Best card hunting destinations in Cornhusker State with first pick of rare Pokemon cards and fresh stock',
            'icon': 'fas fa-seedling'
        },
        {
            'name': 'North Dakota',
            'slug': 'north-dakota',
            'description': 'Find Pokemon cards early in North Dakota - Premier card hunting spots in Peace Garden State with fresh Pokemon card inventory and rare finds',
            'icon': 'fas fa-flower'
        },
        {
            'name': 'South Dakota',
            'slug': 'south-dakota',
            'description': 'Discover Pokemon cards first in South Dakota - Top card hunting locations in Mount Rushmore State with early access to new releases and exclusive Pokemon cards',
            'icon': 'fas fa-mountain'
        },
        
        # Mountain West
        {
            'name': 'Colorado',
            'slug': 'colorado',
            'description': 'Get Pokemon cards before anyone else in Colorado - Best card hunting destinations in Centennial State with first pick of rare Pokemon cards and fresh inventory',
            'icon': 'fas fa-mountain'
        },
        {
            'name': 'Utah',
            'slug': 'utah',
            'description': 'Find Pokemon cards early in Utah - Premier card hunting spots in Beehive State with fresh Pokemon card inventory and rare finds',
            'icon': 'fas fa-bee'
        },
        {
            'name': 'Wyoming',
            'slug': 'wyoming',
            'description': 'Discover Pokemon cards first in Wyoming - Top card hunting locations in Equality State with early access to new releases and exclusive Pokemon cards',
            'icon': 'fas fa-balance-scale'
        },
        {
            'name': 'Montana',
            'slug': 'montana',
            'description': 'Get Pokemon cards before anyone else in Montana - Best card hunting destinations in Treasure State with first pick of rare Pokemon cards and fresh stock',
            'icon': 'fas fa-gem'
        },
        {
            'name': 'Idaho',
            'slug': 'idaho',
            'description': 'Find Pokemon cards early in Idaho - Premier card hunting spots in Gem State with fresh Pokemon card inventory and rare finds',
            'icon': 'fas fa-gem'
        },
        
        # Alaska & Hawaii
        {
            'name': 'Alaska',
            'slug': 'alaska',
            'description': 'Discover Pokemon cards first in Alaska - Top card hunting locations in Last Frontier with early access to new releases and exclusive Pokemon cards',
            'icon': 'fas fa-snowflake'
        },
        {
            'name': 'Hawaii',
            'slug': 'hawaii',
            'description': 'Get Pokemon cards before anyone else in Hawaii - Best card hunting destinations in Aloha State with first pick of rare Pokemon cards and fresh stock',
            'icon': 'fas fa-umbrella-beach'
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
    Dynamic state page showing all KIOSKS AND CARD SHOPS in a specific state organized by city.
    BLOCKED: This route is for search engines only, not user access.
    
    Args:
        state_name (str): The state name (e.g., 'washington', 'california')
    
    Returns:
        str: 404 error for users, XML for search engines
    """
    # Block user access - this is for search engines only
    user_agent = request.headers.get('User-Agent', '').lower()
    if 'preview' not in request.args and not any(bot in user_agent for bot in ['bot', 'crawler', 'spider', 'googlebot', 'bingbot']):
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
    
    # Build query for ALL RETAILERS (both kiosks and card shops)
    from sqlalchemy import or_
    
    # Query for kiosks
    kiosk_query = db.session.query(Retailer).filter(
        Retailer.enabled == True,
        Retailer.retailer_type.ilike('%kiosk%')
    )
    
    # Query for card shops with multiple naming variations
    cardshop_type_filters = or_(
        Retailer.retailer_type.ilike('%card shop%'),
        Retailer.retailer_type.ilike('%card_shop%'),
        Retailer.retailer_type.ilike('%indie%'),
        Retailer.retailer_type.ilike('%card%shop%'),
        Retailer.retailer_type.ilike('%shop%')
    )
    cardshop_query = db.session.query(Retailer).filter(
        Retailer.enabled == True,
        cardshop_type_filters
    )
    
    # Use OR conditions for multiple state name variations
    state_filters = []
    for term in search_terms:
        state_filters.append(Retailer.full_address.ilike(f'%{term}%'))
    
    # Get both kiosks and card shops
    kiosks = kiosk_query.filter(or_(*state_filters)).all()
    card_shops = cardshop_query.filter(or_(*state_filters)).all()
    
    # Group retailers by city with better address parsing
    cities = {}
    
    # Process kiosks
    for retailer in kiosks:
        address_parts = retailer.full_address.split(',')
        if len(address_parts) >= 2:
            city = address_parts[1].strip()
            city = ' '.join(city.split())
            if city:
                if city not in cities:
                    cities[city] = {'kiosks': [], 'card_shops': []}
                cities[city]['kiosks'].append(retailer)
    
    # Process card shops
    for retailer in card_shops:
        address_parts = retailer.full_address.split(',')
        if len(address_parts) >= 2:
            city = address_parts[1].strip()
            city = ' '.join(city.split())
            if city:
                if city not in cities:
                    cities[city] = {'kiosks': [], 'card_shops': []}
                cities[city]['card_shops'].append(retailer)
    
    # Sort cities alphabetically
    sorted_cities = dict(sorted(cities.items()))
    
    total_kiosks = len(kiosks)
    total_card_shops = len(card_shops)
    
    # Return XML for search engines instead of HTML template
    from flask import make_response
    import html
    
    def escape_xml(text):
        """Escape XML special characters"""
        if text is None:
            return 'N/A'
        return html.escape(str(text))
    
    xml_content = f'''<?xml version="1.0" encoding="UTF-8"?>
<state_retailers xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
    <state_name>{escape_xml(state_name_normalized)}</state_name>
    <description>Find Pokemon trading card game retailers in {escape_xml(state_name_normalized)}. Discover kiosks and card shops where you can buy Pokemon cards, booster packs, and TCG accessories across cities throughout {escape_xml(state_name_normalized)}.</description>
    <total_kiosks>{total_kiosks}</total_kiosks>
    <total_card_shops>{total_card_shops}</total_card_shops>
    <total_cities>{len(sorted_cities)}</total_cities>
    <retailers>
'''
    
    for city, city_data in sorted_cities.items():
        city_kiosks = city_data['kiosks']
        city_card_shops = city_data['card_shops']
        
        # Add all kiosks for this city in simple format
        for retailer in city_kiosks:
            xml_content += f'''        <retailer>
            <location>{escape_xml(state_name_normalized)} - {escape_xml(city)} - Pokemon cards at {escape_xml(retailer.retailer)} {escape_xml(retailer.full_address)}</location>
            <type>Kiosk</type>
        </retailer>
'''
        
        # Add all card shops for this city in simple format  
        for retailer in city_card_shops:
            xml_content += f'''        <retailer>
            <location>{escape_xml(state_name_normalized)} - {escape_xml(city)} - Pokemon trading card shop {escape_xml(retailer.retailer)} {escape_xml(retailer.full_address)}</location>
            <type>Card Shop</type>
        </retailer>
'''
    
    xml_content += '''    </retailers>
</state_retailers>'''
    
    response = make_response(xml_content)
    response.headers['Content-Type'] = 'application/xml'
    return response





def render_correct_form_template(form):
    """Render the correct form template based on form type"""
    if form.communication_type.data == 'location':
        if form.form_type.data == 'correct_existing':
            return render_template("correct_location_form.html", form=form)
        elif form.form_type.data == 'add_new':
            return render_template("add_location_form.html", form=form)
    
    # Default to message form for other types
    return render_template("message_form.html", form=form)

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
    print(f"DEBUG: send_message function called - Method: {request.method}")
    current_app.logger.info(f"send_message function called - Method: {request.method}")
    form = MessageForm()

    # only override on GET when link provides type & metadata
    if request.method == "GET":
        pre = request.args.get("type", "")
        form.communication_type.data = (
            pre if pre in ["suggestion", "contact", "location", "report", "support", "business", "post_wins"] else "contact"
        )
        if form.communication_type.data == "report":
            addr = request.args.get("address", "")
            form.subject.data = addr
            form.reported_address.data = addr
            form.reported_phone.data = request.args.get("phone", "")
            form.reported_website.data = request.args.get("website", "")
            form.reported_hours.data = request.args.get("hours", "")

    # Debug form validation
    current_app.logger.info(f"Form validation - validate_on_submit(): {form.validate_on_submit()}")
    if not form.validate_on_submit():
        current_app.logger.warning(f"Form validation failed - errors: {form.errors}")
        current_app.logger.warning(f"Form data received: {request.form.to_dict()}")
        # Show validation errors to user
        for field, errors in form.errors.items():
            for error in errors:
                flash(f"{field}: {error}", "danger")
    
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
            return render_correct_form_template(form)
        
        # Check for suspicious keywords in subject or body
        spam_keywords = ['urgent', 'act now', 'limited time', 'free money', 'make money fast', 'work from home', 'earn cash']
        for keyword in spam_keywords:
            if keyword in body_text or keyword in subject_text:
                current_app.logger.warning(f"Potential spam from IP {client_ip}: keyword '{keyword}' detected")
                flash("Message contains inappropriate content.", "danger")
                return render_correct_form_template(form)
        
        # Check for suspicious user agent
        user_agent = request.headers.get('User-Agent', '').lower()
        if 'bot' in user_agent or 'crawler' in user_agent or 'spider' in user_agent:
            current_app.logger.warning(f"Bot detected from IP {client_ip}: {user_agent}")
            flash("Automated submissions are not allowed.", "danger")
            return render_correct_form_template(form)
        
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
        if form.communication_type.data == 'location':
            if form.form_type.data == 'add_new':
                extra_lines.append("Form Type: ADD NEW LOCATION")
            elif form.form_type.data == 'correct_existing':
                extra_lines.append("Form Type: CORRECT EXISTING LOCATION")
            if form.is_admin_report.data:
                extra_lines.append("ADMIN REVIEW REQUESTED")
        if form.communication_type.data == 'post_wins':
            if form.win_type.data:
                extra_lines.append(f"Win Type: {form.win_type.data}")
            if form.location_used.data:
                extra_lines.append(f"Location Used: {form.location_used.data}")
            if form.cards_found.data:
                extra_lines.append(f"Cards Found: {form.cards_found.data}")
            if form.time_saved.data:
                extra_lines.append(f"Time Saved: {form.time_saved.data}")
            if form.money_saved.data:
                extra_lines.append(f"Money Saved: {form.money_saved.data}")
            if form.allow_feature.data:
                extra_lines.append("Permission to Feature: YES")
        extra = "\n".join(extra_lines) + "\n"

        try:
            # Log form data for debugging
            current_app.logger.info(f"Processing form submission from IP {client_ip} by {user_name}")
            current_app.logger.info(f"Form data - communication_type: {form.communication_type.data}, form_type: {form.form_type.data}")
            current_app.logger.info(f"Form data - out_of_business: {form.out_of_business.data}, is_new_location: {form.is_new_location.data}")
            
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
                is_new_location=form.is_new_location.data,
                is_admin_report=form.is_admin_report.data,
                form_type=form.form_type.data,
                name=form.name.data,
                address=form.address.data,
                email=form.address.data,  # Map address field to email field for backward compatibility
                # Post Wins fields
                win_type=form.win_type.data,
                location_used=form.location_used.data,
                cards_found=form.cards_found.data,
                time_saved=form.time_saved.data,
                money_saved=form.money_saved.data,
                allow_feature=form.allow_feature.data
            )
            db.session.add(msg_record)
            db.session.commit()

            # Send admin notification email
            try:
                current_app.logger.info(f"Attempting to send admin notification email")
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
                    is_new_location=form.is_new_location.data,
                    config=current_app.config
                )
                current_app.logger.info(f"Admin notification email sent successfully")
            except Exception as email_error:
                current_app.logger.error(f"Failed to send admin notification email: {email_error}")
                # Don't fail the whole process if email fails

            # Log successful submission for monitoring
            current_app.logger.info(f"Message submitted successfully from IP {client_ip} by {user_name}")
            
            flash("Your message has been sent.", "success")
            return redirect(url_for("public.home"))
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Failed to save message: {e}")
            current_app.logger.error(f"Exception type: {type(e).__name__}")
            current_app.logger.error(f"Exception details: {str(e)}")
            import traceback
            current_app.logger.error(f"Traceback: {traceback.format_exc()}")
            flash("An error occurred while sending your message.", "danger")

    # Render the correct form template based on form type
    return render_correct_form_template(form)


@public_bp.route("/add-location")
def add_location():
    """
    Display the 'Add New Location' form.
    
    This form is for users to submit completely new locations that aren't in the database.
    It's accessible from the header contact dropdown.
    """
    form = MessageForm()
    form.communication_type.data = 'location'
    form.form_type.data = 'add_new'
    form.is_admin_report.data = True  # New locations always need admin review
    form.is_new_location.data = True  # This is a new location
    form.out_of_business.data = False  # Explicitly set to unchecked
    form.subject.data = "New Location Submission"
    
    return render_template("add_location_form.html", form=form)


@public_bp.route("/correct-location")
def correct_location():
    """
    Display the 'Correct Existing Location' form with pre-populated data.
    
    This form is for users to fix incorrect data for existing locations.
    It's only accessible from Info Windows and pre-populates with current location data.
    """
    form = MessageForm()
    form.communication_type.data = 'location'
    form.form_type.data = 'correct_existing'
    form.is_admin_report.data = True  # Corrections need admin review
    form.is_new_location.data = False  # This is correcting an existing location
    form.out_of_business.data = False  # Explicitly set to unchecked
    form.subject.data = "Location Data Correction"
    
    # Debug logging
    print(f"DEBUG: out_of_business.data = {form.out_of_business.data}")
    print(f"DEBUG: out_of_business.default = {form.out_of_business.default}")
    
    # Pre-populate with location data from URL parameters
    if request.args.get("address"):
        form.reported_address.data = request.args.get("address")
    if request.args.get("phone"):
        form.reported_phone.data = request.args.get("phone")
    if request.args.get("website"):
        form.reported_website.data = request.args.get("website")
    if request.args.get("hours"):
        form.reported_hours.data = request.args.get("hours")
    
    return render_template("correct_location_form.html", form=form)


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
@public_bp.route("/sitemap.html")
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


@public_bp.route("/how-to-make-money")
def how_to_make_money():
    """Render the comprehensive guide for making money flipping Pokemon cards."""
    return render_template("how-to-make-money.html")


@public_bp.route("/how-to-hunt-cards")
def how_to_hunt_cards():
    """Render the comprehensive guide for Pokemon card hunting strategies."""
    return render_template("how-to-hunt-cards.html")


@public_bp.route("/how-to-timing")
def how_to_timing():
    """Render the comprehensive guide for optimal timing in Pokemon card hunting."""
    return render_template("how-to-timing.html")


@public_bp.route("/how-to-routes")
def how_to_routes():
    """Render the comprehensive guide for route planning in Pokemon card hunting."""
    return render_template("how-to-routes.html")


# Site Tutorials - Functional guides for using TamerMap features
@public_bp.route("/site-tutorials")
def site_tutorials():
    """Render the site tutorials hub page."""
    return render_template("site-tutorials.html")


@public_bp.route("/faq")
def faq():
    """Render the FAQ page with common questions and answers."""
    return render_template("faq.html")


@public_bp.route("/user-wins")
def user_wins():
    """Render the User Wins testimonials page."""
    return render_template("user-wins.html")


@public_bp.route("/how-to-route-planning-tool")
def how_to_route_planning_tool():
    """Render the comprehensive guide for using TamerMap's route planning tool."""
    return render_template("how-to-route-planning-tool.html")


@public_bp.route("/how-to-use-heatmaps")
def how_to_use_heatmaps():
    """Render the comprehensive guide for using TamerMap's heatmap feature."""
    return render_template("how-to-use-heatmaps.html")

@public_bp.route("/how-to-use-new-locations-filter")
def how_to_use_new_locations_filter():
    """Render the comprehensive guide for using TamerMap's New Locations filter."""
    return render_template("how-to-use-new-locations-filter.html")

@public_bp.route("/how-to-use-open-now-filter")
def how_to_use_open_now_filter():
    """Render the comprehensive guide for using TamerMap's Open Now filter."""
    return render_template("how-to-use-open-now-filter.html")


@public_bp.route("/how-to-reset-password")
def how_to_reset_password():
    """Render the comprehensive guide for resetting TamerMap passwords."""
    return render_template("how-to-reset-password.html")


@public_bp.route("/how-to-personal-notes")
def how_to_personal_notes():
    """Render the Personal Notes tutorial page."""
    return render_template("how-to-personal-notes.html")


@public_bp.route("/how-to-update-account")
def how_to_update_account():
    """Render the account information update guide."""
    return render_template("how-to-update-account.html")


@public_bp.route("/how-to-manage-pro-subscription")
def how_to_manage_pro_subscription():
    """Render the Pro subscription management guide."""
    return render_template("how-to-manage-pro-subscription.html")


@public_bp.route("/how-to-get-help")
def how_to_get_help():
    """Render the comprehensive help and support guide."""
    return render_template("how-to-get-help.html")


@public_bp.route("/sitemap.xml")
def sitemap_xml():
    """Generate dynamic XML sitemap for search engines with caching for performance."""
    from flask import make_response
    from datetime import datetime
    
    # Get current date
    now = datetime.utcnow().strftime('%Y-%m-%d')
    
    # Determine scheme and host robustly (behind proxies/CDN)
    forwarded_proto = request.headers.get('X-Forwarded-Proto')
    scheme = (forwarded_proto or request.scheme or 'https').split(',')[0].strip()
    host = request.headers.get('X-Forwarded-Host', request.host).split(',')[0].strip()
    base_url = f"{scheme}://{host}".rstrip('/')
    
    # Create a cache key based on date AND host (avoid cross-domain contamination)
    cache_key = f"sitemap_{host}_{now}"
    
    # Check if we have a cached version
    cached_content = _get_cached_sitemap(cache_key)
    if cached_content:
        response = make_response(cached_content)
        response.headers['Content-Type'] = 'application/xml; charset=utf-8'
        response.headers['Cache-Control'] = 'public, max-age=3600'
        response.headers['X-Cache'] = 'HIT'
        return response
    
    # Use tuples for better memory efficiency
    static_pages = (
        ('/', '1.0', 'daily'),
        ('/learn', '0.8', 'weekly'),
        ('/how-to', '0.8', 'weekly'),
        ('/user-wins', '0.8', 'weekly'),
        ('/how-to-make-money', '0.9', 'weekly'),
        ('/how-to-hunt-cards', '0.9', 'weekly'),
        ('/how-to-timing', '0.9', 'weekly'),
        ('/how-to-routes', '0.9', 'weekly'),
        ('/site-tutorials', '0.8', 'weekly'),
        ('/faq', '0.8', 'weekly'),
        ('/how-to-route-planning-tool', '0.9', 'weekly'),
        ('/how-to-use-heatmaps', '0.9', 'weekly'),
        ('/how-to-use-new-locations-filter', '0.9', 'weekly'),
        ('/how-to-use-open-now-filter', '0.9', 'weekly'),
        ('/how-to-reset-password', '0.8', 'weekly'),
        ('/how-to-personal-notes', '0.9', 'weekly'),
        ('/how-to-update-account', '0.8', 'weekly'),
        ('/how-to-manage-pro-subscription', '0.8', 'weekly'),
        ('/how-to-get-help', '0.8', 'weekly'),
        ('/card-hunting-tips', '0.8', 'weekly'),
        ('/states', '0.8', 'weekly'),
        ('/about', '0.7', 'monthly'),
        ('/terms', '0.6', 'monthly'),
        ('/privacy', '0.6', 'monthly'),
        ('/add-location', '0.7', 'monthly'),
        ('/correct-location', '0.7', 'monthly'),
        ('/message', '0.5', 'monthly'),
        ('/robots.txt', '0.3', 'monthly'),
        ('/manifest.json', '0.3', 'monthly'),
        ('/sitemap', '0.5', 'monthly'),
    )
    
    # Pre-define state slugs for efficiency
    state_slugs = (
        # West Coast
        'washington', 'oregon', 'california', 'nevada', 'arizona',
        # Southwest
        'texas', 'new-mexico',
        # Southeast
        'florida', 'georgia', 'north-carolina', 'south-carolina', 'tennessee', 
        'alabama', 'mississippi', 'louisiana', 'arkansas',
        # Northeast
        'new-york', 'new-jersey', 'pennsylvania', 'delaware', 'maryland', 
        'virginia', 'west-virginia', 'massachusetts', 'connecticut', 
        'rhode-island', 'vermont', 'new-hampshire', 'maine',
        # Midwest
        'illinois', 'indiana', 'michigan', 'ohio', 'wisconsin', 'minnesota', 
        'iowa', 'missouri', 'kansas', 'nebraska', 'north-dakota', 'south-dakota',
        # Mountain West
        'colorado', 'utah', 'wyoming', 'montana', 'idaho',
        # Alaska & Hawaii
        'alaska', 'hawaii'
    )
    
    # Generate XML content efficiently using string building
    xml_parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
    ]
    
    # Add static pages
    for url, priority, changefreq in static_pages:
        xml_parts.append(
            f'<url><loc>{base_url}{url}</loc><lastmod>{now}</lastmod>'
            f'<changefreq>{changefreq}</changefreq><priority>{priority}</priority></url>'
        )
    
    # Add state pages efficiently (now combined kiosks + card shops) with priority based on size/importance
    high_priority_states = {'california', 'texas', 'florida', 'new-york', 'illinois', 'pennsylvania', 'ohio', 'michigan', 'georgia', 'washington'}
    medium_priority_states = {'oregon', 'nevada', 'arizona', 'new-mexico', 'north-carolina', 'south-carolina', 'tennessee', 'alabama', 'virginia', 'massachusetts', 'new-jersey', 'maryland', 'wisconsin', 'minnesota', 'missouri', 'indiana', 'colorado', 'utah'}
    
    for state_slug in state_slugs:
        if state_slug in high_priority_states:
            priority = '0.9'
        elif state_slug in medium_priority_states:
            priority = '0.8'
        else:
            priority = '0.7'
            
        xml_parts.append(
            f'<url><loc>{base_url}/state/{state_slug}</loc><lastmod>{now}</lastmod>'
            f'<changefreq>weekly</changefreq><priority>{priority}</priority></url>'
        )
    
    xml_parts.append('</urlset>')
    
    # Join all parts efficiently
    xml_content = ''.join(xml_parts)
    
    # Cache the generated content
    _set_cached_sitemap(cache_key, xml_content)
    
    # Create response with proper headers
    response = make_response(xml_content)
    response.headers['Content-Type'] = 'application/xml; charset=utf-8'
    response.headers['Cache-Control'] = 'public, max-age=3600'  # Cache for 1 hour
    response.headers['X-Cache'] = 'MISS'
    
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
Allow: /
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


@public_bp.route("/manifest.json")
def manifest_json():
    """Serve manifest.json with proper CORS headers to avoid Cloudflare Access issues."""
    manifest_content = {
        "name": "TamerMap - Pokemon Card Hunting",
        "short_name": "TamerMap",
        "icons": [
            {
                "src": "/static/android-chrome-192x192.png",
                "sizes": "192x192",
                "type": "image/png"
            },
            {
                "src": "/static/android-chrome-512x512.png", 
                "sizes": "512x512",
                "type": "image/png"
            }
        ],
        "theme_color": "#ffffff",
        "background_color": "#ffffff",
        "display": "standalone",
        "start_url": "/",
        "scope": "/"
    }
    
    response = Response(
        json.dumps(manifest_content, indent=2),
        mimetype='application/json'
    )
    
    # Add CORS headers to prevent Cloudflare Access issues
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    response.headers['Cache-Control'] = 'public, max-age=3600'  # Cache for 1 hour
    
    return response
