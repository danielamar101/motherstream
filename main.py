from fastapi import FastAPI, Form, BackgroundTasks, status, Request
from fastapi.responses import JSONResponse, RedirectResponse, HTMLResponse
from fastapi.exceptions import RequestValidationError
from contextlib import asynccontextmanager

import subprocess
import threading
import time
import re
import logging
import os

# Global variables
stream_queue = []
current_stream_name = None
current_stream_process = None
queue_lock = threading.Lock()
ffmpeg_out_log = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global ffmpeg_out_log
    global current_stream_name
    global current_stream_process

    print("SERVER STARTUP.")
    ffmpeg_out_log = open('ffmpeg.log','a', encoding='utf-8') 
    yield
    print("SERVER SHUTDOWN")
    ffmpeg_out_log.write("SERVER IS SHUTTING DOWN. KILLING FFMPEG PROCESS...")

    try:
        print("Killing ffmpeg...")
        if current_stream_process:
            current_stream_process.wait(timeout=10)
        print("...done.")
    except Exception as e:
        print(e)
        if current_stream_process:
            current_stream_process.kill()

    ffmpeg_out_log.write("FFMPEG PROCESS KILLED. GOODBYE!")
    ffmpeg_out_log.close()

    print("For safe measure, killing all running ffmpeg processes...")
    try:
        subprocess.run(["killall", "ffmpeg"], check=True)
        print("Done killing all running ffmpeg processes.")
    except Exception as e:
        print(f"Error trying to kill all ffmpeg processes: {e}")

app = FastAPI(lifespan=lifespan)

try:
    import debugpy
    debug_port: int = os.environ.get('DEBUG_PORT',5555)
    debugpy.listen(("localhost", int(debug_port)))
    print(f"Debugger listening on port {debug_port}")
except Exception as e:
    print(e)


def register_exception(app: FastAPI):
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):

        exc_str = f'{exc}'.replace('\n', ' ').replace('   ', ' ')
        logging.getLogger().error(request, exc_str)
        content = {'status_code': 10422, 'message': exc_str, 'data': None}
        return JSONResponse(content=content, status_code=status.HTTP_422_UNPROCESSABLE_ENTITY)

register_exception(app)

def log_ffmpeg_output(pipe, prefix):
    global ffmpeg_out_log
    try:
        for line in iter(pipe.readline, ''):
            if not line:
                break
            formatted_output = f"{prefix} {line.rstrip()}\n"
            ffmpeg_out_log.write(formatted_output)
            ffmpeg_out_log.flush()
    except Exception as e:
        print(f"Error reading FFmpeg output: {e}")
    finally:
        pipe.close()

# Function to start re-streaming a user's stream to motherstream
def start_stream(stream_name: str):
    global current_stream_process, current_stream_name
    # Sanitize stream_name
    if not re.match(r'^[A-Za-z0-9_-]+$', stream_name):
        print(f"Invalid stream name: {stream_name}")
        return
    
    try:
        stream_host = os.environ.get('HOST')
        rtmp_port = os.environ.get('RTMP_PORT')
        if not stream_host or not rtmp_port:
            print("Error: HOST and RTMP_PORT environment variables must be set.")
            return
    except Exception as e:
        print(e)

    # build motherstream restream command
    ffmpeg_cmd = [
        'ffmpeg', '-i', f'rtmp://{stream_host}:{rtmp_port}/live/{stream_name}', '-map', '0',
        '-c', 'copy', '-f', 'flv', f'rtmp://{stream_host}:{rtmp_port}/motherstream/live'
    ]
    print("Starting ffmpeg subprocess...")
    current_stream_process = subprocess.Popen(ffmpeg_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return_code = current_stream_process.poll()
    if return_code is not None:
        print(f"FFmpeg process exited immediately with return code {return_code}")
        # Read any remaining output
        stderr_output, stdout_output = current_stream_process.communicate()
        print(f"FFmpeg stderr:\n{stderr_output}")
        print(f"FFmpeg stdout:\n{stdout_output}")
        return
    print("...done")

    current_stream_name = stream_name

    print(f"Started streaming live/{stream_name} to motherstream")

    threading.Thread(target=log_ffmpeg_output, args=(current_stream_process.stdout, "[FFmpeg stdout]"), daemon=True).start()
    threading.Thread(target=log_ffmpeg_output, args=(current_stream_process.stderr, "[FFmpeg stderr]"), daemon=True).start()


# Function to stop the current re-streaming process
def stop_current_stream():
    global current_stream_process, current_stream_name
    if current_stream_process:
        try:
            print("Terminating ffmpeg process...")
            current_stream_process.terminate()
            current_stream_process.wait(timeout=10)
            print("ffmpeg process terminated")
        except Exception as e:
            print(e)
            current_stream_process.kill()
            print("ffmpeg process killed")
        print(f"Stopped streaming {current_stream_name}")
        current_stream_process = None
        current_stream_name = None

        print("For safe measure, killing all running ffmpeg processes...")
        try:
            subprocess.run(["killall", "ffmpeg"], check=True)
            print("Done killing all running ffmpeg processes.")
        except Exception as e:
            print(f"Error trying to kill all ffmpeg processes: {e}")

# Background thread to manage the stream queue
def process_queue():
    while True:
        with queue_lock:
            # If no current stream and there are streams in the queue
            if not current_stream_process and stream_queue:
                print("Starting a stream...")
                next_stream = stream_queue[0] 
                start_stream(next_stream)

            # If the current stream has ended (ffmpeg process has exited)
            if current_stream_process and current_stream_process.poll() is not None:
                print(f"ffmpeg process for {current_stream_name} ended")
                stop_current_stream()

                if current_stream_name in stream_queue:
                    stream_queue.remove(current_stream_name)
        time.sleep(5) 

# Start the process queueing thread
queue_thread = threading.Thread(target=process_queue, daemon=True)
queue_thread.start()

# RTMP on_connect callback
@app.post("/on_connect")
async def on_connect(
    app: str = Form(...),
    flashver: str = Form(...),
    swfurl: str = Form(...),
    tcurl: str = Form(...),
    pageurl: str = Form(...),
    addr: str = Form(...),
    epoch: str = Form(...),
    call: str = Form(...)
):
    print("on_connect")

    payload = {
    "app": app,
    "flashver": flashver,
    "swfurl": swfurl,
    "tcurl": tcurl,
    "pageurl": pageurl,
    "addr": addr,
    "epoch": epoch,
    "call": call
}
    #TODO: Implement auth logic here.
    # NOTE: the call var to distinguish between play/publish 
    # 
    # Specifications:
    # 1. Authenticate stream key/IP address
	# 1a. Check if DJ is registered in DB
	# 1b. Check if IP address matches expected
	# 1c. Obtain the DJ data object for later


    print(payload)
    print(f"[on_connect] Client connected to {app} from {addr}")
    return JSONResponse(status_code=200, content={"message": "Connection allowed"})

# RTMP on_publish callback
@app.post("/on_publish")
async def on_publish(
    app: str = Form(...),
    name: str = Form(...),
    flashver: str = Form(...),
    swfurl: str = Form(...),
    tcurl: str = Form(...),
    pageurl: str = Form(...),
    addr: str = Form(...),
    call: str = Form(...)
):
    print(f"[on_publish] Stream {name} started by client {addr} in app {app}")
    if app != 'live':
        return JSONResponse(status_code=200, content={"message": f"Not handling this app: {app}"})
    with queue_lock:
        if name not in stream_queue:
            stream_queue.append(name)
            print(f"Added {name} to the queue")
    return JSONResponse(status_code=200, content={"message": "Publishing allowed"})

# RTMP on_publish_done callback
@app.post("/on_publish_done")
async def on_publish_done(
    app: str = Form(...),
    name: str = Form(None),
    flashver: str = Form(...),
    swfurl: str = Form(...),
    tcurl: str = Form(...),
    pageurl: str = Form(...),
    addr: str = Form(...),
    call: str = Form(...)
):
    print(f"[on_publish_done] Stream {name} stopped by client in app {app}")
    with queue_lock:
        if name and name in stream_queue:
            stream_queue.remove(name)
            print(f"Removed {name} from the queue")
        if name and name == current_stream_name:
            stop_current_stream()
    return JSONResponse(status_code=200, content={"message": "Publish done"})

# RTMP on_done callback
@app.post("/on_done")
async def on_done(
    app: str = Form(...),
    name: str = Form(None),
    flashver: str = Form(...),
    swfurl: str = Form(...),
    tcurl: str = Form(...),
    pageurl: str = Form(...),
    addr: str = Form(...),
    call: str = Form(...)
):
    if name:
        print(name)
    print(f"[on_done] Client disconnected from {app}")
    return JSONResponse(status_code=200, content={"message": "Disconnected"})


@app.get("/queue-list",response_class=HTMLResponse)
async def queue_list():
    global stream_queue
    return f"""
    <html>
        <head>
            <title>Queue</title>
            <meta http-equiv="refresh" content="10">
            <style>
                body {{ color: white; font-family: Arial, sans-serif; }}
                ul {{ list-style-type: disc; padding-left: 20px; }}
                li {{ color: white; margin-bottom: 10px; }}
            </style>
        </head>
        <body>
            <h1>Queue</h1>
            <div id="queue-list">
                <!-- The list will be rendered here -->
            </div>
            <script>
                async function fetchQueue() {{
                    try {{
                        const response = await fetch('http://192.168.1.100:8483/queue-json');
                        const data = await response.json();
                        const queueList = document.getElementById('queue-list');
                        
                        // Clear the current list
                        queueList.innerHTML = '';

                        // Create a new unordered list element
                        const ul = document.createElement('ul');

                        // Iterate over the JSON data and create list items
                        data.forEach(item => {{
                            const li = document.createElement('li');
                            li.textContent = item;
                            ul.appendChild(li);
                        }});

                        // Append the new list to the div
                        queueList.appendChild(ul);
                    }} catch (error) {{
                        console.error('Error fetching queue:', error);
                    }}
                }}

                // Fetch and render the queue immediately
                fetchQueue();

                // Refresh the queue every 10 seconds
                setInterval(fetchQueue, 10000);
            </script>
        </body>
    </html>
    """

@app.get('/queue-json')
async def queue_json():
        global stream_queue
        return JSONResponse(content=stream_queue)


@app.post("/on_play")
async def on_connect(
    app: str = Form(...),
    flashver: str = Form(...),
    swfurl: str = Form(...),
    tcurl: str = Form(...),
    pageurl: str = Form(...),
    addr: str = Form(...),
    call: str = Form(...)
):
    payload = {
    "app": app,
    "flashver": flashver,
    "swfurl": swfurl,
    "tcurl": tcurl,
    "pageurl": pageurl,
    "addr": addr,
    "call": call
    }

    print(payload)

    print(f"[on_play] Client is playing app: {app} from {addr}")
    return JSONResponse(status_code=200, content={"message": "Play allowed"})

@app.post("/kill_ffmpeg")
async def kill_ffmpeg():
    stop_current_stream()
    return JSONResponse(status_code=200,content={"message": "stopped current stream"})


