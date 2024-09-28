from fastapi import FastAPI
from contextlib import asynccontextmanager

import subprocess
import threading
import logging
import os

from app.api.exceptions import register_exception
from app.api.process_manager import ProcessManager

from app.queue import StreamQueue

try:
    import debugpy
    debug_port: int = os.environ.get('DEBUG_PORT',5555)
    debugpy.listen(("localhost", int(debug_port)))
    print(f"Debugger listening on port {debug_port}")
except Exception as e:
    print(e)

# Global variables
stream_queue = []
process_manager = None
ffmpeg_out_log = None

logger = logging.getLogger(__name__)

OBS_HOST = os.environ.get("OBS_HOST")
OBS_PORT = os.environ.get("OBS_PORT")
OBS_PASSWORD = os.environ.get("OBS_PASSWORD")

@asynccontextmanager
async def lifespan(app: FastAPI):
    global stream_queue, process_manager, ffmpeg_out_log

    print("SERVER STARTUP.")

    actual_stream_queue = StreamQueue()
    stream_queue = actual_stream_queue.persist_queue()

    yield
    print("SERVER SHUTDOWN")
    ffmpeg_out_log.write("SERVER IS SHUTTING DOWN. KILLING FFMPEG PROCESS...")

    try:
        print("Killing ffmpeg...")
        if actual_stream_queue.get_stream_queue():
            process_manager.current_stream_process.wait(timeout=10)
        print("...done.")
    except Exception as e:
        print(e)
        if actual_stream_queue.get_stream_queue():
            process_manager.current_stream_process.kill()

    ffmpeg_out_log.write("FFMPEG PROCESS KILLED. GOODBYE!")
    ffmpeg_out_log.close()

    print("For safe measure, killing all running ffmpeg processes...")
    try:
        subprocess.run(["killall", "ffmpeg"], check=True)
        print("Done killing all running ffmpeg processes.")
    except Exception as e:
        print(f"Error trying to kill all ffmpeg processes: {e}")


app = FastAPI(lifespan=lifespan)
register_exception(app)

ffmpeg_out_log = open('ffmpeg.log','w', encoding='utf-8')
print('ffmpeg file pipe is open ')

import time
time.sleep(5)
print("Starting process manager...")
process_manager = ProcessManager(ffmpeg_out_log) 

# Start the process queueing thread
print("Starting process queueing thread")
queue_thread = threading.Thread(target=process_manager.process_queue, daemon=True)
queue_thread.start()

from app.api.rtmp_endpoints import rtmp_blueprint
from app.api.http_endpoints import http_blueprint
app.include_router(rtmp_blueprint)
app.include_router(http_blueprint)




