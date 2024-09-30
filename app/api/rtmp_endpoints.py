from fastapi.responses import JSONResponse
from fastapi import Form, APIRouter

from ..lock_manager import lock as queue_lock

from main import process_manager
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
        stream_queue = process_manager.stream_queue.get_stream_queue_as_list()

        if name not in stream_queue:
            process_manager.stream_queue.queue_client_stream(name)
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
            process_manager.stream_queue.unqueue_client_stream()
            process_manager.stream_queue.stop_current_stream()
            print(f"Removed {name} from the queue")

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