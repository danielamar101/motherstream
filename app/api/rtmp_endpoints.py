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
        print("Motherstream app. Doing nothing.")
        return JSONResponse(status_code=200, content={"code": 0, "data": do_not_forward_stream})


    if action == 'on_unpublish':
        if stream and stream == process_manager.get_current_streamer_key():
            process_manager.cleanup_stream()
            
        # kick the next user, allow OBS to reconnect 
        # but save the stream key prior
        print(f"----> NOT FORWARDING: {stream}")
        return JSONResponse(status_code=200, content={"code": 0, "data": do_not_forward_stream})
    elif action == 'on_forward':
        if stream == process_manager.get_current_streamer_key():
            print(f"----> FORWARDING: {stream}")
            return JSONResponse(status_code=200, content={"code": 0, "data": forward_stream})
        else:
            print(f"----> NOT FORWARDING: {stream}")
            return JSONResponse(status_code=200, content={"code": 0, "data": do_not_forward_stream})

    elif action == 'on_publish':
        user = ensure_valid_user(stream)
        if not user:
            return JSONResponse(status_code=401, content={"message": "Invalid stream key. you do not have permission to join the queue."})
        
        stream_queue = process_manager.stream_queue.get_dj_name_queue_list()
        if user.dj_name not in stream_queue and stream != process_manager.get_last_streamer_key():
            process_manager.stream_queue.queue_client_stream(user)
            logger.debug(f"Added {user.dj_name} ({stream}) to the queue")
            current_streamer = process_manager.get_current_streamer_key()
            if not current_streamer:
                print(f"CURRENT STREAMER: {current_streamer}. Will Forward.")
                process_manager.start_stream(user)
                print(f"----> FORWARDING: {user.stream_key}")
                return JSONResponse(status_code=200, content={"code": 0, "data": forward_stream})
        print(f"----> NOT FORWARDING: {stream}")
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
