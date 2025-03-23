
import json
import os
from pathlib import Path
import logging

from ..lock_manager import lock as queue_lock
from ..db.schemas import User
from ..db.crud import get_user, get_user_by_stream_key
from ..db.main import get_db

logger = logging.getLogger(__name__)

class Singleton(type):
    _instances = {}
    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]


class StreamQueue(metaclass=Singleton):

    last_stream_key = None
    stream_queue = []
    queue_file_path = Path(os.getcwd()) / 'QUEUE.json'


    def __init__(self, saved_state=[]):
        self.stream_queue = saved_state

         # Reload the queue object in the event of server shutdown during stream
        self.persist_queue()
    
    def get_full_user_object(self,user_id):
        db = next(get_db())
        return get_user(db,user_id)
    
    def get_full_user_object_with_stream_key(self,stream_key):
        db = next(get_db())
        return get_user_by_stream_key(db,stream_key)

    def get_dj_name_queue_list(self):
        dj_name_list_to_return = []
        for user in self.stream_queue:
            dj_name_list_to_return.append(user.dj_name)

        return dj_name_list_to_return
    
    def get_stream_key_queue_list(self):
        stream_key_list_to_return = []
        for user in self.stream_queue:
            stream_key_list_to_return.append(user.stream_key)

        return stream_key_list_to_return
    
    def current_streamer(self):
        if self.stream_queue:
            return self.stream_queue[0]
        else:
            return None

    def lead_streamer(self):
        if self.stream_queue:
            return self.stream_queue[0].stream_key
        else:
            return None

        # save updated queue state to persistent store.
    def _write_persistent_state(self):
        try:
            with self.queue_file_path.open('w') as queue_file:
                to_write = []
                for user in self.stream_queue:
                    to_write.append(str(user.id))
                queue_file.write(json.dumps(to_write))
        except Exception as e:
            print(e)
            print("ERROR")
            logger.exception(f'error: {e}')

    # store user queue by id
    def queue_client_stream(self,user: User):
        with queue_lock:
            self.stream_queue.append(user)
        self._write_persistent_state()

    def unqueue_client_stream(self):
        with queue_lock:
            last_user = self.stream_queue.pop(0)
        self._write_persistent_state()
        return last_user
    
    def remove_client_with_stream_key(self, stream_key):
        try:
            user_to_remove = None
            for user in self.stream_queue:
                if user.stream_key == stream_key:
                    user_to_remove = user
                    break
            if user_to_remove:
                self.stream_queue.remove(user_to_remove)
            else:
                logger.debug(f"No user with stream key {stream_key} found in the queue")
        except Exception as e:
            logger.debug(f"Error removing user with stream key: {e}")

    def clear_queue(self):
        self.stream_queue = []

    # convert user id back into user object
    def persist_queue(self):
        # import persistent queue in the event of a server timeout
        try:
            if os.path.exists(self.queue_file_path):
                with self.queue_file_path.open('r') as queue_file:
                    users = json.load(queue_file)
                    for user_id in users:
                        user_object = self.get_full_user_object(int(user_id))
                        if user_object:
                            self.stream_queue.append(user_object)
                        else:
                            logger.error("Error finding user in stream queue.")
        except json.JSONDecodeError as e:
            logger.debug(f"Error reading input file: {e}")
        except Exception as e:
            logger.exception(e)

