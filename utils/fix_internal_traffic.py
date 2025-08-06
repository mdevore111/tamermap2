#!/usr/bin/env python3
"""
Script to fix existing internal traffic data in the database.
Updates is_internal_referrer flag for existing records based on IP addresses.
"""

import re
from app import create_app
from app.models import VisitorLog
from app.extensions import db

def is_internal_ip(ip):
    """Check if IP is internal using the same logic as the app."""
    if not ip:
        return False
    
    # Server IPs
    if ip in ["137.184.244.37", "144.126.210.185", "50.106.23.189", "10.48.0.2", "24.199.116.220"]:
        return True
    
    # DigitalOcean IPs
    if re.match(r"^(144\.126\.\d+\.\d+|143\.198\.\d+\.\d+|134\.209\.\d+\.\d+)$", ip):
        return True
    
    # Private IP ranges (RFC 1918) - all non-routable addresses
    if (ip.startswith("10.") or  # 10.0.0.0/8
        ip.startswith("192.168.") or  # 192.168.0.0/16
        ip.startswith("127.") or  # 127.0.0.0/8 (localhost)
        re.match(r"^172\.(1[6-9]|2[0-9]|3[0-1])\.", ip) or  # 172.16.0.0/12
        ip == "localhost"):
        return True
    
    return False

def fix_internal_traffic():
    """Update existing records to properly mark internal traffic."""
    app = create_app()
    
    with app.app_context():
        print("Starting internal traffic fix...")
        
        # Get all records
        total_records = VisitorLog.query.count()
        print(f"Total records: {total_records}")
        
        # Get current counts
        current_internal = VisitorLog.query.filter_by(is_internal_referrer=True).count()
        current_external = VisitorLog.query.filter_by(is_internal_referrer=False).count()
        print(f"Current internal: {current_internal}")
        print(f"Current external: {current_external}")
        
        # Find records that should be marked as internal
        records_to_update = []
        batch_size = 1000
        
        # Process in batches to avoid memory issues
        offset = 0
        while True:
            batch = VisitorLog.query.offset(offset).limit(batch_size).all()
            if not batch:
                break
                
            for record in batch:
                if record.ip_address and is_internal_ip(record.ip_address):
                    if not record.is_internal_referrer:
                        records_to_update.append(record.id)
            
            offset += batch_size
            print(f"Processed {offset} records...")
        
        print(f"Found {len(records_to_update)} records that need to be marked as internal")
        
        if records_to_update:
            # Update in batches
            for i in range(0, len(records_to_update), batch_size):
                batch_ids = records_to_update[i:i + batch_size]
                VisitorLog.query.filter(VisitorLog.id.in_(batch_ids)).update(
                    {'is_internal_referrer': True}, 
                    synchronize_session=False
                )
                print(f"Updated batch {i//batch_size + 1}/{(len(records_to_update) + batch_size - 1)//batch_size}")
            
            db.session.commit()
            print("Database updated successfully!")
        else:
            print("No records need updating.")
        
        # Show final counts
        final_internal = VisitorLog.query.filter_by(is_internal_referrer=True).count()
        final_external = VisitorLog.query.filter_by(is_internal_referrer=False).count()
        print(f"Final internal: {final_internal}")
        print(f"Final external: {final_external}")
        print(f"Internal records added: {final_internal - current_internal}")
        
        # Show specific counts for 10.48.0.2
        monitor_visits = VisitorLog.query.filter_by(ip_address='10.48.0.2').count()
        monitor_internal = VisitorLog.query.filter_by(ip_address='10.48.0.2', is_internal_referrer=True).count()
        monitor_external = VisitorLog.query.filter_by(ip_address='10.48.0.2', is_internal_referrer=False).count()
        print(f"10.48.0.2 total visits: {monitor_visits}")
        print(f"10.48.0.2 marked as internal: {monitor_internal}")
        print(f"10.48.0.2 marked as external: {monitor_external}")

if __name__ == "__main__":
    fix_internal_traffic() 