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
    # RTMP hook logging disabled for cleaner logs
    # print(request_obj)

    record_stream = os.getenv('RECORD_STREAM')
    forward_stream = {
        "urls": [
            # f"rtmp://{RTMP_HOST}:{RTMP_PORT}/motherstream/live{param}"
        ]
    }
    do_not_forward_stream = {
        "urls": [
        ]
    }

    if record_stream: 
        forward_stream["urls"].append(f"rtmp://{RTMP_RECORD_HOST}:{RTMP_RECORD_PORT}/live/{stream}") #nginx record path

    if app == 'motherstream':
        # RTMP hook logging disabled for cleaner logs
        # print("Motherstream app. Doing nothing.")
        return JSONResponse(status_code=200, content={"code": 0, "data": do_not_forward_stream})


    if action == 'on_unpublish':
        if not stream:
            logger.warning("on_unpublish called without stream key")
            return JSONResponse(status_code=200, content={"code": 0, "data": do_not_forward_stream})

        should_switch = False
        with queue_lock:
            lead_stream_key = process_manager.stream_queue.lead_streamer()

            if stream == lead_stream_key:
                should_switch = True
                logger.info(f"Lead streamer {stream} disconnected. Switching to next in queue.")
            else:
                logger.info(f"Removing non-lead streamer {stream} from queue")
                process_manager.stream_queue.remove_client_with_stream_key(stream)
                return JSONResponse(status_code=200, content={"code": 0, "data": do_not_forward_stream})

        if should_switch:
            process_manager.switch_stream()
            return JSONResponse(status_code=200, content={"code": 0, "data": do_not_forward_stream})

    elif action == 'on_forward':
        # Atomically check if this stream is the lead
        with queue_lock:
            lead_stream_key = process_manager.stream_queue.lead_streamer()
            if stream and stream == lead_stream_key:
                logger.info(f"FORWARDING: {stream}")
                return JSONResponse(status_code=200, content={"code": 0, "data": forward_stream})
            else:
                logger.info(f"NOT FORWARDING: {stream}")
                return JSONResponse(status_code=200, content={"code": 0, "data": do_not_forward_stream})

    elif action == 'on_publish':
        # Validate user first (no lock needed for this)
        user = ensure_valid_user(stream)
        if not user:
            return JSONResponse(status_code=401, content={"message": "Invalid stream key. you do not have permission to join the queue."})
        
        should_start_stream = False
        response_payload = do_not_forward_stream

        with queue_lock:
            lead_stream_key = process_manager.stream_queue.lead_streamer()

            if not lead_stream_key:
                if process_manager.should_block_streamer(stream):
                    logger.info(f"Blocking {stream} from immediately reclaiming lead slot")
                    return JSONResponse(
                        status_code=401,
                        content={"message": "Please wait before reconnecting.", "code": 0}
                    )

                was_added = process_manager.stream_queue.queue_client_stream_if_not_exists(user)
                if was_added:
                    logger.info(f"Stream {stream} is now the lead streamer")
                    should_start_stream = True
                    response_payload = forward_stream
                    process_manager.clear_last_stream_key()
                else:
                    logger.info(f"Stream {stream} already scheduled as lead")
                    lead_stream_key = process_manager.stream_queue.lead_streamer()
                    if lead_stream_key == stream:
                        response_payload = forward_stream

            elif lead_stream_key == stream:
                logger.info(f"Lead streamer {stream} connected")
                response_payload = forward_stream

            else:
                was_added = process_manager.stream_queue.queue_client_stream_if_not_exists(user)
                if was_added:
                    logger.info(f"Stream {stream} joined queue behind lead {lead_stream_key}")
                else:
                    logger.info(f"Stream {stream} already in queue")

        if should_start_stream:
            logger.info(f"Starting stream for {stream}")
            process_manager.start_stream(user)
            return JSONResponse(status_code=200, content={"code": 0, "data": forward_stream})

        return JSONResponse(status_code=200, content={"code": 0, "data": response_payload})
    elif action == 'on_record_begin':
        pass
    elif action == 'on_record_end':
        pass
    elif action == 'on_ocr':
        pass
    
    return JSONResponse(status_code=200, content={"message": "Publishing allowed", "code": 0})
