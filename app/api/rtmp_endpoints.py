from fastapi.responses import JSONResponse
from fastapi import Form, APIRouter, Body
from fastapi.background import BackgroundTasks

from main import process_manager
from ..lock_manager import lock as queue_lock
from ..db.validation import ensure_valid_user

import logging
import os
import asyncio

logger = logging.getLogger(__name__)

multipart_logger = logging.getLogger('multipart.multipart')
multipart_logger.setLevel(logging.CRITICAL + 1)

rtmp_blueprint = APIRouter()

async def handle_stream_operations(stream: str, user: dict, action: str):
    """Handle stream operations asynchronously in the background"""
    try:
        if action == 'on_publish':
            lead_stream_key = process_manager.stream_queue.lead_streamer()
            last_stream_key = process_manager.get_last_streamer_key()
            BLOCKING = process_manager.get_is_blocking_last_streamer()

            if not lead_stream_key:
                if last_stream_key:
                    if BLOCKING and last_stream_key == stream:
                        return
                    else:
                        process_manager.delete_last_streamer_key()
                        process_manager.stream_queue.queue_client_stream(user)
                        process_manager.start_stream(user)
                else:
                    process_manager.stream_queue.queue_client_stream(user)
                    process_manager.start_stream(user)
            elif lead_stream_key and lead_stream_key == stream:
                return
            elif lead_stream_key and lead_stream_key != stream:
                process_manager.stream_queue.queue_client_stream(user)

        elif action == 'on_unpublish':
            PRIORITY = process_manager.get_priority_key()
            lead_stream_key = process_manager.stream_queue.lead_streamer()

            if PRIORITY and PRIORITY == stream:
                process_manager.set_priority_key(None)
            else:
                if stream and stream == lead_stream_key:
                    process_manager.switch_stream()
                else:
                    process_manager.stream_queue.remove_client_with_stream_key(stream)

    except Exception as e:
        logger.error(f"Error in handle_stream_operations: {e}")

# RTMP handle all callback
@rtmp_blueprint.post("/")
async def on_publish(
    background_tasks: BackgroundTasks,
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
    logger.info(f"RTMP request: {request_obj}")

    forward_stream = {
        "urls": [
            f"rtmp://127.0.0.1:1935/motherstream/live{param}"
        ]
    }
    do_not_forward_stream = {
        "urls": []
    }
    
    record_stream = os.getenv('RECORD_STREAM')
    if record_stream: 
        forward_stream["urls"].append(f"rtmp://127.0.0.1:1936/live/{stream}")

    if app == 'motherstream':
        logger.info("Motherstream app. Doing nothing.")
        return JSONResponse(status_code=200, content={"code": 0, "data": do_not_forward_stream})

    if action == 'on_publish':
        user = await ensure_valid_user(stream)
        if not user:
            return JSONResponse(status_code=401, content={"message": "Invalid stream key. you do not have permission to join the queue."})
        
        # Add stream operations to background tasks
        background_tasks.add_task(handle_stream_operations, stream, user, action)
        return JSONResponse(status_code=200, content={"code": 0, "data": forward_stream})

    elif action == 'on_unpublish':
        # Add stream operations to background tasks
        background_tasks.add_task(handle_stream_operations, stream, None, action)
        return JSONResponse(status_code=401, content={"code": 0, "data": do_not_forward_stream})

    elif action == 'on_forward':
        lead_stream_key = process_manager.stream_queue.lead_streamer()
        if stream and stream == lead_stream_key:
            logger.info(f"----> FORWARDING: {stream}")
            return JSONResponse(status_code=200, content={"code": 0, "data": forward_stream})
        else:
            logger.info(f"----> NOT FORWARDING: {stream}")
            return JSONResponse(status_code=200, content={"code": 0, "data": do_not_forward_stream})

    elif action in ['on_record_begin', 'on_record_end', 'on_ocr']:
        pass
    
    return JSONResponse(status_code=200, content={"message": "Publishing allowed", "code": 0})
