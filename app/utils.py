# app/utils.py
import calendar
from datetime import datetime, timedelta
from flask import current_app
from sqlalchemy import text


def trial_period(days: int) -> datetime.date:
    """
    Calculate the end date of a trial period based on today's date.

    Args:
        days (int): The number of days to add to today's date.

    Returns:
        datetime.date: The date representing today plus the specified number of days.
    """
    # Get the current date.
    # today = datetime.today().date()
    # Return the date after adding the specified number of days.
    return datetime.utcnow() + timedelta(days=days)


def add_one_month(d: datetime.date) -> datetime.date:
    """
    Calculate the date one calendar month after a given date.

    This function accounts for months with fewer days by selecting the last valid day
    of the target month if necessary (e.g., moving from January 31st to February 28th or 29th).

    Args:
        d (datetime.date): The original date.

    Returns:
        datetime.date: The date exactly one calendar month later.
    """
    # Extract the year, month, and day from the input date.
    year = d.year
    month = d.month + 1  # Increment month by one.
    day = d.day

    # If the new month exceeds December, roll over to the next year.
    if month > 12:
        month -= 12
        year += 1

    # Determine the last valid day of the target month.
    last_day_of_target_month = calendar.monthrange(year, month)[1]
    # Ensure the day does not exceed the last valid day of the month.
    day = min(day, last_day_of_target_month)

    # Return the new date. Using __import__('datetime') avoids potential name conflicts.
    return __import__('datetime').date(year, month, day)


def get_retailer_locations(db, bounds=None, fields_only=True):
    """
    Retrieve retailer location records from the database with optional viewport filtering.

    Args:
        db: The SQLAlchemy database instance.
        bounds: Optional dict with 'north', 'south', 'east', 'west' for viewport filtering
        fields_only: If True, only return essential fields for map rendering

    Returns:
        list: A list of dictionaries containing retailer data.
    """
    try:
        # Build the base query with optimized field selection
        if fields_only:
            # Only select fields needed for map rendering (reduces payload by ~60%)
            base_query = """
                SELECT id, retailer, retailer_type, full_address, latitude, longitude, 
                       place_id, phone_number, opening_hours, machine_count, status, enabled
                FROM retailers
                WHERE latitude IS NOT NULL AND longitude IS NOT NULL
                  AND (status IS NULL OR LOWER(status) != 'disabled')
            """
        else:
            # Full query for admin or detailed views
            base_query = """
                SELECT id, retailer, retailer_type, full_address, latitude, longitude, 
                       place_id, first_seen, phone_number, website, opening_hours, rating, 
                       last_api_update, machine_count, previous_count, status, enabled
                FROM retailers
                WHERE latitude IS NOT NULL AND longitude IS NOT NULL
                  AND (status IS NULL OR LOWER(status) != 'disabled')
            """
        
        # Add viewport filtering if bounds provided
        if bounds:
            viewport_filter = """
                AND latitude BETWEEN :south AND :north
                AND longitude BETWEEN :west AND :east
            """
            base_query += viewport_filter
            
            # Add index hint for better performance
            base_query += " ORDER BY latitude, longitude"
            
            # Execute with bounds parameters
            with db.engine.connect() as connection:
                result = connection.execute(
                    text(base_query),
                    {
                        'north': float(bounds['north']),
                        'south': float(bounds['south']),
                        'east': float(bounds['east']),
                        'west': float(bounds['west'])
                    }
                )
                rows = [dict(row._mapping) for row in result]
        else:
            # Execute without bounds (full dataset)
            with db.engine.connect() as connection:
                result = connection.execute(text(base_query))
                rows = [dict(row._mapping) for row in result]
        
        return rows
        
    except Exception as e:
        current_app.logger.error(f"Failed to retrieve retailer locations: {str(e)}")
        return []


def format_date_for_display(date_str):
    """
    Format a date string from YYYY-MM-DD to MMM d, YYYY format
    """
    if not date_str:
        return ''
    try:
        date = datetime.strptime(date_str, '%Y-%m-%d')
        return date.strftime('%b %-d, %Y')
    except ValueError:
        return date_str


def format_time_for_display(time_str):
    """
    Format a time string from HH:mm to h:mm AM/PM format
    """
    if not time_str:
        return ''
    try:
        time = datetime.strptime(time_str, '%H:%M')
        return time.strftime('%-I:%M %p')
    except ValueError:
        return time_str


def parse_display_date(date_str):
    """
    Parse a date string from MMM d, YYYY format to YYYY-MM-DD
    """
    if not date_str:
        return ''
    try:
        date = datetime.strptime(date_str, '%b %d, %Y')
        return date.strftime('%Y-%m-%d')
    except ValueError:
        return date_str


def parse_display_time(time_str):
    """
    Parse a time string from h:mm AM/PM format to HH:mm
    """
    if not time_str:
        return ''
    try:
        time = datetime.strptime(time_str, '%I:%M %p')
        return time.strftime('%H:%M')
    except ValueError:
        return time_str


def get_event_locations(db, bounds=None, days_ahead=30):
    """
    Retrieve event location records from the database with optional filtering.

    Args:
        db: The SQLAlchemy database instance.
        bounds: Optional dict with 'north', 'south', 'east', 'west' for viewport filtering
        days_ahead: Only return events within this many days (default 30)

    Returns:
        list: A list of dictionaries containing event data.
    """
    try:
        # Build base query with date filtering
        base_query = """
            SELECT id, event_title, full_address, start_date, start_time,
                   latitude, longitude, first_seen
            FROM events
            WHERE latitude IS NOT NULL AND longitude IS NOT NULL
        """
        
        # Add date filtering for upcoming events only
        if days_ahead:
            base_query += " AND start_date >= date('now') AND start_date <= date('now', '+{} days')".format(days_ahead)
        
        # Add viewport filtering if bounds provided
        params = {}
        if bounds:
            viewport_filter = """
                AND latitude BETWEEN :south AND :north
                AND longitude BETWEEN :west AND :east
            """
            base_query += viewport_filter
            params = {
                'north': float(bounds['north']),
                'south': float(bounds['south']),
                'east': float(bounds['east']),
                'west': float(bounds['west'])
            }
        
        base_query += " ORDER BY start_date ASC"
        
        with db.engine.connect() as connection:
            if params:
                result = connection.execute(text(base_query), params)
            else:
                result = connection.execute(text(base_query))
            rows = [dict(row._mapping) for row in result]
            
    except Exception as e:
        current_app.logger.error(f"Failed to retrieve event locations: {e}")
        return []

    # Format dates and times for display
    for row in rows:
        row['start_date'] = format_date_for_display(row.get('start_date'))
        row['start_time'] = format_time_for_display(row.get('start_time'))

    return rows



