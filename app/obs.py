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


class OBSOperationalError(Exception):
    """Exception for OBS operational errors (not connection issues)"""
    pass


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

        # Connection health monitoring
        self._connection_healthy = False
        self._last_health_check = 0
        self._health_check_interval = 30  # Check every 30 seconds
        self._reconnect_attempts = 0
        self._max_reconnect_attempts = 5
        self._reconnect_delay = 5  # Start with 5 second delay
        self._last_reconnect_attempt = 0  # Timestamp of last reconnect attempt for throttling
        
        # Streaming monitoring and auto-start
        self._streaming_monitor_enabled = False  # Disabled by default
        self._is_streaming = False
        self._last_streaming_check = 0
        self._streaming_check_interval = 15  # Check streaming status every 15 seconds
        self._auto_start_attempts = 0
        self._max_auto_start_attempts = 3
        self._auto_start_delay = 10  # Wait 10 seconds between auto-start attempts
        self._last_auto_start_attempt = 0  # Timestamp of last auto-start attempt for throttling
        
        # Scene item caching to reduce redundant OBS calls during burst operations
        self._scene_cache = {}  # Cache scene item lists by scene name
        self._scene_cache_ttl = 5  # Cache for 5 seconds (balance between performance and freshness)
        self._scene_cache_time = {}  # Track when each scene was cached
        
        # Start health monitoring thread
        self._start_health_monitor()

        # TODO: Evaluate if we want this websocket usage - This used stream_queue
        # self.start_loading_message_thread()

    
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

        current_time = time.time()
        
        # Check if enough time has passed since last attempt (throttling for retry attempts)
        if self._auto_start_attempts > 0:
            time_since_last_attempt = current_time - self._last_auto_start_attempt
            if time_since_last_attempt < self._auto_start_delay:
                time_remaining = self._auto_start_delay - time_since_last_attempt
                logger.debug(f"Too soon to retry auto-start. Waiting {time_remaining:.1f}s more")
                return

        self._auto_start_attempts += 1
        self._last_auto_start_attempt = current_time
        logger.info(f"Attempting to auto-start OBS streaming (attempt {self._auto_start_attempts}/{self._max_auto_start_attempts})")
        
        try:
            with obs_lock:
                # Removed time.sleep() to avoid blocking while holding obs_lock
                # Throttling is now handled by timestamp checking above
                
                # Start streaming
                start_stream_request = requests.StartStream()
                response = self.obs_websocket.call(start_stream_request)
                
                logger.info(f"Auto-start streaming command sent to OBS")
                logger.debug(f"Start stream response: {response.datain if hasattr(response, 'datain') else 'No response data'}")
                
                # REMOVED: Immediate verification to reduce OBS calls
                # Assume success - the next health check cycle will verify
                self._is_streaming = True
                self._auto_start_attempts = 0  # Reset on command sent
                logger.info("Auto-start command completed - health monitor will verify status")
                        
        except Exception as e:
            logger.error(f"Failed to auto-start streaming (attempt {self._auto_start_attempts}): {e}")
            self._is_streaming = False

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
                
                # REMOVED: Immediate verification to reduce OBS calls
                # Let the health monitor check verify streaming status on next cycle
                # This reduces immediate OBS calls and prevents overwhelming OBS
                
                # Assume success - health monitor will detect if it actually failed
                self._is_streaming = True
                return True
                
        except Exception as e:
            logger.error(f"Failed to manually start streaming: {e}")
            self._is_streaming = False
            return False

    def _attempt_reconnect(self):
        """Attempt to reconnect to OBS with exponential backoff."""
        if self._reconnect_attempts >= self._max_reconnect_attempts:
            logger.error(f"Max reconnection attempts ({self._max_reconnect_attempts}) reached. Giving up.")
            return

        # Calculate required wait time using exponential backoff
        wait_time = min(self._reconnect_delay * (2 ** self._reconnect_attempts), 60)
        current_time = time.time()
        
        # Check if enough time has passed since last reconnection attempt (throttling)
        time_since_last_attempt = current_time - self._last_reconnect_attempt
        if time_since_last_attempt < wait_time:
            time_remaining = wait_time - time_since_last_attempt
            logger.debug(f"Too soon to reconnect. Waiting {time_remaining:.1f}s more")
            return

        self._reconnect_attempts += 1
        self._last_reconnect_attempt = current_time
        logger.info(f"Attempting to reconnect to OBS (attempt {self._reconnect_attempts}/{self._max_reconnect_attempts})")
        
        try:
            # Removed time.sleep() to avoid blocking the health monitor loop
            # Throttling is now handled by timestamp checking above
            
            # Create new websocket instance and connect
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

    def _get_scene_item_list_cached(self, scene_name):
        """Get scene item list with caching to reduce OBS calls during burst operations."""
        current_time = time.time()
        
        # Check if we have a valid cached entry
        if scene_name in self._scene_cache:
            cache_age = current_time - self._scene_cache_time.get(scene_name, 0)
            if cache_age < self._scene_cache_ttl:
                logger.debug(f"Using cached scene item list for '{scene_name}' (age: {cache_age:.1f}s)")
                return self._scene_cache[scene_name]
        
        # Cache miss or expired - fetch fresh data
        logger.debug(f"Fetching fresh scene item list for '{scene_name}'")
        scene_item_list = self.obs_websocket.call(requests.GetSceneItemList(sceneName=scene_name))
        
        # Update cache
        self._scene_cache[scene_name] = scene_item_list
        self._scene_cache_time[scene_name] = current_time
        
        return scene_item_list
    
    def _invalidate_scene_cache(self, scene_name):
        """Invalidate cache for a specific scene after state changes."""
        if scene_name in self._scene_cache:
            logger.debug(f"Invalidating cache for scene '{scene_name}'")
            del self._scene_cache[scene_name]
            del self._scene_cache_time[scene_name]

    def is_source_visible(self, source_name, scene_name):
        logger.debug(f"Checking visibility for {scene_name}:{source_name}...")
        try:
            self.ensure_connection()
            
            # 1. Get scene item list for the scene (with caching)
            scene_item_list = self._get_scene_item_list_cached(scene_name)

            # 2. Get sceneItemId for the specified source
            scene_id = None
            for item in scene_item_list.datain['sceneItems']:
                if item['sourceName'] == source_name:
                    scene_id = item['sceneItemId']
                    break
            if not scene_id:
                raise OBSOperationalError(f"Cannot find source '{source_name}' in scene '{scene_name}'.")

            # 3. Get source properties to check if it's enabled (visible)
            scene_item_properties = self.obs_websocket.call(requests.GetSceneItemEnabled(sceneName=scene_name, sceneItemId=scene_id))

            is_visible = scene_item_properties.datain['sceneItemEnabled']
            
            logger.debug(f"Source '{source_name}' visibility in '{scene_name}': {'Visible' if is_visible else 'Hidden'}")
            return is_visible
        except OBSOperationalError as e:
            # Source doesn't exist - this is not a connection issue
            logger.error(f"OBS operational error while checking source visibility: {e}")
            return False
        except WebSocketConnectionClosedException as e:
            # Connection error - mark unhealthy
            logger.error(f"WebSocket connection closed while checking source visibility: {e}")
            self._connection_healthy = False
            return False
        except Exception as e:
            # Other unexpected errors
            logger.error(f"Unexpected exception while checking source visibility: {e}")
            self._connection_healthy = False
            return False

    def toggle_obs_source(self,source_name, scene_name, only_off=False):

        with obs_lock:
            try:
                self.ensure_connection()
                
                # 1. Get scene item list from scene (ONLY ONCE - optimized with caching to prevent duplicate calls)
                scene_item_list = self._get_scene_item_list_cached(scene_name)
        
                # 2. Get scene_id AND current visibility state from the scene item list
                scene_id = None
                is_currently_visible = False
                for item in scene_item_list.datain['sceneItems']:
                    if item['sourceName'] == source_name:
                        scene_id = item['sceneItemId']
                        # Extract visibility directly from scene item data (avoids extra OBS call)
                        is_currently_visible = item.get('sceneItemEnabled', False)
                        break
                        
                if not scene_id:
                    raise OBSOperationalError(f"Error getting source id. Cannot find source '{source_name}' in scene '{scene_name}'.")

                # 3. Toggle the source based on the visibility we already retrieved
                if is_currently_visible:
                    logger.debug(f"TOGGLING OBS {scene_name}:{source_name} OFF")
                    self.obs_websocket.call(requests.SetSceneItemEnabled(sceneName=scene_name, sceneItemId=scene_id, sceneItemEnabled=False))

                    
                if not only_off:
                    logger.debug(f"TOGGLING OBS {scene_name}:{source_name} ON")
                    self.obs_websocket.call(requests.SetSceneItemEnabled(sceneName=scene_name, sceneItemId=scene_id, sceneItemEnabled=True))
                    logger.info("...done toggling.")
                
                # Invalidate cache after changing source state to ensure next call gets fresh data
                self._invalidate_scene_cache(scene_name)
                    
            except OBSOperationalError as e:
                # Operational errors (source not found, etc) - don't reconnect
                logger.error(f"OBS operational error: {e}")
                logger.error("This is not a connection issue - skipping reconnection")
            except WebSocketConnectionClosedException as e:
                # Connection closed - reconnect
                logger.error("WebSocket is closed. Is the OBS app open?")
                logger.error("Attempting to restart connection to the websocket...")
                self._connection_healthy = False
                self._attempt_reconnect()
                time.sleep(2)
            except Exception as e:
                # Other unexpected errors - log and reconnect as safety measure
                logger.error(f"Unexpected exception with OBS WebSocket: {e}")
                logger.warning("Marking connection as unhealthy and attempting reconnection")
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