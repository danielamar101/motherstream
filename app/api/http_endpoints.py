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


    
