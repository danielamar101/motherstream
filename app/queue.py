
import json
import os
import logging

from .db.schemas import User

logger = logging.getLogger(__name__)

class Singleton(type):
    _instances = {}
    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]


class StreamQueue(metaclass=Singleton):

    stream_queue = []

    def __init__(self, saved_state=[]):
        self.stream_queue = saved_state

    def get_dj_name_queue_list(self):
        dj_name_list_to_return = []
        for user in self.stream_queue:
            dj_name_list_to_return.append(user.dj_name)

        return dj_name_list_to_return
    
    def current_streamer(self):
        if self.stream_queue:
            return self.stream_queue[0]
        else:
            return None
    
        # save updated queue state to persistent store.
    def _write_persistent_state(self):
        try:
            with open('../QUEUE.json','w') as queue_file:
                queue_file.write(json.dumps(self.stream_queue))
        except Exception as e:
            logger.exception(f'error: {e}')

    def queue_client_stream(self,user: User):
        
        self.stream_queue.append(user)
        self._write_persistent_state()

    def unqueue_client_stream(self):
        self.stream_queue.pop(0)
        self._write_persistent_state()

    def clear_queue(self):
        self.stream_queue = []

    def persist_queue(self):
        # import persistent queue in the event of a server timeout
        try:
            if os.path.exists("./QUEUE.json"):
                with open("./QUEUE.json",'r') as queue_file:
                    return json.load(queue_file)
        except json.JSONDecodeError as e:
            logger.debug(f"Error reading input file: {e}")
        except Exception as e:
            logger.exception(e)

