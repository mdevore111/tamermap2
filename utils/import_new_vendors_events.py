#!/usr/bin/env python3
"""Tamermap – JSON → SQLite Import Utility
==========================================
Loads **retailers.json** and **events.json** from *project/instance/* and
bulk‑inserts them into **tamermap_data.db** using SQLAlchemy.

Pipeline
--------
1. **Backup** – calls ``utils/backup_db.py``; aborts if the backup fails.
2. **Load JSON** – warns (does *not* abort) if one or both JSON files are
   missing; ensures dates are in YYYY-MM-DD format and times in HH:mm format.
3. **Normalise** – converts blank strings to ``None`` to avoid type errors.
4. **Insert** – reflects the current DB schema and inserts rows in a single
   transaction for each table.

Paths are calculated relative to this script, so it works no matter the
current working directory.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
from datetime import datetime
from typing import Final, List, Dict, Any

from sqlalchemy import create_engine, insert, MetaData, text, Table, Column, Integer, String, Float, DateTime, Time

# ---------------------------------------------------------------------------
# Logging – file + console
# ---------------------------------------------------------------------------
LOG_DIR = os.path.join(os.path.dirname(__file__), "logs")
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "import_new_vendors_events.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s: %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants – paths resolved from script location
# ---------------------------------------------------------------------------
PROJECT_ROOT: Final[str] = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
INSTANCE_DIR: Final[str] = os.path.join(PROJECT_ROOT, "instance")
DB_PATH: Final[str] = os.path.join(INSTANCE_DIR, "tamermap_data.db")
RETAILERS_JSON: Final[str] = os.path.join(INSTANCE_DIR, "retailers.json")
EVENTS_JSON: Final[str] = os.path.join(INSTANCE_DIR, "events.json")

# Keys that should be parsed as dates/times
DATE_KEYS: Final[set[str]] = {"start_date", "end_date"}
TIME_KEYS: Final[set[str]] = {"start_time", "end_time"}
DATETIME_KEYS: Final[set[str]] = {"first_seen", "last_api_update"}

# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------

def standardize_date(date_str: str) -> str:
    """Convert date string to YYYY-MM-DD format"""
    if not date_str:
        return None
    try:
        # Try parsing as YYYY-MM-DD first
        datetime.strptime(date_str, '%Y-%m-%d')
        return date_str
    except ValueError:
        try:
            # Try parsing as MMM d, YYYY
            date = datetime.strptime(date_str, '%B %d, %Y')
            return date.strftime('%Y-%m-%d')
        except ValueError:
            logger.warning(f"Could not parse date: {date_str}")
            return date_str

def standardize_time(time_str: str) -> str:
    """Convert time string to HH:mm format"""
    if not time_str:
        return None
    formats = ['%H:%M', '%I:%M%p', '%H:%M:%S']
    for fmt in formats:
        try:
            time = datetime.strptime(time_str.strip(), fmt)
            return time.strftime('%H:%M')
        except ValueError:
            continue
    logger.warning(f"Could not parse time: {time_str}")
    return time_str

def try_parse_datetime(val: str) -> Any:
    """Return a datetime object if *val* looks ISO‑formatted, else the original string."""
    if isinstance(val, datetime):
        return val
    try:
        return datetime.fromisoformat(val)
    except Exception:
        return val

def load_json(path: str) -> list[dict]:
    if not os.path.exists(path):
        logger.error("Required file not found -> %s", path)
        sys.exit(1)
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)

        for item in data:
            # Handle date fields
            for key in DATE_KEYS:
                if key in item and isinstance(item[key], str):
                    item[key] = standardize_date(item[key])

            # Handle time fields
            for key in TIME_KEYS:
                if key in item and isinstance(item[key], str):
                    item[key] = standardize_time(item[key])

            # Handle datetime fields - keep as datetime objects for retailers table
            for key in DATETIME_KEYS:
                if key in item and isinstance(item[key], str):
                    item[key] = try_parse_datetime(item[key])

        logger.info("Loaded %d records from %s", len(data), path)
        return data
    except Exception as e:
        logger.error("Failed to load JSON from %s: %s", path, e)
        sys.exit(1)

def clean_empty_strings(data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Convert blank strings in *data* to ``None`` (avoids SQLite type errors)."""
    for item in data:
        for k, v in item.items():
            if isinstance(v, str) and v.strip() == "":
                item[k] = None
    return data

# ---------------------------------------------------------------------------
# Main: backup → load JSON → truncate → insert
# ---------------------------------------------------------------------------

def main() -> None:
    """Back up DB, load JSON, wipe existing rows, then bulk‑insert."""
    # 1) Run backup script
    backup_script = os.path.join(os.path.dirname(__file__), "backup_db.py")
    if not os.path.isfile(backup_script):
        logger.error("Backup script not found: %s", backup_script)
        sys.exit(1)
    try:
        logger.info("Running backup script: %s", backup_script)
        subprocess.run([sys.executable, backup_script], check=True)
        logger.info("Backup completed.")
    except subprocess.CalledProcessError as e:
        logger.error("Backup script failed: %s", e)
        sys.exit(1)

    # 2) Ensure database exists
    if not os.path.exists(DB_PATH):
        logger.error("Database file '%s' does not exist!", DB_PATH)
        sys.exit(1)

    # 3) Load & normalise JSON
    retailers_data = clean_empty_strings(load_json(RETAILERS_JSON))
    events_data = clean_empty_strings(load_json(EVENTS_JSON))

    # 4) Define tables explicitly instead of reflection
    engine = create_engine(f"sqlite:///{DB_PATH}")
    metadata = MetaData()
    
    events = Table('events', metadata,
        Column('id', Integer, primary_key=True),
        Column('event_title', String(255), nullable=False),
        Column('first_seen', String(100)),
        Column('full_address', String(255), nullable=False),
        Column('start_date', String(100)),
        Column('start_time', String(100)),
        Column('latitude', Float),
        Column('longitude', Float),
        Column('end_date', DateTime),
        Column('end_time', Time),
        Column('registration_url', String),
        Column('price', Float),
        Column('email', String),
        Column('phone', String),
        Column('timestamp', DateTime)
    )

    retailers = Table('retailers', metadata,
        Column('id', Integer, primary_key=True),
        Column('retailer', String(255)),
        Column('retailer_type', String(20)),
        Column('full_address', String(255), unique=True, nullable=False),
        Column('latitude', Float),
        Column('longitude', Float),
        Column('place_id', String(100)),
        Column('first_seen', DateTime),
        Column('phone_number', String(50)),
        Column('website', String(255)),
        Column('opening_hours', String),
        Column('rating', Float),
        Column('last_api_update', DateTime),
        Column('machine_count', Integer, default=0),
        Column('previous_count', Integer, default=0),
        Column('status', String(100))
    )

    try:
        with engine.begin() as conn:
            # -------- truncate both tables first -----------------
            conn.execute(text("DELETE FROM retailers"))
            logger.info("Cleared existing rows from retailers table")

            conn.execute(text("DELETE FROM events"))
            logger.info("Cleared existing rows from events table")
            # ------------------------------------------------------

            # Insert retailers
            if retailers_data:
                conn.execute(insert(retailers), retailers_data)
                logger.info("Inserted %d retailer rows", len(retailers_data))
            else:
                logger.info("No retailers to import")

            # Insert events
            if events_data:
                for event in events_data:
                    # Convert datetime fields to strings for events table
                    if 'first_seen' in event and isinstance(event['first_seen'], datetime):
                        event['first_seen'] = event['first_seen'].strftime('%Y-%m-%d %H:%M:%S')
                    
                    # Ensure start_date and start_time are strings
                    if 'start_date' in event:
                        event['start_date'] = str(event['start_date'])
                    if 'start_time' in event:
                        event['start_time'] = str(event['start_time'])
                    
                    # Handle end_date and end_time
                    if 'end_date' in event and event['end_date']:
                        try:
                            event['end_date'] = datetime.strptime(event['end_date'], '%Y-%m-%d')
                        except (ValueError, TypeError):
                            event['end_date'] = None
                    
                    if 'end_time' in event and event['end_time']:
                        try:
                            event['end_time'] = datetime.strptime(event['end_time'], '%H:%M').time()
                        except (ValueError, TypeError):
                            event['end_time'] = None
                    
                    # Ensure numeric fields are float or None
                    if 'price' in event and event['price'] is not None:
                        try:
                            event['price'] = float(event['price'])
                        except (ValueError, TypeError):
                            event['price'] = None
                    
                    try:
                        conn.execute(insert(events), event)
                    except Exception as e:
                        logger.error(f"Error inserting event: {event}")
                        logger.error(f"Exception: {e}")
                        raise
                logger.info("Inserted %d event rows", len(events_data))
            else:
                logger.info("No events to import")

    except Exception as exc:
        logger.error("Database insertion failed: %s", exc)
        sys.exit(1)

    logger.info("Import completed successfully ✅")

if __name__ == "__main__":
    main()
