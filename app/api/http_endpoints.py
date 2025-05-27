from fastapi.responses import JSONResponse, HTMLResponse
from fastapi import APIRouter, Request, HTTPException
from fastapi.templating import Jinja2Templates

from app.core.time_manager import TimeManager
from app.obs import obs_socket_manager_instance

templates = Jinja2Templates(directory="static")

from main import process_manager


http_blueprint = APIRouter()

@http_blueprint.get('/song-json')
async def queue_json():
        song_data = process_manager.current_song_data

        return_content = {
             "song_data": song_data,
        }
        return JSONResponse(content=return_content)


@http_blueprint.get("/song-details",response_class=HTMLResponse)
async def queue_list(request: Request):
    return templates.TemplateResponse("song-overlay.html", {"request":request})

@http_blueprint.get('/queue-json')
async def queue_json():
        stream_queue = process_manager.stream_queue.get_dj_name_queue_list()

        return_content = {
             "stream_queue": stream_queue,
        }
        return JSONResponse(content=return_content)


@http_blueprint.get("/queue-list",response_class=HTMLResponse)
async def queue_list(request: Request):
    return templates.TemplateResponse("queue-list.html", {"request":request})

@http_blueprint.get("/timer-data",response_class=HTMLResponse)
async def queue_list():
        if process_manager.time_manager: 
            remaining_time = process_manager.time_manager.get_remaining_time()
        else:
            remaining_time = 0

        return_content = {
                "remaining_time": remaining_time
        }
        return JSONResponse(content=return_content)


@http_blueprint.get("/timer-page",response_class=HTMLResponse)
async def queue_list(request: Request):
    return templates.TemplateResponse("timer.html", {"request":request})


@http_blueprint.post("/update-timer/{time}")
async def update_timer(time: int, reset_time: bool = False):
    """
    Updates the timer with the given time and optional reset_time flag.
    :param time: The time value (int) from the path parameter.
    :param reset_time: A boolean indicating if the time should reset (default: False).
    """

    if time <= 0:
        raise HTTPException(status_code=400, detail="Time must be a positive integer.")

    try:
        process_manager.modify_swap_time(time=time, reset_time=reset_time)
        return {"status": "success", "time": time, "reset_time": reset_time}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@http_blueprint.get("/time-settings")
async def timer_get():
    try:
        if process_manager.time_manager: 
            swap_interval = process_manager.time_manager.get_swap_interval()
            remaining_time = process_manager.time_manager.get_remaining_time()
        else:
            swap_interval = TimeManager().get_swap_interval()
            remaining_time = 0
        return JSONResponse(content={"swap_interval": swap_interval,"remaining_time": remaining_time})

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@http_blueprint.post("/block-toggle")
async def update_toggle():

    try:
        process_manager.toggle_block_previous_client()
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@http_blueprint.get("/block-toggle")
async def get_toggle():

    try:
        is_blocked = process_manager.get_is_blocking_last_streamer()
        return JSONResponse(content={"is_blocked": is_blocked})

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@http_blueprint.post("/obs/toggle-source")
async def toggle_obs_source(
    source_name: str, 
    scene_name: str = "MOTHERSTREAM", 
    toggle_timespan: float = 1.0, 
    only_off: bool = False
):
    """
    Manually toggle any OBS source for testing purposes.
    :param source_name: Name of the source to toggle
    :param scene_name: Name of the scene (default: MOTHERSTREAM)
    :param toggle_timespan: Time to wait between off/on (default: 1.0 seconds)
    :param only_off: If True, only turn off the source (default: False)
    """
    try:
        obs_socket_manager_instance.toggle_obs_source(
            source_name=source_name,
            scene_name=scene_name,
            toggle_timespan=toggle_timespan,
            only_off=only_off
        )
        
        action = "turned off" if only_off else "toggled"
        return {
            "status": "success", 
            "message": f"Successfully {action} source '{source_name}' in scene '{scene_name}'",
            "source_name": source_name,
            "scene_name": scene_name,
            "only_off": only_off
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to toggle OBS source: {str(e)}")

@http_blueprint.post("/obs/restart-media-source")
async def restart_media_source(input_name: str):
    """
    Restart a specific media source in OBS for testing purposes.
    :param input_name: Name of the media input to restart
    """
    try:
        obs_socket_manager_instance.restart_media_source(input_name=input_name)
        
        return {
            "status": "success", 
            "message": f"Successfully triggered restart for media source '{input_name}'",
            "input_name": input_name
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to restart media source: {str(e)}")

@http_blueprint.get("/obs/source-visibility/{source_name}")
async def check_source_visibility(source_name: str, scene_name: str = "MOTHERSTREAM"):
    """
    Check if a source is currently visible in a scene.
    :param source_name: Name of the source to check
    :param scene_name: Name of the scene (default: MOTHERSTREAM)
    """
    try:
        is_visible = obs_socket_manager_instance.is_source_visible(
            source_name=source_name,
            scene_name=scene_name
        )
        
        return {
            "status": "success",
            "source_name": source_name,
            "scene_name": scene_name,
            "is_visible": is_visible
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to check source visibility: {str(e)}")

@http_blueprint.get("/obs/media-input-status/{input_name}")
async def get_media_input_status(input_name: str):
    """
    Get the status of a media input for debugging purposes.
    :param input_name: Name of the media input to check
    """
    try:
        status = obs_socket_manager_instance.get_media_input_status(input_name=input_name)
        
        return {
            "status": "success",
            "input_name": input_name,
            "media_status": status
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get media input status: {str(e)}")

@http_blueprint.get("/obs/list-inputs")
async def list_obs_inputs():
    """
    List all OBS inputs for debugging purposes.
    """
    try:
        inputs = obs_socket_manager_instance.list_inputs()
        
        return {
            "status": "success",
            "inputs": inputs,
            "count": len(inputs)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list OBS inputs: {str(e)}")

@http_blueprint.get("/debug/job-queue-status")
async def get_job_queue_status():
    """
    Get the current status of the job queue for debugging.
    """
    try:
        from app.core.worker import job_queue
        
        return {
            "status": "success",
            "queue_size": job_queue.qsize(),
            "queue_empty": job_queue.empty()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get job queue status: {str(e)}")

@http_blueprint.post("/debug/test-job-toggle")
async def test_job_toggle(
    source_name: str = "GMOTHERSTREAM",
    scene_name: str = "MOTHERSTREAM", 
    only_off: bool = False,
    toggle_timespan: float = 1.0
):
    """
    Test the job queue system by manually adding a toggle job.
    """
    try:
        from app.core.worker import add_job, JobType
        
        add_job(JobType.TOGGLE_OBS_SRC, payload={
            "source_name": source_name,
            "scene_name": scene_name,
            "only_off": only_off,
            "toggle_timespan": toggle_timespan
        })
        
        return {
            "status": "success",
            "message": f"Added TOGGLE_OBS_SRC job to queue",
            "payload": {
                "source_name": source_name,
                "scene_name": scene_name,
                "only_off": only_off,
                "toggle_timespan": toggle_timespan
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to add job to queue: {str(e)}")

@http_blueprint.post("/debug/simulate-stream-switch")
async def simulate_stream_switch():
    """
    Simulate the OBS operations that happen during a stream switch for debugging.
    """
    try:
        from app.core.worker import add_job, JobType
        
        # Simulate the sequence of jobs that happen during stream switching
        jobs_added = []
        
        # 1. Turn off GMOTHERSTREAM (old streamer teardown)
        add_job(JobType.TOGGLE_OBS_SRC, payload={
            "source_name": "GMOTHERSTREAM", 
            "only_off": True, 
            "toggle_timespan": 5
        })
        jobs_added.append("TOGGLE_OBS_SRC (GMOTHERSTREAM off)")
        
        # 2. Restart media source (new streamer setup)
        add_job(JobType.RESTART_MEDIA_SOURCE, payload={
            "source_name": "GMOTHERSTREAM"
        })
        jobs_added.append("RESTART_MEDIA_SOURCE (GMOTHERSTREAM)")
        
        return {
            "status": "success",
            "message": "Simulated stream switch jobs added to queue",
            "jobs_added": jobs_added
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to simulate stream switch: {str(e)}")

@http_blueprint.get("/obs/connection-health")
async def get_obs_connection_health():
    """
    Get the current health status of the OBS websocket connection.
    """
    try:
        is_healthy = obs_socket_manager_instance.is_connection_healthy()
        
        return {
            "status": "success",
            "connection_healthy": is_healthy,
            "message": "OBS connection is healthy" if is_healthy else "OBS connection is not healthy"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to check OBS connection health: {str(e)}")

@http_blueprint.post("/obs/force-reconnect")
async def force_obs_reconnect():
    """
    Force a reconnection attempt to the OBS websocket.
    """
    try:
        # Mark connection as unhealthy to trigger reconnection
        obs_socket_manager_instance._connection_healthy = False
        obs_socket_manager_instance._attempt_reconnect()
        
        # Check if reconnection was successful
        is_healthy = obs_socket_manager_instance.is_connection_healthy()
        
        return {
            "status": "success" if is_healthy else "warning",
            "connection_healthy": is_healthy,
            "message": "Reconnection successful" if is_healthy else "Reconnection attempted but connection still unhealthy"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to force OBS reconnection: {str(e)}")

@http_blueprint.get("/debug/obs-job-delay-config")
async def get_obs_job_delay_config():
    """
    Get the current OBS job delay configuration.
    """
    try:
        from app.core.worker import OBS_JOB_DELAY, last_obs_job_time
        import time
        
        current_time = time.time()
        time_since_last_job = current_time - last_obs_job_time if last_obs_job_time > 0 else None
        
        return {
            "status": "success",
            "obs_job_delay_seconds": OBS_JOB_DELAY,
            "last_obs_job_time": last_obs_job_time,
            "time_since_last_obs_job": time_since_last_job,
            "ready_for_next_obs_job": time_since_last_job is None or time_since_last_job >= OBS_JOB_DELAY
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get OBS job delay config: {str(e)}")

@http_blueprint.post("/debug/update-obs-job-delay")
async def update_obs_job_delay(delay_seconds: float):
    """
    Update the delay between OBS jobs to prevent crashes.
    :param delay_seconds: New delay in seconds (minimum 0.5, maximum 10.0)
    """
    try:
        if delay_seconds < 0.5 or delay_seconds > 10.0:
            raise HTTPException(status_code=400, detail="Delay must be between 0.5 and 10.0 seconds")
        
        # Import and update the global variable
        import app.core.worker as worker_module
        worker_module.OBS_JOB_DELAY = delay_seconds
        
        return {
            "status": "success",
            "message": f"OBS job delay updated to {delay_seconds} seconds",
            "new_delay_seconds": delay_seconds
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update OBS job delay: {str(e)}")

@http_blueprint.get("/debug/obs-health-monitor-config")
async def get_obs_health_monitor_config():
    """
    Get the current OBS health monitoring configuration.
    """
    try:
        config = {
            "status": "success",
            "health_check_interval": obs_socket_manager_instance._health_check_interval,
            "max_reconnect_attempts": obs_socket_manager_instance._max_reconnect_attempts,
            "reconnect_delay": obs_socket_manager_instance._reconnect_delay,
            "current_reconnect_attempts": obs_socket_manager_instance._reconnect_attempts,
            "connection_healthy": obs_socket_manager_instance.is_connection_healthy()
        }
        
        return config
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get OBS health monitor config: {str(e)}")

@http_blueprint.post("/debug/update-obs-health-monitor-config")
async def update_obs_health_monitor_config(
    health_check_interval: int = None,
    max_reconnect_attempts: int = None,
    reconnect_delay: int = None
):
    """
    Update the OBS health monitoring configuration.
    :param health_check_interval: Seconds between health checks (10-300)
    :param max_reconnect_attempts: Maximum reconnection attempts (1-20)
    :param reconnect_delay: Initial reconnection delay in seconds (1-60)
    """
    try:
        updated_fields = []
        
        if health_check_interval is not None:
            if health_check_interval < 10 or health_check_interval > 300:
                raise HTTPException(status_code=400, detail="Health check interval must be between 10 and 300 seconds")
            obs_socket_manager_instance._health_check_interval = health_check_interval
            updated_fields.append(f"health_check_interval: {health_check_interval}s")
        
        if max_reconnect_attempts is not None:
            if max_reconnect_attempts < 1 or max_reconnect_attempts > 20:
                raise HTTPException(status_code=400, detail="Max reconnect attempts must be between 1 and 20")
            obs_socket_manager_instance._max_reconnect_attempts = max_reconnect_attempts
            updated_fields.append(f"max_reconnect_attempts: {max_reconnect_attempts}")
        
        if reconnect_delay is not None:
            if reconnect_delay < 1 or reconnect_delay > 60:
                raise HTTPException(status_code=400, detail="Reconnect delay must be between 1 and 60 seconds")
            obs_socket_manager_instance._reconnect_delay = reconnect_delay
            updated_fields.append(f"reconnect_delay: {reconnect_delay}s")
        
        if not updated_fields:
            raise HTTPException(status_code=400, detail="No valid configuration parameters provided")
        
        return {
            "status": "success",
            "message": f"Updated OBS health monitor config: {', '.join(updated_fields)}",
            "updated_fields": updated_fields
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update OBS health monitor config: {str(e)}")

@http_blueprint.get("/obs/streaming-status")
async def get_obs_streaming_status():
    """
    Get the current OBS streaming status and monitoring configuration.
    """
    try:
        status = obs_socket_manager_instance.get_streaming_status()
        
        return {
            "status": "success",
            **status
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get OBS streaming status: {str(e)}")

@http_blueprint.post("/obs/enable-streaming-monitor")
async def enable_obs_streaming_monitor(enabled: bool = True):
    """
    Enable or disable OBS streaming monitoring and auto-start.
    :param enabled: Whether to enable streaming monitoring (default: True)
    """
    try:
        obs_socket_manager_instance.enable_streaming_monitor(enabled)
        
        return {
            "status": "success",
            "streaming_monitor_enabled": enabled,
            "message": f"OBS streaming monitoring {'enabled' if enabled else 'disabled'}"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update streaming monitor setting: {str(e)}")

@http_blueprint.post("/obs/force-start-streaming")
async def force_start_obs_streaming():
    """
    Manually force OBS to start streaming (bypasses auto-start attempt limits).
    """
    try:
        success = obs_socket_manager_instance.force_start_streaming()
        
        return {
            "status": "success" if success else "warning",
            "streaming_started": success,
            "message": "Successfully started OBS streaming" if success else "Failed to start OBS streaming"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to force start OBS streaming: {str(e)}")

@http_blueprint.get("/obs/check-streaming-now")
async def check_obs_streaming_now():
    """
    Immediately check the current OBS streaming status (bypasses normal check interval).
    """
    try:
        # Force an immediate streaming status check
        obs_socket_manager_instance._check_streaming_status()
        
        # Get the updated status
        status = obs_socket_manager_instance.get_streaming_status()
        
        return {
            "status": "success",
            "message": "Streaming status check completed",
            **status
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to check OBS streaming status: {str(e)}")

@http_blueprint.post("/debug/update-streaming-monitor-config")
async def update_streaming_monitor_config(
    streaming_check_interval: int = None,
    max_auto_start_attempts: int = None,
    auto_start_delay: int = None
):
    """
    Update the OBS streaming monitoring configuration.
    :param streaming_check_interval: Seconds between streaming checks (5-120)
    :param max_auto_start_attempts: Maximum auto-start attempts (1-10)
    :param auto_start_delay: Delay between auto-start attempts in seconds (5-60)
    """
    try:
        updated_fields = []
        
        if streaming_check_interval is not None:
            if streaming_check_interval < 5 or streaming_check_interval > 120:
                raise HTTPException(status_code=400, detail="Streaming check interval must be between 5 and 120 seconds")
            obs_socket_manager_instance._streaming_check_interval = streaming_check_interval
            updated_fields.append(f"streaming_check_interval: {streaming_check_interval}s")
        
        if max_auto_start_attempts is not None:
            if max_auto_start_attempts < 1 or max_auto_start_attempts > 10:
                raise HTTPException(status_code=400, detail="Max auto-start attempts must be between 1 and 10")
            obs_socket_manager_instance._max_auto_start_attempts = max_auto_start_attempts
            updated_fields.append(f"max_auto_start_attempts: {max_auto_start_attempts}")
        
        if auto_start_delay is not None:
            if auto_start_delay < 5 or auto_start_delay > 60:
                raise HTTPException(status_code=400, detail="Auto-start delay must be between 5 and 60 seconds")
            obs_socket_manager_instance._auto_start_delay = auto_start_delay
            updated_fields.append(f"auto_start_delay: {auto_start_delay}s")
        
        if not updated_fields:
            raise HTTPException(status_code=400, detail="No valid configuration parameters provided")
        
        return {
            "status": "success",
            "message": f"Updated OBS streaming monitor config: {', '.join(updated_fields)}",
            "updated_fields": updated_fields
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update streaming monitor config: {str(e)}")


    
