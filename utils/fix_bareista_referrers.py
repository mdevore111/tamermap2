#!/usr/bin/env python3
"""
Script to fix existing bareista.com referrers that should be marked as internal.
Updates is_internal_referrer flag for existing records with bareista.com referrers.
"""

from app import create_app
from app.models import VisitorLog
from app.extensions import db
from sqlalchemy import or_
from sqlalchemy import func

def fix_bareista_referrers():
    """Update existing records with bareista.com referrers to be marked as internal."""
    app = create_app()
    
    with app.app_context():
        print("Starting bareista.com referrer fix...")
        
        # Find records with bareista.com referrers that are currently marked as external
        bareista_records = VisitorLog.query.filter(
            or_(
                VisitorLog.referrer.like('%bareista.com%'),
                VisitorLog.referrer.like('%www.bareista.com%')
            ),
            VisitorLog.is_internal_referrer == False
        ).all()
        
        print(f"Found {len(bareista_records)} records with bareista.com referrers marked as external")
        
        if bareista_records:
            # Get the IDs of records to update
            record_ids = [record.id for record in bareista_records]
            
            # Update them in batches
            batch_size = 1000
            for i in range(0, len(record_ids), batch_size):
                batch_ids = record_ids[i:i + batch_size]
                VisitorLog.query.filter(VisitorLog.id.in_(batch_ids)).update(
                    {'is_internal_referrer': True}, 
                    synchronize_session=False
                )
                print(f"Updated batch {i//batch_size + 1}/{(len(record_ids) + batch_size - 1)//batch_size}")
            
            db.session.commit()
            print("Database updated successfully!")
        else:
            print("No bareista.com referrers found that need updating.")
        
        # Show final counts
        total_bareista = VisitorLog.query.filter(
            or_(
                VisitorLog.referrer.like('%bareista.com%'),
                VisitorLog.referrer.like('%www.bareista.com%')
            )
        ).count()
        
        bareista_internal = VisitorLog.query.filter(
            or_(
                VisitorLog.referrer.like('%bareista.com%'),
                VisitorLog.referrer.like('%www.bareista.com%')
            ),
            VisitorLog.is_internal_referrer == True
        ).count()
        
        bareista_external = VisitorLog.query.filter(
            or_(
                VisitorLog.referrer.like('%bareista.com%'),
                VisitorLog.referrer.like('%www.bareista.com%')
            ),
            VisitorLog.is_internal_referrer == False
        ).count()
        
        print(f"Bareista.com referrers - Total: {total_bareista}, Internal: {bareista_internal}, External: {bareista_external}")
        
        # Show specific referrer breakdown
        print("\nBareista.com referrer breakdown:")
        referrer_counts = db.session.query(
            VisitorLog.referrer,
            func.count(VisitorLog.id).label('count')
        ).filter(
            or_(
                VisitorLog.referrer.like('%bareista.com%'),
                VisitorLog.referrer.like('%www.bareista.com%')
            )
        ).group_by(VisitorLog.referrer).all()
        
        for referrer, count in referrer_counts:
            print(f"  {referrer}: {count}")

if __name__ == "__main__":
    fix_bareista_referrers() 