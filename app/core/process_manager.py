import re
import subprocess
import threading
import time
import os
import logging

from ..lock_manager import lock as queue_lock
from .time_manager import TimeManager
from ..obs import OBSSocketManager
from .srs_stream_manager import drop_stream_publisher, get_stream_state, async_record_stream
from app.api.discord import send_discord_message
from app.api.shazam import SongRecognizer

logger = logging.getLogger(__name__)


class Singleton(type):
    _instances = {}
    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]
    
class StreamManager(metaclass=Singleton):

    priority_key = None

    last_stream_key = None
    is_blocking_last_streamer = False

    current_dj_name = None
    stream_queue = None
    obs_socket_manager = None
    time_manager = None

    current_song_data = None

    def __init__(self, stream_queue):
        self.stream_queue = stream_queue
        self.obs_socket_manager = OBSSocketManager(stream_queue)

    def set_song_data(self,song_data):
        self.song_data = song_data
    
    def get_song_data(self):
        return self.song_data

    def start_stream(self,streamer):

        stream_key = streamer.stream_key
        dj_name = streamer.dj_name
        time_zone = streamer.timezone
        
        self.set_priority_key(None)
        self.current_dj_name = dj_name
        self.time_manager = TimeManager()
        
        # self.obs_socket_manager.toggle_gstreamer_source(only_off=False)
        # self.obs_socket_manager.toggle_timer_source(only_off=False)

        send_discord_message(f"{dj_name} has now started streaming!")
        async_record_stream(stream_key=stream_key,dj_name=dj_name,action="start")

    def switch_stream(self):
        self.obs_socket_manager.toggle_gstreamer_source(only_off=False)
        # self.obs_socket_manager.toggle_timer_source(only_off=True)
        # self.obs_socket_manager.toggle_loading_message_source(only_off=True)
        self.time_manager = None

        # remove old state
        old_streamer = self.stream_queue.unqueue_client_stream()
        logger.debug(f"Removed {old_streamer.stream_key} from the queue")
        
        # stop recording
        async_record_stream(stream_key=old_streamer.stream_key,dj_name=old_streamer.dj_name,action="stop")
        
        self.set_last_stream_key(old_streamer.stream_key)
        # drop just in case
        drop_stream_publisher(old_streamer.stream_key)

        logger.debug(f"Stopped streaming {old_streamer.stream_key}")

        send_discord_message(f"{old_streamer.dj_name} has stopped streaming.")

        self.set_last_stream_key(old_streamer.stream_key)


        # Get new state ready
        current_streamer = self.stream_queue.current_streamer()
        if current_streamer:
            self.start_stream(current_streamer)
            # self.obs_socket_manager.toggle_gstreamer_source(only_off=False)
            # self.obs_socket_manager.toggle_timer_source(only_off=False)

            # prioritize and kick the user to re-init the forwarding
            self.set_priority_key(current_streamer.stream_key)
            drop_stream_publisher(current_streamer.stream_key)
        else:
            self.set_priority_key(None)

    def delete_last_streamer_key(self):
        self.last_stream_key = None
    def set_last_stream_key(self,key):
        self.last_stream_key = key
    def get_last_streamer_key(self):
        return self.last_stream_key
    
    def get_priority_key(self):
        return self.priority_key
    def set_priority_key(self, key):
        self.priority_key = key


    def get_is_blocking_last_streamer(self):
        return self.is_blocking_last_streamer
    def toggle_block_previous_client(self):
        self.is_blocking_last_streamer = not self.is_blocking_last_streamer
        logger.info(f"Toggle last streamer block. Will block previously kicked client: {self.is_blocking_last_streamer}")

    def modify_swap_time(self,time, reset_time=False):
        self.time_manager.modify_swap_interval(interval=time,reset_time=reset_time)
    



    # Background thread to manage the stream queue
    def process_queue(self):
        # for init
        current_streamer = self.stream_queue.current_streamer()
        shazam_thread = None
        if current_streamer:
            # update state variables at startup.
            logger.info(f"Starting stream from persistent state...: {current_streamer.dj_name}")
            self.start_stream(current_streamer) 
            logger.info("Done")
        while True:

            motherstream_state = self.stream_queue.get_stream_key_queue_list()
            lead_stream = self.stream_queue.lead_streamer()
            logger.info(f'Lead Stream: {lead_stream}, Last Stream: {self.get_last_streamer_key()} State: {motherstream_state} PRIORITY: {self.priority_key} BLOCKING: {self.is_blocking_last_streamer}')
            # oryx_state = get_stream_state()
            
            if self.time_manager and self.time_manager.has_swap_interval_elapsed():
                logger.debug(f"Swap interval of {self.time_manager.get_swap_interval()} seconds elapsed, stopping current stream.")
                self.switch_stream()
            # Polling sleep time
            time.sleep(3) 
            
            if os.environ.get("SHAZAMING") == 'true':
                if shazam_thread is None or not shazam_thread.is_alive():
                    # logger.info("Attempting to restart song recognition thread")
                    song_recognizer = SongRecognizer()
                    shazam_thread = threading.Thread(target=song_recognizer.recognize_song_full, daemon=True)
                    shazam_thread.start()
                else:
                    # logger.info("Shazam thread is still kicking!")
                    if song_recognizer.song_data != self.current_song_data:
                        self.current_song_data = song_recognizer.song_data
                        print(self.current_song_data)
    


