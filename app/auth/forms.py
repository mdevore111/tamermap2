"""
forms.py - Authentication module using Flask-Security-Too

This module defines custom authentication-related forms and helper functions.
We extend the default registration form to include first_name and last_name fields.
Flask-Security-Too's built-in views (login, register, forgot password, etc.) are used,
so we do not define custom routes for these here.
"""

import logging

from flask import current_app
from flask_security.forms import ConfirmRegisterForm
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, HiddenField
from wtforms.validators import DataRequired, Email, EqualTo, Length, ValidationError

# =============================================================================
# Logging Configuration
# =============================================================================
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s'
)


# =============================================================================
# Form Definitions
# =============================================================================
class ExtendedRegisterForm(FlaskForm):
    """
    Extended registration form that includes first_name and last_name fields.
    """
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6)])
    password_confirm = PasswordField('Confirm Password', validators=[
        DataRequired(), EqualTo('password', message="Passwords must match.")
    ])
    first_name = StringField('First Name', validators=[DataRequired()])
    last_name = StringField('Last Name', validators=[DataRequired()])
    submit = SubmitField('Register')

    def validate_email(self, field):
        """
        Check if a user with the provided email already exists.
        """
        # Access the datastore via the Flask-Security extension.
        datastore = current_app.extensions['security'].datastore
        if datastore.find_user(email=field.data):
            raise ValidationError("A user with that email already exists. Please log in or use a different email.")

    def validate(self, extra_validators=None) -> bool:
        """
        Auto-populate the username with the email if not provided, then perform standard validation.
        """
        if not self.email.data:
            self.email.data = self.email.data
        return super().validate(extra_validators=extra_validators)

    def to_dict(self, **kwargs) -> dict:
        """
        Convert the form data into a dictionary suitable for user creation.

        This method excludes fields that are not part of the User model, such as 'password_confirm',
        'submit', and 'csrf_token'. Adjust this method if your User model requires additional fields.
        """
        data = {name: field.data for name, field in self._fields.items()}
        data.pop("password_confirm", None)
        data.pop("submit", None)
        data.pop("csrf_token", None)
        return data


class ExtendedConfirmRegisterForm(ConfirmRegisterForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    first_name = StringField('First Name', validators=[DataRequired()])
    last_name = StringField('Last Name', validators=[DataRequired()])
    password_confirm = PasswordField(
        'Confirm Password',
        validators=[DataRequired(), EqualTo('password', message='Passwords must match')]
    )

    def validate(self, extra_validators=None) -> bool:
        # If the email is empty, auto-populate it with the email.
        if not self.email.data:
            self.email.data = self.email.data
        return super().validate(extra_validators=extra_validators)


class LoginForm(FlaskForm):
    """
    User login form.
    """
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')


class ResetPasswordForm(FlaskForm):
    """
    Form for resetting the temporary password.
    This form includes two fields for password and confirmation.
    """
    password = PasswordField('Password', validators=[
        DataRequired(),
        Length(min=8, message="Password must be at least 8 characters long")
    ])
    password_confirm = PasswordField('Confirm Password', validators=[
        DataRequired(),
        EqualTo('password', message="Passwords must match")
    ])
    submit = SubmitField('Set Password')


class ChangePasswordForm(FlaskForm):
    """
    Form for changing the current password.
    This form includes current password, new password, and confirmation fields.
    """
    current_password = PasswordField('Current Password', validators=[DataRequired()])
    new_password = PasswordField('New Password', validators=[
        DataRequired(),
        Length(min=8, message="Password must be at least 8 characters long")
    ])
    new_password_confirm = PasswordField('Confirm New Password', validators=[
        DataRequired(),
        EqualTo('new_password', message="Passwords must match")
    ])
    submit = SubmitField('Change Password')


class ForgotPasswordForm(FlaskForm):
    """
    Form for requesting a password reset.
    This form includes an email field.
    """
    email = StringField('Email', validators=[
        DataRequired(),
        Email(message="Please enter a valid email address")
    ])
    submit = SubmitField('Send Reset Link')
