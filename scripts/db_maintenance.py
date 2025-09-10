#!/usr/bin/env python3
"""
Database Maintenance Script

Performs SQLite database maintenance operations:
- VACUUM (defragmentation and space recovery)
- ANALYZE (statistics update for query optimization)
- Integrity check

Safe to run while system is online - SQLite handles concurrent access gracefully.

Usage:
    python3 scripts/db_maintenance.py [--backup] [--verbose]

Options:
    --backup    Create a backup before maintenance (recommended for production)
    --verbose   Show detailed output
"""

import os
import sys
import sqlite3
import argparse
import logging
from datetime import datetime
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Import the existing backup function
from utils.db_manage import backup_database, integrity_check

# ─── Configuration ───────────────────────────────────────────────────────────────
DB_PATH = "/home/tamermap/app/instance/tamermap_data.db"
LOG_FILE = "/home/tamermap/app/logs/db_maintenance.log"

# ─── Logging Setup ─────────────────────────────────────────────────────────────
def setup_logging(verbose=False):
    """Setup logging configuration"""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.FileHandler(LOG_FILE),
            logging.StreamHandler(sys.stdout)
        ]
    )
    return logging.getLogger(__name__)

def get_database_size(db_path):
    """Get database file size in MB"""
    try:
        size_bytes = os.path.getsize(db_path)
        return round(size_bytes / (1024 * 1024), 2)
    except Exception:
        return 0

def run_maintenance(db_path, logger, create_backup=False):
    """Run database maintenance operations"""
    
    # Check if database exists
    if not os.path.exists(db_path):
        logger.error(f"Database not found: {db_path}")
        return False
    
    # Get initial size
    initial_size = get_database_size(db_path)
    logger.info(f"📊 Initial database size: {initial_size} MB")
    
    # Create backup if requested
    if create_backup:
        logger.info("🔒 Creating backup before maintenance...")
        backup_path = backup_database()
        if not backup_path:
            logger.error("❌ Backup failed - aborting maintenance")
            return False
        logger.info(f"✅ Backup created: {backup_path}")
    
    # Run integrity check first
    logger.info("🔍 Running integrity check...")
    if not integrity_check(db_path):
        logger.error("❌ Integrity check failed - aborting maintenance")
        return False
    logger.info("✅ Integrity check passed")
    
    # Connect to database
    conn = sqlite3.connect(db_path)
    try:
        # Run VACUUM (defragmentation and space recovery)
        logger.info("🧹 Running VACUUM (defragmentation)...")
        start_time = datetime.now()
        conn.execute("VACUUM")
        vacuum_time = (datetime.now() - start_time).total_seconds()
        logger.info(f"✅ VACUUM completed in {vacuum_time:.2f} seconds")
        
        # Run ANALYZE (update query statistics)
        logger.info("📈 Running ANALYZE (query optimization)...")
        start_time = datetime.now()
        conn.execute("ANALYZE")
        analyze_time = (datetime.now() - start_time).total_seconds()
        logger.info(f"✅ ANALYZE completed in {analyze_time:.2f} seconds")
        
        # Commit any pending transactions
        conn.commit()
        
    except Exception as e:
        logger.error(f"❌ Error during maintenance: {e}")
        return False
    finally:
        conn.close()
    
    # Get final size
    final_size = get_database_size(db_path)
    size_change = final_size - initial_size
    logger.info(f"📊 Final database size: {final_size} MB")
    logger.info(f"📊 Size change: {size_change:+.2f} MB")
    
    # Final integrity check
    logger.info("🔍 Running final integrity check...")
    if not integrity_check(db_path):
        logger.error("❌ Final integrity check failed")
        return False
    
    logger.info("✅ Database maintenance completed successfully")
    return True

def main():
    parser = argparse.ArgumentParser(description="Database maintenance script")
    parser.add_argument("--backup", action="store_true", 
                       help="Create backup before maintenance (recommended for production)")
    parser.add_argument("--verbose", "-v", action="store_true",
                       help="Show detailed output")
    parser.add_argument("--db", default=DB_PATH,
                       help=f"Database path (default: {DB_PATH})")
    
    args = parser.parse_args()
    
    # Setup logging
    logger = setup_logging(args.verbose)
    
    logger.info("🚀 Starting database maintenance...")
    logger.info(f"📁 Database: {args.db}")
    logger.info(f"🔒 Backup: {'Yes' if args.backup else 'No'}")
    
    # Run maintenance
    success = run_maintenance(args.db, logger, args.backup)
    
    if success:
        logger.info("🎉 Database maintenance completed successfully")
        sys.exit(0)
    else:
        logger.error("💥 Database maintenance failed")
        sys.exit(1)

if __name__ == "__main__":
    main()
