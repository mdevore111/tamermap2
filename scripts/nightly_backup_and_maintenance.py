#!/usr/bin/env python3
"""
Nightly Backup and Database Maintenance Script

Combines database backup and maintenance operations for nightly execution.
This script:
1. Creates a timestamped backup using the existing db_manage.py system
2. Runs database maintenance (VACUUM + ANALYZE)
3. Cleans up old backups (keeps last 7 days)
4. Logs all operations

Safe to run while system is online.

Usage:
    python3 scripts/nightly_backup_and_maintenance.py [--keep-days N] [--verbose]

Options:
    --keep-days N    Keep backups for N days (default: 7)
    --verbose        Show detailed output
"""

import os
import sys
import glob
import argparse
import logging
from datetime import datetime, timedelta
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Import existing functions
from utils.db_manage import backup_database, integrity_check
from scripts.db_maintenance import run_maintenance

# ─── Configuration ───────────────────────────────────────────────────────────────
DB_PATH = "/home/tamermap/app/instance/tamermap_data.db"
INSTANCE_DIR = "/home/tamermap/app/instance"
LOG_FILE = "/home/tamermap/app/logs/nightly_maintenance.log"
DEFAULT_KEEP_DAYS = 7

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

def cleanup_old_backups(instance_dir, keep_days, logger):
    """Remove backup files older than keep_days"""
    logger.info(f"🧹 Cleaning up backups older than {keep_days} days...")
    
    # Find all backup files
    backup_pattern = os.path.join(instance_dir, "tamermap_data_backup_*.db")
    backup_files = glob.glob(backup_pattern)
    
    if not backup_files:
        logger.info("📁 No backup files found")
        return
    
    # Calculate cutoff date
    cutoff_date = datetime.now() - timedelta(days=keep_days)
    removed_count = 0
    total_size_removed = 0
    
    for backup_file in backup_files:
        try:
            # Extract timestamp from filename
            filename = os.path.basename(backup_file)
            # Format: tamermap_data_backup_YYYYMMDD_HHMMSS.db
            timestamp_str = filename.replace("tamermap_data_backup_", "").replace(".db", "")
            file_date = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")
            
            if file_date < cutoff_date:
                file_size = os.path.getsize(backup_file)
                os.remove(backup_file)
                removed_count += 1
                total_size_removed += file_size
                logger.debug(f"🗑️  Removed: {filename} ({file_size / (1024*1024):.2f} MB)")
                
        except Exception as e:
            logger.warning(f"⚠️  Could not process {backup_file}: {e}")
    
    if removed_count > 0:
        logger.info(f"✅ Removed {removed_count} old backup files ({total_size_removed / (1024*1024):.2f} MB freed)")
    else:
        logger.info("📁 No old backup files to remove")

def get_backup_stats(instance_dir, logger):
    """Get statistics about backup files"""
    backup_pattern = os.path.join(instance_dir, "tamermap_data_backup_*.db")
    backup_files = glob.glob(backup_pattern)
    
    if not backup_files:
        return
    
    total_size = sum(os.path.getsize(f) for f in backup_files)
    logger.info(f"📊 Backup statistics: {len(backup_files)} files, {total_size / (1024*1024):.2f} MB total")
    
    # Show newest and oldest
    backup_files.sort(key=os.path.getmtime)
    if backup_files:
        newest = os.path.basename(backup_files[-1])
        oldest = os.path.basename(backup_files[0])
        logger.info(f"📅 Newest: {newest}")
        logger.info(f"📅 Oldest: {oldest}")

def main():
    parser = argparse.ArgumentParser(description="Nightly backup and maintenance script")
    parser.add_argument("--keep-days", type=int, default=DEFAULT_KEEP_DAYS,
                       help=f"Keep backups for N days (default: {DEFAULT_KEEP_DAYS})")
    parser.add_argument("--verbose", "-v", action="store_true",
                       help="Show detailed output")
    parser.add_argument("--db", default=DB_PATH,
                       help=f"Database path (default: {DB_PATH})")
    
    args = parser.parse_args()
    
    # Setup logging
    logger = setup_logging(args.verbose)
    
    logger.info("🌙 Starting nightly backup and maintenance...")
    logger.info(f"📁 Database: {args.db}")
    logger.info(f"📁 Instance dir: {INSTANCE_DIR}")
    logger.info(f"🗓️  Keep backups: {args.keep_days} days")
    
    # Step 1: Create backup
    logger.info("🔒 Step 1: Creating database backup...")
    backup_path = backup_database()
    if not backup_path:
        logger.error("❌ Backup failed - aborting nightly maintenance")
        sys.exit(1)
    logger.info(f"✅ Backup created: {os.path.basename(backup_path)}")
    
    # Step 2: Run maintenance
    logger.info("🧹 Step 2: Running database maintenance...")
    success = run_maintenance(args.db, logger, create_backup=False)  # Already backed up
    if not success:
        logger.error("❌ Maintenance failed")
        sys.exit(1)
    
    # Step 3: Cleanup old backups
    logger.info("🗑️  Step 3: Cleaning up old backups...")
    cleanup_old_backups(INSTANCE_DIR, args.keep_days, logger)
    
    # Step 4: Show statistics
    logger.info("📊 Step 4: Backup statistics...")
    get_backup_stats(INSTANCE_DIR, logger)
    
    logger.info("🎉 Nightly backup and maintenance completed successfully")

if __name__ == "__main__":
    main()
