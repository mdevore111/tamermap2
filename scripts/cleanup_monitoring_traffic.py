#!/usr/bin/env python3
"""
Cleanup Historical Monitoring Traffic Script

This script removes historical traffic data from monitoring IPs (10.x.x.x network and staging server)
and internal referrers (tamermap.com, bareista.com, server IPs) that was collected before 
the traffic filtering was implemented.

SAFETY FEATURES:
- Shows what will be deleted before proceeding
- Creates backup of affected data
- Only affects monitoring IPs (10.x.x.x)
- Preserves all legitimate user traffic
"""

import sqlite3
import os
import shutil
from datetime import datetime
import argparse

# Database configuration
DB_PATH = "instance/tamermap_data.db"
BACKUP_PATH = f"instance/tamermap_data_backup_monitoring_cleanup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"

# Monitoring IP patterns to clean up
MONITORING_IPS = [
    '10.%',  # All 10.x.x.x addresses
    '146.190.115.141',  # Staging server monitoring traffic
    '64.23.146.54',  # Additional suspicious IP with high payment page visits
    '50.106.23.189',  # High payment page visits (18)
    '50.47.93.228',   # High payment page visits (15)
    '161.35.232.67',  # High payment page visits (8)
    '194.113.66.142',  # High payment page visits (6)
]

# Internal referrer patterns to clean up (these should not be logged)
INTERNAL_REFERRERS = [
    'tamermap.com',
    'www.tamermap.com', 
    'bareista.com',
    'www.bareista.com',
    '137.184.244.37',
    '144.126.210.185'
]

def backup_database():
    """Create a backup before making changes"""
    print(f"🔒 Creating backup: {BACKUP_PATH}")
    shutil.copy2(DB_PATH, BACKUP_PATH)
    print(f"✅ Backup created successfully")
    return True

def get_monitoring_traffic_stats():
    """Get statistics about monitoring traffic in the database"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Get total monitoring traffic count (IPs + internal referrers)
    internal_refs_condition = " OR ".join([f"referrer LIKE '%{ref}%'" for ref in INTERNAL_REFERRERS])
    cursor.execute(f"""
        SELECT COUNT(*) as total_monitoring_visits
        FROM visitor_log 
        WHERE ip_address LIKE '10.%' OR ip_address = '146.190.115.141' OR ip_address = '64.23.146.54' 
        OR ip_address = '50.106.23.189' OR ip_address = '50.47.93.228' OR ip_address = '161.35.232.67'
        OR ip_address = '194.113.66.142'
        OR {internal_refs_condition}
    """)
    total_monitoring = cursor.fetchone()[0]
    
    # Get monitoring traffic by path (IPs + internal referrers)
    internal_refs_condition = " OR ".join([f"referrer LIKE '%{ref}%'" for ref in INTERNAL_REFERRERS])
    cursor.execute(f"""
        SELECT path, COUNT(*) as visits
        FROM visitor_log 
        WHERE ip_address LIKE '10.%' OR ip_address = '146.190.115.141' OR ip_address = '64.23.146.54'
        OR ip_address = '50.106.23.189' OR ip_address = '50.47.93.228' OR ip_address = '161.35.232.67'
        OR ip_address = '194.113.66.142'
        OR {internal_refs_condition}
        GROUP BY path 
        ORDER BY visits DESC 
        LIMIT 20
    """)
    monitoring_by_path = cursor.fetchall()
    
    # Get monitoring traffic by date (IPs + internal referrers)
    internal_refs_condition = " OR ".join([f"referrer LIKE '%{ref}%'" for ref in INTERNAL_REFERRERS])
    cursor.execute(f"""
        SELECT DATE(timestamp) as date, COUNT(*) as visits
        FROM visitor_log 
        WHERE ip_address LIKE '10.%' OR ip_address = '146.190.115.141' OR ip_address = '64.23.146.54'
        OR ip_address = '50.106.23.189' OR ip_address = '50.47.93.228' OR ip_address = '161.35.232.67'
        OR ip_address = '194.113.66.142'
        OR {internal_refs_condition}
        GROUP BY DATE(timestamp)
        ORDER BY date DESC
        LIMIT 10
    """)
    monitoring_by_date = cursor.fetchall()
    
    # Get total traffic count for comparison
    cursor.execute("SELECT COUNT(*) FROM visitor_log")
    total_traffic = cursor.fetchone()[0]
    
    conn.close()
    
    return {
        'total_monitoring': total_monitoring,
        'total_traffic': total_traffic,
        'monitoring_by_path': monitoring_by_path,
        'monitoring_by_date': monitoring_by_date
    }

def cleanup_monitoring_traffic():
    """Remove all monitoring traffic from the database"""
    print("🗑️  Cleaning up monitoring traffic...")
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Count what will be deleted (IPs + internal referrers)
    internal_refs_condition = " OR ".join([f"referrer LIKE '%{ref}%'" for ref in INTERNAL_REFERRERS])
    cursor.execute(f"SELECT COUNT(*) FROM visitor_log WHERE ip_address LIKE '10.%' OR ip_address = '146.190.115.141' OR ip_address = '64.23.146.54' OR ip_address = '50.106.23.189' OR ip_address = '50.47.93.228' OR ip_address = '161.35.232.67' OR ip_address = '194.113.66.142' OR {internal_refs_condition}")
    to_delete = cursor.fetchone()[0]
    
    if to_delete == 0:
        print("✅ No monitoring traffic found to clean up")
        conn.close()
        return 0
    
    print(f"📊 Found {to_delete} monitoring traffic entries to remove")
    
    # Delete monitoring traffic (IPs + internal referrers)
    internal_refs_condition = " OR ".join([f"referrer LIKE '%{ref}%'" for ref in INTERNAL_REFERRERS])
    cursor.execute(f"DELETE FROM visitor_log WHERE ip_address LIKE '10.%' OR ip_address = '146.190.115.141' OR ip_address = '64.23.146.54' OR ip_address = '50.106.23.189' OR ip_address = '50.47.93.228' OR ip_address = '161.35.232.67' OR ip_address = '194.113.66.142' OR {internal_refs_condition}")
    deleted_count = cursor.rowcount
    
    conn.commit()
    conn.close()
    
    print(f"✅ Removed {deleted_count} monitoring traffic entries")
    return deleted_count

def verify_cleanup():
    """Verify that monitoring traffic was cleaned up"""
    print("🔍 Verifying cleanup...")
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Check if any monitoring IPs remain (IPs + internal referrers)
    internal_refs_condition = " OR ".join([f"referrer LIKE '%{ref}%'" for ref in INTERNAL_REFERRERS])
    cursor.execute(f"SELECT COUNT(*) FROM visitor_log WHERE ip_address LIKE '10.%' OR ip_address = '146.190.115.141' OR ip_address = '64.23.146.54' OR ip_address = '50.106.23.189' OR ip_address = '50.47.93.228' OR ip_address = '161.35.232.67' OR ip_address = '194.113.66.142' OR {internal_refs_condition}")
    remaining = cursor.fetchone()[0]
    
    # Get new total count
    cursor.execute("SELECT COUNT(*) FROM visitor_log")
    new_total = cursor.fetchone()[0]
    
    conn.close()
    
    if remaining == 0:
        print(f"✅ Cleanup successful! New total: {new_total} entries")
        return True
    else:
        print(f"⚠️  Warning: {remaining} monitoring entries still remain")
        return False

def main():
    """Main cleanup process"""
    parser = argparse.ArgumentParser(description='Clean up historical monitoring traffic')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be deleted without actually deleting')
    parser.add_argument('--force', action='store_true', help='Skip confirmation prompt')
    args = parser.parse_args()
    
    print("🧹 Historical Monitoring Traffic Cleanup Script")
    print("=" * 60)
    
    # Step 1: Get current statistics
    print("\n📊 Current traffic statistics:")
    stats = get_monitoring_traffic_stats()
    
    print(f"   Total traffic entries: {stats['total_traffic']:,}")
    print(f"   Monitoring traffic entries: {stats['total_monitoring']:,}")
    print(f"   Monitoring traffic percentage: {(stats['total_monitoring'] / stats['total_traffic'] * 100):.1f}%")
    
    if stats['total_monitoring'] == 0:
        print("\n✅ No monitoring traffic found - nothing to clean up!")
        return
    
    # Step 2: Show what will be deleted
    print(f"\n🗑️  Monitoring traffic by path (top 20):")
    for path, visits in stats['monitoring_by_path']:
        print(f"   {path}: {visits:,} visits")
    
    print(f"\n📅 Monitoring traffic by date (last 10 days):")
    for date, visits in stats['monitoring_by_date']:
        print(f"   {date}: {visits:,} visits")
    
    # Step 3: Dry run or proceed
    if args.dry_run:
        print(f"\n🔍 DRY RUN MODE - No changes will be made")
        print(f"Would remove {stats['total_monitoring']:,} monitoring traffic entries")
        return
    
    # Step 4: Confirmation
    if not args.force:
        print(f"\n⚠️  WARNING: This will permanently delete {stats['total_monitoring']:,} monitoring traffic entries")
        response = input("Are you sure you want to proceed? (yes/no): ")
        if response.lower() not in ['yes', 'y']:
            print("❌ Cleanup cancelled")
            return
    
    # Step 5: Create backup
    if not backup_database():
        print("❌ Backup failed - cannot proceed")
        return
    
    # Step 6: Clean up
    deleted_count = cleanup_monitoring_traffic()
    
    # Step 7: Verify
    if verify_cleanup():
        print(f"\n🎉 Cleanup completed successfully!")
        print(f"   Removed: {deleted_count:,} monitoring entries")
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
