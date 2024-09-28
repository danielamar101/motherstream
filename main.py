from fastapi import FastAPI, Form, BackgroundTasks, status, Request
from fastapi.responses import JSONResponse, RedirectResponse, HTMLResponse
from fastapi.exceptions import RequestValidationError
from contextlib import asynccontextmanager
from obswebsocket import obsws, requests

import subprocess
import threading
import time
import re
import logging
import os
import json

# Global variables
stream_queue = []
current_stream_key = None
current_stream_process = None
queue_lock = threading.Lock()
ffmpeg_out_log = None

logger = logging.getLogger(__name__)

stream_host = os.environ.get('HOST')
rtmp_port = os.environ.get('RTMP_PORT')
if not stream_host or not rtmp_port:
    print("")
    raise Exception("Error: HOST and RTMP_PORT environment variables must be set.")

OBS_HOST = os.environ.get("OBS_HOST")
OBS_PORT = os.environ.get("OBS_PORT")
OBS_PASSWORD = os.environ.get("OBS_PASSWORD")


@asynccontextmanager
async def lifespan(app: FastAPI):
    global ffmpeg_out_log
    global current_stream_key
    global current_stream_process
    global stream_queue

    print("SERVER STARTUP.")
    ffmpeg_out_log = open('ffmpeg.log','w', encoding='utf-8') 

    # import persistent queue in the event of a server timeout
    try:
        if os.path.exists("./QUEUE.json"):
            with open("./QUEUE.json",'r') as queue_file:
                stream_queue = json.load(queue_file)
    except json.JSONDecodeError as e:
        print(f"Error reading input file: {e}")
    except Exception as e:
        print(e)
                
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
def start_stream(stream_key: str):
    global current_stream_process, current_stream_key, stream_host, rtmp_port
    # Sanitize stream_key
    if not re.match(r'^[A-Za-z0-9_-]+$', stream_key):
        print(f"Invalid stream name: {stream_key}")
        raise Exception(f"Invalid stream name. Not starting stream.") 

    # build motherstream restream command
    ffmpeg_cmd = [
        'ffmpeg', "-rw_timeout", "5000000", '-i', f'rtmp://{stream_host}:{rtmp_port}/live/{stream_key}', '-flush_packets', '0', '-fflags', '+genpts', '-max_interleave_delta', '0', '-map', '0:v?', '-map', '0:a?',
        '-copy_unknown', '-c', 'copy', '-f', 'flv', f'rtmp://{stream_host}:{rtmp_port}/motherstream/live'
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

    current_stream_key = stream_key

    print(f"Started streaming live/{stream_key} to motherstream/live")

    threading.Thread(target=log_ffmpeg_output, args=(current_stream_process.stdout, "[FFmpeg stdout]"), daemon=True).start()
    threading.Thread(target=log_ffmpeg_output, args=(current_stream_process.stderr, "[FFmpeg stderr]"), daemon=True).start()

def extend_motherstream():
    import m3u8
    import shutil
    print("In extend_motherstream")
    # Load the existing playlist
    root_path = '/var/www/hls'
    m3u8_file_path = f'{root_path}/live.m3u8'
    updated_m3u8_file_path = f'{root_path}/live.m3u8'

    try:
        # Backup the original .m3u8 file
        shutil.copyfile(m3u8_file_path, m3u8_file_path + '.bak')

        # Load the playlist
        m3u8_obj = m3u8.load(m3u8_file_path)

        # Function to extend playlist with the same segments repeatedly
        def extend_playlist(m3u8_obj, repetitions=2):
            new_segments = m3u8_obj.segments * repetitions  # Repeat the same segments 'repetitions' times
            new_playlist = m3u8.M3U8()
            new_playlist.target_duration = m3u8_obj.target_duration
            new_playlist.media_sequence = m3u8_obj.media_sequence
            for segment in new_segments:
                new_playlist.add_segment(segment)
            return new_playlist

        # Extend playlist
        extended_playlist = extend_playlist(m3u8_obj, repetitions=2)

        print("Doing work...")
        # Save the new playlist to a new file
        with open(updated_m3u8_file_path, 'w') as file:
            file.write(extended_playlist.dumps())
        print(f'Updated .m3u8 file created at {updated_m3u8_file_path}')
    except Exception as e:
        print(e)
    
# Function to stop the current re-streaming process
# Returns stopped stream key
# It is not the responsibility of this function to manage the queue list. That should be done separate of this function
def stop_current_stream():
    global current_stream_process, current_stream_key, ffmpeg_out_log
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
        print(f"Stopped streaming {current_stream_key}")

        to_return = current_stream_key

        current_stream_process = None
        current_stream_key = None

        print("For safe measure, killing all running ffmpeg processes...")
        try:
            subprocess.run(["killall", "ffmpeg"], check=True)
            print("Done killing all running ffmpeg processes.")
        except Exception as e:
            print(f"Error trying to kill all ffmpeg processes: {e}")
        
        ffmpeg_out_log.write("FFMPEG process killed.\n")
        return to_return

def is_streaming(context, stream_key=None, timeout=8):
    global stream_host, rtmp_port
    """
    Check if the given RTMP URL is streaming.
    
    Returns:
    bool: True if the RTMP URL is streaming, False otherwise.
    """

    if context == 'source':
        rtmp_url = f'rtmp://{stream_host}:{rtmp_port}/live/{stream_key}'
    elif context == 'destination':
        rtmp_url = f'rtmp://{stream_host}:{rtmp_port}/motherstream/live'
    else:
        raise Exception("Specify context to be with source or destination.")

    try:
        # Execute the ffprobe command
        cmd = [
            "ffprobe",
            "-v", "error",
            "-show_entries", "stream=index,codec_type",
            "-select_streams", "v",  # Select only video streams
            "-analyzeduration", "5000000", "-probesize", "5000000", "-rw_timeout", "5000000",
            "-of", "json",
            rtmp_url
        ]
        
        # Run the ffprobe command with a timeout
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=timeout)

        # Check if ffprobe returned an empty output or an error message
        if result.returncode != 0 or not result.stdout:
            return False
        
        # Parse the JSON output
        info = json.loads(result.stdout)
        
        # Check if there are any video streams present
        if 'streams' in info and len(info['streams']) > 0:
            return True
        else:
            return False

    except subprocess.TimeoutExpired:
        print(f"ffprobe timed out after {timeout} seconds.")
        return False
    except Exception as e:
        print(f"Error occurred: {e}")
        return False
    
# Background thread to manage the stream queue
def process_queue():
    global stream_queue
    attempt = 1
    attempt_input = 1
    while True:
        with queue_lock:
            # If no current stream and there are streams in the queue
            if not current_stream_process: 
                if stream_queue:
                    print("Starting a stream...")
                    next_stream = stream_queue[0] 
                    try:
                        start_stream(next_stream)
                        # toggle_vlc_obs_source()
                    except Exception as e:
                        print(f"Error starting stream: {e}")
                        stream_queue.pop(0)  


            # If the current stream has ended (ffmpeg process has exited)
            if current_stream_process and current_stream_process.poll() is not None:
                print(f"ffmpeg process for {current_stream_key} ended")
                stop_current_stream()
                unqueue_client_stream()
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

# save updated queue state to persistent store.
def _write_persistent_state():
    
    try:
        with open('QUEUE.json','w') as queue_file:
            queue_file.write(json.dumps(stream_queue))
    except Exception as e:
        print(f'error: {e}')

def queue_client_stream(name):
    global stream_queue
    stream_queue.append(name)
    _write_persistent_state()

def unqueue_client_stream():
    global stream_queue
    stream_queue.pop(0)
    _write_persistent_state()

@app.post("/override-queue")
async def override_queue_manually(
    *args,
    **kwarg
):
    pass

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
        # Will allow streaming but not added to queuing mechanism. TODO: Block this for security purposes
        return JSONResponse(status_code=200, content={"message": f"Not handling this app: {app}"})
    
    with queue_lock:
        if name not in stream_queue:
            queue_client_stream(name)
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
        if name and name == current_stream_key:
            unqueue_client_stream()
            stop_current_stream()
            print(f"Removed {name} from the queue")

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
                ul {{ list-style: none; padding-left: 20px; }}
                li {{ color: white; margin-bottom: 10px; }}
            </style>
        </head>
        <body>
            <h1>Queue</h1>
            <h5 id="next-up">Now Playing:</h5>
            <h5>Next up:</h5>
            <div id="queue-list">
                <!-- The list will be rendered here -->
            </div>
            <script>
                async function fetchQueue() {{
                    try {{
                        const response = await fetch('http://localhost:8483/queue-json');
                        const data = await response.json();
                        const queueList = document.getElementById('queue-list');
                        const nowPlaying = document.getElementById('next-up');
                        
                        // Clear the current list
                        queueList.innerHTML = '';
                        nowPlaying.textContent = 'Now Playing:';

                        // Create a new unordered list element
                        const ul = document.createElement('ul');

                        if (data.length > 0) {{
                            nowPlaying.textContent = `Now Playing: ${{data[0]}}`;
                            // Iterate over the JSON data and create list items


                            data.forEach((item,index) => {{
                                if (index !== 0) {{
                                    const li = document.createElement('li');
                                    li.textContent = item;
                                    ul.appendChild(li);
                                }}
                            }});
                        }}

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

@app.post("/clear-queue")
async def clear_queue():
    global stream_queue
    with open('QUEUE.json','w') as queue_file:
        queue_file.write('[]')
    stream_queue = []
    return JSONResponse(status_code=200, content={"message": "cleared queue."})


