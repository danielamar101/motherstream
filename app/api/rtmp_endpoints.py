from fastapi.responses import JSONResponse
from fastapi import Form, APIRouter

from ..lock_manager import lock as queue_lock
from ..queue import StreamQueue
from .process_manager import ProcessManager

stream_queue = StreamQueue()
process_manager = ProcessManager()
rtmp_blueprint = APIRouter()

# RTMP on_publish callback
@rtmp_blueprint.post("/on_publish")
async def on_publish(
    app: str = Form(...),
    name: str = Form(...),
    flashver: str = Form(...),
    swfurl: str = Form(...),
    tcurl: str = Form(...),
    pageurl: str = Form(...),
    addr: str = Form(...),
    call: str = Form(...)
):
    print(f"[on_publish] Stream {name} started by client {addr} in app {app}")
    if app != 'live':
        # Will allow streaming but not added to queuing mechanism. TODO: Block this for security purposes
        return JSONResponse(status_code=200, content={"message": f"Not handling this app: {app}"})
    
    with queue_lock:
        actual_stream_queue = stream_queue.get_stream_queue()

        if name not in actual_stream_queue:
            stream_queue.queue_client_stream(name)
            print(f"Added {name} to the queue")
    return JSONResponse(status_code=200, content={"message": "Publishing allowed"})

# RTMP on_publish_done callback
@rtmp_blueprint.post("/on_publish_done")
async def on_publish_done(
    app: str = Form(...),
    name: str = Form(None),
    flashver: str = Form(...),
    swfurl: str = Form(...),
    tcurl: str = Form(...),
    pageurl: str = Form(...),
    addr: str = Form(...),
    call: str = Form(...)
):
    print(f"[on_publish_done] Stream {name} stopped by client in app {app}")
    with queue_lock:
        if name and name == process_manager.current_stream_key:
            stream_queue.unqueue_client_stream()
            stream_queue.stop_current_stream()
            print(f"Removed {name} from the queue")

    # SOURCE_NAME = 'MOTHERSTREAM'
    # SCENE_NAME = 'MOTHERSTREAM 1'
    # ws = obsws(OBS_HOST, OBS_PORT, OBS_PASSWORD)
    # try:
    #     ws.connect()

    #     # 1. Get scene item list for MOTHERSTREAM 1
    #     scene_item_list = ws.call(requests.GetSceneItemList(sceneName=SCENE_NAME))
        
    #     #2. Get sceneID from scene item dict
    #     vlc_media_scene_id = None
    #     for item in scene_item_list.datain['sceneItems']:
    #         if item['sourceName'] == SOURCE_NAME:
    #             vlc_media_scene_id = item['sceneItemId']
    #             break;
    #     if not vlc_media_scene_id:
    #         raise Exception("Error getting vlc media source id. Cannot find proper source.")

    #      #3. Hide the source in the current scene
    #     ws.call(requests.SetSceneItemEnabled(sceneName=SCENE_NAME, sceneItemId=vlc_media_scene_id, sceneItemEnabled=False))
    #     time.sleep(10)
    #     ws.call(requests.SetSceneItemEnabled(sceneName=SCENE_NAME,  sceneItemId=vlc_media_scene_id, sceneItemEnabled=True))
    #     print(f"Successfully turned on/off the source: {SOURCE_NAME}")
    # except Exception as e:
    #     print(f"Exception with OBS WebSocket: {e}")
    # finally:
    #     ws.disconnect()

    return JSONResponse(status_code=200, content={"message": "Publish done"})

# RTMP on_done callback
@rtmp_blueprint.post("/on_done")
async def on_done(
    app: str = Form(...),
    name: str = Form(None),
    flashver: str = Form(...),
    swfurl: str = Form(...),
    tcurl: str = Form(...),
    pageurl: str = Form(...),
    addr: str = Form(...),
    call: str = Form(...)
):
    if name:
        print(name)
    print(f"[on_done] Client disconnected from {app}")
    return JSONResponse(status_code=200, content={"message": "Disconnected"})


# RTMP on_connect callback
@rtmp_blueprint.post("/on_connect")
async def on_connect(
    app: str = Form(...),
    flashver: str = Form(...),
    swfurl: str = Form(...),
    tcurl: str = Form(...),
    pageurl: str = Form(...),
    addr: str = Form(...),
    epoch: str = Form(...),
    call: str = Form(...)
):
    payload = {
    "app": app,
    "flashver": flashver,
    "swfurl": swfurl,
    "tcurl": tcurl,
    "pageurl": pageurl,
    "addr": addr,
    "epoch": epoch,
    "call": call
}
    #TODO: Implement auth logic here.
    # NOTE: the call var to distinguish between play/publish 
    # 
    # Specifications:
    # 1. Authenticate stream key/IP address
	# 1a. Check if DJ is registered in DB
	# 1b. Check if IP address matches expected
	# 1c. Obtain the DJ data object for later


    print(payload)
    print(f"[on_connect] Client connected to {app} from {addr}")
    return JSONResponse(status_code=200, content={"message": "Connection allowed"})


@rtmp_blueprint.post("/on_play")
async def on_connect(
    app: str = Form(...),
    flashver: str = Form(...),
    swfurl: str = Form(...),
    tcurl: str = Form(...),
    pageurl: str = Form(...),
    addr: str = Form(...),
    call: str = Form(...)
):
    payload = {
    "app": app,
    "flashver": flashver,
    "swfurl": swfurl,
    "tcurl": tcurl,
    "pageurl": pageurl,
    "addr": addr,
    "call": call
    }

    print(payload)

    print(f"[on_play] Client is playing app: {app} from {addr}")
    return JSONResponse(status_code=200, content={"message": "Play allowed"})
