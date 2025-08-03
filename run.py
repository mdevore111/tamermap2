"""
Entry point for the Flask application.

This script creates and configures the Flask application using the application
factory pattern, initializes the database (including default roles), and starts
the development server.
"""
from app import create_app, models  # noqa
from app.models import db  # explicitly import db
from app.config import BaseConfig
from app.db_helpers import create_default_roles  # Database helper for initializing roles

# Create a Flask application instance using the BaseConfig settings.
app = create_app(BaseConfig)

if __name__ == "__main__":
    # Create an application context so that we can perform database operations.
    with app.app_context():
        try:
            # Initialize default roles (e.g., Basic, Pro, Admin) if they don't already exist.
            create_default_roles(app)
            # Create all database tables based on the models defined in the application.
            db.create_all()
            # Log the registered tables for debugging purposes.
        except Exception as e:
            app.logger.error(f"Error creating default roles: {str(e)}")
            db.session.rollback()
    # Start the Flask development server, using the debug setting from configuration.
    app.run(debug=app.config.get("DEBUG", False))
