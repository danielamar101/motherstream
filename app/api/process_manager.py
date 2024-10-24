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
    ffmpeg_out_log = None
    stream_queue = None
    obs_socket_manager = None
    time_manager = None

    def __init__(self, stream_queue, ffmpeg_out_log=None):
        self.ffmpeg_out_log = ffmpeg_out_log
        self.stream_queue = stream_queue
        self.obs_socket_manager = OBSSocketManager(stream_queue)

    def log_ffmpeg_output(self,pipe, prefix):
        try:
            for line in iter(pipe.readline, ''):
                if not line:
                    break
                formatted_output = f"{prefix} {line.rstrip()}\n"
                self.ffmpeg_out_log.write(formatted_output)
                self.ffmpeg_out_log.flush()
        except Exception as e:
            logger.exception(f"Error reading FFmpeg output: {e}")
        finally:
            pipe.close()

    # Function to start re-streaming a user's stream to motherstream
    def start_stream(self,streamer):
        stream_host = os.environ.get('HOST')
        rtmp_port = os.environ.get('RTMP_PORT')

        stream_key = streamer.stream_key
        dj_name = streamer.dj_name
        time_zone = streamer.timezone
        
        # TODO: Move this app validation up some levels
        if not stream_host or not rtmp_port:
            raise Exception("Error: HOST and RTMP_PORT environment variables must be set.")

        self.current_stream_key = stream_key
        self.current_dj_name = dj_name

        # build motherstream restream command
        ffmpeg_cmd = [
            'ffmpeg', 
            "-rw_timeout", "10000000", 
            '-i', f'rtmp://{stream_host}:{rtmp_port}/live/{stream_key}', 
            '-flush_packets', '0', 
            '-fflags', '+genpts', 
            '-max_interleave_delta', '0', 
            '-map', '0:v?', 
            '-map', '0:a?',
            '-copy_unknown', 
            '-c', 'copy', 
            '-f', 'flv', 
            f'rtmp://{stream_host}:{rtmp_port}/motherstream/live'
        ]

        logger.info("Starting ffmpeg subprocess...")
        self.current_stream_process = subprocess.Popen(ffmpeg_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        
        return_code = self.current_stream_process.poll()
        if return_code is not None:
            logger.debug(f"FFmpeg process exited immediately with return code {return_code}")
            return
        
        logger.debug("...done")
        logger.info(f"Started streaming live/{stream_key} to motherstream/live")

        self.obs_socket_manager.toggle_gstreamer_source(only_off=False)
        self.obs_socket_manager.toggle_timer_source(only_off=False)
        record_stream(stream_key,dj_name,'start')


        send_discord_message(f"{dj_name} has now started streaming!")


        threading.Thread(target=self.log_ffmpeg_output, args=(self.current_stream_process.stdout, "[FFmpeg stdout]"), daemon=True).start()
        threading.Thread(target=self.log_ffmpeg_output, args=(self.current_stream_process.stderr, "[FFmpeg stderr]"), daemon=True).start()


    # Function to stop the current re-streaming process
    # Returns stopped stream key
    # It is not the responsibility of this function to manage the queue list. That should be done separate of this function
    def stop_current_stream(self):
        if self.current_stream_process:
            try:
                logger.info("Terminating ffmpeg process...")
                self.current_stream_process.terminate()
                self.current_stream_process.wait(timeout=2)
                logger.info("...ffmpeg process terminated.")
            except Exception as e:
                logger.exception(e)
                self.current_stream_process.kill()
                logger.exception("...ffmpeg process killed!")

            logger.debug(f"Stopped streaming {self.current_stream_key}")

            # Tell nginx to drop the connection

            record_stream(self.current_stream_key,self.current_dj_name,'stop')
            send_discord_message(f"{self.current_dj_name} has stopped streaming.")

            drop_stream_publisher(self.current_stream_key)
            # stop recording here
            to_return = self.current_stream_key

            self.current_stream_process = None
            self.current_stream_key = None
            self.current_dj_name = None

            logger.debug("For safe measure, killing all running ffmpeg processes...")
            try:
                subprocess.run(["killall", "ffmpeg"], check=True)
                logger.debug("Done killing all running ffmpeg processes.")
            except Exception as e:
                logger.exception(f"Error trying to kill all ffmpeg processes: {e}")
            
            self.ffmpeg_out_log.write("FFMPEG process killed.\n")
            return to_return
        
    def _cleanup_stream(self):
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
    


