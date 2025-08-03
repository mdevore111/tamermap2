#!/usr/bin/env python3
"""
user_manage.py

User management utility for TAMERMAP. Supports two commands:

  1. create — create a new user (interactive prompts if flags omitted)
  2. role   — change an existing user's role

Usage:
    python user_manage.py <command> [options]

Commands:
    create    Create a user; supply --email and --role, optional flags:
              --first-name, --last-name, --stripe-id, --pro-end-date
    role      Assign or change a user's role; requires --email and --role

Examples:
    # Fully non-interactive creation:
    python user_manage.py create \
        --email user@example.com \
        --role Pro \
        --first-name Alice \
        --last-name Smith \
        --stripe-id cus_ABC123 \
        --pro-end-date 2025-06-10

    # Interactive creation (prompts for missing fields):
    python user_manage.py create

    # Change role:
    python user_manage.py role \
        --email user@example.com \
        --role Basic
"""

import os
import sys
import argparse
from datetime import datetime, timezone
from dateutil.relativedelta import relativedelta
import logging
from logging.handlers import RotatingFileHandler

# --- Logging setup ---
LOG_DIR = os.path.join(os.path.dirname(__file__), "logs")
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "user_manage.log")
logger = logging.getLogger("user_manage")
logger.setLevel(logging.INFO)
if not logger.handlers:
    h = RotatingFileHandler(LOG_FILE, maxBytes=5*1024*1024, backupCount=5)
    h.setFormatter(logging.Formatter("[%(asctime)s] %(levelname)s: %(message)s"))
    logger.addHandler(h)

# --- Application imports ---
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, project_root)
from app import create_app, db
from app.models import User, Role
from flask_security import utils as security_utils

# --- Constants ---
VALID_ROLES = ["Basic", "Pro", "Admin"]


# --- Helper prompts for interactive mode ---
def prompt_input(prompt: str, required: bool = True) -> str:
    """Prompt until non-empty input if required, else return possibly empty."""
    while True:
        val = input(prompt).strip()
        if required and not val:
            print("This field is required.")
        else:
            return val

def prompt_date(prompt: str, default: datetime) -> datetime:
    """Prompt for YYYY-MM-DD date, default if blank."""
    while True:
        val = input(prompt).strip()
        if not val:
            return default
        try:
            return datetime.strptime(val, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            print("Invalid format, use YYYY-MM-DD.")


# --- Command implementations ---
def create_user_cli(args: argparse.Namespace) -> None:
    """
    Create a new user. Uses args.email and args.role; prompts for any missing fields.
    """
    print("=== Create a New User ===")
    email = args.email or prompt_input("Enter user's email: ")
    first_name = args.first_name if args.first_name is not None else prompt_input("First name (optional): ", required=False)
    last_name = args.last_name if args.last_name is not None else prompt_input("Last name (optional): ", required=False)
    stripe_id = args.stripe_id if args.stripe_id is not None else prompt_input("Stripe Customer ID (optional): ", required=False)
    role = args.role or prompt_input("Role (Basic, Pro, Admin): ").title()
    if role not in VALID_ROLES:
        print(f"ERROR: Invalid role. Choose from {', '.join(VALID_ROLES)}.")
        sys.exit(1)

    # Pro flag setup
    is_pro = role in ("Pro", "Admin")
    default_pro_end = datetime.now(timezone.utc) + relativedelta(months=1)
    if is_pro:
        pro_end_input = args.pro_end_date or prompt_date(f"Pro end date [YYYY-MM-DD] (default {default_pro_end.date()}): ", default_pro_end)
        pro_end_date = pro_end_input if isinstance(pro_end_input, datetime) else default_pro_end
    else:
        pro_end_date = None

    # Create in DB
    app = create_app()
    with app.app_context():
        ds = getattr(app, "user_datastore", None)
        if ds is None:
            logger.error("user_datastore not configured.")
            sys.exit("ERROR: user_datastore not found.")

        if User.query.filter_by(email=email).first():
            print(f"ERROR: User {email} exists.")
            sys.exit(1)

        pw = security_utils.hash_password("temporary")
        user = User(
            email=email,
            password=pw,
            first_name=first_name,
            last_name=last_name,
            active=True,
            confirmed_at=datetime.now(timezone.utc),
            pro_end_date=pro_end_date,
            cust_id=stripe_id or None
        )

        role_obj = Role.query.filter_by(name=role).first()
        if not role_obj:
            print(f"ERROR: Role {role} not found.")
            sys.exit(1)
        user.roles.append(role_obj)

        db.session.add(user)
        db.session.commit()
        logger.info("User created: %s with role %s", email, role)
        print(f"User {email} created with role {role}.")


def assign_role_cli(args: argparse.Namespace) -> None:
    """
    Assign or change a user's role non-interactively.
    """
    email = args.email
    role = args.role
    logger.info("Assigning role %s to %s", role, email)

    app = create_app()
    with app.app_context():
        ds = getattr(app, "user_datastore", None)
        if ds is None:
            sys.exit("ERROR: user_datastore not found.")

        user = ds.find_user(email=email)
        if not user:
            sys.exit(f"ERROR: User {email} not found.")

        role_obj = ds.find_role(role)
        if not role_obj:
            sys.exit(f"ERROR: Role {role} not found.")

        # remove existing
        for r in list(user.roles):
            ds.remove_role_from_user(user, r)
        db.session.commit()

        # add new
        ds.add_role_to_user(user, role_obj)
        # update flags
        now = datetime.now(timezone.utc)
        if role == "Pro":
            user.pro_end_date = (user.pro_end_date or now) + relativedelta(months=1)
        elif role == "Basic":
            user.pro_end_date = None
        elif role == "Admin":
            # Admin users typically have permanent pro access, set far future date
            user.pro_end_date = now + relativedelta(years=10)

        db.session.add(user)
        db.session.commit()
        logger.info("Role %s assigned to %s", role, email)
        print(f"User {email} is now {role}.")


# --- Main and argument parsing ---
def main():
    parser = argparse.ArgumentParser(
        description="Manage users: create or assign roles"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # create sub-command
    p1 = sub.add_parser("create", help="Create a new user")
    p1.add_argument("--email",       help="User email address")
    p1.add_argument("--role",        choices=VALID_ROLES, help="Role: Basic, Pro, Admin")
    p1.add_argument("--first-name",  dest="first_name", help="First name")
    p1.add_argument("--last-name",   dest="last_name",  help="Last name")
    p1.add_argument("--stripe-id",   dest="stripe_id",  help="Stripe customer ID")
    p1.add_argument("--pro-end-date", dest="pro_end_date", help="Pro end date YYYY-MM-DD")

    # role sub-command
    p2 = sub.add_parser("role", help="Change an existing user's role")
    p2.add_argument("--email", required=True, help="Target user's email")
    p2.add_argument("--role",  required=True, choices=VALID_ROLES, help="New role")

    args = parser.parse_args()

    if args.command == "create":
        create_user_cli(args)
    else:
        assign_role_cli(args)


if __name__ == "__main__":
    main()
