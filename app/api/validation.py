
from ..db.crud import get_user_by_stream_key
from ..db.main import get_db
import logging
import re
from fastapi import Depends
logger = logging.getLogger(__name__)

def ensure_valid_user(stream_key: str):

    db = next(get_db())
    if not stream_key:
        return None
        # Sanitize stream_key
    if not re.match(r'^[A-Za-z0-9_-]+$', stream_key):
        logger.exception(f"Invalid stream name: {stream_key}")
        raise Exception(f"Invalid stream name. Not allowing validation stream.") 
        return None
    try:
        user = get_user_by_stream_key(db=db,stream_key=stream_key)
        if user:
            return user
        else:
            return None
    except Exception as e:
        logger.exception(f"Error getting user: {e}")
        return None
