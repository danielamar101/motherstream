import os
import time
import logging
from obswebsocket import obsws, requests
import threading

from websocket import WebSocketConnectionClosedException

from app.lock_manager import obs_lock

logger = logging.getLogger(__name__)

obsws_logger = logging.getLogger('obswebsocket.core')
obsws_logger.setLevel(logging.CRITICAL + 1)

app_api_obs_log = logging.getLogger('app.api.obs')
# app_api_obs_log.setLevel(logging.CRITICAL + 1)

class OBSSocketManager():

    obs_websocket = None
    # Removed stream_queue dependency from constructor
    # stream_queue = None
    def __init__(self):
        # Removed stream_queue parameter
        # self.stream_queue = stream_queue

        self.OBS_HOST = os.environ.get("OBS_HOST", "localhost") # Added default
        self.OBS_PORT = os.environ.get("OBS_PORT", 4455)      # Added default
        self.OBS_PASSWORD = os.environ.get("OBS_PASSWORD")
        if not self.OBS_PASSWORD:
            logger.warning("OBS_PASSWORD environment variable not set. Connection might fail.")
        self.obs_websocket = obsws(self.OBS_HOST, self.OBS_PORT, self.OBS_PASSWORD)
        logger.debug("Connecting to websocket...")
        self.__connect()

        # TODO: Evaluate if we want this websocket usage - This used stream_queue
        # self.start_loading_message_thread()

        # self.toggle_obs_source(source_name="Queue", scene_name="MOTHERSTREAM", toggle_timespan=1)
    
    def __connect(self):
        try:
            self.obs_websocket.connect()
            logger.info("Connected to obs websocket.")
        except Exception as e:
            logger.error(e)

    def disconnect(self):
        try:
            self.obs_websocket.disconnect()
            logger.info("Disconnected from obs websocket.")
        except Exception as e:
            logger.error(e)

    def is_source_visible(self, source_name, scene_name):
        logger.debug(f"Checking visibility for {scene_name}:{source_name}...")
        try:
            # 1. Get scene item list for the scene
            scene_item_list = self.obs_websocket.call(requests.GetSceneItemList(sceneName=scene_name))

            # 2. Get sceneItemId for the specified source
            scene_id = None
            for item in scene_item_list.datain['sceneItems']:
                if item['sourceName'] == source_name:
                    scene_id = item['sceneItemId']
                    break
            if not scene_id:
                raise Exception(f"Error: Cannot find source '{source_name}' in scene '{scene_name}'.")

            # 3. Get source properties to check if it's enabled (visible)
            scene_item_properties = self.obs_websocket.call(requests.GetSceneItemEnabled(sceneName=scene_name, sceneItemId=scene_id))

            is_visible = scene_item_properties.datain['sceneItemEnabled']
            
            logger.debug(f"Source '{source_name}' visibility in '{scene_name}': {'Visible' if is_visible else 'Hidden'}")
            return is_visible
        except Exception as e:
            logger.error(f"Exception while checking source visibility: {e}")
            return False

    def toggle_obs_source(self,source_name, scene_name, toggle_timespan, only_off=False):

        with obs_lock:
            try:
                # 1. Get scene item list from scene
                scene_item_list = self.obs_websocket.call(requests.GetSceneItemList(sceneName=scene_name))
        
                #2. Get scene_id from scene item dict
                scene_id = None
                for item in scene_item_list.datain['sceneItems']:
                    if item['sourceName'] == source_name:
                        scene_id = item['sceneItemId']
                        break;
                if not scene_id:
                    raise Exception("Error getting source id. Cannot find proper source.")

                #3. Hide/unhide the source in the current scene only if it is on already
                if self.is_source_visible(source_name,scene_name):
                    logger.debug(f"TOGGLING OBS {scene_name}:{source_name} OFF")
                    self.obs_websocket.call(requests.SetSceneItemEnabled(sceneName=scene_name, sceneItemId=scene_id, sceneItemEnabled=False))
                    time.sleep(toggle_timespan)
                    
                if not only_off:
                    logger.debug(f"TOGGLING OBS {scene_name}:{source_name} ON")
                    self.obs_websocket.call(requests.SetSceneItemEnabled(sceneName=scene_name, sceneItemId=scene_id, sceneItemEnabled=True))
                    # time.sleep(toggle_timespan)
                    logger.info("...done toggling.")
            except WebSocketConnectionClosedException as e:
                logger.error("WebSocket is closed. Is the OBS app open?")
                logger.error("Attempting to restart connection to the websocket...")
                self.obs_websocket = obsws(self.OBS_HOST, self.OBS_PORT, self.OBS_PASSWORD)
                self.__connect()
                time.sleep(2)
            except Exception as e:
                logger.error(f"Exception with OBS WebSocket: {e}")
                self.obs_websocket = obsws(self.OBS_HOST, self.OBS_PORT, self.OBS_PASSWORD)
                self.__connect()
                time.sleep(2)
    
    def toggle_timer_source(self, only_off=False):
        source_name = 'TIMER1'
        time_remaining_text = 'TIME REMAINING'
        scene_name = 'MOTHERSTREAM'

        try:
            self.toggle_obs_source(source_name=source_name, scene_name=scene_name, toggle_timespan=1, only_off=only_off)
            self.toggle_obs_source(source_name=time_remaining_text, scene_name=scene_name, toggle_timespan=1, only_off=only_off)
        except Exception as e:
            logger.error(f"Error toggling off {scene_name}:{source_name}. {e}")

    def restart_media_source(self, input_name: str):
        """Sends a request to OBS to restart a specific media source."""
        # Try different action strings based on OBS WebSocket version
        possible_actions = [
            "OBS_WEBSOCKET_MEDIA_INPUT_ACTION_RESTART",
            "restart",
            "RESTART"
        ]
        
        logger.info(f"Attempting to restart media source: {input_name}")
        
        with obs_lock: 
            try:
                # First, let's try to get the media input status to see if it exists
                try:
                    status_request = requests.GetMediaInputStatus(inputName=input_name)
                    status_response = self.obs_websocket.call(status_request)
                    logger.info(f"Media input '{input_name}' status: {status_response.datain}")
                except Exception as status_error:
                    logger.warning(f"Could not get status for media input '{input_name}': {status_error}")
                
                # Try each possible action string
                for action in possible_actions:
                    try:
                        logger.info(f"Trying action: {action}")
                        request = requests.TriggerMediaInputAction(inputName=input_name, mediaAction=action)
                        response = self.obs_websocket.call(request)
                        
                        logger.info(f"Successfully triggered restart for media source: {input_name} using action: {action}")
                        logger.debug(f"Response: {response.datain if hasattr(response, 'datain') else 'No response data'}")
                        return True
                        
                    except Exception as action_error:
                        logger.warning(f"Action '{action}' failed for media source {input_name}: {action_error}")
                        continue
                
                # If we get here, all actions failed
                logger.error(f"All restart actions failed for media source: {input_name}")
                return False
                    
            except WebSocketConnectionClosedException:
                logger.error(f"Failed to restart media source {input_name}: WebSocket is closed. Is OBS running?")
                # Attempt to reconnect
                logger.info("Attempting to reconnect to OBS WebSocket...")
                self.__connect()
                return False
            except Exception as e:
                logger.error(f"An error occurred while trying to restart media source {input_name}: {e}", exc_info=True)
                # Consider if reconnection is needed here too
                self.__connect()
                return False

    def get_media_input_status(self, input_name: str):
        """Get the status of a media input for debugging purposes."""
        logger.info(f"Getting status for media input: {input_name}")
        with obs_lock:
            try:
                request = requests.GetMediaInputStatus(inputName=input_name)
                response = self.obs_websocket.call(request)
                logger.info(f"Media input '{input_name}' status: {response.datain}")
                return response.datain
            except Exception as e:
                logger.error(f"Failed to get media input status for {input_name}: {e}")
                return None

    def list_inputs(self):
        """List all inputs for debugging purposes."""
        logger.info("Getting list of all inputs...")
        with obs_lock:
            try:
                request = requests.GetInputList()
                response = self.obs_websocket.call(request)
                inputs = response.datain.get('inputs', [])
                logger.info(f"Found {len(inputs)} inputs:")
                for input_item in inputs:
                    logger.info(f"  - {input_item.get('inputName', 'Unknown')} (Type: {input_item.get('inputKind', 'Unknown')})")
                return inputs
            except Exception as e:
                logger.error(f"Failed to get input list: {e}")
                return []

# Create a global instance
# Ensure environment variables are loaded before this point if running as script
# In a FastAPI context, this will run when the module is imported.
obs_socket_manager_instance = OBSSocketManager()