import re
import subprocess
import threading
import time
import os
import logging

from ..lock_manager import lock as queue_lock
from .time_manager import TimeManager
from ..obs import OBSSocketManager
from .srs_stream_manager import drop_stream_publisher, get_stream_state
from app.api.discord import send_discord_message

logger = logging.getLogger(__name__)


class Singleton(type):
    _instances = {}
    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]
    
class StreamManager(metaclass=Singleton):

    is_switching = None
    current_stream_key = None
    next_stream_key = None

    current_dj_name = None
    stream_queue = None
    obs_socket_manager = None
    time_manager = None

    def __init__(self, stream_queue):
        self.stream_queue = stream_queue
        self.obs_socket_manager = OBSSocketManager(stream_queue)


    def start_stream(self,streamer):

        stream_key = streamer.stream_key
        dj_name = streamer.dj_name
        time_zone = streamer.timezone
        
        self.current_stream_key = stream_key
        self.is_switching = False
        self.current_dj_name = dj_name
        self.time_manager = TimeManager()
        

        self.obs_socket_manager.toggle_gstreamer_source(only_off=False)
        self.obs_socket_manager.toggle_timer_source(only_off=False)


        send_discord_message(f"{dj_name} has now started streaming!")

    def update_stream_state(self):

        # remove old state
        old_streamer = self.stream_queue.unqueue_client_stream()

        logger.debug(f"Removed {self.current_stream_key} from the queue")
        drop_stream_publisher(self.current_stream_key)
        logger.debug(f"Stopped streaming {self.current_stream_key}")

        send_discord_message(f"{self.current_dj_name} has stopped streaming.")

        # Get new state ready
        current_streamer = self.stream_queue.current_streamer()
        print(current_streamer)
        if current_streamer:
            self.start_stream(current_streamer)
            # kick the user to re-init the forwarding
            drop_stream_publisher(self.current_stream_key)
        else:
            self.current_stream_key = None
        
        next_streamer = self.stream_queue.next_streamer()
        if next_streamer:
            self.next_stream_key = next_streamer.stream_key
        else:
            self.next_stream_key = None


    def get_current_streamer_key(self):
        return self.current_stream_key
    def get_is_switching(self):
        return self.is_switching
    def toggle_is_switching(self):
        self.is_switching = not self.is_switching
    def get_next_streamer_key(self):
        return self.next_stream_key
    
    def cleanup_stream(self):
        self.obs_socket_manager.toggle_gstreamer_source(only_off=True)
        self.obs_socket_manager.toggle_timer_source(only_off=True)
        self.obs_socket_manager.toggle_loading_message_source(only_off=True)
        self.time_manager = None
        self.update_stream_state()

    # Background thread to manage the stream queue
    def process_queue(self):
        while True:
            with queue_lock:

                motherstream_state = self.stream_queue.get_stream_key_queue_list()
                # print(motherstream_state)
                print(f'Current Stream: {self.current_stream_key}, Next Stream: {self.next_stream_key}, State: {motherstream_state} Is_switching: {self.is_switching}')
                # oryx_state = get_stream_state()
                
                # for stream_key in motherstream_state:
                #     if stream_key not in oryx_state and (stream_key is not self.current_stream_key or stream_key is not self.stream_queue.next_streamer()):
                #         print(f"Removing: {stream_key} because they are no longer publishing to oryx")
                #         drop_stream_publisher(stream_key=stream_key)
                # Check if the swap interval has passed and end the current stream if it has
                if self.time_manager and self.time_manager.has_swap_interval_elapsed():
                    logger.debug(f"Swap interval of {self.time_manager.get_swap_interval()} seconds elapsed, stopping current stream.")
                    self.cleanup_stream()
            # Polling sleep time
            time.sleep(3) 
    


