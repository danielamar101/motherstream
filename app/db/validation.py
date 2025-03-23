from .crud import get_user_by_stream_key
from .main import get_db
import logging
import re
from fastapi import Depends
from sqlalchemy.orm import Session
import asyncio

logger = logging.getLogger(__name__)

async def ensure_valid_user(stream_key: str):
    """Asynchronously validate a user by their stream key"""
    if not stream_key:
        return None
        
    # Sanitize stream_key
    if not re.match(r'^[A-Za-z0-9_-]+$', stream_key):
        logger.exception(f"Invalid stream name: {stream_key}")
        raise Exception(f"Invalid stream name. Not allowing validation stream.")
        return None
        
    try:
        # Get database session
        db = next(get_db())
        
        # Run database query in thread pool to prevent blocking
        loop = asyncio.get_running_loop()
        user = await loop.run_in_executor(None, get_user_by_stream_key, db, stream_key)
        
        if user:
            return user
        else:
            return None
    except Exception as e:
        logger.exception(f"Error getting user: {e}")
        return None
