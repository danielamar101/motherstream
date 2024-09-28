

import re
import subprocess
import threading
import time
import os

from ..lock_manager import lock as queue_lock
from ..queue import StreamQueue

stream_host = os.environ.get('HOST')
rtmp_port = os.environ.get('RTMP_PORT')
if not stream_host or not rtmp_port:
    print("")
    raise Exception("Error: HOST and RTMP_PORT environment variables must be set.")

class Singleton(type):
    _instances = {}
    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]
    
class ProcessManager(metaclass=Singleton):

    current_stream_process = None
    current_stream_key = None
    ffmpeg_out_log = None
    stream_queue = None

    def __init__(self, ffmpeg_out_log=None):
        self.ffmpeg_out_log = ffmpeg_out_log
        self.stream_queue = StreamQueue()

    def log_ffmpeg_output(self,pipe, prefix):
        try:
            for line in iter(pipe.readline, ''):
                if not line:
                    break
                formatted_output = f"{prefix} {line.rstrip()}\n"
                self.ffmpeg_out_log.write(formatted_output)
                self.ffmpeg_out_log.flush()
        except Exception as e:
            print(f"Error reading FFmpeg output: {e}")
        finally:
            pipe.close()

    # Function to start re-streaming a user's stream to motherstream
    def start_stream(self,stream_key: str):
        global stream_host, rtmp_port
        # Sanitize stream_key
        if not re.match(r'^[A-Za-z0-9_-]+$', stream_key):
            print(f"Invalid stream name: {stream_key}")
            raise Exception(f"Invalid stream name. Not starting stream.") 

        # build motherstream restream command
        ffmpeg_cmd = [
            'ffmpeg', "-rw_timeout", "5000000", '-i', f'rtmp://{stream_host}:{rtmp_port}/live/{stream_key}', '-flush_packets', '0', '-fflags', '+genpts', '-max_interleave_delta', '0', '-map', '0:v?', '-map', '0:a?',
            '-copy_unknown', '-c', 'copy', '-f', 'flv', f'rtmp://{stream_host}:{rtmp_port}/motherstream/live'
        ]
        print("Starting ffmpeg subprocess...")
        self.current_stream_process = subprocess.Popen(ffmpeg_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return_code = self.current_stream_process.poll()
        if return_code is not None:
            print(f"FFmpeg process exited immediately with return code {return_code}")
            # Read any remaining output
            stderr_output, stdout_output = self.current_stream_process.communicate()
            print(f"FFmpeg stderr:\n{stderr_output}")
            print(f"FFmpeg stdout:\n{stdout_output}")
            return
        print("...done")

        self.current_stream_key = stream_key

        print(f"Started streaming live/{stream_key} to motherstream/live")

        threading.Thread(target=self.log_ffmpeg_output, args=(self.current_stream_process.stdout, "[FFmpeg stdout]"), daemon=True).start()
        threading.Thread(target=self.log_ffmpeg_output, args=(self.current_stream_process.stderr, "[FFmpeg stderr]"), daemon=True).start()


    # Function to stop the current re-streaming process
    # Returns stopped stream key
    # It is not the responsibility of this function to manage the queue list. That should be done separate of this function
    def stop_current_stream(self):
        if self.current_stream_process:
            try:
                print("Terminating ffmpeg process...")
                self.current_stream_process.terminate()
                self.current_stream_process.wait(timeout=10)
                print("ffmpeg process terminated")
            except Exception as e:
                print(e)
                self.current_stream_process.kill()
                print("ffmpeg process killed")
            print(f"Stopped streaming {self.current_stream_key}")

            to_return = self.current_stream_key

            self.current_stream_process = None
            self.current_stream_key = None

            print("For safe measure, killing all running ffmpeg processes...")
            try:
                subprocess.run(["killall", "ffmpeg"], check=True)
                print("Done killing all running ffmpeg processes.")
            except Exception as e:
                print(f"Error trying to kill all ffmpeg processes: {e}")
            
            self.ffmpeg_out_log.write("FFMPEG process killed.\n")
            return to_return
        
    # Background thread to manage the stream queue
    def process_queue(self):

        while True:
            with queue_lock:
                # If no current stream and there are streams in the queue
                actual_stream_queue = self.stream_queue.get_stream_queue()
                if not self.current_stream_process and actual_stream_queue:
                    print("Starting a stream...")
                    next_stream = actual_stream_queue[0] 
                    try:
                        self.start_stream(next_stream)
                    except Exception as e:
                        print(f"Error starting stream: {e}")
                        self.stream_queue.unqueue_client_stream()  

                # If the current stream has ended (ffmpeg process has exited)
                if self.current_stream_process and self.current_stream_process.poll() is not None:
                    print(f"ffmpeg process for {self.current_stream_key} ended")
                    self.stop_current_stream()
                    self.stream_queue.unqueue_client_stream()
            time.sleep(5) 
    


