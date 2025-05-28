import threading
import time
import logging
from queue import Queue
from enum import Enum
from dataclasses import dataclass

from app.api.discord import send_discord_message
from app.core.srs_stream_manager import async_record_stream, drop_stream_publisher
# Import the global OBS instance
from app.obs import obs_socket_manager_instance


logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# Track the last time an OBS job was executed to add delays
last_obs_job_time = 0
OBS_JOB_DELAY = 2.0  # Minimum seconds between OBS jobs to prevent crashes

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

@dataclass
class Job:
    type: JobType
    payload: dict

job_queue: Queue[Job] = Queue()

def is_obs_related_job(job_type: JobType) -> bool:
    """Check if a job type involves OBS websocket operations."""
    obs_job_types = {JobType.TOGGLE_OBS_SRC, JobType.RESTART_MEDIA_SOURCE, JobType.FLASH_LOADING_MESSAGE}
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
    logger.info(f"Dispatching job: {job.type.name} with payload: {job.payload}")
    
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
            toggle_timespan = job.payload.get("toggle_timespan", 1) # Default timespan
            if source_name:
                # Map specific source names if needed (e.g., "gstreamer" -> "GMOTHERSTREAM")
                actual_source_name = source_name
                if source_name == "gstreamer":
                    actual_source_name = "GMOTHERSTREAM"
                elif source_name == "timer":
                    actual_source_name = "TIMER1"
                elif source_name == "loading":
                    actual_source_name = "LOADING"
                # Add more mappings as needed

                logger.info(f"Toggling OBS source: {scene_name}:{actual_source_name}, only_off={only_off}")
                obs_socket_manager_instance.toggle_obs_source(
                    source_name=actual_source_name,
                    scene_name=scene_name,
                    toggle_timespan=toggle_timespan,
                    only_off=only_off
                )
                # Special case for timer - toggle text label too
                if source_name == "timer":
                     obs_socket_manager_instance.toggle_obs_source(
                        source_name="TIME REMAINING",
                        scene_name=scene_name,
                        toggle_timespan=toggle_timespan,
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
            toggle_timespan = job.payload.get("toggle_timespan", 1.5)  # Default timespan from original code
            
            logger.debug("Flashing loading message...")
            obs_socket_manager_instance.toggle_obs_source(
                source_name="LOADING",
                scene_name=scene_name,
                toggle_timespan=toggle_timespan,
                only_off=only_off
            )

        else:
            # Consider logging an error or raising for unhandled job types
            logger.warning(f"Unhandled job type: {job.type}")
    except Exception as e:
        logger.error(f"Error processing job {job.type.name}: {e}", exc_info=True)
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