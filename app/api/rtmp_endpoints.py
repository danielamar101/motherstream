from fastapi.responses import JSONResponse
from fastapi import Form, APIRouter, Body

from main import process_manager
from ..lock_manager import lock as queue_lock, state_lock
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
        # RTMP hook logging disabled for cleaner logs
        # print("Motherstream app. Doing nothing.")
        return JSONResponse(status_code=200, content={"code": 0, "data": do_not_forward_stream})


    if action == 'on_unpublish':
        # Atomically check state and determine action
        should_switch = False
        with queue_lock:
            with state_lock:
                PRIORITY = process_manager.priority_key
                lead_stream_key = process_manager.stream_queue.lead_streamer()
                
                # Case 1: Not the lead streamer, just remove from queue
                if stream and stream != lead_stream_key:
                    logger.info(f"Removing non-lead streamer {stream} from queue")
                    process_manager.stream_queue.remove_client_with_stream_key(stream)
                    return JSONResponse(status_code=200, content={"code": 0, "data": do_not_forward_stream})
                
                # Case 2: Priority streamer disconnecting
                if PRIORITY and PRIORITY == stream:
                    logger.info(f"Priority streamer {stream} disconnecting")
                    process_manager.priority_key = None
                    
                    # Check if this priority streamer is also the lead streamer
                    if stream == lead_stream_key:
                        logger.info(f"Priority streamer {stream} is the lead - will switch to next streamer")
                        should_switch = True
                    else:
                        # Hide GStreamer source and disable health checks when priority streamer disconnects
                        # but they're not the lead (reconnection case)
                        process_manager.stream_health_checker.disable()
                        logger.info(f"Disabled health checks for {stream}")
                        return JSONResponse(status_code=200, content={"code": 0, "data": do_not_forward_stream})
                
                # Case 3: Lead streamer disconnecting - need to switch
                if stream and stream == lead_stream_key:
                    should_switch = True
                else:
                    # Case 4: Other streamer, just remove
                    logger.info(f"Removing streamer {stream} from queue")
                    process_manager.stream_queue.remove_client_with_stream_key(stream)
                    return JSONResponse(status_code=200, content={"code": 0, "data": do_not_forward_stream})
        
        # Call switch_stream OUTSIDE the locks to avoid deadlock
        if should_switch:
            logger.info(f"Lead streamer {stream} disconnecting, switching stream")
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
        
        # Atomically check state and determine action
        should_start_stream = False
        with queue_lock:
            with state_lock:
                lead_stream_key = process_manager.stream_queue.lead_streamer()
                last_stream_key = process_manager.last_stream_key
                BLOCKING = process_manager.is_blocking_last_streamer
                
                logger.info(f"on_publish: stream={stream}, BLOCKING={BLOCKING}, LEAD={lead_stream_key}, LAST={last_stream_key}")
                
                # Case 1: Queue is empty - potentially start this stream immediately
                if not lead_stream_key:
                    # Check if this user was just blocked
                    if last_stream_key and BLOCKING and last_stream_key == stream:
                        logger.info(f"Blocking {stream} - recently kicked")
                        return JSONResponse(status_code=401, content={"code": 0, "data": do_not_forward_stream})
                    
                    # Clear last streamer key if we're allowing them back
                    if last_stream_key:
                        process_manager.last_stream_key = None
                    
                    # Try to add to queue atomically
                    was_added = process_manager.stream_queue.queue_client_stream_if_not_exists(user)
                    if was_added:
                        should_start_stream = True
                    else:
                        logger.info(f"Stream {stream} already in queue")
                        return JSONResponse(status_code=200, content={"code": 0, "data": do_not_forward_stream})
                
                # Case 2: This IS the lead streamer (reconnecting)
                elif lead_stream_key == stream:
                    logger.info(f"Lead streamer {stream} reconnecting")
                    # Re-enable health checks and show GStreamer source when lead streamer reconnects
                    from app.core.worker import add_job, JobType
                    rtmp_url = process_manager.get_rtmp_url(stream_key=stream)
                    process_manager.stream_health_checker.update_stream_url(rtmp_url)
                    logger.info(f"Re-enabled health checks for reconnected lead streamer {stream}")
                    return JSONResponse(status_code=200, content={"code": 0, "data": forward_stream})
                
                # Case 3: Someone else is lead - join the queue
                else:
                    was_added = process_manager.stream_queue.queue_client_stream_if_not_exists(user)
                    if was_added:
                        logger.info(f"Stream {stream} joining queue (lead: {lead_stream_key})")
                    else:
                        logger.info(f"Stream {stream} already in queue")
                    return JSONResponse(status_code=200, content={"code": 0, "data": do_not_forward_stream})
        
        # Start stream OUTSIDE the locks (it does I/O operations)
        if should_start_stream:
            logger.info(f"Starting stream for {stream}")
            process_manager.start_stream(user)
            return JSONResponse(status_code=200, content={"code": 0, "data": forward_stream})
    elif action == 'on_record_begin':
        pass
    elif action == 'on_record_end':
        pass
    elif action == 'on_ocr':
        pass
    
    return JSONResponse(status_code=200, content={"message": "Publishing allowed", "code": 0})
