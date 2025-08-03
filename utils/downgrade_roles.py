#!/usr/bin/env python
"""
role_downgrade.py

Downgrades expired Pro subscriptions to Basic.
Automatically manages subscription lifecycle.

This script is intended to be run periodically (e.g., via cron). It performs the following steps:
  1. Gets the current UTC datetime.
  2. Finds all non-admin users with a non-null pro_end_date that is older than a specified threshold (default: 3 hours ago).
  3. For each such user:
       - Removes all existing roles.
       - Assigns the "Basic" role.
       - Clears (removes) the 'pro_end_date'.

Admins are not modified by this script.

Usage:
    python downgrade_roles.py
"""

import logging
import os
import sys
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from sqlalchemy import and_

# Set up logging
LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "downgrade_roles.log")

logger = logging.getLogger("downgrade_roles")
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = RotatingFileHandler(LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=5)
    formatter = logging.Formatter("[%(asctime)s] %(levelname)s: %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)

# Ensure the app module path is available
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, project_root)

from app import create_app, db
from app.models import User

def downgrade_expired_users():
    """
    Downgrade non-admin users whose pro_end_date is expired or inconsistent.

    For each user:
      - If the user has Pro role AND (pro_end_date is None OR pro_end_date is in the past)
        and does NOT have the "Admin" role:
            - Remove Pro role (and any other non-Admin roles).
            - Assign the "Basic" role.
            - Clear (remove) the 'pro_end_date'.
    """
    app = create_app()
    
    with app.app_context():
        # Get user_datastore within app context
        try:
            from app import user_datastore
            from app.models import Role
        except ImportError:
            user_datastore = getattr(app, 'user_datastore', None)
            if user_datastore is None:
                logger.error("user_datastore is not defined. Aborting.")
                raise RuntimeError("user_datastore is not defined in app")

        now = datetime.now(timezone.utc)
        logger.info(f"Checking for users with Pro role and expired/missing pro_end_date before {now.isoformat()}")

        try:
            # Find users with Pro role whose pro_end_date is expired or missing
            pro_role = user_datastore.find_role("Pro")
            if not pro_role:
                logger.error("Pro role not found in database. Aborting.")
                return

            # Get all users with Pro role
            users_with_pro = db.session.query(User).join(User.roles).filter(Role.name == "Pro").all()
            
            expired_users = []
            for user in users_with_pro:
                # Check if pro_end_date is None or in the past
                if not user.pro_end_date:
                    expired_users.append(user)
                else:
                    # Convert naive datetime to UTC-aware for comparison
                    user_pro_end_utc = user.pro_end_date.replace(tzinfo=timezone.utc)
                    if user_pro_end_utc < now:
                        expired_users.append(user)
            
            logger.info(f"Found {len(expired_users)} users with Pro role and expired/missing pro_end_date")

            if not expired_users:
                logger.info("No expired users to downgrade.")
                return

            for user in expired_users:
                if any(role.name == "Admin" for role in user.roles):
                    logger.info(f"Skipping admin user: {user.email}")
                    continue

                pro_end_date_str = user.pro_end_date.isoformat() if user.pro_end_date else "None"
                logger.info(f"Downgrading user {user.email} with pro_end_date of {pro_end_date_str}")

                # Remove Pro role and other non-Admin roles, but preserve Admin if present
                roles_to_remove = [role for role in user.roles if role.name != "Admin"]
                if roles_to_remove:
                    for role in roles_to_remove:
                        user_datastore.remove_role_from_user(user, role)
                        logger.info(f"Removed {role.name} role from user: {user.email}")
                    db.session.commit()

                # Add Basic role if not already present
                basic_role = user_datastore.find_role("Basic")
                if not user.has_role("Basic"):
                    user_datastore.add_role_to_user(user, basic_role)
                    logger.info(f"Added Basic role to user: {user.email}")

                # Clear pro_end_date
                user.pro_end_date = None
                db.session.add(user)
                db.session.commit()
                logger.info(f"Downgraded: {user.email} => Basic, pro_end_date=None")

        except Exception as e:
            db.session.rollback()
            logger.error(f"Error during downgrade process: {str(e)}")
            raise

def main():
    try:
        downgrade_expired_users()
    except Exception as e:
        logger.exception("Unexpected error during downgrade.")
        print(f"ERROR: {str(e)}")
        print("See downgrade_roles.log for details.")
        sys.exit(1)

if __name__ == "__main__":
    main()
