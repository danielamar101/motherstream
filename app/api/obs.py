import os
import time
import logging
from obswebsocket import obsws, requests

logger = logging.getLogger()

class OBSSocketManager():

    obs_websocket = None

    def __init__(self):

        OBS_HOST = os.environ.get("OBS_HOST")
        OBS_PORT = os.environ.get("OBS_PORT")
        OBS_PASSWORD = os.environ.get("OBS_PASSWORD")

        self.obs_websocket = obsws(OBS_HOST, OBS_PORT, OBS_PASSWORD)
    
    def __connect(self):
        try:
            self.obs_websocket.connect()
        except Exception as e:
            logger.exception(e)

    def __disconnect(self):
        try:
            self.obs_websocket.disconnect()
        except Exception as e:
            logger.exception(e)

    def ob

    def toggle_obs_source(self,only_off=False, source_name=None, scene_name=None):

        SOURCE_NAME = source_name
        SCENE_NAME = scene_name
        
        logger.info("Toggling VLC source.")
        try:
            logger.debug("Connecting to websocket...")
            self.__connect()

            # 1. Get scene item list for MOTHERSTREAM 1
            scene_item_list = self.obs_websocket.call(requests.GetSceneItemList(sceneName=SCENE_NAME))

            #2. Get sceneID from scene item dict
            gstreamer_pipeline_scene_id = None
            for item in scene_item_list.datain['sceneItems']:
                if item['sourceName'] == SOURCE_NAME:
                    gstreamer_pipeline_scene_id = item['sceneItemId']
                    break;
            if not gstreamer_pipeline_scene_id:
                raise Exception("Error getting vlc media source id. Cannot find proper source.")

            #3. Hide/uuhide the source in the current scene
            logger.info("Toggling source...")
            self.obs_websocket.call(requests.SetSceneItemEnabled(sceneName=SCENE_NAME, sceneItemId=gstreamer_pipeline_scene_id, sceneItemEnabled=False))
            
            if not only_off:
                time.sleep(1)
                self.obs_websocket.call(requests.SetSceneItemEnabled(sceneName=SCENE_NAME, sceneItemId=gstreamer_pipeline_scene_id, sceneItemEnabled=True))
            logger.info("...done toggling.")
        except Exception as e:
            logger.info(f"Exception with OBS WebSocket: {e}")
            raise e
        finally:
            self.__disconnect()


