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

# RTMP configuration from environment
RTMP_HOST = os.getenv("RTMP_HOST", "127.0.0.1")
RTMP_PORT = os.getenv("RTMP_PORT", "1935")

RTMP_RECORD_HOST = os.getenv("RTMP_RECORD_HOST", "127.0.0.1")
RTMP_RECORD_PORT = os.getenv("RTMP_RECORD_PORT", "1936")

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
            f"rtmp://{RTMP_HOST}:{RTMP_PORT}/motherstream/live{param}"
        ]
    }
    do_not_forward_stream = {
        "urls": [
        ]
    }
    if record_stream: 
        forward_stream["urls"].append(f"rtmp://{RTMP_RECORD_HOST}:{RTMP_RECORD_PORT}/live/{stream}") #nginx record path

    if app == 'motherstream':
        print("Motherstream app. Doing nothing.")
        return JSONResponse(status_code=200, content={"code": 0, "data": do_not_forward_stream})


    if action == 'on_unpublish':
        PRIORITY = process_manager.get_priority_key()
        lead_stream_key = process_manager.stream_queue.lead_streamer()

        if stream and stream != lead_stream_key:
            # streamer in the queue but not lead left, just update state
            print("Removing streamer from queue")
            process_manager.stream_queue.remove_client_with_stream_key(stream)
            return JSONResponse(status_code=200, content={"code": 0, "data": do_not_forward_stream})
        
        if PRIORITY and PRIORITY == stream:
            process_manager.set_priority_key(None)
            return JSONResponse(status_code=200, content={"code": 0, "data": do_not_forward_stream})
        else:
            if stream and stream == lead_stream_key:
                process_manager.switch_stream()
                return JSONResponse(status_code=200, content={"code": 0, "data": do_not_forward_stream})
            else: # remove the correct streamer from the queue
                print("Removing streamer from queue")
                process_manager.stream_queue.remove_client_with_stream_key(stream)
                print("Done")
                return JSONResponse(status_code=200, content={"code": 0, "data": do_not_forward_stream})

    elif action == 'on_forward':
        lead_stream_key = process_manager.stream_queue.lead_streamer()
        if stream and stream == lead_stream_key:
            print(f"----> FORWARDING: {stream}")
            return JSONResponse(status_code=200, content={"code": 0, "data": forward_stream})
        else:
            print(f"----> NOT FORWARDING: {stream}")
            return JSONResponse(status_code=200, content={"code": 0, "data": do_not_forward_stream})

    elif action == 'on_publish':
        user = ensure_valid_user(stream)
        if not user:
            return JSONResponse(status_code=401, content={"message": "Invalid stream key. you do not have permission to join the queue."})
        
        lead_stream_key = process_manager.stream_queue.lead_streamer() # get stream key in the front of the queue
        last_stream_key = process_manager.get_last_streamer_key()
        BLOCKING = process_manager.get_is_blocking_last_streamer()
        print(f"BLOCKING: {BLOCKING} LEAD_STREAM_KEY: {lead_stream_key} LAST_STREAM_KEY: {last_stream_key}")

        if not lead_stream_key: #If there is no one else in stream queue, just start stream immediately
            if last_stream_key:
                if BLOCKING and last_stream_key == stream:
                    
                    return JSONResponse(status_code=401, content={"code": 0, "data": do_not_forward_stream})
                else:
                    process_manager.delete_last_streamer_key()
                    if stream not in process_manager.stream_queue.get_stream_key_queue_list():
                        process_manager.stream_queue.queue_client_stream(user)
                        process_manager.start_stream(user)
                        return JSONResponse(status_code=200, content={"code": 0, "data": forward_stream})
                    else:
                        print("Streamer already in queue")
                        return JSONResponse(status_code=200, content={"code": 0, "data": do_not_forward_stream})
            else:
                if stream not in process_manager.stream_queue.get_stream_key_queue_list():
                    process_manager.stream_queue.queue_client_stream(user)
                    process_manager.start_stream(user)
                    return JSONResponse(status_code=200, content={"code": 0, "data": forward_stream})
                else:
                    print("Streamer already in queue")
                    return JSONResponse(status_code=200, content={"code": 0, "data": do_not_forward_stream})
            
        if lead_stream_key and lead_stream_key == stream:
            return JSONResponse(status_code=200, content={"code": 0, "data": forward_stream})

        if lead_stream_key and lead_stream_key != stream: # Gotta wait in line
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
