from fastapi.responses import JSONResponse, HTMLResponse
from fastapi import APIRouter, Request, HTTPException
from fastapi.templating import Jinja2Templates

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
async def update_timer():
    try:
        swap_interval = process_manager.time_manager.get_swap_interval()
        remaining_time = process_manager.time_manager.get_remaining_time()
        return JSONResponse(content={"swap_interval": swap_interval,"remaining_time": remaining_time})

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@http_blueprint.post("/block-toggle")
async def update_timer():

    try:
        process_manager.toggle_block_previous_client()
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@http_blueprint.get("/block-toggle")
async def update_timer():

    try:
        is_blocked = process_manager.get_is_blocking_last_streamer()
        return JSONResponse(content={"is_blocked": is_blocked})

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


    
