import re
import subprocess
import threading
import time
import os
import logging

from ..lock_manager import lock as queue_lock
from .time_manager import TimeManager
from ..obs import OBSSocketManager
from .nginx_stream_manager import drop_stream_publisher, record_stream
from app.api.discord import send_discord_message

logger = logging.getLogger(__name__)


class Singleton(type):
    _instances = {}
    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]
    
class ProcessManager(metaclass=Singleton):

    current_stream_process = None
    current_stream_key = None
    current_dj_name = None
    gstreamer_out_log = None
    stream_queue = None
    obs_socket_manager = None
    time_manager = None

    def __init__(self, stream_queue, ffmpeg_out_log=None):
        self.gstreamer_out_log = ffmpeg_out_log
        self.stream_queue = stream_queue
        self.obs_socket_manager = OBSSocketManager(stream_queue)

    def log_gstreamer_output(self,pipe, prefix, log_file):
        """
        Logs the output from the GStreamer subprocess.

        Args:
            pipe: Stream to read from (stdout or stderr).
            prefix: Prefix for each log line.
            log_file: File object to write logs to.
        """
        try:
            for line in iter(pipe.readline, ''):
                if not line:
                    break
                formatted_output = f"{prefix} {line.rstrip()}\n"
                log_file.write(formatted_output)
                log_file.flush()
        except Exception as e:
            logger.exception(f"Error reading GStreamer output: {e}")
        finally:
            pipe.close()

        # Function to start re-streaming a user's stream to motherstream
    def start_stream(self, streamer):
        """
        Starts re-streaming the user's stream to motherstream using GStreamer.

        Args:
            streamer: Object containing stream details like stream_key, dj_name, etc.
        """
        stream_host = os.environ.get('HOST')
        rtmp_port = os.environ.get('RTMP_PORT')

        stream_key = streamer.stream_key
        dj_name = streamer.dj_name
        time_zone = streamer.timezone

        # Validate environment variables
        if not stream_host or not rtmp_port:
            raise Exception("Error: HOST and RTMP_PORT environment variables must be set.")

        self.current_stream_key = stream_key
        self.current_dj_name = dj_name

        gstreamer_cmd = [
            "gst-launch-1.0",
            "-e",  # Ensure EOS is sent on interrupt
            "rtmpsrc", f"location=rtmp://{stream_host}:{rtmp_port}/live/{stream_key}", "timeout=10", "!",
            "flvdemux", "name=demux", 
            "demux.audio", "!", "queue", "!", "decodebin", "!",
            "audioconvert", "!", "audioresample", "!",
            "voaacenc", "bitrate=128000", "!",  # Set to match desired audio quality
            "queue", "!", "mux.",
            "demux.video", "!", "queue", "!", "decodebin", "!", "videorate" "!",
            "videoconvert", "!", "x264enc", "bitrate=3000", "tune=zerolatency", "speed-preset=veryslow", "!",
            "video/x-h264,profile=baseline", "!",  # Ensures compatibility
            "queue", "!", "mux.",
            "flvmux", "name=mux", "streamable=true", "!",
            "rtmpsink", f"location=rtmp://{stream_host}:{rtmp_port}/motherstream/live", "sync=false"
            
        ]

        
        logger.info("Starting GStreamer subprocess...")
        self.current_stream_process = subprocess.Popen(
            gstreamer_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        # Check if the process started successfully
        return_code = self.current_stream_process.poll()
        if return_code is not None:
            logger.debug(f"GStreamer process exited immediately with return code {return_code}")
            return

        logger.debug("...GStreamer subprocess started successfully")
        logger.info(f"Started streaming live/{stream_key} to motherstream/live")

        # Toggle OBS sources if necessary
        self.obs_socket_manager.toggle_gstreamer_source(only_off=False)
        self.obs_socket_manager.toggle_timer_source(only_off=False)

        # Record the stream start (implement record_stream as needed)
        record_stream(stream_key, dj_name, 'start')

        # Send a Discord notification (implement send_discord_message as needed)
        send_discord_message(f"{dj_name} has now started streaming!")

        # Start threads to log GStreamer output
        threading.Thread(target=self.log_gstreamer_output, args=(self.current_stream_process.stdout, "[GStreamer stdout]", self.gstreamer_out_log), daemon=True).start()
        threading.Thread(target=self.log_gstreamer_output, args=(self.current_stream_process.stderr, "[GStreamer stderr]", self.gstreamer_out_log), daemon=True).start()

    # Function to stop the current re-streaming process
    # Returns stopped stream key
    # It is not the responsibility of this function to manage the queue list. That should be done separate of this function
    def stop_stream(self):

        if self.current_stream_process:
            logger.info("Stopping GStreamer subprocess...")
            self.current_stream_process.terminate()
            try:
                self.current_stream_process.wait(timeout=10)
                self.current_stream_process.kill()
                logger.info("GStreamer subprocess terminated gracefully.")
            except subprocess.TimeoutExpired:
                logger.warning("GStreamer subprocess did not terminate in time; killing it.")
            finally:
                self.current_stream_process = None   

            self.obs_socket_manager.toggle_gstreamer_source(only_off=True)
            self.obs_socket_manager.toggle_timer_source(only_off=True)   

            logger.debug(f"Stopped streaming {self.current_stream_key}")

            # stop recording here
            record_stream(self.current_stream_key,self.current_dj_name,'stop')
            send_discord_message(f"{self.current_dj_name} has stopped streaming.")

            # Tell nginx to drop the connection
            drop_stream_publisher(self.current_stream_key)
            to_return = self.current_stream_key

            self.current_stream_key = None
            self.current_dj_name = None

            logger.debug("For safe measure, killing all running ffmpeg processes...")
            try:
                subprocess.run(["killall", "gst-launch-1.0"], check=True)
                logger.debug("Done killing all running ffmpeg processes.")
            except Exception as e:
                logger.exception(f"Error trying to kill all ffmpeg processes. There are probably none left: {e}")
            
            self.gstreamer_out_log.write("FFMPEG process killed.\n")
            return to_return

        
    def _cleanup_stream(self):
        self.stop_stream()
        self.stream_queue.unqueue_client_stream()
        self.obs_socket_manager.toggle_gstreamer_source(only_off=True)
        self.obs_socket_manager.toggle_timer_source(only_off=True)
        self.obs_socket_manager.toggle_loading_message_source(only_off=True)
        self.time_manager = None

    # Background thread to manage the stream queue
    def process_queue(self):
        while True:
            with queue_lock:
                # If no current stream and there are streams in the queue
                current_streamer = self.stream_queue.current_streamer()
                if not self.current_stream_process: 
                    if current_streamer:
                        logger.debug("Starting a stream...")
                        next_streamer = current_streamer
                        try:
                            self.start_stream(next_streamer)
                            self.time_manager = TimeManager()

                        except Exception as e:
                            logger.exception(f"Error starting stream: {e}")
                            self.stream_queue.unqueue_client_stream()  
                    else:
                        #TODO: create method of toggling only off once by knowing status of source
                        self.obs_socket_manager.toggle_gstreamer_source(only_off=True)
                        self.obs_socket_manager.toggle_timer_source(only_off=True)
                else:
                    # Check if the swap interval has passed and end the current stream if it has
                    if self.time_manager.has_swap_interval_elapsed():
                        logger.debug(f"Swap interval of {self.time_manager.get_swap_interval()} seconds elapsed, stopping current stream.")
                        self._cleanup_stream()
        
                # If the current stream has ended (ffmpeg process has exited)
                if self.current_stream_process and self.current_stream_process.poll() is not None:
                    logger.debug(f"ffmpeg process for {self.current_stream_key} ended")
                    self._cleanup_stream()
            # Polling sleep time
            time.sleep(3) 
    


