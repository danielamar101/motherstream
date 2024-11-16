
import requests
import logging
import os
import glob
import time
import shutil

logger = logging.getLogger(__name__)

NGINX_HOST = os.environ.get("HOST")
CONTROL_PORT = str(os.environ.get("STAT_PORT"))

def rename_latest_recording(dj_name):
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

def record_stream(stream_key, dj_name, action):
    # action should be start/stop
    params = {
        "app": "live",
        "name": stream_key,
    }
    try:
        response = requests.post(f"http://{NGINX_HOST}:{CONTROL_PORT}/control/record/{action}",params=params)
        if response.status_code in [200,204]:
            logger.info(f"Successfully controlled recording: {action}")
            if action == 'stop':
                rename_latest_recording(dj_name)
        else:
            logger.info(f"Failure to control recording: {action}")
    except Exception as e:
        logger.error(f"Exception controlling recording. Action: {action}. Exception {e}")

    return response

def drop_stream_publisher(stream_key):

    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer srs-v2-a084f4b728964d3084564329affb906d" 
    }
    params = {
      "token": "always12",
      "vhost": "__defaultVhost__",
      "app": "live",
      "stream": stream_key
    }
    logger.info("Kicking stream publisher...")
    try:
        response = requests.post(f"http://localhost:2022/terraform/v1/mgmt/streams/kickoff",json=params, headers=headers)
        if response.status_code == 200:
            logger.info("Successfully dropped publisher.")
        else:
            logger.info("Failure dropping publisher.")
    except Exception as e:
        logger.error(f"Exception dropping publisher: {e}")

    return response

def get_stream_state():

    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer srs-v2-a084f4b728964d3084564329affb906d" 
    }

    logger.info("Obtaining all streamer info ")
    try:
        response = requests.post(f"http://localhost:2022/terraform/v1/mgmt/streams/query",headers=headers)
        if response.status_code == 200:
            json_response = response.json()
            streams = [client["stream"] for client in json_response["data"]["streams"]]
            return streams
        else:
            logger.info(f"Failure querying stream state. Code: {response.status_code}")
    except Exception as e:
        logger.error(f"Exception querying stream state.: {e}")

    return response



