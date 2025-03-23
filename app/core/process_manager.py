import threading
import time
import os
import logging
import asyncio


from ..lock_manager import lock as queue_lock
from .time_manager import TimeManager
from ..obs import OBSSocketManager
from .srs_stream_manager import drop_stream_publisher, async_record_stream
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

    async def start_stream(self,streamer):
        """Start streaming asynchronously"""
        try:
            # Run blocking operations in thread pool
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, self._start_stream_sync, streamer)
        except Exception as e:
            logger.error(f"Error starting stream: {e}")

    def _start_stream_sync(self, streamer):
        """Synchronous part of starting stream"""
        self.obs_socket_manager.toggle_gstreamer_source(only_on=True)
        self.obs_socket_manager.toggle_timer_source(only_on=True)
        self.obs_socket_manager.toggle_loading_message_source(only_on=True)
        self.obs_socket_manager.obs_process_call_queue()
        self.time_manager = TimeManager(streamer)

    async def switch_stream(self):
        """Asynchronously handle stream switching"""
        try:
            # Run OBS operations in a thread pool to prevent blocking
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, self._handle_obs_operations)
            
            # Handle queue operations
            old_streamer = self.stream_queue.unqueue_client_stream()
            logger.debug(f"Removed {old_streamer.stream_key} from the queue")
            
            # Stop recording asynchronously
            await record_stream(stream_key=old_streamer.stream_key, dj_name=old_streamer.dj_name, action="stop")
            
            self.set_last_stream_key(old_streamer.stream_key)
            
            # Drop publisher in background
            loop.create_task(self._drop_publisher_background(old_streamer.stream_key))
            
            logger.debug(f"Stopped streaming {old_streamer.stream_key}")
            
            # Send Discord message in background
            loop.create_task(self._send_discord_message_background(f"{old_streamer.dj_name} has stopped streaming."))
            
            # Get new state ready
            current_streamer = self.stream_queue.current_streamer()
            if current_streamer:
                await self.start_stream(current_streamer)
                
                # Prioritize and kick the user to re-init the forwarding
                self.set_priority_key(current_streamer.stream_key)
                loop.create_task(self._drop_publisher_background(current_streamer.stream_key))
            else:
                self.set_priority_key(None)
                
        except Exception as e:
            logger.error(f"Error in switch_stream: {e}")

    def _handle_obs_operations(self):
        """Handle OBS operations in a separate thread"""
        self.obs_socket_manager.toggle_gstreamer_source(only_off=True)
        self.obs_socket_manager.toggle_timer_source(only_off=True)
        self.obs_socket_manager.toggle_loading_message_source(only_off=True)
        self.obs_socket_manager.obs_process_call_queue()
        self.time_manager = None

    async def _drop_publisher_background(self, stream_key):
        """Drop publisher in the background"""
        try:
            await asyncio.sleep(0.1)  # Small delay to ensure proper order
            drop_stream_publisher(stream_key)
        except Exception as e:
            logger.error(f"Error dropping publisher: {e}")

    async def _send_discord_message_background(self, message):
        """Send Discord message in the background"""
        try:
            await asyncio.sleep(0.1)  # Small delay to ensure proper order
            send_discord_message(message)
        except Exception as e:
            logger.error(f"Error sending Discord message: {e}")

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

    def init_queue(self):
        # for init
        current_streamer = self.stream_queue.current_streamer()

        if current_streamer:
            # update state variables at startup.
            logger.info(f"Starting stream from persistent state...: {current_streamer.dj_name}")
            self.start_stream(current_streamer) 
            logger.info("Done")

    def process_queue(self):

        motherstream_state = self.stream_queue.get_stream_key_queue_list()
        lead_stream = self.stream_queue.lead_streamer()
        logger.info(f'Lead Stream: {lead_stream}, Last Stream: {self.get_last_streamer_key()} State: {motherstream_state} PRIORITY: {self.priority_key} BLOCKING: {self.is_blocking_last_streamer}')
        # oryx_state = get_stream_state()
        
        if self.time_manager and self.time_manager.has_swap_interval_elapsed():
            logger.debug(f"Swap interval of {self.time_manager.get_swap_interval()} seconds elapsed, stopping current stream.")
            self.switch_stream()

    shazam_thread = None
    def shazaming(self):

        if os.environ.get("SHAZAMING") == 'true':
            if self.shazam_thread is None or not self.shazam_thread.is_alive():
                # logger.info("Attempting to restart song recognition thread")
                song_recognizer = SongRecognizer()
                self.shazam_thread = threading.Thread(target=song_recognizer.recognize_song_full, daemon=True)
                self.shazam_thread.start()
            else:
                # logger.info("Shazam thread is still kicking!")
                if song_recognizer.song_data != self.current_song_data:
                    self.current_song_data = song_recognizer.song_data
                    print(self.current_song_data)
    


