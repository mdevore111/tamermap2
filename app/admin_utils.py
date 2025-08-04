import psutil
from datetime import datetime, timedelta
from sqlalchemy import func, desc, and_, or_, case
from .models import User, VisitorLog, Event, Retailer, Message, Role

def exclude_monitor_traffic(query):
    """Filter out monitor traffic from analytics queries"""
    return query.filter(~VisitorLog.user_agent.contains('Tamermap-Monitor'))
from collections import defaultdict
from urllib.parse import urlparse
from app import db


def get_system_stats():
    """Get system resource statistics with cross-platform support."""
    try:
        # CPU usage
        cpu_percent = psutil.cpu_percent(interval=1)
        
        # Memory usage
        memory = psutil.virtual_memory()
        memory_percent = memory.percent
        memory_used_gb = memory.used / (1024**3)
        memory_total_gb = memory.total / (1024**3)
        
        # Disk usage - handle different OS paths
        try:
            # Try root directory first (Linux/Unix)
            disk = psutil.disk_usage('/')
        except (OSError, FileNotFoundError):
            try:
                # Try Windows C: drive
                disk = psutil.disk_usage('C:\\')
            except (OSError, FileNotFoundError):
                # Fallback to current working directory
                import os
                disk = psutil.disk_usage(os.getcwd())
        
        disk_percent = disk.percent
        disk_used_gb = disk.used / (1024**3)
        disk_total_gb = disk.total / (1024**3)
        
        return {
            'cpu': round(cpu_percent, 1),
            'memory': round(memory_percent, 1),
            'memory_used': round(memory_used_gb, 1),
            'memory_total': round(memory_total_gb, 1),
            'disk': round(disk_percent, 1),
            'disk_used': round(disk_used_gb, 1),
            'disk_total': round(disk_total_gb, 1)
        }
    except Exception as e:
        # Return safe defaults if any error occurs
        return {
            'cpu': 0.0,
            'memory': 0.0,
            'memory_used': 0.0,
            'memory_total': 0.0,
            'disk': 0.0,
            'disk_used': 0.0,
            'disk_total': 0.0
        }

def get_batched_user_metrics():
    """Get all user-related metrics in batched queries"""
    now = datetime.utcnow()
    thirty_days_ago = now - timedelta(days=30)
    twenty_four_hours_ago = now - timedelta(days=1)
    
    # Single query to get user counts and pro user statistics
    user_stats = db.session.query(
        func.count(User.id).label('total_users'),
        func.count(case((User.active == True, 1))).label('active_users'),
        func.count(case((User.pro_end_date > now, 1))).label('pro_users'),
        func.count(case((
            or_(User.pro_end_date.is_(None), User.pro_end_date <= now) & 
            User.confirmed_at.isnot(None), 1
        ))).label('basic_users'),
        func.count(case((
            (User.pro_end_date > now) & (User.confirmed_at >= thirty_days_ago), 1
        ))).label('new_pro_users_30d'),
        func.count(case((
            (User.pro_end_date > now) & (User.confirmed_at >= twenty_four_hours_ago), 1
        ))).label('new_pro_users_24h'),
        func.count(case((
            (User.pro_end_date > now) & (User.last_login >= thirty_days_ago), 1
        ))).label('pro_users_active_30d'),
        func.count(case((
            (User.pro_end_date > now) & (User.last_login >= twenty_four_hours_ago), 1
        ))).label('pro_users_active_24h'),
        func.count(case((User.confirmed_at >= thirty_days_ago, 1))).label('user_growth_30d')
    ).first()
    
    # Get pro user login statistics
    pro_users = User.query.filter(User.pro_end_date > now).all()
    
    if pro_users:
        total_logins = sum(u.login_count or 0 for u in pro_users)
        logins = sorted([u.login_count or 0 for u in pro_users])
        n = len(logins)
        
        avg_logins = round(total_logins / len(pro_users), 1) if pro_users else 0.0
        
        if n == 0:
            median_logins = 0
        else:
            mid = n // 2
            if n % 2 == 0:
                median_logins = (logins[mid - 1] + logins[mid]) // 2
            else:
                median_logins = logins[mid]
    else:
        avg_logins = 0.0
        median_logins = 0
    
    # Calculate conversion rate
    new_users_30d = user_stats.user_growth_30d or 0
    pro_conversion_rate = round(
        (user_stats.new_pro_users_30d or 0) / new_users_30d, 2
    ) if new_users_30d > 0 else 0.0
    
    return {
        'total_users': user_stats.total_users or 0,
        'active_users': user_stats.active_users or 0,
        'pro_users': user_stats.pro_users or 0,
        'basic_users': user_stats.basic_users or 0,
        'new_pro_users_30d': user_stats.new_pro_users_30d or 0,
        'new_pro_users_24h': user_stats.new_pro_users_24h or 0,
        'pro_users_active_30d': user_stats.pro_users_active_30d or 0,
        'pro_users_active_24h': user_stats.pro_users_active_24h or 0,
        'user_growth_30d': user_stats.user_growth_30d or 0,
        'avg_logins_per_pro_user': avg_logins,
        'median_logins_per_pro_user': median_logins,
        'pro_conversion_rate_30d': pro_conversion_rate
    }

def get_batched_content_metrics():
    """Get all content-related metrics in batched queries"""
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    
    # Single query for basic content counts
    content_stats = db.session.query(
        func.count(Event.id).label('total_events'),
        func.count(case((Event.timestamp >= thirty_days_ago, 1))).label('event_growth_30d'),
        func.count(Retailer.id).label('total_retailers'),
        func.count(case((func.lower(Retailer.retailer_type) == 'kiosk', 1))).label('kiosk_retailers'),
        func.count(case((func.lower(Retailer.retailer_type) == 'card shop', 1))).label('card_shops'),
        func.count(case((func.lower(Retailer.retailer_type) == 'store', 1))).label('stores'),
        func.count(case((Retailer.machine_count > 0, 1))).label('kiosk_machines'),
        func.count(Message.id).label('total_messages')
    ).select_from(
        Event.__table__.outerjoin(Retailer.__table__).outerjoin(Message.__table__)
    ).first()
    
    return {
        'total_events': content_stats.total_events or 0,
        'event_growth_30d': content_stats.event_growth_30d or 0,
        'total_retailers': content_stats.total_retailers or 0,
        'kiosk_retailers': content_stats.kiosk_retailers or 0,
        'card_shops': content_stats.card_shops or 0,
        'stores': content_stats.stores or 0,
        'kiosk_machines': content_stats.kiosk_machines or 0,
        'total_messages': content_stats.total_messages or 0
    }

def get_batched_visitor_metrics():
    """Get all visitor-related metrics in batched queries"""
    now = datetime.utcnow()
    today = now.date()
    week_ago = now - timedelta(days=7)
    thirty_days_ago = now - timedelta(days=30)
    twenty_four_hours_ago = now - timedelta(days=1)
    start_of_month = datetime(now.year, now.month, 1)
    
    # Single comprehensive visitor query
    visitor_stats = db.session.query(
        func.count(VisitorLog.id).label('total_visitors'),
        func.count(func.distinct(VisitorLog.ip_address)).filter(
            func.date(VisitorLog.timestamp) == today
        ).label('visitors_today'),
        func.count(func.distinct(VisitorLog.ip_address)).filter(
            VisitorLog.timestamp >= week_ago
        ).label('visitors_this_week'),
        func.count(case((VisitorLog.timestamp >= thirty_days_ago, 1))).label('total_visits_30d'),
        func.count(case((
            (VisitorLog.timestamp >= thirty_days_ago) & (VisitorLog.user_id.isnot(None)), 1
        ))).label('pro_user_visits_30d'),
        func.count(case((
            (VisitorLog.timestamp >= thirty_days_ago) & (VisitorLog.user_id.is_(None)), 1
        ))).label('guest_visits_30d'),
        func.count(func.distinct(VisitorLog.ip_address)).filter(
            VisitorLog.timestamp >= twenty_four_hours_ago
        ).label('unique_ips_24h'),
        func.count(func.distinct(VisitorLog.ip_address)).filter(
            VisitorLog.timestamp >= week_ago
        ).label('unique_ips_7d'),
        func.count(func.distinct(VisitorLog.ip_address)).filter(
            VisitorLog.timestamp >= start_of_month
        ).label('unique_ips_month'),
        func.count(case((
            (VisitorLog.timestamp >= thirty_days_ago) & 
            (VisitorLog.referrer.isnot(None)) & 
            (VisitorLog.referrer != ''), 1
        ))).label('visits_with_referrers_30d'),
        func.count(func.distinct(VisitorLog.referrer)).filter(
            VisitorLog.timestamp >= thirty_days_ago,
            VisitorLog.referrer.isnot(None),
            VisitorLog.referrer != ''
        ).label('unique_referrers_30d'),
        func.count(case((
            (VisitorLog.timestamp >= thirty_days_ago) & 
            ((VisitorLog.referrer.is_(None)) | (VisitorLog.referrer == '')), 1
        ))).label('direct_visits_30d')
    ).first()
    
    # Calculate derived metrics
    total_visits_30d = visitor_stats.total_visits_30d or 0
    guest_visits_30d = visitor_stats.guest_visits_30d or 0
    direct_visits_30d = visitor_stats.direct_visits_30d or 0
    unique_ips_30d = db.session.query(func.count(func.distinct(VisitorLog.ip_address))).filter(
        VisitorLog.timestamp >= thirty_days_ago
    ).scalar() or 0
    
    guest_visit_share = round(100 * guest_visits_30d / total_visits_30d, 1) if total_visits_30d > 0 else 0.0
    direct_visit_percentage = round(100 * direct_visits_30d / total_visits_30d, 1) if total_visits_30d > 0 else 0.0
    visits_per_ip = round(total_visits_30d / unique_ips_30d, 1) if unique_ips_30d > 0 else 0.0
    
    return {
        'total_visitors': visitor_stats.total_visitors or 0,
        'visitors_today': visitor_stats.visitors_today or 0,
        'visitors_this_week': visitor_stats.visitors_this_week or 0,
        'total_page_visits_30d': total_visits_30d,
        'pro_user_visits_30d': visitor_stats.pro_user_visits_30d or 0,
        'guest_visits_30d': guest_visits_30d,
        'guest_visit_share_30d': guest_visit_share,
        'unique_ips_24h': visitor_stats.unique_ips_24h or 0,
        'unique_ips_7d': visitor_stats.unique_ips_7d or 0,
        'unique_ips_month': visitor_stats.unique_ips_month or 0,
        'visits_with_referrers_30d': visitor_stats.visits_with_referrers_30d or 0,
        'unique_referrers_30d': visitor_stats.unique_referrers_30d or 0,
        'direct_visits_30d': direct_visits_30d,
        'direct_visit_percentage_30d': direct_visit_percentage,
        'visits_per_unique_ip_30d': visits_per_ip
    }

def get_metrics():
    """Get all metrics for the admin dashboard using batched queries."""
    try:
        # Get metrics in batches to reduce database load
        user_metrics = get_batched_user_metrics()
        content_metrics = get_batched_content_metrics()
        visitor_metrics = get_batched_visitor_metrics()
        
        # Get top referrers and pages (these are complex queries that need separate handling)
        top_referrers = get_top_referrers()
        top_pages = get_top_pages()
        
        # Calculate avg visits per pro user (needs special handling)
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        active_pro_users = User.query.join(VisitorLog).filter(
            User.pro_end_date > datetime.utcnow(),
            VisitorLog.timestamp >= thirty_days_ago
        ).distinct().count()
        
        avg_visits_per_pro_user = round(
            visitor_metrics['pro_user_visits_30d'] / active_pro_users, 1
        ) if active_pro_users > 0 else 0.0
        
        # Combine all metrics
        all_metrics = {
            **user_metrics,
            **content_metrics, 
            **visitor_metrics,
            'top_referrers': top_referrers,
            'top_pages': top_pages,
            'avg_visits_per_pro_user_30d': avg_visits_per_pro_user,
            'monthly_retention_rate': get_monthly_retention_rate(),  # Keep separate due to complexity
            'avg_session_duration': 3.0  # Placeholder
        }
        
        return all_metrics
        
    except Exception as e:
        # Return safe defaults on error
        return {
            'total_users': 0, 'active_users': 0, 'pro_users': 0, 'basic_users': 0,
            'total_events': 0, 'total_retailers': 0, 'total_messages': 0,
            'total_visitors': 0, 'visitors_today': 0, 'visitors_this_week': 0,
            'top_referrers': [], 'top_pages': [],
            'user_growth': 0, 'event_growth': 0,
            'avg_logins_per_pro_user': 0.0, 'median_logins_per_pro_user': 0,
            'monthly_retention_rate': 0.0, 'avg_session_duration': 0.0,
            'visits_per_unique_ip_30d': 0.0, 'pro_users_active_24h': 0,
            'pro_users_active_30d': 0, 'new_pro_users_24h': 0,
            'new_pro_users_30d': 0, 'pro_conversion_rate_30d': 0.0,
            'kiosk_retailers': 0, 'card_shops': 0, 'stores': 0, 'kiosk_machines': 0,
            'total_page_visits_30d': 0, 'pro_user_visits_30d': 0, 'guest_visits_30d': 0,
            'guest_visit_share_30d': 0.0, 'avg_visits_per_pro_user_30d': 0.0,
            'unique_ips_24h': 0, 'unique_ips_7d': 0, 'unique_ips_month': 0,
            'visits_with_referrers_30d': 0, 'unique_referrers_30d': 0,
            'direct_visits_30d': 0, 'direct_visit_percentage_30d': 0.0
    }

def get_nav_links():
    """Get navigation links for the admin dashboard."""
    return [
        {'name': 'Dashboard', 'url': '/admin/', 'icon': 'fas fa-tachometer-alt'},
        {'name': 'Users', 'url': '/admin/users', 'icon': 'fas fa-users'},
        {'name': 'Visitors', 'url': '/admin/visitors', 'icon': 'fas fa-user-friends'},
        {'name': 'Visitor Logs', 'url': '/admin/visitor_logs', 'icon': 'fas fa-list'},
        {'name': 'Retailers', 'url': '/admin/retailers', 'icon': 'fas fa-store'},
        {'name': 'Events', 'url': '/admin/events', 'icon': 'fas fa-calendar'},
        {'name': 'Future Events', 'url': '/admin/future_events', 'icon': 'fas fa-calendar-plus'},
        {'name': 'Messages', 'url': '/admin/messages', 'icon': 'fas fa-envelope'},
        {'name': 'Analytics', 'url': '/admin/analytics', 'icon': 'fas fa-chart-line'},
        {'name': 'Top Pages', 'url': '/admin/top_pages', 'icon': 'fas fa-file-alt'},
        {'name': 'Top Referrers', 'url': '/admin/top_referrers', 'icon': 'fas fa-external-link-alt'},
        {'name': 'Top Ref Codes', 'url': '/admin/top_ref_codes', 'icon': 'fas fa-hashtag'},
        {'name': 'Settings', 'url': '/admin/settings', 'icon': 'fas fa-cog'}
    ]

def get_total_users():
    """Get total number of users."""
    return db.session.query(func.count(User.id)).scalar() or 0

def get_pro_users():
    """Get all pro users."""
    return User.query.filter(User.pro_end_date > datetime.utcnow()).all()

def get_total_events():
    """Get total number of events."""
    return db.session.query(func.count(Event.id)).scalar() or 0

def get_visitors_today():
    """Get number of unique visitors today (excluding monitor traffic)."""
    today = datetime.utcnow().date()
    return exclude_monitor_traffic(
        db.session.query(func.count(func.distinct(VisitorLog.ip_address)))
    ).filter(
        func.date(VisitorLog.timestamp) == today
    ).scalar() or 0

def get_visitors_this_week():
    """Get number of unique visitors this week (excluding monitor traffic)."""
    week_ago = datetime.utcnow() - timedelta(days=7)
    return exclude_monitor_traffic(
        db.session.query(func.count(func.distinct(VisitorLog.ip_address)))
    ).filter(
        VisitorLog.timestamp >= week_ago
    ).scalar() or 0

def get_top_referrers(limit=5, include_internal=False, days=None):
    """Get top referrers with count, domain, and full URL. Excludes internal referrers by default."""
    query = exclude_monitor_traffic(VisitorLog.query).with_entities(
        VisitorLog.referrer,
        VisitorLog.ref_code,
        func.count(VisitorLog.id).label('count')
    ).filter(
        VisitorLog.referrer.isnot(None),
        VisitorLog.referrer != ''
    )
    
    # Add date filter if specified
    if days:
        since = datetime.utcnow() - timedelta(days=days)
        query = query.filter(VisitorLog.timestamp >= since)
    
    if not include_internal:
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
    results = (
        query
        .group_by(VisitorLog.referrer, VisitorLog.ref_code)
        .order_by(desc('count'))
        .limit(limit)
        .all()
    )
    
    processed_results = []
    for r in results:
        referrer_url = r.referrer
        domain = 'Unknown'
        full_url = referrer_url
        
        # Try to extract domain from URL
        if referrer_url and referrer_url != 'Direct':
            try:
                # Add protocol if missing
                if not referrer_url.startswith(('http://', 'https://')):
                    referrer_url = 'https://' + referrer_url
                
                parsed = urlparse(referrer_url)
                domain = parsed.netloc
                if not domain:
                    domain = 'Unknown'
            except Exception:
                domain = 'Unknown'
        
        processed_results.append({
            'referrer': r.referrer,
            'ref_code': r.ref_code,
            'count': r.count,
            'domain': domain,
            'full_url': full_url
        })
    
    return processed_results

def get_top_pages(limit=5, days=None):
    """Get most visited pages with path and count."""
    query = exclude_monitor_traffic(VisitorLog.query).with_entities(
        VisitorLog.path, 
        func.count(VisitorLog.id).label('visits')
    )
    
    # Add date filter if specified
    if days:
        since = datetime.utcnow() - timedelta(days=days)
        query = query.filter(VisitorLog.timestamp >= since)
    
    results = (
        query
        .group_by(VisitorLog.path)
        .order_by(desc('visits'))
        .limit(limit)
        .all()
    )
    return [(r.path, r.visits) for r in results]

def get_top_ref_codes(limit=5, days=None):
    """Get most used referral codes with count."""
    query = exclude_monitor_traffic(VisitorLog.query).with_entities(
        VisitorLog.ref_code,
        func.count(VisitorLog.id).label('count')
    ).filter(
        VisitorLog.ref_code.isnot(None),
        VisitorLog.ref_code != ''
    )
    
    # Add date filter if specified
    if days:
        since = datetime.utcnow() - timedelta(days=days)
        query = query.filter(VisitorLog.timestamp >= since)
    
    results = (
        query
        .group_by(VisitorLog.ref_code)
        .order_by(desc('count'))
        .limit(limit)
        .all()
    )
    return [(r.ref_code, r.count) for r in results]

def get_user_growth():
    """Get user growth over the last 30 days."""
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    return User.query.filter(User.confirmed_at.isnot(None)).filter(User.confirmed_at >= thirty_days_ago).count()

def get_event_growth():
    """Get event growth over the last 30 days."""
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    return Event.query.filter(
        Event.timestamp >= thirty_days_ago
    ).count()

def get_avg_logins_per_pro_user():
    pro_users = User.query.filter(User.pro_end_date > datetime.utcnow()).all()
    if not pro_users:
        return 0.0
    total_logins = sum(u.login_count or 0 for u in pro_users)
    return round(total_logins / len(pro_users), 1)

def get_median_logins_per_pro_user():
    pro_users = User.query.filter(User.pro_end_date > datetime.utcnow()).all()
    logins = sorted([u.login_count or 0 for u in pro_users])
    n = len(logins)
    if n == 0:
        return 0
    mid = n // 2
    if n % 2 == 0:
        return (logins[mid - 1] + logins[mid]) // 2
    else:
        return logins[mid]

def get_monthly_retention_rate():
    # Users who logged in this month and last month
    now = datetime.utcnow()
    start_this_month = datetime(now.year, now.month, 1)
    if now.month == 1:
        start_last_month = datetime(now.year - 1, 12, 1)
    else:
        start_last_month = datetime(now.year, now.month - 1, 1)
    pro_users = User.query.filter(User.pro_end_date > datetime.utcnow()).all()
    retained = 0
    for u in pro_users:
        if u.last_login and u.last_login >= start_this_month and u.last_login < now:
            if u.last_login >= start_last_month:
                retained += 1
    if not pro_users:
        return 0.0
    return round(100 * retained / len(pro_users), 1)

def get_avg_session_duration():
    # Placeholder: requires session tracking, so return a dummy value
    return 3.0

def get_visits_per_unique_ip_30d():
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    total_visits = exclude_monitor_traffic(VisitorLog.query).filter(VisitorLog.timestamp >= thirty_days_ago).count()
    unique_ips = exclude_monitor_traffic(VisitorLog.query).filter(VisitorLog.timestamp >= thirty_days_ago).distinct(VisitorLog.ip_address).count()
    if unique_ips == 0:
        return 0.0
    return round(total_visits / unique_ips, 1)

def get_pro_users_active_last_24h():
    since = datetime.utcnow() - timedelta(days=1)
    return User.query.filter(User.pro_end_date > datetime.utcnow(), User.last_login >= since).count()

def get_pro_users_active_last_30d():
    since = datetime.utcnow() - timedelta(days=30)
    return User.query.filter(User.pro_end_date > datetime.utcnow(), User.last_login >= since).count()

def get_new_pro_users_last_24h():
    since = datetime.utcnow() - timedelta(days=1)
    return User.query.filter(User.pro_end_date > datetime.utcnow()).filter(User.confirmed_at.isnot(None)).filter(User.confirmed_at >= since).count()

def get_new_pro_users_last_30d():
    since = datetime.utcnow() - timedelta(days=30)
    return User.query.filter(User.pro_end_date > datetime.utcnow()).filter(User.confirmed_at.isnot(None)).filter(User.confirmed_at >= since).count()

def get_pro_conversion_rate_last_30d():
    since = datetime.utcnow() - timedelta(days=30)
    new_pro = get_new_pro_users_last_30d()
    new_users = User.query.filter(User.confirmed_at.isnot(None)).filter(User.confirmed_at >= since).count()
    if new_users == 0:
        return 0.0
    return round(new_pro / new_users, 2)

def get_total_retailers():
    return Retailer.query.count()

def get_kiosk_retailers():
    """Get count of unique retailers that have kiosks (machine_count > 0)."""
    return Retailer.query.filter(Retailer.machine_count > 0).count()

def get_total_kiosks():
    """Get total number of kiosk machines across all retailers."""
    return Retailer.query.with_entities(func.sum(Retailer.machine_count)).scalar() or 0

def get_card_shops():
    """Get count of retailers with retail_type 'Card Shop' (case insensitive)."""
    return Retailer.query.filter(func.lower(Retailer.retailer_type) == 'card shop').count()

def get_stores():
    """Get count of retailers with retail_type 'store' (case insensitive)."""
    return Retailer.query.filter(func.lower(Retailer.retailer_type) == 'store').count()

def get_kiosk_machines():
    return Retailer.query.filter(Retailer.machine_count > 0).count()

def get_total_page_visits_30d():
    since = datetime.utcnow() - timedelta(days=30)
    return VisitorLog.query.filter(VisitorLog.timestamp >= since).count()

def get_pro_user_visits_30d():
    since = datetime.utcnow() - timedelta(days=30)
    return VisitorLog.query.filter(VisitorLog.timestamp >= since, VisitorLog.user_id.isnot(None)).count()

def get_guest_visits_30d():
    since = datetime.utcnow() - timedelta(days=30)
    return VisitorLog.query.filter(VisitorLog.timestamp >= since, VisitorLog.user_id.is_(None)).count()

def get_guest_visit_share_30d():
    total = get_total_page_visits_30d()
    guest = get_guest_visits_30d()
    if total == 0:
        return 0.0
    return round(100 * guest / total, 1)

def get_avg_visits_per_pro_user_30d():
    """Get average number of visits per Pro user in the last 30 days."""
    since = datetime.utcnow() - timedelta(days=30)
    # Get Pro users who have visited in the last 30 days
    active_pro_users = User.query.join(VisitorLog).filter(
        User.pro_end_date > datetime.utcnow(),
        VisitorLog.timestamp >= since
    ).distinct().all()
    
    if not active_pro_users:
        return 0.0
        
    # Count total visits for these users
    total_visits = VisitorLog.query.filter(
        VisitorLog.timestamp >= since,
        VisitorLog.user_id.in_([u.id for u in active_pro_users])
    ).count()
    
    return round(total_visits / len(active_pro_users), 1)

def get_unique_ips_last_24h():
    since = datetime.utcnow() - timedelta(days=1)
    return VisitorLog.query.filter(VisitorLog.timestamp >= since).distinct(VisitorLog.ip_address).count()

def get_unique_ips_last_7d():
    since = datetime.utcnow() - timedelta(days=7)
    return VisitorLog.query.filter(VisitorLog.timestamp >= since).distinct(VisitorLog.ip_address).count()

def get_unique_ips_current_month():
    now = datetime.utcnow()
    start_of_month = datetime(now.year, now.month, 1)
    return VisitorLog.query.filter(VisitorLog.timestamp >= start_of_month).distinct(VisitorLog.ip_address).count()

def get_visits_with_referrers_30d():
    since = datetime.utcnow() - timedelta(days=30)
    return VisitorLog.query.filter(VisitorLog.timestamp >= since, VisitorLog.referrer.isnot(None), VisitorLog.referrer != '').count()

def get_unique_referrers_30d():
    since = datetime.utcnow() - timedelta(days=30)
    return VisitorLog.query.filter(VisitorLog.timestamp >= since, VisitorLog.referrer.isnot(None), VisitorLog.referrer != '').distinct(VisitorLog.referrer).count()

def get_direct_visits_30d():
    since = datetime.utcnow() - timedelta(days=30)
    return VisitorLog.query.filter(VisitorLog.timestamp >= since, (VisitorLog.referrer.is_(None) | (VisitorLog.referrer == ''))).count()

def get_direct_visit_percentage_30d():
    total = get_total_page_visits_30d()
    direct = get_direct_visits_30d()
    if total == 0:
        return 0.0
    return round(100 * direct / total, 1)

def get_visit_trends_30d(days=30):
    """Return daily visit trends for the last N days: total, pro user, and guest visits.
    
    Uses historical accuracy: counts users as Pro based on their status at the time of visit,
    not their current status. Excludes monitor traffic and admin users.
    
    Args:
        days (int): Number of days to look back (default: 30, max: 60)
    """
    if days < 1 or days > 60:
        days = 30
    
    since = datetime.utcnow().date() - timedelta(days=days-1)
    
    # Debug logging
    from flask import current_app
    current_app.logger.debug(f"Getting visit trends since {since}")
    
    # Query all visits in the last N days with user pro_end_date for historical accuracy
    # Exclude monitor traffic and admin users
    logs = (
        exclude_monitor_traffic(VisitorLog.query)
        .outerjoin(User, VisitorLog.user_id == User.id)
        .with_entities(
            func.date(VisitorLog.timestamp).label('date'),
            VisitorLog.user_id,
            VisitorLog.timestamp,
            User.pro_end_date
        )
        .filter(VisitorLog.timestamp >= since)
        .all()
    )
    
    current_app.logger.debug(f"Found {len(logs)} visitor log records (excluding monitor traffic)")
    
    # Prepare date buckets
    trends = defaultdict(lambda: {'total': 0, 'pro': 0, 'guest': 0})
    
    # Get admin user IDs to exclude them
    from app.models import Role
    admin_user_ids = set()
    try:
        admin_users = db.session.query(User.id).join(User.roles).filter(
            func.lower(db.text("role.name")) == 'admin'
        ).all()
        admin_user_ids = {user.id for user in admin_users}
    except Exception as e:
        current_app.logger.warning(f"Could not get admin user IDs: {e}")
    
    for log in logs:
        # Skip admin users
        if log.user_id in admin_user_ids:
            continue
            
        date = str(log.date)
        trends[date]['total'] += 1
        
        if log.user_id is None:
            # Guest visit
            trends[date]['guest'] += 1
        elif log.pro_end_date is not None and log.timestamp < log.pro_end_date:
            # User was Pro at the time of visit (historical accuracy)
            trends[date]['pro'] += 1
        else:
            # Registered user but not Pro at time of visit
            pass
    # Fill in missing days
    result = []
    for i in range(days):
        day = since + timedelta(days=i)
        day_str = day.strftime('%Y-%m-%d')
        t = trends[day_str]
        result.append({
            'date': day_str,
            'total': t['total'],
            'pro': t['pro'],
            'guest': t['guest']
        })
    
    # Calculate 7-day moving average for total visits
    moving_averages = []
    for i in range(len(result)):
        # Get the 7 days ending at current day (or fewer if at the beginning)
        start_idx = max(0, i - 6)  # 7-day window: current day + 6 previous days
        window_data = result[start_idx:i+1]
        
        if len(window_data) > 0:
            avg = sum(day['total'] for day in window_data) / len(window_data)
            moving_averages.append(round(avg, 1))
        else:
            moving_averages.append(0)
    
    # Add moving average to each result
    for i, item in enumerate(result):
        item['moving_average'] = moving_averages[i]
    
    return result

def get_pro_users_by_date():
    """Get pro users grouped by date."""
    pro_users = User.query.filter(User.pro_end_date > datetime.utcnow()).all()
    return group_users_by_date(pro_users)

def get_pro_users_by_region():
    """Get pro users grouped by region."""
    pro_users = User.query.filter(User.pro_end_date > datetime.utcnow()).all()
    return group_users_by_region(pro_users)

def get_active_pro_users(since):
    """Get count of pro users who logged in since date."""
    return User.query.filter(
        User.pro_end_date > datetime.utcnow(),
        User.last_login >= since
    ).count()

def get_new_pro_users(since):
    """Get count of new pro users since date."""
    return User.query.filter(
        User.pro_end_date > datetime.utcnow(),
        User.confirmed_at.isnot(None),
        User.confirmed_at >= since
    ).count()

def get_pro_user_ids():
    """Get set of pro user IDs."""
    return set(str(u.id) for u in User.query.filter(User.pro_end_date > datetime.utcnow()).all())

def get_3d_secure_attempts_last_30d():
    """Get count of 3D Secure authentication attempts in the last 30 days."""
    since = datetime.utcnow() - timedelta(days=30)
    return BillingEvent.query.filter(
        BillingEvent.event_type == 'setup_intent_requires_action',
        BillingEvent.event_timestamp >= since
    ).count()

def calculate_event_period(start_date):
    """Calculate the period category for an event based on its start date."""
    today = datetime.utcnow().date()
    
    # Handle both string and datetime dates
    if isinstance(start_date, str):
        try:
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
        except ValueError:
            return 'unknown'
    
    days_until = (start_date - today).days
    
    if days_until <= 30:
        return '0_30'
    elif days_until <= 60:
        return '31_60'
    else:
        return 'beyond_60'

def get_future_events_stats():
    """Get statistics for events grouped by period."""
    today = datetime.utcnow().date()
    
    # Get all events
    all_events = Event.query.all()
    total_events = len(all_events)
    
    # Get past events
    past_events = Event.query.filter(Event.start_date < today).count()
    
    # Get future events
    future_events = Event.query.filter(Event.start_date >= today).all()
    
    stats = {
        'total': total_events,
        'past': past_events,
        '0_30': 0,
        '31_60': 0
    }
    
    for event in future_events:
        period = calculate_event_period(event.start_date)
        if period in ['0_30', '31_60']:
            stats[period] += 1
    
    return stats

# ============================================================================
# REFERRAL JOURNEY TRACKING FUNCTIONS
# ============================================================================

def get_referral_codes_with_journeys(days=30, limit=10):
    """Get top referral codes with their journey statistics."""
    since = datetime.utcnow() - timedelta(days=days)
    
    # Get referral codes with visit counts
    # Apply exclude_monitor_traffic before limit() to avoid SQLAlchemy error
    base_query = db.session.query(
        VisitorLog.ref_code,
        func.count(VisitorLog.id).label('total_visits'),
        func.count(func.distinct(VisitorLog.ip_address)).label('unique_visitors')
    ).filter(
        VisitorLog.ref_code.isnot(None),
        VisitorLog.ref_code != '',
        VisitorLog.timestamp >= since
    ).group_by(VisitorLog.ref_code).order_by(func.count(VisitorLog.id).desc())
    
    # Apply monitor traffic exclusion first, then limit
    ref_codes = exclude_monitor_traffic(base_query).limit(limit).all()
    
    # Get journey data for each referral code
    results = []
    for ref_code, total_visits, unique_visitors in ref_codes:
        journey_data = get_referral_journey_data(ref_code, days)
        results.append({
            'ref_code': ref_code,
            'total_visits': total_visits,
            'unique_visitors': unique_visitors,
            'journey_data': journey_data
        })
    
    return results

def get_referral_journey_data(ref_code, days=30):
    """Get detailed journey data for a specific referral code."""
    since = datetime.utcnow() - timedelta(days=days)
    
    # Get all visits that started with this referral code
    initial_visits = exclude_monitor_traffic(
        VisitorLog.query.filter(
            VisitorLog.ref_code == ref_code,
            VisitorLog.timestamp >= since
        ).order_by(VisitorLog.timestamp)
    ).all()
    
    if not initial_visits:
        return {
            'total_sessions': 0,
            'avg_session_duration': 0,
            'page_flow': [],
            'conversion_rate': 0,
            'return_visits': 0
        }
    
    # Use session_id if available, otherwise fallback to IP + User Agent
    use_session_id = hasattr(VisitorLog, 'session_id') and any(v.session_id for v in initial_visits)
    
    if use_session_id:
        # Group by session_id (more accurate)
        sessions = {}
        for visit in initial_visits:
            if visit.session_id:
                if visit.session_id not in sessions:
                    sessions[visit.session_id] = []
                sessions[visit.session_id].append(visit)
        
        # Get all visits for these sessions
        session_ids = list(sessions.keys())
        all_visits = exclude_monitor_traffic(
            VisitorLog.query.filter(
                VisitorLog.session_id.in_(session_ids),
                VisitorLog.timestamp >= since
            ).order_by(VisitorLog.session_id, VisitorLog.timestamp)
        ).all()
        
        # Group all visits by session_id
        all_sessions = {}
        for visit in all_visits:
            if visit.session_id:
                if visit.session_id not in all_sessions:
                    all_sessions[visit.session_id] = []
                all_sessions[visit.session_id].append(visit)
    else:
        # Fallback to IP + User Agent grouping
        sessions = {}
        for visit in initial_visits:
            session_key = f"{visit.ip_address}_{visit.user_agent}"
            if session_key not in sessions:
                sessions[session_key] = []
            sessions[session_key].append(visit)
        
        # Get all visits for these sessions
        all_session_ips = list(set(visit.ip_address for visit in initial_visits))
        all_visits = exclude_monitor_traffic(
            VisitorLog.query.filter(
                VisitorLog.ip_address.in_(all_session_ips),
                VisitorLog.timestamp >= since
            ).order_by(VisitorLog.ip_address, VisitorLog.timestamp)
        ).all()
        
        # Group all visits by IP + User Agent
        all_sessions = {}
        for visit in all_visits:
            session_key = f"{visit.ip_address}_{visit.user_agent}"
            if session_key not in all_sessions:
                all_sessions[session_key] = []
            all_sessions[session_key].append(visit)
    
    # Analyze each session
    total_sessions = len(sessions)
    total_duration = 0
    page_counts = defaultdict(int)
    conversions = 0
    return_visits = 0
    
    for session_key, visits in all_sessions.items():
        # Sort visits by timestamp
        visits.sort(key=lambda x: x.timestamp)
        
        if len(visits) > 1:
            duration = (visits[-1].timestamp - visits[0].timestamp).total_seconds() / 60
            total_duration += duration
        
        # Count pages
        for visit in visits:
            page_counts[visit.path] += 1
        
        # Check for conversions (signup, pro upgrade, etc.)
        for visit in visits:
            if visit.user_id is not None:
                conversions += 1
                break
        
        # Check for return visits
        first_visit = visits[0]
        if use_session_id:
            # For session_id tracking, look for different session_ids from same IP
            later_visits = exclude_monitor_traffic(
                VisitorLog.query.filter(
                    VisitorLog.ip_address == first_visit.ip_address,
                    VisitorLog.timestamp > first_visit.timestamp + timedelta(hours=1),
                    VisitorLog.session_id != first_visit.session_id,
                    VisitorLog.session_id.isnot(None)
                )
            ).count()
        else:
            # For IP + User Agent tracking, look for different user agents
            later_visits = exclude_monitor_traffic(
                VisitorLog.query.filter(
                    VisitorLog.ip_address == first_visit.ip_address,
                    VisitorLog.timestamp > first_visit.timestamp + timedelta(hours=1),
                    VisitorLog.user_agent != first_visit.user_agent
                )
            ).count()
        
        if later_visits > 0:
            return_visits += 1
    
    avg_duration = total_duration / total_sessions if total_sessions > 0 else 0
    conversion_rate = (conversions / total_sessions * 100) if total_sessions > 0 else 0
    
    # Get top pages
    top_pages = sorted(page_counts.items(), key=lambda x: x[1], reverse=True)[:10]
    
    return {
        'total_sessions': total_sessions,
        'avg_session_duration': round(avg_duration, 1),
        'page_flow': [{'page': page, 'visits': count} for page, count in top_pages],
        'conversion_rate': round(conversion_rate, 1),
        'return_visits': return_visits,
        'tracking_method': 'session_id' if use_session_id else 'ip_user_agent'
    }

def get_referral_funnel_data(ref_code, days=30):
    """Get funnel data for a specific referral code."""
    since = datetime.utcnow() - timedelta(days=days)
    
    # Get all visits from this referral code
    visits = exclude_monitor_traffic(
        VisitorLog.query.filter(
            VisitorLog.ref_code == ref_code,
            VisitorLog.timestamp >= since
        ).order_by(VisitorLog.timestamp)
    ).all()
    
    if not visits:
        return []
    
    # Use session_id if available, otherwise fallback to IP + User Agent
    use_session_id = hasattr(VisitorLog, 'session_id') and any(v.session_id for v in visits)
    
    if use_session_id:
        # Group by session_id (more accurate)
        sessions = {}
        for visit in visits:
            if visit.session_id:
                if visit.session_id not in sessions:
                    sessions[visit.session_id] = []
                sessions[visit.session_id].append(visit)
    else:
        # Fallback to IP + User Agent grouping
        sessions = {}
        for visit in visits:
            session_key = f"{visit.ip_address}_{visit.user_agent}"
            if session_key not in sessions:
                sessions[session_key] = []
            sessions[session_key].append(visit)
    
    # Analyze funnel steps
    funnel_steps = {
        'entry': len(sessions),
        'first_page': 0,
        'maps_page': 0,
        'search_page': 0,
        'pin_interaction': 0,
        'signup': 0,
        'pro_upgrade': 0
    }
    
    for session_key, session_visits in sessions.items():
        pages_visited = [v.path for v in session_visits]
        user_ids = [v.user_id for v in session_visits if v.user_id is not None]
        
        # Count funnel steps
        if len(pages_visited) > 1:
            funnel_steps['first_page'] += 1
        
        if any('/maps' in page for page in pages_visited):
            funnel_steps['maps_page'] += 1
        
        if any('/search' in page for page in pages_visited):
            funnel_steps['search_page'] += 1
        
        # Check for pin interactions
        first_visit = session_visits[0]
        if use_session_id:
            # Use session_id for pin interaction matching
            pin_interactions = PinInteraction.query.filter(
                PinInteraction.session_id == first_visit.session_id
            ).count()
        else:
            # Fallback to IP-based matching
            pin_interactions = PinInteraction.query.filter(
                PinInteraction.session_id.like(f"%{first_visit.ip_address}%")
            ).count()
        
        if pin_interactions > 0:
            funnel_steps['pin_interaction'] += 1
        
        # Check for signups
        if user_ids:
            funnel_steps['signup'] += 1
            
            # Check for pro upgrades
            pro_users = User.query.filter(
                User.id.in_(user_ids),
                User.pro_end_date > datetime.utcnow()
            ).count()
            
            if pro_users > 0:
                funnel_steps['pro_upgrade'] += 1
    
    # Convert to funnel format
    funnel_data = []
    total = funnel_steps['entry']
    
    for step, count in funnel_steps.items():
        percentage = (count / total * 100) if total > 0 else 0
        funnel_data.append({
            'step': step,
            'count': count,
            'percentage': round(percentage, 1)
        })
    
    return funnel_data

def get_referral_time_analysis(ref_code, days=30):
    """Get time-based analysis for a referral code."""
    since = datetime.utcnow() - timedelta(days=days)
    
    # Get visits grouped by hour of day
    hourly_visits = exclude_monitor_traffic(
        db.session.query(
            func.extract('hour', VisitorLog.timestamp).label('hour'),
            func.count(VisitorLog.id).label('visits')
        ).filter(
            VisitorLog.ref_code == ref_code,
            VisitorLog.timestamp >= since
        ).group_by(func.extract('hour', VisitorLog.timestamp))
        .order_by(func.extract('hour', VisitorLog.timestamp))
    ).all()
    
    # Get visits grouped by day of week
    daily_visits = exclude_monitor_traffic(
        db.session.query(
            func.extract('dow', VisitorLog.timestamp).label('day'),
            func.count(VisitorLog.id).label('visits')
        ).filter(
            VisitorLog.ref_code == ref_code,
            VisitorLog.timestamp >= since
        ).group_by(func.extract('dow', VisitorLog.timestamp))
        .order_by(func.extract('dow', VisitorLog.timestamp))
    ).all()
    
    return {
        'hourly': [{'hour': int(h), 'visits': v} for h, v in hourly_visits],
        'daily': [{'day': int(d), 'visits': v} for d, v in daily_visits]
    }

def get_referral_geographic_data(ref_code, days=30):
    """Get geographic data for a referral code."""
    since = datetime.utcnow() - timedelta(days=days)
    
    # Get visits by location
    location_data = exclude_monitor_traffic(
        db.session.query(
            VisitorLog.city,
            VisitorLog.region,
            VisitorLog.country,
            func.count(VisitorLog.id).label('visits')
        ).filter(
            VisitorLog.ref_code == ref_code,
            VisitorLog.timestamp >= since,
            VisitorLog.city.isnot(None)
        ).group_by(VisitorLog.city, VisitorLog.region, VisitorLog.country)
        .order_by(func.count(VisitorLog.id).desc())
        .limit(20)
    ).all()
    
    return [{
        'city': city,
        'region': region,
        'country': country,
        'visits': visits
    } for city, region, country, visits in location_data]

def get_referral_device_data(ref_code, days=30):
    """Get device/browser data for a referral code."""
    since = datetime.utcnow() - timedelta(days=days)
    
    # Get visits by user agent
    device_data = exclude_monitor_traffic(
        db.session.query(
            VisitorLog.user_agent,
            func.count(VisitorLog.id).label('visits')
        ).filter(
            VisitorLog.ref_code == ref_code,
            VisitorLog.timestamp >= since
        ).group_by(VisitorLog.user_agent)
        .order_by(func.count(VisitorLog.id).desc())
        .limit(10)
    ).all()
    
    # Parse user agents into device types
    device_types = defaultdict(int)
    for user_agent, visits in device_data:
        if 'Mobile' in user_agent or 'Android' in user_agent or 'iPhone' in user_agent:
            device_types['Mobile'] += visits
        elif 'Tablet' in user_agent or 'iPad' in user_agent:
            device_types['Tablet'] += visits
        else:
            device_types['Desktop'] += visits
    
    return [{'device': device, 'visits': visits} for device, visits in device_types.items()]