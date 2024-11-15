import re
import subprocess
import threading
import time
import os
import logging

from ..lock_manager import lock as queue_lock
from .time_manager import TimeManager
from ..obs import OBSSocketManager
from .srs_stream_manager import drop_stream_publisher
from app.api.discord import send_discord_message

logger = logging.getLogger(__name__)


class Singleton(type):
    _instances = {}
    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]
    
class StreamManager(metaclass=Singleton):

    current_stream_key = None
    current_dj_name = None
    stream_queue = None
    obs_socket_manager = None
    time_manager = None

    def __init__(self, stream_queue):
        self.stream_queue = stream_queue
        self.obs_socket_manager = OBSSocketManager(stream_queue)

    # Function to start re-streaming a user's stream to motherstream
    def start_stream(self,streamer):

        stream_key = streamer.stream_key
        dj_name = streamer.dj_name
        time_zone = streamer.timezone
        
        self.current_stream_key = stream_key
        self.current_dj_name = dj_name
        self.time_manager = TimeManager()
        

        self.obs_socket_manager.toggle_gstreamer_source(only_off=False)
        self.obs_socket_manager.toggle_timer_source(only_off=False)


        send_discord_message(f"{dj_name} has now started streaming!")

    # Function to stop the current re-streaming process
    # Returns stopped stream key
    # It is not the responsibility of this function to manage the queue list. That should be done separate of this function
    def stop_current_stream(self):

        logger.debug(f"Stopped streaming {self.current_stream_key}")

        send_discord_message(f"{self.current_dj_name} has stopped streaming.")
        drop_stream_publisher(self.current_stream_key)

        to_return = self.current_stream_key

        self.current_stream_key = None
        self.current_dj_name = None

        return to_return
    
    def cleanup_stream(self):
        self.stop_current_stream()
        self.stream_queue.unqueue_client_stream()
        self.obs_socket_manager.toggle_gstreamer_source(only_off=True)
        self.obs_socket_manager.toggle_timer_source(only_off=True)
        self.obs_socket_manager.toggle_loading_message_source(only_off=True)
        self.time_manager = None

    # Background thread to manage the stream queue
    def process_queue(self):
        while True:
            with queue_lock:
                # Check if the swap interval has passed and end the current stream if it has
                if self.time_manager and self.time_manager.has_swap_interval_elapsed():
                    logger.debug(f"Swap interval of {self.time_manager.get_swap_interval()} seconds elapsed, stopping current stream.")
                    self.cleanup_stream()
            # Polling sleep time
            time.sleep(3) 
    


