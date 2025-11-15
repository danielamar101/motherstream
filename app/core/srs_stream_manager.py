
import requests
import logging
import os
import glob
import time
import shutil
import asyncio
import httpx

logger = logging.getLogger(__name__)
logging.getLogger("httpcore.http11").setLevel(logging.WARNING)
logging.getLogger("httpcore.connection").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)

NGINX_HOST = os.environ.get("RTMP_RECORD_HOST", "localhost")  # Default to localhost if not set
CONTROL_PORT = str(os.environ.get("STAT_PORT", "1985"))  # Default SRS API port

# Oryx/SRS configuration from environment
ORYX_HOST = os.getenv("ORYX_HOST", "localhost")
ORYX_PORT = os.getenv("ORYX_PORT", "2022")
ORYX_API_BASE = f"http://{ORYX_HOST}:{ORYX_PORT}/terraform/v1/mgmt"

# Log configuration for debugging
logger.info(f"SRS Stream Manager initialized - HOST: {NGINX_HOST}, PORT: {CONTROL_PORT}")

async def rename_latest_recording(dj_name):
    RECORD_DIR = os.environ.get("RECORD_DIR", "/var/www/streams/stream-recordings")
    record_dir = RECORD_DIR 

    try:
        # Find the most recently added .flv file in the record directory
        list_of_files = glob.glob(os.path.join(record_dir, "*.flv"))
        if not list_of_files:
            logger.info("No recording files found.")
            return

        latest_file = max(list_of_files, key=os.path.getmtime)

        timestamp = time.strftime("%m-%d-%I-%M%p")
        new_file = os.path.join(record_dir, f"{dj_name}-{timestamp}.flv")

        # Rename the latest file
        shutil.move(latest_file, new_file)

        logger.info(f"Renamed {latest_file} to {new_file}")
    except shutil.Error as e:
        print(f"Shutil error: {e}")
    except FileNotFoundError as e:
        print(f"File not found: {e}")
    except PermissionError as e:
        print(f"Permission error: {e}")
    except Exception as e:
        logger.error(f"Error trying to rename recording name: {e}")

async def record_stream(stream_key, dj_name, action):
    # action should be start/stop

    params = {
        "app": "live",
        "name": stream_key,
    }
    response = None
    
    # Log the attempted connection for debugging
    target_url = f"http://{NGINX_HOST}:{CONTROL_PORT}/control/record/{action}"
    logger.debug(f"Attempting recording control: {action} to {target_url}")
    
    try:
        # Use an async HTTP library with timeout to prevent hanging
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(
                target_url,
                params=params,
            )
        if response.status_code in [200, 204]:
            logger.info(f"Successfully controlled recording: {action} for {dj_name}")
            if action == 'stop':
                # Ensure rename_latest_recording is asynchronous or wrap in a thread pool
                await rename_latest_recording(dj_name)
        else:
            logger.warning(f"Recording control returned status {response.status_code} for action: {action}")
    except httpx.ConnectError as e:
        logger.error(f"Cannot connect to recording service at {target_url}: {e}")
        logger.info(f"Recording failed but stream will continue without recording")
    except httpx.TimeoutException as e:
        logger.error(f"Timeout connecting to recording service: {e}")
        logger.info(f"Recording failed but stream will continue without recording")
    except Exception as e:
        logger.error(f"Exception controlling recording. Action: {action}. Exception: {e}")
        logger.info(f"Recording failed but stream will continue without recording")

    return response

# run this asynchronously from http server so that it doesnt block and activates only after the publish hook request completes.
# Wrapper to trigger the coroutine in an active event loop
def async_record_stream(stream_key, dj_name, action):
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(record_stream(stream_key=stream_key, dj_name=dj_name, action=action))
    except RuntimeError:
        # If no running loop, create a new one
        asyncio.run(record_stream(stream_key=stream_key, dj_name=dj_name, action=action))


def drop_stream_publisher(stream_key):

    headers = {
        "Content-Type": "application/json",
        "Authorization": os.environ.get("SRS_AUTHORIZATION_BEARER", "Invalid auth bearer")
    }
    params = {
      "token": "always12",
      "vhost": "__defaultVhost__",
      "app": "live",
      "stream": stream_key
    }
    logger.info("Kicking stream publisher...")
    try:
        response = requests.post(f"{ORYX_API_BASE}/streams/kickoff",json=params, headers=headers)
        if response.status_code == 200:
            logger.info("Successfully dropped publisher.")
        else:
            logger.info("Failure dropping publisher.")
    except Exception as e:
        logger.error(f"Exception dropping publisher: {e}")
    return response
#nada


def get_stream_state():

    headers = {
        "Content-Type": "application/json",
        "Authorization": os.environ.get("SRS_AUTHORIZATION_BEARER", "Invalid auth bearer")
    }

    logger.info("Obtaining all streamer info ")
    try:
        response = requests.post(f"{ORYX_API_BASE}/streams/query",headers=headers)
        if response.status_code == 200:
            json_response = response.json()
            streams = [client["stream"] for client in json_response["data"]["streams"]]
            return streams
        else:
            logger.info(f"Failure querying stream state. Code: {response.status_code}")
    except Exception as e:
        logger.error(f"Exception querying stream state.: {e}")

    return response


def is_stream_publishing(stream_key: str, timeout: float = 2.0) -> bool:
    """
    Check if a specific stream key is currently publishing to SRS.
    
    Args:
        stream_key: The stream key to check
        timeout: Maximum time to wait for the API response
        
    Returns:
        bool: True if stream is actively publishing, False otherwise
    """
    headers = {
        "Content-Type": "application/json",
        "Authorization": os.environ.get("SRS_AUTHORIZATION_BEARER", "Invalid auth bearer")
    }

    try:
        response = requests.post(
            f"{ORYX_API_BASE}/streams/query",
            headers=headers,
            timeout=timeout
        )
        
        if response.status_code == 200:
            json_response = response.json()
            streams = json_response.get("data", {}).get("streams", [])
            
            # Check if our stream key is in the active streams list
            for client in streams:
                if client.get("stream") == stream_key:
                    logger.debug(f"Stream {stream_key} is actively publishing")
                    return True
            
            logger.debug(f"Stream {stream_key} is NOT currently publishing")
            return False
        else:
            logger.warning(f"Failed to query stream state. Code: {response.status_code}")
            return False
            
    except requests.Timeout:
        logger.warning(f"Timeout checking if stream {stream_key} is publishing")
        return False
    except Exception as e:
        logger.error(f"Exception checking if stream {stream_key} is publishing: {e}")
        return False



