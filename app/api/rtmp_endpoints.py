from fastapi.responses import JSONResponse
from fastapi import Form, APIRouter, Body

from main import process_manager
from ..lock_manager import lock as queue_lock
from ..db.validation import ensure_valid_user

import logging

logger = logging.getLogger(__name__)

multipart_logger = logging.getLogger('multipart.multipart')
multipart_logger.setLevel(logging.CRITICAL + 1)

rtmp_blueprint = APIRouter()

# RTMP handle all callback
@rtmp_blueprint.post("/")
async def on_publish(
    request_id: str| None = Body(None),
    action: str | None = Body(None),
    opaque: str | None = Body(None),
    vhost: str | None = Body(None),
    app: str | None = Body(None),
    stream: str | None = Body(None),
    addr: str | None = Body(None),
    param: str | None = Body(None),
):
    request_obj = {
        "request_id": request_id,
        "action": action,
        "opaque": opaque,
        "vhost": vhost,
        "app": app,
        "stream": stream,
        "addr": addr,
        "param": param
    }
    print(request_obj)

    forward_stream = {
        "urls": [
            f"rtmp://127.0.0.1:1935/motherstream/live{param}"
        ]
    }
    do_not_forward_stream = {
        "urls": [
        ]
    }
    if app == 'motherstream':
        return JSONResponse(status_code=200, content={"code": 0, "data": do_not_forward_stream})


    if action == 'on_unpublish':
        if stream and stream == process_manager.current_stream_key:
            process_manager.stream_queue.unqueue_client_stream()
            process_manager.stop_current_stream()
            logger.debug(f"Removed {stream} from the queue")
        # kick the next user, allow OBS to reconnect 
        # but save the stream key prior
        return JSONResponse(status_code=200, content={"code": 0, "data": do_not_forward_stream})
    elif action == 'on_forward':
        return JSONResponse(status_code=200, content={"code": 0, "data": forward_stream})
    elif action == 'on_publish':
        stream_queue = process_manager.stream_queue.get_dj_name_queue_list()
        user = ensure_valid_user(stream)
        if not user:
            return JSONResponse(status_code=401, content={"message": "Invalid stream key. you do not have permission to join the queue."})
        
        if user.dj_name not in stream_queue and stream != process_manager.stream_queue.last_stream_key:
            process_manager.stream_queue.queue_client_stream(user)
            logger.debug(f"Added {user.dj_name} ({stream}) to the queue")
            next_streamer = process_manager.stream_queue.next_streamer()
            if next_streamer and next_streamer.dj_name == user.dj_name or not next_streamer: 
                process_manager.start_stream(user)
                return JSONResponse(status_code=200, content={"code": 0, "data": forward_stream})
            else:
                return JSONResponse(status_code=200, content={"code": 0, "data": do_not_forward_stream})
        return JSONResponse(status_code=200, content={"code": 0, "data": do_not_forward_stream})
    elif action == 'on_record_begin':
        pass
    elif action == 'on_record_end':
        pass
    elif action == 'on_ocr':
        pass
    
    # logger.info(f"[on_publish] Stream {name} started by client {addr} in app {app}")
    # if app != 'live':
    #     # Will allow streaming but not added to queuing mechanism. TODO: Block this for security purposes
    #     return JSONResponse(status_code=200, content={"message": f"Not handling this app: {app}"})
    

    return JSONResponse(status_code=200, content={"message": "Publishing allowed", "code": 0})
# RTMP on_publish callback
@rtmp_blueprint.post("/on_publish")
async def on_publish(
    request_id: str = Form(...),
    action: str = Form(...),
    opaque: str = Form(...),
    vhost: str = Form(...),
    app: str = Form(...),
    stream: str = Form(...),
    addr: str = Form(...),
    params: str = Form(...)
):
    request_obj = {
        "request_id": request_id,
        "action": action,
        "opaque": opaque,
        "vhost": vhost,
        "app": app,
        "stream": stream,
        "addr": addr,
        "params": params
    }
    print(request_obj)
    
    # logger.info(f"[on_publish] Stream {name} started by client {addr} in app {app}")
    # if app != 'live':
    #     # Will allow streaming but not added to queuing mechanism. TODO: Block this for security purposes
    #     return JSONResponse(status_code=200, content={"message": f"Not handling this app: {app}"})
    
    # with queue_lock:
    #     stream_queue = process_manager.stream_queue.get_dj_name_queue_list()
    #     user = ensure_valid_user(name)
    #     if not user:
    #         return JSONResponse(status_code=401, content={"message": "Invalid stream key. you do not have permission to join the queue."})
        
    #     if user.dj_name not in stream_queue:
    #         process_manager.stream_queue.queue_client_stream(user)
    #         logger.debug(f"Added {name} to the queue")
    return JSONResponse(status_code=200, content={"message": "Publishing allowed", "code": 0})

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
    # logger.debug(f"[on_publish_done] Stream {name} stopped by client in app {app}")
    # with queue_lock:
    #     if name and name == process_manager.current_stream_key:
    #         process_manager.stream_queue.unqueue_client_stream()
    #         process_manager.stream_queue.stop_current_stream()
    #         logger.debug(f"Removed {name} from the queue")

    return JSONResponse(status_code=200, content={"message": "Publish done", "code": 0})

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
    logger.debug(f"[on_done] {name} client disconnected from {app}")
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
    # NOTE: the call var to distinguish between play/publish 

    logger.debug(payload)
    logger.debug(f"[on_connect] Client connected to {app} from {addr}")
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

    logger.debug(payload)

    logger.debug(f"[on_play] Client is playing app: {app} from {addr}")
    return JSONResponse(status_code=200, content={"message": "Play allowed"})
