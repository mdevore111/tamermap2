import os
import sys
import argparse
from dotenv import load_dotenv
from flask import current_app
from flask_mail import Message

# Compute the project root directory (assumes this script is at the project root)
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__)))
# Add the project root to sys.path so that the 'app' module can be found
sys.path.insert(0, BASE_DIR)

# Load environment variables from the .env file in the project root
load_dotenv(os.path.join(BASE_DIR, '.env'))

from app import create_app
from app.custom_email import custom_send_mail


def main():
    parser = argparse.ArgumentParser(description="Send a test email via Mailgun")
    parser.add_argument(
        "recipients",
        help="Comma-separated list of recipient email addresses (e.g., user1@example.com,user2@example.com)"
    )
    args = parser.parse_args()

    # Split the recipients by comma and strip any extra whitespace
    recipient_list = [email.strip() for email in args.recipients.split(",") if email.strip()]

    # Create the Flask application instance
    app = create_app()

    # Enter the app context to access current_app and configuration
    with app.app_context():


        # Construct the message
        msg = Message(
            subject="Mailgun Test",
            recipients=recipient_list,
            html="<strong>This is a test email from Mailgun.</strong>",
            sender=current_app.config["MAILGUN_SENDER"]
        )

        # Send the email using your custom function
        response = custom_send_mail(msg)
        print(f"Email sent successfully to {', '.join(recipient_list)}")


if __name__ == "__main__":
    main()
