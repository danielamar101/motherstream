from fastapi.responses import JSONResponse
from fastapi import Form, APIRouter, Body

from main import process_manager
from ..lock_manager import lock as queue_lock
from ..db.validation import ensure_valid_user

import logging
import os

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

    record_stream = os.getenv('RECORD_STREAM')
    forward_stream = {
        "urls": [
            f"rtmp://127.0.0.1:1935/motherstream/live{param}"
        ]
    }
    do_not_forward_stream = {
        "urls": [
        ]
    }
    if record_stream: 
        forward_stream["urls"].append(f"rtmp://127.0.0.1:1936/live/{stream}") #nginx record path

    if app == 'motherstream':
        print("Motherstream app. Doing nothing.")
        return JSONResponse(status_code=200, content={"code": 0, "data": do_not_forward_stream})


    if action == 'on_unpublish':
        if process_manager.get_last_streamer_key() == stream:
            if process_manager.get_is_blocking_last_streamer():
                return JSONResponse(status_code=401, content={"code": 0, "data": do_not_forward_stream})
        else:
            process_manager.delete_last_streamer_key()
        current_stream_key = process_manager.get_current_streamer_key()
        if stream and stream == current_stream_key:
            process_manager.cleanup_stream()
            process_manager.toggle_is_switching()
            return JSONResponse(status_code=200, content={"code": 0, "data": do_not_forward_stream})
        elif stream and stream != current_stream_key and process_manager.get_is_switching():
            process_manager.toggle_is_switching()
            return JSONResponse(status_code=200, content={"code": 0, "data": do_not_forward_stream})
        elif stream and stream != current_stream_key:
            return JSONResponse(status_code=200, content={"code": 0, "data": do_not_forward_stream})
        # TODO: Perhaps add logic to fix erroneous state
        else:
            print("Somehow got in an unexpected spot in on_unpublish... investigate...")
            print(f'-> on_unpublish Current Stream: {current_stream_key}, State: {process_manager.stream_queue.get_stream_key_queue_list()} Is_switching: {process_manager.get_is_switching()}')
            return JSONResponse(status_code=401, content={"code": 0, "data": do_not_forward_stream})
    elif action == 'on_forward':
        if process_manager.get_last_streamer_key() == stream:
            if process_manager.get_is_blocking_last_streamer():
                return JSONResponse(status_code=401, content={"code": 0, "data": do_not_forward_stream})
        else:
            process_manager.delete_last_streamer_key()
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
        if process_manager.get_last_streamer_key() == stream:
            if process_manager.get_is_blocking_last_streamer():
                return JSONResponse(status_code=401, content={"code": 0, "data": do_not_forward_stream})
        else:
            process_manager.delete_last_streamer_key()
        current_stream_key = process_manager.get_current_streamer_key()
        if not current_stream_key: #If there is no one else in stream queue, just start stream immediately
            process_manager.stream_queue.queue_client_stream(user)
            process_manager.start_stream(user)
            return JSONResponse(status_code=200, content={"code": 0, "data": forward_stream})
        if current_stream_key and current_stream_key == stream:
            return JSONResponse(status_code=200, content={"code": 0, "data": forward_stream})
        if current_stream_key and current_stream_key != stream:
            process_manager.stream_queue.queue_client_stream(user)
            return JSONResponse(status_code=200, content={"code": 0, "data": do_not_forward_stream})

        print("Somehow got into an erroneous state in on_publish hook. Investigate...")
        return JSONResponse(status_code=404, content={"code": 0, "data": do_not_forward_stream})
    elif action == 'on_record_begin':
        pass
    elif action == 'on_record_end':
        pass
    elif action == 'on_ocr':
        pass
    
    return JSONResponse(status_code=200, content={"message": "Publishing allowed", "code": 0})
