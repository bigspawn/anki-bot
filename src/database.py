"""
Database operations for the German Learning Bot
"""

# Direct import from the new modular structure
from .core.database.database_manager import DatabaseManager, get_db_manager
from .config import get_database_path

# Simple init function
def init_db(db_path=None):
    """Initialize database"""
    db_manager = get_db_manager(db_path)
    db_manager.init_database()
    return db_manager

# Clean exports
__all__ = ['DatabaseManager', 'get_db_manager', 'init_db', 'get_database_path']