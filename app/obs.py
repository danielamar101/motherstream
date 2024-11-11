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
    stream_queue = None
    def __init__(self, stream_queue):

        self.stream_queue = stream_queue

        self.OBS_HOST = os.environ.get("OBS_HOST")
        self.OBS_PORT = os.environ.get("OBS_PORT")
        self.OBS_PASSWORD = os.environ.get("OBS_PASSWORD")

        self.obs_websocket = obsws(self.OBS_HOST, self.OBS_PORT, self.OBS_PASSWORD)
        logger.debug("Connecting to websocket...")
        self.__connect()

        self.start_loading_message_thread()
        self.toggle_obs_source(source_name="Queue", scene_name="MOTHERSTREAM", toggle_timespan=1)
    
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
                    time.sleep(toggle_timespan)
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

    def flash_loading_message(self):
       
        while True:
            if self.stream_queue.get_dj_name_queue_list():
                logger.debug("TOGGLING NEXT STREAM IS LOADING MSG...")
                self.toggle_loading_message_source(only_off=False)
            

    def start_loading_message_thread(self):
        print("Starting loading message toggle thread..")
        threading.Thread(target=self.flash_loading_message, daemon=True).start()

    def toggle_loading_message_source(self, only_off=False):
        source_name = 'LOADING'
        scene_name = 'MOTHERSTREAM'
        try:
            self.toggle_obs_source(source_name=source_name, scene_name=scene_name, toggle_timespan=1.5, only_off=only_off)
        except Exception as e:
            logger.error(f"Error toggling off {scene_name}:{source_name}. {e}")

    def toggle_gstreamer_source(self, only_off=False):
        source_name = 'GMOTHERSTREAM'
        scene_name = 'MOTHERSTREAM'
        try:
            self.toggle_obs_source(source_name=source_name, scene_name=scene_name, toggle_timespan=1, only_off=only_off)
        except Exception as e:
            logger.error(f"Error toggling off {scene_name}:{source_name}. {e}")
    
    def toggle_timer_source(self, only_off=False):
        source_name = 'TIMER1'
        time_remaining_text = 'TIME REMAINING'
        scene_name = 'MOTHERSTREAM'

        try:
            self.toggle_obs_source(source_name=source_name, scene_name=scene_name, toggle_timespan=1, only_off=only_off)
            self.toggle_obs_source(source_name=time_remaining_text, scene_name=scene_name, toggle_timespan=1, only_off=only_off)
        except Exception as e:
            logger.error(f"Error toggling off {scene_name}:{source_name}. {e}")