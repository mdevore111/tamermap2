"""
Database helper functions.

This module provides helper functions for database operations.
"""

from flask import current_app
from flask_security import SQLAlchemyUserDatastore
from .extensions import db
from .models import Role, User


def create_default_roles(app):
    """
    Create default roles (Basic, Pro, Admin) if they don't already exist.

    This function initializes the default roles in the database using the
    SQLAlchemyUserDatastore provided by Flask-Security. It checks whether each
    role exists, and if not, creates it with the specified description.

    Args:
        app (Flask): The Flask application instance.

    Returns:
        None
    """
    with app.app_context():
        # Initialize the datastore with the current database and models.
        user_datastore = SQLAlchemyUserDatastore(db, User, Role)

        # Define the default roles to be created.
        default_roles = [
            {"name": "Basic", "description": "Standard user role"},
            {"name": "Pro", "description": "Pro users have additional privileges"},
            {"name": "Admin", "description": "Administrator access"}
        ]

        try:
            # Loop through each default role and create it if it doesn't exist.
            for role_data in default_roles:
                # Remove 'description' if the Role model doesn't have that attribute.
                if not hasattr(Role, 'description'):
                    role_data.pop("description", None)

                # Check if the role already exists.
                role = Role.query.filter_by(name=role_data["name"]).first()
                if not role:
                    # Create the role using the datastore's create_role method.
                    user_datastore.create_role(**role_data)
                    current_app.logger.info(f"Created role: {role_data['name']}")

            # Commit the new roles to the database.
            db.session.commit()
        except Exception as e:
            current_app.logger.error(f"Error creating default roles: {str(e)}")
            db.session.rollback()
