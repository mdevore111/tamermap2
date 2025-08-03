# User Management Utility

## Overview
The `user_manage.py` utility provides comprehensive user management capabilities, including user creation and role management. It supports both interactive and command-line modes of operation.

## Features
- Create new users with roles and subscription dates
- Assign/change user roles (Basic, Pro, Admin)
- Update membership flags and subscription dates
- Interactive user creation with validation
- Command-line role management

## Usage
```bash
python user_manage.py [create|role] [options]
```

### Commands
1. Create User:
```bash
python user_manage.py create
```
Interactive mode prompts for:
- Email address
- First name (optional)
- Last name (optional)
- Stripe Customer ID (optional)
- Role (Basic, Pro, Admin)
- Pro subscription end date (for Pro/Admin roles)

2. Assign Role:
```bash
python user_manage.py role --email user@example.com --role [Basic|Pro|Admin]
```

## Role Management
### Valid Roles
- `Basic`: Standard user access
- `Pro`: Premium features access
- `Admin`: Administrative access

### Role Effects
- Pro/Admin roles automatically set `is_pro=True`
- Basic role sets `is_pro=False`
- Pro role extends subscription by one month if active

## User Creation Process
1. Validates input data
2. Checks for existing users
3. Creates user with temporary password
4. Assigns specified role
5. Sets membership flags
6. Configures subscription dates (if applicable)

## Logging
- Logs are stored in `utils/logs/user_manage.log`
- Rotating file handler with 5MB max size and 5 backup files
- Detailed logging of all operations

## Functions

### create_user()
Interactive function for creating new users with:
- Input validation
- Role assignment
- Subscription date management
- Error handling

### assign_role()
Command-line function for role management:
- Role verification
- User lookup
- Role assignment
- Membership flag updates

## Error Handling
- Input validation
- Duplicate user checks
- Role existence verification
- Database transaction management
- Detailed error logging

## Dependencies
- Flask-Security
- SQLAlchemy
- Flask
- Python standard library 