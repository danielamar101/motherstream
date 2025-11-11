import threading
import time
import os
import logging
import csv
from queue import Queue
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime

from app.api.discord import send_discord_message
from app.core.srs_stream_manager import async_record_stream, drop_stream_publisher
from app.core.stream_health_checker import StreamHealthChecker
# Import the global OBS instance
from app.obs import obs_socket_manager_instance


logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# Track the last time an OBS job was executed to add delays
last_obs_job_time = 0
OBS_JOB_DELAY = 2.0  # Minimum seconds between OBS jobs to prevent crashes

# Job timing tracking
JOB_TIMING_FILE = "/app/logs/job_timings.csv"  # Docker container path with volume mount
job_timing_lock = threading.Lock()

class JobType(Enum):
    START_STREAM     = "start_stream"
    SWITCH_STREAM    = "switch_stream"
    TOGGLE_OBS_SRC   = "toggle_obs_source"
    KICK_PUBLISHER   = "kick_publisher"
    RENAME_RECORDING = "rename_recording"
    STOP_RECORDING   = "stop_recording" 
    SEND_DISCORD_MESSAGE = "send_discord_message" 
    RESTART_MEDIA_SOURCE = "restart_media_source"
    FLASH_LOADING_MESSAGE = "flash_loading_message"
    CHECK_STREAM_HEALTH = "check_stream_health"
    SWITCH_GSTREAMER_SOURCE = "switch_gstreamer_source"  # New: Dynamic source creation

@dataclass
class Job:
    type: JobType
    payload: dict
    enqueued_at: float = field(default_factory=time.time)

job_queue: Queue[Job] = Queue()

def write_job_timing(job_type: JobType, wait_time: float, execution_time: float, timestamp: str):
    """Write job timing information to a CSV file."""
    try:
        with job_timing_lock:
            # Ensure the logs directory exists
            log_dir = os.path.dirname(JOB_TIMING_FILE)
            os.makedirs(log_dir, exist_ok=True)
            
            # Check if file exists to determine if we need to write headers
            file_exists = os.path.isfile(JOB_TIMING_FILE)
            
            with open(JOB_TIMING_FILE, 'a', newline='') as csvfile:
                writer = csv.writer(csvfile)
                
                # Write header if file is new
                if not file_exists:
                    writer.writerow(['timestamp', 'job_type', 'wait_time_ms', 'execution_time_ms', 'total_time_ms'])
                
                # Write timing data
                writer.writerow([
                    timestamp,
                    job_type.name,
                    f"{wait_time * 1000:.2f}",  # Convert to milliseconds
                    f"{execution_time * 1000:.2f}",  # Convert to milliseconds
                    f"{(wait_time + execution_time) * 1000:.2f}"  # Total time
                ])
    except Exception as e:
        logger.error(f"Failed to write job timing to file: {e}", exc_info=True)

def is_obs_related_job(job_type: JobType) -> bool:
    """Check if a job type involves OBS websocket operations."""
    obs_job_types = {
        JobType.TOGGLE_OBS_SRC, 
        JobType.RESTART_MEDIA_SOURCE, 
        JobType.FLASH_LOADING_MESSAGE,
        JobType.SWITCH_GSTREAMER_SOURCE
    }
    return job_type in obs_job_types

def wait_for_obs_job_delay():
    """Ensure minimum delay between OBS jobs to prevent crashes."""
    global last_obs_job_time
    current_time = time.time()
    time_since_last_obs_job = current_time - last_obs_job_time
    
    if time_since_last_obs_job < OBS_JOB_DELAY:
        sleep_time = OBS_JOB_DELAY - time_since_last_obs_job
        logger.debug(f"Waiting {sleep_time:.2f}s before next OBS job to prevent crashes")
        time.sleep(sleep_time)
    
    last_obs_job_time = time.time()

def dispatch(job: Job):
    """Calls the appropriate function based on the job type."""
    # Track timing
    dispatch_start_time = time.time()
    wait_time = dispatch_start_time - job.enqueued_at
    timestamp = datetime.now().isoformat()
    
    if job.type not in [JobType.CHECK_STREAM_HEALTH]:
        logger.info(f"Dispatching job: {job.type.name} with payload: {job.payload} (waited {wait_time*1000:.2f}ms)")
    else:
        logger.debug(f"Dispatching job: {job.type.name} (waited {wait_time*1000:.2f}ms)")
        
    # Add delay before OBS-related jobs to prevent crashes
    if is_obs_related_job(job.type):
        wait_for_obs_job_delay()
    
    try:
        if job.type == JobType.START_STREAM:
            # Actual logic for starting stream side-effects
            dj_name = job.payload.get("dj_name")
            stream_key = job.payload.get("stream_key")
            if dj_name:
                send_discord_message(f"{dj_name} has now started streaming!")
            else:
                logger.warning("START_STREAM job missing 'dj_name' in payload")
            if stream_key and dj_name:
                async_record_stream(stream_key=stream_key, dj_name=dj_name, action="start")
            else:
                logger.warning("START_STREAM job missing 'stream_key' or 'dj_name' for recording")
        elif job.type == JobType.TOGGLE_OBS_SRC:
            # Assumes payload contains necessary info like source_name, scene_name, only_off
            source_name = job.payload.get("source_name")
            scene_name = job.payload.get("scene_name", "MOTHERSTREAM") # Default scene
            only_off = job.payload.get("only_off", False)
            if source_name:
                # Map specific source names if needed (e.g., "gstreamer" -> "GMOTHERSTREAM")
                actual_source_name = source_name
                if source_name == "gstreamer":
                    actual_source_name = "GMOTHERSTREAM"
                elif source_name == "timer":
                    actual_source_name = "TIMER"
                elif source_name == "loading":
                    actual_source_name = "LOADING"
                # Add more mappings as needed

                if os.environ.get("ENVIRONMENT") == "staging":
                    actual_source_name = f"{actual_source_name} Staging"

                logger.info(f"Toggling OBS source: {scene_name}:{actual_source_name}, only_off={only_off}")
                obs_socket_manager_instance.toggle_obs_source(
                    source_name=actual_source_name,
                    scene_name=scene_name,
                    only_off=only_off
                )
                # Special case for timer - toggle text label too
                if source_name == "timer":
                     obs_socket_manager_instance.toggle_obs_source(
                        source_name="TIME REMAINING",
                        scene_name=scene_name,
                        only_off=only_off
                    )
            else:
                logger.warning("TOGGLE_OBS_SRC job missing 'source_name' in payload")

        elif job.type == JobType.KICK_PUBLISHER:
            stream_key = job.payload.get("stream_key")
            if stream_key:
                drop_stream_publisher(stream_key)
            else:
                logger.warning("KICK_PUBLISHER job missing 'stream_key' in payload")

        elif job.type == JobType.STOP_RECORDING:
            dj_name = job.payload.get("dj_name")
            stream_key = job.payload.get("stream_key")
            if stream_key and dj_name:
                async_record_stream(stream_key=stream_key, dj_name=dj_name, action="stop")
            else:
                logger.warning("STOP_RECORDING job missing 'stream_key' or 'dj_name'")

        elif job.type == JobType.SEND_DISCORD_MESSAGE:
            message = job.payload.get("message")
            if message:
                send_discord_message(message)
            else:
                logger.warning("SEND_DISCORD_MESSAGE job missing 'message' in payload")

        elif job.type == JobType.RESTART_MEDIA_SOURCE:
            source_name = job.payload.get("source_name")
            if source_name:
                logger.info(f"Restarting OBS media source: {source_name}")
                obs_socket_manager_instance.restart_media_source(input_name=source_name)
                logger.info(f"Successfully triggered restart for media source: {source_name}")
            else:
                 logger.warning("RESTART_MEDIA_SOURCE job missing 'source_name' in payload")

        elif job.type == JobType.FLASH_LOADING_MESSAGE:
            # Flash the loading message - equivalent to toggle_loading_message_source
            scene_name = job.payload.get("scene_name", "MOTHERSTREAM")  # Default scene
            only_off = job.payload.get("only_off", False)
            
            logger.debug("Flashing loading message...")
            obs_socket_manager_instance.toggle_obs_source(
                source_name="LOADING",
                scene_name=scene_name,
                only_off=only_off
            )

        elif job.type == JobType.CHECK_STREAM_HEALTH:
            # Check stream health using the health checker
            stream_url = job.payload.get("stream_url")
            health_checker = job.payload.get("health_checker")
            
            if stream_url and health_checker:
                logger.debug(f"Checking health for stream: {stream_url}")
                is_healthy = health_checker.check_stream_health()
                
                if not is_healthy:
                    unhealthy_duration = health_checker.get_unhealthy_duration()
                    logger.warning(f"Stream {stream_url} unhealthy for {unhealthy_duration:.1f}s")
                else:
                    logger.debug(f"Stream {stream_url} is healthy")
            else:
                logger.warning("CHECK_STREAM_HEALTH job missing 'stream_url' or 'health_checker' in payload")

        elif job.type == JobType.SWITCH_GSTREAMER_SOURCE:
            # Dynamic source creation for stream switching
            rtmp_url = job.payload.get("rtmp_url")
            scene_name = job.payload.get("scene_name", "MOTHERSTREAM")
            
            if rtmp_url:
                logger.info(f"Switching to new GStreamer source with URL: {rtmp_url}")
                success = obs_socket_manager_instance.switch_to_new_gstreamer_source(
                    rtmp_url=rtmp_url,
                    scene_name=scene_name
                )
                if success:
                    logger.info("Successfully switched to new GStreamer source")
                else:
                    logger.error("Failed to switch to new GStreamer source")
            else:
                logger.warning("SWITCH_GSTREAMER_SOURCE job missing 'rtmp_url' in payload")

        else:
            # Consider logging an error or raising for unhandled job types
            logger.warning(f"Unhandled job type: {job.type}")
        
        # Record successful execution time
        execution_time = time.time() - dispatch_start_time
        write_job_timing(job.type, wait_time, execution_time, timestamp)
        
        if job.type not in [JobType.CHECK_STREAM_HEALTH]:
            logger.info(f"Job {job.type.name} executed in {execution_time*1000:.2f}ms")
        
    except Exception as e:
        logger.error(f"Error processing job {job.type.name}: {e}", exc_info=True)
        # Still record timing even on failure
        execution_time = time.time() - dispatch_start_time
        write_job_timing(job.type, wait_time, execution_time, timestamp)
        # Optional: Implement retry logic here, e.g., re-queueing the job
        # if job.retries < MAX_RETRIES:
        #     job.retries += 1
        #     job_queue.put(job)
        # else:
        #     logger.error(f"Job {job.type.name} failed after max retries.")

def worker_loop():
    """Continuously fetches jobs from the queue and dispatches them."""
    logger.info("Worker thread started.")
    while True:
        job = None # Ensure job is defined in the loop scope
        try:
            job = job_queue.get() # Blocks until a job is available
            logger.info(f"Job queue contains {job_queue.qsize()} jobs: {[job.type.name for job in job_queue.queue]}")
            logger.debug(f"Worker processing job: {job.type.name}")
            dispatch(job)
        except Exception as e:
            # Catch unexpected errors during job retrieval or dispatch handling
            logger.error(f"Critical error in worker loop: {e}", exc_info=True)
            # Avoid rapid failure loops; consider a small delay
            time.sleep(1)
        finally:
            # Ensure task_done is called if a job was retrieved, even if dispatch failed
            if job is not None:
                try:
                    job_queue.task_done()
                except ValueError:
                    # Can happen if queue is empty/job already marked done elsewhere
                    logger.warning(f"Failed to mark job {job.type.name} as done, possibly already handled.")
            # Optional: Short sleep to prevent busy-waiting if queue is empty often
            # time.sleep(0.01)

# Initialize and start the worker thread
# daemon=True allows the main program to exit even if this thread is running
worker_thread = threading.Thread(target=worker_loop, daemon=True, name="JobWorkerThread")
worker_thread.start()
logger.info("Worker thread initialized and dispatched.")

# Helper function to enqueue jobs (optional, but can be convenient)
def add_job(job_type: JobType, payload: dict):
    """Adds a job to the central queue."""
    new_job = Job(type=job_type, payload=payload)
    logger.debug(f"Enqueuing job: {new_job.type.name}")
    job_queue.put(new_job)