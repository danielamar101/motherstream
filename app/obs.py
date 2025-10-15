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
        logger.info(f"Connecting to OBS: {self.OBS_HOST}:{self.OBS_PORT}")
        self.obs_websocket = obsws(self.OBS_HOST, self.OBS_PORT, self.OBS_PASSWORD)
        logger.debug("Connecting to websocket...")
        self.__connect()

        # Connection health monitoring
        self._connection_healthy = False
        self._last_health_check = 0
        self._health_check_interval = 30  # Check every 30 seconds
        self._reconnect_attempts = 0
        self._max_reconnect_attempts = 5
        self._reconnect_delay = 5  # Start with 5 second delay
        
        # Streaming monitoring and auto-start
        self._streaming_monitor_enabled = False  # Disabled by default
        self._is_streaming = False
        self._last_streaming_check = 0
        self._streaming_check_interval = 15  # Check streaming status every 15 seconds
        self._auto_start_attempts = 0
        self._max_auto_start_attempts = 3
        self._auto_start_delay = 10  # Wait 10 seconds between auto-start attempts
        
        # Start health monitoring thread
        self._start_health_monitor()

        # TODO: Evaluate if we want this websocket usage - This used stream_queue
        # self.start_loading_message_thread()

        # self.toggle_obs_source(source_name="Queue", scene_name="MOTHERSTREAM", toggle_timespan=1)
    
    def __connect(self):
        try:
            self.obs_websocket.connect()
            logger.info("Connected to obs websocket.")
            self._connection_healthy = True
            self._reconnect_attempts = 0  # Reset on successful connection
            self._reconnect_delay = 5     # Reset delay
        except Exception as e:
            logger.error(f"Failed to connect to OBS websocket: {e}")
            self._connection_healthy = False

    def disconnect(self):
        try:
            self.obs_websocket.disconnect()
            logger.info("Disconnected from obs websocket.")
            self._connection_healthy = False
        except Exception as e:
            logger.error(e)

    def _start_health_monitor(self):
        """Start the health monitoring thread."""
        health_thread = threading.Thread(target=self._health_monitor_loop, daemon=True, name="OBSHealthMonitor")
        health_thread.start()
        logger.info("OBS health monitor thread started")

    def _health_monitor_loop(self):
        """Continuously monitor OBS connection health and streaming status."""
        while True:
            try:
                current_time = time.time()
                
                # Regular health check
                if current_time - self._last_health_check >= self._health_check_interval:
                    self._check_connection_health()
                    self._last_health_check = current_time
                
                # Streaming status check (if enabled)
                if (self._streaming_monitor_enabled and 
                    current_time - self._last_streaming_check >= self._streaming_check_interval):
                    self._check_streaming_status()
                    self._last_streaming_check = current_time
                
                time.sleep(5)  # Check every 5 seconds, but only do health check based on interval
            except Exception as e:
                logger.error(f"Error in health monitor loop: {e}", exc_info=True)
                time.sleep(10)  # Wait longer on error

    def _check_connection_health(self):
        """Check if the OBS connection is healthy by making a simple request."""
        try:
            with obs_lock:
                # Try a simple request to check if connection is alive
                version_request = requests.GetVersion()
                response = self.obs_websocket.call(version_request)
                
                if response and hasattr(response, 'datain'):
                    self._connection_healthy = True
                    logger.debug("OBS connection health check passed")
                else:
                    logger.warning("OBS health check returned unexpected response")
                    self._connection_healthy = False
                    
        except WebSocketConnectionClosedException:
            logger.warning("OBS health check failed: WebSocket connection closed")
            self._connection_healthy = False
            self._attempt_reconnect()
        except Exception as e:
            logger.warning(f"OBS health check failed: {e}")
            self._connection_healthy = False
            self._attempt_reconnect()

    def _check_streaming_status(self):
        """Check if OBS is currently streaming and auto-start if needed."""
        if not self._connection_healthy:
            logger.debug("Skipping streaming check - connection not healthy")
            return
            
        try:
            with obs_lock:
                # Get streaming status
                stream_status_request = requests.GetStreamStatus()
                response = self.obs_websocket.call(stream_status_request)
                
                if response and hasattr(response, 'datain'):
                    self._is_streaming = response.datain.get('outputActive', False)
                    
                    if self._is_streaming:
                        logger.debug("OBS streaming status check: Currently streaming")
                        # Reset auto-start attempts when streaming is active
                        self._auto_start_attempts = 0
                    else:
                        logger.info("OBS streaming status check: Not streaming - attempting to start")
                        self._attempt_auto_start_streaming()
                else:
                    logger.warning("Failed to get streaming status from OBS")
                    
        except Exception as e:
            logger.error(f"Error checking streaming status: {e}")
            self._connection_healthy = False

    def _attempt_auto_start_streaming(self):
        """Attempt to automatically start streaming in OBS."""
        if self._auto_start_attempts >= self._max_auto_start_attempts:
            logger.warning(f"Max auto-start attempts ({self._max_auto_start_attempts}) reached. Stopping auto-start attempts.")
            return

        self._auto_start_attempts += 1
        logger.info(f"Attempting to auto-start OBS streaming (attempt {self._auto_start_attempts}/{self._max_auto_start_attempts})")
        
        try:
            with obs_lock:
                # Wait before attempting to start streaming
                if self._auto_start_attempts > 1:
                    logger.info(f"Waiting {self._auto_start_delay} seconds before auto-start attempt")
                    time.sleep(self._auto_start_delay)
                
                # Start streaming
                start_stream_request = requests.StartStream()
                response = self.obs_websocket.call(start_stream_request)
                
                logger.info(f"Auto-start streaming command sent to OBS")
                logger.debug(f"Start stream response: {response.datain if hasattr(response, 'datain') else 'No response data'}")
                
                # Give OBS a moment to start streaming, then check status
                time.sleep(2)
                
                # Verify streaming started
                stream_status_request = requests.GetStreamStatus()
                status_response = self.obs_websocket.call(stream_status_request)
                
                if status_response and hasattr(status_response, 'datain'):
                    is_now_streaming = status_response.datain.get('outputActive', False)
                    if is_now_streaming:
                        logger.info("Successfully auto-started OBS streaming")
                        self._is_streaming = True
                        self._auto_start_attempts = 0  # Reset on success
                    else:
                        logger.warning("Auto-start command sent but OBS is still not streaming")
                        
        except Exception as e:
            logger.error(f"Failed to auto-start streaming (attempt {self._auto_start_attempts}): {e}")

    def enable_streaming_monitor(self, enabled: bool = True):
        """Enable or disable streaming monitoring and auto-start."""
        self._streaming_monitor_enabled = enabled
        if enabled:
            logger.info("OBS streaming monitoring and auto-start enabled")
            # Reset attempts when enabling
            self._auto_start_attempts = 0
        else:
            logger.info("OBS streaming monitoring and auto-start disabled")

    def is_streaming_monitor_enabled(self):
        """Check if streaming monitoring is enabled."""
        return self._streaming_monitor_enabled

    def get_streaming_status(self):
        """Get current streaming status information."""
        return {
            "monitor_enabled": self._streaming_monitor_enabled,
            "is_streaming": self._is_streaming,
            "auto_start_attempts": self._auto_start_attempts,
            "max_auto_start_attempts": self._max_auto_start_attempts,
            "streaming_check_interval": self._streaming_check_interval
        }

    def force_start_streaming(self):
        """Manually force start streaming (bypasses attempt limits)."""
        logger.info("Manually forcing OBS to start streaming")
        try:
            with obs_lock:
                start_stream_request = requests.StartStream()
                response = self.obs_websocket.call(start_stream_request)
                
                logger.info("Manual start streaming command sent to OBS")
                logger.debug(f"Start stream response: {response.datain if hasattr(response, 'datain') else 'No response data'}")
                
                # Give OBS a moment to start streaming, then check status
                time.sleep(2)
                
                # Verify streaming started
                stream_status_request = requests.GetStreamStatus()
                status_response = self.obs_websocket.call(stream_status_request)
                
                if status_response and hasattr(status_response, 'datain'):
                    is_now_streaming = status_response.datain.get('outputActive', False)
                    self._is_streaming = is_now_streaming
                    return is_now_streaming
                    
                return False
                
        except Exception as e:
            logger.error(f"Failed to manually start streaming: {e}")
            return False

    def _attempt_reconnect(self):
        """Attempt to reconnect to OBS with exponential backoff."""
        if self._reconnect_attempts >= self._max_reconnect_attempts:
            logger.error(f"Max reconnection attempts ({self._max_reconnect_attempts}) reached. Giving up.")
            return

        self._reconnect_attempts += 1
        logger.info(f"Attempting to reconnect to OBS (attempt {self._reconnect_attempts}/{self._max_reconnect_attempts})")
        
        try:
            # Wait before attempting reconnection (exponential backoff)
            wait_time = min(self._reconnect_delay * (2 ** (self._reconnect_attempts - 1)), 60)
            logger.info(f"Waiting {wait_time} seconds before reconnection attempt")
            time.sleep(wait_time)
            
            # Create new websocket instance and connect
            logger.info(f"Creating new websocket instance and connecting to OBS: {self.OBS_HOST}:{self.OBS_PORT}")
            self.obs_websocket = obsws(self.OBS_HOST, self.OBS_PORT, self.OBS_PASSWORD)
            self.__connect()
            
            if self._connection_healthy:
                logger.info("Successfully reconnected to OBS")
            else:
                logger.warning("Reconnection attempt failed")
                
        except Exception as e:
            logger.error(f"Reconnection attempt {self._reconnect_attempts} failed: {e}")
            self._connection_healthy = False

    def is_connection_healthy(self):
        """Check if the OBS connection is currently healthy."""
        return self._connection_healthy

    def ensure_connection(self):
        """Ensure connection is healthy before making requests."""
        if not self._connection_healthy:
            logger.warning("OBS connection is not healthy, attempting immediate reconnect")
            self._attempt_reconnect()
            
        if not self._connection_healthy:
            raise Exception("OBS connection is not available")

    def is_source_visible(self, source_name, scene_name):
        logger.debug(f"Checking visibility for {scene_name}:{source_name}...")
        try:
            self.ensure_connection()
            
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
            self._connection_healthy = False
            return False

    def toggle_obs_source(self,source_name, scene_name, toggle_timespan, only_off=False):

        with obs_lock:
            try:
                self.ensure_connection()
                
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
                self._connection_healthy = False
                self._attempt_reconnect()
                time.sleep(2)
            except Exception as e:
                logger.error(f"Exception with OBS WebSocket: {e}")
                self._connection_healthy = False
                self._attempt_reconnect()
                time.sleep(2)
    
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
                self.ensure_connection()
                
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
                self._connection_healthy = False
                self._attempt_reconnect()
                return False
            except Exception as e:
                logger.error(f"An error occurred while trying to restart media source {input_name}: {e}", exc_info=True)
                # Consider if reconnection is needed here too
                self._connection_healthy = False
                self._attempt_reconnect()
                return False

    def get_media_input_status(self, input_name: str):
        """Get the status of a media input for debugging purposes."""
        logger.info(f"Getting status for media input: {input_name}")
        with obs_lock:
            try:
                self.ensure_connection()
                request = requests.GetMediaInputStatus(inputName=input_name)
                response = self.obs_websocket.call(request)
                logger.info(f"Media input '{input_name}' status: {response.datain}")
                return response.datain
            except Exception as e:
                logger.error(f"Failed to get media input status for {input_name}: {e}")
                self._connection_healthy = False
                return None

    def list_inputs(self):
        """List all inputs for debugging purposes."""
        logger.info("Getting list of all inputs...")
        with obs_lock:
            try:
                self.ensure_connection()
                request = requests.GetInputList()
                response = self.obs_websocket.call(request)
                inputs = response.datain.get('inputs', [])
                logger.info(f"Found {len(inputs)} inputs:")
                for input_item in inputs:
                    logger.info(f"  - {input_item.get('inputName', 'Unknown')} (Type: {input_item.get('inputKind', 'Unknown')})")
                return inputs
            except Exception as e:
                logger.error(f"Failed to get input list: {e}")
                self._connection_healthy = False
                return []

# Create a global instance
# Ensure environment variables are loaded before this point if running as script
# In a FastAPI context, this will run when the module is imported.
obs_socket_manager_instance = OBSSocketManager()