#!/usr/bin/env python3
"""
Cleanup Non-North American Traffic Script

This script removes visitor log entries from countries outside North America.
It targets traffic that should have been blocked by Cloudflare geo-fencing rules
but may have gotten through due to:
- Bot traffic spoofing user agents
- Direct server access bypassing Cloudflare
- Rule configuration issues

North American countries included:
- US (United States)
- CA (Canada) 
- MX (Mexico)

SAFETY FEATURES:
- Shows what will be deleted before proceeding
- Creates backup of affected data
- Only affects non-North American traffic
- Preserves all legitimate North American traffic
- Dry-run mode to preview changes
"""

import sqlite3
import os
import shutil
from datetime import datetime
import argparse

# Database configuration
DB_PATH = "instance/tamermap_data.db"
BACKUP_PATH = f"instance/tamermap_data_backup_non_na_cleanup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"

# North American countries to preserve (both codes and full names)
NORTH_AMERICAN_COUNTRIES = [
    'US', 'CA', 'MX',  # Country codes
    'United States', 'Canada', 'Mexico',  # Full names
    'United States of America', 'USA'  # Alternative names
]

def backup_database():
    """Create a backup before making changes"""
    print(f"🔒 Creating backup: {BACKUP_PATH}")
    shutil.copy2(DB_PATH, BACKUP_PATH)
    print(f"✅ Backup created successfully")
    return True

def get_non_na_traffic_stats():
    """Get statistics about non-North American traffic in the database"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Get total non-North American traffic count
    na_countries_placeholders = ', '.join(['?' for _ in NORTH_AMERICAN_COUNTRIES])
    cursor.execute(f"""
        SELECT COUNT(*) as total_non_na_visits
        FROM visitor_log 
        WHERE country NOT IN ({na_countries_placeholders}) OR country IS NULL
    """, NORTH_AMERICAN_COUNTRIES)
    total_non_na = cursor.fetchone()[0]
    
    # Get non-North American traffic by country
    cursor.execute(f"""
        SELECT country, COUNT(*) as visits
        FROM visitor_log 
        WHERE country NOT IN ({na_countries_placeholders}) OR country IS NULL
        GROUP BY country 
        ORDER BY visits DESC 
        LIMIT 20
    """, NORTH_AMERICAN_COUNTRIES)
    non_na_by_country = cursor.fetchall()
    
    # Get non-North American traffic by path
    cursor.execute(f"""
        SELECT path, COUNT(*) as visits
        FROM visitor_log 
        WHERE country NOT IN ({na_countries_placeholders}) OR country IS NULL
        GROUP BY path 
        ORDER BY visits DESC 
        LIMIT 20
    """, NORTH_AMERICAN_COUNTRIES)
    non_na_by_path = cursor.fetchall()
    
    # Get non-North American traffic by date
    cursor.execute(f"""
        SELECT DATE(timestamp) as date, COUNT(*) as visits
        FROM visitor_log 
        WHERE country NOT IN ({na_countries_placeholders}) OR country IS NULL
        GROUP BY DATE(timestamp) 
        ORDER BY date DESC 
        LIMIT 10
    """, NORTH_AMERICAN_COUNTRIES)
    non_na_by_date = cursor.fetchall()
    
    # Get total traffic count for comparison
    cursor.execute("SELECT COUNT(*) FROM visitor_log")
    total_traffic = cursor.fetchone()[0]
    
    # Get North American traffic count
    cursor.execute(f"""
        SELECT COUNT(*) FROM visitor_log 
        WHERE country IN ('{na_countries_str}')
    """)
    total_na = cursor.fetchone()[0]
    
    conn.close()
    
    return {
        'total_non_na': total_non_na,
        'total_na': total_na,
        'total_traffic': total_traffic,
        'non_na_by_country': non_na_by_country,
        'non_na_by_path': non_na_by_path,
        'non_na_by_date': non_na_by_date
    }

def cleanup_non_na_traffic():
    """Remove all non-North American traffic from the database"""
    print("🗑️  Cleaning up non-North American traffic...")
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Count what will be deleted
    na_countries_placeholders = ', '.join(['?' for _ in NORTH_AMERICAN_COUNTRIES])
    cursor.execute(f"""
        SELECT COUNT(*) FROM visitor_log 
        WHERE country NOT IN ({na_countries_placeholders}) OR country IS NULL
    """, NORTH_AMERICAN_COUNTRIES)
    to_delete = cursor.fetchone()[0]
    
    if to_delete == 0:
        print("✅ No non-North American traffic found to clean up")
        conn.close()
        return 0
    
    print(f"📊 Found {to_delete} non-North American traffic entries to remove")
    
    # Delete non-North American traffic
    cursor.execute(f"""
        DELETE FROM visitor_log 
        WHERE country NOT IN ({na_countries_placeholders}) OR country IS NULL
    """, NORTH_AMERICAN_COUNTRIES)
    deleted_count = cursor.rowcount
    
    conn.commit()
    conn.close()
    
    print(f"✅ Removed {deleted_count} non-North American traffic entries")
    return deleted_count

def verify_cleanup():
    """Verify that non-North American traffic was cleaned up"""
    print("🔍 Verifying cleanup...")
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Check if any non-North American traffic remains
    na_countries_placeholders = ', '.join(['?' for _ in NORTH_AMERICAN_COUNTRIES])
    cursor.execute(f"""
        SELECT COUNT(*) FROM visitor_log 
        WHERE country NOT IN ({na_countries_placeholders}) OR country IS NULL
    """, NORTH_AMERICAN_COUNTRIES)
    remaining = cursor.fetchone()[0]
    
    # Get new total count
    cursor.execute("SELECT COUNT(*) FROM visitor_log")
    new_total = cursor.fetchone()[0]
    
    # Get remaining North American traffic count
    cursor.execute(f"""
        SELECT COUNT(*) FROM visitor_log 
        WHERE country IN ('{na_countries_str}')
    """)
    remaining_na = cursor.fetchone()[0]
    
    conn.close()
    
    if remaining == 0:
        print(f"✅ Cleanup successful! New total: {new_total} entries")
        print(f"   North American traffic preserved: {remaining_na} entries")
        return True
    else:
        print(f"⚠️  Warning: {remaining} non-North American entries still remain")
        return False

def main():
    """Main cleanup process"""
    parser = argparse.ArgumentParser(description='Clean up non-North American traffic')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be deleted without actually deleting')
    parser.add_argument('--force', action='store_true', help='Skip confirmation prompt')
    args = parser.parse_args()
    
    print("🌍 Non-North American Traffic Cleanup Script")
    print("=" * 60)
    print(f"North American countries preserved: {', '.join(NORTH_AMERICAN_COUNTRIES)}")
    
    # Step 1: Get current statistics
    print("\n📊 Current traffic statistics:")
    stats = get_non_na_traffic_stats()
    
    print(f"   Total traffic entries: {stats['total_traffic']:,}")
    print(f"   North American traffic: {stats['total_na']:,}")
    print(f"   Non-North American traffic: {stats['total_non_na']:,}")
    print(f"   Non-North American percentage: {(stats['total_non_na'] / stats['total_traffic'] * 100):.1f}%")
    
    if stats['total_non_na'] == 0:
        print("\n✅ No non-North American traffic found - nothing to clean up!")
        return
    
    # Step 2: Show what will be deleted
    print(f"\n🗑️  Non-North American traffic by country (top 20):")
    for country, visits in stats['non_na_by_country']:
        country_display = country if country else "Unknown/Null"
        print(f"   {country_display}: {visits:,} visits")
    
    print(f"\n📄 Non-North American traffic by path (top 20):")
    for path, visits in stats['non_na_by_path']:
        print(f"   {path}: {visits:,} visits")
    
    print(f"\n📅 Non-North American traffic by date (last 10 days):")
    for date, visits in stats['non_na_by_date']:
        print(f"   {date}: {visits:,} visits")
    
    # Step 3: Dry run or proceed
    if args.dry_run:
        print(f"\n🔍 DRY RUN MODE - No changes will be made")
        print(f"Would remove {stats['total_non_na']:,} non-North American traffic entries")
        print(f"Would preserve {stats['total_na']:,} North American traffic entries")
        return
    
    # Step 4: Confirmation
    if not args.force:
        print(f"\n⚠️  WARNING: This will permanently delete {stats['total_non_na']:,} non-North American traffic entries")
        print(f"   This includes traffic from countries outside: {', '.join(NORTH_AMERICAN_COUNTRIES)}")
        print(f"   North American traffic will be preserved: {stats['total_na']:,} entries")
        response = input("Are you sure you want to proceed? (yes/no): ")
        if response.lower() not in ['yes', 'y']:
            print("❌ Cleanup cancelled")
            return
    
    # Step 5: Create backup
    if not backup_database():
        print("❌ Backup failed - cannot proceed")
        return
    
    # Step 6: Clean up
    deleted_count = cleanup_non_na_traffic()
    
    # Step 7: Verify
    if verify_cleanup():
        print(f"\n🎉 Cleanup completed successfully!")
        print(f"   Removed: {deleted_count:,} non-North American entries")
        print(f"   Preserved: {stats['total_na']:,} North American entries")
        print(f"   Backup created: {BACKUP_PATH}")
    else:
        print(f"\n⚠️  Cleanup may not have completed fully")
        print(f"   Backup created: {BACKUP_PATH}")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
        print("Please check the backup and restore if needed")
