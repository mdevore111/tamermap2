#!/usr/bin/env python3
"""
Backfill VisitorLog.is_pro for recent visits.

Usage:
  python utils/backfill_is_pro_visitor_log.py --days 60

Notes:
  - This uses User.pro_end_date relative to the visit timestamp when available.
  - If pro_end_date is missing, falls back to current role (has_role('Pro')) as heuristic.
  - Run within the Flask app context.
"""

import argparse
from datetime import datetime, timedelta

from app import create_app
from app.extensions import db
from app.models import VisitorLog, User


def backfill(days: int) -> int:
    app = create_app()
    updated = 0
    cutoff = datetime.utcnow() - timedelta(days=days)

    with app.app_context():
        # Fetch recent logs with null is_pro
        logs = (VisitorLog.query
                .filter(VisitorLog.timestamp >= cutoff)
                .filter((VisitorLog.is_pro.is_(None)) | (VisitorLog.is_pro == None))  # noqa: E711
                .order_by(VisitorLog.id.asc())
                .all())

        user_cache = {}
        for log in logs:
            if not log.user_id:
                log.is_pro = False
                updated += 1
                continue

            user = user_cache.get(log.user_id)
            if user is None:
                user = User.query.get(log.user_id)
                user_cache[log.user_id] = user

            if not user:
                log.is_pro = False
                updated += 1
                continue

            # Prefer pro_end_date snapshot logic
            if user.pro_end_date is not None and isinstance(user.pro_end_date, datetime):
                log.is_pro = user.pro_end_date > log.timestamp
            else:
                # Heuristic fallback to current role
                try:
                    log.is_pro = user.has_role('Pro')
                except Exception:
                    log.is_pro = False
            updated += 1

        if updated:
            db.session.commit()

    return updated


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--days', type=int, default=60, help='Days back to backfill')
    args = parser.parse_args()
    count = backfill(args.days)
    print(f"Backfilled {count} VisitorLog rows")


if __name__ == '__main__':
    main()


