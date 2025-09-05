from flask import Blueprint, render_template, jsonify, request, flash, redirect, url_for, current_app, send_file
import json
from flask_login import login_required, current_user
from flask_authorize import Authorize
from werkzeug.security import generate_password_hash
from app.models import User, Retailer, Event, Message, Role, VisitorLog, OutboundMessage, BulkEmailJob, BulkEmailRecipient  # Removed Location import since table doesn't exist
from app import db
from sqlalchemy import func
from datetime import datetime
from datetime import datetime, timedelta
from sqlalchemy import desc, func, or_, case
from functools import wraps
import time
from collections import defaultdict
import stripe
from app.payment.stripe_webhooks import log_billing_event
from app.custom_email import send_email_with_context
from app.admin_utils import get_top_referrers, get_top_pages, get_top_ref_codes
import os
from io import BytesIO
from typing import Optional
from app.models import RouteEvent, LegendClick

def convert_utc_to_pacific_time(utc_timestamp):
    """Convert UTC timestamp to Pacific time for display"""
    if not utc_timestamp:
        return None
    
    try:
        from zoneinfo import ZoneInfo
        # Convert to Pacific time
        utc_time = utc_timestamp.replace(tzinfo=ZoneInfo("UTC"))
        pacific_time = utc_time.astimezone(ZoneInfo("America/Los_Angeles"))
        return pacific_time.strftime('%Y-%m-%d %H:%M')
    except ImportError:
        try:
            import pytz
            # Fallback for older Python versions
            utc_time = pytz.utc.localize(utc_timestamp)
            pacific_time = utc_time.astimezone(pytz.timezone("America/Los_Angeles"))
            return pacific_time.strftime('%Y-%m-%d %H:%M')
        except ImportError:
            # Final fallback - show UTC with note
            return f"{utc_timestamp.strftime('%Y-%m-%d %H:%M')} UTC"

# Optional imports for PDF functionality
SIGNING_AVAILABLE: bool
try:
    from pyhanko.sign import signers
    from pyhanko.sign.signers import PdfSigner, PdfSignatureMetadata
    SIGNING_AVAILABLE = True
except ImportError:
    SIGNING_AVAILABLE = False

try:
    import pikepdf
except ImportError:
    pikepdf = None

try:
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.lib.units import inch
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False

admin_bp = Blueprint('admin', __name__)
authorize = Authorize()

# Simple rate limiting for DataTables requests (DISABLED - Cloudflare handles this)
# request_timestamps = defaultdict(list)

# Simple cache for DataTables responses
data_cache = {}
CACHE_DURATION = 30  # seconds

def get_cache_key(endpoint, **kwargs):
    """Generate cache key for DataTables requests"""
    params = sorted(kwargs.items())
    return f"{endpoint}:{hash(str(params))}"

def get_cached_response(cache_key):
    """Get cached response if still valid"""
    if cache_key in data_cache:
        timestamp, response = data_cache[cache_key]
        if time.time() - timestamp < CACHE_DURATION:
            return response
        else:
            del data_cache[cache_key]
    return None

def cache_response(cache_key, response):
    """Cache response with timestamp"""
    data_cache[cache_key] = (time.time(), response)

def rate_limit_data_tables(max_requests=10, window_seconds=60):
    """Simple rate limiting decorator for DataTables endpoints (DISABLED - Cloudflare handles this)"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Rate limiting disabled - Cloudflare handles this
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def admin_required(f):
    """Decorator that combines @login_required and @authorize.has_role('Admin')"""
    @wraps(f)
    @login_required
    @authorize.has_role('Admin')
    def decorated_function(*args, **kwargs):
        return f(*args, **kwargs)
    return decorated_function

@admin_bp.route('/')
@admin_required
def index():
    # Import admin utilities for analytics
    from app.admin_utils import get_visitors_today, get_visitors_this_week, get_top_referrers, get_top_pages, get_top_ref_codes, get_visit_trends_30d, get_total_retailers, get_kiosk_retailers, get_stores, get_card_shops, get_total_kiosks
    
    # Batch database queries for better performance
    def get_dashboard_counts():
        """Get all dashboard counts in batched queries"""
        try:
            # Get basic counts with separate queries for reliability
            total_users = db.session.query(func.count(User.id)).scalar() or 0
            total_retailers = db.session.query(func.count(Retailer.id)).scalar() or 0
            total_events = db.session.query(func.count(Event.id)).scalar() or 0
            total_messages = db.session.query(func.count(Message.id)).scalar() or 0
            
            # Get retailer type counts
            kiosk_retailers = get_kiosk_retailers()
            retail_stores = get_stores()
            indie_stores = get_card_shops()
            total_kiosks = get_total_kiosks()
            
            # Validate that total retailers equals sum of types
            calculated_total = kiosk_retailers + retail_stores + indie_stores
            if calculated_total != total_retailers:
                current_app.logger.warning(f"Retailer count mismatch: total={total_retailers}, calculated={calculated_total} (kiosk={kiosk_retailers}, stores={retail_stores}, indie={indie_stores})")
            
            # Validate that total kiosks >= kiosk retailers
            if total_kiosks < kiosk_retailers:
                current_app.logger.warning(f"Kiosk count anomaly: total_kiosks={total_kiosks}, kiosk_retailers={kiosk_retailers}")
            
            # Get role-based counts with proper join
            from app.models import roles_users
            pro_users = db.session.query(func.count(User.id)).join(roles_users).join(Role).filter(Role.name == 'Pro').scalar() or 0
            admin_users = db.session.query(func.count(User.id)).join(roles_users).join(Role).filter(Role.name == 'Admin').scalar() or 0
            active_users = total_users  # For now, consider all users as active
            
            # Get visitor analytics counts (excluding monitor traffic)
            from app.admin_utils import exclude_monitor_traffic
            unique_pages = exclude_monitor_traffic(
                db.session.query(func.count(func.distinct(VisitorLog.path)))
            ).scalar() or 0
            unique_referrers = exclude_monitor_traffic(
                db.session.query(func.count(func.distinct(VisitorLog.referrer)))
            ).filter(
                VisitorLog.referrer.isnot(None),
                VisitorLog.referrer != ''
            ).scalar() or 0
            
            return {
                'total_users': total_users,
                'total_retailers': total_retailers,
                'total_events': total_events,
                'total_messages': total_messages,
                'kiosk_retailers': kiosk_retailers,
                'retail_stores': retail_stores,
                'indie_stores': indie_stores,
                'total_kiosks': total_kiosks,
                'pro_users': pro_users,
                'admin_users': admin_users,
                'active_users': active_users,
                'unique_pages': unique_pages,
                'unique_referrers': unique_referrers
            }
        except Exception as e:
            current_app.logger.error(f"Error getting dashboard counts: {e}")
            # Return safe defaults
            return {
                'total_users': 0, 'total_retailers': 0, 'total_events': 0, 'total_messages': 0,
                'kiosk_retailers': 0, 'retail_stores': 0, 'indie_stores': 0, 'total_kiosks': 0,
                'pro_users': 0, 'admin_users': 0, 'active_users': 0,
                'unique_pages': 0, 'unique_referrers': 0
            }
    
    # Get all counts in batched queries
    counts = get_dashboard_counts()
    
    # Get visitor statistics
    try:
        visitors_today = get_visitors_today()
        visitors_this_week = get_visitors_this_week()
    except Exception:
        visitors_today = 0
        visitors_this_week = 0
    
    # Get date filter parameter (default to 30 days)
    days_filter = request.args.get('days', 30, type=int)
    if days_filter < 1 or days_filter > 60:
        days_filter = 30
    
    # Get top analytics data with date filtering
    try:
        top_referrers = get_top_referrers(limit=10, include_internal=False, days=days_filter)
        top_pages = get_top_pages(limit=10, days=days_filter)
        # Get top referral codes for dashboard
        top_ref_codes = get_top_ref_codes(limit=10, days=days_filter)
    except Exception:
        top_referrers = []
        top_pages = []
        top_ref_codes = []

    dashboard_groups = [
        ('User Statistics', [
            {'title': 'Total Users', 'value': counts['total_users'], 'summary': 'Total registered users'},
            {'title': 'Pro Users', 'value': counts['pro_users'], 'summary': 'Users with Pro subscription'},
            {'title': 'Admin Users', 'value': counts['admin_users'], 'summary': 'Administrative users'},
            {'title': 'Active Users', 'value': counts['active_users'], 'summary': 'Currently active users'}
        ]),
        ('Visitor Statistics', [
            {'title': 'Visitors Today', 'value': visitors_today, 'summary': 'Unique visitors today'},
            {'title': 'Visitors This Week', 'value': visitors_this_week, 'summary': 'Unique visitors this week'},
            {'title': 'Unique Referrers', 'value': counts['unique_referrers'], 'summary': 'Unique referrer domains'}
        ]),
        ('Content Statistics', [
            {'title': 'Total Retailers', 'value': counts['total_retailers'], 'summary': 'Total retailer locations'},
            {'title': 'Kiosk Retailers', 'value': counts['kiosk_retailers'], 'summary': 'Retailers with kiosks'},
            {'title': 'Retail Stores', 'value': counts['retail_stores'], 'summary': 'Retail store locations'},
            {'title': 'Indie Stores', 'value': counts['indie_stores'], 'summary': 'Card shop locations'},
            {'title': 'Events', 'value': counts['total_events'], 'summary': 'Total events'},
            {'title': 'Messages', 'value': counts['total_messages'], 'summary': 'Total user messages'},
            {'title': 'Unique Pages', 'value': counts['unique_pages'], 'summary': 'Unique pages visited'},
            {'title': 'Kiosks', 'value': counts['total_kiosks'], 'summary': 'Total kiosk machines'}
        ])
    ]
    
    # Get visit trends data for the chart
    try:
        visit_trends = get_visit_trends_30d()
        # Only log if there's an actual issue (not every successful operation)
        if current_app.debug and len(visit_trends) == 0:
            current_app.logger.warning("No visit trend records found")
        
        # Prepare chart data
        chart_data = {
            'labels': [trend['date'] for trend in visit_trends],
            'total': [trend['total'] for trend in visit_trends],
            'registered': [trend['pro'] for trend in visit_trends],
            'guests': [trend['guest'] for trend in visit_trends],
            'moving_average': [trend['moving_average'] for trend in visit_trends]
        }
        
        # Only log if there's an actual issue (not every successful operation)
        if current_app.debug and not visit_trends:
            current_app.logger.warning("No trend data available for chart")
        
    except Exception as e:
        current_app.logger.error(f"Error getting visit trends: {e}")
        # Fallback to empty data
        chart_data = {
            'labels': [],
            'total': [],
            'registered': [],
            'guests': []
        }
    
    return render_template('admin/dashboard.html', 
                         dashboard_groups=dashboard_groups,
                         chart_data=chart_data,
                         top_referrers=top_referrers,
                         top_pages=top_pages,
                         top_ref_codes=top_ref_codes,
                         days_filter=days_filter)

# AJAX endpoints for dynamic analytics updates
@admin_bp.route('/api/analytics/top-referrers')
@admin_required
def api_top_referrers():
    """AJAX endpoint for top referrers data."""
    days = request.args.get('days', 30, type=int)
    if days < 1 or days > 60:
        days = 30
    
    try:
        top_referrers = get_top_referrers(limit=10, include_internal=False, days=days)
        return jsonify({
            'success': True,
            'data': top_referrers,
            'days': days
        })
    except Exception as e:
        current_app.logger.error(f"Error getting top referrers: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to load referrers data'
        }), 500

@admin_bp.route('/api/analytics/top-pages')
@admin_required
def api_top_pages():
    """AJAX endpoint for top pages data."""
    days = request.args.get('days', 30, type=int)
    if days < 1 or days > 60:
        days = 30
    
    try:
        top_pages = get_top_pages(limit=10, days=days)
        return jsonify({
            'success': True,
            'data': top_pages,
            'days': days
        })
    except Exception as e:
        current_app.logger.error(f"Error getting top pages: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to load pages data'
        }), 500

@admin_bp.route('/api/analytics/top-ref-codes')
@admin_required
def api_top_ref_codes():
    """AJAX endpoint for top referral codes data."""
    days = request.args.get('days', 30, type=int)
    if days < 1 or days > 60:
        days = 30
    
    try:
        top_ref_codes = get_top_ref_codes(limit=10, days=days)
        return jsonify({
            'success': True,
            'data': top_ref_codes,
            'days': days
        })
    except Exception as e:
        current_app.logger.error(f"Error getting top referral codes: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to load referral codes data'
        }), 500

@admin_bp.route('/api/analytics/visit-trends')
@admin_required
def api_visit_trends():
    """AJAX endpoint for visit trends data."""
    days = request.args.get('days', 30, type=int)
    if days < 1 or days > 60:
        days = 30
    
    try:
        from app.admin_utils import get_visit_trends_30d
        visit_trends = get_visit_trends_30d(days=days)
        
        # Prepare chart data
        chart_data = {
            'labels': [trend['date'] for trend in visit_trends],
            'total': [trend['total'] for trend in visit_trends],
            'registered': [trend['pro'] for trend in visit_trends],
            'guests': [trend['guest'] for trend in visit_trends],
            'moving_average': [trend['moving_average'] for trend in visit_trends]
        }
        
        return jsonify({
            'success': True,
            'data': chart_data,
            'days': days
        })
    except Exception as e:
        current_app.logger.error(f"Error getting visit trends: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to load visit trends data'
        }), 500

@admin_bp.route('/api/analytics/referral-code-trends')
@admin_required
def api_referral_code_trends():
    """AJAX endpoint for referral code trends data."""
    days = request.args.get('days', 30, type=int)
    if days < 1 or days > 60:
        days = 30
    
    try:
        from app.admin_utils import get_referral_code_trends_30d
        trends = get_referral_code_trends_30d(days=days)
        
        return jsonify({
            'success': True,
            'data': trends,
            'days': days
        })
    except Exception as e:
        current_app.logger.error(f"Error getting referral code trends: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to load referral code trends data'
        }), 500

@admin_bp.route('/api/analytics/traffic-by-hour')
@admin_required
def api_traffic_by_hour():
    """AJAX endpoint for traffic by hour data."""
    days = request.args.get('days', 30, type=int)
    if days < 1 or days > 60:
        days = 30
    
    try:
        from app.admin_utils import get_traffic_by_hour
        result = get_traffic_by_hour(days=days)
        
        return jsonify({
            'success': True,
            'data': result['hourly_data'],
            'total_visits': result['total_visits'],
            'total_pro_visits': result['total_pro_visits'],
            'total_non_pro_visits': result['total_non_pro_visits'],
            'avg_visits_per_hour': result['avg_visits_per_hour'],
            'days': result['days']
        })
    except Exception as e:
        current_app.logger.error(f"Error getting traffic by hour: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to load traffic by hour data'
        }), 500

@admin_bp.route('/api/analytics/traffic-by-day-of-week')
@admin_required
def api_traffic_by_day_of_week():
    """AJAX endpoint for traffic by day of week data."""
    days = request.args.get('days', 30, type=int)
    if days < 1 or days > 60:
        days = 30
    
    try:
        from app.admin_utils import get_traffic_by_day_of_week
        result = get_traffic_by_day_of_week(days=days)
        
        return jsonify({
            'success': True,
            'data': result['daily_data'],
            'total_visits': result['total_visits'],
            'total_pro_visits': result['total_pro_visits'],
            'total_non_pro_visits': result['total_non_pro_visits'],
            'avg_visits_per_day': result['avg_visits_per_day'],
            'avg_pro_visits_per_day': result['avg_pro_visits_per_day'],
            'avg_non_pro_visits_per_day': result['avg_non_pro_visits_per_day'],
            'days': result['days']
        })
    except Exception as e:
        current_app.logger.error(f"Error getting traffic by day of week: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to load traffic by day of week data'
        }), 500

# Users routes
@admin_bp.route('/users')
@admin_required
def users():
    return render_template('admin/users.html')
@admin_bp.route('/messages/reply', methods=['POST'])
@admin_required
def reply_message():
    data = request.get_json() or {}
    msg_id = data.get('message_id')
    to_email = data.get('to')
    subject = data.get('subject')
    body = data.get('body')
    if not (msg_id and to_email and subject and body):
        return jsonify({'message': 'Missing fields'}), 400
    
    # Get the original message for context
    original_message = Message.query.get(msg_id)
    if not original_message:
        return jsonify({'message': 'Original message not found'}), 404
    
    # Clean the reply body if it accidentally contains an inline original message
    def strip_inline_original(text: str) -> str:
        if not text:
            return ''
        markers = [
            '--- Original Message ---',
            'Original Message',
            '\nOn ',
        ]
        for marker in markers:
            idx = text.find(marker)
            if idx != -1:
                return text[:idx].rstrip()
        return text

    clean_body = strip_inline_original(body)

    # Format the email with proper structure
    formatted_body_html = f"""<div style="font-family: Arial, sans-serif; line-height: 1.6;">
  <p>Thank you for your message.</p>
  <p>{clean_body.replace('\n', '<br>')}</p>
  <p>Thank you,<br>Tamermap.com Staff</p>
  <p style="color: #666; font-size: 12px;"><em>Note: This is an automated response. Please do not reply to this email as replies will not be received.</em></p>
  <hr style="border: none; border-top: 1px solid #ccc; margin: 20px 0;">
  <h4>Original Message</h4>
  <p><strong>From:</strong> {original_message.name or 'Unknown'}<br>
  <strong>Subject:</strong> {original_message.subject}<br>
  <strong>Message:</strong> {original_message.body}</p>
</div>"""

    # Plain text version with proper line breaks
    formatted_body_text = f"""Thank you for your message.

{clean_body}

Thank you,
Tamermap.com Staff

Note: This is an automated response. Please do not reply to this email as replies will not be received.

________________________________________
Original Message
From: {original_message.name or 'Unknown'}
Subject: {original_message.subject}
Message: {original_message.body}"""
    
    # Send email
    ok = send_email_with_context(subject=subject, template='email/generic', recipient=to_email, body_html=formatted_body_html, body_text=formatted_body_text)
    db.session.add(OutboundMessage(parent_message_id=msg_id, to_email=to_email, subject=subject, body=formatted_body_html, sent_by_user_id=current_user.id))
    db.session.commit()
    return jsonify({'success': bool(ok)})

@admin_bp.route('/users/bulk-email', methods=['POST'])
@admin_required
def users_bulk_email():
    data = request.get_json() or {}
    subject = data.get('subject')
    body = data.get('body')
    signature = (data.get('signature') or '').strip()
    emails = data.get('emails') or []
    if not (subject and body and emails):
        return jsonify({'message': 'Missing fields'}), 400
    job = BulkEmailJob(subject=subject, body=body, created_by_user_id=current_user.id, total_recipients=len(emails))
    db.session.add(job)
    db.session.flush()
    sent = 0
    failed = 0
    for e in emails:
        rec = BulkEmailRecipient(job_id=job.id, email=e)
        db.session.add(rec)
        try:
            # Compose with optional signature
            body_text = body + ("\n\n" + signature if signature else '')
            # Simple HTML with preserved newlines
            body_html = f"<div style=\"font-family: Arial, sans-serif; line-height:1.6;\">{body.replace('\n','<br>')}" + (f"<br><br>{signature.replace('\n','<br>')}" if signature else '') + "</div>"
            ok = send_email_with_context(subject=subject, template='email/generic', recipient=e, body_html=body_html, body_text=body_text)
            rec.status = 'sent' if ok else 'failed'
            rec.sent_at = datetime.utcnow()
            if ok:
                sent += 1
            else:
                failed += 1
        except Exception as ex:
            rec.status = 'failed'
            rec.error = str(ex)
            failed += 1
    job.sent_count = sent
    job.failed_count = failed
    db.session.commit()
    return jsonify({'success': True, 'job_id': job.id, 'sent': sent, 'failed': failed})


@admin_bp.route('/engagement')
@admin_required
def engagement():
    days = request.args.get('days', 30, type=int)
    cutoff = datetime.utcnow() - timedelta(days=days)

    # Route planner metrics
    totals_rows = db.session.query(RouteEvent.event, func.count()).filter(RouteEvent.created_at >= cutoff).group_by(RouteEvent.event).all()
    totals = {k: v for k, v in totals_rows}
    sessions_open = db.session.query(func.count(func.distinct(RouteEvent.session_id))).filter(RouteEvent.created_at >= cutoff, RouteEvent.event == 'open').scalar() or 0
    sessions_go = db.session.query(func.count(func.distinct(RouteEvent.session_id))).filter(RouteEvent.created_at >= cutoff, RouteEvent.event == 'go').scalar() or 0
    completion_rate = (sessions_go / sessions_open) if sessions_open else 0

    # Legend clicks by control (top 10)
    legend_rows = db.session.query(
        LegendClick.control_id,
        func.sum(case((LegendClick.is_pro == True, 1), else_=0)).label('pro'),
        func.sum(case((LegendClick.is_pro == False, 1), else_=0)).label('non_pro')
    ).filter(
        LegendClick.created_at >= cutoff
    ).group_by(LegendClick.control_id).order_by(func.count().desc()).limit(10).all()

    legend_data = [
        {
            'control_id': cid,
            'pro': int(pro or 0),
            'non_pro': int(non_pro or 0)
        } for cid, pro, non_pro in legend_rows
    ]

    return render_template('admin/engagement.html',
                           days=days,
                           route_totals=totals,
                           sessions_open=sessions_open,
                           sessions_go=sessions_go,
                           completion_rate=completion_rate,
                           legend_data=legend_data)

@admin_bp.route('/api/admin/engagement/legend/recent')
@admin_required
def api_engagement_legend_recent():
    days = request.args.get('days', 30, type=int)
    limit = request.args.get('limit', 200, type=int)
    cutoff = datetime.utcnow() - timedelta(days=days)
    
    rows = db.session.query(
        LegendClick.created_at,
        LegendClick.session_id,
        LegendClick.is_pro,
        LegendClick.control_id,
        LegendClick.path,
        LegendClick.zoom,
        LegendClick.center_lat,
        LegendClick.center_lng
    ).filter(
        LegendClick.created_at >= cutoff
    ).order_by(LegendClick.created_at.desc()).limit(limit).all()
    
    data = [
        {
            'created_at': r[0].strftime('%Y-%m-%d %H:%M:%S') if r[0] else '',
            'session_id': r[1],
            'is_pro': bool(r[2]),
            'control_id': r[3],
            'path': r[4],
            'zoom': r[5],
            'center_lat': r[6],
            'center_lng': r[7]
        } for r in rows
    ]
    return jsonify({ 
        'data': data,
        'timezone_info': 'All times shown in UTC (server time)'
    })

@admin_bp.route('/api/admin/engagement/stats')
@admin_required
def api_engagement_stats():
    """AJAX endpoint for engagement statistics."""
    days = request.args.get('days', 30, type=int)
    if days < 1 or days > 60:
        days = 30
    
    cutoff = datetime.utcnow() - timedelta(days=days)
    
    try:
        # Route planner metrics
        totals_rows = db.session.query(RouteEvent.event, func.count()).filter(
            RouteEvent.created_at >= cutoff
        ).group_by(RouteEvent.event).all()
        totals = {k: v for k, v in totals_rows}
        
        sessions_open = db.session.query(func.count(func.distinct(RouteEvent.session_id))).filter(
            RouteEvent.created_at >= cutoff, 
            RouteEvent.event == 'open'
        ).scalar() or 0
        
        sessions_go = db.session.query(func.count(func.distinct(RouteEvent.session_id))).filter(
            RouteEvent.created_at >= cutoff, 
            RouteEvent.event == 'go'
        ).scalar() or 0
        
        completion_rate = (sessions_go / sessions_open) if sessions_open else 0
        
        return jsonify({
            'success': True,
            'route_totals': totals,
            'sessions_open': sessions_open,
            'sessions_go': sessions_go,
            'completion_rate': completion_rate
        })
    except Exception as e:
        current_app.logger.error(f"Error getting engagement stats: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to load engagement statistics'
        }), 500

@admin_bp.route('/api/admin/engagement/legend/chart')
@admin_required
def api_engagement_legend_chart():
    """AJAX endpoint for legend click chart data."""
    days = request.args.get('days', 30, type=int)
    if days < 1 or days > 60:
        days = 30
    
    cutoff = datetime.utcnow() - timedelta(days=days)
    
    try:
        # Legend clicks by control (top 10)
        legend_rows = db.session.query(
            LegendClick.control_id,
            func.sum(case((LegendClick.is_pro == True, 1), else_=0)).label('pro'),
            func.sum(case((LegendClick.is_pro == False, 1), else_=0)).label('non_pro')
        ).filter(
            LegendClick.created_at >= cutoff
        ).group_by(LegendClick.control_id).order_by(func.count().desc()).limit(10).all()
        
        legend_data = [
            {
                'control_id': cid,
                'pro': int(pro or 0),
                'non_pro': int(non_pro or 0)
            } for cid, pro, non_pro in legend_rows
        ]
        
        return jsonify({
            'success': True,
            'data': legend_data
        })
    except Exception as e:
        current_app.logger.error(f"Error getting legend chart data: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to load legend chart data'
        }), 500

# ---------- Duplicates (place_id) admin UI ----------
@admin_bp.route('/duplicates/place-id/ui')
@admin_required
def duplicates_place_id_ui():
    """Render a simple UI to review and merge duplicate retailers by place_id."""
    dup_rows = db.session.query(
        Retailer.place_id, func.count(Retailer.id).label('count')
    ).filter(
        Retailer.place_id.isnot(None),
        Retailer.place_id.notin_(['not_found', 'api_error', 'none'])
    ).group_by(Retailer.place_id).having(func.count(Retailer.id) > 1).all()

    groups = []
    for pid, cnt in dup_rows:
        # SQLite-safe ordering: handle NULLs by coalescing to epoch
        try:
            members = Retailer.query.filter_by(place_id=pid).order_by(Retailer.last_api_update.desc()).all()
        except Exception:
            members = Retailer.query.filter_by(place_id=pid).all()
        groups.append({'place_id': pid, 'count': cnt, 'members': members})

    return render_template('admin/duplicates_place_id.html', groups=groups)

@admin_bp.route('/roles')
@admin_required
def get_roles():
    roles = Role.query.all()
    return jsonify([{'id': role.id, 'name': role.name} for role in roles])

@admin_bp.route('/users/data')
@admin_required
@rate_limit_data_tables(max_requests=20, window_seconds=60)
def users_data():
    try:
        draw = request.args.get('draw', type=int)
        start = request.args.get('start', type=int)
        length = request.args.get('length', type=int)
        search_value = request.args.get('search[value]', '')
        # Only log if there's an actual issue (not every successful operation)
        if current_app.debug and not draw:
            current_app.logger.warning("users_data called without required draw parameter")

        # Check cache first
        cache_key = get_cache_key('users_data', draw=draw, start=start, length=length, search=search_value)
        cached_response = get_cached_response(cache_key)
        if cached_response:
            return cached_response

        query = User.query

        if search_value:
            search = f"%{search_value}%"
            query = query.filter(
                (User.email.ilike(search)) |
                (User.first_name.ilike(search)) |
                (User.last_name.ilike(search))
            )

        # Handle sorting
        order_column = request.args.get('order[0][column]', type=int)
        order_dir = request.args.get('order[0][dir]', 'asc')

        # Define column mapping for sorting
        column_map = {
            0: User.email,      # Email column
            1: User.first_name, # Name column (sort by first_name)
            2: User.active,     # Active column
            3: User.last_login, # Last Login column
            4: None,            # Roles column (will handle separately)
            5: User.pro_end_date, # Is Pro column (sort by pro_end_date)
            6: None,            # Is Admin column (not sortable)
            7: None             # Actions column (not sortable)
        }

        if order_column is not None and order_column in column_map:
            if order_column == 4:  # Roles column
                # Sort by roles using a subquery
                if order_dir == 'desc':
                    query = query.outerjoin(User.roles).group_by(User.id).order_by(db.func.max(Role.name).desc())
                else:
                    query = query.outerjoin(User.roles).group_by(User.id).order_by(db.func.max(Role.name).asc())
            elif column_map[order_column] is not None:
                sort_column = column_map[order_column]
                if order_dir == 'desc':
                    sort_column = sort_column.desc()
                query = query.order_by(sort_column)
            else:
                # Default sorting by ID if no valid sort column
                query = query.order_by(User.id)
        else:
            # Default sorting by ID if no valid sort column
            query = query.order_by(User.id)

        total_records = query.count()
        users = query.offset(start).limit(length).all()
        
        # Only log if there's an actual issue (not every successful operation)
        if current_app.debug and total_records == 0:
            current_app.logger.warning("No users found matching criteria")

        data = []
        for user in users:
            try:
                # Get user roles as a comma-separated string
                roles = ', '.join([role.name for role in user.roles]) if user.roles else 'User'
                data.append({
                    'id': user.id,
                    'name': f"{user.first_name or ''} {user.last_name or ''}".strip() or 'N/A',
                    'email': user.email,
                    'active': 'Yes' if user.active else 'No',
                    'last_login': convert_utc_to_pacific_time(user.last_login) if user.last_login else 'Never',
                    'roles': roles,
                    'is_pro': 'Yes' if user.has_role('Pro') else 'No',
                    'is_admin': 'Yes' if any(role.name == 'Admin' for role in user.roles) else 'No',
                    'actions': f'<button class="btn btn-sm btn-primary edit-user-btn" data-id="{user.id}">Edit</button> <button class="btn btn-sm btn-danger delete-user-btn" data-id="{user.id}">Delete</button>'
                })
            except Exception as e:
                # Log actual errors, not debug info
                current_app.logger.error(f"Error processing user {user.id}: {e}")
                continue

        # Only log if there's an actual issue (not every successful operation)
        if current_app.debug and len(data) == 0:
            current_app.logger.warning("No user data to return")

        response_data = {
            'draw': draw,
            'recordsTotal': User.query.count(),
            'recordsFiltered': total_records,
            'data': data
        }
        
        # Cache the response
        cache_response(cache_key, response_data)
        
        return jsonify(response_data)

    except Exception as e:
        current_app.logger.error(f"users_data route failed: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Failed to load users data'}), 500

@admin_bp.route('/users/<int:id>', methods=['GET'])
@admin_required
def get_user(id):
    user = User.query.get_or_404(id)
    return jsonify({
        'id': user.id,
        'first_name': user.first_name,
        'last_name': user.last_name,
        'email': user.email,
        'active': user.active,
        'pro_end_date': user.pro_end_date.isoformat() if user.pro_end_date else None,
        'last_login': convert_utc_to_pacific_time(user.last_login) if user.last_login else None,
        'login_count': user.login_count,
        'cust_id': user.cust_id,
        'canceled_at': user.canceled_at.isoformat() if user.canceled_at else None,
        'cancellation_reason': user.cancellation_reason,
        'cancellation_comment': user.cancellation_comment,
        'roles': [role.name for role in user.roles]
    })

@admin_bp.route('/users/<int:id>', methods=['PUT'])
@admin_required
def update_user(id):
    user = User.query.get_or_404(id)
    data = request.get_json()
    
    # Update basic fields
    if 'first_name' in data:
        user.first_name = data['first_name']
    if 'last_name' in data:
        user.last_name = data['last_name']
    if 'email' in data:
        user.email = data['email']
    if 'active' in data:
        user.active = bool(int(data['active']))
    if 'password' in data and data['password']:
        # Basic strength check: min 8 chars, upper/lower/digit
        pw = data['password']
        if len(pw) < 8 or not any(c.islower() for c in pw) or not any(c.isupper() for c in pw) or not any(c.isdigit() for c in pw):
            return jsonify({'error': 'Password must be at least 8 chars and include upper, lower, and a number'}), 400
        user.password = utils.encrypt_password(pw)
    
    # Handle Pro end date
    if 'pro_end_date' in data:
        if data['pro_end_date']:
            try:
                user.pro_end_date = datetime.strptime(data['pro_end_date'], '%Y-%m-%d')
            except ValueError:
                return jsonify({'error': 'Invalid pro_end_date format'}), 400
        else:
            user.pro_end_date = None
    
    # Handle cancellation fields
    if 'canceled_at' in data:
        if data['canceled_at']:
            try:
                user.canceled_at = datetime.strptime(data['canceled_at'], '%Y-%m-%d')
            except ValueError:
                return jsonify({'error': 'Invalid canceled_at format'}), 400
        else:
            user.canceled_at = None
    
    if 'cancellation_reason' in data:
        user.cancellation_reason = data['cancellation_reason']
    if 'cancellation_comment' in data:
        user.cancellation_comment = data['cancellation_comment']
    
    # Handle roles
    if 'roles' in data:
        # Clear existing roles
        user.roles = []
        # Add new roles
        for role_name in data['roles']:
            role = Role.query.filter_by(name=role_name).first()
            if role:
                user.roles.append(role)
    
    db.session.commit()
    return jsonify({'message': 'User updated successfully'})

@admin_bp.route('/users/<int:id>', methods=['DELETE'])
@admin_required
def delete_user(id):
    user = User.query.get_or_404(id)
    db.session.delete(user)
    db.session.commit()
    return jsonify({'message': 'User deleted successfully'})

@admin_bp.route('/users/add', methods=['POST'])
@admin_required
def add_user():
    data = request.get_json()
    
    # Check if user with this email already exists
    if User.query.filter_by(email=data['email']).first():
        return jsonify({'errors': {'email': 'User with this email already exists'}}), 400
    
    # Create new user
    # Validate password
    pw = data.get('password', '')
    current_app.logger.info(f"Creating user with email: {data['email']}, password length: {len(pw)}")
    
    if len(pw) < 8 or not any(c.islower() for c in pw) or not any(c.isupper() for c in pw) or not any(c.isdigit() for c in pw):
        current_app.logger.warning(f"Password validation failed for user {data['email']}: length={len(pw)}, has_lower={any(c.islower() for c in pw)}, has_upper={any(c.isupper() for c in pw)}, has_digit={any(c.isdigit() for c in pw)}")
        return jsonify({'errors': {'password': 'Password must be at least 8 chars and include upper, lower, and a number'}}), 400

    hashed_password = generate_password_hash(pw)
    current_app.logger.info(f"Password hashed successfully for user {data['email']}, hash length: {len(hashed_password)}")

    user = User(
        first_name=data.get('first_name'),
        last_name=data.get('last_name'),
        email=data['email'],
        password=hashed_password,
        active=bool(int(data.get('active', 1)))
    )
    
    # Handle Pro end date
    if data.get('pro_end_date'):
        try:
            user.pro_end_date = datetime.strptime(data['pro_end_date'], '%Y-%m-%d')
        except ValueError:
            return jsonify({'errors': {'pro_end_date': 'Invalid date format'}}), 400
    
    # Handle roles
    if 'roles' in data:
        for role_name in data['roles']:
            role = Role.query.filter_by(name=role_name).first()
            if role:
                user.roles.append(role)
    
    db.session.add(user)
    current_app.logger.info(f"User object added to session for {data['email']}")
    
    try:
        db.session.commit()
        current_app.logger.info(f"User successfully committed to database: {data['email']}, ID: {user.id}")
        return jsonify({'message': 'User created successfully'})
    except Exception as e:
        current_app.logger.error(f"Failed to commit user {data['email']} to database: {e}")
        db.session.rollback()
        return jsonify({'errors': {'database': 'Failed to save user to database'}}), 500

@admin_bp.route('/users/edit/<int:id>', methods=['PUT'])
@admin_required
def edit_user(id):
    return update_user(id)



# Retailers routes
@admin_bp.route('/retailers')
@admin_required
def retailers():
    return render_template('admin/retailers.html')

@admin_bp.route('/retailers/data')
@admin_required
@rate_limit_data_tables(max_requests=20, window_seconds=60)
def retailers_data():
    try:
        # Get DataTables parameters
        draw = request.args.get('draw', type=int)
        start = request.args.get('start', type=int)
        length = request.args.get('length', type=int)
        search_value = request.args.get('search[value]', '')

        # Only log if there's an actual issue (not every successful operation)
        if current_app.debug and not draw:
            current_app.logger.warning("retailers_data called without required draw parameter")

        # Build the query
        query = Retailer.query

        if search_value:
            search = f"%{search_value}%"
            query = query.filter(
                (Retailer.retailer.ilike(search)) |
                (Retailer.full_address.ilike(search)) |
                (Retailer.phone_number.ilike(search)) |
                (Retailer.retailer_type.ilike(search))
            )

        # Handle sorting
        order_column = request.args.get('order[0][column]', type=int)
        order_dir = request.args.get('order[0][dir]', 'asc')

        # Define column mapping for sorting
        column_map = {
            0: Retailer.retailer,       # Name column
            1: Retailer.retailer_type,  # Type column
            2: Retailer.full_address,   # Address column
            3: Retailer.phone_number,   # Phone column
            4: Retailer.machine_count,  # Machine Count column
            5: Retailer.enabled,        # Active column (sortable by enabled field)
            6: None                     # Actions column (not sortable)
        }

        if order_column is not None and order_column in column_map and column_map[order_column] is not None:
            sort_column = column_map[order_column]
            if order_dir == 'desc':
                sort_column = sort_column.desc()
            query = query.order_by(sort_column)
        else:
            # Default sorting by name
            query = query.order_by(Retailer.retailer)

        total_records = query.count()
        retailers = query.offset(start).limit(length).all()
        
        # Only log if there's an actual issue (not every successful operation)
        if current_app.debug and total_records == 0:
            current_app.logger.warning("No retailers found matching criteria")

        data = []
        for retailer in retailers:
            # Use the existing 'enabled' field for active/inactive state
            is_enabled = retailer.enabled if hasattr(retailer, 'enabled') else True
            current_status = 'True' if is_enabled else 'False'
            
            # Inline status dropdown - True/False only
            status_options = ['True', 'False']
            options_html = ''.join([
                f'<option value="{opt}" {"selected" if current_status==opt else ""}>{opt}</option>' for opt in status_options
            ])
            status_select = f'<select class="form-select form-select-sm retailer-status-select" data-id="{retailer.id}" data-current="{current_status}">{options_html}</select>'

            data.append({
                'id': retailer.id,
                'name': retailer.retailer,
                'address': retailer.full_address,
                'phone': retailer.phone_number or '',
                'retailer_type': retailer.retailer_type or '',
                'machine_count': retailer.machine_count or 0,
                'active': status_select,
                'active_value': current_status,
                'actions': f'''<button class="btn btn-sm btn-primary edit-retailer-btn" data-id="{retailer.id}">Edit</button> 
                              <button class="btn btn-sm btn-danger delete-retailer-btn" data-id="{retailer.id}" data-name="{retailer.retailer or 'Unknown'}">Delete</button>'''
            })

        # Only log if there's an actual issue (not every successful operation)
        if current_app.debug and len(data) == 0:
            current_app.logger.warning("No retailer data to return")

        response_data = {
            'draw': draw,
            'recordsTotal': total_records,
            'recordsFiltered': total_records,
            'data': data
        }

        return jsonify(response_data)

    except Exception as e:
        current_app.logger.error(f"retailers_data route failed: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Failed to load retailers data'}), 500

@admin_bp.route('/retailers/<int:id>', methods=['GET'])
@admin_required
def get_retailer(id):
    retailer = Retailer.query.get_or_404(id)
    return jsonify({
        'id': retailer.id,
        'retailer': retailer.retailer,
        'retailer_type': retailer.retailer_type,
        'full_address': retailer.full_address,
        'latitude': retailer.latitude,
        'longitude': retailer.longitude,
        'place_id': retailer.place_id,
        'first_seen': retailer.first_seen.isoformat() if retailer.first_seen else None,
        'phone_number': retailer.phone_number,
        'website': retailer.website,
        'opening_hours': retailer.opening_hours,
        'rating': retailer.rating,
        'last_api_update': retailer.last_api_update.isoformat() if retailer.last_api_update else None,
        'machine_count': retailer.machine_count,
        'previous_count': retailer.previous_count,
        'status': retailer.status,
        'enabled': retailer.enabled
    })

@admin_bp.route('/retailers/<int:id>', methods=['PUT'])
@admin_required
def update_retailer(id):
    retailer = Retailer.query.get_or_404(id)
    data = request.get_json()
    
    # Update allowed fields
    allowed_fields = [
        'retailer', 'retailer_type', 'full_address', 'latitude', 'longitude',
        'place_id', 'phone_number', 'website', 'opening_hours', 'rating',
        'machine_count', 'status', 'enabled'
    ]
    
    for key, value in data.items():
        if key in allowed_fields and hasattr(retailer, key):
            # Convert numeric fields appropriately
            if key in ['latitude', 'longitude', 'rating'] and value:
                try:
                    setattr(retailer, key, float(value))
                except (ValueError, TypeError):
                    setattr(retailer, key, None)
            elif key in ['machine_count'] and value:
                try:
                    setattr(retailer, key, int(value))
                except (ValueError, TypeError):
                    setattr(retailer, key, 0)
            elif key == 'enabled':
                # Convert boolean field
                setattr(retailer, key, bool(value))
            else:
                setattr(retailer, key, value if value else None)
    
    retailer.last_api_update = datetime.utcnow()
    db.session.commit()
    return jsonify({'message': 'Retailer updated successfully'})

@admin_bp.route('/retailers/<int:id>', methods=['DELETE'])
@admin_required
def delete_retailer(id):
    retailer = Retailer.query.get_or_404(id)
    db.session.delete(retailer)
    db.session.commit()
    return jsonify({'message': 'Retailer deleted successfully'})

@admin_bp.route('/retailers/add', methods=['POST'])
@admin_required
def add_retailer():
    data = request.get_json()
    
    # Validate required fields
    if not data.get('retailer'):
        return jsonify({'message': 'Retailer name is required'}), 400
    if not data.get('full_address'):
        return jsonify({'message': 'Full address is required'}), 400
    
    try:
        # Create new retailer with proper type conversion
        retailer = Retailer(
            retailer=data.get('retailer'),
            retailer_type=data.get('retailer_type'),
            full_address=data.get('full_address'),
            latitude=float(data.get('latitude')) if data.get('latitude') else None,
            longitude=float(data.get('longitude')) if data.get('longitude') else None,
            place_id=data.get('place_id'),
            phone_number=data.get('phone_number'),
            website=data.get('website'),
            opening_hours=data.get('opening_hours'),
            rating=float(data.get('rating')) if data.get('rating') else None,
            machine_count=int(data.get('machine_count', 0)),
            status=data.get('status'),
            enabled=data.get('enabled', True),  # Default to True for new retailers
            active=data.get('active', True),    # Default to True for new retailers
            first_seen=datetime.utcnow()
        )
        
        db.session.add(retailer)
        db.session.commit()
        return jsonify({'message': 'Retailer created successfully', 'id': retailer.id})
        
    except ValueError as e:
        return jsonify({'message': f'Invalid data format: {str(e)}'}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': f'Error creating retailer: {str(e)}'}), 500

@admin_bp.route('/retailers/edit/<int:id>', methods=['PUT'])
@admin_required
def edit_retailer(id):
    return update_retailer(id)


# -------------------- Place ID duplicate tools --------------------

@admin_bp.route('/duplicates/place-id', methods=['GET'])
@admin_required
def list_place_id_duplicates():
    """List duplicate retailers grouped by place_id (excluding placeholders)."""
    rows = db.session.query(
        Retailer.place_id, func.count(Retailer.id).label('count')
    ).filter(
        Retailer.place_id.isnot(None),
        Retailer.place_id.notin_(['not_found', 'api_error', 'none'])
    ).group_by(Retailer.place_id).having(func.count(Retailer.id) > 1).all()

    result = []
    for pid, cnt in rows:
        members = Retailer.query.filter_by(place_id=pid).all()
        result.append({
            'place_id': pid,
            'count': cnt,
            'members': [
                {
                    'id': r.id,
                    'retailer': r.retailer,
                    'retailer_type': r.retailer_type,
                    'full_address': r.full_address,
                    'latitude': r.latitude,
                    'longitude': r.longitude,
                    'opening_hours': bool(r.opening_hours),
                    'phone_number': bool(r.phone_number),
                    'website': bool(r.website),
                    'last_api_update': r.last_api_update.isoformat() if r.last_api_update else None,
                    'enabled': r.enabled,
                } for r in members
            ]
        })

    return jsonify(result)

@admin_bp.route('/duplicates/place-id/preview', methods=['POST'])
@admin_required
def preview_place_id_merge():
    """Preview the result of merging duplicate retailers by place_id.
    
    Body: { place_id: "...", master_id: "..." }
    Returns: Preview of the final merged record
    """
    try:
        data = request.get_json(silent=True) or {}
        current_app.logger.info(f"Preview request data: {data}")
        
        pid = (data.get('place_id') or '').strip()
        master_id = data.get('master_id')
        
        if not pid:
            current_app.logger.warning(f"Missing place_id in preview request: {data}")
            return jsonify({'message': 'place_id is required'}), 400
        if not master_id:
            current_app.logger.warning(f"Missing master_id in preview request: {data}")
            return jsonify({'message': 'master_id is required'}), 400
        
        # Convert master_id to integer for database comparison
        try:
            master_id = int(master_id)
        except (ValueError, TypeError):
            current_app.logger.error(f"Invalid master_id format: {master_id}")
            return jsonify({'message': 'Invalid master_id format'}), 400

        current_app.logger.info(f"Looking for duplicates with place_id: {pid}")
        members = Retailer.query.filter_by(place_id=pid).all()
        current_app.logger.info(f"Found {len(members)} records with place_id {pid}")
        
        if len(members) <= 1:
            current_app.logger.info(f"No duplicates to merge for place_id: {pid}")
            return jsonify({'message': 'No duplicates to merge', 'place_id': pid})

        # Find the master record
        master = next((m for m in members if m.id == master_id), None)
        if not master:
            current_app.logger.error(f"Master record {master_id} not found for place_id {pid}")
            return jsonify({'message': 'Master record not found'}), 400

        current_app.logger.info(f"Building preview for master record {master_id}")
        
        # Build the preview by merging data from all records
        preview = {}
        sources = {}
        
        # Start with master record data
        preview['retailer'] = master.retailer
        preview['retailer_type'] = master.retailer_type
        preview['full_address'] = master.full_address
        preview['coordinates'] = f"{master.latitude:.5f}, {master.longitude:.5f}" if master.latitude and master.longitude else None
        preview['phone_number'] = master.phone_number
        preview['website'] = master.website
        preview['opening_hours'] = master.opening_hours
        preview['last_api_update'] = master.last_api_update.strftime('%Y-%m-%d %H:%M') if master.last_api_update else None
        preview['enabled'] = 'Yes' if master.enabled else 'No'
        
        # Track sources for each field
        sources['retailer'] = master.id
        sources['retailer_type'] = master.id
        sources['full_address'] = master.id
        sources['coordinates'] = master.id
        sources['phone_number'] = master.id
        sources['website'] = master.id
        sources['opening_hours'] = master.id
        sources['last_api_update'] = master.id
        sources['enabled'] = master.id
        
        # Merge retailer_type from all records
        types = set()
        for r in members:
            if r.retailer_type:
                for t in str(r.retailer_type).lower().split('+'):
                    t = t.strip()
                    if t:
                        types.add(t)
        if types:
            preview['retailer_type'] = ' + '.join(sorted(types))
            # Source is the first record that contributed to the merged type
            sources['retailer_type'] = 'merged'
        
        # Merge other fields conservatively (keep best data)
        for field, source_field in [
            ('phone_number', 'phone_number'),
            ('website', 'website'), 
            ('opening_hours', 'opening_hours')
        ]:
            if not preview[field] or preview[field] == '—':
                # Find best available value from other records
                for r in members:
                    if r.id != master.id and getattr(r, source_field):
                        preview[field] = getattr(r, source_field) if source_field != 'opening_hours' else '✓'
                        sources[field] = r.id
                        break
        
        # Handle coordinates specially
        if not preview['coordinates'] or preview['coordinates'] == 'None':
            for r in members:
                if r.id != master.id and r.latitude and r.longitude:
                    preview['coordinates'] = f"{r.latitude:.5f}, {r.longitude:.5f}"
                    sources['coordinates'] = r.id
                    break
        
        # Handle address specially
        if not preview['full_address'] or preview['full_address'] == '—':
            for r in members:
                if r.id != master.id and r.full_address:
                    preview['full_address'] = r.full_address
                    sources['full_address'] = r.id
                    break
        
        # Handle retailer name specially
        if not preview['retailer'] or preview['retailer'] == '—':
            for r in members:
                if r.id != master.id and r.retailer:
                    preview['retailer'] = r.retailer
                    sources['retailer'] = r.id
                    break
        
        # Handle enabled status (if any are enabled, keep enabled)
        if any(r.enabled for r in members):
            preview['enabled'] = 'Yes'
            # Source is the first enabled record
            for r in members:
                if r.enabled:
                    sources['enabled'] = r.id
                    break
        
        # Handle last API update (keep most recent)
        latest_update = None
        latest_record = None
        for r in members:
            if r.last_api_update and (not latest_update or r.last_api_update > latest_update):
                latest_update = r.last_api_update
                latest_record = r
        
        if latest_update:
            preview['last_api_update'] = latest_update.strftime('%Y-%m-%d %H:%M')
            sources['last_api_update'] = latest_record.id
        
        result = {
            'place_id': pid,
            'master_id': master_id,
            'sources': sources,
            **preview
        }
        
        current_app.logger.info(f"Preview generated successfully for place_id {pid}")
        return jsonify(result)
        
    except Exception as e:
        current_app.logger.error(f"Error in preview_place_id_merge: {str(e)}", exc_info=True)
        return jsonify({'message': f'Internal server error: {str(e)}'}), 500

@admin_bp.route('/duplicates/place-id/merge', methods=['POST'])
@admin_required
def merge_place_id_duplicates():
    """Merge kiosk/store duplicates sharing the same place_id.

    Body: { place_id: "...", master_id: "..." }
    """
    data = request.get_json(silent=True) or {}
    pid = (data.get('place_id') or '').strip()
    master_id = data.get('master_id')
    
    if not pid:
        return jsonify({'message': 'place_id is required'}), 400
    if not master_id:
        return jsonify({'message': 'master_id is required'}), 400
    
    # Convert master_id to integer for database comparison
    try:
        master_id = int(master_id)
    except (ValueError, TypeError):
        return jsonify({'message': 'Invalid master_id format'}), 400

    members = Retailer.query.filter_by(place_id=pid).all()
    if len(members) <= 1:
        return jsonify({'message': 'No duplicates to merge', 'place_id': pid})

    # Find the master record
    master = next((m for m in members if m.id == master_id), None)
    if not master:
        return jsonify({'message': 'Master record not found'}), 400

    # Merge retailer_type from all records
    types = set()
    for r in members:
        if r.retailer_type:
            for t in str(r.retailer_type).lower().split('+'):
                t = t.strip()
                if t:
                    types.add(t)
    if types:
        master.retailer_type = ' + '.join(sorted(types))

    # Merge other fields conservatively (keep best data)
    if not master.phone_number:
        master.phone_number = next((r.phone_number for r in members if r.phone_number), None)
    if not master.website:
        master.website = next((r.website for r in members if r.website), None)
    if not master.opening_hours:
        master.opening_hours = next((r.opening_hours for r in members if r.opening_hours), None)
    if not master.full_address:
        master.full_address = next((r.full_address for r in members if r.full_address), None)
    if not master.retailer:
        master.retailer = next((r.retailer for r in members if r.retailer), None)
    
    # Handle coordinates (keep best available)
    if not master.latitude or not master.longitude:
        for r in members:
            if r.latitude and r.longitude:
                master.latitude = r.latitude
                master.longitude = r.longitude
                break
    
    # Handle enabled status (if any are enabled, keep enabled)
    if any(r.enabled for r in members):
        master.enabled = True
    
    # Handle last API update (keep most recent)
    latest_update = max([r.last_api_update for r in members if r.last_api_update] or [master.last_api_update])
    if latest_update:
        master.last_api_update = latest_update
    
    # Handle first seen (keep earliest)
    first_seen = min([r.first_seen for r in members if r.first_seen] or [master.first_seen])
    if first_seen:
        master.first_seen = first_seen
    
    # Handle machine count (keep highest)
    max_machines = max([r.machine_count or 0 for r in members])
    master.machine_count = max_machines
    
    # Delete duplicate records
    to_delete = [r for r in members if r.id != master.id]
    deleted_ids = []
    
    for r in to_delete:
        deleted_ids.append(r.id)
        db.session.delete(r)

    db.session.commit()

    return jsonify({
        'message': 'merged', 
        'place_id': pid, 
        'kept_id': master.id, 
        'deleted_ids': deleted_ids
    })

# Events routes
@admin_bp.route('/events')
@admin_required
def events():
    return render_template('admin/events.html')

@admin_bp.route('/events/data')
@admin_required
@rate_limit_data_tables(max_requests=20, window_seconds=60)
def events_data():
    draw = request.args.get('draw', type=int)
    start = request.args.get('start', type=int)
    length = request.args.get('length', type=int)
    search_value = request.args.get('search[value]', '')
    future_only = request.args.get('future_only', 'false').lower() == 'true'
    
    # Handle sorting
    order_column = request.args.get('order[0][column]', type=int)
    order_dir = request.args.get('order[0][dir]', 'asc')
    
    # Column mapping for sorting (based on the template columns)
    column_map = {
        0: Event.event_title,  # Title
        1: Event.full_address, # Address
        2: Event.start_date,   # Start Date
        3: Event.start_time,   # Start Time
        4: Event.end_date,     # End Date
        5: Event.end_time      # End Time
        # Actions column (6) is not sortable
    }
    
    query = Event.query
    
    # Apply future events filter if requested
    if future_only:
        today = datetime.utcnow().date()
        query = query.filter(Event.start_date >= today)
    
    if search_value:
        search = f"%{search_value}%"
        query = query.filter(
            (Event.event_title.ilike(search)) |
            (Event.full_address.ilike(search)) |
            (Event.email.ilike(search)) |
            (Event.phone.ilike(search))
        )
    
    # Apply sorting
    if order_column is not None and order_column in column_map:
        sort_column = column_map[order_column]
        if order_dir == 'desc':
            sort_column = sort_column.desc()
        query = query.order_by(sort_column)
    else:
        query = query.order_by(Event.event_title.asc())  # Default sort by title ascending
    
    total_records = query.count()
    events = query.offset(start).limit(length).all()
    
    data = []
    for event in events:
        data.append({
            'id': event.id,
            'event_title': event.event_title,
            'full_address': event.full_address,
            'start_date': event.start_date,
            'start_time': event.start_time,
            'end_date': event.end_date.strftime('%Y-%m-%d') if event.end_date else None,
            'end_time': event.end_time.strftime('%H:%M') if event.end_time else None,
            'registration_url': event.registration_url,
            'price': event.price,
            'email': event.email,
            'phone': event.phone,
            'timestamp': event.timestamp.strftime('%Y-%m-%d %H:%M:%S') if event.timestamp else None,
            'first_seen': event.first_seen,
            'actions': f'''<button class="btn btn-sm btn-primary edit-event-btn" data-id="{event.id}">Edit</button> 
                          <button class="btn btn-sm btn-danger delete-event-btn" data-id="{event.id}" data-name="{event.event_title or 'Unknown'}">Delete</button>'''
        })
    
    return jsonify({
        'draw': draw,
        'recordsTotal': total_records,
        'recordsFiltered': total_records,
        'data': data
    })

@admin_bp.route('/events/<int:id>', methods=['GET'])
@admin_required
def get_event(id):
    """Get individual event data for editing."""
    try:
        event = Event.query.get_or_404(id)
        return jsonify({
            'id': event.id,
            'event_title': event.event_title,
            'full_address': event.full_address,
            'start_date': event.start_date,
            'start_time': event.start_time,
            'end_date': event.end_date.strftime('%Y-%m-%d') if event.end_date else None,
            'end_time': event.end_time.strftime('%H:%M') if event.end_time else None,
            'registration_url': event.registration_url,
            'price': event.price,
            'email': event.email,
            'phone': event.phone
        })
    except Exception as e:

        return jsonify({'error': str(e)}), 500

@admin_bp.route('/events/<int:id>', methods=['PUT'])
@admin_required
def update_event(id):
    event = Event.query.get_or_404(id)
    data = request.get_json()

    try:
        # Handle datetime fields specially
        for key, value in data.items():
            if hasattr(event, key):
                if key == 'end_date':
                    # Convert empty string or null to None for datetime fields
                    if value is None or not value or (isinstance(value, str) and value.strip() == ''):
                        setattr(event, key, None)
                    else:
                        try:
                            # Try to parse as datetime
                            parsed_date = datetime.strptime(value, '%Y-%m-%d')
                            setattr(event, key, parsed_date)
                        except ValueError:
                            setattr(event, key, None)
                elif key == 'end_time':
                    # Convert empty string or null to None for time fields
                    if value is None or not value or (isinstance(value, str) and value.strip() == ''):
                        setattr(event, key, None)
                    else:
                        try:
                            # Try to parse as time
                            parsed_time = datetime.strptime(value, '%H:%M').time()
                            setattr(event, key, parsed_time)
                        except ValueError:
                            setattr(event, key, None)
                elif key == 'price':
                    # Handle price field conversion
                    if value is None or not value or (isinstance(value, str) and value.strip() == ''):
                        setattr(event, key, None)
                    else:
                        try:
                            setattr(event, key, float(value))
                        except ValueError:
                            setattr(event, key, None)
                else:
                    # Handle other fields normally, but convert empty strings to None for optional fields
                    if key in ['registration_url', 'email', 'phone'] and (value is None or value == ''):
                        setattr(event, key, None)
                    else:
                        setattr(event, key, value)
        db.session.commit()
        return jsonify({'message': 'Event updated successfully'})
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error updating event {id}: {str(e)}")
        return jsonify({'error': f'Failed to update event: {str(e)}'}), 500

@admin_bp.route('/events/<int:id>', methods=['DELETE'])
@admin_required
def delete_event(id):
    event = Event.query.get_or_404(id)
    db.session.delete(event)
    db.session.commit()
    return jsonify({'success': True})

@admin_bp.route('/events/add', methods=['POST'])
@admin_required
def add_event():
    data = request.get_json()
    
    try:
        # Parse end_date and end_time safely
        end_date = None
        end_time = None
        
        end_date_value = data.get('end_date')
        if end_date_value is not None and str(end_date_value).strip():
            try:
                end_date = datetime.strptime(str(end_date_value), '%Y-%m-%d')
            except ValueError:
                end_date = None
        
        end_time_value = data.get('end_time')
        if end_time_value is not None and str(end_time_value).strip():
            try:
                end_time = datetime.strptime(str(end_time_value), '%H:%M').time()
            except ValueError:
                end_time = None
        
        # Handle price field
        price = None
        price_value = data.get('price')
        if price_value is not None and str(price_value).strip():
            try:
                price = float(price_value)
            except ValueError:
                price = None
        
        # Handle optional string fields
        registration_url = data.get('registration_url')
        if registration_url == '':
            registration_url = None
            
        email = data.get('email')
        if email == '':
            email = None
            
        phone = data.get('phone')
        if phone == '':
            phone = None
        
        # Create new event
        event = Event(
            event_title=data.get('event_title'),
            full_address=data.get('full_address'),
            start_date=data.get('start_date'),
            start_time=data.get('start_time'),
            end_date=end_date,
            end_time=end_time,
            registration_url=registration_url,
            price=price,
            email=email,
            phone=phone
        )
        
        db.session.add(event)
        db.session.commit()
        return jsonify({'message': 'Event created successfully'})
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error creating event: {str(e)}")
        return jsonify({'error': 'Failed to create event'}), 500

@admin_bp.route('/events/edit/<int:id>', methods=['PUT'])
@admin_required
def edit_event(id):
    return update_event(id)

@admin_bp.route('/events/stats')
@admin_required
def events_stats():
    """Get statistics for future events."""
    from app.admin_utils import get_future_events_stats
    stats = get_future_events_stats()
    return jsonify(stats)

# Messages routes
@admin_bp.route('/messages')
@admin_required
def messages():
    return render_template('admin/messages.html')

@admin_bp.route('/messages/data')
@admin_required
@rate_limit_data_tables(max_requests=50, window_seconds=60)
def messages_data():
    draw = request.args.get('draw', type=int)
    start = request.args.get('start', type=int)
    length = request.args.get('length', type=int)
    search_value = request.args.get('search[value]', '')
    
    # Handle sorting
    order_column = request.args.get('order[0][column]', type=int)
    order_dir = request.args.get('order[0][dir]', 'desc')
    
    # Column mapping for sorting (based on the template columns)
    column_map = {
        0: None,  # Checkbox column (not sortable)
        1: Message.id,  # ID
        2: Message.email,  # Email
        3: Message.communication_type,  # Type
        4: Message.subject,  # Subject
        5: Message.body,  # Body
        6: Message.timestamp,  # Timestamp
        7: Message.read,  # Read
        8: None  # Actions column (not sortable)
    }
    
    query = Message.query
    
    if search_value:
        search = f"%{search_value}%"
        query = query.filter(
            (Message.name.ilike(search)) |
            (Message.email.ilike(search)) |
            (Message.subject.ilike(search))
        )
    
    # Apply sorting
    if order_column is not None and order_column in column_map and column_map[order_column] is not None:
        sort_column = column_map[order_column]
        if order_dir == 'desc':
            sort_column = sort_column.desc()
        query = query.order_by(sort_column)
    else:
        # Default sorting by timestamp descending (newest first)
        query = query.order_by(Message.timestamp.desc())
    
    total_records = query.count()
    messages = query.offset(start).limit(length).all()
    
    data = []
    for message in messages:
        # Truncate subject and body to 40 characters for display
        subject_display = message.subject[:40] + '...' if message.subject and len(message.subject) > 40 else message.subject
        body_display = message.body[:40] + '...' if message.body and len(message.body) > 40 else message.body
        
        # Convert UTC timestamp to Pacific time
        pacific_timestamp = None
        if message.timestamp:
            try:
                from zoneinfo import ZoneInfo
                pacific_tz = ZoneInfo("America/Los_Angeles")
                utc_time = message.timestamp.replace(tzinfo=ZoneInfo("UTC"))
                pacific_time = utc_time.astimezone(pacific_tz)
                pacific_timestamp = pacific_time.strftime('%Y-%m-%d %H:%M:%S')
            except ImportError:
                try:
                    import pytz
                    pacific_tz = pytz.timezone("America/Los_Angeles")
                    utc_time = pytz.utc.localize(message.timestamp)
                    pacific_time = utc_time.astimezone(pacific_tz)
                    pacific_timestamp = pacific_time.strftime('%Y-%m-%d %H:%M:%S')
                except ImportError:
                    # Fallback to UTC if timezone libraries not available
                    pacific_timestamp = message.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')
        
        data.append({
            'id': message.id,
            'email': message.email,
            'communication_type': message.communication_type,
            'subject': subject_display,
            'body': body_display,
            'timestamp': pacific_timestamp,
            'read': 'Yes' if message.read else 'No',
            'actions': (
                f'<button class="btn btn-sm btn-info view-message-btn me-1" data-id="{message.id}">View</button>'
                f'<button class="btn btn-sm btn-secondary reply-message-btn me-1" data-id="{message.id}">Reply</button>'
                f'<button class="btn btn-sm btn-primary edit-message-btn me-1" data-id="{message.id}">Edit</button>'
                f'<button class="btn btn-sm btn-danger delete-message-btn" data-id="{message.id}">Delete</button>'
            )
        })
    
    return jsonify({
        'draw': draw,
        'recordsTotal': total_records,
        'recordsFiltered': total_records,
        'data': data
    })

@admin_bp.route('/messages/<int:id>', methods=['GET'])
@admin_required
def get_message(id):
    message = Message.query.get_or_404(id)
    sender_email = None
    if message.sender_id:
        user = User.query.get(message.sender_id)
        if user:
            sender_email = user.email
    return jsonify({
        'id': message.id,
        'sender_id': message.sender_id,
        'sender_email': sender_email or '',
        'communication_type': message.communication_type,
        'subject': message.subject,
        'body': message.body,
        'reported_address': message.reported_address,
        'reported_phone': message.reported_phone,
        'reported_website': message.reported_website,
        'reported_hours': message.reported_hours,
        'out_of_business': message.out_of_business,
        'is_new_location': message.is_new_location,
        'is_admin_report': message.is_admin_report,
        'read': message.read,
        'name': message.name,
        'address': message.address,
        'email': message.email,
        'timestamp': message.timestamp.strftime('%Y-%m-%d %H:%M') if message.timestamp else '',
        # Post Wins fields
        'win_type': message.win_type,
        'location_used': message.location_used,
        'cards_found': message.cards_found,
        'time_saved': message.time_saved,
        'money_saved': message.money_saved,
        'allow_feature': message.allow_feature
    })

@admin_bp.route('/messages/<int:id>', methods=['DELETE'])
@admin_required
def delete_message(id):
    message = Message.query.get_or_404(id)
    db.session.delete(message)
    db.session.commit()
    return jsonify({'message': 'Message deleted successfully'})

@admin_bp.route('/messages/add', methods=['POST'])
@admin_required
def add_message():
    data = request.get_json()
    
    message = Message(
        sender_id=data.get('sender_id'),
        recipient_id=data.get('recipient_id'),
        communication_type=data.get('communication_type'),
        subject=data.get('subject'),
        body=data.get('body'),
        reported_address=data.get('reported_address'),
        reported_phone=data.get('reported_phone'),
        reported_website=data.get('reported_website'),
        reported_hours=data.get('reported_hours'),
        out_of_business=data.get('out_of_business') == 'true',
        is_new_location=data.get('is_new_location') == 'true',
        is_admin_report=data.get('is_admin_report') == 'true',
        read=data.get('read') == 'true',
        name=data.get('name'),
        address=data.get('address'),
        email=data.get('email'),
        # Post Wins fields
        win_type=data.get('win_type'),
        location_used=data.get('location_used'),
        cards_found=data.get('cards_found'),
        time_saved=data.get('time_saved'),
        money_saved=data.get('money_saved'),
        allow_feature=data.get('allow_feature') == 'true'
    )
    
    db.session.add(message)
    db.session.commit()
    
    return jsonify({'message': 'Message added successfully'})

@admin_bp.route('/messages/edit/<int:id>', methods=['PUT'])
@admin_required
def edit_message(id):
    message = Message.query.get_or_404(id)
    data = request.get_json()
    
    # Update fields
    if 'sender_id' in data:
        message.sender_id = data['sender_id']
    if 'recipient_id' in data:
        message.recipient_id = data['recipient_id']
    if 'communication_type' in data:
        message.communication_type = data['communication_type']
    if 'subject' in data:
        message.subject = data['subject']
    if 'body' in data:
        message.body = data['body']
    if 'reported_address' in data:
        message.reported_address = data['reported_address']
    if 'reported_phone' in data:
        message.reported_phone = data['reported_phone']
    if 'reported_website' in data:
        message.reported_website = data['reported_website']
    if 'reported_hours' in data:
        message.reported_hours = data['reported_hours']
    if 'out_of_business' in data:
        message.out_of_business = data['out_of_business'] == 'true'
    if 'is_new_location' in data:
        message.is_new_location = data['is_new_location'] == 'true'
    if 'is_admin_report' in data:
        message.is_admin_report = data['is_admin_report'] == 'true'
    if 'read' in data:
        message.read = data['read'] == 'true'
    if 'name' in data:
        message.name = data['name']
    if 'address' in data:
        message.address = data['address']
    if 'email' in data:
        message.email = data['email']
    # Post Wins fields
    if 'win_type' in data:
        message.win_type = data['win_type']
    if 'location_used' in data:
        message.location_used = data['location_used']
    if 'cards_found' in data:
        message.cards_found = data['cards_found']
    if 'time_saved' in data:
        message.time_saved = data['time_saved']
    if 'money_saved' in data:
        message.money_saved = data['money_saved']
    if 'allow_feature' in data:
        message.allow_feature = data['allow_feature'] == 'true'
    
    db.session.commit()
    return jsonify({'message': 'Message updated successfully'})

@admin_bp.route('/messages/<int:id>/mark-read', methods=['POST'])
@admin_required
def mark_message_read(id):
    message = Message.query.get_or_404(id)
    message.read = True
    db.session.commit()
    return jsonify({'message': 'Message marked as read'})

@admin_bp.route('/messages/bulk-delete', methods=['POST'])
@admin_required
def bulk_delete_messages():
    """Delete multiple messages at once"""
    data = request.get_json()
    ids = data.get('ids', [])
    
    if not ids:
        return jsonify({'error': 'No message IDs provided'}), 400
    
    try:
        # Delete messages with the specified IDs
        deleted_count = db.session.query(Message).filter(Message.id.in_(ids)).delete(synchronize_session='fetch')
        db.session.commit()
        
        current_app.logger.info(f"Bulk deleted {deleted_count} messages by admin user {current_user.email}")
        
        return jsonify({
            'message': f'Successfully deleted {deleted_count} messages',
            'deleted_count': deleted_count
        })
    
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error in bulk delete messages: {e}")
        return jsonify({'error': 'Failed to delete messages'}), 500

@admin_bp.route('/messages/bulk-mark-read', methods=['POST'])
@admin_required
def bulk_mark_read_messages():
    """Mark multiple messages as read (placeholder for future implementation)"""
    data = request.get_json()
    ids = data.get('ids', [])
    
    if not ids:
        return jsonify({'error': 'No message IDs provided'}), 400
    
    try:
        # Update messages to mark as read
        updated_count = db.session.query(Message).filter(Message.id.in_(ids)).update(
            {'read': True}, synchronize_session='fetch'
        )
        db.session.commit()
        
        current_app.logger.info(f"Bulk marked {updated_count} messages as read by admin user {current_user.email}")
        
        return jsonify({
            'message': f'Successfully marked {updated_count} messages as read',
            'updated_count': updated_count
        })
    
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error in bulk mark read messages: {e}")
        return jsonify({'error': 'Failed to mark messages as read'}), 500

@admin_bp.route('/messages/bulk-archive', methods=['POST'])
@admin_required
def bulk_archive_messages():
    """Archive multiple messages (placeholder for future implementation)"""
    # Note: This would require adding an 'archived' column to the Message model
    # For now, just return a placeholder response
    return jsonify({'message': 'Archive functionality not yet implemented'}), 501

# Pages routes
@admin_bp.route('/pages')
@admin_required
def pages():
    # Redirect to top_pages since Page table doesn't exist
    return redirect(url_for('admin.top_pages'))

@admin_bp.route('/pages/data')
@admin_required
@rate_limit_data_tables(max_requests=20, window_seconds=60)
def pages_data():
    """Return top pages data in DataTables format"""
    draw = request.args.get('draw', type=int)
    start = request.args.get('start', type=int)
    length = request.args.get('length', type=int)
    search_value = request.args.get('search[value]', '')
    days = request.args.get('days', 30, type=int)
    
    # Validate days parameter
    if days < 1 or days > 60:
        days = 30
    
    # Apply days filter
    from datetime import datetime, timedelta
    cutoff_date = datetime.utcnow() - timedelta(days=days)
    
    # Get page visit data from VisitorLog model
    query = db.session.query(
        VisitorLog.path,
        db.func.count(VisitorLog.id).label('visits')
    ).filter(
        VisitorLog.timestamp >= cutoff_date
    ).group_by(VisitorLog.path)
    
    if search_value:
        search = f"%{search_value}%"
        query = query.filter(VisitorLog.path.ilike(search))
    
    # Handle sorting
    order_column = request.args.get('order[0][column]', type=int)
    order_dir = request.args.get('order[0][dir]', 'desc')
    
    # Define column mapping for sorting
    column_map = {
        0: VisitorLog.path,  # Page Path column
        1: db.func.count(VisitorLog.id)  # Visit Count column
    }
    
    if order_column is not None and order_column in column_map:
        sort_column = column_map[order_column]
        if order_dir == 'desc':
            sort_column = sort_column.desc()
        query = query.order_by(sort_column)
    else:
        # Default sorting by visit count descending
        query = query.order_by(db.func.count(VisitorLog.id).desc())
    
    total_records = query.count()
    pages = query.offset(start).limit(length).all()
    
    data = []
    for page in pages:
        data.append({
            'path': page.path,
            'visits': page.visits
        })
    
    return jsonify({
        'draw': draw,
        'recordsTotal': total_records,
        'recordsFiltered': total_records,
        'data': data
    })

@admin_bp.route('/pages/<int:id>', methods=['GET'])
@admin_required
def get_page(id):
    page = Page.query.get_or_404(id)
    return jsonify({
        'id': page.id,
        'path': page.path,
        'visits': page.visits,
        'last_visit': page.last_visit.strftime('%Y-%m-%d %H:%M:%S') if page.last_visit else None
    })

@admin_bp.route('/pages/<int:id>', methods=['PUT'])
@admin_required
def update_page(id):
    page = Page.query.get_or_404(id)
    data = request.get_json()
    
    for key, value in data.items():
        if hasattr(page, key):
            setattr(page, key, value)
    
    db.session.commit()
    return jsonify({'message': 'Page updated successfully'})

@admin_bp.route('/pages/<int:id>', methods=['DELETE'])
@admin_required
def delete_page(id):
    page = Page.query.get_or_404(id)
    db.session.delete(page)
    db.session.commit()
    return jsonify({'message': 'Page deleted successfully'})

# Referrers routes
@admin_bp.route('/referrers')
@admin_required
def referrers():
    # Redirect to top_referrers since Referrer table doesn't exist
    return redirect(url_for('admin.top_referrers'))

@admin_bp.route('/referrers/data')
@admin_required
@rate_limit_data_tables(max_requests=20, window_seconds=60)
def referrers_data():
    """Return top referrers data in DataTables format"""
    draw = request.args.get('draw', type=int)
    start = request.args.get('start', type=int)
    length = request.args.get('length', type=int)
    search_value = request.args.get('search[value]', '')
    show_internal = request.args.get('show_internal', 'false').lower() == 'true'
    days = request.args.get('days', 30, type=int)
    
    # Validate days parameter
    if days < 1 or days > 60:
        days = 30
    
    # Apply days filter
    from datetime import datetime, timedelta
    cutoff_date = datetime.utcnow() - timedelta(days=days)
    
    # Get referrer data from VisitorLog model
    query = db.session.query(
        VisitorLog.referrer,
        db.func.count(VisitorLog.id).label('visits'),
        db.func.max(VisitorLog.is_internal_referrer).label('is_internal')
    ).filter(
        VisitorLog.referrer.isnot(None),
        VisitorLog.referrer != '',
        VisitorLog.timestamp >= cutoff_date
    ).group_by(VisitorLog.referrer)
    
    if not show_internal:
        # Filter out internal referrers using the database flag
        query = query.filter(VisitorLog.is_internal_referrer == False)
        
        # Additional filtering for localhost and private IP addresses
        query = query.filter(
            ~or_(
                # Filter out localhost patterns (with and without protocol)
                VisitorLog.referrer.ilike('%://127.%'),
                VisitorLog.referrer.ilike('127.%'),
                VisitorLog.referrer.ilike('%localhost%'),
                # Filter out private IP ranges (with and without protocol)
                VisitorLog.referrer.ilike('%://192.168.%'),
                VisitorLog.referrer.ilike('192.168.%'),
                VisitorLog.referrer.ilike('%://10.%'),
                VisitorLog.referrer.ilike('10.%'),
                VisitorLog.referrer.ilike('%://172.16.%'),
                VisitorLog.referrer.ilike('172.16.%'),
                VisitorLog.referrer.ilike('%://172.17.%'),
                VisitorLog.referrer.ilike('172.17.%'),
                VisitorLog.referrer.ilike('%://172.18.%'),
                VisitorLog.referrer.ilike('172.18.%'),
                VisitorLog.referrer.ilike('%://172.19.%'),
                VisitorLog.referrer.ilike('172.19.%'),
                VisitorLog.referrer.ilike('%://172.20.%'),
                VisitorLog.referrer.ilike('172.20.%'),
                VisitorLog.referrer.ilike('%://172.21.%'),
                VisitorLog.referrer.ilike('172.21.%'),
                VisitorLog.referrer.ilike('%://172.22.%'),
                VisitorLog.referrer.ilike('172.22.%'),
                VisitorLog.referrer.ilike('%://172.23.%'),
                VisitorLog.referrer.ilike('172.23.%'),
                VisitorLog.referrer.ilike('%://172.24.%'),
                VisitorLog.referrer.ilike('172.24.%'),
                VisitorLog.referrer.ilike('%://172.25.%'),
                VisitorLog.referrer.ilike('172.25.%'),
                VisitorLog.referrer.ilike('%://172.26.%'),
                VisitorLog.referrer.ilike('172.26.%'),
                VisitorLog.referrer.ilike('%://172.27.%'),
                VisitorLog.referrer.ilike('172.27.%'),
                VisitorLog.referrer.ilike('%://172.28.%'),
                VisitorLog.referrer.ilike('172.28.%'),
                VisitorLog.referrer.ilike('%://172.29.%'),
                VisitorLog.referrer.ilike('172.29.%'),
                VisitorLog.referrer.ilike('%://172.30.%'),
                VisitorLog.referrer.ilike('172.30.%'),
                VisitorLog.referrer.ilike('%://172.31.%'),
                VisitorLog.referrer.ilike('172.31.%'),
                # Filter out site's own domain
                VisitorLog.referrer.ilike('%tamermap.com%'),
                VisitorLog.referrer.ilike('%www.tamermap.com%')
            )
        )
    
    if search_value:
        search = f"%{search_value}%"
        query = query.filter(VisitorLog.referrer.ilike(search))
    
    # Handle sorting
    order_column = request.args.get('order[0][column]', type=int)
    order_dir = request.args.get('order[0][dir]', 'desc')
    
    # For domain sorting, we need to extract domain in the query
    if order_column == 0:  # Domain column
        # Use a case-insensitive substring extraction for domain
        if order_dir == 'desc':
            query = query.order_by(db.func.lower(VisitorLog.referrer).desc())
        else:
            query = query.order_by(db.func.lower(VisitorLog.referrer).asc())
    elif order_column == 1:  # Full URL column
        if order_dir == 'desc':
            query = query.order_by(VisitorLog.referrer.desc())
        else:
            query = query.order_by(VisitorLog.referrer.asc())
    elif order_column == 2:  # Visit Count column
        if order_dir == 'desc':
            query = query.order_by(db.func.count(VisitorLog.id).desc())
        else:
            query = query.order_by(db.func.count(VisitorLog.id).asc())
    else:
        # Default sorting by visit count descending
        query = query.order_by(db.func.count(VisitorLog.id).desc())
    
    total_records = query.count()
    referrers = query.offset(start).limit(length).all()
    
    data = []
    for referrer, count, is_internal in referrers:
        # Extract domain from URL
        domain = 'Unknown'
        full_url = referrer or 'Direct'
        
        if full_url and full_url != 'Direct':
            try:
                from urllib.parse import urlparse
                # Add protocol if missing
                if not full_url.startswith(('http://', 'https://')):
                    full_url = 'https://' + full_url
                
                parsed = urlparse(full_url)
                domain = parsed.netloc
                if not domain:
                    domain = 'Unknown'
            except Exception:
                domain = 'Unknown'
        
        # Get location data (simplified - you might want to enhance this)
        location_data = {
            'city': None,
            'region': None,
            'country': None
        }
        
        data.append({
            'domain': domain,
            'full_url': full_url,
            'visits': count,
            'is_internal': is_internal,
            'location': location_data
        })
    
    return jsonify({
        'draw': draw,
        'recordsTotal': total_records,
        'recordsFiltered': total_records,
        'data': data
    })

@admin_bp.route('/visitors')
@admin_required
def visitors():
    # Get query parameters
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 25, type=int)
    search = request.args.get('search', '')
    sort = request.args.get('sort', 'timestamp')
    order = request.args.get('order', 'desc')
    
    # Validate sort column
    valid_sort_columns = ['timestamp', 'ip_address', 'path', 'referrer', 'location', 'ref_code']
    if sort not in valid_sort_columns:
        sort = 'timestamp'
    
    # Validate order
    if order not in ['asc', 'desc']:
        order = 'desc'
    
    # Build query
    from .admin_utils import exclude_monitor_traffic
    query = exclude_monitor_traffic(VisitorLog.query)
    
    # Apply search filter
    if search:
        search_filter = f"%{search}%"
        query = query.filter(
            (VisitorLog.path.ilike(search_filter)) |
            (VisitorLog.ip_address.ilike(search_filter)) |
            (VisitorLog.referrer.ilike(search_filter)) |
            (VisitorLog.city.ilike(search_filter)) |
            (VisitorLog.region.ilike(search_filter)) |
            (VisitorLog.country.ilike(search_filter)) |
            (VisitorLog.ref_code.ilike(search_filter))
        )
    
    # Apply sorting
    if sort == 'location':
        # Sort by city, then region, then country for location column
        if order == 'desc':
            query = query.order_by(VisitorLog.city.desc().nullslast(), 
                                  VisitorLog.region.desc().nullslast(), 
                                  VisitorLog.country.desc().nullslast())
        else:
            query = query.order_by(VisitorLog.city.asc().nullslast(), 
                                  VisitorLog.region.asc().nullslast(), 
                                  VisitorLog.country.asc().nullslast())
    else:
        # For other columns, use the standard approach
        sort_column = getattr(VisitorLog, sort)
        if order == 'desc':
            query = query.order_by(sort_column.desc())
        else:
            query = query.order_by(sort_column.asc())
    
    # Get total count for pagination
    total_visitors = query.count()
    
    # Apply pagination
    visitors = query.offset((page - 1) * per_page).limit(per_page).all()
    
    # Calculate pagination info
    total_pages = (total_visitors + per_page - 1) // per_page
    
    return render_template('admin/visitors.html', 
                         visitors=visitors,
                         page=page,
                         per_page=per_page,
                         total_visitors=total_visitors,
                         total_pages=total_pages,
                         search=search,
                         sort=sort,
                         order=order)

@admin_bp.route('/visitors/data')
@admin_required
@rate_limit_data_tables(max_requests=20, window_seconds=60)
def visitors_data():
    """Return visitor data in DataTables format"""
    draw = request.args.get('draw', type=int)
    start = request.args.get('start', type=int)
    length = request.args.get('length', type=int)
    search_value = request.args.get('search[value]', '')
    days = request.args.get('days', 30, type=int)
    
    # Validate days parameter
    if days < 1 or days > 60:
        days = 30
    
    # Build the query
    from .admin_utils import exclude_monitor_traffic
    query = exclude_monitor_traffic(VisitorLog.query)
    
    # Apply days filter
    from datetime import datetime, timedelta
    cutoff_date = datetime.utcnow() - timedelta(days=days)
    query = query.filter(VisitorLog.timestamp >= cutoff_date)
    
    # Apply search filter if provided
    if search_value:
        search = f"%{search_value}%"
        query = query.filter(
            (VisitorLog.path.ilike(search)) |
            (VisitorLog.ip_address.ilike(search)) |
            (VisitorLog.referrer.ilike(search)) |
            (VisitorLog.city.ilike(search)) |
            (VisitorLog.region.ilike(search)) |
            (VisitorLog.country.ilike(search)) |
            (VisitorLog.ref_code.ilike(search))
        )
    
    # Handle sorting
    order_column = request.args.get('order[0][column]', type=int)
    order_dir = request.args.get('order[0][dir]', 'desc')
    
    # Define column mapping for sorting
    column_map = {
        0: VisitorLog.timestamp,
        1: VisitorLog.ip_address,
        2: VisitorLog.path,
        3: VisitorLog.referrer,
        4: VisitorLog.city,  # We'll use city for location sorting
        5: VisitorLog.ref_code
    }
    
    if order_column is not None and order_column in column_map:
        sort_column = column_map[order_column]
        if order_dir == 'desc':
            sort_column = sort_column.desc()
        query = query.order_by(sort_column)
    else:
        # Default sorting by timestamp descending
        query = query.order_by(VisitorLog.timestamp.desc())
    
    total_records = query.count()
    visitors = query.offset(start).limit(length).all()
    
    data = []
    for visitor in visitors:
        # Format location
        location_parts = []
        if visitor.city:
            location_parts.append(visitor.city)
        if visitor.region:
            location_parts.append(visitor.region)
        if visitor.country:
            location_parts.append(visitor.country)
        location = ', '.join(location_parts) if location_parts else 'Unknown'
        
        data.append({
            'timestamp': visitor.timestamp.strftime('%Y-%m-%d %H:%M:%S') if visitor.timestamp else '',
            'ip_address': visitor.ip_address or '',
            'path': visitor.path or '',
            'referrer': visitor.referrer or 'Direct',
            'location': location,
            'ref_code': visitor.ref_code or 'N/A'
        })
    
    return jsonify({
        'draw': draw,
        'recordsTotal': total_records,
        'recordsFiltered': total_records,
        'data': data
    })

@admin_bp.route('/visitors/data/pages')
@admin_required
def visitors_pages_data():
    draw = request.args.get('draw', type=int)
    start = request.args.get('start', type=int)
    length = request.args.get('length', type=int)
    search_value = request.args.get('search[value]', '')
    
    # Get page visit data from VisitorLog model
    query = db.session.query(
        VisitorLog.path,
        db.func.count(VisitorLog.id).label('visits')
    ).group_by(VisitorLog.path)
    
    if search_value:
        search = f"%{search_value}%"
        query = query.filter(VisitorLog.path.ilike(search))
    
    total_records = query.count()
    pages = query.order_by(db.func.count(VisitorLog.id).desc()).offset(start).limit(length).all()
    
    data = []
    for page in pages:
        data.append({
            'path': page.path,
            'visits': page.visits
        })
    
    return jsonify({
        'draw': draw,
        'recordsTotal': total_records,
        'recordsFiltered': total_records,
        'data': data
    })

@admin_bp.route('/visitors/data/codes')
@admin_required
def visitors_codes_data():
    draw = request.args.get('draw', type=int)
    start = request.args.get('start', type=int)
    length = request.args.get('length', type=int)
    search_value = request.args.get('search[value]', '')
    
    # Get referral code data from VisitorLog model
    query = db.session.query(
        VisitorLog.ref_code,
        db.func.count(VisitorLog.id).label('visits')
    ).filter(
        VisitorLog.ref_code.isnot(None),
        VisitorLog.ref_code != ''
    ).group_by(VisitorLog.ref_code)
    
    if search_value:
        search = f"%{search_value}%"
        query = query.filter(VisitorLog.ref_code.ilike(search))
    
    total_records = query.count()
    codes = query.order_by(db.func.count(VisitorLog.id).desc()).offset(start).limit(length).all()
    
    data = []
    for code in codes:
        data.append({
            'ref_code': code.ref_code or 'None',
            'visits': code.visits
        })
    
    return jsonify({
        'draw': draw,
        'recordsTotal': total_records,
        'recordsFiltered': total_records,
        'data': data
    })

@admin_bp.route('/visitors/data/ip-summary')
@admin_required
@rate_limit_data_tables(max_requests=20, window_seconds=60)
def visitors_ip_summary_data():
    """Return visitor IP summary data in DataTables format"""
    draw = request.args.get('draw', type=int)
    start = request.args.get('start', type=int)
    length = request.args.get('length', type=int)
    search_value = request.args.get('search[value]', '')
    days = request.args.get('days', 30, type=int)
    
    # Validate days parameter
    if days < 1 or days > 60:
        days = 30
    
    # Build the query for IP summary
    from .admin_utils import exclude_monitor_traffic
    base_query = exclude_monitor_traffic(VisitorLog.query)
    
    # Apply days filter
    from datetime import datetime, timedelta
    cutoff_date = datetime.utcnow() - timedelta(days=days)
    base_query = base_query.filter(VisitorLog.timestamp >= cutoff_date)
    
    # Group by IP address and get summary data
    query = db.session.query(
        VisitorLog.ip_address,
        func.count(VisitorLog.id).label('request_count'),
        func.max(VisitorLog.city).label('city'),
        func.max(VisitorLog.region).label('region'),
        func.max(VisitorLog.country).label('country'),
        func.max(VisitorLog.timestamp).label('last_visit'),
        func.min(VisitorLog.timestamp).label('first_visit')
    ).filter(
        VisitorLog.timestamp >= cutoff_date
    ).group_by(VisitorLog.ip_address)
    
    # Apply search filter if provided
    if search_value:
        search = f"%{search_value}%"
        query = query.filter(
            (VisitorLog.ip_address.ilike(search)) |
            (VisitorLog.city.ilike(search)) |
            (VisitorLog.region.ilike(search)) |
            (VisitorLog.country.ilike(search))
        )
    
    # Handle sorting
    order_column = request.args.get('order[0][column]', type=int)
    order_dir = request.args.get('order[0][dir]', 'desc')
    
    # Define column mapping for sorting
    column_map = {
        0: VisitorLog.ip_address,
        1: func.count(VisitorLog.id),
        2: func.max(VisitorLog.city),
        3: func.max(VisitorLog.region),
        4: func.max(VisitorLog.country),
        5: func.max(VisitorLog.timestamp)
    }
    
    if order_column is not None and order_column in column_map:
        sort_column = column_map[order_column]
        if order_dir == 'desc':
            sort_column = sort_column.desc()
        query = query.order_by(sort_column)
    else:
        # Default sorting by request count descending
        query = query.order_by(func.count(VisitorLog.id).desc())
    
    total_records = query.count()
    ip_summaries = query.offset(start).limit(length).all()
    
    data = []
    for summary in ip_summaries:
        # Format location
        location_parts = []
        if summary.city:
            location_parts.append(summary.city)
        if summary.region:
            location_parts.append(summary.region)
        if summary.country:
            location_parts.append(summary.country)
        location = ', '.join(location_parts) if location_parts else 'Unknown'
        
        # Calculate time span
        time_span = 'N/A'
        if summary.first_visit and summary.last_visit:
            time_diff = summary.last_visit - summary.first_visit
            if time_diff.days > 0:
                time_span = f"{time_diff.days} days"
            elif time_diff.seconds > 3600:
                time_span = f"{time_diff.seconds // 3600} hours"
            elif time_diff.seconds > 60:
                time_span = f"{time_diff.seconds // 60} minutes"
            else:
                time_span = f"{time_diff.seconds} seconds"
        
        data.append({
            'ip_address': summary.ip_address or '',
            'request_count': summary.request_count,
            'city': summary.city or 'Unknown',
            'region': summary.region or 'Unknown',
            'country': summary.country or 'Unknown',
            'location': location,
            'last_visit': summary.last_visit.strftime('%Y-%m-%d %H:%M:%S') if summary.last_visit else '',
            'time_span': time_span
        })
    
    return jsonify({
        'draw': draw,
        'recordsTotal': total_records,
        'recordsFiltered': total_records,
        'data': data
    })

@admin_bp.route('/visitors/data/locations')
@admin_required
def visitors_locations_data():
    draw = request.args.get('draw', type=int)
    start = request.args.get('start', type=int)
    length = request.args.get('length', type=int)
    search_value = request.args.get('search[value]', '')
    show_internal = request.args.get('show_internal', 'false').lower() == 'true'
    
    # Get location data from VisitorLog model
    query = db.session.query(
        VisitorLog.city,
        VisitorLog.region,
        VisitorLog.country,
        db.func.count(VisitorLog.id).label('visits')
    ).group_by(VisitorLog.city, VisitorLog.region, VisitorLog.country)
    
    if not show_internal:
        query = query.filter(~VisitorLog.country.like('%internal%'))
    
    if search_value:
        search = f"%{search_value}%"
        query = query.filter(
            (VisitorLog.city.ilike(search)) |
            (VisitorLog.region.ilike(search)) |
            (VisitorLog.country.ilike(search))
        )
    
    total_records = query.count()
    locations = query.order_by(db.func.count(VisitorLog.id).desc()).offset(start).limit(length).all()
    
    data = []
    for location in locations:
        data.append({
            'city': location.city or 'Unknown',
            'region': location.region or 'Unknown',
            'country': location.country or 'Unknown',
            'visits': location.visits
        })
    
    return jsonify({
        'draw': draw,
        'recordsTotal': total_records,
        'recordsFiltered': total_records,
        'data': data
    })

# Analytics routes
@admin_bp.route('/top_referrers')
@admin_required
def top_referrers():
    """Shows the top website referrers."""
    show_internal = request.args.get('show_internal', 'false').lower() == 'true'
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 25))
    search = request.args.get('search', '').strip()
    sort = request.args.get('sort', 'count')  # Default sort by count
    order = request.args.get('order', 'desc')  # Default descending
    
    # Get referrers from the past 30 days
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    
    # Main query for paginated results
    query = (
        db.session.query(
            VisitorLog.referrer,
            func.count().label('count'),
            func.max(VisitorLog.country).label('country'),
            func.max(VisitorLog.region).label('region'),
            func.max(VisitorLog.city).label('city'),
            func.max(VisitorLog.is_internal_referrer).label('is_internal')
        )
        .filter(
            VisitorLog.referrer.isnot(None), 
            VisitorLog.referrer != '',
            VisitorLog.timestamp >= thirty_days_ago
        )
    )
    if not show_internal:
        # Filter out internal referrers using the database flag
        query = query.filter(VisitorLog.is_internal_referrer == False)
        
        # Additional filtering for localhost and private IP addresses
        query = query.filter(
            ~or_(
                # Filter out localhost patterns (with and without protocol)
                VisitorLog.referrer.ilike('%://127.%'),
                VisitorLog.referrer.ilike('127.%'),
                VisitorLog.referrer.ilike('%localhost%'),
                # Filter out private IP ranges (with and without protocol)
                VisitorLog.referrer.ilike('%://192.168.%'),
                VisitorLog.referrer.ilike('192.168.%'),
                VisitorLog.referrer.ilike('%://10.%'),
                VisitorLog.referrer.ilike('10.%'),
                VisitorLog.referrer.ilike('%://172.16.%'),
                VisitorLog.referrer.ilike('172.16.%'),
                VisitorLog.referrer.ilike('%://172.17.%'),
                VisitorLog.referrer.ilike('172.17.%'),
                VisitorLog.referrer.ilike('%://172.18.%'),
                VisitorLog.referrer.ilike('172.18.%'),
                VisitorLog.referrer.ilike('%://172.19.%'),
                VisitorLog.referrer.ilike('172.19.%'),
                VisitorLog.referrer.ilike('%://172.20.%'),
                VisitorLog.referrer.ilike('172.20.%'),
                VisitorLog.referrer.ilike('%://172.21.%'),
                VisitorLog.referrer.ilike('172.21.%'),
                VisitorLog.referrer.ilike('%://172.22.%'),
                VisitorLog.referrer.ilike('172.22.%'),
                VisitorLog.referrer.ilike('%://172.23.%'),
                VisitorLog.referrer.ilike('172.23.%'),
                VisitorLog.referrer.ilike('%://172.24.%'),
                VisitorLog.referrer.ilike('172.24.%'),
                VisitorLog.referrer.ilike('%://172.25.%'),
                VisitorLog.referrer.ilike('172.25.%'),
                VisitorLog.referrer.ilike('%://172.26.%'),
                VisitorLog.referrer.ilike('172.26.%'),
                VisitorLog.referrer.ilike('%://172.27.%'),
                VisitorLog.referrer.ilike('172.27.%'),
                VisitorLog.referrer.ilike('%://172.28.%'),
                VisitorLog.referrer.ilike('172.28.%'),
                VisitorLog.referrer.ilike('%://172.29.%'),
                VisitorLog.referrer.ilike('172.29.%'),
                VisitorLog.referrer.ilike('%://172.30.%'),
                VisitorLog.referrer.ilike('172.30.%'),
                VisitorLog.referrer.ilike('%://172.31.%'),
                VisitorLog.referrer.ilike('172.31.%'),
                # Filter out site's own domain
                VisitorLog.referrer.ilike('%tamermap.com%'),
                VisitorLog.referrer.ilike('%www.tamermap.com%')
            )
        )
    
    # Apply search filter to main query
    if search:
        search_term = f"%{search}%"
        query = query.filter(VisitorLog.referrer.ilike(search_term))
    
    # Apply grouping first to get the correct count
    grouped_query = query.group_by(VisitorLog.referrer)
    total_unique = grouped_query.count()
    total_pages = max(1, (total_unique + per_page - 1) // per_page)
    
    # Apply sorting
    if sort == 'count':
        if order == 'asc':
            grouped_query = grouped_query.order_by(func.count().asc())
        else:
            grouped_query = grouped_query.order_by(func.count().desc())
    elif sort == 'domain':
        if order == 'asc':
            grouped_query = grouped_query.order_by(VisitorLog.referrer.asc())
        else:
            grouped_query = grouped_query.order_by(VisitorLog.referrer.desc())
    elif sort == 'url':
        if order == 'asc':
            grouped_query = grouped_query.order_by(VisitorLog.referrer.asc())
        else:
            grouped_query = grouped_query.order_by(VisitorLog.referrer.desc())
    elif sort == 'location':
        if order == 'asc':
            grouped_query = grouped_query.order_by(func.max(VisitorLog.city).asc())
        else:
            grouped_query = grouped_query.order_by(func.max(VisitorLog.city).desc())
    else:  # Default sort by count descending
        grouped_query = grouped_query.order_by(func.count().desc())
    
    top_referrers = (
        grouped_query
        .offset((page-1)*per_page)
        .limit(per_page)
        .all()
    )
    
    # Process referrers for better display
    processed_referrers = []
    for referrer, count, country, region, city, is_internal in top_referrers:
        try:
            from urllib.parse import urlparse
            parsed_url = urlparse(referrer)
            domain = parsed_url.netloc
            processed_referrers.append({
                'domain': domain,
                'full_url': referrer,
                'count': count,
                'country': country,
                'region': region,
                'city': city,
                'is_internal': is_internal
            })
        except:
            processed_referrers.append({
                'domain': 'Unknown',
                'full_url': referrer,
                'count': count,
                'country': country,
                'region': region,
                'city': city,
                'is_internal': is_internal
            })
    
    return render_template('admin/top_referrers.html', 
                         top_referrers=processed_referrers,
                         show_internal=show_internal,
                         page=page,
                         total_pages=total_pages,
                         per_page=per_page,
                         sort=sort,
                         order=order,
                         total_unique=total_unique,
                         title='Referrers')

@admin_bp.route('/top_pages')
@admin_required
def top_pages():
    """Shows the top most visited paths with sorting and pagination."""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 25, type=int)
    sort = request.args.get('sort', 'count')
    order = request.args.get('order', 'desc')
    search = request.args.get('search', '').strip()

    # Build the query
    query = db.session.query(VisitorLog.path, func.count().label('count')) \
        .group_by(VisitorLog.path)

    # Apply search filter
    if search:
        search_term = f"%{search}%"
        query = query.filter(VisitorLog.path.ilike(search_term))

    # Sorting
    if sort == 'path':
        if order == 'asc':
            query = query.order_by(VisitorLog.path.asc())
        else:
            query = query.order_by(VisitorLog.path.desc())
    else:  # sort == 'count' or default
        if order == 'asc':
            query = query.order_by(func.count().asc())
        else:
            query = query.order_by(func.count().desc())

    # Paginate
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    return render_template('admin/top_pages.html',
                         top_paths=pagination.items,
                         pagination=pagination,
                         sort=sort,
                         order=order,
                         title='Top Pages')

@admin_bp.route('/top_ref_codes')
@admin_required
def top_ref_codes():
    """Shows the top referring codes with sorting and pagination."""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 25, type=int)
    sort = request.args.get('sort', 'count')
    order = request.args.get('order', 'desc')
    search = request.args.get('search', '').strip()

    # Build the query - include all ref_codes including None
    query = db.session.query(VisitorLog.ref_code, func.count().label('count')) \
        .group_by(VisitorLog.ref_code)

    # Apply search filter
    if search:
        search_term = f"%{search}%"
        query = query.filter(VisitorLog.ref_code.ilike(search_term))

    # Sorting
    if sort == 'code':
        if order == 'asc':
            query = query.order_by(VisitorLog.ref_code.asc().nullslast())
        else:
            query = query.order_by(VisitorLog.ref_code.desc().nullslast())
    else:  # sort == 'count' or default
        if order == 'asc':
            query = query.order_by(func.count().asc())
        else:
            query = query.order_by(func.count().desc())

    # Paginate
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    return render_template('admin/top_ref_codes.html',
                         top_refs=pagination.items,
                         pagination=pagination,
                         sort=sort,
                         order=order,
                         title='Referral Codes')

# Future Events routes have been consolidated into the main Events page

@admin_bp.route('/ref_codes/data')
@admin_required
@rate_limit_data_tables(max_requests=20, window_seconds=60)
def ref_codes_data():
    """Return referral codes data in DataTables format"""
    draw = request.args.get('draw', type=int)
    start = request.args.get('start', type=int)
    length = request.args.get('length', type=int)
    search_value = request.args.get('search[value]', '')
    days = request.args.get('days', 30, type=int)
    
    # Validate days parameter
    if days < 1 or days > 60:
        days = 30
    
    # Apply days filter
    from datetime import datetime, timedelta
    cutoff_date = datetime.utcnow() - timedelta(days=days)
    
    # Get referral codes with usage count
    query = db.session.query(
        VisitorLog.ref_code,
        func.count(VisitorLog.id).label('count')
    ).filter(
        VisitorLog.timestamp >= cutoff_date
    ).group_by(VisitorLog.ref_code)
    
    # Apply search filter if provided
    if search_value:
        search = f"%{search_value}%"
        query = query.filter(VisitorLog.ref_code.ilike(search))
    
    # Handle sorting
    order_column = request.args.get('order[0][column]', type=int)
    order_dir = request.args.get('order[0][dir]', 'desc')
    
    # Define column mapping for sorting
    column_map = {
        0: VisitorLog.ref_code,    # Referral Code column
        1: func.count(VisitorLog.id),  # Usage Count column
    }
    
    if order_column is not None and order_column in column_map:
        sort_column = column_map[order_column]
        if order_dir == 'desc':
            sort_column = sort_column.desc()
        query = query.order_by(sort_column)
    else:
        # Default sorting by count descending
        query = query.order_by(func.count(VisitorLog.id).desc())
    
    total_records = query.count()
    results = query.offset(start).limit(length).all()
    
    data = []
    for ref_code, count in results:
        data.append({
            'code': ref_code,
            'count': count
        })
    
    return jsonify({
        'draw': draw,
        'recordsTotal': total_records,
        'recordsFiltered': total_records,
        'data': data
    })

@admin_bp.route('/setup-intents')
@admin_required
def setup_intents():
    """Admin page to view and manage setup intents."""
    # Check Stripe configuration
    stripe.api_key = current_app.config.get("STRIPE_SECRET_KEY")
    if not stripe.api_key:
        flash("Warning: STRIPE_SECRET_KEY not configured", "warning")
    else:
        try:
            # Test Stripe connection
            test_list = stripe.SetupIntent.list(limit=1)
            current_app.logger.info(f"Stripe connection test successful. Found {len(test_list.data)} setup intents")
        except Exception as e:
            current_app.logger.error(f"Stripe connection test failed: {e}")
            flash(f"Warning: Stripe connection failed: {str(e)}", "warning")
    
    return render_template('admin/setup_intents.html')

@admin_bp.route('/setup-intents/data')
@admin_required
@rate_limit_data_tables(max_requests=20, window_seconds=60)
def setup_intents_data():
    """Get setup intents data for admin dashboard."""
    try:
        draw = request.args.get('draw', type=int)
        start = request.args.get('start', type=int)
        length = request.args.get('length', type=int)
        search_value = request.args.get('search[value]', '')
        
        # Get setup intents from Stripe
        stripe.api_key = current_app.config.get("STRIPE_SECRET_KEY")
        
        # Debug logging
        current_app.logger.info(f"Fetching setup intents from Stripe with limit={length}")
        
        if not stripe.api_key:
            current_app.logger.error("STRIPE_SECRET_KEY not configured")
            return jsonify({'error': 'Stripe API key not configured'}), 500
        
        # Get setup intents with pagination
        try:
            # Fix pagination parameters - handle None values
            limit_param = length if length is not None else 10
            
            # For now, just get all setup intents since Stripe pagination uses cursors, not offsets
            # In a production app, you'd want to implement proper cursor-based pagination
            setup_intents = stripe.SetupIntent.list(
                limit=limit_param
            )
            current_app.logger.info(f"Retrieved {len(setup_intents.data)} setup intents from Stripe")
            
            # Log details of each setup intent for debugging
            for i, si in enumerate(setup_intents.data):
                current_app.logger.info(f"Setup Intent {i+1}: ID={si.id}, Status={si.status}, Customer={si.customer}, Created={si.created}")
                
        except stripe.error.StripeError as e:
            current_app.logger.error(f"Stripe API error: {e}")
            return jsonify({'error': f'Stripe API error: {str(e)}'}), 500
        except Exception as e:
            current_app.logger.error(f"Unexpected error fetching setup intents: {e}")
            return jsonify({'error': f'Unexpected error: {str(e)}'}), 500
        
        data = []
        for si in setup_intents.data:
            # Get user info if available
            user = None
            if si.customer:
                user = User.query.filter_by(cust_id=si.customer).first()
            
            # Determine if retry button should be enabled
            # Allow retry for 3D Secure issues and canceled setups that might need completion
            can_retry = si.status in ['requires_action', 'canceled']
            retry_button_class = "btn btn-sm btn-warning" if can_retry else "btn btn-sm btn-secondary"
            retry_disabled = "" if can_retry else "disabled"
            retry_text = "Retry" if can_retry else "N/A"
            
            data.append({
                'id': si.id,
                'status': si.status,
                'customer_id': si.customer,
                'user_email': user.email if user else 'Unknown',
                'created': datetime.fromtimestamp(si.created).strftime('%Y-%m-%d %H:%M:%S'),
                'payment_method_types': ', '.join(si.payment_method_types),
                'usage': si.usage,
                'actions': f'''
                    <button class="btn btn-sm btn-info view-setup-intent" data-id="{si.id}">View</button>
                    <button class="{retry_button_class} retry-setup-intent" data-id="{si.id}" {retry_disabled}>
                        {retry_text}
                    </button>
                '''
            })
        
        return jsonify({
            'draw': draw,
            'recordsTotal': len(setup_intents.data),
            'recordsFiltered': len(setup_intents.data),
            'data': data
        })
        
    except Exception as e:
        current_app.logger.error(f"setup_intents_data route failed: {e}")
        return jsonify({'error': 'Failed to load setup intents data'}), 500

@admin_bp.route('/setup-intents/<setup_intent_id>/retry', methods=['POST'])
@admin_required
def retry_setup_intent(setup_intent_id):
    """Retry a setup intent that requires action."""
    try:
        stripe.api_key = current_app.config.get("STRIPE_SECRET_KEY")
        
        # Retrieve the setup intent
        setup_intent = stripe.SetupIntent.retrieve(setup_intent_id)
        
        # Check if retry is allowed
        if setup_intent.status not in ['requires_action', 'canceled']:
            status_messages = {
                'succeeded': 'This payment method has already been successfully set up.',
                'processing': 'This setup is currently being processed.',
                'requires_payment_method': 'This setup failed due to payment method issues. Customer should add a different payment method instead of retrying.'
            }
            message = status_messages.get(setup_intent.status, f'Setup intent status "{setup_intent.status}" does not allow retry.')
            return jsonify({'error': message}), 400
        
        # Get user info for logging
        user = None
        customer_email = None
        customer_name = None
        
        if setup_intent.customer:
            # First try to find user in database
            user = User.query.filter_by(cust_id=setup_intent.customer).first()
            
            if not user:
                # If user not in database, try to get customer info from Stripe
                try:
                    stripe_customer = stripe.Customer.retrieve(setup_intent.customer)
                    customer_email = stripe_customer.email
                    customer_name = stripe_customer.name
                except Exception as e:
                    current_app.logger.error(f"Failed to retrieve customer from Stripe: {e}")
        else:
            current_app.logger.warning(f"No customer associated with setup intent {setup_intent_id}")
        
        current_app.logger.info(f"Retrying setup intent {setup_intent_id} for user {user.email if user else 'unknown'}")
        
        # Test email functionality
        try:
            test_result = send_email_with_context(
                subject="TEST EMAIL - Setup Intent Retry",
                template="email/admin_message_notification",
                recipient=current_app.config.get('ADMIN_EMAIL', 'mark@markdevore.com'),
                communication_type="test",
                name="Test User",
                address="Test Address",
                form_subject="Test Subject",
                body="This is a test email to verify the email system is working.",
                config=current_app.config
            )
        except Exception as e:
            current_app.logger.error(f"Test email failed: {e}")
        
        # Create a new checkout session for this setup intent
        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            mode='setup',
            setup_intent_data={
                'metadata': {
                    'original_setup_intent': setup_intent_id,
                    'retry_initiated_by': 'admin',
                    'retry_timestamp': datetime.utcnow().isoformat()
                }
            },
            success_url=url_for('auth.account', _external=True) + '?setup_intent={CHECKOUT_SESSION_ID}',
            cancel_url=url_for('auth.account', _external=True)
        )
        
        # Log the retry attempt
        if user:
            log_billing_event(
                user=user,
                event_type="setup_intent_retry_initiated",
                event_data={
                    "original_setup_intent_id": setup_intent_id,
                    "new_session_id": session.id,
                    "retry_reason": setup_intent.status,
                    "admin_initiated": True
                }
            )
        
        # Send email notification to customer
        customer_email_to_use = None
        customer_name_to_use = None
        
        if user:
            # Use user from database
            customer_email_to_use = user.email
            customer_name_to_use = user.first_name or user.email
        elif customer_email:
            # Use customer info from Stripe
            customer_email_to_use = customer_email
            customer_name_to_use = customer_name or customer_email
        else:
            current_app.logger.warning(f"No customer email available for setup intent {setup_intent_id}")
        
        if customer_email_to_use:
            try:
                retry_reason = setup_intent.status.replace('_', ' ')
                if setup_intent.status == 'canceled':
                    retry_reason = 'canceled (likely 3D Secure timeout)'
                
                # Send customer email notification
                
                # Create a minimal user object for the template
                template_user = type('User', (), {
                    'email': customer_email_to_use,
                    'first_name': customer_name_to_use
                })()
                
                send_email_with_context(
                    subject="Payment Setup Retry - Complete Your Setup",
                    template="email/setup_intent_retry_notification",
                    recipient=customer_email_to_use,
                    user=template_user,
                    checkout_url=session.url,
                    retry_reason=retry_reason,
                    retry_timestamp=datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')
                )
                current_app.logger.info(f"Sent retry notification email to customer {customer_email_to_use}")
            except Exception as e:
                current_app.logger.error(f"Failed to send retry notification email to customer {customer_email_to_use}: {e}")
                current_app.logger.error(f"Exception details: {str(e)}", exc_info=True)
        else:
            current_app.logger.warning(f"No customer email sent - no email available for setup intent {setup_intent_id}")
        
        # Send email notification to admin
        try:
            admin_url = url_for('admin.setup_intents', _external=True)
            checkout_url = f"https://dashboard.stripe.com/sessions/{session.id}"
            
            # Debug logging
            admin_email = current_app.config.get('ADMIN_EMAIL', 'admin@tamermap.com')
                    # Send admin email notification
            
            send_email_with_context(
                subject="Setup Intent Retry Initiated - Admin Alert",
                template="email/admin_setup_intent_retry_notification",
                recipient=admin_email,
                original_setup_intent_id=setup_intent_id,
                new_session_id=session.id,
                customer_email=user.email if user else 'Unknown',
                customer_id=setup_intent.customer,
                original_status=setup_intent.status,
                retry_reason=setup_intent.status.replace('_', ' '),
                admin_email=current_user.email,
                retry_timestamp=datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC'),
                admin_url=admin_url,
                checkout_url=checkout_url
            )
            current_app.logger.info(f"Sent admin notification email for setup intent retry")
        except Exception as e:
            current_app.logger.error(f"Failed to send admin notification email: {e}")
            current_app.logger.error(f"Exception details: {str(e)}", exc_info=True)
        
        # Create appropriate message based on status
        if setup_intent.status == 'canceled':
            message = 'New checkout session created for canceled setup intent (likely 3D Secure timeout). Customer and admin notified.'
        else:
            message = f'New checkout session created for {setup_intent.status.replace("_", " ")} setup intent. Customer and admin notified.'
        
        return jsonify({
            'success': True,
            'checkout_url': session.url,
            'message': message,
            'setup_intent_status': setup_intent.status
        })
        
    except Exception as e:
        current_app.logger.error(f"Error retrying setup intent {setup_intent_id}: {e}")
        return jsonify({'error': str(e)}), 500

@admin_bp.route('/setup-intents/<setup_intent_id>', methods=['GET'])
@admin_required
def get_setup_intent(setup_intent_id):
    """Get detailed information about a setup intent."""
    try:
        stripe.api_key = current_app.config.get("STRIPE_SECRET_KEY")
        setup_intent = stripe.SetupIntent.retrieve(setup_intent_id)
        
        # Get user info if available
        user = None
        if setup_intent.customer:
            user = User.query.filter_by(cust_id=setup_intent.customer).first()
        
        return jsonify({
            'id': setup_intent.id,
            'status': setup_intent.status,
            'customer_id': setup_intent.customer,
            'user_email': user.email if user else 'Unknown',
            'created': datetime.fromtimestamp(setup_intent.created).strftime('%Y-%m-%d %H:%M:%S'),
            'payment_method_types': setup_intent.payment_method_types,
            'usage': setup_intent.usage,
            'next_action': setup_intent.next_action,
            'last_setup_error': setup_intent.last_setup_error,
            'client_secret': setup_intent.client_secret[:20] + "..." if setup_intent.client_secret else None
        })
        
    except Exception as e:
        current_app.logger.error(f"Error getting setup intent {setup_intent_id}: {e}")
        return jsonify({'error': str(e)}), 500

@admin_bp.route('/checkout-sessions')
@admin_required
def checkout_sessions():
    """Admin page to view checkout sessions."""
    return render_template('admin/checkout_sessions.html')

@admin_bp.route('/checkout-sessions/data')
@admin_required
@rate_limit_data_tables(max_requests=20, window_seconds=60)
def checkout_sessions_data():
    """Get checkout sessions data for admin dashboard."""
    try:
        draw = request.args.get('draw', type=int)
        start = request.args.get('start', type=int)
        length = request.args.get('length', type=int)
        search_value = request.args.get('search[value]', '')
        
        # Get checkout sessions from Stripe
        stripe.api_key = current_app.config.get("STRIPE_SECRET_KEY")
        
        if not stripe.api_key:
            current_app.logger.error("STRIPE_SECRET_KEY not configured")
            return jsonify({'error': 'Stripe API key not configured'}), 500
        
        # Get checkout sessions
        try:
            limit_param = length if length is not None else 10
            
            checkout_sessions = stripe.checkout.Session.list(
                limit=limit_param
            )
            current_app.logger.info(f"Retrieved {len(checkout_sessions.data)} checkout sessions from Stripe")
            
        except stripe.error.StripeError as e:
            current_app.logger.error(f"Stripe API error: {e}")
            return jsonify({'error': f'Stripe API error: {str(e)}'}), 500
        except Exception as e:
            current_app.logger.error(f"Unexpected error fetching checkout sessions: {e}")
            return jsonify({'error': f'Unexpected error: {str(e)}'}), 500
        
        data = []
        for session in checkout_sessions.data:
            # Get user info if available
            user = None
            if session.customer:
                user = User.query.filter_by(cust_id=session.customer).first()
            
            # Format amount
            amount_display = f"${session.amount_total / 100:.2f}" if session.amount_total else "N/A"
            
            # Determine status color
            status_class = ''
            if session.status == 'expired':
                status_class = 'badge bg-warning'
            elif session.status == 'complete':
                status_class = 'badge bg-success'
            elif session.status == 'open':
                status_class = 'badge bg-info'
            else:
                status_class = 'badge bg-secondary'
            
            data.append({
                'id': session.id,
                'status': session.status,
                'customer_id': session.customer,
                'user_email': user.email if user else 'Unknown',
                'created': datetime.fromtimestamp(session.created).strftime('%Y-%m-%d %H:%M:%S'),
                'expires_at': datetime.fromtimestamp(session.expires_at).strftime('%Y-%m-%d %H:%M:%S') if session.expires_at else 'N/A',
                'mode': session.mode,
                'amount_total': amount_display,
                'payment_status': session.payment_status,
                'actions': f'''
                    <button class="btn btn-sm btn-info view-checkout-session" data-id="{session.id}">View</button>
                '''
            })
        
        return jsonify({
            'draw': draw,
            'recordsTotal': len(checkout_sessions.data),
            'recordsFiltered': len(checkout_sessions.data),
            'data': data
        })
        
    except Exception as e:
        current_app.logger.error(f"checkout_sessions_data route failed: {e}")
        return jsonify({'error': 'Failed to load checkout sessions data'}), 500 

# ============================================================================
# REFERRAL JOURNEY ANALYTICS ROUTES
# ============================================================================

@admin_bp.route('/referral-journeys')
@admin_required
def referral_journeys():
    """Main referral journey analytics page."""
    return render_template('admin/referral_journeys.html')

@admin_bp.route('/api/analytics/referral-journeys')
@admin_required
def api_referral_journeys():
    """Get top referral codes with journey data."""
    days = request.args.get('days', 30, type=int)
    limit = request.args.get('limit', 10, type=int)
    
    try:
        from app.admin_utils import get_referral_codes_with_journeys
        data = get_referral_codes_with_journeys(days=days, limit=limit)
        return jsonify({'success': True, 'data': data})
    except Exception as e:
        current_app.logger.error(f"Error getting referral journeys: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@admin_bp.route('/api/analytics/referral-funnel/<ref_code>')
@admin_required
def api_referral_funnel(ref_code):
    """Get funnel data for a specific referral code."""
    days = request.args.get('days', 30, type=int)
    
    try:
        from app.admin_utils import get_referral_funnel_data
        data = get_referral_funnel_data(ref_code, days=days)
        return jsonify({'success': True, 'data': data})
    except Exception as e:
        current_app.logger.error(f"Error getting referral funnel for {ref_code}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@admin_bp.route('/api/analytics/referral-time/<ref_code>')
@admin_required
def api_referral_time_analysis(ref_code):
    """Get time-based analysis for a referral code."""
    days = request.args.get('days', 30, type=int)
    
    try:
        from app.admin_utils import get_referral_time_analysis
        data = get_referral_time_analysis(ref_code, days=days)
        return jsonify({'success': True, 'data': data})
    except Exception as e:
        current_app.logger.error(f"Error getting time analysis for {ref_code}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@admin_bp.route('/api/analytics/referral-geographic/<ref_code>')
@admin_required
def api_referral_geographic(ref_code):
    """Get geographic data for a referral code."""
    days = request.args.get('days', 30, type=int)
    
    try:
        from app.admin_utils import get_referral_geographic_data
        data = get_referral_geographic_data(ref_code, days=days)
        return jsonify({'success': True, 'data': data})
    except Exception as e:
        current_app.logger.error(f"Error getting geographic data for {ref_code}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@admin_bp.route('/api/analytics/referral-devices/<ref_code>')
@admin_required
def api_referral_devices(ref_code):
    """Get device data for a referral code."""
    days = request.args.get('days', 30, type=int)
    
    try:
        from app.admin_utils import get_referral_device_data
        data = get_referral_device_data(ref_code, days=days)
        return jsonify({'success': True, 'data': data})
    except Exception as e:
        current_app.logger.error(f"Error getting device data for {ref_code}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@admin_bp.route('/referral-journey/<ref_code>')
@admin_required
def referral_journey_detail(ref_code):
    """Detailed view for a specific referral code."""
    days = request.args.get('days', 30, type=int)
    
    try:
        from app.admin_utils import get_referral_journey_data, get_referral_funnel_data
        journey_data = get_referral_journey_data(ref_code, days=days)
        funnel_data = get_referral_funnel_data(ref_code, days=days)
        
        return render_template('admin/referral_journey_detail.html', 
                             ref_code=ref_code, 
                             journey_data=journey_data, 
                             funnel_data=funnel_data,
                             days=days)
    except Exception as e:
        current_app.logger.error(f"Error getting referral journey detail for {ref_code}: {e}")
        flash(f"Error loading referral journey data: {str(e)}", 'error')
        return redirect(url_for('admin.referral_journeys'))

@admin_bp.route('/system')
@admin_required
def system():
    # Get system statistics with cross-platform support
    from app.admin_utils import get_system_stats
    system_stats = get_system_stats()
    
    return render_template('admin/system.html', system_stats=system_stats)

@admin_bp.route('/api/system/stats')
@admin_required
def api_system_stats():
    try:
        from app.admin_utils import get_system_stats
        system_stats = get_system_stats()
        
        return jsonify({
            'success': True,
            'data': system_stats
        })
    except ImportError as e:
        return jsonify({
            'success': False,
            'error': f"Import error: {str(e)}",
            'data': {
                'cpu': 0.0,
                'memory': 0.0,
                'memory_used': 0.0,
                'memory_total': 0.0,
                'disk': 0.0,
                'disk_used': 0.0,
                'disk_total': 0.0
            }
        }), 500
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'data': {
                'cpu': 0.0,
                'memory': 0.0,
                'memory_used': 0.0,
                'memory_total': 0.0,
                'disk': 0.0,
                'disk_used': 0.0,
                'disk_total': 0.0
            }
        }), 500

# Initialize signer once (if cert path provided and pyHanko installed)
_SIGNER: Optional[object] = None
if SIGNING_AVAILABLE:
    if (cert_path := os.environ.get("SIGN_CERT")):
        pw = os.environ.get("SIGN_CERT_PASSWORD", "").encode()
        try:
            with open(cert_path, "rb") as fp:
                _SIGNER = signers.SimpleSigner.load_pkcs12(fp.read(), pw)
        except (FileNotFoundError, ValueError) as exc:
            print(f"[WARN] Cannot load signing cert: {exc}. Signing disabled.")
            _SIGNER = None
    else:
        print("[INFO] No signing certificate configured; signing disabled.")
else:
    print("[INFO] pyHanko not installed; signing disabled.")

def compress_pdf(data: bytes) -> bytes:
    """Compress/optimise PDF using pikepdf (object streams + garbage collect)."""
    if pikepdf is None:
        raise RuntimeError("pikepdf not installed – cannot compress")
    pdf = pikepdf.open(BytesIO(data))
    out = BytesIO()
    pdf.save(out, object_stream_mode=pikepdf.ObjectStreamMode.generate, compress_streams=True)
    return out.getvalue()

def sign_pdf(data: bytes) -> bytes:
    """Sign PDF using pyHanko if signer configured."""
    if _SIGNER is None:
        raise RuntimeError("Signer unavailable – missing cert or pyHanko")
    meta = PdfSignatureMetadata(field_name="Signature1")
    signer = PdfSigner(meta, _SIGNER)
    return signer.sign_pdf(BytesIO(data))

def add_signature_to_pdf(pdf_data: bytes, signature_data: dict) -> bytes:
    """Add signature to PDF using reportlab."""
    if not REPORTLAB_AVAILABLE:
        raise RuntimeError("ReportLab not available – cannot add signature")
    
    try:
        # Open the PDF with pikepdf
        pdf = pikepdf.open(BytesIO(pdf_data))
        
        # Get the target page
        page_num = signature_data.get('page', 1)
        if page_num == 'last':
            target_page = len(pdf.pages) - 1
        else:
            target_page = int(page_num) - 1
        
        if target_page >= len(pdf.pages):
            target_page = len(pdf.pages) - 1
        
        page = pdf.pages[target_page]
        
        # Get page dimensions
        page_width = float(page.mediabox[2])
        page_height = float(page.mediabox[3])
        
        # Get signature positions from the new format
        positions = signature_data.get('positions', [])
        if not positions:
            # Fallback to old format for backward compatibility
            position = signature_data.get('position', 'bottom-right')
            signature_width = 2 * inch  # 2 inches wide
            signature_height = 0.5 * inch  # 0.5 inches tall
            
            # Auto-detect signature fields if requested
            if position == 'auto-detect':
                signature_fields = detect_signature_fields(pdf, target_page)
                if signature_fields:
                    # Use the first detected signature field
                    field = signature_fields[0]
                    x = field['x']
                    y = field['y']
                    signature_width = field['width']
                    signature_height = field['height']
                else:
                    # Fallback to bottom-right if no fields detected
                    x = page_width - signature_width - 0.5 * inch
                    y = 0.5 * inch
            else:
                # Manual positioning
                if position == 'bottom-right':
                    x = page_width - signature_width - 0.5 * inch
                    y = 0.5 * inch
                elif position == 'bottom-left':
                    x = 0.5 * inch
                    y = 0.5 * inch
                elif position == 'center':
                    x = (page_width - signature_width) / 2
                    y = (page_height - signature_height) / 2
                elif position == 'top-right':
                    x = page_width - signature_width - 0.5 * inch
                    y = page_height - signature_height - 0.5 * inch
                elif position == 'top-left':
                    x = 0.5 * inch
                    y = page_height - signature_height - 0.5 * inch
                else:
                    x = page_width - signature_width - 0.5 * inch
                    y = 0.5 * inch
            
            positions = [{'x': x, 'y': y, 'width': signature_width, 'height': signature_height}]
        
        # Create a temporary PDF with the signature
        temp_pdf = BytesIO()
        c = canvas.Canvas(temp_pdf, pagesize=(page_width, page_height))
        
        signature_type = signature_data.get('type', 'drawn')
        
        # Process each signature position
        for pos in positions:
            x = pos['x']
            y = pos['y']
            signature_width = pos['width']
            signature_height = pos['height']
            
            if signature_type == 'drawn':
                # Draw the signature paths
                paths = signature_data.get('paths', [])
                if paths:
                    # Scale the signature to fit the allocated space
                    canvas_width = 600  # Original canvas width
                    canvas_height = 200  # Original canvas height
                    scale_x = signature_width / canvas_width
                    scale_y = signature_height / canvas_height
                    scale = min(scale_x, scale_y)
                    
                    c.setStrokeColorRGB(0, 0, 0)  # Black color
                    c.setLineWidth(2 * scale)
                    
                    for path in paths:
                        if len(path) > 1:
                            c.moveTo(x + path[0]['x'] * scale, y + signature_height - path[0]['y'] * scale)
                            for point in path[1:]:
                                c.lineTo(x + point['x'] * scale, y + signature_height - point['y'] * scale)
                            c.stroke()
            
            elif signature_type == 'typed':
                # Add typed signature
                text = signature_data.get('text', '')
                font_name = signature_data.get('font', 'Dancing Script')
                font_size = signature_data.get('size', 14)
                
                # Try to register the font if it's a custom font
                try:
                    if font_name == 'Dancing Script':
                        # Try to register Dancing Script font
                        try:
                            pdfmetrics.registerFont(TTFont('Dancing Script', 'static/fonts/DancingScript-Regular.ttf'))
                            actual_font_name = 'Dancing Script'
                        except Exception as font_reg_error:
                            # Fallback to a standard font if Dancing Script is not available
                            actual_font_name = 'Helvetica'
                    else:
                        actual_font_name = font_name
                    
                    # Set font and color
                    c.setFont(actual_font_name, font_size)
                    c.setFillColorRGB(0, 0, 0)  # Black color
                    
                    # Calculate text position (center in the signature area)
                    text_width = c.stringWidth(text, actual_font_name, font_size)
                    text_x = x + (signature_width - text_width) / 2
                    text_y = y + signature_height / 2 + 5  # Center vertically with slight offset
                    
                    c.drawString(text_x, text_y, text)
                    
                except Exception as font_error:
                    # Fallback to Helvetica if any font error occurs
                    c.setFont('Helvetica', font_size)
                    c.setFillColorRGB(0, 0, 0)  # Black color
                    
                    # Calculate text position (center in the signature area)
                    text_width = c.stringWidth(text, 'Helvetica', font_size)
                    text_x = x + (signature_width - text_width) / 2
                    text_y = y + signature_height / 2 + 5  # Center vertically with slight offset
                    
                    c.drawString(text_x, text_y, text)
        
        c.save()
        temp_pdf.seek(0)
        
        # Overlay the signature on the original PDF
        signature_pdf = pikepdf.open(temp_pdf)
        signature_page = signature_pdf.pages[0]
        
        # Add the signature page as an overlay for each position
        for pos in positions:
            x = pos['x']
            y = pos['y']
            signature_width = pos['width']
            signature_height = pos['height']
            page.add_overlay(signature_page, pikepdf.Rectangle(x, y, x + signature_width, y + signature_height))
        
        # Save the result
        output = BytesIO()
        pdf.save(output)
        output.seek(0)
        
        return output.getvalue()
        
    except Exception as e:
        raise RuntimeError(f"Failed to add signature to PDF: {str(e)}")

def detect_signature_fields(pdf, page_index):
    """Detect signature fields in PDF forms."""
    try:
        page = pdf.pages[page_index]
        signature_fields = []
        
        # Look for form fields that might be signature fields
        if hasattr(page, 'annotations'):
            for annotation in page.annotations:
                if hasattr(annotation, 'subtype') and annotation.subtype == '/Widget':
                    # Check if it's a signature field
                    if hasattr(annotation, 'ft') and annotation.ft == '/Sig':
                        # Get field coordinates
                        rect = annotation.rect
                        if rect:
                            signature_fields.append({
                                'x': float(rect[0]),
                                'y': float(rect[1]),
                                'width': float(rect[2]) - float(rect[0]),
                                'height': float(rect[3]) - float(rect[1])
                            })
        
        # Also look for text fields that might be signature fields
        if hasattr(page, 'annotations'):
            for annotation in page.annotations:
                if hasattr(annotation, 'subtype') and annotation.subtype == '/Widget':
                    if hasattr(annotation, 'ft') and annotation.ft == '/Tx':
                        # Check field name for signature-related keywords
                        field_name = getattr(annotation, 't', '').lower()
                        if any(keyword in field_name for keyword in ['signature', 'sign', 'sig', 'name']):
                            rect = annotation.rect
                            if rect:
                                signature_fields.append({
                                    'x': float(rect[0]),
                                    'y': float(rect[1]),
                                    'width': float(rect[2]) - float(rect[0]),
                                    'height': float(rect[3]) - float(rect[1])
                                })
        
        return signature_fields
        
    except Exception as e:
        print(f"Warning: Could not detect signature fields: {e}")
        return []



@admin_bp.route('/pdf-tool')
@admin_required
def pdf_tool():
    """PDF Tool page - improved interface with drag-and-drop signature placement"""
    return render_template('admin/pdf_tool.html')





@admin_bp.route('/pdf-tool/process', methods=['POST'])
@admin_required
def pdf_tool_process():
    """Process uploaded PDF - compress and/or sign"""
    uploaded = request.files.get("pdf_file")
    if not uploaded or not uploaded.filename.lower().endswith(".pdf"):
        return jsonify({"error": "Please upload a PDF file."}), 400
    
    original_data = uploaded.read()
    original_size = len(original_data)
    pdf_data = original_data
    
    compression_stats = None
    
    # Apply compression if requested & possible
    if "compress" in request.form:
        try:
            pdf_data = compress_pdf(pdf_data)
            compressed_size = len(pdf_data)
            reduction = ((original_size - compressed_size) / original_size) * 100
            compression_stats = {
                'original_size': original_size,
                'compressed_size': compressed_size,
                'reduction_percent': round(reduction, 1)
            }
        except Exception as exc:
            return jsonify({"error": f"Compression failed: {exc}"}), 400
    
    # Apply drawn signature if requested
    if "add_signature" in request.form:
        signature_data_str = request.form.get('signature_data')
        if signature_data_str:
            try:
                signature_data = json.loads(signature_data_str)
                pdf_data = add_signature_to_pdf(pdf_data, signature_data)
            except Exception as exc:
                return jsonify({"error": f"Signature addition failed: {exc}"}), 400
    
    # Apply digital certificate signature if requested & possible
    if "digital_sign" in request.form:
        if _SIGNER is None:
            return jsonify({"error": "Digital signing not configured on server."}), 400
        try:
            pdf_data = sign_pdf(pdf_data)
        except Exception as exc:
            return jsonify({"error": f"Digital signing failed: {exc}"}), 400
    
    # Create response with compression stats if available
    response = send_file(
        BytesIO(pdf_data),
        as_attachment=True,
        download_name=f"{os.path.splitext(uploaded.filename)[0]}_processed.pdf",
        mimetype="application/pdf"
    )
    
    if compression_stats:
        response.headers['X-Compression-Stats'] = json.dumps(compression_stats)
    
    return response

