"""
Flask extensions module.

This module initializes Flask extensions used throughout the application.
Extensions are initialized without binding to a specific application instance,
allowing the create_app factory to bind them later.
"""

import platform
import warnings
from flask_caching import Cache
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_mail import Mail
from flask_security import Security
from flask_session import Session
from flask_sqlalchemy import SQLAlchemy
from limits.storage import MemoryStorage, RedisStorage

# Initialize extensions
db = SQLAlchemy()
mail = Mail()
security = Security()
session = Session()
cache = Cache()

# Configure limiter storage based on platform
if platform.system() == 'Windows':
    # Suppress the warning about in-memory storage since it's intentional for Windows
    warnings.filterwarnings('ignore', message='Using the in-memory storage.*')
    storage_config = {
        "storage": MemoryStorage(),
        "storage_options": {
            "warn_on_memory_storage": False  # Explicitly disable the warning
        }
    }
else:
    # Use Redis for Linux/Mac
    storage_config = {
        "storage_uri": "redis://localhost:6379/2"
    }

# Initialize Flask-Limiter with platform-specific storage
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["10000 per day", "1000 per hour", "100 per minute"],
    storage_options=storage_config
)
