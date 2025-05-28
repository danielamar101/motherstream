import re
import subprocess
import threading
import time
import os
import logging

from ..lock_manager import lock as queue_lock
from .time_manager import TimeManager
# Import the global OBS instance instead of the class
from ..obs import obs_socket_manager_instance
# Remove direct imports of functions now handled by worker
# from .srs_stream_manager import drop_stream_publisher, get_stream_state, async_record_stream
# from app.api.discord import send_discord_message
from .srs_stream_manager import get_stream_state # Keep if needed elsewhere
from app.api.shazam import SongRecognizer
from .stream_health_checker import StreamHealthChecker

# Import job queue functions
from app.core.worker import add_job, JobType

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
    # Use the global OBS instance
    obs_socket_manager = obs_socket_manager_instance
    time_manager = None

    current_song_data = None

    def __init__(self, stream_queue):
        self.stream_queue = stream_queue
        # No longer need to instantiate OBSSocketManager here
        # self.obs_socket_manager = OBSSocketManager(stream_queue)
        
        # Loading message thread control
        self.loading_message_stop_event = threading.Event()
        self.loading_message_thread = None
        
        # Stream health monitoring
        self.stream_health_checker = StreamHealthChecker(
            stream_url="rtmp://127.0.0.1:1935/motherstream/live",
            unhealthy_threshold_seconds=30
        )

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
        
        # Reset stream health checker for new stream
        self.stream_health_checker.reset()
        
        add_job(JobType.START_STREAM, payload={"stream_key": stream_key, "dj_name": dj_name})
        logger.info(f"Enqueued START_STREAM job for DJ: {dj_name} with key: {stream_key}")

        add_job(JobType.TOGGLE_OBS_SRC, payload={"source_name": "GMOTHERSTREAM", "only_off": False, "toggle_timespan": 5})
        logger.debug("Enqueued TOGGLE_OBS_SRC job (gstreamer on)")

        add_job(JobType.TOGGLE_OBS_SRC, payload={"source_name": "timer", "only_off": False})
        logger.debug("Enqueued TOGGLE_OBS_SRC job (timer on)")

        # Enqueue job to restart the GStreamer media source
        add_job(JobType.RESTART_MEDIA_SOURCE, payload={"source_name": "GMOTHERSTREAM"})
        logger.debug("Enqueued RESTART_MEDIA_SOURCE job for GMOTHERSTREAM")

    def switch_stream(self):
        logger.info("Initiating stream switch...")

        # 1. Get the streamer to be removed
        old_streamer = self.stream_queue.unqueue_client_stream()
        if not old_streamer:
            logger.warning("switch_stream called but no current streamer to remove.")
            return # Nothing to switch from

        logger.debug(f"Switching away from: {old_streamer.dj_name} ({old_streamer.stream_key})")

        add_job(JobType.TOGGLE_OBS_SRC, payload={"source_name": "GMOTHERSTREAM", "only_off": True, "toggle_timespan": 5})
        logger.debug("Enqueued TOGGLE_OBS_SRC job (gstreamer off)")

        # Stop recording old stream
        add_job(JobType.STOP_RECORDING, payload={"stream_key": old_streamer.stream_key, "dj_name": old_streamer.dj_name})
        logger.debug(f"Enqueued STOP_RECORDING job for {old_streamer.dj_name}")

        # Kick old streamer publisher
        add_job(JobType.KICK_PUBLISHER, payload={"stream_key": old_streamer.stream_key})
        logger.debug(f"Enqueued KICK_PUBLISHER job for {old_streamer.stream_key}")

        # Send Discord notification for old streamer stopped
        add_job(JobType.SEND_DISCORD_MESSAGE, payload={"message": f"{old_streamer.dj_name} has stopped streaming."}) 
        logger.debug(f"Enqueued SEND_DISCORD_MESSAGE job for {old_streamer.dj_name} stopped")

        # Update internal state related to the old streamer
        self.set_last_stream_key(old_streamer.stream_key)
        self.time_manager = None # Reset timer since the stream ended
        logger.debug(f"Updated internal state: last_stream_key={old_streamer.stream_key}, time_manager reset.")

        # Reset stream health checker when switching streams
        self.stream_health_checker.reset()

        # 2. Get the next streamer (if any)
        current_streamer = self.stream_queue.current_streamer()
        if current_streamer:
            logger.info(f"Switching to new streamer: {current_streamer.dj_name}")
            # This call now correctly updates internal state and enqueues START_STREAM job
            self.start_stream(current_streamer)
            logger.debug(f"Called start_stream for {current_streamer.dj_name}")

            # Enqueue job to kick the *new* streamer to force re-init/prioritize
            add_job(JobType.KICK_PUBLISHER, payload={"stream_key": current_streamer.stream_key})
            logger.debug(f"Enqueued KICK_PUBLISHER job for new streamer {current_streamer.stream_key}")

            # Prioritize new streamer (Internal state)
            self.set_priority_key(current_streamer.stream_key)
            logger.debug(f"Set priority key to {current_streamer.stream_key}")
        else:
            logger.info("No next streamer in queue.")

            self.set_priority_key(None)

            add_job(JobType.TOGGLE_OBS_SRC, payload={"source_name": "timer", "only_off": True})
            logger.debug("Enqueued TOGGLE_OBS_SRC job (timer off)")

        logger.info("Stream switch processing complete (jobs enqueued).")

    def handle_unhealthy_stream(self):
        """Handle when the output stream has been unhealthy for too long."""
        current_streamer = self.stream_queue.current_streamer()
        if current_streamer:
            unhealthy_duration = self.stream_health_checker.get_unhealthy_duration()
            logger.error(f"Output stream unhealthy for {unhealthy_duration:.1f}s. Dropping publisher for {current_streamer.dj_name} ({current_streamer.stream_key})")
            
            # Send Discord notification about the issue
            add_job(JobType.SEND_DISCORD_MESSAGE, payload={
                "message": f"⚠️ Stream health issue detected. Dropping {current_streamer.dj_name} due to unhealthy output stream (unhealthy for {unhealthy_duration:.1f}s)."
            })
            
            logger.debug("Switching stream due to unhealthy stream")
            self.switch_stream()

            # Reset the health checker
            self.stream_health_checker.reset()
        else:
            logger.warning("Output stream unhealthy but no current streamer found")
            # Reset the health checker anyway
            self.stream_health_checker.reset()

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
    
    def flash_loading_message_loop(self):
        """Background loop to flash loading message when DJs are in queue."""
        logger.info("Loading message flash thread started.")
        while not self.loading_message_stop_event.is_set():
            try:
                if self.stream_queue.get_dj_name_queue_list():
                    logger.debug("TOGGLING NEXT STREAM IS LOADING MSG...")
                    add_job(JobType.FLASH_LOADING_MESSAGE, payload={"only_off": False})
                # Sleep to control flash frequency - adjust as needed
                # Use wait() instead of sleep() to allow immediate response to stop event
                if self.loading_message_stop_event.wait(timeout=2):  # Flash every 2 seconds when DJs are queued
                    break  # Stop event was set
            except Exception as e:
                logger.error(f"Error in loading message flash loop: {e}", exc_info=True)
                if self.loading_message_stop_event.wait(timeout=1):  # Brief pause before retrying
                    break
        logger.info("Loading message flash thread stopped.")

    def start_loading_message_thread(self):
        """Start the background thread for flashing loading messages."""
        # Stop any existing thread first
        self.stop_loading_message_thread()
        
        logger.info("Starting loading message toggle thread...")
        self.loading_message_stop_event.clear()  # Reset the stop event
        self.loading_message_thread = threading.Thread(
            target=self.flash_loading_message_loop, 
            daemon=True, 
            name="LoadingMessageThread"
        )
        self.loading_message_thread.start()
        logger.info("Loading message thread initialized and dispatched.")

    def stop_loading_message_thread(self):
        """Stop the loading message flash thread gracefully."""
        if self.loading_message_thread and self.loading_message_thread.is_alive():
            logger.info("Stopping loading message thread...")
            self.loading_message_stop_event.set()  # Signal the thread to stop
            self.loading_message_thread.join(timeout=5)  # Wait up to 5 seconds for clean shutdown
            
            if self.loading_message_thread.is_alive():
                logger.warning("Loading message thread did not stop within timeout")
            else:
                logger.info("Loading message thread stopped successfully")
        else:
            logger.debug("Loading message thread is not running")
        
        self.loading_message_thread = None

        add_job(JobType.TOGGLE_OBS_SRC, payload={"source_name": "LOADING", "only_off": True, "toggle_timespan": 1})
        logger.debug("Enqueued TOGGLE_OBS_SRC job (loading off)")

    # Background thread to manage the stream queue
    def process_queue(self):
        # for init
        current_streamer = self.stream_queue.current_streamer()
        shazam_thread = None
        if current_streamer:
            # update state variables at startup.
            logger.info(f"Starting stream from persistent state...: {current_streamer.dj_name}")
            # self.start_loading_message_thread()
            self.start_stream(current_streamer) 
            logger.info("Done")
        while True:

            motherstream_state = self.stream_queue.get_stream_key_queue_list()
            lead_stream = self.stream_queue.lead_streamer()
            logger.info(f'Lead Stream: {lead_stream}, Last Stream: {self.get_last_streamer_key()} State: {motherstream_state} PRIORITY: {self.priority_key} BLOCKING: {self.is_blocking_last_streamer}')
            if not lead_stream:
                add_job(JobType.TOGGLE_OBS_SRC, payload={"source_name": "GMOTHERSTREAM", "only_off": True, "toggle_timespan": 1})
                self.stop_loading_message_thread()
                logger.debug("Enqueued TOGGLE_OBS_SRC job (gstreamer off)")
                # Reset health checker when no stream is active
                self.stream_health_checker.reset()
            else:
                # Check stream health when there's an active stream
                add_job(JobType.CHECK_STREAM_HEALTH, payload={
                    "stream_url": self.stream_health_checker.stream_url,
                    "health_checker": self.stream_health_checker
                })
                
                # Check if stream has been unhealthy for too long
                if self.stream_health_checker.is_unhealthy_for_threshold():
                    self.handle_unhealthy_stream()
            
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
    


