from fastapi.responses import JSONResponse, HTMLResponse
from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="static")

from main import process_manager

http_blueprint = APIRouter()

@http_blueprint.get('/queue-json')
async def queue_json():
        stream_queue = process_manager.stream_queue.get_dj_name_queue_list()

        return_content = {
             "stream_queue": stream_queue
        }
        return JSONResponse(content=stream_queue)


@http_blueprint.get("/queue-list",response_class=HTMLResponse)
async def queue_list(request: Request):
    return templates.TemplateResponse("queue-list.html", {"request":request})

@http_blueprint.post("/override-queue")
async def override_queue_manually(
    *args,
    **kwarg
):
    pass


@http_blueprint.post("/kill_ffmpeg")
async def kill_ffmpeg():
    process_manager.stop_current_stream()
    return JSONResponse(status_code=200,content={"message": "stopped current stream"})

@http_blueprint.post("/clear-queue")
async def clear_queue():
    
    return JSONResponse(status_code=200, content={"message": "cleared queue."})


