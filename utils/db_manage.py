#!/usr/bin/env python3
"""
db_manage.py

Database management utilities:
- Create timestamped backups
- List and inspect database schema
- Reset schema for data import

Usage:
    python db_manage.py [backup|schema|reset] [options]

Examples:
    # Create a backup
    python db_manage.py backup

    # List database schema
    python db_manage.py schema

    # Reset schema for import
    python db_manage.py reset
"""

import os
import sys
import sqlite3
import datetime
import shutil
import logging
import argparse
from typing import Optional

# ─── Logging Setup ─────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# ─── Path Setup ───────────────────────────────────────────────────────────────
UTILS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(UTILS_DIR)
INSTANCE_DIR = os.path.join(PROJECT_ROOT, "instance")
DB_PATH = os.path.join(INSTANCE_DIR, "tamermap_data.db")

def get_default_db_path() -> str:
    """Locate the SQLite database file."""
    candidate_paths = [
        os.path.join(UTILS_DIR, "..", "instance", "tamermap_data.db"),
        os.path.join(UTILS_DIR, "..", "..", "instance", "tamermap_data.db"),
        os.path.join(UTILS_DIR, "instance", "tamermap_data.db"),
    ]

    for path in candidate_paths:
        resolved = os.path.abspath(path)
        if os.path.exists(resolved):
            return resolved

    logger.error("Could not find tamermap_data.db in expected locations.")
    for path in candidate_paths:
        logger.error("→ Tried: %s", os.path.abspath(path))
    sys.exit(1)

def _sqlite_supports(conn: sqlite3.Connection, feature: str) -> bool:
    try:
        cur = conn.execute("select 1")
        cur.fetchall()
        if feature == "vacuum_into":
            # Best-effort probe – run VACUUM INTO on a temp file
            tmp_path = os.path.join(INSTANCE_DIR, "__vacuum_probe__.db")
            try:
                conn.execute(f"VACUUM INTO '{tmp_path}'")
                return True
            except sqlite3.OperationalError:
                return False
            finally:
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass
    except Exception:
        return False
    return False

def integrity_check(db_path: Optional[str] = None) -> bool:
    """Run PRAGMA integrity_check and return True if ok."""
    db = db_path or DB_PATH
    conn = sqlite3.connect(db)
    try:
        row = conn.execute("PRAGMA integrity_check").fetchone()
        ok = row and row[0].lower() == "ok"
        if ok:
            logger.info("Integrity check: ok (%s)", db)
        else:
            logger.error("Integrity check FAILED: %s", row[0] if row else "unknown")
        return bool(ok)
    finally:
        conn.close()

def backup_database() -> Optional[str]:
    """Create a timestamped, integrity-checked backup using VACUUM INTO/.backup."""
    if not os.path.exists(DB_PATH):
        logger.error("Database file '%s' does not exist!", DB_PATH)
        return None

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"tamermap_data_backup_{timestamp}.db"
    backup_path = os.path.join(INSTANCE_DIR, backup_name)

    conn = sqlite3.connect(DB_PATH)
    try:
        # Ensure WAL checkpoint to flush pages
        try:
            conn.execute("PRAGMA wal_checkpoint(FULL)")
        except Exception:
            pass

        if _sqlite_supports(conn, "vacuum_into"):
            logger.info("Using VACUUM INTO for consistent snapshot ...")
            conn.execute(f"VACUUM INTO '{backup_path}'")
        else:
            logger.info("Using .backup fallback for snapshot ...")
            # Use sqlite backup API for safe copy
            with sqlite3.connect(backup_path) as dst:
                conn.backup(dst)

    finally:
        conn.close()

    # Verify backup integrity
    if not integrity_check(backup_path):
        logger.error("Backup failed integrity check. Removing %s", backup_path)
        try:
            os.remove(backup_path)
        except Exception:
            pass
        return None

    logger.info("Backup created: %s", backup_path)
    return backup_path

def list_schema():
    """List all tables and their schema definitions."""
    db_path = get_default_db_path()
    logger.info("📦 Using database: %s", db_path)
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT name, sql FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()

    if not tables:
        logger.warning("⚠️  No tables found.")
    else:
        for name, schema in tables:
            logger.info("🗂️ Table: %s", name)
            logger.info("📄 Schema:\n%s", schema)
            logger.info("-" * 40)
    conn.close()

def reset_schema():
    """
    Reset database schema for data import.
    
    This function is used in the following scenarios:
    1. Initial database setup
    2. After major schema changes
    3. When starting fresh with a clean database
    4. Before importing new data that requires a specific schema
    
    WARNING: This will delete all existing data in the retailers and events tables!
    """
    db_path = get_default_db_path()
    logger.warning("⚠️  WARNING: This will delete all data in retailers and events tables!")
    logger.warning("⚠️  Database path: %s", db_path)
    
    # Ask for confirmation
    response = input("Are you sure you want to reset the schema? This will delete all data! (yes/no): ")
    if response.lower() != 'yes':
        logger.info("Schema reset cancelled by user.")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Drop existing tables
        logger.info("Dropping existing tables...")
        cursor.execute("DROP TABLE IF EXISTS retailers")
        cursor.execute("DROP TABLE IF EXISTS events")

        # Create retailers table
        logger.info("Creating retailers table...")
        cursor.execute("""
            CREATE TABLE retailers (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                retailer         VARCHAR(255) NOT NULL,
                retailer_type    VARCHAR(50)  NOT NULL,
                full_address     VARCHAR(255) NOT NULL,
                latitude         FLOAT,
                longitude        FLOAT,
                place_id         VARCHAR(100),
                first_seen       DATETIME,
                phone_number     VARCHAR(50),
                rating           FLOAT,
                website          VARCHAR(255),
                opening_hours    TEXT,
                last_api_update  DATETIME,
                machine_count    INTEGER DEFAULT 0,
                previous_count   INTEGER DEFAULT 0,
                status           TEXT
            )
        """)

        # Create events table
        logger.info("Creating events table...")
        cursor.execute("""
            CREATE TABLE events (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                event_title      TEXT    NOT NULL,
                first_seen       TEXT,
                full_address     TEXT    NOT NULL,
                start_date       DATETIME,
                start_time       TIME,
                latitude         REAL,
                longitude        REAL,
                end_date         DATETIME,
                end_time         TIME,
                registration_url TEXT,
                price            REAL,
                email            TEXT,
                phone            TEXT
            )
        """)

        conn.commit()
        logger.info("✅ Schema reset complete. Tables are ready for data import.")
    except Exception as e:
        conn.rollback()
        logger.error("❌ Error resetting schema: %s", str(e))
        raise
    finally:
        conn.close()

def main():
    parser = argparse.ArgumentParser(description="Database management utilities")
    parser.add_argument("command", choices=["backup", "schema", "reset", "verify"],
                      help="Command to execute")
    parser.add_argument("--db", dest="db", help="Path to DB for verify (optional)")
    args = parser.parse_args()

    if args.command == "backup":
        backup_database()
    elif args.command == "schema":
        list_schema()
    elif args.command == "verify":
        ok = integrity_check(args.db)
        sys.exit(0 if ok else 2)
    else:  # reset
        reset_schema()

if __name__ == "__main__":
    main() 