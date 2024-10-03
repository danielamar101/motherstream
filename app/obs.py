import os
import time
import logging
from obswebsocket import obsws, requests
import threading

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

        OBS_HOST = os.environ.get("OBS_HOST")
        OBS_PORT = os.environ.get("OBS_PORT")
        OBS_PASSWORD = os.environ.get("OBS_PASSWORD")

        self.obs_websocket = obsws(OBS_HOST, OBS_PORT, OBS_PASSWORD)
        logger.debug("Connecting to websocket...")
        self.__connect()

        loading_msg_source_name = "LOADING"
        loading_msg_scene_name = "MOTHERSTREAM"

        self.toggle_loading_message(source_name=loading_msg_source_name,scene_name=loading_msg_scene_name,toggle_timespan=1.5)
        self.toggle_obs_source(source_name="Queue", scene_name="MOTHERSTREAM", toggle_timespan=1)
    
    def __connect(self):
        try:
            self.obs_websocket.connect()
            logger.info("Connected to obs websocket.")
        except Exception as e:
            logger.exception(e)

    def disconnect(self):
        try:
            self.obs_websocket.disconnect()
            logger.info("Disconnected from obs websocket.")
        except Exception as e:
            logger.exception(e)

    def toggle_obs_source(self,source_name, scene_name, toggle_timespan, only_off=False):
        logger.debug(f"TOGGLING OBS {scene_name}:{source_name}...")
        with obs_lock:
            try:
                # 1. Get scene item list for MOTHERSTREAM 1
                scene_item_list = self.obs_websocket.call(requests.GetSceneItemList(sceneName=scene_name))
        
                #2. Get sceneID from scene item dict
                scene_id = None
                for item in scene_item_list.datain['sceneItems']:
                    if item['sourceName'] == source_name:
                        scene_id = item['sceneItemId']
                        break;
                if not scene_id:
                    raise Exception("Error getting source id. Cannot find proper source.")

                #3. Hide/uuhide the source in the current scene
                logger.info("Toggling source...")
                time.sleep(toggle_timespan)
                self.obs_websocket.call(requests.SetSceneItemEnabled(sceneName=scene_name, sceneItemId=scene_id, sceneItemEnabled=False))
                
                if not only_off:
                    time.sleep(toggle_timespan)
                    self.obs_websocket.call(requests.SetSceneItemEnabled(sceneName=scene_name, sceneItemId=scene_id, sceneItemEnabled=True))
                logger.info("...done toggling.")
            except Exception as e:
                logger.info(f"Exception with OBS WebSocket: {e}")
                print(e)
                time.sleep(toggle_timespan)

    def flash_loading_message(self,source_name,scene_name, toggle_timespan):
        while True:
            logger.debug("TOGGLING NEXT STREAM IS LOADING MSG...")

            only_off = False
            if not self.stream_queue.get_dj_name_queue_list():
                only_off = True

            self.toggle_obs_source(source_name=source_name,scene_name=scene_name,toggle_timespan=toggle_timespan, only_off=only_off)

    def toggle_loading_message(self,source_name, scene_name, toggle_timespan):
        print("Starting loading message toggle thread..")
        threading.Thread(target=self.flash_loading_message, args=(source_name, scene_name,toggle_timespan), daemon=True).start()
